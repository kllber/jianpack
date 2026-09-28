"""新建工程对话框。

用户选好名称和位置后，只产出一个 ``.aiproj`` 文件 ——
工程内容（图标、待打包文件、界面设置……）全都装在这一个文件里，
发送、备份、搬移都只搬这一个文件。
"""

from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..core.paths import desktop_dir
from ..core.settings import Settings
from . import theme
from .. import i18n
from ..i18n import t as _
from .widgets import APP_FONT

BOLD = ("Microsoft YaHei UI", 10, "bold")
ILLEGAL_NAME = re.compile(r'[\\/:*?"<>|]')


class NewProjectDialog(tk.Toplevel):
    def __init__(self, master, settings: Settings) -> None:
        super().__init__(master)
        self.settings = settings
        # (工程文件完整路径, 存放位置)，取消时为 None
        self.result: tuple[str, str] | None = None

        self.title(_("新建工程"))
        self.resizable(False, False)
        self.configure(background=theme.c("panel"))
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

        if master is not None and master.winfo_viewable():
            self.transient(master)

        self._build()
        self.update_idletasks()
        self._center()
        self.deiconify()
        self.lift()
        self.update()
        self.grab_set()

        self.name_entry.focus_set()
        self.name_entry.selection_range(0, "end")

    # -- 界面 ---------------------------------------------------------------

    def _build(self) -> None:
        header = tk.Frame(self, background=theme.c("accent"))
        header.pack(fill="x")
        tk.Label(header, text=_("新建工程"), background=theme.c("accent"), foreground="white",
                 font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", padx=22, pady=(14, 12))

        body = ttk.Frame(self, padding=(22, 16, 22, 0))
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=_("工程名称"), font=BOLD).pack(anchor="w")
        self.name_var = tk.StringVar(value=_("我的软件"))
        self.name_entry = ttk.Entry(body, textvariable=self.name_var, width=48)
        self.name_entry.pack(fill="x", pady=(4, 3))
        ttk.Label(body, foreground=theme.c("hint"), font=APP_FONT,
                  text=_("会在下面这个位置创建「名称.aiproj」这一个工程文件。")
                  ).pack(anchor="w")

        ttk.Label(body, text=_("存放位置"), font=BOLD).pack(anchor="w", pady=(16, 0))
        row = ttk.Frame(body)
        row.pack(fill="x", pady=(4, 0))
        self.dir_var = tk.StringVar(value=self._default_dir())
        ttk.Entry(row, textvariable=self.dir_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text=_("浏览…"), width=8,
                   command=self._browse).pack(side="left", padx=(6, 0))

        preview = ttk.LabelFrame(body, text=" " + _("将要创建") + " ", padding=(12, 8, 12, 10))
        preview.pack(fill="x", pady=(18, 0))
        self.preview_path = ttk.Label(preview, text="", font=BOLD,
                                      foreground=theme.c("accent"),
                                      wraplength=520, justify="left")
        self.preview_path.pack(anchor="w")
        self.preview_note = ttk.Label(preview, text="", foreground=theme.c("hint"),
                                      wraplength=520, justify="left", font=APP_FONT)
        self.preview_note.pack(anchor="w", pady=(5, 0))

        footer = ttk.Frame(self, padding=(22, 14, 22, 16))
        footer.pack(fill="x")
        ttk.Button(footer, text=_("创建"), width=12, command=self._create).pack(side="right")
        ttk.Button(footer, text=_("取消"), width=10,
                   command=self._cancel).pack(side="right", padx=(0, 8))

        self.name_var.trace_add("write", lambda *_: self._update_preview())
        self.dir_var.trace_add("write", lambda *_: self._update_preview())
        self._update_preview()

    def _center(self) -> None:
        width = max(self.winfo_reqwidth(), 600)
        height = max(self.winfo_reqheight(), 400)
        master = self.master
        if master is not None and master.winfo_viewable():
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = max(0, (self.winfo_screenheight() - height) // 2 - 60)
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def _default_dir(self) -> str:
        remembered = self.settings.new_project_dir
        if remembered and Path(remembered).is_dir():
            return remembered
        # 用统一的桌面解析，才能跟随 OneDrive 之类的桌面重定向
        return str(desktop_dir())

    # -- 预览与校验 ---------------------------------------------------------

    def _update_preview(self) -> None:
        name = self.name_var.get().strip()
        parent = self.dir_var.get().strip()
        problem = self._validate(name, parent)

        if problem:
            self.preview_path.configure(text=_("（把上面两项填好）"),
                                        foreground=theme.c("hint"))
            self.preview_note.configure(text=problem)
            return

        project_file = Path(parent).expanduser() / f"{name}.aiproj"
        self.preview_path.configure(text=str(project_file), foreground=theme.c("accent"))
        self.preview_note.configure(
            text=_("图标、待打包的文件、界面设置等都会装在这一个文件里，"
                   "发送、备份、搬移都只搬它。"))

    @staticmethod
    def _validate(name: str, parent: str) -> str:
        if not name:
            return _("请填写工程名称。")
        if name in (".", ".."):
            return _("工程名称不合法。")
        if ILLEGAL_NAME.search(name):
            return _('工程名称不能包含 \\ / : * ? " < > | 这些字符。')
        if name != name.rstrip(" ."):
            return _("工程名称不能以空格或句点结尾。")
        if not parent:
            return _("请填写存放位置。")
        return ""

    # -- 动作 ---------------------------------------------------------------

    def _browse(self) -> None:
        current = self.dir_var.get().strip()
        chosen = filedialog.askdirectory(
            parent=self, title=_("选择存放位置"),
            initialdir=current if Path(current).is_dir() else None)
        if chosen:
            self.dir_var.set(chosen)

    def _create(self) -> None:
        name = self.name_var.get().strip()
        parent = self.dir_var.get().strip()
        problem = self._validate(name, parent)
        if problem:
            messagebox.showwarning(_("还差一点"), problem, parent=self)
            return

        parent_path = Path(parent).expanduser()
        project_file = parent_path / f"{name}.aiproj"

        if project_file.exists():
            messagebox.showerror(
                _("这个位置已经有同名工程了"),
                _("{project_file}\n\n换个名字，或者换个存放位置。").format(
                    project_file=project_file),
                parent=self)
            return

        # 真正的写盘交给 MainWindow.new_project -> AppState.save（打成 .aiproj 容器）
        self.result = (str(project_file), str(parent_path))
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
