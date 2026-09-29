# -*- coding: utf-8 -*-
"""在图形界面里真正跑一遍「校验 -> 打包」（开发用）。

会直接调用打包页自己的按钮逻辑，所以覆盖的是界面这条路径，
包括后台线程、日志回填、保存工程这些环节。

用法：
    python tools\\gui-build-test.py <工程文件> [截图输出目录]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab  # noqa: E402

from app.ui.main_window import MainWindow  # noqa: E402


def pump(window: MainWindow, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        window.update()
        time.sleep(0.04)


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python tools\\gui-build-test.py <工程文件> [截图目录]")
        return 2

    project = Path(sys.argv[1]).resolve()
    out_dir = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None

    window = MainWindow(project)
    window.attributes("-topmost", True)
    window.update()
    pump(window, 0.5)

    window._select_step(len(window._pages) - 1)
    page = window._pages[-1]
    panel = window.build_panel            # 打包动作现在在左栏
    pump(window, 0.3)

    print("=== 1. 点「校验工程」")
    panel.run("validate")
    pump(window, 1.5)
    print(panel.log.get("1.0", "end").rstrip())

    print()
    print("=== 2. 点「开始打包」")
    panel.run("build")
    deadline = time.time() + 300
    while panel._busy and time.time() < deadline:
        window.update()
        time.sleep(0.1)
    pump(window, 0.5)

    log = panel.log.get("1.0", "end").rstrip()
    print(log)

    if out_dir and "打包完成" in log:
        out_dir.mkdir(parents=True, exist_ok=True)
        window.update()
        time.sleep(0.4)
        x, y = window.winfo_rootx(), window.winfo_rooty()
        w, h = window.winfo_width(), window.winfo_height()
        target = out_dir / "gui07-build-log.png"
        ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(target)
        print("\n截图 ->", target)

    window.attributes("-topmost", False)
    window.destroy()
    return 0 if "打包完成" in log else 1


if __name__ == "__main__":
    raise SystemExit(main())
