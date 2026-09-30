"""单个 ``.jianpack`` 工程文件的读写（JIANPACK2 容器）。

格式（v2）::

    [固定头 64 字节]
        0   魔数 b"JIANPACK"
        8   格式版本 u32 LE (=2)
        12  索引(manifest)偏移 u64 LE
        20  索引长度       u64 LE
        28  保留（占位）
    [数据块 ...]         每个"版本"一块：该版本内容的内部 ZIP（各自是一个完整 zip）
    [索引 manifest.json] 放在文件末尾；**只有它会经常被改写**

设计目标：
- **切换版本只改索引**：数据块原地不动，切换只需追加一个小索引 + 改头里 16 字节；
- **保存只重写当前版本那一块**（其它版本的数据块原样保留）；
- 打开时**只解"当前版本"那一块**，其余版本按需（切过去时）再解。

老格式（zip 容器）**不再支持**；不带 ``versions.json`` 的文件夹工程（纯 JSON）
仍保留给开发/自检用（由 ``sniff`` 区分）。
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

from ..i18n import t as _
from .errors import ProjectFileError

PROJECT_JSON = "project.json"

# 工程文件扩展名（唯一）。
PROJECT_EXT = ".jianpack"

WORK_PREFIX = "简包装-工程-"

# ---- 新格式常量 ----
MAGIC = b"JIANPACK"
FORMAT = 2
HEADER_SIZE = 64

# 打进"版本数据块"时要排除的顶层名字（这些属于容器/工程自身的管理文件）
_BLOCK_EXCLUDE = {"build", "versions", "versions.json", "manifest.json"}
# 超过这个大小就不压缩：省 CPU，反正里面的程序文件多半已经是压过的
STORE_THRESHOLD = 64 * 1024
# 索引里每个版本保留的元信息字段（顺序即写文件顺序）
META_FIELDS = ("id", "label", "version", "fileVersion", "note", "createdAt",
               "seq", "locked", "payloadStored", "payloadTops")
# 垃圾（被替换掉的旧数据块）超过这个量、且占比够大，就做一次压实
COMPACT_MIN_GARBAGE = 16 * 1024 * 1024
COMPACT_RATIO = 0.35


# ---------------------------------------------------------------------------
# 读取辅助
# ---------------------------------------------------------------------------

def sniff(path: str | Path) -> str:
    """判断一个 ``.jianpack`` 是哪一种：

    ``container`` = 新格式容器；``json`` = 老的文件夹工程（纯 JSON）；``missing``。
    """
    path = Path(path)
    if not path.is_file():
        return "missing"
    try:
        with path.open("rb") as handle:
            head = handle.read(len(MAGIC))
    except OSError:
        return "missing"
    if head == MAGIC:
        return "container"
    if head[:1] == b"{":
        return "json"
    return "other"


def _read_header(handle) -> tuple[int, int]:
    head = handle.read(HEADER_SIZE)
    if len(head) < HEADER_SIZE or head[:len(MAGIC)] != MAGIC:
        raise ProjectFileError(_("这个 .jianpack 不是有效的工程文件（文件头不对）。"))
    version = int.from_bytes(head[8:12], "little")
    if version != FORMAT:
        raise ProjectFileError(
            _("不支持的工程文件版本：{version}（本程序支持 {now}）。").format(
                version=version, now=FORMAT))
    offset = int.from_bytes(head[12:20], "little")
    length = int.from_bytes(head[20:28], "little")
    return offset, length


def _write_header(handle, manifest_offset: int, manifest_length: int) -> None:
    head = bytearray(HEADER_SIZE)
    head[0:len(MAGIC)] = MAGIC
    head[8:12] = FORMAT.to_bytes(4, "little")
    head[12:20] = int(manifest_offset).to_bytes(8, "little")
    head[20:28] = int(manifest_length).to_bytes(8, "little")
    handle.seek(0)
    handle.write(bytes(head))


def read_manifest(path: str | Path) -> dict:
    """只读文件末尾的索引（很小，不会解压任何数据块）。"""
    path = Path(path)
    try:
        with path.open("rb") as handle:
            offset, length = _read_header(handle)
            handle.seek(offset)
            raw = handle.read(length)
    except OSError as exc:
        raise ProjectFileError(_("读不了这个工程文件：{exc}").format(exc=exc)) from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectFileError(_("工程文件的索引损坏了：{exc}").format(exc=exc)) from exc
    if not isinstance(data, dict):
        raise ProjectFileError(_("工程文件的索引格式不对。"))
    return data


def _write_manifest(path: Path, manifest: dict) -> None:
    payload = json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")
    with path.open("r+b") as handle:
        handle.seek(0, os.SEEK_END)
        offset = handle.tell()
        handle.write(payload)
        _write_header(handle, offset, len(payload))
        handle.flush()


def load_versions_json(manifest: dict) -> dict:
    """把索引变成"磁盘上的 versions.json"（只留元信息，不含数据块位置）。"""
    items = []
    for entry in manifest.get("versions") or []:
        items.append({k: entry[k] for k in META_FIELDS if k in entry})
    try:
        keep = int(manifest.get("keep") or 2)
    except (TypeError, ValueError):
        keep = 2
    return {"keep": keep, "current": str(manifest.get("current") or ""),
            "items": items, "rebuild": []}


# ---------------------------------------------------------------------------
# 把容器里的一段当作独立文件（给 zipfile 用；偏移从 0 开始）
# ---------------------------------------------------------------------------

class _Cancelled(Exception):
    """后台解压被要求中止（关软件时用）。"""


class _Region(io.RawIOBase):
    """容器文件 ``[base, base+length)`` 这一段，冒充成一个从 0 开始的文件。

    这样写进去的内部 zip 记的是**相对偏移**，数据块以后挪位置也不会坏。
    写入时若超出 ``length`` 会被截断（调用方据此判断"原地放不下"）。
    """

    def __init__(self, handle, base: int, length: int | None) -> None:
        self._handle = handle
        self._base = int(base)
        self._length = length
        self._pos = 0
        self._max = 0
        self.overflowed = False

    # -- 基本属性 --
    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    @property
    def size(self) -> int:
        return self._max

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            pos = offset
        elif whence == 1:
            pos = self._pos + offset
        elif whence == 2:
            if self._length is None:
                raise OSError("cannot seek from end of an open-ended region")
            pos = self._length + offset
        else:
            raise ValueError(f"invalid whence: {whence}")
        if pos < 0:
            pos = 0
        self._pos = pos
        return pos

    def read(self, size: int = -1) -> bytes:
        if self._length is None:
            limit = None
        else:
            limit = max(0, self._length - self._pos)
        if size is None or size < 0:
            size = limit if limit is not None else -1
        elif limit is not None:
            size = min(size, limit)
        if size == 0:
            return b""
        self._handle.seek(self._base + self._pos)
        data = self._handle.read(size)
        self._pos += len(data)
        return data

    def write(self, data) -> int:
        if self._length is not None:
            room = self._length - self._pos
            if room <= 0:
                self.overflowed = True
                self._max = max(self._max, self._length)
                return 0
            if len(data) > room:
                data = data[:room]
                self.overflowed = True
        self._handle.seek(self._base + self._pos)
        written = self._handle.write(data)
        self._pos += written
        self._max = max(self._max, self._pos)
        return written

    def flush(self) -> None:      # 不关底层文件，只是把缓冲写下去
        try:
            self._handle.flush()
        except Exception:         # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# 数据块
# ---------------------------------------------------------------------------

def _has_payload(directory: Path, tops) -> bool:
    """目录里 ``tops`` 指向的顶层条目是否"非空"（空文件夹不算有程序文件）。"""
    for top in tops or []:
        path = directory / str(top)
        try:
            if path.is_dir():
                if any(path.iterdir()):
                    return True
            elif path.exists():
                return True
        except OSError:
            continue
    return False


def _write_block(handle, src_dir: Path, skip: frozenset[str] = frozenset()) -> tuple[int, int]:
    """把 ``src_dir`` 打成一个内部 zip 追加到 ``handle`` 末尾，返回 (偏移, 长度)。

    ``skip`` 是"顶层要跳过的文件名"——用来避免把容器自己（工程文件正写在它里面时）
    又打进去，那会自我包含、越滚越大。
    """
    handle.seek(0, os.SEEK_END)
    base = handle.tell()
    region = _Region(handle, base, None)
    with zipfile.ZipFile(region, "w", allowZip64=True) as archive:
        for path in sorted(src_dir.rglob("*")):
            if not path.is_file():
                continue
            if skip and path.parent == src_dir and path.name in skip:
                continue
            rel = path.relative_to(src_dir).as_posix()
            if rel.split("/", 1)[0] in _BLOCK_EXCLUDE:
                continue
            if rel.endswith(".tmp"):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            method = zipfile.ZIP_STORED if size > STORE_THRESHOLD else zipfile.ZIP_DEFLATED
            archive.write(path, rel, compress_type=method)
    return base, region.size


def _rewrite_block(handle, src_dir: Path, slot_offset: int, slot_length: int,
                   skip: frozenset[str] = frozenset()) -> tuple[int, int] | None:
    """尝试把数据块**原地**写进旧槽位；放不下就返回 None（调用方改追加）。"""
    region = _Region(handle, slot_offset, slot_length)
    try:
        with zipfile.ZipFile(region, "w", allowZip64=True) as archive:
            for path in sorted(src_dir.rglob("*")):
                if not path.is_file():
                    continue
                if skip and path.parent == src_dir and path.name in skip:
                    continue
                rel = path.relative_to(src_dir).as_posix()
                if rel.split("/", 1)[0] in _BLOCK_EXCLUDE or rel.endswith(".tmp"):
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                method = (zipfile.ZIP_STORED if size > STORE_THRESHOLD
                          else zipfile.ZIP_DEFLATED)
                archive.write(path, rel, compress_type=method)
    except Exception:  # noqa: BLE001 - 原地写失败就当放不下
        return None
    if region.overflowed or region.size > slot_length:
        return None
    return slot_offset, region.size


def _copy_region(src: Path, offset: int, length: int, out) -> None:
    with src.open("rb") as handle:
        handle.seek(offset)
        remaining = length
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            out.write(chunk)
            remaining -= len(chunk)


def _extract_block(handle, offset: int, length: int, out_dir: Path, root: Path,
                   state: dict, progress, should_stop=None) -> None:
    """把一个数据块（内部 zip）解到 ``out_dir``。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    region = _Region(handle, offset, length)
    with zipfile.ZipFile(region) as archive:
        for info in archive.infolist():
            if should_stop is not None and should_stop():
                raise _Cancelled()
            if info.is_dir():
                continue
            if info.file_size > (8 << 30):
                raise ProjectFileError(
                    _("工程文件的数据块看起来损坏了（条目异常大）：{name}").format(
                        name=info.filename))
            name = info.filename.replace("\\", "/")
            parts = name.split("/")
            if name.startswith("/") or any(part in ("..", "") for part in parts[:-1]):
                raise ProjectFileError(
                    _("工程文件里有非法路径，已拒绝：{name}").format(name=name))
            target = (out_dir / name).resolve()
            base = out_dir.resolve()
            if target != base and base not in target.parents:
                raise ProjectFileError(
                    _("工程文件里有越界路径，已拒绝：{name}").format(name=name))
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out, 1024 * 256)
            state["done"] += 1
            if progress is not None:
                try:
                    progress(state["done"], state["total"], name)
                except Exception:  # noqa: BLE001 - 进度回调失败不该影响解压
                    pass


