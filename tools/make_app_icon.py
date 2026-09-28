# -*- coding: utf-8 -*-
"""生成设计器自己的程序图标（assets/packer.ico）。

优先用 ``design\\简装-图标\\`` 里的设计稿（图标.png / 图标.ico）转成多尺寸 ico；
找不到设计稿时，退回内置的「紫色圆角方块 + 向下装入托盘」画法。

用法：python tools\\make_app_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

OUT = ROOT / "assets" / "packer.ico"
DESIGN = ROOT / "design" / "简装-图标"
SIZES = [16, 24, 32, 48, 64, 128, 256]

TOP = (137, 106, 255)
BOTTOM = (74, 42, 196)


def from_design() -> Image.Image | None:
    for name in ("图标.png", "图标.ico", "源文件图标.png"):
        path = DESIGN / name
        if path.is_file():
            with Image.open(path) as raw:
                return raw.convert("RGBA")
    return None


def lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def render(px: int) -> Image.Image:
    """内置画法（没有设计稿时的兜底）。"""
    s = px * 4
    base = Image.new("RGB", (s, s))
    pixels = base.load()
    for y in range(s):
        t = y / max(1, s - 1)
        color = (lerp(TOP[0], BOTTOM[0], t),
                 lerp(TOP[1], BOTTOM[1], t),
                 lerp(TOP[2], BOTTOM[2], t))
        for x in range(s):
            pixels[x, y] = color

    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1],
                                           radius=int(s * 0.235), fill=255)

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(base, (0, 0), mask)

    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    d.rounded_rectangle([s * 0.443, s * 0.232, s * 0.557, s * 0.545],
                        radius=s * 0.030, fill=white)
    d.polygon([(s * 0.298, s * 0.515), (s * 0.702, s * 0.515),
               (s * 0.500, s * 0.752)], fill=white)
    d.rounded_rectangle([s * 0.212, s * 0.782, s * 0.788, s * 0.868],
                        radius=s * 0.034, fill=white)
    return img.resize((px, px), Image.LANCZOS)


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    design = from_design()
    if design is not None:
        design.resize((256, 256), Image.LANCZOS).save(
            OUT, format="ICO", sizes=[(s, s) for s in SIZES])
        print("已按设计稿生成:", OUT)
    else:
        render(256).save(OUT, format="ICO", sizes=[(s, s) for s in SIZES])
        print("没找到设计稿，已用内置画法生成:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
