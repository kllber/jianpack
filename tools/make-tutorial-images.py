# -*- coding: utf-8 -*-
"""生成「使用教程」里的配图（开发用）。

做法：真的把设计器跑起来，走到对应的步骤，截真实界面，再用 Pillow 画上
红圈 / 编号，输出到 ``assets/tutorial/``。

为什么不用手绘图：教程里的图和真实界面对得上，用户才找得到地方；
界面改了，重跑一下这个脚本就能刷新配图。

用法：
    python tools\\make-tutorial-images.py            # 全部重新生成
    python tools\\make-tutorial-images.py t03 t10    # 只生成名字里带这些字的
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont, ImageGrab  # noqa: E402

from app.core.project import load_project  # noqa: E402
from app.engine.assets import TARGETS  # noqa: E402
from app.ui import preview as preview_mod  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402

DEMO = ROOT / "demo" / "feasibility" / "demo.jianpack"
OUT = ROOT / "assets" / "tutorial"       # 中文那套；英文写到 OUT/en/，由 main 设定
LANG = "zh"                              # "zh" | "en"
DEMO_PROJECT = DEMO                      # 抓图用的工程（英文模式换成英文样例）


def L(zh: str, en: str) -> str:
    """示意图里画的文字跟语言走。"""
    return en if LANG == "en" else zh

WIN_W, WIN_H = 1440, 1200            # 抓图时固定的窗口尺寸（和默认窗口一致）
GUTTER = 72                          # 内容截图的左侧留白，专门放编号，避免压住文字
RED = (224, 30, 30)
WHITE = (255, 255, 255)
PAGE_BG = (244, 246, 250)
MIN_CROP_H = 300
BADGE_R = 15


# ---------------------------------------------------------------------------
# 字体
# ---------------------------------------------------------------------------

def font(size: int, bold: bool = False):
    candidates = ([r"C:\Windows\Fonts\msyhbd.ttc"] if bold else []) + [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# 截图与标注
# ---------------------------------------------------------------------------

def rect_of(widget, win) -> tuple[int, int, int, int]:
    """控件在窗口坐标系里的外框。"""
    x = widget.winfo_rootx() - win.winfo_rootx()
    y = widget.winfo_rooty() - win.winfo_rooty()
    return (x, y, x + widget.winfo_width(), y + widget.winfo_height())


_SCREEN_SCALE = None


def screen_scale(win) -> float:
    """物理像素 / 逻辑像素 的比例（高 DPI 屏上不是 1）。

    Tk 的坐标是逻辑像素，而 ImageGrab 用的是物理像素 —— 不换算的话抓图会整体偏移。
    """
    global _SCREEN_SCALE
    if _SCREEN_SCALE is None:
        try:
            _SCREEN_SCALE = ImageGrab.grab().width / max(1, win.winfo_screenwidth())
        except Exception:  # noqa: BLE001
            _SCREEN_SCALE = 1.0
    return _SCREEN_SCALE


def grab(win, box: tuple[int, int, int, int] | None = None):
    """抓窗口的一块区域，返回 (图片, 这块区域在窗口里的左上角)。

    上层给的是**逻辑像素**（和 Tk 一致）；这里换算成物理像素去抓，再缩回逻辑尺寸，
    这样用 winfo_rootx() 得到的坐标去标注才不会有偏差。
    """
    win.update_idletasks()
    win.update()
    scale = screen_scale(win)
    origin_x = win.winfo_rootx() * scale
    origin_y = win.winfo_rooty() * scale
    if box is None:
        box = (0, 0, win.winfo_width(), win.winfo_height())
    x0, y0, x1, y1 = box
    image = ImageGrab.grab(bbox=(round(origin_x + x0 * scale), round(origin_y + y0 * scale),
                                 round(origin_x + x1 * scale), round(origin_y + y1 * scale)))
    if abs(scale - 1.0) > 0.01 and image.width:
        image = image.resize((max(1, round(image.width / scale)),
                              max(1, round(image.height / scale))), Image.LANCZOS)
    return image, (x0, y0)


def union(*rects):
    """几个外框的并集（用来把挨着的按钮一起圈起来）。"""
    return (min(r[0] for r in rects), min(r[1] for r in rects),
            max(r[2] for r in rects), max(r[3] for r in rects))


def find(widget, text: str, exact: bool = True):
    """在控件树里按 ``text`` 找控件。"""
    for child in widget.winfo_children():
        try:
            value = child.cget("text")
        except Exception:  # noqa: BLE001 - 有些控件没有 text
            value = None
        if value is not None and (value == text if exact else text in str(value)):
            return child
        got = find(child, text, exact)
        if got is not None:
            return got
    return None


class Frame:
    """在一张截图上画标注。坐标一律用「窗口坐标」，内部自动换算成图片坐标。"""

    def __init__(self, image: Image.Image, origin: tuple[int, int], gutter: int = 0) -> None:
        self.gutter = gutter
        if gutter:
            padded = Image.new("RGB", (image.width + gutter, image.height), PAGE_BG)
            padded.paste(image, (gutter, 0))
            image = padded
            origin = (origin[0] - gutter, origin[1])
        self.image = image
        self.origin = origin
        self.draw = ImageDraw.Draw(image, "RGBA")

    def w(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.origin[0], y - self.origin[1])

    def ring(self, rect, number: int | None = None,
             badge_at: tuple[float, float] | None = None, pad: int = 10) -> None:
        x0, y0 = self.w(rect[0], rect[1])
        x1, y1 = self.w(rect[2], rect[3])
        box = (int(x0 - pad), int(y0 - pad), int(x1 + pad), int(y1 + pad))
        self.draw.rounded_rectangle(box, radius=14, outline=WHITE, width=7)
        self.draw.rounded_rectangle(box, radius=14, outline=RED, width=4)
        if number is None:
            return
        if badge_at is not None:
            center = self.w(*badge_at)
        elif self.gutter:
            center = (self.gutter // 2, (box[1] + box[3]) / 2)
            self.draw.line([center, (box[0], center[1])], fill=RED, width=4)
        else:
            center = (box[0], box[1])
        self._badge(center[0], center[1], number)

    def arrow(self, start, end) -> None:
        a = self.w(*start)
        b = self.w(*end)
        for color, width in ((WHITE, 9), (RED, 5)):
            self.draw.line([a, b], fill=color, width=width)
        self._arrow_head(b, a)

    def _arrow_head(self, tip, tail) -> None:
        import math
        angle = math.atan2(tip[1] - tail[1], tip[0] - tail[0])
        size = 17
        for color, scale in ((WHITE, 1.35), (RED, 1.0)):
            left = (tip[0] - size * scale * math.cos(angle - 0.5),
                    tip[1] - size * scale * math.sin(angle - 0.5))
            right = (tip[0] - size * scale * math.cos(angle + 0.5),
                     tip[1] - size * scale * math.sin(angle + 0.5))
            self.draw.polygon([tip, left, right], fill=color)

    def pill(self, text: str, at) -> None:
        """在窗口坐标 ``at``（左上角）画一个红底白字的说明牌。"""
        fnt = font(17, bold=True)
        x, y = self.w(*at)
        left, top, right, bottom = self.draw.textbbox((0, 0), text, font=fnt)
        width, height = right - left + 26, bottom - top + 16
        x = max(6, min(x, self.image.width - width - 6))
        y = max(6, min(y, self.image.height - height - 6))
        box = (x, y, x + width, y + height)
        self.draw.rounded_rectangle(box, radius=height // 2, fill=WHITE)
        self.draw.rounded_rectangle(box, radius=height // 2, fill=RED)
        self.draw.text((x + 13 - left, y + 8 - top), text, font=fnt, fill=WHITE)

    def _badge(self, x: float, y: float, number: int) -> None:
        r = BADGE_R
        self.draw.ellipse([x - r, y - r, x + r, y + r], fill=WHITE)
        self.draw.ellipse([x - r + 3, y - r + 3, x + r - 3, y + r - 3], fill=RED)
        fnt = font(16, bold=True)
        text = str(number)
        left, top, right, bottom = self.draw.textbbox((0, 0), text, font=fnt)
        self.draw.text((x - (right - left) / 2 - left, y - (bottom - top) / 2 - top),
                       text, font=fnt, fill=WHITE)

    def save(self, name: str) -> Path:
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        self.image.save(path)
        print(f"  -> {name}  {self.image.size}")
        return path


# ---------------------------------------------------------------------------
# 截图辅助
# ---------------------------------------------------------------------------

def pump(win, seconds: float = 0.35) -> None:
    end = time.time() + seconds
    while time.time() < end:
        win.update()
        time.sleep(0.02)


def scroll_to(win, page, widget) -> None:
    """把页面滚动到 widget 附近（保证它在可视区域里，截图/定位才准）。"""
    if widget is None:
        return
    inner = page.body.inner
    win.update_idletasks()
    view_h = page.body.canvas.winfo_height()
    inner_h = max(1, inner.winfo_height())
    if inner_h <= view_h:
        return
    y = widget.winfo_rooty() - inner.winfo_rooty()
    page.body.canvas.yview_moveto(max(0.0, min(1.0, (y - 16) / inner_h)))
    win.update()


def content_image(win, page):
    """抓「编辑区」，内容下方留一点空白即可，不要拖一条长长的空白。

    先整窗抓一张、再按「窗口内坐标」裁剪 —— 这样即使窗口刚定位、winfo_rootx
    暂时不准，也不会把左栏错抓进来（两个坐标同源，误差相互抵消）。
    """
    win.update_idletasks()
    win.update()
    full, _origin = grab(win)
    area = rect_of(win.content_area, win)
    section_bottom = area[1]
    for child in page.form.winfo_children():
        if child.winfo_ismapped():
            section_bottom = max(section_bottom, child.winfo_rooty() - win.winfo_rooty()
                                 + child.winfo_height())
    bottom = min(area[3], max(area[1] + MIN_CROP_H, section_bottom + 72))
    box = (max(0, area[0]), max(0, area[1]),
           min(full.width, area[2]), min(full.height, bottom))
    return full.crop(box), (box[0], box[1])


def make_sample_photo(path: Path) -> None:
    """造一张「随便什么格式的照片」，用来演示图片裁剪。"""
    width, height = 1600, 1000
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / height
        draw.line([0, y, width, y],
                  fill=(int(120 + 80 * t), int(180 + 40 * t), int(235 - 40 * t)))
    draw.ellipse([1180, 120, 1460, 400], fill=(255, 226, 140))
    draw.polygon([(0, 780), (360, 470), (700, 780)], fill=(96, 132, 110))
    draw.polygon([(420, 820), (820, 430), (1220, 820)], fill=(72, 106, 92))
    draw.polygon([(980, 820), (1300, 560), (1600, 820)], fill=(88, 122, 104))
    draw.rectangle([0, 780, width, height], fill=(58, 92, 84))
    draw.text((60, 60), "Sample Photo 1600x1000", font=font(40, bold=True),
              fill=(255, 255, 255))
    image.save(path)


# ---------------------------------------------------------------------------
# 各张配图
# ---------------------------------------------------------------------------

def shot_overview(win: MainWindow) -> None:
    """主界面总览：把五个板块圈出来，编号放在各自的**右上角**。

    各板块的标题都在左上角，编号放右上角才不会压住文字；同时避开相邻板块
    （预览圈的是渲染区、不含标题行）以免圆角框互相重叠。
    """
    win._select_step(0)
    pump(win)
    image, origin = grab(win)
    frame = Frame(image, origin)
    version = rect_of(win.version_panel, win)
    steps = rect_of(win.steps, win)
    screen = rect_of(win.preview_panel.screen, win)
    preview_panel = rect_of(win.preview_panel, win)
    build = rect_of(win.build_panel, win)
    status = rect_of(win.status, win)

    # 编号统一放右上角（title 在左，右侧空着）
    frame.ring(version, 1, badge_at=(version[2] - 6, version[1] + 16), pad=6)
    frame.ring(steps, 2, badge_at=(steps[2] - 6, steps[1] + 16), pad=6)
    # 预览圈「渲染区」，编号放到预览面板标题行的右上角，远离下拉框、也不压图
    frame.ring(screen, 3, badge_at=(preview_panel[2] - 6, preview_panel[1] + 16), pad=6)
    frame.ring(build, 4, badge_at=(build[2] - 6, build[1] + 16), pad=6)
    # 状态栏很矮，编号放在右端、垂直居中
    frame.ring(status, 5, badge_at=(status[2] - 30, (status[1] + status[3]) // 2), pad=3)
    frame.save("t01-overview.png")


def shot_start(win: MainWindow) -> None:
    from app.ui.start_dialog import StartDialog

    dialog = StartDialog(win, win.settings)
    pump(dialog, 0.5)
    image, origin = grab(dialog)
    frame = Frame(image, origin)
    new_btn = rect_of(find(dialog, L("新建工程", "New Project")), dialog)
    open_btn = rect_of(find(dialog, L("打开已有工程…", "Open Project…")), dialog)
    holder_widget = dialog.tree if dialog.tree.winfo_ismapped() else dialog.empty_hint
    holder = rect_of(holder_widget, dialog)
    frame.ring(new_btn, 1, badge_at=(new_btn[0] - 2, new_btn[1]))
    frame.ring(open_btn, 2, badge_at=(open_btn[0] - 2, open_btn[1]))
    frame.ring(holder, 3, badge_at=(holder[0] - 2, holder[1]))
    frame.save("t02-start.png")
    dialog.destroy()
    pump(win, 0.2)


def shot_basic(win: MainWindow) -> None:
    page = win._pages[0]
    win._select_step(0)
    pump(win)
    image, origin = content_image(win, page)
    frame = Frame(image, origin, gutter=GUTTER)
    names = (L("应用名称 *", "App name *"), L("安装目录名", "Install folder name"),
             L("程序文件版本", "File version"), L("程序图标", "App icon"))
    for number, name in enumerate(names, 1):
        frame.ring(rect_of(find(page, name).master, win), number)
    frame.save("t03-basic.png")


def shot_files(win: MainWindow) -> None:
    page = win._pages[1]
    win._select_step(1)
    pump(win)
    image, origin = content_image(win, page)
    frame = Frame(image, origin, gutter=GUTTER)
    add = union(rect_of(find(page, L("添加文件…", "Add Files…")), win),
                rect_of(find(page, L("添加文件夹…", "Add Folder…")), win))
    frame.ring(add, 1)
    frame.ring(rect_of(page.tree, win), 2)
    frame.ring(rect_of(find(page, L("主程序", "Main program"), exact=False), win), 3)
    frame.save("t04-files.png")


def shot_install(win: MainWindow) -> None:
    page = win._pages[2]
    win._select_step(2)
    pump(win)
    image, origin = content_image(win, page)
    frame = Frame(image, origin, gutter=GUTTER)
    # ① 使用默认路径 + 自定义路径（安装模式已经不在这里了）
    default_path = find(page, L("使用默认路径（按安装模式自动选择）",
                                "Use the default path (chosen by install mode)"))
    custom = find(page, L("自定义路径", "Custom path")).master
    frame.ring(union(rect_of(default_path, win), rect_of(custom, win)), 1)
    # ② 允许用户修改安装位置
    frame.ring(rect_of(find(page, L("允许用户在安装时修改安装位置",
                                    "Let the user change the install location")), win), 2)
    # ③ 用户数据与卸载
    section = find(page, L("用户数据与卸载", "User Data & Uninstall"), exact=False)
    frame.ring(rect_of(section, win), 3)
    frame.save("t05-install.png")


def shot_interface(win: MainWindow) -> None:
    page = win._pages[3]
    win._select_step(3)
    pump(win)
    notebook = page._notebook
    notebook.select(0)
    pump(win, 0.3)
    image, origin = content_image(win, page)
    frame = Frame(image, origin, gutter=GUTTER)
    x0, y0, x1, _y1 = rect_of(notebook, win)
    frame.ring((x0, y0, x1, y0 + 28), 1)
    frame.ring(rect_of(find(page, L("标题", "Title")).master, win), 2)
    frame.ring(rect_of(find(page, L("左侧图片", "Left image")).master, win), 3)
    frame.save("t06-interface.png")


def shot_crop(win: MainWindow) -> None:
    from app.ui.image_crop_dialog import ImageCropDialog

    sample = OUT / "_sample-photo.png"
    make_sample_photo(sample)
    dialog = ImageCropDialog(win, sample, TARGETS["header"])
    pump(dialog, 0.5)

    def rel(widget) -> tuple[int, int, int, int]:
        return rect_of(widget, dialog)

    canvas = rel(dialog.canvas)
    frame_box = (canvas[0] + dialog.frame_x, canvas[1] + dialog.frame_y,
                 canvas[0] + dialog.frame_x + dialog.frame_w,
                 canvas[1] + dialog.frame_y + dialog.frame_h)

    image, origin = grab(dialog)
    frame = Frame(image, origin)
    frame.ring(frame_box, 1, badge_at=(frame_box[0] + 4, frame_box[1] + 4))
    frame.ring(rel(dialog.preview), 2, badge_at=(rel(dialog.preview)[0] + 6,
                                                 rel(dialog.preview)[1] + 6))
    frame.ring(rel(dialog.scale), 3, badge_at=(rel(dialog.scale)[0] - 4,
                                               rel(dialog.scale)[1] - 30))
    confirm = find(dialog, L("确定", "OK"))
    frame.ring(rect_of(confirm, dialog), 4,
               badge_at=(confirm.winfo_rootx() - dialog.winfo_rootx(),
                         confirm.winfo_rooty() - dialog.winfo_rooty()))
    frame.arrow((rel(dialog.preview)[0] - 6, rel(dialog.preview)[1] + 60),
                (frame_box[2] + 6, frame_box[3] - 24))
    frame.save("t07-crop.png")

    dialog.destroy()
    sample.unlink(missing_ok=True)
    pump(win, 0.2)


def shot_shortcuts(win: MainWindow) -> None:
    """快捷方式现在在「第 4 步 → 安装选项页」里。"""
    page = win._pages[3]
    win._select_step(3)
    notebook = getattr(page, "_notebook", None)
    keys = list(getattr(page, "_tab_keys", []))
    if notebook is not None and "安装选项页" in keys:
        notebook.select(keys.index("安装选项页"))
    pump(win, 0.4)
    target = find(page, L("启用桌面快捷方式", "Enable the desktop shortcut"))
    scroll_to(win, page, target)
    pump(win, 0.3)
    image, origin = content_image(win, page)
    frame = Frame(image, origin, gutter=GUTTER)
    frame.ring(rect_of(find(page, L("启用桌面快捷方式", "Enable the desktop shortcut")), win), 1)
    frame.ring(rect_of(find(page, L("允许用户在安装时修改",
                                    "Let the user change it during setup")), win), 2)
    frame.ring(rect_of(find(page, L("启用开始菜单快捷方式",
                                    "Enable the Start menu shortcut")), win), 3)
    frame.save("t08-shortcuts.png")


def shot_build(win: MainWindow) -> None:
    """「开始打包」现在常驻左栏（不再是一个独立的步骤页）。"""
    panel = win.build_panel
    win._select_step(0)
    pump(win)
    image, origin = grab(win)
    frame = Frame(image, origin, gutter=GUTTER)
    frame.ring(union(rect_of(panel.check_button, win),
                     rect_of(panel.gen_button, win),
                     rect_of(panel.build_button, win)), 1)
    frame.ring(rect_of(panel.log, win), 2)
    frame.save("t09-build.png")


def shot_preview(win: MainWindow) -> None:
    page = win._pages[3]
    win._select_step(3)
    pump(win)
    page._notebook.select(1)          # 许可协议
    pump(win, 0.4)
    win._update_preview()
    pump(win, 0.3)

    def rel(widget) -> tuple[int, int, int, int]:
        return rect_of(widget, win)

    image, origin = grab(win)
    frame = Frame(image, origin)
    screen = rel(win.preview_panel.screen)
    page_box = rel(win.preview_panel.page_box)
    # ① 紧挨着下拉框（放它左边），一眼看出标的是下拉框
    frame.ring(page_box, 1, badge_at=(page_box[0] - 12, (page_box[1] + page_box[3]) // 2),
               pad=2)
    # ② 放到预览框的左下角，离下拉框远一点，避免又挤在一起
    frame.ring(screen, 2, badge_at=(screen[0] + 6, screen[3] - 6), pad=2)
    license = rel(find(page, L("协议正文", "License text")))
    frame.ring(license, 3, badge_at=(license[2] - 24, license[1] - 4))
    frame.arrow((license[0] - 36, license[3] - 12), (screen[2] + 8, screen[1] + 120))
    frame.save("t10-preview.png")


def shot_welcome(win: MainWindow) -> None:
    from app.ui.welcome_dialog import WelcomeDialog

    dialog = WelcomeDialog(win, win.settings)
    pump(dialog, 0.5)
    image, origin = grab(dialog)
    frame = Frame(image, origin)
    tutorial = rect_of(find(dialog, L("打开教程", "Open Tutorial")), dialog)
    remember = rect_of(find(dialog, L("以后不再显示这个欢迎页",
                                      "Don't show this welcome page again")), dialog)
    lang = rect_of(find(dialog, "中/en"), dialog)
    frame.ring(tutorial, 1, badge_at=(tutorial[0] - 2, tutorial[1]))
    frame.ring(remember, 2, badge_at=(remember[0] - 2, remember[1]))
    frame.ring(lang, 3, badge_at=(lang[0] - 2, lang[1]))
    frame.save("t14-welcome.png")
    dialog.destroy()
    pump(win, 0.2)


def shot_preferences(win: MainWindow) -> None:
    import sys as _sys

    from app.core import assoc as _assoc
    from app.ui.preferences_dialog import PreferencesDialog

    # 让「文件关联」那一栏显示成用户看到的样子（而不是「源码运行」的开发提示）
    old_frozen = getattr(_sys, "frozen", None)
    old_status = _assoc.status
    _sys.frozen = True
    _assoc.status = lambda: "ok"
    try:
        dialog = PreferencesDialog(win, win.settings)
    finally:
        _assoc.status = old_status
        if old_frozen is None:
            try:
                del _sys.frozen
            except AttributeError:
                pass
        else:
            _sys.frozen = old_frozen
    pump(dialog, 0.5)
    # 设置窗口默认高度只到「文件关联」，后续分区要靠滚动看。教程要把所有分区
    # 都拍进一张图，这里临时把滚动区撑到全部内容的高度（窗口本身可缩放）。
    scroll = getattr(dialog, "body_scroll", None)
    if scroll is not None:
        scroll.inner.update_idletasks()
        scroll.canvas.configure(height=scroll.inner.winfo_reqheight() + 4)
        dialog.update_idletasks()
        dialog._center(dialog.master)
        pump(dialog, 0.4)
    image, origin = grab(dialog)
    frame = Frame(image, origin)
    sections = (
        L("界面语言", "Language"),
        L("界面主题", "Theme"),
        L("使用习惯", "Habits"),
        L("文件关联", "File Association"),
        L("缓存 / 临时目录", "Cache / Temp Folder"),
        L("初始化", "Reset"),
    )
    for number, title in enumerate(sections, start=1):
        widget = find(dialog, title, exact=False)
        if widget is None:
            continue
        box = rect_of(widget, dialog)
        frame.ring(box, number, badge_at=(box[2] - 34, box[1] + 2))
    frame.save("t15-preferences.png")
    dialog.destroy()
    pump(win, 0.2)


def frame_rect(win) -> tuple[int, int]:
    """窗口边框（含标题栏和菜单栏）左上角的屏幕坐标。

    Tk 的 ``winfo_rooty`` 指向的是**客户区**顶部，菜单栏在它上面；
    要截到「帮助」那条菜单，必须从窗口边框开始截。
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32")
    hwnd = int(win.tk.call("wm", "frame", win._w), 16)
    rect = wintypes.RECT()
    user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    return rect.left, rect.top