def _block_file_count(handle, offset: int, length: int) -> tuple[int, int]:
    """数一个数据块里的文件数和未压缩总大小（只读中央目录，很快）。"""
    region = _Region(handle, offset, length)
    try:
        with zipfile.ZipFile(region) as archive:
            infos = [i for i in archive.infolist() if not i.is_dir()]
            return len(infos), sum(i.file_size for i in infos)
    except (zipfile.BadZipFile, OSError):
        return 0, 0


# ---------------------------------------------------------------------------
# 解压 / 写回
# ---------------------------------------------------------------------------

def extract(container: str | Path, dest: str | Path, progress=None) -> Path:
    """把容器解到 ``dest``。

    - **当前版本**的数据块解到 ``dest`` 根目录；
    - 其余版本**暂不解**（切换过去时再按需解，见 :func:`materialize`）；
    - 最后把索引里的元信息写成 ``dest/versions.json``，供版本面板读取。

    ``progress`` 可选：``progress(已处理数, 总数, 当前文件名)``。
    """
    container = Path(container)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    manifest = read_manifest(container)
    current = str(manifest.get("current") or "")
    versions = [v for v in (manifest.get("versions") or []) if isinstance(v, dict)]
    data = manifest.get("data")

    jobs: list[tuple[int, int, Path]] = []
    if data and not versions:
        jobs.append((int(data.get("off", 0)), int(data.get("len", 0)), dest))
    for entry in versions:
        vid = str(entry.get("id") or "")
        if vid and vid == current:
            jobs.append((int(entry.get("off", 0)), int(entry.get("len", 0)), dest))

    total = 0
    total_size = 0
    with container.open("rb") as handle:
        for offset, length, _out in jobs:
            count, size = _block_file_count(handle, offset, length)
            total += count
            total_size += size
    _ensure_space(dest, total_size, _("解开这个工程"))

    state = {"done": 0, "total": max(1, total)}
    with container.open("rb") as handle:
        for offset, length, out in jobs:
            _extract_block(handle, offset, length, out, root, state, progress)

    if not (dest / PROJECT_JSON).is_file():
        raise ProjectFileError(_("这个 .jianpack 里没有 project.json，可能不是本软件的工程。"))
    sync_versions_file(dest, manifest)
    return dest


