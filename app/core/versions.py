"""工程内的「版本迭代 / 切换」。

设计思路（和项目所有者确认过）：

- **当前正在编辑的版本**，内容就放在工程根目录（``project.json`` + ``assets/``
  + ``payload/`` …），和以前完全一样；
- **其它版本**各存一份**完整快照**在 ``versions/<id>/`` 里（含程序文件）；
- 版本清单单独写在 ``versions.json``，**不塞进 project.json** —— 否则切换时
  会用目标版本的 project.json 把清单盖掉；
- **只对"最近 keep 版"保留程序文件**，更早的版本删掉 ``payload/``，只留配置 + 资源
  （切过去仍能看/改配置，但没有程序文件）；
- **切换** = 先保存 → 冻结当前版本 → 用目标版本的快照替换工程根目录的内容。

``versions/`` 与 ``versions.json`` 会随工程一起被装进单文件容器（``build/`` 除外），
所以工程仍然是"一个文件"。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ..i18n import t as _
from . import container
from .errors import ProjectFileError
from .project import _pad_version

VERSIONS_JSON = "versions.json"
VERSIONS_DIR = "versions"

DEFAULT_KEEP = 2          # 默认保留最近 2 版（含当前）的完整程序文件
KEEP_CHOICES = (1, 2, 3, 5)

# 做快照时不复制的东西
_EXCLUDE_SNAPSHOT = {"build", VERSIONS_DIR, VERSIONS_JSON}
# 切换版本时，工程根目录里要保留的东西（其余内容会被目标版本覆盖）
_LIVE_KEEP = {"build", VERSIONS_DIR, VERSIONS_JSON}


def _now() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _new_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tail = os.urandom(2).hex()
    return f"{stamp}-{tail}"


def bump_version(version: str) -> str:
    """把版本号最后一段 +1（1.0.0 -> 1.0.1）。看不懂就原样返回。"""
    parts = re.findall(r"\d+", version or "")
    if not parts:
        return version or "1.0.0"
    parts = parts[:4]
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def version_sort_key(version: str) -> tuple[int, int, int, int]:
    """把版本号变成可比较的元组（1.0.10 > 1.0.9，不是按字符串比）。"""
    parts = [int(x) for x in re.findall(r"\d+", version or "")][:4]
    return tuple(parts + [0] * (4 - len(parts)))  # type: ignore[return-value]


@dataclass
class VersionInfo:
    """一个版本在清单里的信息（内容存在 ``versions/<id>/`` 里）。"""

    id: str
    label: str = ""            # 显示名（默认 v<版本号>）
    version: str = ""          # 显示版本
    file_version: str = ""     # 四段文件版本
    note: str = ""             # 备注
    created_at: str = ""
    seq: int = 0                   # 创建顺序（时间可能同秒，靠它排先后）
    payload_stored: bool = True    # 是否保留着程序文件
    payload_tops: list[str] = field(default_factory=list)   # 程序文件的顶层条目
    locked: bool = False           # 锁定的版本不会被自动淘汰

    @classmethod
    def from_dict(cls, d: dict) -> "VersionInfo":
        tops = d.get("payloadTops")
        tops = [str(x) for x in tops] if isinstance(tops, list) else []
        try:
            seq = int(d.get("seq") or 0)
        except (TypeError, ValueError):
            seq = 0
        return cls(
            id=str(d.get("id") or ""),
            label=str(d.get("label") or ""),
            version=str(d.get("version") or ""),
            file_version=str(d.get("fileVersion") or ""),
            note=str(d.get("note") or ""),
            created_at=str(d.get("createdAt") or ""),
            seq=seq,
            payload_stored=bool(d.get("payloadStored", True)),
            payload_tops=tops,
            locked=bool(d.get("locked", False)),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "version": self.version,
            "fileVersion": self.file_version,
            "note": self.note,
            "createdAt": self.created_at,
            "seq": self.seq,
            "payloadStored": self.payload_stored,
            "payloadTops": list(self.payload_tops),
            "locked": self.locked,
        }

    def display(self) -> str:
        return self.label or (f"v{self.version}" if self.version else self.id)


def _payload_tops(project, root: Path) -> list[str]:
    """算出"打包内容"在 ``root`` 下的顶层条目名（用来判断/精简程序文件）。

    demo 之类的工程用的是 ``input/``，不一定是 ``payload/``，所以不能写死名字。
    """
    tops: list[str] = []
    try:
        base = root.resolve()
    except OSError:
        return tops
    for item in project.files.items:
        rel = (item.source or "").strip()
        if not rel:
            continue
        path = Path(rel)
        top = ""
        if path.is_absolute():
            try:
                parts = path.resolve().relative_to(base).parts
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


def _copy_content(src: Path, dest: Path, exclude: set[str]) -> None:
    """把 ``src`` 里的内容复制进 ``dest``（跳过 ``exclude`` 里的顶层名字）。"""
    dest.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.name in exclude:
            continue
        target = dest / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)


def _move_content(src: Path, dest: Path, exclude: set[str]) -> None:
    """把 ``src`` 里的内容**移动**进 ``dest``（跳过 ``exclude`` 里的顶层名字）。

    同一块盘上的 rename 只是改一条目录记录，几乎不搬数据 —— 版本切换靠它做到"秒切"。
    万一 rename 失败（跨盘、被占用等），退回"复制 + 删除"，保证结果一致。
    """
    dest.mkdir(parents=True, exist_ok=True)
    for entry in list(src.iterdir()):
        if entry.name in exclude:
            continue
        target = dest / entry.name
        if target.exists():
            if target.is_dir():
                _rmtree(target)
            else:
                _unlink(target)
        try:
            os.replace(entry, target)
        except OSError:
            if entry.is_dir():
                shutil.copytree(entry, target, dirs_exist_ok=True)
                _rmtree(entry)
            else:
                shutil.copy2(entry, target)
                _unlink(entry)


def _force_remove(func, path, _excinfo) -> None:
    """删除失败时的兜底：去掉只读属性再试一次。

    Windows 上从版本库 / 网盘同步下来的文件常带只读属性，
    ``shutil.rmtree`` 默认会直接抛 PermissionError。
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _rmtree(path: Path) -> None:
    """删一个目录（带"去只读再试"的兜底）。"""
    if not path.exists():
        return
    try:
        shutil.rmtree(path, onerror=_force_remove)
    except OSError:
        pass
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _unlink(path: Path) -> None:
    """删一个文件（带"去只读再试"的兜底）。"""
    try:
        path.unlink()
        return
    except OSError:
        pass
    try:
        os.chmod(path, stat.S_IWRITE)
        path.unlink()
    except OSError:
        pass


