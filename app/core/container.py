"""单个 ``.aiproj`` 工程文件（ZIP 容器）的读写。

设计成「容器只是搬运层」：运行时永远把工程解到一份真实目录（临时工作目录），
生成器、NSIS、预览、图片处理全都照旧在磁盘上干活；保存时再把这份目录压回去。
这样引擎完全不用改，用户又只拿到一个文件。

容器里装的是：``project.json``、``assets/``、``payload/`` 以及用户自己放的
其它文件；``build/`` 这类中间产物不装（每次编译都会重做）。
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

from ..i18n import t as _
from .errors import ProjectFileError

PROJECT_JSON = "project.json"
WORK_PREFIX = "简包装-工程-"
# 顶层里不装进容器的目录（中间产物）
EXCLUDE_TOP = {"build"}
# 超过这个大小就不压缩：省 CPU，反正 NSIS 最后还会再压一遍
STORE_THRESHOLD = 64 * 1024


def sniff(path: str | Path) -> str:
    """判断一个 ``.aiproj`` 是哪一种：``container`` / ``json`` / ``missing``。"""
    path = Path(path)
    if not path.is_file():
        return "missing"
    try:
        with path.open("rb") as handle:
            head = handle.read(4)
    except OSError:
        return "missing"
    if head[:2] == b"PK":
        return "container"
    return "json"


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


def extract(container: str | Path, dest: str | Path, progress=None) -> Path:
    """把容器解到 ``dest``。会做 zip-slip 校验，拒绝越界路径。

    ``progress`` 可选：``progress(已处理数, 总数, 当前文件名)``，供加载提示窗口
    显示真实进度。它会被放到后台线程里调用，回调本身不要直接碰 Tk。
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    try:
        archive = zipfile.ZipFile(container)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProjectFileError(
            _("这个工程文件打不开（不是有效的 .aiproj 容器）：{exc}").format(exc=exc)) from exc

    with archive:
        names = archive.namelist()
        if PROJECT_JSON not in names:
            raise ProjectFileError(_("这个 .aiproj 里没有 project.json，可能不是本软件的工程。"))
        files = [info for info in archive.infolist()
                 if info.filename and not info.is_dir()
                 and not info.filename.endswith(("/", "\\"))]
        total = sum(info.file_size for info in files)
        _ensure_space(dest, total, _("解开这个工程"))
        count = len(files)
        for index, info in enumerate(files, 1):
            name = info.filename.replace("\\", "/")
            parts = name.split("/")
            if name.startswith("/") or any(part in ("..", "") for part in parts[:-1]):
                raise ProjectFileError(
                    _("工程文件里有非法路径，已拒绝：{name}").format(name=name))
            target = (dest / name).resolve()
            if target != root and root not in target.parents:
                raise ProjectFileError(
                    _("工程文件里有越界路径，已拒绝：{name}").format(name=name))
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out, 1024 * 256)
            if progress is not None:
                try:
                    progress(index, count, name)
                except Exception:  # noqa: BLE001 - 进度回调失败不该影响解压
                    pass
    return dest


def read_project_bytes(container: str | Path) -> bytes:
    try:
        with zipfile.ZipFile(container) as archive:
            return archive.read(PROJECT_JSON)
    except KeyError as exc:
        raise ProjectFileError(_("这个 .aiproj 里没有 project.json。")) from exc
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProjectFileError(_("读不了这个工程文件：{exc}").format(exc=exc)) from exc


def pack(src_dir: str | Path, dest: str | Path) -> Path:
    """把工作目录压成一个 ``.aiproj``（先写临时文件再原子替换）。"""
    src = Path(src_dir)
    dest = Path(dest)
    if not (src / PROJECT_JSON).is_file():
        raise ProjectFileError(_("工作目录里没有 project.json，无法打包。"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = sum(p.stat().st_size for p in src.rglob("*") if p.is_file())
    _ensure_space(dest.parent, total, _("保存工程"))
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with zipfile.ZipFile(tmp, "w", allowZip64=True) as archive:
            for path in sorted(src.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(src).as_posix()
                if rel.split("/", 1)[0] in EXCLUDE_TOP:
                    continue
                if rel.endswith(".tmp"):
                    continue
                size = path.stat().st_size
                method = zipfile.ZIP_STORED if size > STORE_THRESHOLD else zipfile.ZIP_DEFLATED
                archive.write(path, rel, compress_type=method)
        os.replace(tmp, dest)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise ProjectFileError(_("保存工程失败：{exc}").format(exc=exc)) from exc
    return dest
