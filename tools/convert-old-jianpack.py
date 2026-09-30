# -*- coding: utf-8 -*-
"""一次性工具：把旧的 zip 版 ``.jianpack`` 转成新的 JIANPACK2 格式。

**只用于 v1.0.0 这次格式升级**（软件本身已经不再读旧格式）。转换完成后这个脚本
就没有用了，可以删掉。

用法::

    python tools\\convert-old-jianpack.py <旧的.jianpack> [输出的.jianpack]

不指定输出文件时**原地覆盖**（会先把原文件备份成 ``<名字>.old-format``）。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core import container                      # noqa: E402
from app.core.project import load_project           # noqa: E402
from app.core.serialize import save_project         # noqa: E402
from app.core.versions import load_store            # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python tools\\convert-old-jianpack.py <旧的.jianpack> [输出的.jianpack]")
        return 2
    src = Path(sys.argv[1]).expanduser().resolve()
    if not src.is_file():
        print("找不到文件:", src)
        return 2
    kind = container.sniff(src)
    if kind == "container":
        print("本来就是新格式，不用转换。")
        return 0
    if kind != "other":
        print("这个文件既不是新格式、也不像旧的 zip 版工程：", kind)
        return 2

    work = Path(tempfile.mkdtemp(prefix="jianpack-convert-"))
    try:
        with zipfile.ZipFile(src) as archive:
            archive.extractall(work)
        if not (work / "project.json").is_file():
            print("旧的工程里没有 project.json，无法转换。")
            return 2

        out = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) > 2 else src
        tmp_out = work / "converted.jianpack"

        # 直接读旧工作目录，按新的"每版一块 + 索引"写出来
        from app.core import container as _c  # noqa: F401

        project = load_project(work / "project.json")
        versions = load_store(project)
        print("版本数:", len(versions.items),
              " 当前:", versions.current_item().display() if versions.current_item() else "（无）")
        save_project(project, tmp_out, container_mode=True)
        project.cleanup()

        # 校验：新文件能打开、版本数一致
        check = load_project(tmp_out)
        try:
            if len(load_store(check).items) != len(versions.items):
                print("！！转换后版本数不一致，已放弃。")
                return 1
        finally:
            check.cleanup()
        manifest = container.read_manifest(tmp_out)
        print("已生成新格式：", tmp_out, tmp_out.stat().st_size // 1024, "KB",
              " 版本块:", len(manifest.get("versions") or []),
              " 根数据块:", bool(manifest.get("data")))

        if out == src:
            backup = src.with_name(src.name + ".old-format")
            if not backup.exists():
                shutil.copy2(src, backup)
                print("原文件已备份为：", backup)
        shutil.copy2(tmp_out, out)
        print("完成：", out)
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
