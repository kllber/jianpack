"""界面用到的小组件。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme
from ..i18n import t as _

APP_FONT = ("Microsoft YaHei UI", 9)
TITLE_FONT = ("Microsoft YaHei UI", 14, "bold")
SUBTITLE_FONT = ("Microsoft YaHei UI", 9)
# 这两个是给「不跟主题变」的地方兜底用的；会跟主题变的颜色请用 theme.c(...)
HINT_FG = "#8a8f99"
ACCENT = "#1a44be"


class ScrollFrame(ttk.Frame):
    """带垂直滚动条的容器；内容放在 ``.inner`` 里。"""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0,
                                background=theme.c("canvas"))
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)

        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.vbar.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._sync_scrollregion)
        self.canvas.bind("<Configure>", self._fit_width)
        self.canvas.bind("<Enter>", lambda _e: self._bind_wheel(True))
        self.canvas.bind("<Leave>", lambda _e: self._bind_wheel(False))

    def _sync_scrollregion(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _fit_width(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self, active: bool) -> None:
        if active:
            self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        else:
            self.canvas.unbind_all("<MouseWheel>")

    def sync_scrollregion(self) -> None:
        self._sync_scrollregion()

    def _on_wheel(self, event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


def hint_label(parent, text: str, **pack) -> ttk.Label:
    label = ttk.Label(parent, text=_(text), foreground=theme.c("hint"), font=SUBTITLE_FONT,
                      wraplength=620, justify="left")
    label.pack(anchor="w", **pack)
    return label


def section(parent, title: str, **pack) -> ttk.LabelFrame:
    frame = ttk.LabelFrame(parent, text=" " + _(title) + " ", padding=(12, 8, 12, 10))
    frame.pack(fill="x", pady=(6, 10), **pack)
    return frame


def separator(parent, **pack) -> ttk.Separator:
    line = ttk.Separator(parent, orient="horizontal")
    line.pack(fill="x", pady=8, **pack)
    return line


def keep_wheel_inside(widget) -> None:
    """滚轮只滚这个控件自己，不把外层可滚动页面一起带着滚。

    页面的滚动是绑在 ``bind_all`` 上的，所以这里要 ``return "break"``
    把事件截断，否则鼠标放在列表上滚滚轮会连页面一起动。
    """
    def on_wheel(event):
        widget.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    widget.bind("<MouseWheel>", on_wheel)
