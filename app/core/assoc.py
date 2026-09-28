"""把 ``.aiproj`` 文件关联到本程序（Windows，写 HKCU，不需要管理员）。

关联之后，用户双击一个 ``.aiproj`` 就能打开软件并直接进入工程。
软件是绿色版，没有安装程序，所以提供菜单里的一键关联 / 取消关联。
"""

from __future__ import annotations

import sys
from pathlib import Path

PROGID = "JianPack.Project"
EXT = ".aiproj"
FRIENDLY = "简包装 工程文件"


def _app_command() -> str:
    """双击 .aiproj 时执行的命令行（不含 ``"%1"``）。"""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"'
    root = Path(__file__).resolve().parents[2]
    launcher = Path(sys.executable)
    pythonw = launcher.with_name("pythonw.exe")
    if pythonw.is_file():
        launcher = pythonw
    return f'"{launcher}" "{root / "aipack.py"}"'


def _icon_file() -> Path | None:
    # 工程文件用它自己的图标（和软件图标区分开）
    from .paths import assets_root

    icon = assets_root() / "project.ico"
    return icon if icon.is_file() else None


def _expected_command() -> str:
    return f'{_app_command()} "%1"'


def _expected_icon() -> str | None:
    icon = _icon_file()
    return f'"{icon}",0' if icon is not None else None


def is_associated() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes" + "\\" + EXT) as key:
            value, _ = winreg.QueryValueEx(key, "")
        return value == PROGID
    except OSError:
        return False


def current_command() -> str | None:
    """当前注册的打开命令（没注册时返回 None）。"""
    try:
        import winreg

        path = r"Software\Classes" + "\\" + PROGID + r"\shell\open\command"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return winreg.QueryValueEx(key, "")[0]
    except OSError:
        return None


def current_icon() -> str | None:
    try:
        import winreg

        path = r"Software\Classes" + "\\" + PROGID + r"\DefaultIcon"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return winreg.QueryValueEx(key, "")[0]
    except OSError:
        return None


def status() -> str:
    """``ok`` 正常 / ``stale`` 指错了地方需要修复 / ``missing`` 没关联。"""
    if not is_associated():
        return "missing"
    if current_command() != _expected_command():
        return "stale"
    icon = _expected_icon()
    if icon is not None and current_icon() != icon:
        return "stale"
    return "ok"


def ensure_registered() -> bool:
    """没关联、或关联指向的可执行文件已经变了（换了位置/换电脑）就修一下。

    返回是否真的写了一次注册表。已经正常就不动，避免每次启动都写。
    """
    if status() == "ok":
        return False
    register()
    return True


def register() -> None:
    import winreg

    classes = r"Software\Classes"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, classes + "\\" + EXT) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, PROGID)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, classes + "\\" + PROGID) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, FRIENDLY)
    icon = _icon_file()
    if icon is not None:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              classes + "\\" + PROGID + r"\DefaultIcon") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{icon}",0')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                          classes + "\\" + PROGID + r"\shell\open\command") as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'{_app_command()} "%1"')
    _notify_shell()


def unregister() -> None:
    import winreg

    classes = r"Software\Classes"
    _delete_tree(winreg.HKEY_CURRENT_USER, classes + "\\" + PROGID)
    # 只有 .aiproj 指向我们时才清掉这个扩展名键
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, classes + "\\" + EXT) as key:
            value, _ = winreg.QueryValueEx(key, "")
        if value == PROGID:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, classes + "\\" + EXT)
    except OSError:
        pass
    _notify_shell()


def _delete_tree(root: int, path: str) -> None:
    import winreg

    try:
        with winreg.OpenKey(root, path) as key:
            subkeys = []
            index = 0
            while True:
                try:
                    subkeys.append(winreg.EnumKey(key, index))
                except OSError:
                    break
                index += 1
        for name in subkeys:
            _delete_tree(root, path + "\\" + name)
        winreg.DeleteKey(root, path)
    except OSError:
        pass


def _notify_shell() -> None:
    """让资源管理器立刻刷新图标 / 关联。"""
    try:
        import ctypes

        SHCNE_ASSOCCHANGED = 0x08000000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, 0, None, None)
    except Exception:  # noqa: BLE001
        pass