def materialize(container: str | Path, dest: str | Path, version_id: str,
                should_stop=None) -> Path:
    """把某个版本的数据块解到 ``dest/versions/<id>/``（切换过去之前调用）。"""
    container = Path(container)
    dest = Path(dest)
    manifest = read_manifest(container)
    root = dest.resolve()
    for entry in manifest.get("versions") or []:
        if str(entry.get("id") or "") != version_id:
            continue
        out = dest / "versions" / version_id
        if (out / PROJECT_JSON).is_file():
            return out
        state = {"done": 0, "total": 1}
        with container.open("rb") as handle:
            _extract_block(handle, int(entry.get("off", 0)), int(entry.get("len", 0)),
                           out, root, state, None, should_stop)
        return out
    raise ProjectFileError(_("这个版本的数据块不见了，无法切换。"))


def missing_versions(container: str | Path, dest: str | Path) -> list[str]:
    """还没解到磁盘的版本 id（打开后可以让后台慢慢把它们解出来）。"""
    try:
        manifest = read_manifest(container)
    except ProjectFileError:
        return []
    dest = Path(dest)
    out: list[str] = []
    for entry in manifest.get("versions") or []:
        vid = str(entry.get("id") or "")
        if vid and not (dest / "versions" / vid / PROJECT_JSON).is_file():
            out.append(vid)
    return out


