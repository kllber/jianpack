"""打开工程时的「启动 / 加载」提示窗口。

两个版本共用同一套代码：

- ``with_icon=True``  —— 双击 ``.jianpack`` 或直接启动软件时用，带品牌图标；
- ``with_icon=False`` —— 已经在软件里、再去打开一个工程时用，只有一条小提示
  加一个进度条（按需求：**简化版不带图标**）。

窗口是无边框、置顶、不进任务栏的小面板：加载时把它显示出来，并让真正耗时的
解压/读取在后台线程里跑，主线程只负责刷新这里的进度，所以不会「静默卡住」。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import __version__
from ..i18n import app_full_name
from ..i18n import t as _
from . import resources, theme

NAME_FONT = ("Microsoft YaHei UI", 13, "bold")
STATUS_FONT = ("Microsoft YaHei UI", 10)
HINT_FONT = ("Microsoft YaHei UI", 9)
PAD_X = 22
FULL_WIDTH = 430
MINI_WIDTH = 370


class Splash(tk.Toplevel):
    """加载提示窗口。确定后由调用方在完成时 :meth:`close`。"""

    def __init__(self, master, *, with_icon: bool, status: str = "",
                 file_name: str = "", show: bool = True) -> None:
        super().__init__(master)
        self.withdraw()
        self._with_icon = with_icon
        self._icon_photo = None
        self._shown = False
        self._width = FULL_WIDTH if with_icon else MINI_WIDTH

        self.overrideredirect(True)                 # 无边框
        self.configure(background=theme.c("panel"), highlightthickness=1,
                       highlightbackground=theme.c("border"))
        self._set_topmost()

        self._build(status, file_name)
        self.update_idletasks()
        self._center()
        if show:
            self.show()

    # -- 显示 / 隐藏 --------------------------------------------------------

    def show(self) -> None:
        """真正显示出来。

        延迟显示时，读得快就不调用它；这样小工程打开时根本不会闪出一个窗口。
        """
        if self._shown:
            return
        self._shown = True
        self.deiconify()
        self.lift()
        self._set_topmost()

    @property
    def is_shown(self) -> bool:
        return self._shown

    # -- 界面 ---------------------------------------------------------------

    def _build(self, status: str, file_name: str) -> None:
        tk.Frame(self, background=theme.c("accent"), height=4).pack(fill="x")

        body = ttk.Frame(self, padding=(PAD_X, 16, PAD_X, 16))
        body.pack(fill="both", expand=True)

        if self._with_icon:
            self._build_head(body)

        self.status_label = ttk.Label(
            body, text=status or _("正在打开工程…"),
            font=STATUS_FONT, foreground=theme.c("text"))
        self.status_label.pack(anchor="w")

        self.bar = ttk.Progressbar(body, mode="determinate", maximum=100,
                                   length=self._width - PAD_X * 2 - 6)
        self.bar.pack(fill="x", pady=(9, 7))

        self.file_label = ttk.Label(body, text=file_name or "", font=HINT_FONT,
                                    foreground=theme.c("hint"))
        self.file_label.pack(anchor="w")

    def _build_head(self, parent) -> None:
        head = ttk.Frame(parent)
        head.pack(fill="x", pady=(0, 14))

        icon = self._load_icon(52)
        if icon is not None:
            tk.Label(head, image=icon, background=theme.c("panel")
                     ).pack(side="left", padx=(0, 14))

        text = ttk.Frame(head)
        text.pack(side="left", fill="x", expand=True)
        ttk.Label(text, text=app_full_name(), font=NAME_FONT,
                  foreground=theme.c("text")).pack(anchor="w")
        ttk.Label(text, text=f"v{__version__}", font=HINT_FONT,
                  foreground=theme.c("hint")).pack(anchor="w", pady=(2, 0))

    def _load_icon(self, size: int):
        path = resources.app_icon()
        if path is None:
            return None
        try:
            from PIL import Image, ImageTk

            with Image.open(path) as raw:
                image = raw.convert("RGBA")
            image.thumbnail((size, size), Image.LANCZOS)
            self._icon_photo = ImageTk.PhotoImage(image)   # 必须留引用
            return self._icon_photo
        except Exception:  # noqa: BLE001 - 图标取不到就用纯文字
            return None

    def _set_topmost(self) -> None:
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

    def _center(self) -> None:
        height = self.winfo_reqheight()
        x = (self.winfo_screenwidth() - self._width) // 2
        y = max(0, (self.winfo_screenheight() - height) // 2 - 40)
        self.geometry(f"{self._width}x{height}+{x}+{y}")

    # -- 进度 ---------------------------------------------------------------

    def set_status(self, text: str) -> None:
        try:
            self.status_label.configure(text=text)
        except tk.TclError:
            pass

    def set_file(self, text: str) -> None:
        try:
            self.file_label.configure(text=text or "")
        except tk.TclError:
            pass

    def set_indeterminate(self) -> None:
        """不知道总量时用的来回滚动条（例如「正在启动…」）。"""
        try:
            self.bar.configure(mode="indeterminate")
            self.bar.start(14)
        except tk.TclError:
            pass

    def set_progress(self, done: int, total: int, name: str = "") -> None:
        """已知总量时的真实进度（由后台线程把数字丢进队列，主线程调用这里）。"""
        try:
            if total > 0:
                if str(self.bar.cget("mode")) != "determinate":
                    self.bar.stop()
                    self.bar.configure(mode="determinate", maximum=100)
                self.bar["value"] = max(0.0, min(100.0, done * 100.0 / total))
            if name:
                self.file_label.configure(text=name)
        except tk.TclError:
            pass

    def close(self) -> None:
        # 先停掉进度条动画：否则销毁后它的 after 回调还会再触发，报
        # 「can't invoke winfo command: application has been destroyed」。
        try:
            self.bar.stop()
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass
