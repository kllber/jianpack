# -*- coding: utf-8 -*-
"""把系统里安装的 NSIS 复制成随软件分发的便携版（``vendor/nsis``）。

只需要编译器本身和它依赖的脚本/插件，不需要手册、示例、卸载程序那些东西，
所以最终体积只有 4 MB 左右。NSIS 是 zlib 类许可，允许随软件一起分发。

用法：python tools\\vendor-nsis.py [NSIS 安装目录]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "vendor" / "nsis"

CANDIDATE_SOURCES = (
    r"C:\Program Files (x86)\NSIS",
    r"C:\Program Files\NSIS",
)

# 必须一起带走的目录
DERIVE_DIRS = ("Bin", "Include", "Stubs", "Contrib", "Plugins")
# 必须带的单文件
DERIVE_FILES = ("makensis.exe", "nsisconf.nsh", "COPYING")
# 用不到、可以省掉的（省体积）
#
# 注意：Contrib\UIs 不能删！MUI2 的 MUI_INTERFACE 会去加载
#       $(NSISDIR)\Contrib\UIs\modern.exe，删了会直接编译失败。
DROP = (
    "Plugins/x86-ansi",       # 我们生成的脚本都是 Unicode 版
    "Contrib/zip2exe",        # 和我们无关的小工具
)


def find_source() -> Path:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if path.is_dir():
            return path
        raise SystemExit(f"目录不存在：{path}")
    for candidate in CANDIDATE_SOURCES:
        if (Path(candidate) / "makensis.exe").is_file():
            return Path(candidate)
    raise SystemExit(
        "找不到 NSIS 安装目录。\n"
        "  先装一个：winget install NSIS.NSIS\n"
        "  或手工指定：python tools\\vendor-nsis.py \"D:\\NSIS\""
    )


def main() -> int:
    source = find_source()
    print("源目录:", source)

    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)

    for name in DERIVE_FILES:
        src = source / name
        if not src.is_file():
            raise SystemExit(f"缺少必需文件：{src}")
        shutil.copy2(src, DEST / name)

    for name in DERIVE_DIRS:
        src = source / name
        if not src.is_dir():
            raise SystemExit(f"缺少必需目录：{src}")
        shutil.copytree(src, DEST / name)

    for relative in DROP:
        target = DEST / relative
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()

    total = sum(f.stat().st_size for f in DEST.rglob("*") if f.is_file())
    count = sum(1 for f in DEST.rglob("*") if f.is_file())
    print(f"完成：{DEST}")
    print(f"  {count} 个文件，{total / 1024 / 1024:.1f} MB")
    print("  （NSIS 采用 zlib 类许可，允许随软件分发，COPYING 已一并复制）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