def payload_tops_of_dir(directory: str | Path) -> list[str]:
    """从某个版本目录里的 ``project.json`` 算出它的"打包内容"顶层条目。

    比索引里记的 ``payloadTops`` 可靠 —— 索引里可能是老版本留下的脏数据
    （比如"没有程序文件"却留着 70MB 的数据块，就是这么来的）。
    """
    directory = Path(directory)
    try:
        data = json.loads((directory / PROJECT_JSON).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    files = data.get("files")
    raw = files.get("items") if isinstance(files, dict) else None
    try:
        base = directory.resolve()
    except OSError:
        return []
    tops: list[str] = []
    for entry in (raw or []):
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("source") or "").strip()
        if not rel:
            continue
        name = Path(rel)
        top = ""
        if name.is_absolute():
            try:
                parts = name.resolve().relative_to(base).parts
                top = parts[0] if parts else ""
            except (ValueError, OSError):
                top = ""
        else:
            parts = [x for x in rel.replace("\\", "/").split("/") if x not in ("", ".")]
            if parts and parts[0] != "..":
                top = parts[0]
        if top and top not in tops:
            tops.append(top)
    return tops


def block_tops(container: str | Path, version_id: str) -> set[str] | None:
    """某个版本的数据块里**实际**装了哪些顶层条目（只读中央目录，很快）。

    用它可以判断"索引说没有程序文件、块里其实还有"的脏数据；读不出来就返回 None。
    """
    container = Path(container)
    try:
        manifest = read_manifest(container)
    except ProjectFileError:
        return None
    for entry in manifest.get("versions") or []:
        if str(entry.get("id") or "") != version_id:
            continue
        try:
            with container.open("rb") as handle:
                region = _Region(handle, int(entry.get("off", 0)), int(entry.get("len", 0)))
                with zipfile.ZipFile(region) as archive:
                    tops: set[str] = set()
                    for info in archive.infolist():
                        if info.is_dir():
                            continue
                        name = info.filename.replace("\\", "/")
                        top = name.split("/", 1)[0]
                        if top and top not in _BLOCK_EXCLUDE:
                            tops.add(top)
                    return tops
        except (zipfile.BadZipFile, OSError, KeyError, ValueError):
            return None
    return None


