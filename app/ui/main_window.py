"""主窗口：左侧步骤导航 + 右侧页面 + 底部状态栏。"""

from __future__ import annotations

import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import __version__
from ..core import assoc, demo
from ..core.errors import PackError
from ..core.project import load_project, reload_project
from ..core.settings import load_settings, save_settings
from ..core.versions import current_version_is_retired
from .. import i18n
from ..i18n import t as _, app_name
from . import resources
from .about_dialog import AboutDialog
from .build_panel import BuildPanel
from .pages.basic import BasicPage
from .pages.files import FilesPage
from .pages.install import InstallPage
from .pages.interface import InterfacePage
from .new_project_dialog import NewProjectDialog
from .preferences_dialog import PreferencesDialog
from .preview import PANEL_WIDTH, PreviewPanel
from .start_dialog import StartDialog
from .splash import Splash
from .state import AppState
from .tutorial import TutorialWindow
from .version_panel import VersionPanel
from .welcome_dialog import WelcomeDialog
from . import theme
from .widgets import APP_FONT, TITLE_FONT, set_enabled_tree

STEPS = (BasicPage, FilesPage, InstallPage, InterfacePage)


def project_file_types() -> list[tuple[str, str]]:
    from ..core.container import PROJECT_EXT

    return [(_("安装打包工程"), "*" + PROJECT_EXT), (_("所有文件"), "*.*")]


SIDEBAR_WIDTH = 470      # 收起预览时左栏的宽度（要放得下「版本迭代」面板）
CONTENT_WIDTH = 1000     # 编辑区希望保底的宽度
# 默认窗口高度：要让左栏的「安装效果预览」能以原尺寸（503 宽）完整显示
#（左栏现在是「版本迭代 + 预览 + 开始打包」三块，比原来更高）；
# 屏幕不够高时会在 _apply_preview 里自动收窄，预览再等比缩放兜底。
WINDOW_HEIGHT = 1200
WRAP_TEXT = 470          # 左栏提示文字的换行宽度

# 打开工程的加载窗：读得快就不弹（免得小工程「闪一下」像出 bug）；
# 一旦弹出来，就至少停留这么久，让用户看清这是什么窗口。
SPLASH_DELAY_MS = 350
SPLASH_MIN_MS = 800
# 版本操作（冻结/切换/删除大版本）的加载窗：延迟出现，出现后至少停留一会儿
VERSION_OP_MIN_MS = 500


