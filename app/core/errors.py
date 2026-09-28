"""可预期的错误类型。"""

from __future__ import annotations

from ..i18n import t as _


class PackError(Exception):
    """本程序所有可预期错误的基类。"""


class ProjectFileError(PackError):
    """工程文件读不了 / 结构不对（JSON 语法、formatVersion 等）。"""


class BuildError(PackError):
    """调用 makensis 编译失败。"""


class MakensisNotFound(BuildError):
    """找不到 makensis.exe。"""


class Problem:
    """一条校验结论。level 为 ``error`` 时阻断打包，``warning`` 只是提示。"""

    __slots__ = ("level", "where", "message")

    def __init__(self, level: str, where: str, message: str) -> None:
        self.level = level
        self.where = where
        self.message = message

    def __str__(self) -> str:
        tag = _("错误") if self.level == "error" else _("警告")
        return f"[{tag}] {self.where}: {self.message}"


def error(where: str, message: str) -> Problem:
    return Problem("error", where, message)


def warning(where: str, message: str) -> Problem:
    return Problem("warning", where, message)