def block_sizes(container: str | Path) -> dict[str, int]:
    """每个版本数据块的字节数（按 id）——"占用"列在版本还没解到磁盘时用它。"""
    try:
        manifest = read_manifest(container)
    except ProjectFileError:
        return {}
    sizes: dict[str, int] = {}
    for entry in manifest.get("versions") or []:
        vid = str(entry.get("id") or "")
        if vid:
            sizes[vid] = int(entry.get("len", 0))
    return sizes


def sync_versions_file(dest: Path, manifest: dict) -> None:
    """把索引里的版本元信息写成 ``dest/versions.json``（供版本面板读取）。"""
    payload = load_versions_json(manifest)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    (dest / "versions.json").write_text(text, encoding="utf-8")


def save(target: str | Path, base_dir: str | Path, versions_json: dict,
         source: str | Path | None = None) -> dict:
    """把工程写回容器。

    - **原地保存**（``target`` 就是当前容器）：只重建"当前版本"和
      ``versions_json['rebuild']`` 里列出的版本；其它版本的数据块原样保留。
    - **另存为 / 新建**：``source`` 给旧容器时，未重建的版本数据块**原样搬运**；
      否则所有版本都重建。
    """
    target = Path(target)
    base_dir = Path(base_dir)
    src = Path(source) if source is not None else target

    items = [it for it in (versions_json.get("items") or []) if isinstance(it, dict)]
    current = str(versions_json.get("current") or "")
    try:
        keep = int(versions_json.get("keep") or 2)
    except (TypeError, ValueError):
        keep = 2
    rebuild = {str(x) for x in (versions_json.get("rebuild") or [])}
    if current:
        rebuild.add(current)
    metas = {str(it.get("id")): it for it in items if it.get("id")}

    in_place = (target.is_file() and target.resolve() == src.resolve()
                and sniff(target) == "container")
    old: dict | None = None
    if sniff(src) == "container":
        try:
            old = read_manifest(src)
        except ProjectFileError:
            old = None
    old_blocks: dict[str, tuple[int, int]] = {
        str(v.get("id")): (int(v.get("off", 0)), int(v.get("len", 0)))
        for v in (old or {}).get("versions", []) if v.get("id")}
    old_data = None
    if old and old.get("data"):
        old_data = (int(old["data"]["off"]), int(old["data"]["len"]))

    if not in_place and old is None:
        # 源不是新格式容器（例如从文件夹工程另存为）→ 所有版本都得重建
        rebuild = set(metas)
        old_blocks = {}

    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "r+b" if in_place else "wb"
    new_blocks: dict[str, tuple[int, int]] = {}
    data_rec: tuple[int, int] | None = None

    def dir_of(vid: str) -> Path:
        return base_dir if vid == current else (base_dir / "versions" / vid)

    with target.open(mode) as handle:
        if not in_place:
            _write_header(handle, 0, 0)
            handle.seek(HEADER_SIZE)
            # 另存为：没重建的版本，数据块原样搬运（不重新压缩）
            if old is not None:
                for vid, (old_off, old_len) in old_blocks.items():
                    if vid in rebuild or vid not in metas:
                        continue
                    new_off = handle.tell()
                    _copy_region(src, old_off, old_len, handle)
                    new_blocks[vid] = (new_off, old_len)
                if old_data is not None and not items:
                    new_off = handle.tell()
                    _copy_region(src, old_data[0], old_data[1], handle)
                    data_rec = (new_off, old_data[1])

        # 1) 重建：当前版本 + rebuild 里列出的版本
        skip_root = frozenset({target.name, target.name + ".tmp"})
        for vid in sorted(rebuild):
            directory = dir_of(vid)
            if not directory.is_dir():
                continue
            if directory != base_dir and not (directory / PROJECT_JSON).is_file():
                # 目录只是"半截"（后台还在解 / 上次没解完）→ 不要拿它写数据块，
                # 保留旧块更安全（下次真正解好后再重写）。
                continue
            skip = skip_root if directory == base_dir else frozenset()
            slot = old_blocks.get(vid)
            written = None
            if in_place and slot is not None:
                written = _rewrite_block(handle, directory, slot[0], slot[1], skip)
            if written is None:
                written = _write_block(handle, directory, skip)
            new_blocks[vid] = written

        # 2) 没有版本时：把根目录内容作为"根数据块"
        if not items and data_rec is None:
            data_rec = _write_block(handle, base_dir, skip_root)

        # 3) 组装新索引
        versions: list[dict] = []
        for item in items:
            vid = str(item.get("id") or "")
            if not vid:
                continue
            if vid in new_blocks:
                offset, length = new_blocks[vid]
                directory = dir_of(vid)
                if directory.is_dir():
                    # 刚刚重写过数据块 → 按磁盘实际情况修正"含哪些程序文件"
                    # （索引里的 payloadTops 可能是旧的脏数据，以工程自己的
                    #  project.json 为准）
                    item = dict(item)
                    tops = payload_tops_of_dir(directory) or list(item.get("payloadTops") or [])
                    item["payloadTops"] = tops
                    item["payloadStored"] = _has_payload(directory, tops)
            elif vid in old_blocks:
                offset, length = old_blocks[vid]
            else:
                # 既没有旧块、目录也不在（可能被懒解压/已删除）→ 不放进去，避免坏索引
                continue
            entry = {k: item[k] for k in META_FIELDS if k in item}
            entry["off"] = offset
            entry["len"] = length
            versions.append(entry)

        manifest = {
            "formatVersion": FORMAT,
            "keep": keep,
            "current": current,
            "data": ({"off": data_rec[0], "len": data_rec[1]} if data_rec else None),
            "versions": versions,
        }
        payload = json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")
        handle.seek(0, os.SEEK_END)
        offset = handle.tell()
        handle.write(payload)
        _write_header(handle, offset, len(payload))
        handle.flush()

    _maybe_compact(target, manifest)
    return manifest