class MainWindow(tk.Tk):
    def __init__(self, project_path: str | Path | None = None,
                 welcome: bool = False) -> None:
        super().__init__()

        # 必须紧跟在 Tk 初始化之后：Tk 创建根窗口时会立刻把它画出来，
        # 晚一步再 withdraw 的话，用户会先看见主窗口闪一下，像程序坏了。
        # 等用户在启动窗口里选定了工程，再决定要不要显示。
        self.withdraw()

        self.app = AppState()
        self.settings = load_settings()
        # 语言和主题都要在建界面之前定好，之后创建的控件才用得上
        i18n.set_language(self.settings.language)
        theme.activate(self, self.settings.theme)
        resources.apply_icon(self)      # 设成默认后，各个子窗口也会用同一个图标
        self._welcome_enabled = bool(welcome)
        self._preferences: PreferencesDialog | None = None
        # 改主题 / 初始化设置后用它让 run() 重建一个窗口
        self._restart_requested = False
        self._restart_path: str | None = None
        self._restart_welcome = False
        self._pages: list = []
        self._index = 0
        self._preview_job = None
        self._jobs: set[str] = set()      # 其它延时动作，销毁时要一并取消
        self._load_job = None             # 后台读工程时的轮询句柄
        self._version_job = None          # 后台跑版本操作时的轮询句柄
        self._version_busy = False        # 版本操作进行中（期间冻结界面/预览）
        self._splash = None               # 当前的加载提示窗口
        self._keep_tutorial = False       # 从欢迎页进来的话，启动窗口这次不抢输入
        self._preview_shown = False
        self._tutorial: TutorialWindow | None = None

        self.title(app_name())
        self.minsize(980, 680)
        self._center(1120, 780)
        self.app.subscribe(self._on_state_change)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_menu()
        self._build_layout()
        self._bind_keys()
        self._apply_preview(first=True)

        if project_path:
            # 双击工程文件 / 带路径启动：后台读取，期间显示带图标的启动页
            self._load_async(project_path, with_icon=True,
                             on_done=self._after_startup_open,
                             on_fail=self._show_start)
        elif self._welcome_enabled and self.settings.auto_open_last:
            recent = self._first_existing_recent()
            if recent:
                self._load_async(recent, with_icon=True,
                                 on_done=self._after_startup_open,
                                 on_fail=self._show_start)
            else:
                self._later(60, self._startup_splash)
        else:
            # 直接打开软件：先亮一下带图标的启动页，再进欢迎页 / 启动窗口
            self._later(60, self._startup_splash)

    def _after_startup_open(self) -> None:
        self._show_window()
        self._welcome_after_open()

    def _first_existing_recent(self) -> str | None:
        for path, exists in self.settings.existing():
            if exists:
                return path
        return None

    def _startup_splash(self) -> None:
        """直接打开软件时的启动页（不加载工程，很快，所以只停留一小会儿）。"""
        splash = Splash(self, with_icon=True, status=_("正在启动…"))
        splash.set_indeterminate()
        self._splash = splash

        def go() -> None:
            splash.close()
            if self._splash is splash:
                self._splash = None
            self._show_start()

        self._later(450, go)

    def _welcome_turn(self) -> tuple[bool, bool]:
        """弹一次欢迎页（如果开着）。

        返回 ``(要不要打开教程, 要不要重建界面)`` —— 在欢迎页点了「中/en」
        时语言变了，得让 :func:`run` 重建一个窗口。
        """
        if not self._welcome_enabled or not self.settings.show_welcome:
            return False, False
        dialog = WelcomeDialog(self, self.settings)
        self.wait_window(dialog)
        if dialog.switch_language:
            self._switch_language(dialog.switch_language)
            return False, True
        return dialog.open_tutorial, False

    def _switch_language(self, lang: str) -> None:
        """在欢迎页里切中/英文：存下来并重建界面（欢迎页保留，用新语言再出现）。"""
        self.settings.language = i18n.normalize(lang)
        try:
            save_settings(self.settings)
        except PackError:
            pass
        self._restart(keep_welcome=True)

    def _welcome_after_open(self) -> None:
        """主窗口显示出来之后再弹欢迎页，免得被启动窗口的 grab 挡住。"""
        def show() -> None:
            if not self.winfo_exists():
                return
            want_tutorial, restart = self._welcome_turn()
            if restart:
                return
            if want_tutorial:
                self.open_tutorial()
        self._later(120, show)

    def _show_start(self) -> None:
        """欢迎页 + 启动选择窗口。选到工程为止；取消就直接退出。"""
        # 欢迎页里点了「打开教程」的话：教程和启动窗口一起开着，
        # 启动窗口这次不抢输入，方便新手边对照教程边操作。
        # 点了「中/en」的话：本窗口会被销毁，由 run() 用新语言重建。
        want_tutorial, restart = self._welcome_turn()
        if restart:
            return
        self._keep_tutorial = want_tutorial
        if want_tutorial:
            self.open_tutorial()
        self._prompt_start()

    def _prompt_start(self) -> None:
        """弹一次启动选择窗口；用户选了工程就异步打开，取消就退出。"""
        if self.app.project is not None:
            self._reveal_main()
            return
        self.withdraw()
        dialog = StartDialog(self, self.settings, modal=not self._keep_tutorial)
        try:
            self.wait_window(dialog)
        except tk.TclError:
            pass              # 对话框在等待期间被销毁（极端情况），照常读它的结果
        choice = dialog.result
        if choice is None:
            self.destroy()
            return
        kind, value = choice
        if kind == "new":
            # 新建要弹文件对话框，父窗口必须是可见的，否则对话框可能不出现
            self._show_window()
            self.update_idletasks()
            self.new_project()
            if self.app.project is None:
                self._prompt_start()          # 取消 / 失败：回到启动窗口
            else:
                self._reveal_main()
        elif value:
            # 打开已有工程：**先不显示主窗口**（否则读条时背景会露出零散的空状态，
            # 看着像 bug）；读完后 on_done 再显示。
            self._load_async(value, with_icon=False,
                             on_done=self._reveal_main,
                             on_fail=self._prompt_start)

    def _reveal_main(self) -> None:
        self._show_window()
        self.lift()
        self.focus_force()

    def load_path(self, path: str | Path) -> bool:
        """同步打开一个工程文件。失败时弹提示并返回 False。"""
        try:
            self.app.load(path)
        except (PackError, OSError) as exc:
            messagebox.showerror(_("打开失败"), str(exc), parent=self)
            return False
        self._apply_project(path)
        return True

    def _apply_project(self, path: str | Path) -> None:
        """工程读好之后的公共收尾：记最近、重建页面、选到第 1 步。"""
        self._remember(path)
        self._rebuild_pages()
        self._select_step(0)
        self.version_panel.refresh()
        self._apply_version_gate()
        if self._is_demo():
            messagebox.showinfo(
                _("演示项目"),
                _("这是随软件自带的演示项目，只用来了解软件怎么用，不能保存修改。\n\n"
                  "想基于它做一个自己的工程，请点「文件 → 新建工程」。"),
                parent=self)

    # -- 后台读取工程（带加载提示）------------------------------------------

    def _load_async(self, path, *, with_icon: bool,
                    on_done=None, on_fail=None) -> None:
        """在后台线程里读工程。

        ``with_icon`` 决定加载窗是带图标的启动页还是简化版；真正的解压/读取
        在后台线程里做，进度通过队列回到主线程刷新。

        加载窗**延迟显示**：读得快（小工程）就根本不弹，避免「闪一下就没了」
        看起来像 bug；真读得慢才显示，且显示后至少停留 ``SPLASH_MIN_MS``。
        """
        if self._load_job is not None:
            return                              # 已经有一个在读了
        path = str(path)
        splash = Splash(self, with_icon=with_icon, show=False,
                        status=_("正在打开工程…"), file_name=Path(path).name)
        self._splash = splash
        results: dict = {}
        shown_at: dict = {"t": 0.0}
        q: queue.Queue = queue.Queue()

        def report(done: int, total: int, name: str) -> None:
            q.put((done, total, name))          # 只入队，不直接碰 Tk

        def work() -> None:
            try:
                results["project"] = load_project(path, progress=report)
            except BaseException as exc:         # noqa: BLE001 - 原样带回主线程
                results["error"] = exc
            finally:
                q.put(None)

        threading.Thread(target=work, daemon=True).start()

        def show_if_still_loading() -> None:
            if results:                          # 已经读完，不用弹了
                return
            splash.show()
            shown_at["t"] = time.monotonic()

        show_job = self._later(SPLASH_DELAY_MS, show_if_still_loading)

        def poll() -> None:
            self._load_job = None
            if not self.winfo_exists():
                return
            try:
                while True:
                    item = q.get_nowait()
                    if item is None:
                        self._after_load(path, results, splash, on_done, on_fail,
                                         show_job, shown_at)
                        return
                    if splash.is_shown:
                        splash.set_progress(*item)
            except queue.Empty:
                pass
            self._load_job = self.after(40, poll)

        self._load_job = self.after(40, poll)

    def _after_load(self, path, results, splash, on_done, on_fail,
                    show_job, shown_at) -> None:
        """读完后的收尾：已经显示过的加载窗要保证停留够久，别一闪而过。"""
        try:
            self.after_cancel(show_job)
        except tk.TclError:
            pass
        self._jobs.discard(show_job)
        if splash.is_shown:
            elapsed = (time.monotonic() - shown_at["t"]) * 1000
            delay = int(max(0, SPLASH_MIN_MS - elapsed))
            if delay > 0:
                self._later(
                    delay,
                    lambda: self._finish_load(path, results, splash, on_done, on_fail))
                return
        self._finish_load(path, results, splash, on_done, on_fail)

    def _finish_load(self, path, results, splash, on_done, on_fail) -> None:
        splash.close()
        if self._splash is splash:
            self._splash = None
        if "error" in results:
            exc = results["error"]
            text = str(exc) if isinstance(exc, (PackError, OSError)) else repr(exc)
            messagebox.showerror(_("打开失败"), text, parent=self)
            if on_fail is not None:
                on_fail()
            return
        self.app.adopt(results["project"])
        self._apply_project(path)
        if on_done is not None:
            on_done()

    def _is_demo(self) -> bool:
        """当前打开的工程是不是自带的演示项目（只读）。"""
        if self.app.project is None:
            return False
        return demo.is_demo(self.app.project.source_path)

    def after_version_change(self, reload: bool = True, clear_payload: bool = False) -> None:
        """版本切换 / 新建版本之后：重建界面。

        ``reload=False`` 用于"新建版本"：这时内存里的工程才是最新的（版本号刚改过），
        磁盘上的 project.json 还没写；重载会把刚设好的版本号冲掉。

        ``reload=True`` 用于"切换版本"：磁盘上的内容已经被换成目标版本，
        内存模型是旧的，必须原地重载；``clear_payload=True`` 表示目标版本是
        「仅配置」，要把"打包内容"清空，不能留着上一版的文件冒充。

        这里**不能**用 ``load_project``：切换已经改过 ``base_dir`` 里的内容，
        再按磁盘上的旧容器解压一遍会把改动盖回去。
        """
        project = self.app.project
        if project is None:
            return
        if reload:
            try:
                new = reload_project(project)
            except (PackError, OSError) as exc:
                messagebox.showerror(_("版本操作失败"), str(exc), parent=self)
                return
            if clear_payload and new.files.items:
                new.files.items = []
            self.app.adopt(new)
        # 落盘已经在后台线程里做完了，这里只刷新界面
        self.app.dirty = False
        self._rebuild_pages()
        self._select_step(0)
        self.version_panel.refresh()
        self._apply_version_gate()
        self._sync_title()
        self._schedule_preview()

    # -- 耗时操作（版本冻结 / 切换等）在后台跑，配一个延迟加载窗 ---------------

    def run_background(self, work, on_done, *, status: str = "", file_name: str = "") -> None:
        """在后台线程执行 ``work()``，同时弹一个"加载窗"。

        - 加载窗**延迟出现**：操作很快（小工程）就根本不弹，避免闪一下像 bug；
        - 一旦出现，就至少停留一小会儿，让用户看清；
        - 完成后回到主线程调用 ``on_done(value, error)``。
        """
        if self._version_job is not None:
            return                      # 已经有一个在跑了
        self._version_busy = True
        splash = Splash(self, with_icon=True, show=False, status=status,
                        file_name=file_name)
        self._splash = splash
        result: dict = {}
        shown_at = {"t": 0.0}

        def runner() -> None:
            try:
                result["value"] = work()
            except BaseException as exc:      # noqa: BLE001 - 原样带回主线程
                result["error"] = exc

        threading.Thread(target=runner, daemon=True).start()

        def show_if_slow() -> None:
            if result:
                return
            splash.show()
            shown_at["t"] = time.monotonic()

        show_job = self._later(SPLASH_DELAY_MS, show_if_slow)

        def poll() -> None:
            self._version_job = None
            if not self.winfo_exists():
                return
            if not result:
                self._version_job = self.after(40, poll)
                return
            try:
                self.after_cancel(show_job)
            except tk.TclError:
                pass
            self._jobs.discard(show_job)
            delay = 0
            if splash.is_shown:
                elapsed = (time.monotonic() - shown_at["t"]) * 1000
                delay = int(max(0, VERSION_OP_MIN_MS - elapsed))

            def finish() -> None:
                splash.close()
                if self._splash is splash:
                    self._splash = None
                self._version_busy = False
                on_done(result.get("value"), result.get("error"))

            if delay > 0:
                self._later(delay, finish)
            else:
                finish()

        self._version_job = self.after(40, poll)

    # -- 空工程 / 已淘汰版本 的界面开关 --------------------------------------
    def _apply_version_gate(self) -> None:
        """按当前版本的状态切换界面：

        - 空工程（还没建版本）：只显示左侧的「版本迭代 / 创建」；
        - 当前版本「已淘汰」：把「开始打包」面板换成一句说明；
        - 其余：正常显示。
        """
        project = self.app.project
        blank = bool(project is not None and self.version_panel.is_create_mode())
        retired = bool(project is not None and not blank
                       and current_version_is_retired(project))
        state = "blank" if blank else ("retired" if retired else "full")
        if state == getattr(self, "_gate_state", None):
            return
        self._gate_state = state
        self._blank_mode = blank

        for widget in (self.steps_bar, self.steps_sep, self.container,
                       self.preview_panel, self.build_panel, self.build_retired,
                       self.placeholder):
            widget.pack_forget()

        if state == "blank":
            self.placeholder.pack(fill="both", expand=True)
            return
        self.steps_bar.pack(side="top", fill="x")
        self.steps_sep.pack(fill="x", padx=20)
        self.container.pack(fill="both", expand=True)
        if state == "retired":
            self.build_retired.pack(side="bottom", fill="x", padx=12, pady=(4, 8))
        else:
            self.build_panel.pack(side="bottom", fill="x", padx=12, pady=(4, 8))
        self.preview_panel.pack(fill="both", expand=True, pady=(8, 0))

    def _remember(self, path: str | Path) -> None:
        """记进「最近打开」列表。存不下来也不影响使用。"""
        self.settings.remember(path)
        try:
            save_settings(self.settings)
        except PackError:
            pass

    # -- 界面搭建 -----------------------------------------------------------

    def _center(self, width: int = 1120, height: int = 780) -> None:
        """把窗口摆到屏幕中间。

        尺寸要显式传进来，不能靠 ``winfo_width()`` 读——窗口还处于隐藏状态时
        它返回的是 1，会把窗口设成 1×1。
        """
        x = (self.winfo_screenwidth() - width) // 2
        y = max(0, (self.winfo_screenheight() - height) // 2 - 20)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _later(self, ms: int, callback) -> str:
        """安排一个延时动作，并登记下来，窗口销毁时一并取消。返回这个 after 句柄。

        直接 ``self.after(...)`` 的话，窗口关掉之后回调仍会触发，Tk 找不到
        已经销毁的控件就会报 ``invalid command name ...``；这里顺带在真正执行
        前再确认一次窗口还在。
        """
        job: str = ""

        def run() -> None:
            self._jobs.discard(job)
            try:
                if self.winfo_exists():
                    callback()
            except tk.TclError:
                pass

        job = self.after(ms, run)
        self._jobs.add(job)
        return job

    @staticmethod
    def _shortcut(action, keycode: int | None = None):
        """把动作包成按键回调，顺便挡掉「中文输入法误报的功能键」。

        Windows 上 Tk 处理输入法合成时有个老问题（CPython issue #125349）：
        在中文输入法里敲字母再按回车确认，Tk 会**额外**发出一个 keysym 被错报
        成 F1 / F5 / F3 的假事件。不拦的话：输入 "p"+回车 会弹出「使用教程」。

        真假事件的判据（两个都查，兼容性最好）：
        - 真的功能键 ``char`` 是空的；假事件的 ``char`` 是刚敲的那个字母；
        - 真功能键的**虚拟键码**就是 F1/F5 自己（112 / 116）；假事件带的是字母的键码。

        注意：**不能**用 ``send_event`` 判断 —— 实测真按键在某些环境下
        ``send_event`` 也是真，用它会把真的 F 键一起挡掉。
        """
        def handler(event) -> None:
            if getattr(event, "char", ""):
                return
            if keycode and getattr(event, "keycode", 0) not in (0, keycode):
                return
            action()
        return handler

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=_("新建工程…"), accelerator="Ctrl+N", command=self.new_project)
        file_menu.add_command(label=_("打开工程…"), accelerator="Ctrl+O", command=self.open_project)
        file_menu.add_separator()
        file_menu.add_command(label=_("保存"), accelerator="Ctrl+S", command=self.save)
        file_menu.add_command(label=_("另存为…"), accelerator="Ctrl+Shift+S", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label=_("退出"), command=self._on_close)
        menubar.add_cascade(label=_("文件"), menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label=_("校验工程"), accelerator="F5", command=self.validate_project)
        tools_menu.add_command(label=_("打开输出目录"), command=self._open_output)
        menubar.add_cascade(label=_("工具"), menu=tools_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        self.preview_var = tk.BooleanVar(value=self.settings.show_preview)
        view_menu.add_checkbutton(label=_("显示安装预览"), accelerator="Ctrl+P",
                                  variable=self.preview_var, command=self.toggle_preview)
        menubar.add_cascade(label=_("视图"), menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=_("教程"), accelerator="F1", command=self.open_tutorial)
        help_menu.add_separator()
        help_menu.add_command(label=_("关于"), command=self._about)
        menubar.add_cascade(label=_("帮助"), menu=help_menu)

        # 「首选项/设置」直接作为顶级菜单项，点了就弹设置窗口
        menubar.add_command(label=_("首选项/设置"), accelerator="Ctrl+,",
                            command=self.open_preferences)

        self.configure(menu=menubar)

    def _build_layout(self) -> None:
        self.status = ttk.Label(self, anchor="w", padding=(12, 5),
                                foreground=theme.c("hint"), font=APP_FONT)
        self.status.pack(side="bottom", fill="x")

        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        # 左栏（从上到下）：版本迭代 / 安装效果预览 / 开始打包。
        # 预览放左栏而不是最右边，是为了让编辑区能吃掉全部剩余宽度。
        self.left_column = ttk.Frame(outer, width=PANEL_WIDTH)
        self.left_column.pack(side="left", fill="y")
        self.left_column.pack_propagate(False)

        self.version_panel = VersionPanel(self.left_column, self.app)
        self.version_panel.window = self
        self.version_panel.pack(side="top", fill="x", padx=12, pady=(12, 2))

        ttk.Separator(self.left_column, orient="horizontal").pack(
            side="top", fill="x", padx=12, pady=(8, 0))

        # 「开始打包」常驻左栏底部：按钮 + 日志，随时能点
        self.build_panel = BuildPanel(self.left_column, self.app)
        self.build_panel.window = self
        self.build_panel.pack(side="bottom", fill="x", padx=12, pady=(4, 8))

        # 当前版本「已淘汰」时，用它顶替「开始打包」面板（并说明原因）
        self.build_retired = ttk.Frame(self.left_column)
        ttk.Label(self.build_retired, text=_("开始打包"), font=TITLE_FONT,
                  foreground=theme.c("hint")).pack(anchor="w", pady=(0, 6))
        ttk.Label(self.build_retired, foreground=theme.c("hint"), justify="left",
                  wraplength=WRAP_TEXT, font=APP_FONT,
                  text=_("当前版本已被淘汰，不能再打包了。\n"
                         "想继续更新，请在左上角的「版本迭代 / 切换」里"
                         "切换到最新的两个版本。")).pack(anchor="w")

        self.preview_panel = PreviewPanel(self.left_column, self.app)
        self.preview_panel.pack(fill="both", expand=True, pady=(8, 6))

        self.content_area = ttk.Frame(outer)
        self.content_area.pack(side="left", fill="both", expand=True)

        # 顶部：打包步骤（两列：名称 + 一句话说明）+ 上一步/下一步（挪到右边）
        self.steps_bar = ttk.Frame(self.content_area, padding=(20, 14, 20, 8))
        self.steps_bar.pack(side="top", fill="x")

        nav = ttk.Frame(self.steps_bar)
        nav.pack(side="right", anchor="n", padx=(14, 0), pady=(30, 0))
        self.nav = nav
        self.back_button = ttk.Button(nav, text=_("< 上一步"), width=12, command=self.prev_step)
        self.back_button.pack()
        self.next_button = ttk.Button(nav, text=_("下一步 >"), width=12, command=self.next_step)
        self.next_button.pack(pady=(6, 0))

        steps = ttk.Frame(self.steps_bar)
        steps.pack(side="left", fill="x", expand=True)
        self.steps = steps
        ttk.Label(steps, text=_("打包步骤"), font=TITLE_FONT,
                  foreground=theme.c("accent")).pack(anchor="w")
        self.step_list = ttk.Treeview(steps, columns=("step", "desc"), show="",
                                      selectmode="browse", height=len(STEPS))
        self.step_list.column("step", width=160, anchor="w", stretch=False)
        self.step_list.column("desc", width=420, anchor="w")
        self.step_list.pack(fill="x", pady=(4, 0))
        self.step_list.bind("<<TreeviewSelect>>", self._on_step_click)

        self.steps_sep = ttk.Separator(self.content_area, orient="horizontal")
        self.steps_sep.pack(fill="x", padx=20)

        self.container = ttk.Frame(self.content_area)
        self.container.pack(fill="both", expand=True)
        self._gate_state = None

        # 空工程（还没建第一个版本）时显示的提示页
        self.placeholder = ttk.Frame(self.content_area, padding=(40, 70))
        ttk.Label(self.placeholder, text=_("这个工程还没有任何版本"),
                  font=TITLE_FONT, foreground=theme.c("accent")).pack()
        ttk.Label(self.placeholder, foreground=theme.c("hint"), font=APP_FONT,
                  justify="center", wraplength=560,
                  text=_("请在左上角「版本迭代 / 创建」里点「新建版本…」，"
                         "创建第一个版本后，完整界面就会出现。")).pack(pady=(10, 0))
        self._blank_mode = False

    def _bind_keys(self) -> None:
        self.bind("<Control-n>", lambda _e: self.new_project())
        self.bind("<Control-o>", lambda _e: self.open_project())
        self.bind("<Control-s>", lambda _e: self.save())
        self.bind("<Control-S>", lambda _e: self.save_as())
        self.bind("<F5>", self._shortcut(self.validate_project, 116))
        self.bind("<F1>", self._shortcut(self.open_tutorial, 112))
        self.bind("<Control-comma>", lambda _e: self.open_preferences())
        self.bind("<Control-p>", lambda _e: self._toggle_preview_from_key())
        self.bind("<Alt-Left>", lambda _e: self.prev_step())
        self.bind("<Alt-Right>", lambda _e: self.next_step())

    # -- 页面 -----------------------------------------------------------------

    def _rebuild_pages(self) -> None:
        for page in self._pages:
            page.destroy()
        self._pages = []
        self._index = 0
        self.app.context = {"step": 0, "subtab": ""}

        for cls in STEPS:
            page = cls(self.container, self.app)
            page.window = self
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._pages.append(page)

        self.step_list.delete(*self.step_list.get_children())
        for index, cls in enumerate(STEPS):
            self.step_list.insert(
                "", "end", iid=str(index),
                values=(f"{index + 1}. {_(cls.title)}", _(getattr(cls, "description", ""))))

    def _select_step(self, index: int) -> None:
        if not self._pages:
            return
        index = max(0, min(index, len(self._pages) - 1))
        if self._pages[self._index] is not None and index != self._index:
            self._pages[self._index].flush()

        self._index = index
        page = self._pages[index]
        page.on_enter()
        page.tkraise()

        self.app.context["step"] = index
        self._follow_preview(index)

        self.step_list.selection_set(str(index))
        self.step_list.see(str(index))

        self.back_button.state(["!disabled"] if index > 0 else ["disabled"])
        self.next_button.state(["disabled"] if index >= len(self._pages) - 1 else ["!disabled"])
        self._sync_title()

    def _on_step_click(self, _event=None) -> None:
        if self.editing_locked:
            current = str(self._index)
            if self.step_list.selection() != (current,):
                self.step_list.selection_set(current)
            return
        selection = self.step_list.selection()
        if selection and int(selection[0]) != self._index:
            self._select_step(int(selection[0]))

    def prev_step(self) -> None:
        if self.editing_locked:
            return
        self._select_step(self._index - 1)

    def next_step(self) -> None:
        if self.editing_locked:
            return
        self._select_step(self._index + 1)

    # -- 打包期间锁定编辑区 --------------------------------------------------

    @property
    def editing_locked(self) -> bool:
        return getattr(self, "_editing_locked", False)

    def set_editing_enabled(self, enabled: bool) -> None:
        """打包 / 校验期间锁住编辑区和步骤切换，避免用户在后台干活时改数据。"""
        self._editing_locked = not enabled
        for page in self._pages:
            set_enabled_tree(page.form, enabled)
        state = "!disabled" if enabled else "disabled"
        for button in (self.back_button, self.next_button):
            try:
                button.state([state])
            except tk.TclError:
                pass
        try:
            self.version_panel.refresh_enabled()
        except (tk.TclError, AttributeError):
            pass
        if enabled:
            # 解锁会把所有控件都启用，这里让各页按自己的联动规则重刷一遍，
            # 否则「父项没勾 → 子项变灰」这类状态会被一起解除。
            with self.app.quiet():
                for page in self._pages:
                    page.on_enter()

    def flush_all(self) -> None:
        for page in self._pages:
            page.flush()

    # -- 标题与状态栏 --------------------------------------------------------

    def _sync_title(self) -> None:
        if self.app.project is None:
            self.title(app_name())
            return
        is_demo = self._is_demo()
        # 标题里的项目名**只跟工程文件名**走（改里面的应用名不影响它）
        file_name = self.app.project.source_path.stem or _("未命名工程")
        mark = "" if is_demo else (" *" if self.app.dirty else "")
        version = self.app.project.app.version
        title = f"{app_name()}--{_('当前项目：')}{file_name}{mark}"
        if version:
            title += f"    {_('打开版本：')}{version}"
        self.title(title)

        path = self.app.project.source_path
        if is_demo:
            state = _("演示项目（只读，不能保存）")
        else:
            state = _("有未保存的改动") if self.app.dirty else _("已保存")
        self.status.configure(
            text=_("工程：{path}    （{state}）").format(path=path, state=state))

    # -- 实时预览 -----------------------------------------------------------

    def _on_state_change(self) -> None:
        self._sync_title()
        self._schedule_preview()

    def _schedule_preview(self) -> None:
        """任何改动都排队刷新预览；连续输入时只在停下来之后画一次。"""
        if self._version_busy:
            return                      # 版本操作进行中，别去碰正在搬动的文件
        if self.app.project is not None:
            try:
                # 「占用」那一列也让它在后台顺手更新一下
                self.version_panel.schedule_size_refresh(600)
            except (tk.TclError, AttributeError):
                pass
        if not self.settings.show_preview or self.app.project is None:
            return
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(200, self._update_preview)

    def _update_preview(self) -> None:
        self._preview_job = None
        if self._version_busy:
            return
        if self.app.project is None or not self.settings.show_preview:
            return
        # 控件里的最新值要先收回模型，预览读的才是当前内容
        with self.app.quiet():
            self.flush_all()
        # 子标签可能刚换过（第 4 步里切页），先让预览跟上位置
        self.preview_panel.follow(int(self.app.context.get("step", 0)),
                                  str(self.app.context.get("subtab", "")))
        self.preview_panel.refresh()

    def _follow_preview(self, step: int) -> None:
        if not self.settings.show_preview:
            return
        self.preview_panel.follow(step, str(self.app.context.get("subtab", "")))
        self.preview_panel.refresh()

    def _toggle_preview_from_key(self) -> None:
        self.preview_var.set(not self.settings.show_preview)
        self.toggle_preview()

    def _show_window(self) -> None:
        """显示主窗口。

        最大化 / 还原交给系统标题栏（双击标题栏、Win+↑ 都可以），不再拦。
        默认尺寸和位置仍由 :meth:`_apply_preview` 决定，不受影响。
        """
        self.deiconify()

    def toggle_preview(self, show: bool | None = None) -> None:
        if show is None:
            show = bool(self.preview_var.get())
        self.settings.show_preview = bool(show)
        try:
            save_settings(self.settings)
        except PackError:
            pass
        self._apply_preview()

    def _apply_preview(self, first: bool = False) -> None:
        """显示 / 隐藏预览，并据此调整左栏和窗口的宽度。"""
        show = self.settings.show_preview

        if show:
            if not self._preview_shown and self._gate_state != "blank":
                self.preview_panel.pack(fill="both", expand=True, pady=(8, 0))
                self._preview_shown = True
            self.preview_panel.refresh()
        elif self._preview_shown:
            self.preview_panel.pack_forget()
            self._preview_shown = False

        left = PANEL_WIDTH if show else SIDEBAR_WIDTH
        self.left_column.configure(width=left)

        if self.preview_var.get() != show:
            self.preview_var.set(show)

        width = min(left + CONTENT_WIDTH, max(1000, self.winfo_screenwidth() - 80))
        self.minsize(min(left + 820, width), 680)
        # 高度按「能完整显示预览」来，屏幕放不下再收窄（预览会等比缩放兜底）
        height = min(WINDOW_HEIGHT, max(700, self.winfo_screenheight() - 80))

        # 最大化时**不要**再设置 geometry：那会把窗口从最大化拽回普通大小，
        # 用户一切换预览（Ctrl+P）或改设置就会「莫名弹回小窗」。
        # 最大化下只需调整左栏宽度，其余交给系统，窗口才能一直铺满屏幕。
        try:
            maximized = self.state() == "zoomed"
        except tk.TclError:
            maximized = False
        if maximized:
            return

        if first:
            x = (self.winfo_screenwidth() - width) // 2
            y = max(0, (self.winfo_screenheight() - height) // 2 - 20)
        else:
            x, y = max(0, self.winfo_x()), max(0, self.winfo_y())
        self.geometry(f"{width}x{height}+{x}+{y}")

    # -- 文件操作 ------------------------------------------------------------

    def new_project(self) -> None:
        if not self._confirm_discard():
            return

        dialog = NewProjectDialog(self, self.settings)
        self.wait_window(dialog)
        info = dialog.result
        if info is None:
            return
        project_file, parent_dir = info

        self.app.new_project(project_file)
        try:
            self.app.save()          # 先落盘，工程文件夹才算是完整的
        except (PackError, OSError) as exc:
            messagebox.showerror(_("保存失败"), str(exc), parent=self)
            return

        self.settings.new_project_dir = parent_dir
        self._remember(project_file)
        self._rebuild_pages()
        self._select_step(0)
        self.version_panel.refresh()
        self._apply_version_gate()

    def open_project(self) -> None:
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(parent=self, title=_("打开工程"),
                                          filetypes=project_file_types())
        if not path:
            return
        # 软件里打开工程：简化版加载窗（不带图标）
        self._load_async(path, with_icon=False)

    def _refuse_demo_save(self) -> bool:
        """演示项目不能保存；顺便问一句要不要新建工程。返回 True 表示已拦下。"""
        if not self._is_demo():
            return False
        if messagebox.askyesno(
                _("演示项目不能保存"),
                _("这是随软件自带的演示项目，不能保存修改。\n\n要新建一个自己的工程吗？"),
                parent=self):
            self.new_project()
        return True

    def save(self) -> None:
        if self.app.project is None:
            return
        if self._refuse_demo_save():
            return
        self.flush_all()
        self.status.configure(text=_("正在保存工程…"))
        self.update_idletasks()
        try:
            self.app.save()
        except PackError as exc:
            messagebox.showerror(_("保存失败"), str(exc), parent=self)
            return
        except OSError as exc:
            messagebox.showerror(_("保存失败"), str(exc), parent=self)
            return
        self._remember(self.app.project.source_path)
        self.status.configure(text=_("已保存到 {path}").format(path=self.app.project.source_path))

    def save_as(self) -> None:
        if self.app.project is None:
            return
        if self._refuse_demo_save():
            return
        self.flush_all()
        path = filedialog.asksaveasfilename(parent=self, title=_("另存为"),
                                            defaultextension=".jianpack",
                                            filetypes=project_file_types(),
                                            initialfile=self.app.project.source_path.name)
        if not path:
            return
        # 另存为统一产出「单个 .jianpack」文件：不管原来是文件夹工程还是单文件工程，
        # 都能得到一个自包含、可直接发给别人的文件。
        try:
            self.app.save(path, container_mode=True)
        except (PackError, OSError) as exc:
            messagebox.showerror(_("保存失败"), str(exc), parent=self)
            return
        self._remember(self.app.project.source_path)
        self._sync_title()

    def validate_project(self) -> None:
        """校验工程（F5 / 菜单「工具 → 校验工程」）。

        打包动作已经搬到左栏常驻的「开始打包」面板，这里直接走它的
        「校验工程」逻辑；结论输出在面板的日志里（有错会弹提示）。
        """
        self.build_panel.run("validate")

    def _open_output(self) -> None:
        for page in self._pages:
            if hasattr(page, "open_output"):
                page.open_output()
                return

    def _confirm_discard(self) -> bool:
        """有未保存改动时问一句。返回 False 表示用户取消了操作。"""
        if self.app.project is None or not self.app.dirty:
            return True
        if self._is_demo():
            return True          # 演示项目本来就不保存，直接继续
        name = self.app.project.project_name or self.app.project.source_path.name
        answer = messagebox.askyesnocancel(
            _("还有未保存的改动"),
            _("工程「{name}」有未保存的改动，要先保存吗？").format(name=name),
            parent=self)
        if answer is None:
            return False
        if answer:
            self.save()
            return not self.app.dirty
        return True

    def _on_close(self) -> None:
        if self._confirm_discard():
            self.destroy()

    def open_tutorial(self) -> TutorialWindow:
        """打开「使用教程」窗口。

        非模态：不抢主窗口焦点、也不阻塞操作。已经开着就把它提到前面，
        避免点一次开一个。
        """
        existing = self._tutorial
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return existing

        window = TutorialWindow(self)
        self._tutorial = window
        return window

    def open_preferences(self) -> None:
        """打开「首选项 / 设置」窗口。"""
        existing = self._preferences
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return

        dialog = PreferencesDialog(self, self.settings)
        self._preferences = dialog
        self.wait_window(dialog)
        if not dialog.saved:
            return

        # 预览的显隐可以立刻生效
        self.preview_var.set(self.settings.show_preview)
        self._apply_preview()

        if dialog.restart_needed:
            self._restart()

    def _restart(self, keep_welcome: bool = False) -> None:
        """按新设置重建整个界面（换主题 / 换语言用）。

        主题或语言变了就得让控件按新配色 / 新文案重新创建。工程会先保存，
        然后由 :func:`run` 重新建窗口。``keep_welcome`` 为真时重建后仍弹欢迎页
        （欢迎页里切语言就是这种）。
        """
        path: str | None = None
        if self.app.project is not None:
            self.flush_all()
            if not self._is_demo():          # 演示项目不保存，直接按新设置重建
                try:
                    self.app.save()
                except (PackError, OSError) as exc:
                    messagebox.showerror(
                        _("保存失败"),
                        _("切换界面前需要先保存工程，但保存失败了：\n{exc}\n\n"
                          "设置已经记下了，下次打开软件时生效。").format(exc=exc),
                        parent=self)
                    return
            path = str(self.app.project.source_path)

        self._restart_requested = True
        self._restart_path = path
        self._restart_welcome = keep_welcome
        self.destroy()

    def destroy(self) -> None:
        # 关窗口前把排队中的回调全部取消掉，免得控件没了之后回调再触发
        for job in list(self._jobs):
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._jobs.clear()
        if self._load_job is not None:
            try:
                self.after_cancel(self._load_job)
            except tk.TclError:
                pass
            self._load_job = None
        if self._version_job is not None:
            try:
                self.after_cancel(self._version_job)
            except tk.TclError:
                pass
            self._version_job = None
        if self._splash is not None:
            self._splash.close()
            self._splash = None
        if self._preview_job is not None:
            try:
                self.after_cancel(self._preview_job)
            except tk.TclError:
                pass
            self._preview_job = None
        try:
            self.app.close()          # 清掉容器工程解出来的临时工作目录
        except Exception:  # noqa: BLE001 - 清理失败不该拦住关闭
            pass
        super().destroy()

    def _about(self) -> None:
        dialog = AboutDialog(self)
        self.wait_window(dialog)


def run(project_path: str | Path | None = None) -> int:
    """图形界面入口。

    带一个「重建」循环：用户在首选项里换了主题、或做了初始化时，主窗口会
    先设好 ``_restart_requested`` 再销毁自己，这里就按新的设置重建一个 ——
    复用同一套启动流程，不用重启整个进程。
    """
    from ..core import container

    container.cleanup_stale()        # 清掉上次异常退出留下的临时工作目录
    # 打包成 exe 后，自动把 .jianpack 关联到本程序（双击即可打开，无需用户手动设置）。
    # 只在打包版做：源码运行会写成开发脚本路径，没必要。
    # 用 ensure_registered：先检查，只有「没关联 / 关联指到别处」才写，避免每次启动都动注册表。
    if getattr(sys, "frozen", False):
        try:
            assoc.ensure_registered()
        except OSError:
            pass

    path = project_path
    # 双击 .jianpack / 带工程路径启动：直接进主界面，跳过欢迎页和启动窗口
    welcome = project_path is None
    while True:
        window = MainWindow(path, welcome=welcome)
        window.mainloop()
        if not getattr(window, "_restart_requested", False):
            break
        path = getattr(window, "_restart_path", None)
        # 换主题/换语言后默认不再弹欢迎页；只有从欢迎页里切语言才保留
        welcome = bool(getattr(window, "_restart_welcome", False))
    return 0
