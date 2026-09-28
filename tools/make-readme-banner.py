# -*- coding: utf-8 -*-
r"""生成 README 顶部的大横幅（bazzite 风格）。

产出：docs/images/banner.png
用法：python tools\make-readme-banner.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "design" / "简装-图标" / "图标.png"
OUT = ROOT / "docs" / "images" / "banner.png"

W, H = 1280, 320

FONT_CJK_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_LATIN_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
FONT_LATIN = r"C:\Windows\Fonts\segoeui.ttf"

# 深色青绿渐变，和图标配色一致
COLOR_TL = (11, 24, 30)      # 左上
COLOR_BR = (16, 58, 53)      # 右下
COLOR_WHITE = (245, 250, 249)
COLOR_TEAL = (95, 224, 192)
COLOR_TAGLINE = (150, 182, 176)
GLOW = (47, 184, 154)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def make_background() -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        for x in range(W):
            t = 0.55 * (x / (W - 1)) + 0.45 * (y / (H - 1))
            px[x, y] = lerp(COLOR_TL, COLOR_BR, t)
    return img


def add_glow(base: Image.Image) -> None:
    """图标后面加一团柔和的青色光晕。"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy, r = 168, 160, 240
    d.ellipse([cx - r, cy - int(r * 1.15), cx + r, cy + int(r * 1.15)],
              fill=GLOW + (70,))
    layer = layer.filter(ImageFilter.GaussianBlur(110))
    base.alpha_composite(layer) if base.mode == "RGBA" else base.paste(
        Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB"), (0, 0))


def main() -> int:
    if not ICON.is_file():
        print(f"找不到图标：{ICON}", file=sys.stderr)
        return 2

    base = make_background().convert("RGBA")
    add_glow(base)

    # 图标
    icon = Image.open(ICON).convert("RGBA").resize((188, 188), Image.LANCZOS)
    base.alpha_composite(icon, (72, 66))

    draw = ImageDraw.Draw(base)
    x0 = 306
    baseline = 176

    # 中文主标题
    f_name = font(FONT_CJK_BOLD, 114)
    draw.text((x0, baseline), "简包装", font=f_name, fill=COLOR_WHITE, anchor="ls")
    w_name = draw.textlength("简包装", font=f_name)

    # 拉丁名（紧跟其后，颜色为青色）
    f_latin = font(FONT_LATIN_BOLD, 48)
    draw.text((x0 + w_name + 26, baseline), "JianPack", font=f_latin,
              fill=COLOR_TEAL, anchor="ls")

    # 副标题
    f_tag = font(FONT_CJK_BOLD, 25)
    draw.text((x0 + 4, baseline + 56),
              "可视化 Windows 安装包制作工具  ·  Visual Windows Installer Builder",
              font=f_tag, fill=COLOR_TAGLINE, anchor="ls")

    # 底部一条青色细线做点缀
    draw.rectangle([x0 + 4, baseline + 74, W - 74, baseline + 77], fill=GLOW + (110,))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(OUT, "PNG", optimize=True)
    print("已生成:", OUT, Image.open(OUT).size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
