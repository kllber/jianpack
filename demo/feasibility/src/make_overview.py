# -*- coding: utf-8 -*-
"""把安装向导各页面截图拼成一张总览图。

用法：python make_overview.py [文件名前缀，默认 g]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(os.path.dirname(HERE), "screenshots")

PAGES = [
    ("01.png", "1. 欢迎页（自定义竖版位图）"),
    ("02.png", "2. 许可协议页（勾选后才可继续）"),
    ("03.png", "3. 更新日志页（自定义页面）"),
    ("04.png", "4. 安装位置页（路径可自定义）"),
    ("05.png", "5. 安装选项页（快捷方式开关）"),
    ("06.png", "6. 完成页（可勾选立即运行）"),
]

PREFIX = sys.argv[1] if len(sys.argv) > 1 else "g"

FONT = None
for p in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
    if os.path.exists(p):
        FONT = p
        break


def font(size):
    if FONT:
        try:
            return ImageFont.truetype(FONT, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main() -> None:
    imgs = [(Image.open(os.path.join(SHOTS, PREFIX + f)).convert("RGB"), t)
            for f, t in PAGES if os.path.exists(os.path.join(SHOTS, PREFIX + f))]

    pad, gap, label_h, top = 24, 18, 34, 66
    cw = max(i.width for i, _ in imgs)
    ch = max(i.height for i, _ in imgs)
    cols = 3
    rows = (len(imgs) + cols - 1) // cols

    W = pad * 2 + cols * cw + (cols - 1) * gap
    H = top + pad + rows * (label_h + ch) + (rows - 1) * gap

    canvas = Image.new("RGB", (W, H), (244, 246, 250))
    d = ImageDraw.Draw(canvas)

    d.text((pad, 20), "应用安装向导打包软件  ·  可行性验证 Demo 生成的安装程序",
           font=font(24), fill=(24, 68, 190))

    for idx, (img, title) in enumerate(imgs):
        r, c = divmod(idx, cols)
        x = pad + c * (cw + gap)
        y = top + r * (label_h + ch + gap)
        d.text((x + 2, y + 6), title, font=font(17), fill=(60, 60, 70))
        canvas.paste(img, (x, y + label_h))
        d.rectangle([x - 1, y + label_h - 1, x + cw, y + label_h + ch], outline=(205, 212, 224))

    out = os.path.join(SHOTS, "总览-安装向导全部页面.png")
    canvas.save(out)
    print("已生成:", out)


if __name__ == "__main__":
    main()
