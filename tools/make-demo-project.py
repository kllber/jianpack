# -*- coding: utf-8 -*-
"""生成随软件分发的演示工程：``assets/demo/演示测试项目.jianpack``。

启动窗口「最近打开」的第一行固定是这个演示项目，方便新用户参考。
它由 ``demo/feasibility`` 里的示例改成单文件容器（只带 assets / input / src）。

用法：python tools\\make-demo-project.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.project import load_project  # noqa: E402
from app.core.serialize import save_project  # noqa: E402

SRC = ROOT / "demo" / "feasibility" / "demo.jianpack"
OUT = ROOT / "assets" / "demo" / "演示测试项目.jianpack"
DEMO_NAME = "演示测试项目"


def main() -> int:
    src_dir = SRC.parent
    work = Path(tempfile.mkdtemp(prefix="aipack-demobuild-"))
    try:
        for sub in ("assets", "input", "src"):
            source = src_dir / sub
            if source.is_dir():
                shutil.copytree(source, work / sub)

        data = json.loads(SRC.read_text(encoding="utf-8"))
        data["project"]["name"] = DEMO_NAME
        data["build"]["outputDir"] = ""      # 与默认一致：测试打包时输出到桌面
        project_json = work / "demo.jianpack"
        project_json.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                encoding="utf-8")

        project = load_project(project_json)
        try:
            project_json.unlink()          # 不要把那份 JSON 也装进容器
            OUT.parent.mkdir(parents=True, exist_ok=True)
            target = save_project(project, OUT, container_mode=True)
        finally:
            project.cleanup()
        print(f"已生成: {target}  ({target.stat().st_size // 1024} KB)")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
