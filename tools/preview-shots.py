# -*- coding: utf-8 -*-
"""把预览渲染出来，和真实安装程序的截图并排比对（开发用）。

真实截图（g01~g06）是同一个 demo 工程编译出来的安装程序截图，
所以可以直接逐页对照，看预览画得像不像。

用法：python tools\\preview-shots.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.core.project import load_project  # noqa: E402
from app.ui import preview  # noqa: E402

SHOTS = ROOT / "demo" / "feasibility" / "screenshots"
PROJECT = ROOT / "demo" / "feasibility" / "demo.aiproj"

# 预览页 -> 真实截图
PAIRS = [
    ("welcome", "g01.png", "欢迎页"),
    ("license", "g02.png", "许可协议"),
    ("changelog", "g03.png", "更新日志"),
    ("directory", "g04.png", "安装位置"),
    ("options", "g05.png", "安装选项"),
    ("finish", "g06.png", "完成页"),
]


def font(size: int):
    for candidate in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    project = load_project(PROJECT)
    print("预览页:", preview.available_pages(project))

    rows = []
    for key, real_name, title in PAIRS:
        rendered = preview.render(project, key)
        out = SHOTS / f"预览-{key}.png"
        rendered.save(out)

        real_path = SHOTS / real_name
        real = Image.open(real_path).convert("RGB") if real_path.is_file() else None
        rows.append((title, real, rendered))
        print(f"  {title:6s} -> {out.name}  {rendered.size}")

    if not any(real for _, real, _ in rows):
        print("没有找到真实截图，跳过对比图")
        return 0

    pad, gap, label_h, top = 20, 14, 26, 56
    cell_w = max(r.width if r else 0 for _, r, _ in rows) + \
             max(p.width for _, _, p in rows)
    width = pad * 2 + 2 * 503 + gap
    height = top + pad + len(rows) * (label_h + 362 + gap)

    canvas = Image.new("RGB", (width, height), (244, 246, 250))
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 16), "左：真实安装程序    右：本软件的实时预览",
              font=font(18), fill=(26, 68, 190))

    for index, (title, real, rendered) in enumerate(rows):
        y = top + pad + index * (label_h + 362 + gap)
        draw.text((pad, y), title, font=font(14), fill=(60, 60, 70))
        if real is not None:
            canvas.paste(real, (pad, y + label_h))
            draw.rectangle([pad - 1, y + label_h - 1, pad + 503, y + label_h + 362],
                           outline=(205, 212, 224))
        else:
            draw.text((pad + 8, y + label_h + 12), "（没有真实截图）",
                      font=font(13), fill=(160, 160, 160))
        right = pad + 503 + gap
        canvas.paste(rendered, (right, y + label_h))
        draw.rectangle([right - 1, y + label_h - 1, right + 503, y + label_h + 362],
                       outline=(205, 212, 224))

    out = SHOTS / "预览对比.png"
    canvas.save(out)
    print("对比图:", out, canvas.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
