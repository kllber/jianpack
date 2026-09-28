"""启动时的欢迎页。

每次打开软件弹一次，用一句话说清楚这软件是干嘛的，并告诉第一次用的人
教程在哪。底部可以「打开教程」，也可以勾选「不再显示这个欢迎页」。

它会持久化一个开关（``settings.show_welcome``），勾上关掉之后就不再出现。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..core.settings import Settings, save_settings
from ..core.errors import PackError
from . import theme
from .. import i18n
from ..i18n import t as _, app_full_name, app_name
from .widgets import APP_FONT

BOLD = ("Microsoft YaHei UI", 11, "bold")


class WelcomeDialog(tk.Toplevel):
    def __init__(self, master, settings: Settings) -> None:
        super().__init__(master)
        self.settings = settings
        self.open_tutorial = False          # 用户是不是点了「打开教程」
        self.switch_language: str | None = None   # 点了「中/en」时记下目标语言
        self._remember = tk.BooleanVar(value=False)

        self.title(app_name())
        self.resizable(False, False)
        self.configure(background=theme.c("panel"))
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _e: self._close())

        if master is not None and master.winfo_viewable():
            self.transient(master)

        self._build()
        self.update_idletasks()
        self._center(master)
        self.deiconify()
        self.lift()
        self.update()
        self.grab_set()
        self.focus_set()

    # -- 界面 ---------------------------------------------------------------

    def _build(self) -> None:
        header = tk.Frame(self, background=theme.c("accent"))
        header.pack(fill="x")
        tk.Label(header, text=_("欢迎使用") + " " + app_full_name(), background=theme.c("accent"),
                 foreground="white", font=("Microsoft YaHei UI", 14, "bold")
                 ).pack(anchor="w", padx=22, pady=(14, 12))

        body = ttk.Frame(self, padding=(24, 18, 24, 0))
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=_("把文件夹里的程序，一键打成中文安装包。"), font=BOLD,
                  wraplength=440, justify="left").pack(anchor="w")
        ttk.Label(body,
                  text=_("对方双击就能装，能选安装路径、建快捷方式，"
                         "还能在「程序和功能」里正常卸载。"),
                  foreground=theme.c("hint"), font=APP_FONT,
                  wraplength=478, justify="left").pack(anchor="w", pady=(6, 0), fill="x")

        tip = tk.Frame(body, background=theme.c("note_bg"),
                       highlightbackground=theme.c("note_border"), highlightthickness=1)
        tip.pack(fill="x", pady=(16, 0))
        tk.Label(tip,
                 text=_("第一次使用？点下面的「打开教程」看图文教程；"
                        "平时也可以从菜单「帮助 → 教程」（F1）打开。"),
                 background=theme.c("note_bg"), foreground=theme.c("note_fg"),
                 font=APP_FONT, wraplength=454, justify="left"
                 ).pack(anchor="w", padx=12, pady=10)

        ttk.Checkbutton(body, text=_("以后不再显示这个欢迎页"), variable=self._remember
                        ).pack(anchor="w", pady=(16, 0))

        footer = ttk.Frame(self, padding=(24, 16, 24, 16))
        footer.pack(fill="x")
        # 左下角：一键切换中英文（按钮文字固定为「中/en」）
        ttk.Button(footer, text="中/en", width=6,
                   command=self._toggle_language).pack(side="left")
        ttk.Button(footer, text=_("打开教程"), width=12,
                   command=self._tutorial).pack(side="right")
        ttk.Button(footer, text=_("知道了"), width=10,
                   command=self._close).pack(side="right", padx=(0, 8))

    def _center(self, master) -> None:
        width = max(self.winfo_reqwidth(), 540)
        height = self.winfo_reqheight()
        if master is not None and master.winfo_viewable():
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = max(0, (self.winfo_screenheight() - height) // 2 - 60)
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    # -- 动作 ---------------------------------------------------------------

    def _tutorial(self) -> None:
        self.open_tutorial = True
        self._close()

    def _toggle_language(self) -> None:
        """切到另一种语言：记下来，关掉欢迎页后由主窗口重建界面。"""
        self.switch_language = "en" if i18n.current() == "zh" else "zh"
        if self._remember.get():          # 顺手把「不再显示」也一并保存
            self.settings.show_welcome = False
            try:
                save_settings(self.settings)
            except PackError:
                pass
        self.destroy()

    def _close(self) -> None:
        if self._remember.get():
            self.settings.show_welcome = False
            try:
                save_settings(self.settings)
            except PackError:
                pass
        self.destroy()
