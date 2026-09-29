"""第 3 步：安装设置。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...i18n import t as _
from ..widgets import hint_label, section
from .base import StepPage


class InstallPage(StepPage):
    title = "安装设置"
    description = "安装路径、用户数据与卸载"
    subtitle = "决定默认装到哪、卸载时怎么处理用户数据（装给谁在第 5 步选）"

    def build(self, parent: ttk.Frame) -> None:
        install = self.app.project.install
        uninstall = self.app.project.uninstall

        # 「装给所有用户 / 仅当前用户」是输出选项，统一放到第 5 步多选，
        # 免得这里选一遍、那里再勾一遍，还容易和预览对不上。
        hint_label(parent,
                   "装给「所有用户」还是「仅当前用户」在第 5 步「打包」里选，"
                   "两种版本也能同时生成。这一页只管安装路径、用户数据和卸载。")

        location = self.section(parent, "安装位置")
        self.auto_dir = tk.BooleanVar(value=install.default_dir is None)
        ttk.Checkbutton(location, text=_("使用默认路径（按安装模式自动选择）"),
                        variable=self.auto_dir,
                        command=self._sync_dir_state).pack(anchor="w")

        row = ttk.Frame(location)
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(row, text=_("自定义路径"), width=15).pack(side="left")
        self.dir_var = tk.StringVar(value=install.default_dir or "")
        self.dir_entry = ttk.Entry(row, textvariable=self.dir_var)
        self.dir_entry.pack(side="left", fill="x", expand=True)
        self.dir_var.trace_add("write", lambda *_: self.app.touch())

        hint_label(location,
                   "可以用 $PROGRAMFILES64 / $LOCALAPPDATA 这类变量，也可以用 {appName}。\n"
                   "例如：  D:\\软件\\{appName}      或      $PROGRAMFILES64\\MyCorp\\{appName}")

        self.check(location, "允许用户在安装时修改安装位置", install, "allow_change_dir",
                   hint="关掉的话就不显示「安装位置」页，强制装到上面的路径")
        self.check(location, "记住上次安装的位置", install, "remember_last_dir",
                   hint="写进注册表，下次安装（比如升级）时自动带出来")
        self.check(location, "在「程序和功能」里显示占用空间", install, "estimated_size_auto")

        data = self.section(parent, "用户数据与卸载")
        path_var = self.text(
            data, "用户数据目录", uninstall, "user_data_path",
            hint="程序运行时存放配置/数据的地方，例如 $APPDATA\\{appName}。留空表示没有独立的数据目录。")

        # 没有独立数据目录时，下面这些都没意义 -> 变灰
        has_data = lambda: bool(path_var.get().strip())
        ask_row = ttk.Frame(data)
        ask_row.pack(fill="x")
        ask_var = self.check(ask_row, "卸载时询问是否保留用户数据",
                             uninstall, "ask_keep_user_data")

        prompt_row = ttk.Frame(data)
        prompt_row.pack(fill="x")
        self.text(prompt_row, "询问文案", uninstall, "keep_user_data_text", height=4,
                  hint="卸载时弹出的询问内容")

        silent_row = ttk.Frame(data)
        silent_row.pack(fill="x")
        self.radio(silent_row, "静默卸载默认", uninstall, "delete_user_data_by_default", [
            (False, "保留用户数据（推荐）"),
            (True, "连用户数据一起删除"),
        ], hint="命令行静默卸载（Uninstall.exe /S）时按这个选项走")

        self.gate(ask_row, has_data, [path_var])
        self.gate(prompt_row, lambda: has_data() and bool(ask_var.get()),
                  [path_var, ask_var])
        self.gate(silent_row, has_data, [path_var])

        self._sync_dir_state()

    # -- 同步 ---------------------------------------------------------------

    def _sync_dir_state(self) -> None:
        self.dir_entry.configure(state="disabled" if self.auto_dir.get() else "normal")

    def flush(self) -> None:
        super().flush()
        install = self.app.project.install
        if self.auto_dir.get():
            install.default_dir = None
        else:
            install.default_dir = self.dir_var.get().strip() or None
