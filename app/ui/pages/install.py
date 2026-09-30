"""第 3 步：安装设置。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...core.project import AssocEntry, ProtocolEntry, RegEntry
from ...i18n import t as _
from ..integration_dialog import EntryDialog
from ..widgets import hint_label, keep_wheel_inside, section
from .base import StepPage

ASSOC_FIELDS = [    {"key": "ext", "label": "扩展名", "hint": "例如 .myext（带不带点都行）"},
    {"key": "description", "label": "描述", "hint": "显示在「打开方式」里"},
    {"key": "icon", "label": "图标", "hint": "安装目录内的相对路径；留空用主程序图标"},
    {"key": "is_default", "label": "设为默认打开方式", "kind": "check",
     "hint": "Windows 10/11 保护用户已选的默认程序，勾选只是把它注册为可选项，"
             "不一定会立刻成为默认"},
]
PROTO_FIELDS = [
    {"key": "scheme", "label": "协议名", "hint": "例如 myapp（对应 myapp://…）"},
    {"key": "description", "label": "描述"},
]
REG_FIELDS = [
    {"key": "root", "label": "根键", "kind": "combo", "default": "HKCU", "options": [
        ("HKCU", "HKCU（当前用户）"),
        ("HKLM", "HKLM（所有用户，需要管理员）")]},
    {"key": "path", "label": "路径", "hint": "例如 Software\\MyApp"},
    {"key": "name", "label": "值名", "hint": "留空 = 该键的默认值"},
    {"key": "type", "label": "类型", "kind": "combo", "default": "REG_SZ", "options": [
        ("REG_SZ", "字符串 REG_SZ"),
        ("REG_EXPAND_SZ", "可展开字符串 REG_EXPAND_SZ"),
        ("REG_DWORD", "32 位数字 REG_DWORD")]},
    {"key": "data", "label": "数据"},
]


MODE_TEXT = (
    ("perMachine", "为所有用户安装（需要管理员权限，装到 Program Files）"),
    ("perUser", "仅当前用户安装（免提权，装到 %LOCALAPPDATA%\\Programs）"),
)


class InstallPage(StepPage):
    title = "安装设置"
    description = "安装路径、用户数据与卸载"
    subtitle = "安装路径、用户数据与卸载；输出与编译也在这里"

    def build(self, parent: ttk.Frame) -> None:
        install = self.app.project.install
        uninstall = self.app.project.uninstall

        # 「装给所有用户 / 仅当前用户」以及输出、签名都收在这一页
        # （原来单独一个「打包」步骤；动作按钮移到了左栏常驻面板）。
        hint_label(parent,
                   "装给「所有用户」还是「仅当前用户」在本页下面的「要生成哪些版本」里选，"
                   "两种版本也能同时生成。打包动作在左下角常驻的「开始打包」面板里。")

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

        self._integration_block(parent)
        self._output_block(parent)
        self._sync_dir_state()

    # -- 输出与编译 ---------------------------------------------------------

    def _output_block(self, parent: ttk.Frame) -> None:
        """原来「打包」步骤里的设置，现在并到这一页（动作按钮在左栏）。"""
        build = self.app.project.build

        modes = self.section(parent, "要生成哪些版本")
        hint_label(modes, "勾一个就出一个安装包，勾两个就两个一起出；文件名会自动加 "
                          "-PerMachine / -PerUser 后缀，避免互相覆盖。")
        self.mode_vars: dict[str, tk.BooleanVar] = {}
        for key, text in MODE_TEXT:
            var = tk.BooleanVar(value=key in build.modes)
            ttk.Checkbutton(modes, text=_(text), variable=var).pack(anchor="w", pady=2)
            var.trace_add("write", lambda *_: self.app.touch())
            self.mode_vars[key] = var

        output = self.section(parent, "输出设置")
        self.path(output, "输出位置", build, "output_dir", mode="dir", optional=True,
                  hint="留空 = 输出到桌面；也可以填绝对路径（相对路径按工程文件所在目录算）")
        self.text(output, "文件名", build, "file_name",
                  hint="可以用 {appName} {appVersion}")
        self.combo(output, "压缩方式", build, "compression", [
            ("solid-lzma", "lzma 整体压缩（体积最小，推荐）"),
            ("lzma", "lzma 逐文件压缩"),
            ("zlib", "zlib（压缩最快，体积偏大）"),
            ("bzip2", "bzip2"),
        ])

        box = self.section(parent, "代码签名（高级）")
        self._sign_open = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text=_("展开：打包后自动签名（Authenticode）"),
                        variable=self._sign_open,
                        command=self._toggle_sign).pack(anchor="w")
        hint_label(box, "默认收起。需要给安装包做数字签名时再展开。")
        self._sign_body = ttk.Frame(box)
        self._sign_body.pack(fill="x")
        self._toggle_sign()

        body = self._sign_body
        sign_on = self.check(body, "打包后自动签名（Authenticode）", build, "sign_enabled",
                             hint="需要你自己有数字证书；不勾选就完全跳过。")
        inner = ttk.Frame(body)
        inner.pack(fill="x")
        self.path(inner, "证书文件", build, "sign_cert", mode="file",
                  patterns=[("证书文件", "*.pfx *.p12"), ("所有文件", "*.*")],
                  hint=".pfx / .p12 数字证书文件")
        self.text(inner, "证书密码", build, "sign_password",
                  hint="会保存在工程文件里（明文），请自行妥善保管")
        self.text(inner, "时间戳服务器", build, "sign_timestamp",
                  hint="留空则不添加时间戳")
        self.path(inner, "signtool 路径", build, "signtool", mode="file",
                  hint="留空则自动查找（PATH / Windows SDK）")
        self.gate(inner, lambda: bool(sign_on.get()), [sign_on])

    def _toggle_sign(self) -> None:
        if self._sign_open.get():
            self._sign_body.pack(fill="x")
        else:
            self._sign_body.pack_forget()

    # -- 系统集成（高级，收起式）--------------------------------------------

    def _integration_block(self, parent: ttk.Frame) -> None:
        box = self.section(parent, "系统集成（高级）")
        self._drawer_open = tk.BooleanVar(value=False)
        ttk.Checkbutton(box, text=_("展开：文件关联 / URL 协议 / 注册表"),
                        variable=self._drawer_open,
                        command=self._toggle_drawer).pack(anchor="w")
        hint_label(box, "默认收起。只有需要让安装包替你做这些系统集成时才展开。")

        self._drawer = ttk.Frame(box)
        self._drawer.pack(fill="x")
        self._toggle_drawer()

        integration = self.app.project.integration
        self._assoc_view = self._make_list(
            self._drawer, "文件关联", ("扩展名", "描述", "默认"),
            on_add=lambda: self._add_entry(
                _("添加文件关联"), ASSOC_FIELDS, integration.associations, AssocEntry),
            on_edit=lambda: self._edit_entry(
                self._assoc_view, _("编辑文件关联"), ASSOC_FIELDS,
                integration.associations, AssocEntry),
            on_del=lambda: self._del_entry(self._assoc_view, integration.associations))
        self._proto_view = self._make_list(
            self._drawer, "URL 协议", ("协议", "描述"),
            on_add=lambda: self._add_entry(
                _("添加 URL 协议"), PROTO_FIELDS, integration.protocols, ProtocolEntry),
            on_edit=lambda: self._edit_entry(
                self._proto_view, _("编辑 URL 协议"), PROTO_FIELDS,
                integration.protocols, ProtocolEntry),
            on_del=lambda: self._del_entry(self._proto_view, integration.protocols))
        self._reg_view = self._make_list(
            self._drawer, "注册表", ("根", "路径", "名称", "类型", "数据"),
            on_add=lambda: self._add_entry(
                _("添加注册表项"), REG_FIELDS, integration.registry, RegEntry),
            on_edit=lambda: self._edit_entry(
                self._reg_view, _("编辑注册表项"), REG_FIELDS,
                integration.registry, RegEntry),
            on_del=lambda: self._del_entry(self._reg_view, integration.registry))

        self._enter_actions.append(self._refresh_integration)
        self._refresh_integration()

    def _toggle_drawer(self) -> None:
        if self._drawer_open.get():
            self._drawer.pack(fill="x")
        else:
            self._drawer.pack_forget()

    def _make_list(self, parent, title: str, columns: tuple[str, ...],
                   on_add, on_edit, on_del) -> ttk.Treeview:
        box = ttk.LabelFrame(parent, text=" " + _(title) + " ", padding=(10, 6, 10, 8))
        box.pack(fill="x", pady=(8, 0))
        view = ttk.Treeview(box, columns=columns, show="headings", height=3,
                            selectmode="browse")
        for column in columns:
            view.heading(column, text=_(column))
            view.column(column, width=max(90, 470 // len(columns)), anchor="w")
        view.pack(fill="x")
        keep_wheel_inside(view)         # 滚轮只滚列表，别把整页也带着滚
        row = ttk.Frame(box)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Button(row, text=_("添加…"), width=8, command=on_add).pack(side="left")
        ttk.Button(row, text=_("编辑…"), width=8,
                   command=on_edit).pack(side="left", padx=(6, 0))
        ttk.Button(row, text=_("删除"), width=8,
                   command=on_del).pack(side="left", padx=(6, 0))
        return view

    @staticmethod
    def _selected_index(view: ttk.Treeview) -> int | None:
        selection = view.selection()
        return int(selection[0]) if selection else None

    def _add_entry(self, title: str, fields: list[dict], entries: list, make) -> None:
        dialog = EntryDialog(self.winfo_toplevel(), title, fields)
        if dialog.result is None:
            return
        entries.append(make(**dialog.result))
        self.app.touch()
        self._refresh_integration()

    def _edit_entry(self, view, title: str, fields: list[dict],
                    entries: list, make) -> None:
        index = self._selected_index(view)
        if index is None:
            return
        current = entries[index]
        values = {f["key"]: getattr(current, f["key"], "") for f in fields}
        dialog = EntryDialog(self.winfo_toplevel(), title, fields, values)
        if dialog.result is None:
            return
        entries[index] = make(**dialog.result)
        self.app.touch()
        self._refresh_integration()

    def _del_entry(self, view, entries: list) -> None:
        index = self._selected_index(view)
        if index is None:
            return
        del entries[index]
        self.app.touch()
        self._refresh_integration()

    def _refresh_integration(self) -> None:
        integration = self.app.project.integration
        self._assoc_view.delete(*self._assoc_view.get_children())
        for index, item in enumerate(integration.associations):
            self._assoc_view.insert(
                "", "end", iid=str(index),
                values=(item.ext, item.description, _("是") if item.is_default else _("否")))
        self._proto_view.delete(*self._proto_view.get_children())
        for index, item in enumerate(integration.protocols):
            self._proto_view.insert("", "end", iid=str(index),
                                    values=(item.scheme, item.description))
        self._reg_view.delete(*self._reg_view.get_children())
        for index, item in enumerate(integration.registry):
            self._reg_view.insert("", "end", iid=str(index),
                                  values=(item.root, item.path, item.name,
                                          item.type, item.data))

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
        modes = [key for key, var in self.mode_vars.items() if var.get()]
        self.app.project.build.modes = modes or ["perMachine"]