def _clear_content(base: Path, keep: set[str]) -> None:
    """清空 ``base`` 里除 ``keep`` 之外的内容（保留文件夹本身）。"""
    for entry in base.iterdir():
        if entry.name in keep:
            continue
        if entry.is_dir():
            _rmtree(entry)
        else:
            _unlink(entry)


def _has_content(path: Path) -> bool:
    """路径存在且"非空"（空文件夹不算有程序文件）。"""
    try:
        if path.is_file():
            return True
        if path.is_dir():
            return any(path.iterdir())
    except OSError:
        return False
    return False


def _clear_packing_list(project) -> None:
    """把磁盘上工程 JSON 里的 "files.items" 清空（切换"仅配置"版本后用）。

    只动磁盘 JSON，不碰内存模型——调用方随后会用 :func:`reload_project` 重读。
    """
    path = (project.base_dir / "project.json") if project.is_container \
        else Path(project.source_path)
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return
    files = data.get("files")
    if isinstance(files, dict):
        files["items"] = []
        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        except OSError:
            pass


def is_blank_project(project) -> bool:
    """判断是不是"刚新建、还没登记过任何版本"的空工程。

    这种工程只显示「版本迭代 / 创建」，让用户先建第一个版本，再把界面全貌放出来。
    已经填过内容、或已经写过版本清单的，都算"正式工程"。
    """
    base = project.base_dir
    if (base / VERSIONS_JSON).is_file():
        return False
    return not project.app.name.strip() and not project.files.items


