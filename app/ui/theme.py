"""界面主题：浅色 / 深色。

两个约定：

- **颜色不要写死在控件里**，一律用 :func:`c` 从当前主题取，这样深色模式下
  才不会留下白底黑字的「补丁」。
- 深色用 ttk 的 ``clam`` 主题重新配一整套颜色（系统自带的 ``vista`` 是原生
  绘制，改不动颜色）；浅色回到系统默认主题。

切换主题采用「重建主窗口」的方式（见 ``MainWindow._restart``）：每个新窗口
是新的 Tk 解释器，ttk 样式表也是全新的，所以不会出现两种主题混在一起的残留。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# 品牌蓝：浅色下深一点，深色下提亮，保证在各自背景上都看得清
LIGHT = {
    "window": "#f0f0f0",
    "panel": "#ffffff",
    "canvas": "#ffffff",
    "field": "#ffffff",
    "text": "#1a1a1a",
    "hint": "#8a8f99",
    "accent": "#1a44be",
    "accent_soft": "#d3dcff",
    "border": "#c8cedb",
    "button": "#f0f0f0",
    "button_hover": "#e3e6ea",
    "select_bg": "#1a44be",
    "select_fg": "#ffffff",
    "danger": "#c0392b",
    "thumb": "#e9edf4",
    "log": "#fbfcfe",
    "note_bg": "#eef3ff",
    "note_fg": "#274690",
    "note_border": "#c7d6ff",
    "code_bg": "#f4f5f7",
    "code_fg": "#2b2f36",
    "code_border": "#dcdfe6",
    "screen": "#d8dce4",
    "preview_bg": "#c8cedb",
    # 复选框自绘指示器（勾）用的颜色
    "check_bg": "#ffffff",
    "check_border": "#9aa3b2",
    "check_on_bg": "#1a44be",
    "check_on_mark": "#ffffff",
    "check_dis_bg": "#f0f0f0",
    "check_dis_border": "#ced2d9",
    "check_dis_mark": "#c2c6cd",
}

DARK = {
    "window": "#20242b",
    "panel": "#272c34",
    "canvas": "#20242b",
    "field": "#1b1f25",
    "text": "#e6e8ec",
    "hint": "#9aa3b2",
    "accent": "#7aa7ff",
    "accent_soft": "#b9ccff",
    "border": "#3a4048",
    "button": "#2f353e",
    "button_hover": "#3a424d",
    "select_bg": "#33518f",
    "select_fg": "#ffffff",
    "danger": "#ff6b6b",
    "thumb": "#2c313a",
    "log": "#161a1f",
    "note_bg": "#22304a",
    "note_fg": "#cfe0ff",
    "note_border": "#33507f",
    "code_bg": "#161a1f",
    "code_fg": "#d7dbe2",
    "code_border": "#3a4048",
    "screen": "#3a4048",
    "preview_bg": "#4a515c",
    "check_bg": "#1b1f25",
    "check_border": "#6b7280",
    "check_on_bg": "#7aa7ff",
    "check_on_mark": "#20242b",
    "check_dis_bg": "#1b1f25",
    "check_dis_border": "#3a4048",
    "check_dis_mark": "#565f6b",
}

PALETTE = {"light": LIGHT, "dark": DARK}

_mode = "light"
_native_theme: str | None = None


def mode() -> str:
    return _mode


def is_dark() -> bool:
    return _mode == "dark"


def c(role: str) -> str:
    """取当前主题下的颜色（``#rrggbb``）。"""
    return PALETTE[_mode][role]


def rgb(role: str) -> tuple[int, int, int]:
    value = c(role).lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _normalize(name: str | None) -> str:
    return "dark" if str(name).lower() == "dark" else "light"


def activate(root: tk.Misc, name: str | None) -> str:
    """按 ``name`` 给 ``root`` 所在窗口装上主题，返回实际生效的模式。"""
    global _mode, _native_theme
    try:
        style = ttk.Style(root)
    except tk.TclError:
        return _mode

    if _native_theme is None:
        try:
            _native_theme = style.theme_use()
        except tk.TclError:
            _native_theme = "vista"

    _mode = _normalize(name)
    try:
        style.theme_use("clam" if _mode == "dark" else _native_theme)
    except tk.TclError:
        pass

    if _mode == "dark":
        _configure_dark(style, DARK)
    _configure_combobox(root, PALETTE[_mode])
    _install_check_indicator(root, PALETTE[_mode])
    return _mode


# ---------------------------------------------------------------------------
# 复选框的「勾」自绘
#
# Tk 的 clam 主题把「已勾选」画成一个 ✗，不符合普通人的直觉（用户也希望是 ✓）。
# 这里自己画一套 ✓ 图标，替换掉主题的指示器绘制：和主题无关、深浅色都一致，
# 而且纯外观——勾选状态仍由 BooleanVar 决定，不影响任何逻辑。
# ---------------------------------------------------------------------------

_CHECK_SIZE = 16          # 指示器大小（像素）
_CHECK_ELEMENT = "JianPack.Checkbutton.indicator"
_CHECK_LAYOUT = [
    ("Checkbutton.padding", {"sticky": "nswe", "children": [
        (_CHECK_ELEMENT, {"side": "left", "sticky": ""}),
        ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
            ("Checkbutton.label", {"sticky": "nswe"})]}),
    ]}),
]


