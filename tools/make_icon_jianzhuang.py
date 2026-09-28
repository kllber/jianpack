# -*- coding: utf-8 -*-
"""「简装」图标设计稿生成器。

产物全部输出到 ``design/简装-图标/``，**不会**用到软件本身里
（程序的图标仍是 assets/packer.ico，显示名仍是 app/__init__.py 里的常量）。

方案：
  C 青绿 · 竹简      纯图形。「简」的本义就是竹简，一捆竹简本身就是"打包"的样子
  D 青绿 · 简字      单字标，最直白
  E 绿卡 · 简字      绿底上开一张白卡，卡里是绿色「简」
  F 青绿 · 一叠文件  纯图形，一叠待打包的文件

用法：python tools\\make_icon_jianzhuang.py
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "design" / "简装-图标"

SUPERSAMPLE = 4
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
PREVIEW_SIZES = (256, 128, 64, 48, 32, 24, 16)

CHAR = "简"
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",   # 微软雅黑 Bold
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]
LABEL_FONT_CANDIDATES = FONT_CANDIDATES

GREEN_TOP = (34, 196, 170)
GREEN_BOTTOM = (8, 104, 92)
GREEN_DARK = GREEN_BOTTOM


# ---------------------------------------------------------------------------
# 基础绘制
# ---------------------------------------------------------------------------

def load_font(candidates, size: int):
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def gradient(size: int, top, bottom) -> Image.Image:
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        row = (lerp(top[0], bottom[0], t), lerp(top[1], bottom[1], t),
               lerp(top[2], bottom[2], t))
        for x in range(size):
            px[x, y] = row
    return img


def rounded_base(size: int, top, bottom, radius_ratio: float = 0.225,
                 gloss: int = 34) -> Image.Image:
    """圆角方块 + 垂直渐变（顶部一层很淡的高光）。"""
    base = gradient(size, top, bottom)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * radius_ratio), fill=255)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(base, (0, 0), mask)

    if gloss:
        layer = Image.new("L", (size, size), 0)
        gd = ImageDraw.Draw(layer)
        for y in range(int(size * 0.5)):
            gd.line([(0, y), (size, y)], fill=int(gloss * (1 - y / (size * 0.5))))
        layer = Image.composite(layer, Image.new("L", (size, size), 0), mask)
        white = Image.new("L", (size, size), 255)
        img = Image.alpha_composite(img, Image.merge("RGBA", (white, white, white, layer)))
    return img


_ink_cache: dict = {}


def measure_ink(font, char: str) -> tuple[int, int, int, int]:
    """量出字形的**真实墨迹**范围（相对绘制原点的像素）。

    PIL 的 ``textbbox`` 会带上字形两侧的留白，拿它做边缘对齐会差几个像素；
    这里真的把字画到一张空白图上，再取非零像素的包围盒。
    """
    key = (getattr(font, "path", ""), font.size, char)
    if key in _ink_cache:
        return _ink_cache[key]

    pad = font.size * 2
    canvas = Image.new("L", (font.size * 4, font.size * 4), 0)
    ImageDraw.Draw(canvas).text((pad, pad), char, font=font, fill=255)
    box = canvas.getbbox()
    result = (0, 0, font.size, font.size) if box is None else (
        box[0] - pad, box[1] - pad, box[2] - pad, box[3] - pad)
    _ink_cache[key] = result
    return result


def draw_char(img: Image.Image, char: str, fill_ratio: float = 0.66,
              color=(255, 255, 255, 255), center=(0.5, 0.5),
              nudge: float = -0.01,
              right: float | None = None, bottom: float | None = None) -> None:
    """把字画上去。

    默认让字形的**墨迹中心**落在 ``center``；给了 ``right`` / ``bottom``
    就按**墨迹边缘**对齐（值为相对画布的比例）。

    ``fill_ratio`` 是墨迹高度相对画布的比例；``nudge`` 是 1% 的光学微调。
    """
    size = img.width
    target = size * fill_ratio
    font = load_font(FONT_CANDIDATES, int(target))
    for _ in range(24):
        box = measure_ink(font, char)
        height = box[3] - box[1]
        if abs(height - target) <= max(1, target * 0.01):
            break
        font = load_font(FONT_CANDIDATES, max(8, int(font.size * target / max(1, height))))

    box = measure_ink(font, char)
    if right is not None:
        x = size * right - box[2]
    else:
        x = size * center[0] - (box[0] + box[2]) / 2
    if bottom is not None:
        y = size * bottom - box[3]
    else:
        y = size * center[1] - (box[1] + box[3]) / 2 + size * nudge
    ImageDraw.Draw(img).text((x, y), char, font=font, fill=color)


# ---------------------------------------------------------------------------
# 各个方案
# ---------------------------------------------------------------------------

def variant_c(size: int) -> Image.Image:
    """青绿 · 竹简 + 简字。

    「简」的本义就是竹简 —— 几片竹片用绳编成一册，本身就是"打包"的样子。
    中间那根做宽一点（像竹简册里的"篇名简"），上面刻一个小小的「简」字。
    """
    img = rounded_base(size, GREEN_TOP, GREEN_BOTTOM)
    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    cut = (*GREEN_DARK, 255)

    thin = size * 0.095
    wide = size * 0.355
    gap = size * 0.045
    total = thin + gap + wide + gap + thin
    left = (size - total) / 2
    top, bottom = size * 0.160, size * 0.840
    radius = thin * 0.38

    for x, width in ((left, thin),
                     (left + thin + gap, wide),
                     (left + thin + gap + wide + gap, thin)):
        d.rounded_rectangle([x, top, x + width, bottom], radius=radius, fill=white)

    # 编绳：两道，避开中间的字
    cord_h = max(1, size * 0.042)
    for ratio in (0.243, 0.757):
        y = size * ratio
        d.rectangle([left - size * 0.020, y, left + total + size * 0.020, y + cord_h],
                    fill=cut)

    # 宽简上的小「简」字
    draw_char(img, CHAR, 0.235, color=cut)
    return img


def variant_d(size: int) -> Image.Image:
    """青绿 · 简字。最直白的单字标。"""
    img = rounded_base(size, GREEN_TOP, GREEN_BOTTOM)
    draw_char(img, CHAR, 0.66)
    return img


def variant_e(size: int) -> Image.Image:
    """绿卡 · 简字。绿底上开一张白卡，卡里是绿色「简」。"""
    img = rounded_base(size, GREEN_TOP, GREEN_BOTTOM)
    margin = size * 0.165
    ImageDraw.Draw(img).rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=size * 0.135, fill=(255, 255, 255, 255))
    draw_char(img, CHAR, 0.44, color=(*GREEN_DARK, 255))
    return img


def variant_f(size: int) -> Image.Image:
    """青绿 · 一叠文件。三张纸错开叠着，等你去打包。"""
    img = rounded_base(size, GREEN_TOP, GREEN_BOTTOM)
    d = ImageDraw.Draw(img)

    w, h = size * 0.40, size * 0.50
    base_x, base_y = size * 0.5 - w / 2, size * 0.5 - h / 2
    radius = size * 0.055

    for dx, dy, alpha in ((0.115, -0.115, 120), (0.058, -0.058, 175), (0.0, 0.0, 255)):
        x0 = base_x + size * dx
        y0 = base_y + size * dy
        d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=radius,
                            fill=(255, 255, 255, alpha))

    # 最上面那张画几道"文字"，一眼看出是文件
    for index in range(3):
        y = base_y + h * (0.26 + index * 0.21)
        d.rounded_rectangle([base_x + w * 0.16, y, base_x + w * 0.84,
                             y + size * 0.032],
                            radius=size * 0.016, fill=(*GREEN_DARK, 255))

    # 左下角的「简」：垫一块淡色圆角小块，做成一个明确的角标。
    # 小块的右边跟纸的左边缘对齐，整个角标底边留出边距。
    plate = size * 0.225
    plate_right, plate_bottom = base_x / size, 0.895
    d.rounded_rectangle(
        [size * plate_right - plate, size * plate_bottom - plate,
         size * plate_right, size * plate_bottom],
        radius=plate * 0.26, fill=(255, 255, 255, 40))

    draw_char(img, CHAR, 0.172, right=plate_right - 0.028, bottom=plate_bottom - 0.026,
              nudge=0.0)
    return img


VARIANTS = [
    ("C", "青绿 · 竹简", variant_c, "简装-C-青绿竹简.ico"),
    ("D", "青绿 · 简字", variant_d, "简装-D-青绿简字.ico"),
    ("E", "绿卡 · 简字", variant_e, "简装-E-绿卡简字.ico"),
    ("F", "青绿 · 一叠文件", variant_f, "简装-F-一叠文件.ico"),
]


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def render(variant, size: int) -> Image.Image:
    return variant(size * SUPERSAMPLE).resize((size, size), Image.LANCZOS)


def build_preview(images: dict) -> None:
    cell = 256
    pad = 26
    row_h = cell + 44
    baseline = 132
    width = pad * 2 + cell + 40 + 640
    height = pad + 62 + row_h * len(VARIANTS) + pad

    canvas = Image.new("RGB", (width, height), (246, 247, 250))
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 20), "「简装」图标设计稿",
              font=load_font(LABEL_FONT_CANDIDATES, 26), fill=(12, 96, 86))
    draw.text((pad + 268, 28), "大图看设计　右边一排看小尺寸下的辨识度",
              font=load_font(LABEL_FONT_CANDIDATES, 14), fill=(130, 136, 148))

    for index, (key, title, _fn, _name) in enumerate(VARIANTS):
        y = 62 + pad + index * row_h
        draw.text((pad, y + 2), f"方案 {key}　{title}",
                  font=load_font(LABEL_FONT_CANDIDATES, 18), fill=(60, 60, 70))

        big = images[(key, 256)]
        canvas.paste(big, (pad, y + 30), big)
        draw.rectangle([pad - 1, y + 29, pad + cell, y + 29 + cell],
                       outline=(210, 216, 226))

        x = pad + cell + 40
        for size in PREVIEW_SIZES[1:]:
            img = images[(key, size)]
            canvas.paste(img, (x, y + 30 + baseline - size), img)
            draw.text((x, y + 30 + baseline + 8), f"{size}px",
                      font=load_font(LABEL_FONT_CANDIDATES, 11), fill=(140, 146, 158))
            x += max(size, 46) + 22

    canvas.save(OUT / "预览.png")
    print("  -> 预览.png", canvas.size)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    images = {}
    for key, title, fn, file_name in VARIANTS:
        for size in sorted(set(ICON_SIZES) | set(PREVIEW_SIZES)):
            images[(key, size)] = render(fn, size)

        base = images[(key, 256)]
        base.save(OUT / file_name, format="ICO", sizes=[(s, s) for s in ICON_SIZES])
        base.save(OUT / file_name.replace(".ico", ".png"))
        print(f"  -> {file_name}")

    build_preview(images)
    print("完成，输出目录:", OUT)


if __name__ == "__main__":
    main()
