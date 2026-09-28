# -*- coding: utf-8 -*-
"""把设计器打包成可以分发的 exe（内嵌便携版 NSIS）。

产出（都在 dist\\ 下）：
    简包装.exe                图形界面版，双击即用，**发给朋友不用装任何东西**
    aipack.exe                命令行版，便于脚本化和自动化测试

为什么要先「搬到临时目录再打包」：
  1. 工程放在 OneDrive 里，PyInstaller 清理工作目录时会被同步进程锁住；
  2. PyInstaller 在源目录和工作目录跨盘符时会报
     ``path is on mount 'E:', start on mount 'C:'``。
  先把要打包的东西复制到系统临时目录，这两个问题都绕开了。

用法：
    python tools\\build-exe.py            # 两个都打
    python tools\\build-exe.py gui        # 只打界面版
    python tools\\build-exe.py cli        # 只打命令行版
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import APP_NAME, __version__  # noqa: E402

DIST = ROOT / "dist"
WORK = Path(os.environ.get("AIPACK_BUILD_DIR")
            or (Path(tempfile.gettempdir()) / "aipack-pyinstaller"))
VENDOR = ROOT / "vendor" / "nsis"
ICON = ROOT / "assets" / "packer.ico"

GUI_EXE = "简包装.exe"

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")

# 随分发包一起给出的许可与声明（Apache-2.0 要求「许可随副本分发」）
LEGAL_FILES = ("LICENSE", "NOTICE", "THIRD-PARTY-NOTICES.md")


def _force_remove(function, path, _excinfo) -> None:
    """删除失败时的兜底：去掉只读属性再试一次。"""
    try:
        os.chmod(path, stat.S_IWRITE)
        function(path)
    except OSError:
        pass


def rmtree(path: Path, attempts: int = 5) -> None:
    """带重试的删除 —— Windows 上文件常被同步 / 杀软临时占住。"""
    for index in range(attempts):
        if not path.exists():
            return
        try:
            shutil.rmtree(path, onerror=_force_remove)
        except OSError:
            pass
        if not path.exists():
            return
        time.sleep(1.0 * (index + 1))
    shutil.rmtree(path, ignore_errors=True)


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
        return
    except ImportError:
        pass
    print("没有找到 PyInstaller，正在安装…")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"],
                   check=True)


def fresh_copy(source: Path, target: Path) -> None:
    """先删干净再复制 —— 避免上一次运行留下的文件互相干扰。

    ``dirs_exist_ok=True`` 是保险：Windows 上偶尔有文件刚被释放、
    删不干净，这时直接覆盖比彻底失败要好。
    """
    rmtree(target)
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, ignore=IGNORE, dirs_exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def stage_project() -> Path:
    """把要打包的内容复制到临时目录（必须和 build 目录在同一个盘）。"""
    stage = WORK / "stage"
    rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)

    fresh_copy(ROOT / "aipack.py", stage / "aipack.py")
    fresh_copy(ROOT / "app", stage / "app")
    # 整个 assets 一起带上：程序图标 + 「使用教程」的配图
    fresh_copy(ROOT / "assets", stage / "assets")
    fresh_copy(VENDOR, stage / "vendor" / "nsis")
    return stage


def version_file(stage: Path) -> Path:
    """生成 exe 属性里显示的版本 / 版权信息。"""
    parts = [int(x) for x in (__version__.split(".") + ["0", "0", "0", "0"])[:4]]
    quad = ", ".join(str(p) for p in parts)
    path = stage / "version_info.txt"
    path.write_text(
        "VSVersionInfo(\n"
        f"  ffi=FixedFileInfo(filevers=({quad}), prodvers=({quad}), mask=0x3f, "
        "flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),\n"
        "  kids=[\n"
        "    StringFileInfo([\n"
        "      StringTable('080404B0', [\n"
        f"        StringStruct('CompanyName', '{APP_NAME}'),\n"
        f"        StringStruct('FileDescription', '{APP_NAME}'),\n"
        f"        StringStruct('FileVersion', '{__version__}'),\n"
        "        StringStruct('InternalName', 'aipack'),\n"
        f"        StringStruct('OriginalFilename', '{GUI_EXE}'),\n"
        f"        StringStruct('ProductName', '{APP_NAME}'),\n"
        f"        StringStruct('ProductVersion', '{__version__}')])\n"
        "    ]),\n"
        "    VarFileInfo([VarStruct('Translation', [2052, 1200])])\n"
        "  ]\n"
        ")\n",
        encoding="utf-8")
    return path


def build(name: str, windowed: bool, stage: Path, version: Path) -> Path:
    """返回产出的 exe 路径（onedir 模式下在 <out>/<name>/<name>.exe）。"""
    out_dir = WORK / "dist"
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        # 用 onedir 而不是 onefile：onefile 每次启动都要把内嵌的 4 MB NSIS
        # 解压到临时目录，实测启动要 30 秒以上（还要被实时防护逐个扫描）。
        "--onedir",
        "--name", name,
        "--distpath", str(out_dir),
        "--workpath", str(WORK / "obj"),
        "--specpath", str(stage),
        "--icon", "assets/" + ICON.name,
        "--version-file", str(version),
        # 便携版 NSIS 一起塞进去
        "--add-data", f"{stage / 'vendor' / 'nsis'}{os.pathsep}vendor\\nsis",
        # 程序图标 + 帮助里的「使用教程」配图（运行时从 sys._MEIPASS/assets 读）
        "--add-data", f"{stage / 'assets'}{os.pathsep}assets",
        "--hidden-import", "app.ui.main_window",
        "--hidden-import", "PIL.ImageOps",
        # Pillow：只要常规格式。AVIF 插件单个就有 7.6 MB，还会拖进 OpenSSL，
        # 对"把用户的照片裁成 BMP"这件事毫无用处，剔掉。
        "--exclude-module", "PIL._avif",
        "--exclude-module", "PIL.AvifImagePlugin",
        "--exclude-module", "numpy",
        "--exclude-module", "unittest",
        "--exclude-module", "pydoc_data",
        "--windowed" if windowed else "--console",
        "aipack.py",
    ]
    print()
    print("=== 打包", name, "（", "界面版" if windowed else "命令行版", "）")
    subprocess.run(args, check=True, cwd=stage)

    produced = out_dir / name / f"{name}.exe"
    if not produced.is_file():
        raise SystemExit(f"没有产出：{produced}")
    return produced


def deliver(source_exe: Path, final_name: str) -> Path:
    """把 PyInstaller 的产出搬进 dist\\，并换上中文名。"""
    folder = source_exe.parent
    target_dir = DIST / final_name
    rmtree(target_dir)
    if target_dir.exists():
        # 删不掉就直接搬失败，免得 shutil.move 把文件夹嵌套进去
        raise SystemExit(f"目标目录已存在且删不掉（可能被占用）：{target_dir}")
    shutil.move(str(folder), str(target_dir))

    exe = target_dir / source_exe.name
    if exe.stem != final_name:
        renamed = exe.with_name(final_name + ".exe")
        if renamed.exists():
            renamed.unlink()
        shutil.move(str(exe), str(renamed))
        exe = renamed
    return exe


def copy_legal_files(folder: Path) -> None:
    """把 LICENSE / NOTICE / THIRD-PARTY-NOTICES.md 放进分发包根目录。"""
    for name in LEGAL_FILES:
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, folder / name)


def folder_size(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024 / 1024


def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else "all"

    if not VENDOR.is_dir():
        print(f"缺少便携版 NSIS：{VENDOR}", file=sys.stderr)
        print("先执行：python tools\\vendor-nsis.py", file=sys.stderr)
        return 2

    if not ICON.is_file():
        print("生成程序图标…")
        subprocess.run([sys.executable, str(ROOT / "tools" / "make_app_icon.py")],
                       check=True, cwd=ROOT)

    ensure_pyinstaller()
    WORK.mkdir(parents=True, exist_ok=True)
    rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)

    print("暂存目录:", WORK)
    stage = stage_project()
    version = version_file(stage)

    produced: list[Path] = []
    if what in ("all", "gui"):
        raw = build("aipack-gui", windowed=True, stage=stage, version=version)
        exe = deliver(raw, "简包装")
        copy_legal_files(exe.parent)
        produced.append(exe)
    if what in ("all", "cli"):
        raw = build("aipack", windowed=False, stage=stage, version=version)
        exe = deliver(raw, "aipack")
        copy_legal_files(exe.parent)
        produced.append(exe)

    print()
    print("打包完成（dist 目录里每个子文件夹都是一个可直接运行的完整程序）：")
    for path in produced:
        print(f"  {path}")
        print(f"      整个文件夹 {folder_size(path.parent):.1f} MB")
    print()
    print("分发方式：把 dist\\<文件夹> 整个压缩发给别人，解压后双击里面的 exe 即可。")
    print("对方不需要安装 Python、NSIS 或任何运行时。")
    rmtree(stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
