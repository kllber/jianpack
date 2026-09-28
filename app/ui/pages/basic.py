"""第 1 步：基本信息。"""

from __future__ import annotations

from tkinter import ttk

from ..widgets import hint_label, section
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