@dataclass
class VersionStore:
    """某个工程里的版本清单 + 快照操作。"""

    base_dir: Path
    keep: int = DEFAULT_KEEP
    current: str = ""
    items: list[VersionInfo] = field(default_factory=list)
    container_path: Path | None = None                # 单文件容器（新格式）的路径
    rebuild: set[str] = field(default_factory=set)    # 需要重新写数据块的版本 id

    # -- 查询 ---------------------------------------------------------------

    def item(self, vid: str) -> VersionInfo | None:
        for entry in self.items:
            if entry.id == vid:
                return entry
        return None

    def current_item(self) -> VersionInfo | None:
        return self.item(self.current)

    def dir_for(self, vid: str) -> Path:
        return self.base_dir / VERSIONS_DIR / vid

    def _others_by_age(self) -> list[VersionInfo]:
        """除当前版本外，按创建先后从新到旧。"""
        others = [i for i in self.items if i.id != self.current]
        others.sort(key=lambda i: (i.seq, i.id), reverse=True)
        return others

    def retired_items(self) -> list[VersionInfo]:
        """被淘汰的版本。

        规则：按创建先后取**最近 keep 个**作为"保留窗口"（锁定的版本也占名额），
        窗口之外、且没被锁定的，一律「已淘汰」。

        注意：
        - 按位置算，哪怕某个老版本原本就没放文件，也一样是「已淘汰」；
        - 锁定 🔒 只是"不受保护地留在窗口外也不删文件"——它仍然算已淘汰，
          不能再加文件；解锁后立刻按淘汰处理。
        """
        order = sorted(self.items, key=lambda i: (i.seq, i.id), reverse=True)
        limit = max(0, self.keep)
        return [i for i in order[limit:] if not i.locked]

    def would_retire_without_lock(self, vid: str) -> bool:
        """这个版本"假如没锁"，是不是落在保留窗口之外（即该被淘汰）。"""
        order = sorted(self.items, key=lambda i: (i.seq, i.id), reverse=True)
        limit = max(0, self.keep)
        for index, item in enumerate(order):
            if item.id == vid:
                return index >= limit
        return False

    def is_retired(self, vid: str) -> bool:
        return any(i.id == vid for i in self.retired_items())

    def ordered(self) -> list[VersionInfo]:
        """按版本号从大到小排（版本号看不懂的按创建先后）。顺序固定，不随当前版本跳动。"""
        def key(item: VersionInfo):
            return (version_sort_key(item.version), item.seq, item.id)
        return sorted(self.items, key=key, reverse=True)

    def _next_seq(self) -> int:
        return max((i.seq for i in self.items), default=0) + 1

    # -- 清单读写 -----------------------------------------------------------

    def to_json(self) -> dict:
        return {
            "keep": self.keep,
            "current": self.current,
            "items": [item.to_dict() for item in self.items],
            "rebuild": sorted(self.rebuild),
        }

    def save(self) -> None:
        path = self.base_dir / VERSIONS_JSON
        payload = self.to_json()
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        try:
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            raise ProjectFileError(_("保存版本清单失败：{exc}").format(exc=exc)) from exc
        # 单文件容器：把"谁当前 + 各版本元信息"写进容器索引。
        # 这一步**只改索引**（数据块原地不动），所以切换版本几乎是瞬时的。
        if self.container_path is not None and Path(self.container_path).is_file():
            try:
                container.set_current(self.container_path, payload)
            except Exception:  # noqa: BLE001 - 索引更新失败不该让版本操作整个失败
                pass

    def ensure_current(self, project) -> VersionInfo:
        """工程还没登记过版本时，把当前状态登记成第一个版本（不写盘）。"""
        item = self.current_item()
        if item is None:
            item = VersionInfo(id=_new_id(), version=project.app.version,
                               file_version=project.app.file_version,
                               created_at=_now(), seq=self._next_seq(),
                               payload_stored=True)
            self.items.append(item)
            self.current = item.id
        return item

    # -- 操作 ---------------------------------------------------------------

    def _refresh_payload_meta(self, item: VersionInfo, project, dest: Path) -> None:
        """把版本记录的元信息按快照落地后的实际情况更新一遍。"""
        item.version = project.app.version
        item.file_version = project.app.file_version
        item.label = item.label or f"v{project.app.version}"
        item.created_at = item.created_at or _now()
        item.payload_tops = _payload_tops(project, dest)
        item.payload_stored = any(_has_content(dest / top) for top in item.payload_tops)

    def freeze_current(self, project) -> None:
        """把工程根目录的当前内容**复制**一份，存成"当前版本"的快照。

        这里用复制而不用移动：调用方是「新建版本」，新版本还要接着用原来的
        图标 / 页头图等资源。（"切换版本"的归档走 :meth:`switch_to` 里的移动。）
        """
        item = self.ensure_current(project)
        dest = self.dir_for(item.id)
        _rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        _copy_content(self.base_dir, dest, _EXCLUDE_SNAPSHOT)
        self._refresh_payload_meta(item, project, dest)

    def new_version(self, project, version: str, file_version: str = "",
                    note: str = "") -> VersionInfo:
        """登记一个新版本。

        - 还没有任何版本时（刚新建的工程）：直接把当前状态登记成第一个版本，
          不用去冻结一份空的快照；
        - 已经有版本时：先把当前版本冻结下来，再新建。
        """
        if self.items:
            self.freeze_current(project)
            # 新版本从"空的打包内容"开始，免得把上一版的文件当成这一版的
            self._clear_payload(project)

        project.app.version = version or project.app.version
        project.app.file_version = file_version or ""
        project.apply_derived()

        tops = _payload_tops(project, self.base_dir)
        item = VersionInfo(id=_new_id(), version=project.app.version,
                           file_version=project.app.file_version, note=note,
                           label=f"v{project.app.version}", created_at=_now(),
                           seq=self._next_seq(),
                           payload_stored=any(_has_content(self.base_dir / t) for t in tops),
                           payload_tops=tops)
        self.items.append(item)
        self.current = item.id
        self.prune(project)
        self.save()
        return item

    def _clear_payload(self, project) -> None:
        """清空"打包内容"：删掉工程目录内被引用的程序文件，并把列表清空。

        只删**工程目录里**的副本（外部的"直接引用"不动），所以不会碰用户的构建输出。
        """
        for top in _payload_tops(project, self.base_dir):
            path = self.base_dir / top
            if path.is_dir():
                _rmtree(path)
            elif path.exists():
                _unlink(path)
        project.files.items = []

    def switch_to(self, project, target_id: str) -> VersionInfo:
        """切到另一个版本：先冻结当前，再用目标的快照替换工程内容。"""
        target = self.item(target_id)
        if target is None:
            raise ProjectFileError(_("找不到这个版本。"))
        if target_id == self.current:
            return target

        target_dir = self.dir_for(target_id)
        self._ensure_materialized(project, target)
        if not (target_dir / "project.json").is_file():
            raise ProjectFileError(
                _("版本「{name}」的存档已经不存在了，无法切换。").format(
                    name=target.display()))

        # 1. 把当前版本**改名**归档：同盘 rename，几乎不搬数据（比"复制一趟"快得多）。
        current = self.ensure_current(project)
        current_dir = self.dir_for(current.id)
        _rmtree(current_dir)
        current_dir.mkdir(parents=True, exist_ok=True)
        _move_content(self.base_dir, current_dir, _EXCLUDE_SNAPSHOT)
        self._refresh_payload_meta(current, project, current_dir)

        # 2. 用目标的快照**改名**替换工程根目录。程序文件也一起换掉：
        #    - 目标带程序文件 → 用它的；
        #    - 目标是「已淘汰」（程序文件已被清掉）→ 工程里就**没有**程序文件，
        #      界面会清空「打包内容」并禁止再加，绝不让上一版的文件留在那里冒充。
        retired = self.is_retired(target_id)
        has_payload = any(_has_content(target_dir / top) for top in target.payload_tops)
        _move_content(target_dir, self.base_dir, set())
        _rmtree(target_dir)

        self.current = target_id
        target.payload_stored = has_payload
        if retired:
            # 目标已被淘汰：把磁盘上工程 JSON 里的"打包内容"一起清掉，
            # 不然重新打开后列表里还挂着一堆找不到的文件。
            _clear_packing_list(project)
        self.save()
        return target

    def _ensure_materialized(self, project, item) -> None:
        """确保这个版本的目录已经在磁盘上（懒解压时要先从容器里解出来）。"""
        if item is None or self.container_path is None:
            return
        directory = self.dir_for(item.id)
        if (directory / "project.json").is_file():
            return
        # 打开后后台可能在解它 → 先等它收尾，避免两边同时写同一个目录
        wait = getattr(project, "wait_materialize", None)
        if wait is not None:
            wait()
        try:
            container.materialize(self.container_path, self.base_dir, item.id)
        except ProjectFileError:
            pass

    def prune(self, project=None) -> list[VersionInfo]:
        """把被淘汰版本的程序文件删掉，返回被清理的版本。"""
        stripped: list[VersionInfo] = []
        for item in self.retired_items():
            if item.id == self.current or not item.payload_stored:
                continue
            self._ensure_materialized(project, item)
            dest = self.dir_for(item.id)
            for top in item.payload_tops:
                path = dest / top
                if path.is_dir():
                    _rmtree(path)
                elif path.exists():
                    _unlink(path)
            item.payload_stored = any(
                _has_content(dest / top) for top in item.payload_tops)
            # 这个版本的数据块内容变了（少了程序文件）→ 让保存时重写它
            self.rebuild.add(item.id)
            stripped.append(item)
        return stripped

    def rename(self, project, vid: str, version: str, note: str) -> None:
        """改版本号（可顺带改备注）。

        当前版本改号时，同步写回工程（安装包文件名、实时预览、窗口标题都跟着走）；
        程序文件版本如果原本就是按版本号自动补的，也跟着更新。
        """
        item = self.item(vid)
        if item is None:
            return
        version = (version or "").strip()
        if version:
            old_version = item.version
            item.version = version
            item.label = f"v{version}"
            if vid == self.current and project is not None:
                project.app.version = version
                if (not project.app.file_version
                        or project.app.file_version == _pad_version(old_version)):
                    project.app.file_version = ""
                    project.apply_derived()
                item.file_version = project.app.file_version
        item.note = note.strip()
        self.save()

    def set_locked(self, vid: str, locked: bool) -> None:
        item = self.item(vid)
        if item is None:
            return
        item.locked = bool(locked)
        self.save()

    def delete(self, vid: str) -> None:
        if vid == self.current:
            raise ProjectFileError(_("不能删除当前正在编辑的版本。"))
        item = self.item(vid)
        if item is None:
            return
        _rmtree(self.dir_for(vid))
        self.items = [i for i in self.items if i.id != vid]
        self.save()