def set_current(path: str | Path, versions_json: dict) -> None:
    """**只改索引**：更新 current / 各版本的元信息，删掉已不存在的版本。

    切换版本、重命名、锁定、删除版本都走这里 —— 数据块原地不动，所以很快。
    """
    path = Path(path)
    try:
        manifest = read_manifest(path)
    except ProjectFileError:
        return
    items = [it for it in (versions_json.get("items") or []) if isinstance(it, dict)]
    metas = {str(it.get("id")): it for it in items if it.get("id")}
    versions = []
    for entry in manifest.get("versions") or []:
        vid = str(entry.get("id") or "")
        if vid not in metas:
            continue
        item = metas[vid]
        for key in META_FIELDS:
            if key in item:
                entry[key] = item[key]
        versions.append(entry)
    manifest["versions"] = versions
    manifest["current"] = str(versions_json.get("current") or "")
    try:
        manifest["keep"] = int(versions_json.get("keep") or manifest.get("keep") or 2)
    except (TypeError, ValueError):
        pass
    _write_manifest(path, manifest)
    _maybe_compact(path, manifest)


# ---------------------------------------------------------------------------
# 压实（把被替换掉的旧数据块清掉）
# ---------------------------------------------------------------------------

def _maybe_compact(path: Path, manifest: dict) -> None:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            _offset, manifest_len = _read_header(handle)
    except OSError:
        return
    live = 0
    if manifest.get("data"):
        live += int(manifest["data"].get("len", 0))
    for entry in manifest.get("versions") or []:
        live += int(entry.get("len", 0))
    garbage = size - HEADER_SIZE - live - int(manifest_len)
    if garbage <= COMPACT_MIN_GARBAGE or garbage < COMPACT_RATIO * max(1, live):
        return
    _compact(path, manifest)


