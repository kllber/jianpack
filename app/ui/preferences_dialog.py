"""首选项 / 设置窗口。

目前能改这几样「使用习惯」：

- 界面主题（浅色 / 深色）；
- 启动时要不要弹欢迎页；
- 启动时要不要自动打开上一次的工程；
- 默认要不要显示「安装效果预览」；
- 一键「恢复默认设置」（初始化软件）。

改主题需要重新创建界面（见 ``MainWindow._restart``），所以对话框只负责把
设置写盘并告诉主窗口「要不要重启」。
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..core import assoc, paths
from ..core.errors import PackError
from ..core.settings import Settings, save_settings
from . import theme
from .. import i18n
from ..i18n import t as _
from .widgets import APP_FONT

BOLD = ("Microsoft YaHei UI", 11, "bold")


def _size_text(num_bytes: int) -> str:
    mb = num_bytes / 1024 / 1024
    if mb >= 1:
        return f"{mb:.1f} MB"
    kb = num_bytes / 1024
    return f"{kb:.0f} KB" if kb >= 1 else f"{num_bytes} B"


class PreferencesDialog(tk.Toplevel):
    def __init__(self, master, settings: Settings) -> None:
        super().__init__(master)
        self.settings = settings
        # 调用方据此决定要不要重建界面
        self.saved = False
        self.restart_needed = False
        self.reset_done = False

        self.theme_var = tk.StringVar(value="dark" if settings.theme == "dark" else "light")
        self.language_var = tk.StringVar(value=i18n.normalize(settings.language))
        self.welcome_var = tk.BooleanVar(value=settings.show_welcome)
        self.preview_var = tk.BooleanVar(value=settings.show_preview)
        self.auto_last_var = tk.BooleanVar(value=settings.auto_open_last)

        self.title(_("首选项 / 设置"))
        self.resizable(False, False)
        self.configure(background=theme.c("panel"))
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

        if master is not None and master.winfo_viewable():
            self.transient(master)

        self._build()
        self.update_idletasks()
        self._center(master)
        self.deiconify()
        self.lift()
        self.update()
        self.grab_set()
        self.focus_set()

    # -- 界面 ---------------------------------------------------------------

    def _build(self) -> None:
        header = tk.Frame(self, background=theme.c("accent"))
        header.pack(fill="x")
        tk.Label(header, text=_("首选项 / 设置"), background=theme.c("accent"),
                 foreground="white", font=("Microsoft YaHei UI", 14, "bold")
                 ).pack(anchor="w", padx=22, pady=(14, 4))
        tk.Label(header, text=_("调成自己顺手的用法"), background=theme.c("accent"),
                 foreground=theme.c("accent_soft"), font=APP_FONT
                 ).pack(anchor="w", padx=22, pady=(0, 12))

        body = ttk.Frame(self, padding=(22, 16, 22, 0))
        body.pack(fill="both", expand=True)

        language = ttk.LabelFrame(body, text=" " + _("界面语言") + " ",
                                  padding=(14, 10, 14, 12))
        language.pack(fill="x", pady=(0, 12))
        for code, name in i18n.LANGUAGES:      # 语言名用各自的写法，不翻译
            ttk.Radiobutton(language, text=name, value=code,
                            variable=self.language_var).pack(anchor="w", pady=2)
        ttk.Label(language, foreground=theme.c("hint"), font=APP_FONT,
                  wraplength=430, justify="left",
                  text=_("界面语言会立即切换（工程会先自动保存）。")
                  ).pack(anchor="w", pady=(6, 0))

        appearance = ttk.LabelFrame(body, text=" " + _("界面主题") + " ",
                                    padding=(14, 10, 14, 12))
        appearance.pack(fill="x", pady=(0, 12))
        ttk.Radiobutton(appearance, text=_("浅色（默认）"), value="light",
                        variable=self.theme_var).pack(anchor="w", pady=2)
        ttk.Radiobutton(appearance, text=_("深色"), value="dark",
                        variable=self.theme_var).pack(anchor="w", pady=2)
        ttk.Label(appearance, foreground=theme.c("hint"), font=APP_FONT,
                  wraplength=430, justify="left",
                  text=_("切换主题后界面会重新加载一次（工程会先自动保存）。")
                  ).pack(anchor="w", pady=(6, 0))

        habits = ttk.LabelFrame(body, text=" " + _("使用习惯") + " ",
                                padding=(14, 10, 14, 12))
        habits.pack(fill="x", pady=(0, 12))
        ttk.Checkbutton(habits, text=_("启动时显示欢迎页"), variable=self.welcome_var
                        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(habits, text=_("启动时自动打开上次打开的工程（跳过启动窗口）"),
                        variable=self.auto_last_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(habits, text=_("默认显示「安装效果预览」"), variable=self.preview_var
                        ).pack(anchor="w", pady=2)

        assoc_frame = ttk.LabelFrame(body, text=" " + _("文件关联") + " ",
                                     padding=(14, 10, 14, 12))
        assoc_frame.pack(fill="x", pady=(0, 12))
        self.assoc_status = ttk.Label(assoc_frame, foreground=theme.c("hint"),
                                      font=APP_FONT, wraplength=430, justify="left")
        self.assoc_status.pack(anchor="w")
        assoc_row = ttk.Frame(assoc_frame)
        assoc_row.pack(anchor="w", pady=(8, 0))
        ttk.Button(assoc_row, text=_("立即关联 / 修复"),
                   command=self._assoc_register).pack(side="left")
        ttk.Button(assoc_row, text=_("取消关联"),
                   command=self._assoc_unregister).pack(side="left", padx=(8, 0))
        self._refresh_assoc_status()

        cache = ttk.LabelFrame(body, text=" " + _("缓存 / 临时目录") + " ",
                               padding=(14, 10, 14, 12))
        cache.pack(fill="x", pady=(0, 12))
        cache_row = ttk.Frame(cache)
        cache_row.pack(fill="x")
        self.cache_var = tk.StringVar(value=self.settings.cache_dir or "")
        ttk.Entry(cache_row, textvariable=self.cache_var).pack(
            side="left", fill="x", expand=True)
        ttk.Button(cache_row, text=_("浏览…"), width=8,
                   command=self._browse_cache).pack(side="left", padx=(6, 0))
        ttk.Button(cache_row, text=_("用默认位置"), width=10,
                   command=lambda: self.cache_var.set("")).pack(side="left", padx=(4, 0))
        ttk.Label(cache, foreground=theme.c("hint"), font=APP_FONT,
                  wraplength=430, justify="left",
                  text=_("留空 = 软件目录下的 data\\work。\n"
                         "解开单文件工程、编译中间产物都放这里；换目录后下次打开工程时生效。\n"
                         "「用默认位置」只清掉自定义路径，不会删除文件。")
                  ).pack(anchor="w", pady=(6, 0))
        ttk.Button(cache, text=_("清空缓存文件…"),
                   command=self._clear_cache).pack(anchor="w", pady=(8, 0))

        reset = ttk.LabelFrame(body, text=" " + _("初始化") + " ",
                               padding=(14, 10, 14, 12))
        reset.pack(fill="x")
        ttk.Label(reset, foreground=theme.c("hint"), font=APP_FONT,
                  wraplength=430, justify="left",
                  text=_("恢复默认设置会清空「最近打开」记录，并把上面这些选项重置为出厂值。")
                  ).pack(anchor="w")
        ttk.Button(reset, text=_("恢复默认设置…"),
                   command=self._reset).pack(anchor="w", pady=(8, 0))

        footer = ttk.Frame(self, padding=(22, 16, 22, 16))
        footer.pack(fill="x")
        ttk.Button(footer, text=_("保存"), width=12, command=self._save).pack(side="right")
        ttk.Button(footer, text=_("取消"), width=10,
                   command=self._cancel).pack(side="right", padx=(0, 8))

    def _center(self, master) -> None:
        width = max(self.winfo_reqwidth(), 520)
        height = self.winfo_reqheight()
        if master is not None and master.winfo_viewable():
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = max(0, (self.winfo_screenheight() - height) // 2 - 60)
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    # -- 动作 ---------------------------------------------------------------

    def _refresh_assoc_status(self) -> None:
        text = {
            "ok": _("已关联到本程序（双击 .jianpack 即可打开）"),
            "stale": _("关联指向了别的位置，建议点「立即关联 / 修复」"),
            "missing": _("尚未关联，点「立即关联 / 修复」即可"),
        }.get(assoc.status(), "")
        if not getattr(sys, "frozen", False):
            text += "\n" + _("（当前是源码运行，关联会指向开发用的脚本）")
        self.assoc_status.configure(text=text)

    def _assoc_register(self) -> None:
        try:
            assoc.register()
        except OSError as exc:
            messagebox.showerror(_("设置文件关联失败"), str(exc), parent=self)
        self._refresh_assoc_status()

    def _assoc_unregister(self) -> None:
        try:
            assoc.unregister()
        except OSError:
            pass
        self._refresh_assoc_status()

    def _browse_cache(self) -> None:
        current = self.cache_var.get().strip()
        chosen = filedialog.askdirectory(
            parent=self, title=_("选择缓存目录"),
            initialdir=current if current and Path(current).is_dir() else str(paths.data_dir()))
        if chosen:
            self.cache_var.set(chosen)

    def _clear_cache(self) -> None:
        """删掉缓存目录里本软件产生的「临时工程」（跳过当前正在用的那个）。

        只删名字以 ``简包装-工程-`` 开头的目录，别的东西（用户自己放进来的）
        一律不动；当前打开的工程正在用的目录也跳过，免得删到自己在用的文件。
        """
        import shutil

        from ..core import container

        root = container.cache_root()
        active = None
        try:
            state = getattr(self.master, "app", None)
            if state is not None and state.project is not None:
                active = state.project.work_dir
        except Exception:  # noqa: BLE001 - 拿不到就当没有正在用的
            active = None
        if active is not None:
            active = Path(active).resolve()

        entries = []
        if root.is_dir():
            for entry in root.iterdir():
                try:
                    if not entry.is_dir() or not entry.name.startswith(container.WORK_PREFIX):
                        continue
                    if active is not None and entry.resolve() == active:
                        continue
                except OSError:
                    continue
                entries.append(entry)

        if not entries:
            messagebox.showinfo(_("清空缓存"), _("缓存里没有可清理的内容。"), parent=self)
            return

        total = 0
        for entry in entries:
            for path in entry.rglob("*"):
                try:
                    if path.is_file():
                        total += path.stat().st_size
                except OSError:
                    pass

        if not messagebox.askyesno(
                _("清空缓存"),
                _("将删除缓存目录里的 {n} 个临时工程，约释放 {size}。\n\n继续吗？").format(
                    n=len(entries), size=_size_text(total)),
                parent=self):
            return

        removed = 0
        for entry in entries:
            shutil.rmtree(entry, ignore_errors=True)
            if not entry.exists():
                removed += 1

        messagebox.showinfo(
            _("清空缓存"),
            _("已清理 {n} 项，约释放 {size}。").format(
                n=removed, size=_size_text(total)),
            parent=self)

    def _persist(self) -> bool:
        try:
            save_settings(self.settings)
            return True
        except PackError as exc:
            messagebox.showerror(_("保存设置失败"), str(exc), parent=self)
            return False

    def _save(self) -> None:
        old_theme = self.settings.theme
        old_language = self.settings.language
        self.settings.theme = "dark" if self.theme_var.get() == "dark" else "light"
        self.settings.language = i18n.normalize(self.language_var.get())
        self.settings.show_welcome = bool(self.welcome_var.get())
        self.settings.show_preview = bool(self.preview_var.get())
        self.settings.auto_open_last = bool(self.auto_last_var.get())
        self.settings.cache_dir = self.cache_var.get().strip()
        if not self._persist():
            return
        self.saved = True
        self.restart_needed = (self.settings.theme != old_theme
                               or self.settings.language != old_language)
        self.destroy()

    def _reset(self) -> None:
        if not messagebox.askyesno(
                _("恢复默认设置"),
                _("会清空「最近打开」记录，并把主题、欢迎页等选项恢复成默认值。\n\n确定继续吗？"),
                parent=self):
            return
        self.settings.reset()
        if not self._persist():
            return
        self.saved = True
        self.restart_needed = True
        self.reset_done = True
        self.destroy()

    def _cancel(self) -> None:
        self.destroy()