def load_store(project) -> VersionStore:
    """读取工程里的版本清单（不会写入磁盘；没有就返回空清单）。"""
    base = project.base_dir
    is_container = bool(getattr(project, "is_container", False))
    store = VersionStore(
        base_dir=base,
        container_path=(Path(project.source_path) if is_container else None))
    path = base / VERSIONS_JSON
    if not path.is_file():
        return store
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return store
    if not isinstance(data, dict):
        return store
    try:
        store.keep = int(data.get("keep") or DEFAULT_KEEP)
    except (TypeError, ValueError):
        store.keep = DEFAULT_KEEP
    if store.keep <= 0:
        store.keep = DEFAULT_KEEP
    store.current = str(data.get("current") or "")
    raw = data.get("items")
    if isinstance(raw, list):
        store.items = [VersionInfo.from_dict(x) for x in raw if isinstance(x, dict)]
    raw_rebuild = data.get("rebuild")
    if isinstance(raw_rebuild, list):
        store.rebuild = {str(x) for x in raw_rebuild}
    return store


def current_version_is_retired(project) -> bool:
    """当前版本是不是"已淘汰"——这种版本一律不能再往里面加文件。"""
    if project is None:
        return False
    store = load_store(project)
    if not store.current:
        return False
    return store.is_retired(store.current)


def folder_size(path: Path, skip: set[str] | None = None) -> int:
    """目录里所有文件的总字节数（``skip`` 里的顶层名字不计）。"""
    skip = skip or set()
    total = 0
    if not path.is_dir():
        return 0
    for base, dirs, files in os.walk(path):
        if base == str(path):
            dirs[:] = [d for d in dirs if d not in skip]
        for name in files:
            try:
                total += os.path.getsize(os.path.join(base, name))
            except OSError:
                pass
    return total


def version_size(project, item) -> int:
    """某个版本占用的磁盘空间（当前版本就是工程根目录，其余是它的快照目录）。"""
    if project is None or item is None:
        return 0
    store = load_store(project)
    if item.id == store.current:
        return folder_size(project.base_dir, skip={VERSIONS_DIR, "build"})
    directory = store.dir_for(item.id)
    if directory.is_dir():
        return folder_size(directory)
    if store.container_path is not None:
        # 数据块还没解到磁盘 → 用容器里记的块大小
        return container.block_sizes(store.container_path).get(item.id, 0)
    return 0


def version_numbers(project) -> list[str]:
    """工程里已经用过的版本号（用来防止用户建出重复版本）。"""
    if project is None:
        return []
    return [i.version for i in load_store(project).items if i.version]
