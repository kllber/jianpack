"""第 1 步：基本信息。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...i18n import t as _
from ..integration_dialog import EntryDialog
from ..widgets import APP_FONT, hint_label, keep_wheel_inside, section
from .base import StepPage


class BasicPage(StepPage):
    title = "基本信息"
    description = "应用名称、版本、版权与图标"
    subtitle = "这些信息会出现在安装向导、快捷方式和「控制面板 - 程序和功能」里"

    def build(self, parent: ttk.Frame) -> None:
        app = self.app.project.app

        hint_label(parent, "带 * 的是必填项，其余留空也能打包，只是信息会少一些。")

        identity = self.section(parent, "应用标识")
        self.text(identity, "应用名称 *", app, "name",
                  hint="安装向导里显示的名字，例如「我的小工具」")
        self.text(identity, "安装目录名", app, "dir_name",
                  hint="装到磁盘上的文件夹名，例如 MyApp。留空则同应用名。"
                       "中文软件建议用英文，中文路径在命令行和日志里容易出问题。")
        self.text(identity, "版本号 *", app, "version",
                  hint="显示用版本，例如 1.0.0 / 1.0.0.1")
        self.text(identity, "程序文件版本", app, "file_version",
                  hint="写进 exe 属性，必须是 a.b.c.d 四段数字。留空则按版本号自动补齐。")
        self.text(identity, "内部标识", app, "registry_key",
                  hint="注册表和卸载项用的键名，留空则同安装目录名。只能用字母、数字、- _ .")

        info = self.section(parent, "版权与联系方式")
        self.text(info, "公司 / 作者", app, "publisher",
                  hint="留空的话，控制面板的卸载列表里会显示「未知发布者」")
        self.text(info, "版权信息", app, "copyright",
                  hint="例如 Copyright (C) 2026 示例软件工作室")
        self.text(info, "官网地址", app, "homepage",
                  hint="会写进程序属性和卸载项的「访问支持」")
        self.text(info, "一句话描述", app, "description",
                  hint="显示在程序属性里")

        assets = self.section(parent, "图标")
        self.image_field(assets, "程序图标", app, "icon", "icon",
                         hint="会用在安装包、桌面快捷方式、开始菜单和「程序和功能」列表里。")

        self._languages_block(parent)

    # -- 程序属性：语言（可多选）--------------------------------------------

    def _languages_block(self, parent) -> None:
        from ...core.project import LANGUAGES, LanguageEntry

        interface = self.app.project.interface
        box = self.section(parent, "程序属性")

        ttk.Label(box, text=_("语言（可多选）")).pack(anchor="w")
        hint_label(box, "安装包 exe 属性里会列出所选语言；英语(美国) 是 NSIS 自带的，总会显示。")

        self._lang_items: list[tuple[str, int]] = list(LANGUAGES)
        known = {lcid for _name, lcid in self._lang_items}
        for entry in interface.languages:
            if entry.lcid not in known:
                self._lang_items.append((entry.name or f"LCID {entry.lcid}", entry.lcid))
                known.add(entry.lcid)

        listbox = tk.Listbox(box, selectmode="extended", height=6,
                             exportselection=False, activestyle="none", font=APP_FONT)
        for name, _lcid in self._lang_items:
            listbox.insert("end", _(name))
        for index, (_name, lcid) in enumerate(self._lang_items):
            if any(entry.lcid == lcid for entry in interface.languages):
                listbox.selection_set(index)
        listbox.pack(fill="x")
        listbox.bind("<<ListboxSelect>>", lambda _e: self._sync_languages())
        keep_wheel_inside(listbox)      # 滚轮只滚列表，别把整页也带着滚
        self._lang_list = listbox

        row = ttk.Frame(box)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Button(row, text=_("自定义语言…"),
                   command=self._add_language).pack(side="left")
        ttk.Button(row, text=_("全选"),
                   command=lambda: self._select_all_languages(True)).pack(side="left",
                                                                         padx=(6, 0))
        ttk.Button(row, text=_("全不选"),
                   command=lambda: self._select_all_languages(False)).pack(side="left",
                                                                           padx=(6, 0))

        self._enter_actions.append(self._refresh_languages)

    def _sync_languages(self) -> None:
        from ...core.project import LanguageEntry

        interface = self.app.project.interface
        chosen = self._lang_list.curselection()
        interface.languages = [LanguageEntry(name=name, lcid=lcid)
                               for index, (name, lcid) in enumerate(self._lang_items)
                               if index in chosen]
        self.app.touch()

    def _select_all_languages(self, on: bool) -> None:
        self._lang_list.selection_clear(0, "end")
        if on:
            self._lang_list.selection_set(0, "end")
        self._sync_languages()

    def _add_language(self) -> None:
        dialog = EntryDialog(self.winfo_toplevel(), _("自定义语言"), [
            {"key": "name", "label": "语言名称", "hint": "会显示在预览和程序属性里"},
            {"key": "lcid", "label": "语言 ID (LCID)",
             "hint": "十进制或 0x 十六进制，例如 2052；写进版本信息用的就是它"},
        ])
        if dialog.result is None:
            return
        raw = str(dialog.result.get("lcid", "")).strip()
        try:
            lcid = int(raw, 0) if raw else 0
        except ValueError:
            lcid = 0
        name = str(dialog.result.get("name", "")).strip() or f"LCID {lcid}"
        self._lang_items.append((name, lcid))
        self._lang_list.insert("end", name)
        self._lang_list.selection_set("end")
        self._sync_languages()

    def _refresh_languages(self) -> None:
        interface = self.app.project.interface
        with self.app.quiet():
            self._lang_list.selection_clear(0, "end")
            for index, (_name, lcid) in enumerate(self._lang_items):
                if any(entry.lcid == lcid for entry in interface.languages):
                    self._lang_list.selection_set(index)
