"""「关于」窗口。

比系统弹框多一点东西：作者、**可点击的** GitHub 主页和邮箱链接、开源说明、
免责声明，以及开发时用到的 AI 辅助工具。链接点击后用系统默认浏览器 / 邮件
客户端打开。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import __version__
from . import resources, theme
from ..i18n import t as _, app_full_name
from .widgets import APP_FONT

BOLD = ("Microsoft YaHei UI", 11, "bold")
LINK_FONT = ("Microsoft YaHei UI", 9, "underline")

GITHUB_URL = "https://github.com/kllber"
EMAIL = "1394141383@qq.com"
LICENSE_URL = "https://github.com/kllber/jianpack/blob/main/LICENSE"


def _open_url(url: str) -> None:
    try:
        import webbrowser

        if webbrowser.open(url):
            return
    except Exception:  # noqa: BLE001
        pass
    try:
        import os

        os.startfile(url)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass


class AboutDialog(tk.Toplevel):
    def __init__(self, master) -> None:
        super().__init__(master)
        self.title(_("关于"))
        self.resizable(False, False)
        self.configure(background=theme.c("panel"))
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        if master is not None and master.winfo_viewable():
            self.transient(master)

        resources.apply_icon(self)
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
        tk.Label(header, text=app_full_name(), background=theme.c("accent"),
                 foreground="white", font=("Microsoft YaHei UI", 14, "bold")
                 ).pack(anchor="w", padx=22, pady=(14, 0))
        tk.Label(header, text=f"v{__version__}", background=theme.c("accent"),
                 foreground=theme.c("accent_soft"), font=APP_FONT
                 ).pack(anchor="w", padx=22, pady=(2, 12))

        body = tk.Frame(self, background=theme.c("panel"))
        body.pack(fill="both", expand=True, padx=24, pady=(16, 0))

        tk.Label(body, background=theme.c("panel"), foreground=theme.c("text"),
                 font=APP_FONT, justify="left", wraplength=430,
                 text=_("一个开源的应用安装包制作工具：把文件夹里的程序打成一个安装包，"
                        "对方双击就能装。底层使用 NSIS，生成的安装包零依赖。")
                 ).pack(anchor="w")

        self._row(body, _("作者："), "kllber")
        self._link_row(body, "GitHub：", GITHUB_URL, GITHUB_URL)
        self._link_row(body, _("邮箱："), EMAIL, "mailto:" + EMAIL)
        self._link_row(body, _("许可："), "Apache-2.0", LICENSE_URL)

        note = tk.Frame(body, background=theme.c("note_bg"),
                        highlightbackground=theme.c("note_border"), highlightthickness=1)
        note.pack(fill="x", pady=(14, 0))
        tk.Label(note, background=theme.c("note_bg"), foreground=theme.c("note_fg"),
                 font=APP_FONT, justify="left", wraplength=410,
                 text=_("本软件是开源工具，欢迎使用、分发和反馈问题。")
                      + "\n"
                      + _("开发过程中使用了 DeepSeek V4.1 Flash 进行辅助创作。")
                 ).pack(anchor="w", padx=12, pady=9)

        tk.Label(body, background=theme.c("panel"), foreground=theme.c("hint"),
                 font=("Microsoft YaHei UI", 8), justify="left", wraplength=430,
                 text=_("免责声明：本软件按「现状」提供，不附带任何明示或暗示的担保。"
                        "请确保你拥有所打包内容的合法权利，并遵守相关法律法规；"
                        "因使用本软件产生的任何直接或间接后果由使用者自行承担。")
                 ).pack(anchor="w", pady=(12, 0))

        footer = ttk.Frame(self, padding=(24, 16, 24, 16))
        footer.pack(fill="x")
        ttk.Button(footer, text=_("关闭"), width=10, command=self.destroy).pack(side="right")

    def _row(self, parent, label: str, value: str) -> None:
        row = tk.Frame(parent, background=theme.c("panel"))
        row.pack(anchor="w", fill="x", pady=(10, 0))
        tk.Label(row, text=label, background=theme.c("panel"), foreground=theme.c("text"),
                 font=APP_FONT).pack(side="left")
        tk.Label(row, text=value, background=theme.c("panel"), foreground=theme.c("text"),
                 font=APP_FONT).pack(side="left")

    def _link_row(self, parent, label: str, text: str, url: str) -> None:
        row = tk.Frame(parent, background=theme.c("panel"))
        row.pack(anchor="w", fill="x", pady=(6, 0))
        tk.Label(row, text=label, background=theme.c("panel"), foreground=theme.c("text"),
                 font=APP_FONT).pack(side="left")
        link = tk.Label(row, text=text, background=theme.c("panel"),
                        foreground=theme.c("accent"), font=LINK_FONT, cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda _e: _open_url(url))

    def _center(self, master) -> None:
        width = max(self.winfo_reqwidth(), 520)
        height = self.winfo_reqheight()
        if master is not None and master.winfo_viewable():
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = max(0, (self.winfo_screenheight() - height) // 2 - 60)
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
