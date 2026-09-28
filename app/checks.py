"""把「校验一个工程」这件事收在一个地方，命令行和图形界面共用。"""

from __future__ import annotations

from .core.errors import Problem, error
from .core.project import Project
from .engine.assets import (
    HEADER_BITMAP_SIZE,
    WELCOME_BITMAP_SIZE,
    check_bitmap,
    check_icon,
)


def check_project(project: Project) -> list[Problem]:
    """完整校验：字段合法性 + 引用文件存在性 + 图片尺寸。

    返回的列表里 ``error`` 级会阻断打包，``warning`` 级只是提示。
    """
    problems = list(project.validate())
    problems.extend(_asset_size_problems(project))
    return problems


def split(problems: list[Problem]) -> tuple[list[str], list[str]]:
    errors = [str(p) for p in problems if p.level == "error"]
    warnings = [str(p) for p in problems if p.level == "warning"]
    return errors, warnings


def _asset_size_problems(project: Project) -> list[Problem]:
    """图标和位图的尺寸是 NSIS/MUI 的硬性要求，这里提前拦住。"""
    found: list[Problem] = []
    app, interface = project.app, project.interface

    if app.icon:
        message = check_icon(project.resolve("app.icon", app.icon), "app.icon")
        if message:
            found.append(error("app.icon", message))

    if interface.header_image:
        message = check_bitmap(
            project.resolve("interface.headerImage", interface.header_image),
            HEADER_BITMAP_SIZE, "interface.headerImage")
        if message:
            found.append(error("interface.headerImage", message))

    if interface.welcome.enabled and interface.welcome.image:
        message = check_bitmap(
            project.resolve("interface.welcome.image", interface.welcome.image),
            WELCOME_BITMAP_SIZE, "interface.welcome.image")
        if message:
            found.append(error("interface.welcome.image", message))

    return found
