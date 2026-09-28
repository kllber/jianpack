"""第 5 步：快捷方式。"""

from __future__ import annotations

from tkinter import ttk

from ..widgets import hint_label, section
from .base import StepPage


class ShortcutsPage(StepPage):
    title = "快捷方式"
    description = "桌面 / 开始菜单快捷方式"
    subtitle = "决定安装时创建哪些快捷方式，以及用户能不能自己改"

    def build(self, parent: ttk.Frame) -> None:
        shortcuts = self.app.project.shortcuts

        hint_label(parent,
                   "「允许用户修改」如果关掉，安装选项页上对应的复选框会变成灰色不可点，"
                   "一律按「默认勾选」执行。")

        desktop = self.section(parent, "桌面快捷方式")
        desk_on = self.check(desktop, "启用桌面快捷方式", shortcuts.desktop, "enabled")
        desk_body = ttk.Frame(desktop)
        desk_body.pack(fill="x")
        self.check(desk_body, "默认勾选", shortcuts.desktop, "default")
        self.check(desk_body, "允许用户在安装时修改", shortcuts.desktop, "user_can_toggle")
        self.text(desk_body, "快捷方式名称", shortcuts.desktop, "name",
                  hint="不带 .lnk 后缀")
        # 没启用桌面快捷方式 -> 下面这些没意义，变灰
        self.gate(desk_body, lambda: bool(desk_on.get()), [desk_on])

        start_menu = self.section(parent, "开始菜单快捷方式")
        menu_on = self.check(start_menu, "启用开始菜单快捷方式", shortcuts.start_menu, "enabled")
        menu_body = ttk.Frame(start_menu)
        menu_body.pack(fill="x")
        self.check(menu_body, "默认勾选", shortcuts.start_menu, "default")
        self.check(menu_body, "允许用户在安装时修改", shortcuts.start_menu, "user_can_toggle")
        self.text(menu_body, "快捷方式名称", shortcuts.start_menu, "name")
        self.check(menu_body, "放在同名子文件夹里", shortcuts.start_menu, "use_folder",
                   hint="开始菜单里会多一层文件夹，例如「开始菜单\\我的小工具\\我的小工具」")
        self.check(menu_body, "同时放一个「卸载」快捷方式",
                   shortcuts.start_menu, "uninstall_shortcut")
        self.gate(menu_body, lambda: bool(menu_on.get()), [menu_on])
