# -*- coding: utf-8 -*-
"""
生成可行性验证 demo 所需的图形资源。

产出（全部写入 demo/feasibility/assets/）：
    app.ico        程序图标 / 安装包图标（多尺寸）
    welcome.bmp    NSIS MUI 欢迎页左侧竖版位图（164 x 314）
    header.bmp     NSIS MUI 内页顶部横版位图（150 x 57）

说明：Pillow 只在"设计器"运行期使用，生成出来的安装包本身不依赖 Pillow。
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")

# 主题色：与设计器 GUI 保持一致的蓝
C_TOP = (86, 148, 255)
C_BOT = (24, 68, 190)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",   # 微软雅黑 Bold
    r"C:\Windows\Fonts\msyh.ttc",     # 微软雅黑
    r"C:\Windows\Fonts\simhei.ttf",   # 黑体
]


def lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def pick_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def gradient(width: int, height: int, top, bottom) -> Image.Image:
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        t = y / max(1, height - 1)
        color = (lerp(top[0], bottom[0], t),
                 lerp(top[1], bottom[1], t),
                 lerp(top[2], bottom[2], t))
        for x in range(width):
            px[x, y] = color
    return img


def render_logo(px: int) -> Image.Image:
    """渲染圆角方块 + 白色"向下装入托盘"箭头，象征"安装"。"""
    s = px * 4
    base = gradient(s, s, C_TOP, C_BOT)

    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, s - 1, s - 1], radius=int(s * 0.235), fill=255)

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(base, (0, 0), mask)

    d = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)
    d.rounded_rectangle([s * 0.443, s * 0.242, s * 0.557, s * 0.560],
                        radius=s * 0.030, fill=white)          # 竖杆
    d.polygon([(s * 0.300, s * 0.530), (s * 0.700, s * 0.530),
               (s * 0.500, s * 0.760)], fill=white)            # 箭头
    d.rounded_rectangle([s * 0.225, s * 0.792, s * 0.775, s * 0.856],
                        radius=s * 0.032, fill=white)          # 托盘

    return img.resize((px, px), Image.LANCZOS)


def build_icon() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base = render_logo(256)
    out = os.path.join(ASSETS, "app.ico")
    base.save(out, format="ICO", sizes=[(s, s) for s in sizes])
    print("  app.ico        ->", out)


def build_welcome() -> None:
    w, h = 164, 314
    img = gradient(w, h, (100, 150, 245), (18, 54, 158))

    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([-80, -90, 118, 108], fill=(255, 255, 255, 16))   # 装饰光晕
    d.ellipse([56, 196, 262, 402], fill=(255, 255, 255, 12))

    logo = render_logo(76)
    img.paste(logo, ((w - 76) // 2, 40), logo)

    name_font = pick_font(19)
    sub_font = pick_font(10)
    foot_font = pick_font(9)

    def center(text: str, font, y: int, fill) -> None:
        left, top, right, bottom = d.textbbox((0, 0), text, font=font)
        d.text(((w - (right - left)) / 2 - left, y), text, font=font, fill=fill)

    center("我的小工具", name_font, 132, (255, 255, 255, 255))
    center("安装向导", sub_font, 162, (198, 216, 255, 255))

    d.line([24, 244, w - 24, 244], fill=(255, 255, 255, 60), width=1)
    center("示例软件工作室", foot_font, 254, (190, 210, 250, 255))

    out = os.path.join(ASSETS, "welcome.bmp")
    img.save(out)
    print("  welcome.bmp    ->", out)


def build_header() -> None:
    w, h = 150, 57
    img = gradient(w, h, (72, 128, 240), (26, 70, 190))

    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([84, -40, 200, 76], fill=(255, 255, 255, 14))

    logo = render_logo(30)
    img.paste(logo, (11, 13), logo)

    font = pick_font(13)
    d.text((50, 19), "我的小工具", font=font, fill=(255, 255, 255, 255))

    out = os.path.join(ASSETS, "header.bmp")
    img.save(out)
    print("  header.bmp     ->", out)


def main() -> None:
    os.makedirs(ASSETS, exist_ok=True)
    print("[assets] 生成图形资源：")
    build_icon()
    build_welcome()
    build_header()


if __name__ == "__main__":
    main()
