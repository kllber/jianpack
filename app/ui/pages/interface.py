"""第 4 步：安装界面定制（含快捷方式设置）。"""

from __future__ import annotations

from tkinter import ttk

from ...i18n import t as _
from ..widgets import hint_label, section
from .base import StepPage


class InterfacePage(StepPage):
    title = "安装界面"
    description = "各页面的文案与图片"
    subtitle = "自定义安装向导里每一页的文字和图片，留空就用默认内容"

    def build(self, parent: ttk.Frame) -> None:
        interface = self.app.project.interface

        common = self.section(parent, "通用")
        hint_label(common,
                   "文字里可以用这些占位符：{appName} {appVersion} {appPublisher} "
                   "{appHomepage} {installMode}；"
                   "也可以用 $INSTDIR 这类安装时才会确定的路径。")
        self.text(common, "底部状态栏", interface, "branding_text",
                  hint="安装向导最下面那行小字")
        self.check(common, "安装中途取消时二次确认", interface, "show_abort_warning")
        self.check(common, "显示安装过程日志", interface, "show_details",
                   hint="关掉之后安装界面更简洁，只留进度条")
        self.image_field(common, "内页页头图片", interface, "header_image", "header",
                         hint="出现在许可协议 / 更新日志 / 安装位置等内页的左上角。"
                              "不选也可以，页头就只显示标题文字。")

        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True, pady=(4, 0))
        self._notebook = notebook
        self._tab_keys: list[str] = []      # 各子标签的原文名，供预览定位（与语言无关）
        notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._welcome(notebook, interface)
        self._license(notebook, interface)
        self._changelog(notebook, interface)
        self._directory(notebook, interface)
        self._options_tab(notebook, interface)
        self._finish(notebook, interface)

    # -- 各分页 -------------------------------------------------------------

    def _on_tab_changed(self, _event=None) -> None:
        """把自己的子标签名字告诉外部，预览面板据此切换页面。

        对外用**原文名**（中文），预览面板的映射表就不用跟着语言变。
        """
        notebook = getattr(self, "_notebook", None)
        if notebook is None:
            return
        try:
            index = notebook.index(notebook.select())
        except tk.TclError:
            return
        keys = getattr(self, "_tab_keys", [])
        text = keys[index] if 0 <= index < len(keys) else ""
        if text and self.app.context.get("subtab") != text:
            self.app.context["subtab"] = text
            self.app.notify()          # 只刷新预览，不算改动

    def _tab(self, notebook: ttk.Notebook, text: str) -> ttk.Frame:
        frame = ttk.Frame(notebook, padding=12)
        self._tab_keys.append(text)
        notebook.add(frame, text=_(text))
        return frame

    def _welcome(self, notebook, interface) -> None:
        page = self._tab(notebook, "欢迎页")
        on = self.check(page, "显示欢迎页", interface.welcome, "enabled")
        body = ttk.Frame(page)
        body.pack(fill="x")
        self.text(body, "标题", interface.welcome, "title", label_width=10)
        self.text(body, "正文", interface.welcome, "text", height=5, label_width=10)
        self.image_field(body, "左侧图片", interface.welcome, "image", "welcome", label_width=10,
                         hint="只出现在欢迎页和完成页的左侧。留空则用默认蓝色背景。")
        self.gate(body, lambda: bool(on.get()), [on])

    def _license(self, notebook, interface) -> None:
        page = self._tab(notebook, "许可协议")
        on = self.check(page, "显示许可协议页", interface.license, "enabled")
        body = ttk.Frame(page)
        body.pack(fill="x")
        self._text_source_block(
            body, interface.license, "协议", label_width=11, height=12,
            text_hint="直接在这里写条款，改起来最快。换行和空行都按原样显示。",
            file_hint="不用管编码，程序会自动转成 NSIS 需要的格式")
        self.check(body, "必须勾选「我接受」才能继续", interface.license, "require_accept")
        self.text(body, "勾选文案", interface.license, "accept_text", label_width=11)
        self.text(body, "上方提示", interface.license, "text_top", label_width=11,
                  hint="显示在协议框上方的小字")
        self.text(body, "下方提示", interface.license, "text_bottom", label_width=11,
                  hint="显示在协议框下方的小字")
        self.gate(body, lambda: bool(on.get()), [on])

    def _changelog(self, notebook, interface) -> None:
        page = self._tab(notebook, "更新日志")
        on = self.check(page, "显示更新日志页", interface.changelog, "enabled")
        body = ttk.Frame(page)
        body.pack(fill="x")
        self._text_source_block(
            body, interface.changelog, "日志", label_width=11, height=12,
            text_hint="每次发新版改这里就行。写多长都不会被截断。",
            file_hint="不用管编码，程序会自动转成 NSIS 需要的格式")
        self.text(body, "标题", interface.changelog, "title", label_width=11)
        self.text(body, "副标题", interface.changelog, "subtitle", label_width=11)
        self.gate(body, lambda: bool(on.get()), [on])

    def _text_source_block(self, parent, target, noun: str, text_hint: str,
                           file_hint: str, height: int = 12,
                           label_width: int = 11) -> None:
        """「直接编辑正文 / 从 txt 导入」二选一的编辑块。

        两种来源的内容都留在模型里，来回切换不会丢东西；
        打包时只使用当前选中的那一种。
        """
        from tkinter import messagebox

        from ...core.errors import ProjectFileError
        from ...engine.assets import read_text_auto

        # 两个容器只有其中一个会显示。放进独立的 switcher 里，
        # pack / pack_forget 就不会把外层的排版顺序搞乱。
        switcher = ttk.Frame(parent)
        text_holder = ttk.Frame(switcher)
        file_holder = ttk.Frame(switcher)

        def sync(value: object) -> None:
            if value == "file":
                text_holder.pack_forget()
                file_holder.pack(fill="x")
            else:
                file_holder.pack_forget()
                text_holder.pack(fill="x")

        self.radio(parent, "内容来源", target, "source", [
            ("text", "直接在下面编辑"),
            ("file", "从 txt 文件导入"),
        ], on_change=sync)
        switcher.pack(fill="x")

        text_widget = self.text(text_holder, f"{noun}正文", target, "text",
                                height=height, label_width=label_width, hint=text_hint)
        self.path(file_holder, f"{noun}文件", target, "file", mode="file",
                  patterns=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                  import_subdir="payload", label_width=label_width, hint=file_hint)

        def load_into_editor() -> None:
            top = self.winfo_toplevel()
            relative = getattr(target, "file", None)
            if not relative:
                messagebox.showinfo(_("还没选文件"),
                                    _("先选一个 {noun} 的 txt 文件。").format(noun=_(noun)),
                                    parent=top)
                return
            try:
                content = read_text_auto(self.app.base_dir / relative)
            except (OSError, ProjectFileError) as exc:
                messagebox.showerror(_("读不了这个文件"), str(exc), parent=top)
                return
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", content)
            target.source = "text"
            target.text = content
            source_var.set(_("直接在下面编辑"))   # 让上面的单选按钮跟着切过去
            sync("text")
            self.app.touch()

        ttk.Button(file_holder, text=_("读入编辑器（改成直接编辑）"),
                   command=load_into_editor).pack(anchor="w", pady=(6, 0))

        source_var = self._last_radio_var
        hint_label(parent, "两种来源随时切换，两边的内容都会保留；"
                           "打包时只用当前选中的那一种。")

        def refresh() -> None:
            """切回本页时，把界面按模型重新同步一遍。"""
            with self.app.quiet():
                current = getattr(target, "source", "file")
                source_var.set(_("从 txt 文件导入") if current == "file"
                               else _("直接在下面编辑"))
                sync(current)
                body = getattr(target, "text", "") or ""
                if text_widget.get("1.0", "end-1c") != body:
                    text_widget.delete("1.0", "end")
                    text_widget.insert("1.0", body)

        self._enter_actions.append(refresh)
        refresh()

    def _directory(self, notebook, interface) -> None:
        page = self._tab(notebook, "安装位置页")
        hint_label(page, "注意：如果第 3 步关掉了「允许用户修改安装位置」，这一页不会显示。")
        body = ttk.Frame(page)
        body.pack(fill="x")
        self.text(body, "上方说明", interface.directory_page, "text_top",
                  height=4, label_width=11)
        self.text(body, "输入框标签", interface.directory_page, "text_destination",
                  label_width=11)
        # 这一页是否会出现取决于第 3 步；切回本页时会重新判断
        self.gate(body, lambda: bool(self.app.project.install.allow_change_dir))

    def _options_tab(self, notebook, interface) -> None:
        page = self._tab(notebook, "安装选项页")
        on = self.check(page, "显示安装选项页", interface.options_page, "enabled",
                        hint="只有「桌面 / 开始菜单快捷方式」至少启用了一个时才会显示")
        body = ttk.Frame(page)
        body.pack(fill="x")
        self.text(body, "标题", interface.options_page, "title", label_width=11)
        self.text(body, "副标题", interface.options_page, "subtitle", label_width=11)
        self.text(body, "分组框标题", interface.options_page, "group_text", label_width=11)
        self.text(body, "说明", interface.options_page, "intro", height=3, label_width=11)
        self.text(body, "底部提示", interface.options_page, "hint", height=3, label_width=11)
        self.gate(body, lambda: bool(on.get()), [on])
        # 快捷方式设置（原来单独一步，现在并到这里）
        self._shortcuts_block(page)

    def _shortcuts_block(self, parent) -> None:
        """桌面 / 开始菜单快捷方式（原来独立的「第 5 步」，现并入本页）。"""
        shortcuts = self.app.project.shortcuts

        def group(title: str) -> ttk.LabelFrame:
            # 注意：这里不能用 self.section()——那个会把分组框排到**页面级**的
            # 自动两列区里（忽略传入的父容器），放进标签页会跑到标签条外面去。
            box = ttk.LabelFrame(parent, text=" " + _(title) + " ",
                                 padding=(12, 8, 12, 10))
            box.pack(fill="x", pady=(6, 10))
            return box

        hint_label(parent,
                   "「允许用户修改」如果关掉，安装选项页上对应的复选框会变成灰色不可点，"
                   "一律按「默认勾选」执行。")

        desktop = group("桌面快捷方式")
        desk_on = self.check(desktop, "启用桌面快捷方式", shortcuts.desktop, "enabled")
        desk_body = ttk.Frame(desktop)
        desk_body.pack(fill="x")
        self.check(desk_body, "默认勾选", shortcuts.desktop, "default")
        self.check(desk_body, "允许用户在安装时修改", shortcuts.desktop, "user_can_toggle")
        self.text(desk_body, "快捷方式名称", shortcuts.desktop, "name",
                  hint="不带 .lnk 后缀")
        self.gate(desk_body, lambda: bool(desk_on.get()), [desk_on])

        start_menu = group("开始菜单快捷方式")
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

    def _finish(self, notebook, interface) -> None:
        page = self._tab(notebook, "完成页")
        self.text(page, "标题", interface.finish, "title", label_width=11)
        self.text(page, "正文", interface.finish, "text", height=5, label_width=11,
                  hint="可以用 $INSTDIR 显示安装位置")

        run_on = self.check(page, "提供「立即运行」复选框", interface.finish, "run_app")
        run_body = ttk.Frame(page)
        run_body.pack(fill="x")
        self.text(run_body, "复选框文字", interface.finish, "run_text", label_width=11)
        self.gate(run_body, lambda: bool(run_on.get()), [run_on])

        auto_on = self.check(page, "提供「开机自启」复选框", interface.finish,
                             "autostart_enabled")
        auto_body = ttk.Frame(page)
        auto_body.pack(fill="x")
        self.text(auto_body, "复选框文字", interface.finish, "autostart_text", label_width=11)
        self.check(auto_body, "默认勾选", interface.finish, "autostart_default")
        self.gate(auto_body, lambda: bool(auto_on.get()), [auto_on])

        link_on = self.check(page, "显示超链接", interface.finish.link, "enabled")
        link_body = ttk.Frame(page)
        link_body.pack(fill="x")
        self.text(link_body, "链接文字", interface.finish.link, "text", label_width=11)
        self.text(link_body, "链接地址", interface.finish.link, "url", label_width=11,
                  hint="填官网地址，一般是 {appHomepage}")
        self.gate(link_body, lambda: bool(link_on.get()), [link_on])
