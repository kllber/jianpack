"""代码签名（Authenticode）：打包完成后调用 ``signtool.exe`` 给安装包签名。

没有证书时可以完全不启用；启用后如果找不到 signtool 或签名失败，会把
原始输出带回来，由调用方决定怎么提示（不吞掉错误）。
"""

from __future__ import annotations

import glob
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..i18n import t as _
from .makensis import no_window_flags

# Windows SDK 里 signtool 的常见位置（版本号在中间一段，用 glob 找最新的）
SDK_GLOBS = (
    r"C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe",
    r"C:\Program Files (x86)\Windows Kits\10\bin\*\x86\signtool.exe",
    r"C:\Program Files\Windows Kits\10\bin\*\x64\signtool.exe",
)


@dataclass
class SignResult:
    returncode: int
    output: str = ""
    command: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def find_signtool(explicit: str | Path | None = None) -> Path | None:
    """定位 signtool.exe：显式指定 → PATH → Windows SDK。找不到返回 None。"""
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None

    found = shutil.which("signtool")
    if found:
        return Path(found)

    candidates: list[Path] = []
    for pattern in SDK_GLOBS:
        candidates.extend(Path(p) for p in glob.glob(pattern) if Path(p).is_file())
    if candidates:
        # 版本目录名参与了排序，取最新的一版
        return sorted(candidates)[-1]
    return None


def sign_file(target: str | Path, cert: str | Path | None, password: str = "",
              timestamp: str = "", signtool: str | Path | None = None) -> SignResult:
    """给 ``target`` 签名。返回 :class:`SignResult`（``ok`` 表示成功）。"""
    target = Path(target)
    tool = find_signtool(signtool)
    if tool is None:
        return SignResult(1, _("找不到 signtool.exe，请指定路径，或安装 Windows SDK。"))
    if not cert:
        return SignResult(1, _("没有指定证书文件（.pfx / .p12）。"))

    command = [str(tool), "sign", "/fd", "SHA256",
               "/f", str(Path(cert).expanduser())]
    if password:
        command += ["/p", password]
    if timestamp:
        command += ["/tr", timestamp, "/td", "SHA256"]
    command.append(str(target))

    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                creationflags=no_window_flags())
    except OSError as exc:
        return SignResult(1, str(exc), command)

    output = (result.stdout or "") + (result.stderr or "")
    return SignResult(result.returncode, output, command)
