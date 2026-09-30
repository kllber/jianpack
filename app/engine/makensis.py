"""定位并调用 NSIS 编译器（makensis.exe）。"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..core.errors import MakensisNotFound
from ..i18n import t as _

# 系统里装了 NSIS 时的常见位置
CANDIDATE_PATHS = (
    r"C:\Program Files (x86)\NSIS\makensis.exe",
    r"C:\Program Files\NSIS\makensis.exe",
)

BUNDLED_RELATIVE = Path("vendor") / "nsis" / "makensis.exe"

# Windows 上以图形界面运行时，subprocess 默认会闪出一个黑色命令行窗口。
# 用 CREATE_NO_WINDOW 把它藏掉（只影响窗口，不影响进程和管道）。
_CREATE_NO_WINDOW = 0x08000000


def no_window_flags() -> int:
    return _CREATE_NO_WINDOW if sys.platform == "win32" else 0


@dataclass
class CompileResult:
    returncode: int
    output: str
    command: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def search_roots() -> list[Path]:
    """按优先级列出「随软件分发的便携版 NSIS」可能所在的根目录。

    - ``sys._MEIPASS``：PyInstaller 打包成单个 exe 后，数据会被解到那里；
    - 源码目录：``<项目根>/vendor/nsis/``。
    """
    roots: list[Path] = []
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        roots.append(Path(bundle))
    roots.append(Path(__file__).resolve().parents[2])
    return roots


def find_makensis(explicit: str | Path | None = None) -> Path:
    """按「显式指定 -> 环境变量 -> 随软件分发的便携版 -> 系统安装目录 -> PATH」查找。"""
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
        raise MakensisNotFound(_("指定的 makensis 不存在：{path}").format(path=path))

    env = os.environ.get("MAKENSIS")
    if env and Path(env).is_file():
        return Path(env)

    # 随软件分发的便携版（打包成 exe 之后走的就是这条路）
    for root in search_roots():
        candidate = root / BUNDLED_RELATIVE
        if candidate.is_file():
            return candidate

    for candidate in (Path(p) for p in CANDIDATE_PATHS):
        if candidate.is_file():
            return candidate

    found = shutil.which("makensis")
    if found:
        return Path(found)

    raise MakensisNotFound(_(
        "找不到 makensis.exe。\n"
        "  官方安装：winget install NSIS.NSIS\n"
        "  或把便携版放到 vendor\\nsis\\ 目录\n"
        "  或用 --makensis 指定路径 / 设置环境变量 MAKENSIS"
    ))


def compile_nsi(makensis: Path, script: Path, defines: list[str] | None = None) -> CompileResult:
    """编译一个 .nsi 脚本。``defines`` 里的名字会变成 ``/D名字``。"""
    command = [str(makensis), "/V2"]
    for name in defines or []:
        command.append(f"/D{name}")
    command.append(str(script))

    process = subprocess.run(command, capture_output=True, cwd=str(script.parent),
                             creationflags=no_window_flags())
    return CompileResult(
        returncode=process.returncode,
        output=decode_output(process.stdout + process.stderr),
        command=command,
    )


def decode_output(raw: bytes) -> str:
    """makensis 在中文 Windows 上输出 GBK，这里逐个编码试探。"""
    for encoding in ("utf-8", "gbk", "mbcs"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")