def _menu_item_rect(win, index: int):
    """某个菜单项的屏幕矩形（Windows 原生菜单，含标题栏坐标）。

    ``index`` 是**原生菜单项序号**：Tk 的 menubar 在索引 0 放了一个不可见的
    tearoff 项，Windows 原生菜单里没有它，换算时要跳过去。
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32")
    hwnd = int(win.tk.call("wm", "frame", win._w), 16)
    hmenu = user32.GetMenu(wintypes.HWND(hwnd))
    if not hmenu:
        return None
    rect = wintypes.RECT()
    if not user32.GetMenuItemRect(wintypes.HWND(hwnd), hmenu, index, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def shot_menu(win: MainWindow) -> None:
    """截「标题栏 + 菜单栏」，圈出「帮助」菜单。"""
    win._select_step(0)
    pump(win)

    menubar = win.nametowidget(win.cget("menu"))
    count = menubar.index("end") + 1
    labels: list[str] = []
    for i in range(count):
        try:
            labels.append(menubar.entrycget(i, "label"))
        except Exception:  # noqa: BLE001 - 分隔符之类的没有 label
            labels.append("")
    help_index = labels.index(L("帮助", "Help"))
    # Tk 索引 -> 原生菜单索引：跳过那个不可见的 tearoff 项
    native_index = 0
    for i in range(help_index):
        try:
            if menubar.type(i) != "tearoff":
                native_index += 1
        except Exception:  # noqa: BLE001
            native_index += 1

    _, top = frame_rect(win)
    left = win.winfo_rootx()                       # 从客户区左边开始，横向坐标好算
    width, height = 660, 300
    image = ImageGrab.grab(bbox=(left, top, left + width, top + height))
    frame = Frame(image, (0, 0))
    client_top = win.winfo_rooty() - top           # 客户区在图片里的 y

    rect = _menu_item_rect(win, native_index)
    if rect is not None:                           # 精确：直接用菜单项本人的矩形
        box = (rect[0] - left, rect[1] - top, rect[2] - left, rect[3] - top)
    else:                                          # 兜底：按菜单字体估算
        import tkinter.font as tkfont
        measure = tkfont.nametofont("TkMenuFont")
        x = 10
        for i in range(help_index):
            x += measure.measure(labels[i]) + 16
        box = (x - 10, max(0, client_top - 26), x + 44, client_top)

    frame.ring(box, 1, pad=2)
    frame.pill(L("帮助 → 教程（F1）", "Help → Tutorial (F1)"),
               (box[2] + 18, client_top + 4))
    frame.save("t11-menu.png")


def shot_installer() -> None:
    """把最终安装包的各个页面拼成一张总览图（不是截图，是渲染）。"""
    project = load_project(DEMO_PROJECT)
    keys = ["welcome", "license", "changelog", "directory", "options", "instfiles", "finish"]
    titles = {
        "welcome": L("欢迎页", "Welcome"), "license": L("许可协议", "License"),
        "changelog": L("更新日志", "Changelog"), "directory": L("安装位置", "Location"),
        "options": L("安装选项", "Options"), "instfiles": L("安装过程", "Installing"),
        "finish": L("完成页", "Finish"),
    }
    scale = 0.52
    pages = []
    for key in keys:
        rendered = preview_mod.render(project, key)
        pages.append((key, rendered.resize(
            (int(rendered.width * scale), int(rendered.height * scale)), Image.LANCZOS)))

    tw, th = pages[0][1].size
    cols, gap, pad, label_h, top = 4, 16, 24, 26, 64
    rows = (len(pages) + cols - 1) // cols
    width = pad * 2 + cols * tw + (cols - 1) * gap
    height = top + pad + rows * (label_h + th) + (rows - 1) * gap + pad
    canvas = Image.new("RGB", (width, height), PAGE_BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 20), "对方看到的安装向导（示意）", font=font(22, bold=True), fill=(26, 68, 190))
    for index, (key, page) in enumerate(pages):
        row, col = divmod(index, cols)
        px = pad + col * (tw + gap)
        py = top + row * (label_h + th + gap)
        draw.text((px + 2, py + 3), titles[key], font=font(15), fill=(60, 60, 70))
        canvas.paste(page, (px, py + label_h))
        draw.rectangle([px - 1, py + label_h - 1, px + tw, py + label_h + th],
                       outline=(205, 212, 224))
    canvas.save(OUT / "t12-installer.png")
    print(f"  -> t12-installer.png  {canvas.size}")


def shot_project() -> None:
    """画一张「一个工程 = 一个文件」的示意图（不是截图）。"""
    width, height = 1040, 470
    canvas = Image.new("RGB", (width, height), PAGE_BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((30, 22), L("一个工程 = 一个文件", "One project = one file"),
              font=font(22, bold=True), fill=(26, 68, 190))

    # 左边：文件卡片（贴工程文件的图标）
    draw.rounded_rectangle((40, 84, 540, 200), radius=12,
                           fill=(255, 255, 255), outline=(205, 212, 224))
    icon_path = ROOT / "assets" / "project.ico"
    if icon_path.is_file():
        try:
            with Image.open(icon_path) as raw:
                icon = raw.convert("RGBA").resize((80, 80), Image.LANCZOS)
            canvas.paste(icon, (68, 100), icon)
        except Exception:  # noqa: BLE001
            pass
    draw.text((176, 104), L("我的软件.jianpack", "MySoftware.jianpack"),
              font=font(23, bold=True), fill=(224, 30, 30))
    draw.text((176, 146), L("双击就能打开本软件", "Double-click to open this app"),
              font=font(14), fill=(90, 96, 106))

    # 左下：文件里装着什么
    draw.rounded_rectangle((40, 226, 540, 430), radius=12,
                           fill=(244, 247, 252), outline=(205, 212, 224))
    draw.text((64, 242), L("文件里装着：", "Inside the file:"),
              font=font(16, bold=True), fill=(37, 42, 51))
    rows = [
        ("project.json", L("工程配置", "project settings")),
        ("assets/", L("图标、欢迎页图片", "icon, welcome image")),
        ("payload/", L("要打包的文件", "files to package")),
        ("docs/", L("协议 / 日志（可选）", "license / changelog (optional)")),
    ]
    y = 282
    for name, desc in rows:
        draw.text((72, y), name, font=font(15, bold=True), fill=(26, 68, 190))
        draw.text((230, y + 1), desc, font=font(14), fill=(90, 96, 106))
        y += 34

    # 右侧：为什么方便
    draw.text((600, 104), L("发送、备份、搬移，", "Send, back up or move —"),
              font=font(19, bold=True), fill=(37, 42, 51))
    draw.text((600, 140), L("都只搬这一个文件。", "just this one file."),
              font=font(19, bold=True), fill=(37, 42, 51))
    draw.text((600, 210), L("中间产物（build 等）", "Intermediate files (build etc.)"),
              font=font(14), fill=(90, 96, 106))
    draw.text((600, 236), L("放在临时目录，不进文件。", "stay in a temp folder, not in the file."),
              font=font(14), fill=(90, 96, 106))
    draw.text((600, 300), L("工程文件有自己的图标，", "The project file has its own icon,"),
              font=font(14), fill=(90, 96, 106))
    draw.text((600, 326), L("和软件图标区分开。", "different from the app icon."),
              font=font(14), fill=(90, 96, 106))
    canvas.save(OUT / "t13-project.png")
    print(f"  -> t13-project.png  {canvas.size}")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

TASKS = {
    "t01": shot_overview,
    "t02": shot_start,
    "t03": shot_basic,
    "t04": shot_files,
    "t05": shot_install,
    "t06": shot_interface,
    "t07": shot_crop,
    "t08": shot_shortcuts,
    "t09": shot_build,
    "t10": shot_preview,
    "t11": shot_menu,
    "t14": shot_welcome,
    "t15": shot_preferences,
}


def _english_banners(assets: Path) -> None:
    """给英文样例换一套英文的欢迎页 / 页头位图（原来是中文的）。"""
    welcome = Image.new("RGB", (164, 314))
    draw = ImageDraw.Draw(welcome)
    for y in range(314):
        t = y / 313
        draw.line([0, y, 164, y],
                  fill=(int(70 + 25 * t), int(120 - 20 * t), int(230 - 40 * t)))
    draw.text((24, 120), "My Tool", font=font(20, bold=True), fill=WHITE)
    draw.text((24, 150), "Setup", font=font(15), fill=(216, 228, 255))
    draw.text((24, 276), "Example Software", font=font(11), fill=(210, 222, 250))
    welcome.save(assets / "welcome.bmp", format="BMP")

    header = Image.new("RGB", (150, 57))
    dh = ImageDraw.Draw(header)
    for x in range(150):
        t = x / 149
        dh.line([x, 0, x, 57],
                fill=(int(60 + 40 * t), int(110 + 40 * t), int(225 - 40 * t)))
    dh.text((12, 20), "My Tool", font=font(15, bold=True), fill=WHITE)
    header.save(assets / "header.bmp", format="BMP")


def _english_project() -> Path:
    """做一个英文样例工程，供英文版教程截图使用（样例数据也换成英文）。"""
    work = Path(tempfile.mkdtemp(prefix="aipack-tutorial-en-"))
    root = ROOT / "demo" / "feasibility"
    for sub in ("input", "assets", "src"):
        if (root / sub).is_dir():
            shutil.copytree(root / sub, work / sub)
    _english_banners(work / "assets")

    data = json.loads(DEMO.read_text(encoding="utf-8"))
    data["project"]["name"] = "My Tool"
    data["app"].update({
        "name": "My Tool",
        "publisher": "Example Software Studio",
        "copyright": "Copyright (C) 2026 Example Software Studio",
        "description": "App Installer Packer — demo project",
    })
    iface = data["interface"]
    iface["language"] = "en-US"
    iface["brandingText"] = "{appName} Setup v{appVersion}"
    iface["welcome"]["title"] = "Welcome to the {appName} Setup Wizard"
    iface["welcome"]["text"] = (
        "The Setup Wizard will install {appName} on your computer.\n\n"
        "It is recommended to close other running programs before continuing. "
        "After installation you can start the app from the desktop or Start menu.\n\n"
        "Mode: {installMode}\n\nClick Next to continue.")
    iface["license"].update({
        "source": "text",
        "text": ("SOFTWARE LICENSE AGREEMENT\n\n"
                 "This agreement is between you and Example Software Studio.\n\n"
                 "1. Scope\nThis license applies to the installer, the executable and the "
                 "related documentation.\n\n"
                 "2. Permitted use\nYou may use this software for personal or commercial "
                 "purposes.\n\n"
                 "3. No warranty\nThe software is provided \"as is\", without warranty of "
                 "any kind."),
        "file": None,
        "acceptText": "I accept the terms of the license agreement(&A)",
        "textTop": "Please read the following license agreement before using this software.",
        "textBottom": "Check \"I accept\" and click Next to continue.",
    })
    iface["changelog"].update({
        "source": "text",
        "text": ("Version 1.0.0  (2026-09-27)\n"
                 "------------------------------\n"
                 "[New]\n"
                 "- First public release.\n"
                 "- Installer with a custom install location.\n"
                 "- Desktop and Start menu shortcuts.\n"
                 "- Clean uninstall from Apps & features."),
        "file": None,
        "title": "Changelog",
        "subtitle": "See what changed in this version",
    })
    iface["directoryPage"].update({
        "textTop": "The Setup Wizard will install {appName} into the folder below.\n\n"
                   "To install elsewhere, click Browse and choose a folder.",
        "textDestination": "Install to:",
    })
    iface["optionsPage"].update({
        "title": "Install Options",
        "subtitle": "Choose the shortcuts to create",
        "groupText": "Additional tasks",
        "intro": "The Setup Wizard can create the shortcuts below for {appName}.",
        "hint": "Tip: you can uninstall the app from Apps & features regardless of shortcuts.",
    })
    iface["finish"].update({
        "title": "{appName} Setup Complete",
        "text": "{appName} has been installed on your computer.\n\n"
                "Install location: $INSTDIR\n\nClick Finish to close the wizard.",
        "runText": "Run {appName} now",
    })
    iface["finish"]["link"]["text"] = "Visit the website"
    data["uninstall"]["keepUserDataText"] = (
        "Also delete {appName}'s settings and user data?\n\n"
        "Choose No to keep them for a future reinstall.")

    path = work / "demo.jianpack"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    global LANG, OUT, DEMO_PROJECT
    args = list(sys.argv[1:])
    if "--lang" in args:
        i = args.index("--lang")
        LANG = "en" if i + 1 < len(args) and args[i + 1].lower() == "en" else "zh"
        del args[i:i + 2]
    wanted = [a.lower() for a in args]

    if LANG == "en":
        OUT = ROOT / "assets" / "tutorial" / "en"
    OUT.mkdir(parents=True, exist_ok=True)

    # 抓图固定用浅色主题 + 指定语言：把设置/数据目录引到临时目录，免得受开发机影响
    base = Path(tempfile.mkdtemp(prefix="aipack-tutorial-shots-"))
    os.environ["APPDATA"] = str(base)
    os.environ["AIPACK_HOME"] = str(base / "home")
    cfg = base / "home" / "data"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "settings.json").write_text(
        json.dumps({"theme": "light", "language": LANG, "showWelcome": False}),
        encoding="utf-8")

    DEMO_PROJECT = _english_project() if LANG == "en" else DEMO

    print(f"启动设计器（抓图用，语言={LANG}）…")
    win = MainWindow(str(DEMO_PROJECT))
    win.attributes("-topmost", True)
    win.geometry(f"{WIN_W}x{WIN_H}+20+20")
    win.update()
    time.sleep(0.6)
    win.update()
    # 打开工程现在是异步的，等它读完再开始抓图（否则 _pages 还是空的）
    end = time.time() + 30
    while time.time() < end and win.app.project is None:
        win.update()
        time.sleep(0.02)

    try:
        for key, task in TASKS.items():
            if wanted and not any(word in key for word in wanted):
                continue
            print(f"[{key}]")
            task(win)

        if not wanted or any(word in "t12" for word in wanted):
            print("[t12]")
            shot_installer()
        if not wanted or any(word in "t13" for word in wanted):
            print("[t13]")
            shot_project()
    finally:
        try:
            win.attributes("-topmost", False)
            win.destroy()
        except Exception:  # noqa: BLE001
            pass

    print("完成，输出目录:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
