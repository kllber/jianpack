"""定位随软件一起分发的资源文件。

源码运行和 PyInstaller 打包两种情况都要能找到 —— 打包后数据被解到
``sys._MEIPASS``（onedir 模式就是 ``_internal``），源码运行则在项目根目录。
"""

from __future__ import annotations

from pathlib import Path

from ..core.paths import assets_root


def app_icon() -> Path | None:
    """设计器自己的图标（assets/packer.ico）。"""
    path = assets_root() / "packer.ico"
    return path if path.is_file() else None


def apply_icon(window) -> None:
    """给窗口装上程序图标；设成默认后，之后创建的子窗口也会用它。"""
    path = app_icon()
    if path is None:
        return
    try:
        window.iconbitmap(default=str(path))
        return
    except Exception:  # noqa: BLE001 - 某些环境不支持 default 写法
        pass
    try:
        window.iconbitmap(str(path))
    except Exception:  # noqa: BLE001 - 装不上图标不影响使用
        pass
