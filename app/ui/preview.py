"""安装向导实时预览。

不是真的跑去跑一遍 NSIS，而是按 MUI2 的真实版式**画一个仿真图**：
窗口 503×362、左侧竖版位图 164 宽、内页页头位图 150×57、按钮 75×21……
这些数字都是从真实安装程序的截图里量出来的（见 demo/feasibility/screenshots）。

渲染用 Pillow 一次画整张图，再交给 Tk 显示。相比用 Canvas 拼控件，
这种方式对中文换行、字体、间距的控制更直接，也不容易和编辑区抢布局。
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageDraw, ImageFont

from ..core.project import Project
from ..engine.nsi import MODE_LABELS, placeholder_table
from ..engine.textutil import expand_placeholders
from . import theme
from ..i18n import is_english
from ..i18n import t as _

# ---------------------------------------------------------------------------
# 版式常量（单位：像素，取自真实安装程序截图）
# ---------------------------------------------------------------------------

WINDOW_W, WINDOW_H = 503, 362
BORDER = 2
TITLE_H = 26
CLIENT_X, CLIENT_Y = BORDER, BORDER + TITLE_H
CLIENT_W = WINDOW_W - BORDER * 2          # 499
CLIENT_H = WINDOW_H - TITLE_H - BORDER * 2  # 332

BANNER_W = 164                            # 欢迎页左侧竖版位图宽度
HEADER_W, HEADER_H = 150, 57              # 内页页头位图
BUTTON_W, BUTTON_H = 75, 21
BUTTON_GAP = 13
BOTTOM_H = 43                             # 分隔线以下（按钮区）高度
SEPARATOR_Y = CLIENT_H - BOTTOM_H         # 290

# 预览面板整体需要的宽度（Pillow 画出来的图 + 边距）。
# 用常量而不是去问 Tk 要 reqwidth —— 那个值在窗口还没布局完时不可靠。
PANEL_WIDTH = WINDOW_W + 36

EDGE = 12                                 # 内容左右留白
TEXT_X = 182                              # 欢迎页标题/正文的左边距

COL_BORDER = (0, 0, 0)
COL_TITLEBAR = (0, 0, 0)
COL_TITLEBAR_TEXT = (240, 240, 240)
COL_CAPTION = (200, 200, 200)
COL_CLIENT = (255, 255, 255)
COL_BOTTOM = (240, 240, 240)
COL_SEPARATOR = (160, 160, 160)
COL_BUTTON_FACE = (253, 253, 253)
COL_BUTTON_EDGE = (0, 0, 0)
COL_TEXT = (0, 0, 0)
COL_TEXT_DIM = (90, 90, 90)
COL_GROUP_EDGE = (160, 160, 160)
COL_BOX_BG = (255, 255, 255)

FONT_FAMILY = "Microsoft YaHei UI"

_font_cache: dict[tuple[str, int, bool], ImageFont.FreeTypeFont] = {}
_image_cache: dict[tuple[str, float, tuple[int, int] | None], Image.Image | None] = {}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (FONT_FAMILY, size, bold)
    if key in _font_cache:
        return _font_cache[key]

    candidates = ([r"C:\Windows\Fonts\msyhbd.ttc"] if bold else []) + [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]
    font = None
    for path in candidates:
        if not Path(path).is_file():
            continue
        try:
            font = ImageFont.truetype(path, size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def _open_scaled(path: Path, size: tuple[int, int] | None):
    """读一张图并缩放到指定尺寸（按需裁切，不拉伸变形）。"""
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return None
    key = (str(path), stamp, size)
    if key in _image_cache:
        return _image_cache[key]

    image = None
    try:
        with Image.open(path) as raw:
            image = raw.convert("RGBA")
        if size is not None:
            image = _cover(image, size)
    except Exception:  # noqa: BLE001 - 图片坏了不该让预览崩掉
        image = None
    _image_cache[key] = image
    return image


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """按「铺满」缩放：保持比例，超出部分居中裁掉。"""
    target_w, target_h = size
    scale = max(target_w / image.width, target_h / image.height)
    new = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(new, Image.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _asset(project: Project, relative: str | None, size=None):
    if not relative:
        return None
    try:
        return _open_scaled(project.resolve("preview", relative), size)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# 文本
# ---------------------------------------------------------------------------

def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    """按像素宽度折行。中文逐字断，英文尽量在空格处断。"""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.rstrip("\r")
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            if not current or draw.textlength(current + char, font=font) <= width:
                current += char
                continue
            if char.isascii() and char.isalnum() and " " in current:
                head, _, tail = current.rpartition(" ")
                if head:
                    lines.append(head)
                    current = tail + char
                    continue
            lines.append(current)
            current = char
        lines.append(current)
    return lines


def _draw_text(draw, text, x, y, width, font, fill=COL_TEXT, spacing=3) -> int:
    """画一段自动换行的文字，返回底部 y。"""
    line_h = font.size + spacing
    for index, line in enumerate(_wrap(draw, text, font, width)):
        draw.text((x, y + index * line_h), line, font=font, fill=fill)
    return y + len(_wrap(draw, text, font, width)) * line_h


def _text_height(draw, text, width, font, spacing=3) -> int:
    return len(_wrap(draw, text, font, width)) * (font.size + spacing)


# ---------------------------------------------------------------------------
# 页面清单
# ---------------------------------------------------------------------------

PAGE_TITLES = {
    "welcome": "欢迎页",
    "license": "许可协议",
    "changelog": "更新日志",
    "directory": "安装位置",
    "options": "安装选项",
    "instfiles": "安装过程",
    "finish": "完成页",
}


def available_pages(project: Project) -> list[str]:
    """按当前配置列出安装包里**实际会出现**的页面。"""
    interface = project.interface
    pages: list[str] = []
    if interface.welcome.enabled:
        pages.append("welcome")
    if interface.license.enabled and _has_content(project, interface.license):
        pages.append("license")
    if interface.changelog.enabled and _has_content(project, interface.changelog):
        pages.append("changelog")
    if project.install.allow_change_dir:
        pages.append("directory")
    if interface.options_page.enabled and (
            project.shortcuts.desktop.enabled or project.shortcuts.start_menu.enabled):
        pages.append("options")
    pages.append("instfiles")
    pages.append("finish")
    return pages


def _has_content(project: Project, page) -> bool:
    if getattr(page, "source", "text") == "file":
        return bool(page.file) and (project.base_dir / page.file).is_file()
    return bool(page.body())


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

@dataclass
class PreviewContext:
    project: Project
    table: dict[str, str]
    expand: object            # 展开占位符的函数
    sample_dir: str           # 用来演示的安装路径（把 $XXXX 换成人看得懂的样子）


def _preview_mode(project: Project) -> str:
    """预览按哪个模式画。

    跟随第 6 步「要生成哪些版本」里勾选的第一个——这样预览和最终生成的安装包
    永远一致；没勾选任何版本时才退回工程里的默认值。
    """
    for mode in project.build.modes:
        if mode in MODE_LABELS:
            return mode
    return project.install.mode


def _sample_dir(project: Project) -> str:
    mode = _preview_mode(project)
    base = (project.install.default_dir or "").strip() or (
        r"$LOCALAPPDATA\Programs" if mode == "perUser" else r"$PROGRAMFILES64")
    user = "you" if is_english() else "你"
    return (base.replace("$PROGRAMFILES64", r"C:\Program Files")
                .replace("$PROGRAMFILES", r"C:\Program Files (x86)")
                .replace("$LOCALAPPDATA", rf"C:\Users\{user}\AppData\Local")
                .replace("$APPDATA", rf"C:\Users\{user}\AppData\Roaming"))


def _context(project: Project) -> PreviewContext:
    mode = _preview_mode(project)
    table = dict(placeholder_table(project, mode))
    table["installMode"] = _(MODE_LABELS.get(mode, ""))
    sample = _sample_dir(project)

    def expand(text: str) -> str:
        out = expand_placeholders(text or "", table, "preview")
        return (out.replace("$INSTDIR", sample + "\\" + project.app.dir_name)
                   .replace("${APP_NAME}", project.app.name))

    return PreviewContext(project=project, table=table, expand=expand, sample_dir=sample)


def render(project: Project, page_key: str, window_title: str = "") -> Image.Image:
    """渲染指定页面，返回 503×362 的整窗图。"""
    canvas = Image.new("RGB", (WINDOW_W, WINDOW_H), COL_CLIENT)
    draw = ImageDraw.Draw(canvas)
    ctx = _context(project)

    # 标题栏
    draw.rectangle([0, 0, WINDOW_W - 1, TITLE_H + BORDER], fill=COL_TITLEBAR)
    icon = _asset(project, project.app.icon, (16, 16))
    if icon is not None:
        canvas.paste(icon, (CLIENT_X + 6, (TITLE_H - 16) // 2 + 1), icon)
        text_x = CLIENT_X + 28
    else:
        text_x = CLIENT_X + 8
    title = window_title or _("{name} 安装").format(name=project.app.name)
    draw.text((text_x, (TITLE_H - 12) // 2 + 1), title,
              font=_font(12), fill=COL_TITLEBAR_TEXT)
    _draw_caption_buttons(draw)

    # 客户区底色
    draw.rectangle([CLIENT_X, CLIENT_Y, CLIENT_X + CLIENT_W - 1, CLIENT_Y + CLIENT_H - 1],
                   fill=COL_CLIENT)

    painters = {
        "welcome": _paint_welcome,
        "license": _paint_license,
        "changelog": _paint_changelog,
        "directory": _paint_directory,
        "options": _paint_options,
        "instfiles": _paint_instfiles,
        "finish": _paint_finish,
    }
    painter = painters.get(page_key, _paint_welcome)
    painter(canvas, draw, ctx)

    return canvas


def _draw_caption_buttons(draw) -> None:
    """右上角三个假的窗口按钮，纯装饰。"""
    y = TITLE_H // 2
    for index, glyph in enumerate(("\u2500", "\u25a1", "\u2715")):
        x = WINDOW_W - 24 - index * 26
        draw.text((x, y - 6), glyph, font=_font(10), fill=COL_CAPTION)


def _client_box(x0, y0, x1, y1):
    return [CLIENT_X + x0, CLIENT_Y + y0, CLIENT_X + x1, CLIENT_Y + y1]


def _put(image: Image.Image, canvas: Image.Image, x: int, y: int,
         clip: tuple[int, int] | None = None) -> None:
    """把图片贴到客户区坐标 (x, y)，可指定最大显示尺寸。"""
    if clip is not None and (image.width > clip[0] or image.height > clip[1]):
        image = image.crop((0, 0, min(clip[0], image.width), min(clip[1], image.height)))
    canvas.paste(image, (CLIENT_X + x, CLIENT_Y + y), image)


def _header(canvas: Image.Image, draw, project: Project, title: str, subtitle: str) -> None:
    """内页统一的页头：左上位图 + 标题 + 副标题 + 分隔线。"""
    bitmap = _asset(project, project.interface.header_image, (HEADER_W, HEADER_H))
    if bitmap is not None:
        _put(bitmap, canvas, 0, 0)
    else:
        draw.rectangle(_client_box(0, 0, HEADER_W - 1, HEADER_H - 1), fill=(240, 242, 246))

    draw.text((CLIENT_X + 166, CLIENT_Y + 10), title, font=_font(15, bold=True), fill=COL_TEXT)
    draw.text((CLIENT_X + 168, CLIENT_Y + 33), subtitle, font=_font(11), fill=COL_TEXT_DIM)
    draw.line(_client_box(0, HEADER_H, CLIENT_W - 1, HEADER_H), fill=COL_SEPARATOR)


def _footer(canvas: Image.Image, draw, project: Project, buttons: list[str],
            branding: str, primary: str | None = None) -> None:
    """底部分隔线 + 右下角按钮 + 左下角状态栏文字。"""
    draw.line(_client_box(0, SEPARATOR_Y, CLIENT_W - 1, SEPARATOR_Y), fill=COL_SEPARATOR)
    draw.rectangle(_client_box(0, SEPARATOR_Y + 1, CLIENT_W - 1, CLIENT_H - 1), fill=COL_BOTTOM)

    x = CLIENT_W - EDGE - BUTTON_W
    for label in reversed(buttons):
        _button(draw, x, CLIENT_H - 5 - BUTTON_H, label, primary=(label == primary))
        x -= BUTTON_W + BUTTON_GAP

    if branding:
        draw.text((CLIENT_X + EDGE, CLIENT_Y + CLIENT_H - 20), branding,
                  font=_font(11), fill=COL_TEXT_DIM)


def _button(draw, x: int, y: int, label: str, primary: bool = False) -> None:
    label = label.replace("&", "")          # NSIS 的快捷键标记在界面上不显示
    box = _client_box(x, y, x + BUTTON_W - 1, y + BUTTON_H - 1)
    draw.rectangle(box, fill=COL_BUTTON_FACE, outline=COL_BUTTON_EDGE)
    if primary:
        draw.rectangle([box[0] + 1, box[1] + 1, box[2] - 1, box[3] - 1],
                       outline=(0, 120, 212))
    font = _font(12)
    width = draw.textlength(label, font=font)
    draw.text((CLIENT_X + x + (BUTTON_W - width) / 2,
               CLIENT_Y + y + (BUTTON_H - font.size) / 2 - 1),
              label, font=font, fill=COL_TEXT)


def _sunken_box(draw, x0: int, y0: int, x1: int, y1: int) -> None:
    """一个内凹的白框，用来表示文本框/列表。"""
    draw.rectangle(_client_box(x0, y0, x1, y1), fill=COL_BOX_BG,
                   outline=(160, 160, 160))


def _checkbox(draw, x: int, y: int, checked: bool, label: str) -> None:
    label = label.replace("&", "")
    box = _client_box(x, y, x + 13, y + 13)
    draw.rectangle(box, fill=(255, 255, 255), outline=(120, 120, 120))
    if checked:
        draw.line([box[0] + 3, box[1] + 6, box[0] + 5, box[1] + 9], fill=(0, 90, 180), width=2)
        draw.line([box[0] + 5, box[1] + 9, box[0] + 10, box[1] + 2], fill=(0, 90, 180), width=2)
    draw.text((CLIENT_X + x + 19, CLIENT_Y + y), label, font=_font(12), fill=COL_TEXT)


# ---------------------------------------------------------------------------
# 各页面
# ---------------------------------------------------------------------------

def _paint_welcome(canvas, draw, ctx: PreviewContext) -> None:
    project = ctx.project
    welcome = project.interface.welcome

    banner = _asset(project, welcome.image, (BANNER_W, SEPARATOR_Y))
    if banner is not None:
        _put(banner, canvas, 0, 0, clip=(BANNER_W, SEPARATOR_Y))
    else:
        _gradient_banner(canvas, draw, project)

    y = _draw_text(draw, ctx.expand(welcome.title), CLIENT_X + TEXT_X, CLIENT_Y + 12,
                   CLIENT_W - TEXT_X - 24, _font(17, bold=True), spacing=6)
    _draw_text(draw, ctx.expand(welcome.text), CLIENT_X + TEXT_X + 2, y + 12,
               CLIENT_W - TEXT_X - 30, _font(12), spacing=5)

    _footer(canvas, draw, project, [_("上一步"), _("下一步"), _("取消")],
            ctx.expand(project.interface.branding_text), primary=_("下一步"))


def _gradient_banner(canvas, draw, project: Project) -> None:
    """没选位图时，画一条和 MUI 默认相近的蓝色渐变。"""
    box = [CLIENT_X, CLIENT_Y, CLIENT_X + BANNER_W - 1, CLIENT_Y + SEPARATOR_Y - 1]
    for offset in range(SEPARATOR_Y):
        t = offset / max(1, SEPARATOR_Y - 1)
        color = (int(79 + 20 * t), int(140 - 80 * t), int(245 - 90 * t))
        draw.line([box[0], box[1] + offset, box[2], box[1] + offset], fill=color)
    draw.line([box[0], box[1], box[0], box[3]], fill=(60, 60, 60))


def _paint_license(canvas, draw, ctx: PreviewContext) -> None:
    project = ctx.project
    page = project.interface.license
    _header(canvas, draw, project, _("许可证协议"),
            _("在安装 {name} 之前，请阅读许可证条款。").format(name=project.app.name))

    y = _draw_text(draw, ctx.expand(page.text_top), CLIENT_X + EDGE, CLIENT_Y + 66,
                   CLIENT_W - EDGE * 2, _font(12), spacing=5)

    box_top = max(y - CLIENT_Y + 6, 86)
    box_bottom = 232
    _sunken_box(draw, EDGE, box_top, CLIENT_W - EDGE - 1, box_bottom)

    # 正文要裁到框内，不能溢出去压到下面的提示和复选框
    font = _font(11)
    line_h = font.size + 3
    inner_w = CLIENT_W - EDGE * 2 - 20
    max_lines = max(1, (box_bottom - box_top - 12) // line_h)
    lines = _wrap(draw, _page_body(project, page), font, inner_w)[:max_lines]
    for index, line in enumerate(lines):
        draw.text((CLIENT_X + EDGE + 6, CLIENT_Y + box_top + 6 + index * line_h),
                  line, font=font, fill=COL_TEXT)

    hint = ctx.expand(page.text_bottom) or _("要阅读协议的其余部分，请按 [PgDn] 键向下翻页。")
    _draw_text(draw, hint, CLIENT_X + EDGE, CLIENT_Y + box_bottom + 8,
               CLIENT_W - EDGE * 2, _font(12), spacing=5)

    accept = ctx.expand(page.accept_text) if page.require_accept else _("我接受许可协议中的条款")
    _checkbox(draw, EDGE, 254, not page.require_accept, accept)

    _footer(canvas, draw, project, [_("上一步"), _("下一步"), _("取消")],
            ctx.expand(project.interface.branding_text), primary=_("下一步"))


def _paint_changelog(canvas, draw, ctx: PreviewContext) -> None:
    project = ctx.project
    page = project.interface.changelog
    _header(canvas, draw, project, ctx.expand(page.title), ctx.expand(page.subtitle))

    top = HEADER_H + 16
    bottom = SEPARATOR_Y - 38
    _sunken_box(draw, EDGE, top, CLIENT_W - EDGE - 1, bottom)

    body = _page_body(project, page)
    font = _font(11)
    line_h = font.size + 3
    max_lines = max(1, (bottom - top - 12) // line_h)
    lines = _wrap(draw, body, font, CLIENT_W - EDGE * 2 - 20)[:max_lines]
    for index, line in enumerate(lines):
        draw.text((CLIENT_X + EDGE + 6, CLIENT_Y + top + 6 + index * line_h),
                  line, font=font, fill=COL_TEXT)

    if len(_wrap(draw, body, font, CLIENT_W - EDGE * 2 - 20)) > max_lines:
        draw.text((CLIENT_X + CLIENT_W - EDGE - 40, CLIENT_Y + bottom - 18), "▼",
                  font=_font(10), fill=COL_TEXT_DIM)

    _footer(canvas, draw, project, [_("上一步"), _("下一步"), _("取消")],
            ctx.expand(project.interface.branding_text), primary=_("下一步"))


def _paint_directory(canvas, draw, ctx: PreviewContext) -> None:
    project = ctx.project
    page = project.interface.directory_page
    _header(canvas, draw, project, _("选择安装位置"),
            _("选择 {name} 的安装文件夹。").format(name=project.app.name))

    y = _draw_text(draw, ctx.expand(page.text_top), CLIENT_X + EDGE, CLIENT_Y + 66,
                   CLIENT_W - EDGE * 2, _font(12), spacing=5)

    label_y = max(y + 18, 146)
    draw.text((CLIENT_X + EDGE, CLIENT_Y + label_y), ctx.expand(page.text_destination),
              font=_font(12), fill=COL_TEXT)
    edit_y = label_y + 18
    draw.rectangle(_client_box(EDGE, edit_y, CLIENT_W - EDGE - 96, edit_y + 21),
                   fill=(255, 255, 255), outline=(120, 120, 120))
    draw.text((CLIENT_X + EDGE + 4, CLIENT_Y + edit_y + 4),
              f"{ctx.sample_dir}\\{project.app.dir_name}", font=_font(11), fill=COL_TEXT)
    _button(draw, CLIENT_W - EDGE - 90, edit_y, _("浏览(&B)..."))

    info_y = edit_y + 34
    draw.text((CLIENT_X + EDGE, CLIENT_Y + info_y), _("所需空间: 34.0 KB"),
              font=_font(12), fill=COL_TEXT)
    draw.text((CLIENT_X + EDGE, CLIENT_Y + info_y + 20), _("可用空间: 26.9 GB"),
              font=_font(12), fill=COL_TEXT)

    _footer(canvas, draw, project, [_("上一步"), _("下一步"), _("取消")],
            ctx.expand(project.interface.branding_text), primary=_("下一步"))


def _paint_options(canvas, draw, ctx: PreviewContext) -> None:
    project = ctx.project
    page = project.interface.options_page
    _header(canvas, draw, project, ctx.expand(page.title), ctx.expand(page.subtitle))

    top, bottom = HEADER_H + 10, SEPARATOR_Y - 14
    draw.rectangle(_client_box(EDGE, top, CLIENT_W - EDGE - 1, bottom),
                   outline=COL_GROUP_EDGE)
    draw.rectangle(_client_box(EDGE + 8, top - 7, EDGE + 8 + 84, top + 7),
                   fill=COL_CLIENT)
    draw.text((CLIENT_X + EDGE + 12, CLIENT_Y + top - 7), ctx.expand(page.group_text),
              font=_font(12), fill=COL_TEXT)

    y = top + 14
    if page.intro:
        y = _draw_text(draw, ctx.expand(page.intro), CLIENT_X + EDGE + 12, CLIENT_Y + y,
                       CLIENT_W - EDGE * 2 - 30, _font(12), spacing=5)

    y = max(y + 10, top + 42)
    shortcuts = project.shortcuts
    if shortcuts.desktop.enabled:
        _checkbox(draw, EDGE + 12, y, shortcuts.desktop.default,
                  _("在桌面创建 {name} 的快捷方式(&D)").format(
                      name=ctx.expand(shortcuts.desktop.name)))
        y += 20
    if shortcuts.start_menu.enabled:
        _checkbox(draw, EDGE + 12, y, shortcuts.start_menu.default,
                  _("在开始菜单创建 {name} 的快捷方式(&S)").format(
                      name=ctx.expand(shortcuts.start_menu.name)))
        y += 20
    if page.hint:
        _draw_text(draw, ctx.expand(page.hint), CLIENT_X + EDGE + 12, CLIENT_Y + y + 6,
                   CLIENT_W - EDGE * 2 - 30, _font(11), fill=COL_TEXT_DIM, spacing=4)

    _footer(canvas, draw, project, [_("上一步"), _("安装"), _("取消")],
            ctx.expand(project.interface.branding_text), primary=_("安装"))


def _paint_instfiles(canvas, draw, ctx: PreviewContext) -> None:
    project = ctx.project
    _header(canvas, draw, project, _("正在安装"),
            _("正在安装 {name}，请稍候。").format(name=project.app.name))

    top, bottom = HEADER_H + 9, SEPARATOR_Y - 10
    _sunken_box(draw, EDGE, top, CLIENT_W - EDGE - 1, bottom)
    font = _font(11)
    line_h = font.size + 3
    fake = [_("输出文件夹: {dir}").format(dir=project.app.dir_name),
            _("文件: {exe}").format(exe=project.app.main_exe or "MyApp.exe"),
            _("创建快捷方式: 桌面"),
            _("创建快捷方式: 开始菜单")]
    for index, line in enumerate(fake):
        draw.text((CLIENT_X + EDGE + 6, CLIENT_Y + top + 6 + index * line_h),
                  line, font=font, fill=COL_TEXT)

    # 进度条
    bar_y = bottom + 6
    draw.rectangle(_client_box(EDGE, bar_y, CLIENT_W - EDGE - 1, bar_y + 14),
                   fill=(255, 255, 255), outline=(120, 120, 120))
    filled = int((CLIENT_W - EDGE * 2 - 4) * 0.62)
    draw.rectangle(_client_box(EDGE + 2, bar_y + 2, EDGE + 2 + filled, bar_y + 12),
                   fill=(6, 176, 37))

    _footer(canvas, draw, project, [_("取消")],
            ctx.expand(project.interface.branding_text))


def _paint_finish(canvas, draw, ctx: PreviewContext) -> None:
    project = ctx.project
    page = project.interface.finish

    banner = _asset(project, project.interface.welcome.image, (BANNER_W, SEPARATOR_Y))
    if banner is not None:
        _put(banner, canvas, 0, 0, clip=(BANNER_W, SEPARATOR_Y))
    else:
        _gradient_banner(canvas, draw, project)

    y = _draw_text(draw, ctx.expand(page.title), CLIENT_X + TEXT_X, CLIENT_Y + 12,
                   CLIENT_W - TEXT_X - 24, _font(17, bold=True), spacing=6)
    y = _draw_text(draw, ctx.expand(page.text), CLIENT_X + TEXT_X + 2, y + 12,
                   CLIENT_W - TEXT_X - 30, _font(12), spacing=5)

    if page.run_app:
        _checkbox(draw, TEXT_X + 2, max(y + 14, 140), True, ctx.expand(page.run_text))

    if page.link.enabled and page.link.text:
        link_y = SEPARATOR_Y - 34
        draw.text((CLIENT_X + TEXT_X + 2, CLIENT_Y + link_y), ctx.expand(page.link.text),
                  font=_font(12), fill=(0, 102, 204))
        width = draw.textlength(ctx.expand(page.link.text), font=_font(12))
        draw.line([CLIENT_X + TEXT_X + 2, CLIENT_Y + link_y + 15,
                   CLIENT_X + TEXT_X + 2 + width, CLIENT_Y + link_y + 15],
                  fill=(0, 102, 204))

    _footer(canvas, draw, project, [_("上一步"), _("完成"), _("取消")],
            ctx.expand(project.interface.branding_text), primary=_("完成"))


def _page_body(project: Project, page) -> str:
    """取页面正文：内嵌文字直接用，文件来源就现场读（读不到给个提示）。"""
    if getattr(page, "source", "text") == "file":
        if not page.file:
            return _("（还没有选择文件）")
        path = project.base_dir / page.file
        if not path.is_file():
            return _("（找不到文件：{file}）").format(file=page.file)
        try:
            from ..engine.assets import read_text_auto
            return read_text_auto(path)
        except Exception:  # noqa: BLE001
            return _("（这个文件读不出来）")
    return page.body() or _("（正文是空的）")


# ---------------------------------------------------------------------------
# 界面上的预览面板
# ---------------------------------------------------------------------------

# 第 4 步的子标签 -> 预览哪一页
SUBTAB_TO_PAGE = {
    "欢迎页": "welcome",
    "许可协议": "license",
    "更新日志": "changelog",
    "安装位置页": "directory",
    "安装选项页": "options",
    "完成页": "finish",
}


class PreviewPanel(ttk.Frame):
    """左侧栏里的实时预览。"""

    def __init__(self, master, app) -> None:
        super().__init__(master, padding=(10, 6, 10, 12))
        self.app = app
        self._photo = None
        self._page = "welcome"
        self._pages: list[str] = []
        self._build()

    def _build(self) -> None:
        from .widgets import APP_FONT, TITLE_FONT

        # 字号和左边的「打包步骤」保持一致，两个区块看起来才是一套
        ttk.Label(self, text=_("安装效果预览"), foreground=theme.c("accent"),
                  font=TITLE_FONT).pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(self)
        row.pack(fill="x", pady=(0, 8))
        self.page_var = tk.StringVar()
        self.page_box = ttk.Combobox(row, textvariable=self.page_var, state="readonly",
                                     width=12, values=[])
        self.page_box.pack(side="left")
        self.page_box.bind("<<ComboboxSelected>>", self._on_page_selected)
        ttk.Label(row, text=_("   跟着编辑内容实时变"), foreground=theme.c("hint"),
                  font=APP_FONT).pack(side="left")

        self.screen = tk.Label(self, background=theme.c("screen"), borderwidth=1, relief="solid")
        self.screen.pack()

        ttk.Label(self, foreground=theme.c("hint"), justify="left",
                  font=("Microsoft YaHei UI", 8),
                  text=_("按真实版式绘制的示意图，用来确认文案和图片效果；\n"
                         "字体和换行位置可能和最终安装程序差一两行。")
                  ).pack(anchor="w", pady=(8, 0))

    # -- 数据 ---------------------------------------------------------------

    def follow(self, step: int, subtab: str = "") -> bool:
        """跟随编辑器的当前位置切换预览页面。

        返回是否真的换了页；**不在这里刷新**，由调用方统一刷（免得画两遍）。
        """
        key = None
        if step == 3:
            key = SUBTAB_TO_PAGE.get(subtab)
        elif step == 4:
            key = "options"
        elif step == 5:
            key = "finish"
        if key and key != self._page:
            self._page = key
            return True
        return False

    def _on_page_selected(self, _event=None) -> None:
        labels = [_(PAGE_TITLES[k]) for k in self._pages]
        chosen = self.page_var.get()
        if chosen in labels:
            self._page = self._pages[labels.index(chosen)]
            self.refresh()

    def refresh(self) -> None:
        from PIL import ImageTk

        project = self.app.project
        if project is None:
            self.screen.configure(image="", text=_("（还没有打开工程）"),
                                  foreground=theme.c("hint"))
            return

        pages = available_pages(project)
        if pages != self._pages:
            self._pages = pages
            self.page_box.configure(values=[_(PAGE_TITLES[k]) for k in pages])
        if self._page not in pages:
            self._page = pages[0] if pages else "welcome"
        self.page_var.set(_(PAGE_TITLES.get(self._page, "")))

        try:
            image = render(project, self._page)
        except Exception as exc:  # noqa: BLE001 - 预览出错不该影响编辑
            self.screen.configure(image="", text=_("预览画不出来：\n{exc}").format(exc=exc),
                                  foreground=theme.c("danger"))
            return

        self._photo = ImageTk.PhotoImage(image)
        self.screen.configure(image=self._photo, text="")