def _check_image(size: int, checked: bool, bg: str, border: str, mark: str):
    from PIL import Image, ImageDraw

    scale = 4                       # 先画大再缩小，边缘更平滑
    px = size * scale
    image = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = max(2, px // 5)
    draw.rounded_rectangle([1, 1, px - 2, px - 2], radius=radius, fill=bg,
                           outline=border, width=max(2, px // 12))
    if checked:
        width = max(3, int(px * 0.13))
        points = [(px * 0.22, px * 0.52), (px * 0.42, px * 0.72), (px * 0.79, px * 0.27)]
        draw.line(points, fill=mark, width=width, joint="curve")
        for x, y in (points[0], points[-1]):
            draw.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=mark)
    return image.resize((size, size), Image.LANCZOS)


def _install_check_indicator(root: tk.Misc, p: dict) -> None:
    """给当前窗口装一套自绘的 ✓ 复选框。同一个解释器只装一次。"""
    if getattr(root, "_jianpack_check_marker", False):
        return
    try:
        from tkinter import ttk
        from PIL import ImageTk

        style = ttk.Style(root)
        images = {
            "off": ImageTk.PhotoImage(_check_image(
                _CHECK_SIZE, False, p["check_bg"], p["check_border"], p["check_on_mark"])),
            "on": ImageTk.PhotoImage(_check_image(
                _CHECK_SIZE, True, p["check_on_bg"], p["check_on_bg"], p["check_on_mark"])),
            "off_d": ImageTk.PhotoImage(_check_image(
                _CHECK_SIZE, False, p["check_dis_bg"], p["check_dis_border"], p["check_dis_mark"])),
            "on_d": ImageTk.PhotoImage(_check_image(
                _CHECK_SIZE, True, p["check_dis_bg"], p["check_dis_border"], p["check_dis_mark"])),
        }
        style.element_create(
            _CHECK_ELEMENT, "image",
            images["off"],
            ("selected", images["on"]),
            ("disabled", images["off_d"]),
            ("disabled", "selected", images["on_d"]),
        )
        style.layout("TCheckbutton", _CHECK_LAYOUT)
        # 图片必须留引用，否则会被回收成空白
        root._jianpack_check_marker = images
    except Exception:  # noqa: BLE001 - 自绘失败就退回主题默认画法，不影响使用
        pass


def _configure_combobox(root: tk.Misc, p: dict) -> None:
    """下拉框弹出来的列表是原生的 Tk Listbox，只能通过 option 数据库改。"""
    try:
        root.option_add("*TCombobox*Listbox.background", p["field"])
        root.option_add("*TCombobox*Listbox.foreground", p["text"])
        root.option_add("*TCombobox*Listbox.selectBackground", p["select_bg"])
        root.option_add("*TCombobox*Listbox.selectForeground", p["select_fg"])
    except tk.TclError:
        pass


def _configure_dark(style: ttk.Style, p: dict) -> None:
    style.configure(".", background=p["window"], foreground=p["text"],
                    fieldbackground=p["field"],
                    selectbackground=p["select_bg"], selectforeground=p["select_fg"],
                    bordercolor=p["border"], lightcolor=p["button"],
                    darkcolor=p["border"], troughcolor=p["field"],
                    focuscolor=p["accent"], insertcolor=p["text"])

    style.configure("TFrame", background=p["window"])
    style.configure("TLabel", background=p["window"], foreground=p["text"])
    style.configure("TLabelframe", background=p["window"],
                    bordercolor=p["border"], relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=p["window"], foreground=p["text"])
    style.configure("TButton", background=p["button"], foreground=p["text"],
                    bordercolor=p["border"], focuscolor=p["accent"], padding=(10, 5))
    style.map("TButton",
              background=[("active", p["button_hover"]), ("pressed", p["button_hover"])],
              foreground=[("disabled", p["hint"])])
    style.configure("TEntry", fieldbackground=p["field"], foreground=p["text"],
                    insertcolor=p["text"], bordercolor=p["border"])
    style.configure("TCombobox", fieldbackground=p["field"], background=p["button"],
                    foreground=p["text"], arrowcolor=p["text"], bordercolor=p["border"])
    style.map("TCombobox",
              fieldbackground=[("readonly", p["field"])],
              foreground=[("readonly", p["text"])],
              background=[("readonly", p["button"])])
    style.configure("TCheckbutton", background=p["window"], foreground=p["text"],
                    indicatorcolor=p["field"])
    style.map("TCheckbutton", background=[("active", p["window"])],
              foreground=[("disabled", p["hint"])])
    style.configure("TRadiobutton", background=p["window"], foreground=p["text"],
                    indicatorcolor=p["field"])
    style.map("TRadiobutton", background=[("active", p["window"])],
              foreground=[("disabled", p["hint"])])
    style.configure("TNotebook", background=p["window"], bordercolor=p["border"],
                    tabmargins=(2, 4, 2, 0))
    style.configure("TNotebook.Tab", background=p["button"], foreground=p["text"],
                    padding=(12, 6), bordercolor=p["border"])
    style.map("TNotebook.Tab", background=[("selected", p["window"])],
              foreground=[("selected", p["accent"])])
    style.configure("Treeview", background=p["field"], fieldbackground=p["field"],
                    foreground=p["text"], bordercolor=p["border"])
    style.map("Treeview", background=[("selected", p["select_bg"])],
              foreground=[("selected", p["select_fg"])])
    style.configure("Treeview.Heading", background=p["button"], foreground=p["text"],
                    relief="flat")
    style.map("Treeview.Heading", background=[("active", p["button_hover"])])
    for name in ("TScrollbar", "Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(name, background=p["button"], troughcolor=p["window"],
                        bordercolor=p["border"], arrowcolor=p["text"], gripcount=0)
    style.configure("TSeparator", background=p["border"])
    style.configure("TScale", background=p["window"], troughcolor=p["field"],
                    bordercolor=p["border"])
    style.configure("TSpinbox", fieldbackground=p["field"], background=p["button"],
                    foreground=p["text"], arrowcolor=p["text"])
