"""编辑「打包内容」里某个条目的安装位置。

一个条目可能是文件，也可能是文件夹：

- 文件   —— 只改「安装到」目录；
- 文件夹 —— 还能选「保留文件夹名」：
    勾选 = 安装成 ``<安装到>\\<文件夹名>\\…``（保留文件夹本身与其子目录）；
    取消 = 只把文件夹里的内容放到 ``<安装到>`` 目录。

弹窗里给了实时的「安装后」预览，改字 / 点勾选都能立刻看到结果。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..i18n import t as _
from . import theme
from .widgets import APP_FONT

BOLD = ("Microsoft YaHei UI", 10, "bold")
HEADER_FONT = ("Microsoft YaHei UI", 13, "bold")


class ItemDestDialog(tk.Toplevel):
    """修改一个条目的「安装到」，文件夹还能选是否保留文件夹名。

    确定后 ``result`` 为 ``(安装到, 是否保留文件夹名)``；取消为 ``None``。
    """

    def __init__(self, master, *, dest: str, keep_folder: bool,
                 is_folder: bool, folder_name: str, source_label: str = "") -> None:
        super().__init__(master)
        self.result: tuple[str, bool] | None = None
        self._is_folder = is_folder
        self._folder_name = folder_name

        self.title(_("安装位置"))
        self.resizable(False, False)
        self.configure(background=theme.c("panel"))
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

        if master is not None and master.winfo_viewable():
            self.transient(master)

        self._build(dest, keep_folder, source_label)
        self.update_idletasks()
        self._center(master)
        self.deiconify()
        self.lift()
        self.update()
        self.grab_set()
        self.entry.focus_set()
        self.entry.selection_range(0, "end")

    # -- 界面 ---------------------------------------------------------------

    def _build(self, dest: str, keep_folder: bool, source_label: str) -> None:
        header = tk.Frame(self, background=theme.c("accent"))
        header.pack(fill="x")
        tk.Label(header, text=_("安装位置"), background=theme.c("accent"),
                 foreground="white", font=HEADER_FONT
                 ).pack(anchor="w", padx=22, pady=(13, 2))
        if source_label:
            tk.Label(header, text=source_label, background=theme.c("accent"),
                     foreground=theme.c("accent_soft"), font=APP_FONT,
                     justify="left", wraplength=470
                     ).pack(anchor="w", padx=22, pady=(0, 12))

        body = ttk.Frame(self, padding=(22, 16, 22, 0))
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=_("这个条目在安装目录里的位置："), font=BOLD).pack(anchor="w")
        self.dest_var = tk.StringVar(value=dest or ".")
        self.entry = ttk.Entry(body, textvariable=self.dest_var, width=48)
        self.entry.pack(fill="x", pady=(6, 4))
        ttk.Label(body, foreground=theme.c("hint"), font=APP_FONT, justify="left",
                  wraplength=470,
                  text=_("「.」表示安装目录根部，也可以写子目录，例如 docs 或 runtime\\bin。")
                  ).pack(anchor="w")

        self.keep_var = tk.BooleanVar(value=bool(keep_folder))
        if self._is_folder:
            keep = ttk.LabelFrame(body, text=" " + _("文件夹") + " ",
                                  padding=(12, 8, 12, 10))
            keep.pack(fill="x", pady=(14, 0))
            ttk.Checkbutton(keep, text=_("保留文件夹名"), variable=self.keep_var,
                            command=self._update_preview).pack(anchor="w")
            ttk.Label(keep, foreground=theme.c("hint"), font=APP_FONT, justify="left",
                      wraplength=470,
                      text=_("勾选后装成 安装目录\\{name}\\…；取消勾选则只把里面的内容"
                             "放到上面的目录里（不再多一层「{name}」）。").format(
                                 name=self._folder_name or _("文件夹"))
                      ).pack(anchor="w", pady=(3, 0))

        preview = ttk.LabelFrame(body, text=" " + _("安装后") + " ",
                                 padding=(12, 8, 12, 10))
        preview.pack(fill="x", pady=(14, 0))
        self.preview = ttk.Label(preview, foreground=theme.c("accent"), font=BOLD,
                                 justify="left", wraplength=470)
        self.preview.pack(anchor="w")

        footer = ttk.Frame(self, padding=(22, 14, 22, 16))
        footer.pack(fill="x")
        ttk.Button(footer, text=_("确定"), width=12, command=self._confirm).pack(side="right")
        ttk.Button(footer, text=_("取消"), width=10,
                   command=self._cancel).pack(side="right", padx=(0, 8))

        self.dest_var.trace_add("write", lambda *_: self._update_preview())
        self.keep_var.trace_add("write", lambda *_: self._update_preview())
        self._update_preview()

    # -- 预览与收尾 ---------------------------------------------------------

    def _effective(self) -> str:
        """按当前输入算出安装目录内的相对路径（不含 <安装目录> 前缀）。"""
        base = self.dest_var.get().strip()
        if base in ("", ".", "./", ".\\"):
            base = ""
        else:
            base = base.replace("\\", "/").strip("/")
        if self._is_folder and self.keep_var.get() and self._folder_name:
            base = f"{base}/{self._folder_name}" if base else self._folder_name
        return base

    def _update_preview(self) -> None:
        effective = self._effective()
        path = "<" + _("安装目录") + ">"
        if effective:
            path += "\\" + effective.replace("/", "\\")
        self.preview.configure(text=_("安装后：{path}").format(path=path))

    def _center(self, master) -> None:
        width = max(self.winfo_reqwidth(), 580)
        height = self.winfo_reqheight()
        if master is not None and master.winfo_viewable():
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = max(0, (self.winfo_screenheight() - height) // 2 - 60)
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def _confirm(self) -> None:
        self.result = (self.dest_var.get().strip() or ".", bool(self.keep_var.get()))
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