def _compact(path: Path, manifest: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    blocks: list[tuple[dict, int, int]] = []
    with tmp.open("wb") as out:
        _write_header(out, 0, 0)
        out.seek(HEADER_SIZE)
        new_manifest = dict(manifest)
        data = manifest.get("data")
        if data:
            offset = out.tell()
            _copy_region(path, int(data["off"]), int(data["len"]), out)
            new_manifest["data"] = {"off": offset, "len": int(data["len"])}
        versions = []
        for entry in manifest.get("versions") or []:
            item = dict(entry)
            offset = out.tell()
            _copy_region(path, int(entry["off"]), int(entry["len"]), out)
            item["off"] = offset
            versions.append(item)
        new_manifest["versions"] = versions
        payload = json.dumps(new_manifest, ensure_ascii=False, indent=1).encode("utf-8")
        offset = out.tell()
        out.write(payload)
        _write_header(out, offset, len(payload))
        out.flush()
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# 缓存目录 / 临时工作目录
# ---------------------------------------------------------------------------

def cache_root() -> Path:
    """缓存（解开的工程 / 编译中间产物）放哪。

    优先「首选项 → 缓存目录」里设的；没设或不可写就用**软件目录下的
    ``data\\work``**（便携、不占 C 盘）；再不行才退回系统临时目录。
    """
    from .paths import data_dir, is_writable
    from .settings import load_settings

    candidates: list[Path] = []
    try:
        configured = (load_settings().cache_dir or "").strip()
    except Exception:  # noqa: BLE001 - 设置读不出来不影响用默认位置
        configured = ""
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(data_dir() / "work")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        if is_writable(candidate):
            return candidate
    return Path(tempfile.gettempdir())


def make_work_dir(root: str | Path | None = None) -> Path:
    """建一个本软件独占的临时工作目录。"""
    base = Path(root) if root else cache_root()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        base = Path(tempfile.gettempdir())
    _ensure_space(base, 0, _("创建缓存目录"))
    return Path(tempfile.mkdtemp(prefix=WORK_PREFIX, dir=str(base)))


def cleanup(work_dir: str | Path | None) -> None:
    if not work_dir:
        return
    shutil.rmtree(str(work_dir), ignore_errors=True)


def cleanup_stale(max_age_hours: float = 24.0) -> None:
    """清理上次没来得及删掉的临时工作目录（只删足够旧的，避免误删正在用的）。"""
    cutoff = time.time() - max_age_hours * 3600
    roots = []
    try:
        roots.append(cache_root())
    except Exception:  # noqa: BLE001
        pass
    roots.append(Path(tempfile.gettempdir()))       # 兼容老版本留下的
    seen = set()
    for root in roots:
        if str(root) in seen or not root.is_dir():
            continue
        seen.add(str(root))
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            if not entry.name.startswith(WORK_PREFIX) or not entry.is_dir():
                continue
            try:
                if entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
            except OSError:
                continue


# ---------------------------------------------------------------------------
# 磁盘空间
# ---------------------------------------------------------------------------

def _free_bytes(path: Path) -> int:
    try:
        return shutil.disk_usage(str(path)).free
    except OSError:
        return 1 << 62                                # 查不到就不拦


def _mb(value: int) -> str:
    return f"{value / 1024 / 1024:.0f} MB"


def _ensure_space(path: Path, needed: int, what: str) -> None:
    """空间不够就直接拦下来，并告诉用户还差多少、去哪里换盘。"""
    margin = max(64 * 1024 * 1024, int(needed * 0.05))
    free = _free_bytes(path)
    if free < needed + margin:
        raise ProjectFileError(
            _("磁盘空间不足，无法{what}。\n"
              "需要约 {need}，可用 {free}。\n"
              "请清理磁盘，或在「首选项/设置 → 缓存目录」里换一个盘。").format(
                  what=what, need=_mb(needed + margin), free=_mb(free)))
