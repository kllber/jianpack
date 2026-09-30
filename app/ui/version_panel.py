"""左栏顶部的「版本迭代 / 切换（创建）」面板。

- 上面是版本列表（当前版本排最前，带状态标签：含文件 / 仅配置）；
- 下面是按钮：新建版本 / 切换到选中版 …… 重命名 / 锁定 / 删除；
- 具体的文件搬运、快照逻辑都在 :mod:`app.core.versions` 里，这里只管界面。

规则：
- **刚新建的空工程**只显示「版本迭代 / 创建」，先让用户建第一个版本，再放出界面全貌；
- 切换版本前必须先保存（否则不让切）；新建版本会先存档并给出风险提醒；
- **固定只保留最近 2 版的程序文件**，更早的自动精简为「仅配置」；锁定的版本不会被精简。
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ..core.serialize import save_project
from ..core.versions import (DEFAULT_KEEP, VERSIONS_DIR, VersionStore,
                             bump_version, folder_size, is_blank_project,
                             load_store)
from . import theme
from ..i18n import t as _
from .integration_dialog import EntryDialog
from .widgets import APP_FONT, TITLE_FONT

WRAP = 500


def _fmt_date(created: str, fmt: str) -> str:
    """把 ISO 时间显示成 26/09/30 这样的短日期（顺序按设置）。"""
    raw = (created or "")[2:10]            # 2026-09-30T… -> 26-09-30
    parts = raw.replace("T", "-").split("-")
    if len(parts) < 3:
        return raw
    year, month, day = parts[0], parts[1], parts[2]
    if fmt == "mdy":
        return f"{month}/{day}/{year}"
    if fmt == "dmy":
        return f"{day}/{month}/{year}"
    return f"{year}/{month}/{day}"


def _size_text(num_bytes: int) -> str:
    """占用的存储空间：小于 1GB 用 MB，否则用 GB。"""
    mb = num_bytes / 1024 / 1024
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


class VersionPanel(ttk.Frame):
    """版本列表 + 操作按钮。"""

    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app
        self.window = None                # 主窗口（切完版本后重建界面）
        self._store: VersionStore | None = None
        self._blank = False               # 还没有任何版本的"空工程"
        self._sizes: dict[str, int] = {}  # 各版本占用的磁盘空间（后台统计）
        self._size_job = None
        self._size_busy = False
        self._size_queue: queue.Queue = queue.Queue()
        self._pump_job = None
        self._build()
        self.refresh()

    # -- 界面 ---------------------------------------------------------------

    def _build(self) -> None:
        self._title = ttk.Label(self, text=_("版本迭代 / 切换"), font=TITLE_FONT,
                                foreground=theme.c("accent"))
        self._title.pack(anchor="w", pady=(0, 6))

        holder = ttk.Frame(self)
        holder.pack(fill="x")
        self.tree = ttk.Treeview(holder, columns=("version", "date", "state", "size", "note"),
                                 show="headings", height=5, selectmode="browse")
        self.tree.heading("version", text=_("版本"))
        self.tree.heading("date", text=_("日期"))
        self.tree.heading("state", text=_("状态"))
        self.tree.heading("size", text=_("占用"))
        self.tree.heading("note", text=_("备注"))
        self.tree.column("version", width=112, anchor="w", stretch=False)
        self.tree.column("date", width=66, anchor="center", stretch=False)
        self.tree.column("state", width=58, anchor="center", stretch=False)
        self.tree.column("size", width=66, anchor="e", stretch=False)
        self.tree.column("note", width=180, anchor="w")
        # 当前打开的版本：整行常驻蓝底，一眼能认出来（不只是那个三角号）
        self.tree.tag_configure("current", background=theme.c("select_bg"),
                                foreground=theme.c("select_fg"))
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="x", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self.switch())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._sync_buttons())

        # 一行放齐：左边「新建 / 切换」，右边「重命名 / 锁定 / 删除」
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(6, 0))
        self.new_button = ttk.Button(bar, text=_("新建版本…"), command=self.new_version)
        self.new_button.pack(side="left")
        self.switch_button = ttk.Button(bar, text=_("切换到选中版"), command=self.switch)
        self.switch_button.pack(side="left", padx=(4, 0))
        self.delete_button = ttk.Button(bar, text=_("删除"), width=5, command=self.delete)
        self.delete_button.pack(side="right")
        self.lock_button = ttk.Button(bar, text=_("锁定"), width=5, command=self.toggle_lock)
        self.lock_button.pack(side="right", padx=(0, 4))
        self.rename_button = ttk.Button(bar, text=_("重命名…"), width=8, command=self.rename)
        self.rename_button.pack(side="right", padx=(0, 4))

        self.hint = ttk.Label(self, foreground=theme.c("hint"), justify="left",
                              wraplength=WRAP, font=("Microsoft YaHei UI", 8), text="")
        self.hint.pack(anchor="w", pady=(6, 0))

    # -- 数据 ---------------------------------------------------------------

    def _project(self):
        return self.app.project

    def is_create_mode(self) -> bool:
        return self._blank

    def refresh(self) -> None:
        project = self._project()
        self.tree.delete(*self.tree.get_children())
        if project is None:
            self._store = None
            self._blank = False
            self._title.configure(text=_("版本迭代 / 切换"))
            self.hint.configure(text=_("打开工程后，可以在这里把当前状态存成一个版本，"
                                       "之后一键切回。"))
            self._sync_buttons()
            return

        self._blank = is_blank_project(project)
        store = load_store(project)
        if not self._blank:
            # 老工程（还没写过版本清单，但已经有内容）先按当前版本登记一条
            store.ensure_current(project)
        self._store = store
        self._title.configure(text=_("版本迭代 / 创建") if self._blank
                              else _("版本迭代 / 切换"))

        current = store.current_item()
        date_format = self._date_format()
        retired_ids = {i.id for i in store.retired_items()}
        for item in store.ordered():
            is_current = item is not None and item.id == store.current
            lock = "🔒 " if item.locked else ""
            if is_current:
                name = "▶ " + lock + (f"v{project.app.version}"
                                      if project.app.version else item.display())
            else:
                name = lock + item.display()
            if item.id in retired_ids:
                state = _("已淘汰")
            elif is_current:
                state = _("当前")
            elif item.payload_stored:
                state = _("含文件")
            else:
                state = _("空")
            size = self._sizes.get(item.id)
            date = _fmt_date(item.created_at, date_format)
            self.tree.insert("", "end", iid=item.id,
                             values=(name, date, state,
                                     _size_text(size) if size is not None else "…",
                                     item.note),
                             tags=("current",) if is_current else ())

        if self._blank:
            self.hint.configure(text=_(
                "这个工程还没有任何版本。点「新建版本…」创建第一个版本，"
                "填好版本号后，完整界面就会出现。"))
        else:
            self.hint.configure(text=_(
                "切换 / 新建版本前会先保存工程。\n"
                "只保留最近 {keep} 版的程序文件，更早的版本「已淘汰」（不能再加文件）；"
                "锁定的版本除外。").format(keep=DEFAULT_KEEP))

        if current is not None and not self._blank:
            self.tree.selection_set(current.id)
        self.schedule_size_refresh()
        self._sync_buttons()

    def schedule_size_refresh(self, delay: int = 250) -> None:
        """后台重新统计各版本的占用（不阻塞界面）。"""
        if self._store is None or self.app.project is None:
            return
        if self._size_job is not None:
            try:
                self.after_cancel(self._size_job)
            except tk.TclError:
                pass
        self._size_job = self.after(delay, self._start_size_job)

    def _start_size_job(self) -> None:
        self._size_job = None
        if self._size_busy or self._store is None or self.app.project is None:
            return
        self._size_busy = True
        base = self.app.project.base_dir
        store = self._store
        current = store.current
        others = [(i.id, store.dir_for(i.id)) for i in store.items if i.id != current]
        self._size_queue = queue.Queue()

        def work() -> None:
            results: dict[str, int] = {}
            try:
                results[current] = folder_size(base, skip={VERSIONS_DIR, "build"})
                for vid, path in others:
                    results[vid] = folder_size(path)
            except Exception:  # noqa: BLE001 - 统计失败不该影响界面
                pass
            self._size_queue.put(results)

        threading.Thread(target=work, daemon=True).start()
        self._size_pump()

    def _size_pump(self) -> None:
        if not self.winfo_exists():
            return
        try:
            results = self._size_queue.get_nowait()
        except queue.Empty:
            self._pump_job = self.after(120, self._size_pump)
            return
        self._pump_job = None
        self._size_busy = False
        self._sizes.update(results)
        for vid, size in results.items():
            try:
                if self.tree.exists(vid):
                    self.tree.set(vid, "size", _size_text(size))
            except tk.TclError:
                pass

    def _date_format(self) -> str:
        settings = getattr(getattr(self, "window", None), "settings", None)
        value = getattr(settings, "date_format", "ymd") if settings is not None else "ymd"
        return value if value in ("ymd", "mdy", "dmy") else "ymd"

    def _sync_buttons(self) -> None:
        window = getattr(self, "window", None)
        locked = bool(window is not None and getattr(window, "editing_locked", False))
        has_project = self._project() is not None
        is_demo = bool(has_project and window is not None and window._is_demo())
        editable = has_project and not locked and not is_demo
        store = self._store
        selection = self.tree.selection()
        vid = selection[0] if selection else ""

        # 「新建版本」只要工程可编辑就能点（空工程也要能点）
        self.new_button.state(["!disabled"] if editable else ["disabled"])

        can_switch = editable and not self._blank and bool(vid) \
            and store is not None and vid != store.current
        self.switch_button.state(["!disabled"] if can_switch else ["disabled"])

        can_edit = editable and not self._blank and bool(vid)
        self.rename_button.state(["!disabled"] if can_edit else ["disabled"])
        self.delete_button.state(
            ["!disabled"] if (can_edit and store is not None and vid != store.current)
            else ["disabled"])
        # 「已淘汰」的版本不允许再上锁（否则它会借锁重新变得可用，逻辑就乱了）
        retired = bool(can_edit and store is not None and store.is_retired(vid))
        self.lock_button.state(
            ["!disabled"] if (can_edit and not retired) else ["disabled"])
        if store is not None and vid:
            item = store.item(vid)
            self.lock_button.configure(text=_("解锁") if item and item.locked else _("锁定"))

        if is_demo:
            self.hint.configure(text=_("演示项目是只读的，不能做版本操作。"))

    def _selected(self) -> str:
        selection = self.tree.selection()
        return selection[0] if selection else ""

    def destroy(self) -> None:
        for job in (self._size_job, self._pump_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self._size_job = None
        self._pump_job = None
        super().destroy()

    # -- 动作 ---------------------------------------------------------------

    def new_version(self) -> None:
        project = self._project()
        if project is None or self._store is None:
            return
        first = self._blank
        if first:
            title = _("创建版本")
            question = _("这个工程还没有任何版本。\n\n"
                         "点「确定」后创建第一个版本（版本号可在下一步填写），"
                         "之后完整界面就会出现。\n\n确定创建吗？")
        else:
            title = _("新建版本")
            question = _(
                "新建版本会先把当前版本存档到工程里，然后进入新版本。\n\n"
                "请注意：\n"
                "• 会先保存当前工程；\n"
                "• 当前版本的配置、图标**和程序文件**都会一起存档（占用额外空间）；\n"
                "• 只保留最近 {keep} 版的程序文件，更早的版本会自动「已淘汰」（不能再加文件）；\n"
                "• 存档后，新版本的「打包内容」会**清空**，请重新添加本版本的程序文件。\n\n"
                "确定新建版本吗？").format(keep=DEFAULT_KEEP)
        if not messagebox.askyesno(title, question,
                                   parent=self.winfo_toplevel(), icon=messagebox.WARNING):
            return

        ok, needs_save = self._prepare()
        if not ok:
            return

        default = self._unique_default(project, first)
        dialog = EntryDialog(self.winfo_toplevel(), title, [
            {"key": "version", "label": "版本号", "default": default,
             "hint": "这一版的版本号，例如 1.0.0"},
            {"key": "note", "label": "备注", "hint": "这一版改了什么（可留空）"},
        ])
        if dialog.result is None:
            return
        version = str(dialog.result.get("version", "")).strip() or default
        note = str(dialog.result.get("note", "")).strip()

        existing = {i.version for i in self._store.items if i.version}
        if version in existing:
            messagebox.showwarning(
                _("版本号重复"),
                _("已经有一个 v{version} 的版本了，请换一个版本号。").format(version=version),
                parent=self.winfo_toplevel())
            return

        def work():
            item = self._store.new_version(project, version, note=note)
            save_project(project)          # 落盘（单文件容器会重新打包，这一步也慢）
            return item

        def done(item, error):
            if error is not None:
                messagebox.showerror(_("新建版本失败"), str(error),
                                     parent=self.winfo_toplevel())
                return
            self._after_change(reload=False)
            if first:
                messagebox.showinfo(
                    _("已创建版本"),
                    _("已创建版本 {name}，现在可以填写第 1 步的其它信息并添加打包内容了。")
                    .format(name=item.display()), parent=self.winfo_toplevel())
            else:
                messagebox.showinfo(
                    _("新建版本"),
                    _("已进入新版本 {name}。\n\n「打包内容」已清空，请在第 2 步添加"
                      "本版本要打包的文件，然后再打包。").format(name=item.display()),
                    parent=self.winfo_toplevel())

        self._run_op(_("正在新建版本…"), work, done, needs_save=needs_save)

    def _unique_default(self, project, first: bool) -> str:
        """算一个没被占用的默认版本号（把最后一个数字一直 +1 直到不重复）。"""
        if first:
            return project.app.version or "1.0.0"
        existing = {i.version for i in self._store.items if i.version} if self._store else set()
        candidate = bump_version(project.app.version)
        for _ in range(200):
            if candidate not in existing:
                return candidate
            candidate = bump_version(candidate)
        return candidate

    def switch(self) -> None:
        project = self._project()
        vid = self._selected()
        if project is None or self._store is None or not vid or self._blank:
            return
        if vid == self._store.current:
            return
        target = self._store.item(vid)
        if target is None:
            return

        ok, needs_save = self._prepare(switch=True)
        if not ok:
            return

        retired = self._store.is_retired(vid)
        note = "" if not retired else _(
            "\n\n注意：这个版本已被淘汰（程序文件已清理）；切换后「打包内容」会清空，"
            "并且不能再往里加文件——请在想继续开发时切回最新的两个版本。")
        if not messagebox.askyesno(
                _("切换版本"),
                _("要切换到版本「{name}」吗？\n\n"
                  "当前版本会先被存档到工程里。{note}").format(
                      name=target.display(), note=note),
                parent=self.winfo_toplevel()):
            return

        def work():
            self._store.switch_to(project, vid)
            # 注意：切换后内存里的 project 还是"旧版本"的，不能直接 save_project(project)
            # ——那会把目标的配置覆盖掉。先从磁盘重读（拿到目标版本的配置）再落盘。
            from ..core.project import reload_project
            fresh = reload_project(project)
            save_project(fresh)
            return True

        def done(_value, error):
            if error is not None:
                messagebox.showerror(_("切换版本失败"), str(error),
                                     parent=self.winfo_toplevel())
                return
            self._after_change(reload=True, clear_payload=retired)
            if retired:
                messagebox.showwarning(
                    _("已切换（已淘汰）"),
                    _("已切到版本「{name}」，但这个版本已被淘汰，不能再添加文件。\n\n"
                      "想继续更新，请切换到最新的两个版本。").format(
                          name=target.display()),
                    parent=self.winfo_toplevel())

        self._run_op(_("正在切换版本…"), work, done, needs_save=needs_save)

    def rename(self) -> None:
        vid = self._selected()
        if self._store is None or not vid:
            return
        item = self._store.item(vid)
        if item is None:
            return
        dialog = EntryDialog(self.winfo_toplevel(), _("重命名版本"), [
            {"key": "label", "label": "名称", "default": item.display()},
            {"key": "note", "label": "备注", "default": item.note},
        ])
        if dialog.result is None:
            return
        self._store.rename(vid, str(dialog.result.get("label", "")),
                           str(dialog.result.get("note", "")))
        self.refresh()

    def toggle_lock(self) -> None:
        vid = self._selected()
        if self._store is None or not vid:
            return
        item = self._store.item(vid)
        if item is None:
            return
        if item.locked:
            would_retire = self._store.would_retire_without_lock(vid)
            # 解锁一个"本来就会被淘汰"的版本：提醒它会失去保护、转为已淘汰
            if would_retire and not messagebox.askyesno(
                    _("解锁后会被淘汰"),
                    _("当前版本正常情况下已被淘汰，如果现在解锁会导致当前这个版本"
                      "不再受到保护，转为淘汰状态。\n\n确定解锁吗？"),
                    parent=self.winfo_toplevel(), icon=messagebox.WARNING):
                return
            if not would_retire:
                self._store.set_locked(vid, False)
                self.refresh()
                return
            # 解锁即淘汰：清掉程序文件（大版本会慢，走后台 + 加载窗）
            project = self._project()

            def work():
                self._store.set_locked(vid, False)
                self._store.prune()
                self._store.save()
                if project is not None:
                    save_project(project)
                return True

            def done(_value, error):
                if error is not None:
                    messagebox.showerror(_("解锁失败"), str(error),
                                         parent=self.winfo_toplevel())
                    return
                self.refresh()

            self._run_op(_("正在更新版本…"), work, done)
            return
        self._store.set_locked(vid, True)
        self.refresh()

    def delete(self) -> None:
        project = self._project()
        vid = self._selected()
        if project is None or self._store is None or not vid:
            return
        item = self._store.item(vid)
        if item is None or vid == self._store.current:
            return
        if not messagebox.askyesno(
                _("删除版本"),
                _("确定删除版本「{name}」吗？\n\n它的存档（配置、图标和程序文件）"
                  "都会被一起删掉，无法恢复。").format(name=item.display()),
                parent=self.winfo_toplevel(), icon=messagebox.WARNING):
            return
        def work():
            self._store.delete(vid)
            save_project(project)          # 把容器也更新一下
            return True

        def done(_value, error):
            if error is not None:
                messagebox.showerror(_("删除失败"), str(error),
                                     parent=self.winfo_toplevel())
                return
            self.refresh()

        self._run_op(_("正在删除版本…"), work, done)

    # -- 耗时操作 -----------------------------------------------------------

    def _run_op(self, status: str, work, on_done, needs_save: bool = False) -> None:
        """把耗时的版本操作放到后台线程跑，并弹一个加载窗（快就不弹）。

        ``work()`` 在后台线程执行（只做文件搬运 + 写盘）；``needs_save=True`` 时
        先把工程落盘（单文件工程要重新打包，这一步也慢）。完成后回主线程
        ``on_done(value, error)``。
        """
        window = getattr(self, "window", None)
        if window is None or not hasattr(window, "run_background"):
            try:
                on_done(work(), None)
            except Exception as exc:      # noqa: BLE001 - 按错误带回
                on_done(None, exc)
            return
        if getattr(window, "editing_locked", False) or window._version_busy:
            return
        project = self._project()
        if project is not None:
            try:
                window.flush_all()          # 控件里的最新值先收回模型
            except Exception:  # noqa: BLE001
                pass
        name = project.source_path.stem if project is not None else ""

        def combined():
            if needs_save and project is not None:
                save_project(project)       # 落盘（容器会重新打包）
            return work()

        window.set_editing_enabled(False)   # 操作期间锁住界面

        def done(value, error):
            window.set_editing_enabled(True)
            on_done(value, error)

        window.run_background(combined, done, status=status, file_name=name)

    # -- 收尾 ---------------------------------------------------------------

    def _prepare(self, switch: bool = False) -> tuple[bool, bool]:
        """操作前先 flush 控件，并问要不要保存。

        返回 ``(是否继续, 是否需要保存)``——真正的保存放到后台任务里做
        （单文件工程要重新打包，放主线程会卡住界面）。
        """
        window = getattr(self, "window", None)
        if window is None:
            return True, False
        try:
            window.flush_all()
        except Exception:  # noqa: BLE001 - flush 失败不影响后面的操作
            pass
        if not self.app.dirty:
            return True, False
        question = (_("切换版本前需要先保存当前工程。\n\n现在保存并切换吗？\n"
                      "（选择「否」将取消切换）") if switch else
                    _("新建版本前需要先保存当前工程。\n\n现在保存并新建吗？\n"
                      "（选择「否」将取消）"))
        if not messagebox.askyesno(_("需要先保存"), question,
                                   parent=self.winfo_toplevel()):
            return False, False
        return True, True

    def _after_change(self, reload: bool = True, clear_payload: bool = False) -> None:
        """版本操作之后收尾：让主窗口重建界面。

        落盘已经在后台线程里做完了（见各 work()），这里只负责刷新界面。
        """
        window = getattr(self, "window", None)
        if window is None:
            self.refresh()
            return
        window.after_version_change(reload=reload, clear_payload=clear_payload)
