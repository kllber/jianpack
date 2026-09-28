"""命令行入口。

    python -m app validate <工程文件>
    python -m app generate <工程文件> [--mode perMachine|perUser|all]
    python -m app build    <工程文件> [--mode ...] [--makensis 路径]
    python -m app gui      [工程文件]

不带任何参数时会直接打开图形界面。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import APP_NAME, __version__
from .checks import check_project, split
from .core.container import PROJECT_EXT
from .core.errors import PackError, ProjectFileError
from .core.project import Project, load_project
from .engine import assets
from .engine.nsi import NsiGenerator, output_file_name
from .engine.makensis import compile_nsi, find_makensis

DEFAULT_BUILD_DIR = "build"
DEFAULT_SCRIPT_NAME = "installer.nsi"


# ---------------------------------------------------------------------------
# 公共步骤
# ---------------------------------------------------------------------------

def _load_and_report(project_path: str) -> tuple[Project | None, list[str]]:
    """加载工程并校验，返回 (工程, 错误信息)。有阻断级错误时工程为 None。"""
    project = load_project(project_path)
    errors, warnings = split(check_project(project))

    for line in warnings:
        print("  " + line, file=sys.stderr)

    return (project if not errors else None), errors


def _modes(project: Project, requested: str) -> list[str]:
    if requested == "all":
        return list(project.build.modes)
    return [requested]


def _write_script(project: Project, mode: str, build_dir: Path, total_modes: int) -> tuple[Path, Path]:
    """生成脚本，返回 (脚本路径, 预期产出的安装包路径)。"""
    generator = NsiGenerator(project, mode, build_dir)
    name = output_file_name(project, mode, total_modes)
    text = generator.generate(name)

    script = build_dir / DEFAULT_SCRIPT_NAME
    assets.write_utf8_bom(text, script)

    out_dir = project.output_dir()
    return script, out_dir / name


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def cmd_validate(args: argparse.Namespace) -> int:
    print(f"校验工程：{args.project}")
    project, errors = _load_and_report(args.project)
    if errors:
        print("\n校验未通过：", file=sys.stderr)
        for line in errors:
            print("  " + line, file=sys.stderr)
        return 2
    assert project is not None
    try:
        print(f"\n校验通过。")
        print(f"  应用名    : {project.app.name} {project.app.version}")
        print(f"  安装目录名: {project.app.dir_name}")
        print(f"  主程序    : {project.app.main_exe}")
        print(f"  打包内容  : {len(list(project.iter_payload()))} 个文件")
        print(f"  输出模式  : {', '.join(project.build.modes)}")
        return 0
    finally:
        project.cleanup()


def cmd_generate(args: argparse.Namespace) -> int:
    project, errors = _load_and_report(args.project)
    if errors:
        for line in errors:
            print("  " + line, file=sys.stderr)
        return 2
    assert project is not None

    try:
        modes = _modes(project, args.mode)
        build_dir = project.resolve("build", args.build_dir)
        for mode in modes:
            script, exe = _write_script(project, mode, build_dir, len(modes))
            print(f"[{mode}] 脚本已生成: {script}")
            print(f"          预期产出: {exe}")
        return 0
    finally:
        project.cleanup()


def cmd_build(args: argparse.Namespace) -> int:
    project, errors = _load_and_report(args.project)
    if errors:
        print("校验未通过，未开始打包：", file=sys.stderr)
        for line in errors:
            print("  " + line, file=sys.stderr)
        return 2
    assert project is not None

    try:
        makensis = find_makensis(args.makensis)
        print(f"使用编译器: {makensis}")

        modes = _modes(project, args.mode)
        build_dir = project.resolve("build", args.build_dir)
        produced: list[Path] = []

        for mode in modes:
            script, expected = _write_script(project, mode, build_dir, len(modes))
            defines = ["PER_USER"] if mode == "perUser" else []
            defines.append("OUTFILE_NAME=" + expected.name)
            print(f"\n=== 编译 [{mode}] {script.name}")
            result = compile_nsi(makensis, script, defines)
            if not result.ok:
                print(result.output, file=sys.stderr)
                print(f"编译失败（退出码 {result.returncode}）", file=sys.stderr)
                return 1
            if not expected.is_file():
                print(f"编译报告成功，但没有产出 {expected}", file=sys.stderr)
                return 1
            size_kb = expected.stat().st_size / 1024
            print(f"  -> {expected}  ({size_kb:,.0f} KB)")
            produced.append(expected)

        print("\n打包完成：")
        for path in produced:
            print(f"  {path}")
        return 0
    finally:
        project.cleanup()


def cmd_gui(args: argparse.Namespace) -> int:
    from .ui.main_window import run as run_gui

    return run_gui(getattr(args, "project", None))


def cmd_pack(args: argparse.Namespace) -> int:
    """把（文件夹形式的）工程打成单个 .jianpack 文件。"""
    from .core.serialize import save_project

    project = load_project(args.project)
    try:
        target = save_project(project, args.output, container_mode=True)
    finally:
        project.cleanup()
    print(f"已打包成单个工程文件: {target}")
    return 0


def cmd_unpack(args: argparse.Namespace) -> int:
    """把单个 .jianpack 文件解成文件夹（方便手工改 / 进版本库）。"""
    import shutil

    project = load_project(args.project)
    try:
        if project.work_dir is None:
            print("这个工程本来就是文件夹形式，不需要解包。", file=sys.stderr)
            return 1
        dest = Path(args.output).expanduser().resolve()
        dest.mkdir(parents=True, exist_ok=True)
        for path in project.base_dir.iterdir():
            if path.name == "build":
                continue
            target = dest / path.name
            if path.is_dir():
                shutil.copytree(path, target, dirs_exist_ok=True)
            else:
                shutil.copy2(path, target)
    finally:
        project.cleanup()
    print(f"已解包到: {dest}")
    return 0


# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app",
        description=f"{APP_NAME} v{__version__} —— 把 .jianpack 工程编译成 Windows 安装包",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("project", help="工程文件路径（.jianpack）")
        p.add_argument("--mode", default="all", choices=["perMachine", "perUser", "all"],
                       help="要处理的安装模式，默认 all（按工程里 build.modes）")
        p.add_argument("--build-dir", default=DEFAULT_BUILD_DIR,
                       help=f"中间产物目录（相对工程文件），默认 {DEFAULT_BUILD_DIR}")

    p_validate = sub.add_parser("validate", help="只校验工程，不打包")
    p_validate.add_argument("project", help="工程文件路径（.jianpack）")
    p_validate.set_defaults(func=cmd_validate)

    p_generate = sub.add_parser("generate", help="生成 .nsi 脚本，不编译")
    add_common(p_generate)
    p_generate.set_defaults(func=cmd_generate)

    p_build = sub.add_parser("build", help="生成脚本并编译出安装包")
    add_common(p_build)
    p_build.add_argument("--makensis", default=None, help="makensis.exe 的路径")
    p_build.set_defaults(func=cmd_build)

    p_gui = sub.add_parser("gui", help="打开图形界面（不指定工程则新建一个）")
    p_gui.add_argument("project", nargs="?", default=None, help="要打开的工程文件（可省略）")
    p_gui.set_defaults(func=cmd_gui)

    p_pack = sub.add_parser("pack", help="把工程打包成单个 .jianpack 文件")
    p_pack.add_argument("project", help="工程文件路径（.jianpack）")
    p_pack.add_argument("output", help="输出的单个 .jianpack 文件路径")
    p_pack.set_defaults(func=cmd_pack)

    p_unpack = sub.add_parser("unpack", help="把单个 .jianpack 文件解成文件夹")
    p_unpack.add_argument("project", help="单个 .jianpack 文件路径")
    p_unpack.add_argument("output", help="解包到的文件夹")
    p_unpack.set_defaults(func=cmd_unpack)

    return parser


def _report(message: str, dialog: bool) -> None:
    """把错误告诉用户。

    图形界面版的 exe 没有控制台（``--windowed``），写 stderr 等于扔掉，
    所以那种情况下必须弹个框，否则用户只会看到「程序闪一下就没了」。
    """
    if not dialog:
        print(message, file=sys.stderr)
        return
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, message)
        root.destroy()
    except Exception:  # noqa: BLE001 - 连弹框都失败就只能算了
        pass


def normalize_argv(argv: list[str]) -> list[str]:
    """把命令行整理成规范的子命令形式。

    - 不带参数（双击 exe）→ ``gui``；
    - 只有一个 ``.jianpack`` 路径（双击工程文件）→ ``gui <文件>``，
      这样会直接进主界面，跳过欢迎页和启动选择窗口。
    """
    if not argv:
        return ["gui"]
    if not argv[0].startswith("-") and argv[0].lower().endswith(PROJECT_EXT):
        return ["gui", argv[0]]
    return argv


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = normalize_argv(argv)

    # 图形界面版的 exe 里 sys.stdout / stderr 是 None，先用空设备顶上，
    # 免得 argparse 之类的库往 None 上写。
    windowed = sys.stderr is None
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code != 0 and windowed:
            _report("命令行参数不正确。\n\n直接双击运行即可打开图形界面，不需要参数。", True)
        return code

    try:
        return int(args.func(args))
    except ProjectFileError as exc:
        _report(f"工程文件有问题：{exc}", windowed)
        return 2
    except PackError as exc:
        _report(str(exc), windowed)
        return 1
    except KeyboardInterrupt:
        _report("已取消。", False)
        return 130
    except Exception as exc:  # noqa: BLE001 - 兜底，别让用户看到闪退
        _report(f"意外错误：{exc!r}", windowed)
        return 1
