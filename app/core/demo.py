"""自带演示工程：固定显示在启动窗口「最近打开」的第一行。

就放在软件的 ``assets/demo/`` 里（随文件夹一起分发，谁拿到都有）；
它是**只读**的，程序不会去改它，所以不需要往别处复制副本。
"""

from __future__ import annotations

from pathlib import Path

from .paths import assets_root

DEMO_FILE_NAME = "演示测试项目.jianpack"
DEMO_DISPLAY_NAME = "演示测试项目"


def bundled_demo_path() -> Path | None:
    path = assets_root() / "demo" / DEMO_FILE_NAME
    return path if path.is_file() else None


def repo_demo_path() -> Path | None:
    """源码运行时兜底：仓库里的示例工程（开发用，不算受保护的演示）。"""
    path = Path(__file__).resolve().parents[2] / "demo" / "feasibility" / "demo.jianpack"
    return path if path.is_file() else None


def demo_project_path(create: bool = True) -> Path | None:
    """演示工程路径：优先随软件分发的那个（在软件目录里），否则退回源码示例。"""
    bundled = bundled_demo_path()
    if bundled is not None:
        return bundled
    return repo_demo_path()


def is_demo(path: str | Path | None) -> bool:
    """这个路径是不是自带的演示项目（受只读保护）。

    源码仓库里的 ``demo/feasibility/demo.jianpack`` 不算——它是开发用的
    文件夹工程，不受保护（测试也依赖它能正常保存）。
    """
    if not path:
        return False
    try:
        target = Path(path).expanduser().resolve()
    except (OSError, ValueError):
        return False
    bundled = bundled_demo_path()
    if bundled is None:
        return False
    try:
        return bundled.resolve() == target
    except OSError:
        return False
