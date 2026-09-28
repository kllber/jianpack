"""工程文件里的路径处理。

工程文件中的路径约定是**相对工程文件所在目录**，但也允许两种例外：

- 绝对路径（``D:\\build\\out``）—— 常见于"我就要打包这个构建输出目录"；
- 用 ``..`` 往上跳出工程目录。

这两种情况都能用，只是工程一旦搬到别的机器/目录就会失效，
所以校验时会给出**警告**而不是报错。工程内路径才是推荐做法。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ..i18n import t as _
from .errors import ProjectFileError


def assets_root() -> Path:
    """随软件分发的 ``assets`` 目录（源码运行 / PyInstaller 都适用）。"""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        bundled = Path(bundle) / "assets"
        if bundled.is_dir():
            return bundled
    return Path(__file__).resolve().parents[2] / "assets"


def app_home() -> Path:
    """软件自身所在的目录（便携版就是 exe 旁边那层）。

    环境变量 ``AIPACK_HOME`` 可以覆盖它（测试/抓图脚本用，免得污染真实目录）。
    """
    override = os.environ.get("AIPACK_HOME")
    if override:
        return Path(override).expanduser()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """本软件自己放东西的地方：设置、缓存工程等，都在安装目录下的 ``data``。"""
    return app_home() / "data"


_writable_cache: dict[str, bool] = {}


def is_writable(path: Path) -> bool:
    """这个目录能不能写（会尝试创建目录并写一个探针文件）。"""
    key = str(path)
    if key in _writable_cache:
        return _writable_cache[key]
    ok = True
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".简包装-write-test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        ok = False
    _writable_cache[key] = ok
    return ok


def desktop_dir() -> Path:
    """当前用户的桌面目录（跟随 OneDrive 之类的重定向）。"""
    try:
        import winreg

        key_path = (r"Software\Microsoft\Windows\CurrentVersion"
                    r"\Explorer\User Shell Folders")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "Desktop")
        path = Path(os.path.expandvars(value))
        if path.is_dir():
            return path
    except OSError:
        pass

    home = Path(os.path.expanduser("~"))
    for name in ("Desktop", "桌面"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    return home


def resolve_path(base_dir: Path, relative: str, *, where: str) -> Path:
    """把工程里写的路径解析成绝对路径。"""
    if not isinstance(relative, str) or not relative.strip():
        raise ProjectFileError(_("{where}: 路径为空").format(where=where))

    candidate = Path(relative)
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / relative).resolve()


def is_inside(base_dir: Path, target: Path) -> bool:
    """``target`` 是否位于工程目录之内。"""
    base = base_dir.resolve()
    resolved = target.resolve()
    return resolved == base or base in resolved.parents


def to_nsi_path(path: Path, base_dir: Path) -> str:
    """转成 NSIS 能用的相对路径（跨盘符时退回绝对路径）。"""
    import os

    try:
        rel = os.path.relpath(str(path), str(base_dir))
    except ValueError:
        return str(path)
    return rel.replace("/", "\\")
