# -*- coding: utf-8 -*-
"""在设计器自己的进程里逐页截图（开发用）。

比用外部脚本点鼠标可靠得多：能直接调用窗口自己的方法切换步骤，
截出来的图也精确到客户区，不带窗口边框。

用法：
    python tools\\gui-screenshots.py [工程文件] [输出目录]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont, ImageGrab  # noqa: E402

from app.ui.main_window import STEPS, MainWindow  # noqa: E402

DEFAULT_PROJECT = ROOT / "demo" / "feasibility" / "demo.jianpack"
DEFAULT_OUT = ROOT / "demo" / "feasibility" / "screenshots"

LABELS = (
    "1. 基本信息",
    "2. 打包内容",
    "3. 安装设置",
    "4. 安装界面",
    "5. 打包",
)


def _font(size: int):
    for candidate in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc",
                      r"C:\Windows\Fonts\simhei.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def montage(paths: list[Path], out_path: Path) -> None:
    """把各页截图缩排成一张总览图。"""
    thumbs = [(Image.open(p).convert("RGB"), label)
              for p, label in zip(paths, LABELS)]
    scale = 0.52
    tw = int(thumbs[0][0].width * scale)
    th = int(thumbs[0][0].height * scale)
    cols, pad, gap, label_h, top = 3, 22, 16, 30, 62
    rows = (len(thumbs) + cols - 1) // cols

    width = pad * 2 + cols * tw + (cols - 1) * gap
    height = top + pad + rows * (label_h + th) + (rows - 1) * gap

    canvas = Image.new("RGB", (width, height), (244, 246, 250))
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 18), "简包装  ·  图形界面", font=_font(22),
              fill=(26, 68, 190))

    for index, (image, label) in enumerate(thumbs):
        row, col = divmod(index, cols)
        x = pad + col * (tw + gap)
        y = top + row * (label_h + th + gap)
        draw.text((x + 2, y + 3), label, font=_font(15), fill=(60, 60, 70))
        canvas.paste(image.resize((tw, th), Image.LANCZOS), (x, y + label_h))
        draw.rectangle([x - 1, y + label_h - 1, x + tw, y + label_h + th],
                       outline=(205, 212, 224))

    canvas.save(out_path)
    print("  ->", out_path.name)


def shot(window: MainWindow, path: Path) -> None:
    window.update_idletasks()
    window.update()
    time.sleep(0.35)
    window.update()
    # Tk 给的是逻辑像素，ImageGrab 抓的是物理像素：高 DPI 屏上必须换算，
    # 否则抓出来的画面会整体偏移。
    scale = ImageGrab.grab().width / max(1, window.winfo_screenwidth())
    x, y = window.winfo_rootx() * scale, window.winfo_rooty() * scale
    w, h = window.winfo_width() * scale, window.winfo_height() * scale
    image = ImageGrab.grab(bbox=(round(x), round(y), round(x + w), round(y + h)))
    if abs(scale - 1.0) > 0.01:
        image = image.resize((window.winfo_width(), window.winfo_height()), Image.LANCZOS)
    image.save(path)
    print("  ->", path.name)


def main() -> int:
    project = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PROJECT
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    window = MainWindow(project)
    window.attributes("-topmost", True)
    window.lift()
    window.update()
    time.sleep(0.6)

    for index, page_cls in enumerate(STEPS):
        window._select_step(index)
        window.update()
        shot(window, out_dir / f"gui{index + 1:02d}.png")

    window.attributes("-topmost", False)
    window.destroy()

    produced = [out_dir / f"gui{i + 1:02d}.png" for i in range(len(STEPS))]
    montage(produced, out_dir / "总览-设计器界面.png")
    print("完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
