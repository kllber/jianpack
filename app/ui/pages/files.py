"""第 2 步：打包内容。"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ...core.errors import ProjectFileError
from ...core.project import FileItem
from ...core.versions import current_version_is_retired
from ...i18n import t as _
from .. import theme
from ..item_dest_dialog import ItemDestDialog
from ..widgets import APP_FONT, hint_label, section
from .base import StepPage


class FilesPage(StepPage):
    title = "打包内容"
    description = "添加要装到用户电脑上的文件"
    subtitle = "把要装到用户电脑上的文件加进来，还可以调整它们在安装目录里的位置"

    def build(self, parent: ttk.Frame) -> None:
        # 「当前版本已被淘汰」时的提示条（默认不显示）
        self.notice = tk.Label(
            parent, background=theme.c("note_bg"), foreground=theme.c("note_fg"),
            font=APP_FONT, justify="left", anchor="w", wraplength=760,
            highlightbackground=theme.c("note_border"), highlightthickness=1,
            padx=10, pady=8)
        self.notice.pack(fill="x", pady=(0, 8))
        self.notice.pack_forget()

        self._intro = hint_label(parent,
                                 "选中的文件和文件夹会被打进安装包。若选的位置在工程目录之外，"
                                 "程序会问你要不要复制一份进工程——复制进来的话，"
                                 "整个工程文件夹就可以随意搬移、压缩、发给别人了。")

        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(10, 6))
        self.add_file_button = ttk.Button(bar, text=_("添加文件…"), command=self.add_files)
        self.add_file_button.pack(side="left")
        self.add_folder_button = ttk.Button(bar, text=_("添加文件夹…"), command=self.add_folder)
        self.add_folder_button.pack(side="left", padx=(6, 0))
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=10)
        self.edit_dest_button = ttk.Button(bar, text=_("修改安装位置…"), command=self.edit_dest)
        self.edit_dest_button.pack(side="left")
        self.remove_button = ttk.Button(bar, text=_("移除"), command=self.remove)
        self.remove_button.pack(side="left", padx=(6, 0))
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=10)
        self.move_up_button = ttk.Button(bar, text=_("上移"), width=6,
                                         command=lambda: self.move(-1))
        self.move_up_button.pack(side="left")
        self.move_down_button = ttk.Button(bar, text=_("下移"), width=6,
                                           command=lambda: self.move(1))
        self.move_down_button.pack(side="left", padx=(6, 0))
        self._file_buttons = (self.add_file_button, self.add_folder_button,
                              self.edit_dest_button, self.remove_button,
                              self.move_up_button, self.move_down_button)

        columns = ("type", "source", "dest", "keep")
        self.tree = ttk.Treeview(parent, columns=columns, show="headings", height=11,
                                 selectmode="extended")
        self.tree.heading("type", text=_("类型"))
        self.tree.heading("source", text=_("来源"))
        self.tree.heading("dest", text=_("安装到"))
        self.tree.heading("keep", text=_("保留文件夹名"))
        self.tree.column("type", width=70, anchor="center", stretch=False)
        self.tree.column("source", width=320)
        self.tree.column("dest", width=160)
        self.tree.column("keep", width=110, anchor="center", stretch=False)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self.edit_dest())

        hint_label(parent, "双击某一行可以修改它的安装位置和「保留文件夹名」。"
                           "「安装到」写的是这个条目在安装目录里的路径，「.」表示安装目录根部。"
                           "文件夹条目默认保留自己的名字（装成 安装目录\\a\\…）；"
                           "取消「保留文件夹名」则只把里面的内容放到该目录。")

        main = self.section(parent, "主程序")
        line = ttk.Frame(main)
        line.pack(fill="x")
        self.main_var = tk.StringVar()
        self.main_box = ttk.Combobox(line, textvariable=self.main_var, width=40)
        self.main_box.pack(side="left")
        ttk.Button(line, text=_("重新识别"), width=10,
                   command=self.redetect).pack(side="left", padx=(6, 0))
        hint_label(main, "安装完成后「立即运行」和快捷方式都指向这个文件。"
                         "留空则自动使用安装目录根部唯一的 .exe。")
        self.main_var.trace_add("write", lambda *_: self.app.touch())

    # -- 数据同步 -----------------------------------------------------------

    def on_enter(self) -> None:
        super().on_enter()
        with self.app.quiet():
            self.refresh()
        self._sync_trimmed()

    def _sync_trimmed(self) -> None:
        """「已淘汰」的版本不允许再往"打包内容"里加东西。"""
        retired = current_version_is_retired(self.app.project)
        if retired:
            self.notice.configure(text=_(
                "当前版本已被淘汰，不能再加入文件了。\n"
                "想要更新打包内容，请在左上角的「版本迭代 / 切换」里切换到最新的两个版本。"))
            if not self.notice.winfo_manager():
                self.notice.pack(fill="x", pady=(0, 8), before=self._intro)
        else:
            self.notice.pack_forget()
        state = "disabled" if retired else "!disabled"
        for button in self._file_buttons:
            button.state([state])

    def flush(self) -> None:
        super().flush()
        if self.app.project is not None:
            self.app.project.app.main_exe = self.main_var.get().strip()

    # -- 列表 ---------------------------------------------------------------

    def refresh(self) -> None:
        project = self.app.project
        if project is None:
            return
        self.tree.delete(*self.tree.get_children())
        for index, item in enumerate(project.files.items):
            kind = _("文件夹") if item.type == "folder" else _("文件")
            keep = "—" if item.type == "file" else (_("是") if item.keep_folder else _("否"))
            self.tree.insert("", "end", iid=str(index),
                             values=(kind, item.source, item.dest or ".", keep))

        candidates = _root_exe_candidates(project)
        self.main_box.configure(values=candidates)
        self.main_var.set(project.app.main_exe or "")

    def redetect(self) -> None:
        project = self.app.project
        try:
            detected, hint = project.autodetect_main_exe()
        except ProjectFileError as exc:
            # 选的文件/文件夹丢了或路径非法时，别让异常冒到 Tk 里变成崩溃
            messagebox.showwarning(_("无法自动识别"), str(exc),
                                   parent=self.winfo_toplevel())
            return
        if detected:
            self.main_var.set(detected)
            messagebox.showinfo(_("已识别"),
                                _("主程序：{detected}").format(detected=detected),
                                parent=self.winfo_toplevel())
        else:
            messagebox.showwarning(_("无法自动识别"), hint, parent=self.winfo_toplevel())

    def _selected(self) -> list[int]:
        return sorted(int(iid) for iid in self.tree.selection())

    # -- 增删改 -------------------------------------------------------------

    def add_files(self) -> None:
        from tkinter import filedialog

        top = self.winfo_toplevel()
        chosen = filedialog.askopenfilenames(parent=top, title=_("选择要打包的文件"))
        if not chosen:
            return
        added = False
        for path in chosen:
            relative = self.app.import_path(top, path, "payload")
            if relative is None:
                continue
            self.app.project.files.items.append(FileItem(type="file", source=relative, dest="."))
            added = True
        if added:
            self.app.touch()
            self.refresh()

    def add_folder(self) -> None:
        from tkinter import filedialog

        top = self.winfo_toplevel()
        chosen = filedialog.askdirectory(parent=top, title=_("选择要打包的文件夹"))
        if not chosen:
            return
        relative = self.app.import_path(top, chosen, "payload")
        if relative is None:
            return
        self.app.project.files.items.append(FileItem(type="folder", source=relative, dest="."))
        self.app.touch()
        self.refresh()

    def remove(self) -> None:
        indices = self._selected()
        if not indices:
            messagebox.showinfo(_("没有选中"), _("请先在列表里选中要移除的条目。"),
                                parent=self.winfo_toplevel())
            return
        project = self.app.project
        items = project.files.items
        removed = [items[index] for index in indices]
        copies = project.removable_payload_paths(removed)
        if copies:
            base = project.base_dir.resolve()

            def show(path) -> str:
                try:
                    return path.relative_to(base).as_posix()
                except ValueError:
                    return str(path)

            listing = "\n".join("  • " + show(p) for p in copies)
            if not messagebox.askyesno(
                    _("移除并删除工程里的副本"),
                    _("以下内容是当初复制进工程的，移除后会连同工程里的副本一起删除：\n\n"
                      "{list}\n\n确定移除吗？").format(list=listing),
                    parent=self.winfo_toplevel()):
                return
        for index in reversed(indices):
            del items[index]
        self.app.discard_payload(copies)     # 清掉这份工程内副本，避免残留孤儿文件
        self.app.touch()
        self.refresh()

    def move(self, delta: int) -> None:
        indices = self._selected()
        if len(indices) != 1:
            messagebox.showinfo(_("请选中一项"), _("上移/下移一次只能移动一条。"),
                                parent=self.winfo_toplevel())
            return
        index = indices[0]
        target = index + delta
        items = self.app.project.files.items
        if not (0 <= target < len(items)):
            return
        items[index], items[target] = items[target], items[index]
        self.app.touch()
        self.refresh()
        self.tree.selection_set(str(target))

    def edit_dest(self) -> None:
        indices = self._selected()
        if len(indices) != 1:
            messagebox.showinfo(_("请选中一项"), _("一次只能修改一条的安装位置。"),
                                parent=self.winfo_toplevel())
            return
        index = indices[0]
        item = self.app.project.files.items[index]
        top = self.winfo_toplevel()

        folder_name = ""
        if item.type == "folder":
            try:
                folder_name = self.app.project.resolve(
                    "files.items[].source", item.source).name
            except ProjectFileError:
                folder_name = ""

        dialog = ItemDestDialog(top, dest=item.dest or ".",
                                keep_folder=item.keep_folder,
                                is_folder=item.type == "folder",
                                folder_name=folder_name,
                                source_label=item.source)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        item.dest, item.keep_folder = dialog.result
        self.app.touch()
        self.refresh()


def _root_exe_candidates(project) -> list[str]:
    try:
        return project.root_exe_candidates()
    except Exception:  # 源文件缺失时不该让界面崩掉
        return []
