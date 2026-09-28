"""启动窗口：让用户自己选「新建工程」还是「打开已有工程」。

以前是启动就直接弹「新建工程」的保存对话框，等于没给选择。
现在先出这个窗口，用户不选就不进主界面。

窗口关闭 / 点退出 -> :attr:`StartDialog.result` 为 ``None``，主窗口应当直接结束。
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import __version__
from ..core import demo
from ..core.settings import Settings, save_settings
from . import theme
from ..i18n import t as _, app_full_name, app_name
from .widgets import APP_FONT


def file_types() -> list[tuple[str, str]]:
    return [(_("安装打包工程"), "*.aiproj"), (_("所有文件"), "*.*")]

BOLD = ("Microsoft YaHei UI", 10, "bold")


class StartDialog(tk.Toplevel):
    def __init__(self, master, settings: Settings, modal: bool = True) -> None:
        super().__init__(master)
        self.settings = settings
        # modal=False 时不抢输入：从欢迎页点「打开教程」进来时，
        # 要能一边开着教程一边在启动窗口里选工程。
        self._modal = modal

        # None      -> 用户取消 / 退出
        # ("new", _)      -> 新建工程
        # ("open", path)  -> 打开指定工程
        self.result: tuple[str, str | None] | None = None

        self.title(app_name())
        self.resizable(False, False)
        self.configure(background=theme.c("panel"))
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

        # 主窗口在用户做选择之前是隐藏的。注意：不能对隐藏的主窗口调用
        # transient()，否则 Windows 会把这个子窗口一起藏掉，用户什么都看不到。
        if master is not None and master.winfo_viewable():
            self.transient(master)

        self._build()
        self._refresh()

        self.update_idletasks()
        self._center()
        self.deiconify()
        self.lift()
        self.update()          # 渲染一次，居中/取尺寸才准
        # update() 会处理事件队列，极端情况下窗口可能在这期间就被销毁了；
        # 这时别再对已经不存在的窗口调 grab_set（会报 bad window path name）。
        if not self.winfo_exists():
            return
        if self._modal:
            self.grab_set()
            self.focus_force()

    # -- 界面 ---------------------------------------------------------------

    def _build(self) -> None:
        header = tk.Frame(self, background=theme.c("accent"))
        header.pack(fill="x")
        tk.Label(header, text=app_full_name(), background=theme.c("accent"), foreground="white",
                 font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w", padx=24, pady=(16, 0))
        tk.Label(header, text=f"v{__version__}　　{_('把一个工程编译成 Windows 安装包')}",
                 background=theme.c("accent"), foreground=theme.c("accent_soft"),
                 font=APP_FONT).pack(anchor="w", padx=24, pady=(3, 15))

        body = ttk.Frame(self, padding=(24, 18, 24, 0))
        body.pack(fill="both", expand=True)

        row = ttk.Frame(body)
        row.pack(fill="x")
        ttk.Button(row, text=_("新建工程"), width=18, command=self._new).pack(side="left")
        ttk.Button(row, text=_("打开已有工程…"), width=18,
                   command=self._browse).pack(side="left", padx=(10, 0))

        ttk.Label(body, text=_("最近打开"), font=BOLD).pack(anchor="w", pady=(22, 6))

        self.empty_hint = ttk.Label(
            body, foreground=theme.c("hint"), wraplength=540, justify="left",
            text=_("还没有打开过任何工程。\n\n点上面的「新建工程」从零开始，"
                   "或者用「打开已有工程…」选一个 .aiproj 文件。"))

        self.holder = ttk.Frame(body)
        self.holder.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(self.holder, columns=("name", "where"),
                                 show="headings", height=7, selectmode="browse")
        self.tree.heading("name", text=_("工程"))
        self.tree.heading("where", text=_("位置"))
        self.tree.column("name", width=190, anchor="w", stretch=False)
        self.tree.column("where", width=340, anchor="w")
        scroll = ttk.Scrollbar(self.holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.tag_configure("demo", foreground=theme.c("accent"))
        self.tree.bind("<Double-1>", lambda _e: self._open_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._sync_buttons())
        self.tree.bind("<Return>", lambda _e: self._open_selected())

        footer = ttk.Frame(self, padding=(24, 12, 24, 16))
        footer.pack(fill="x")
        self.list_actions = ttk.Frame(footer)
        self.list_actions.pack(side="left")
        self.open_button = ttk.Button(self.list_actions, text=_("打开选中的工程"),
                                      command=self._open_selected)
        self.open_button.pack(side="left")
        self.forget_button = ttk.Button(self.list_actions, text=_("移除记录"),
                                        command=self._forget)
        self.forget_button.pack(side="left", padx=(8, 0))
        ttk.Button(footer, text=_("退出"), width=10, command=self._cancel).pack(side="right")

    def _center(self) -> None:
        width = max(self.winfo_reqwidth(), 620)
        height = max(self.winfo_reqheight(), 430)
        x = (self.winfo_screenwidth() - width) // 2
        y = max(0, (self.winfo_screenheight() - height) // 2 - 40)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # -- 数据 ---------------------------------------------------------------

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())

        # 第一行固定是自带的演示项目，后面才是用户最近打开的
        rows: list[tuple[str, Path, bool, bool]] = []
        demo_path = demo.demo_project_path()
        if demo_path is not None:
            rows.append(("demo", Path(demo_path), Path(demo_path).is_file(), True))
        for index, (path, exists) in enumerate(self.settings.existing()):
            rows.append((f"r{index}", Path(path), exists, False))

        if rows:
            self.holder.pack(fill="both", expand=True)
            self.empty_hint.pack_forget()
            self.list_actions.pack(side="left")
        else:
            self.holder.pack_forget()
            self.empty_hint.pack(anchor="w", pady=(0, 6))
            self.list_actions.pack_forget()

        for iid, path, exists, is_demo in rows:
            name = _("演示测试项目") if is_demo else path.stem
            if not exists:
                name += _("（找不到）")
            tags = ("demo",) if is_demo else ()
            self.tree.insert("", "end", iid=iid, values=(name, str(path.parent)), tags=tags)
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        selection = self.tree.selection()
        is_demo = bool(selection) and selection[0] == "demo"
        self.open_button.state(["!disabled"] if selection else ["disabled"])
        self.forget_button.state(
            ["disabled"] if (not selection or is_demo) else ["!disabled"])

    def _selected_path(self) -> str | None:
        selection = self.tree.selection()
        if not selection:
            return None
        iid = selection[0]
        if iid == "demo":
            path = demo.demo_project_path()
            return str(path) if path is not None else None
        index = int(iid[1:])
        entries = self.settings.existing()
        if index >= len(entries):
            return None
        return entries[index][0]

    # -- 动作 ---------------------------------------------------------------

    def _new(self) -> None:
        self.result = ("new", None)
        self.destroy()

    def _browse(self) -> None:
        chosen = filedialog.askopenfilename(parent=self, title=_("打开工程"),
                                            filetypes=file_types())
        if not chosen:
            return
        self.result = ("open", chosen)
        self.destroy()

    def _open_selected(self) -> None:
        path = self._selected_path()
        if not path:
            return
        if not Path(path).is_file():
            messagebox.showerror(
                _("找不到工程文件"),
                _("{path}\n\n这个位置已经打不开了（文件被移动、删除，或者所在磁盘没插上）。\n"
                  "可以用「移除记录」把它从列表里去掉。").format(path=path),
                parent=self)
            return
        self.result = ("open", path)
        self.destroy()

    def _forget(self) -> None:
        selection = self.tree.selection()
        if selection and selection[0] == "demo":
            messagebox.showinfo(
                _("演示项目"),
                _("这是随软件自带的演示项目，不能从列表里移除。"), parent=self)
            return
        path = self._selected_path()
        if not path:
            return
        self.settings.forget(path)
        try:
            save_settings(self.settings)
        except Exception:  # noqa: BLE001 - 存不下来也不影响本次使用
            pass
        self._refresh()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
