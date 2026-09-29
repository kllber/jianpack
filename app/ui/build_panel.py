"""左栏常驻的「开始打包」面板：动作按钮 + 实时日志。

原来这一整块是独立的「第 5 步 打包」页；现在固定在左侧面板上，随时能点。
打包相关的**设置**（版本 / 输出 / 压缩 / 签名）已经移到第 3 步「安装设置」。
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..checks import check_project, split
from ..core import demo
from ..core.errors import PackError
from ..engine import assets
from ..engine.makensis import compile_nsi, find_makensis
from ..engine.nsi import MODE_LABELS, NsiGenerator, output_file_name
from . import theme
from ..i18n import t as _
from .splash import Splash
from .widgets import APP_FONT, TITLE_FONT

WRAP = 500          # 左栏比较窄，提示文字按这个宽度换行


class BuildPanel(ttk.Frame):
    """「开始打包」：校验 / 只生成脚本 / 开始打包 / 打开输出目录 + 实时日志。"""

    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app
        self.window = None                 # 主窗口会填进来（打包前先 flush 全部页面）
        self._busy = False
        self._queue: queue.Queue = queue.Queue()
        self._produced: list[Path] = []
        self._pump_job = None
        self._progress_window = None
        self._build()
        self.app.subscribe(self._sync_enabled)
        self._sync_enabled()

    # -- 界面 ---------------------------------------------------------------

    def _build(self) -> None:
        ttk.Label(self, text=_("开始打包"), font=TITLE_FONT,
                  foreground=theme.c("accent")).pack(anchor="w", pady=(0, 6))

        row = ttk.Frame(self)
        row.pack(fill="x")
        self.check_button = ttk.Button(row, text=_("校验工程"), width=10,
                                       command=lambda: self.run("validate"))
        self.check_button.pack(side="left")
        self.gen_button = ttk.Button(row, text=_("只生成脚本"), width=11,
                                     command=lambda: self.run("generate"))
        self.gen_button.pack(side="left", padx=(4, 0))
        self.build_button = ttk.Button(row, text=_("开始打包"), width=10,
                                       command=lambda: self.run("build"))
        self.build_button.pack(side="left", padx=(4, 0))
        ttk.Button(row, text=_("打开输出目录"), width=12,
                   command=self.open_output).pack(side="left", padx=(4, 0))

        ttk.Label(self, foreground=theme.c("hint"), justify="left", wraplength=WRAP,
                  font=("Microsoft YaHei UI", 8),
                  text=_("打包前会自动保存工程。首次打包如果没装 NSIS，"
                         "程序会提示用 winget install NSIS.NSIS 安装。")
                  ).pack(anchor="w", pady=(4, 0))

        ttk.Label(self, text=_("日志"), font=APP_FONT).pack(anchor="w", pady=(6, 2))
        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True)
        self.log = tk.Text(holder, height=7, wrap="none", state="disabled",
                           font=("Consolas", 8), background=theme.c("log"),
                           foreground=theme.c("text"), insertbackground=theme.c("text"),
                           relief="solid", borderwidth=1)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # -- 启用状态 -----------------------------------------------------------

    def _sync_enabled(self) -> None:
        ready = (not self._busy) and self.app.project is not None
        state = "!disabled" if ready else "disabled"
        for button in (self.check_button, self.gen_button, self.build_button):
            button.state([state])

    # -- 日志 ---------------------------------------------------------------

    def _append(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _post(self, text: str) -> None:
        self._queue.put(("log", text))

    def _progress(self, done: int, total: int, status: str, file: str = "") -> None:
        self._queue.put(("progress", done, total, status, file))

    def _pump(self) -> None:
        if not self.winfo_exists():
            return
        try:
            while True:
                item = self._queue.get_nowait()
                if item is None:
                    self._close_progress()
                    self._set_busy(False)
                    return
                if item[0] == "log":
                    self._append(item[1])
                elif item[0] == "progress":
                    self._update_progress(*item[1:])
        except queue.Empty:
            pass
        if self._busy and self.winfo_exists():
            self._pump_job = self.after(120, self._pump)
        else:
            self._pump_job = None

    # -- 进度窗 -------------------------------------------------------------

    def _open_progress(self, total: int) -> None:
        try:
            splash = Splash(self, with_icon=True, status=_("正在打包…"),
                            file_name=self.app.project.project_name)
            splash.set_indeterminate()
        except Exception as exc:  # noqa: BLE001 - 进度窗失败也不该影响打包
            self._append(_("（提示：打包进度窗创建失败，不影响打包）") + f" {exc!r}")
            splash = None
        self._progress_window = splash

    def _update_progress(self, done: int, total: int, status: str, file: str = "") -> None:
        splash = self._progress_window
        if splash is None or not splash.winfo_exists():
            return
        if status:
            splash.set_status(status)
        splash.set_file(file)

    def _close_progress(self) -> None:
        splash = self._progress_window
        self._progress_window = None
        if splash is not None:
            splash.close()

    def destroy(self) -> None:
        job = getattr(self, "_pump_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
            self._pump_job = None
        self._close_progress()
        super().destroy()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._sync_enabled()

    # -- 主流程 -------------------------------------------------------------

    def run(self, action: str) -> None:
        if self._busy:
            return
        if self.app.project is None:
            return
        if self.window is not None:
            self.window.flush_all()

        project = self.app.project
        project.apply_derived()

        problems = check_project(project)
        errors, warnings = split(problems)

        self._clear_log()
        for line in warnings:
            self._append(line)
        if warnings:
            self._append("")

        if errors:
            for line in errors:
                self._append(line)
            self._append("")
            self._append(_("校验没通过，请先按上面的提示修改。"))
            messagebox.showerror(_("校验没通过"),
                                 _("发现 {n} 个问题，详情见下方日志。").format(n=len(errors)),
                                 parent=self.winfo_toplevel())
            return

        if action == "validate":
            try:
                count = len(list(project.iter_payload()))
            except PackError as exc:
                self._append(_("错误  ") + str(exc))
                return
            self._append(_("校验通过，可以打包了。"))
            self._append("")
            self._append(_("  应用名称  : ") + f"{project.app.name} {project.app.version}")
            self._append(_("  安装目录名: ") + project.app.dir_name)
            self._append(_("  主程序    : ") + project.app.main_exe)
            self._append(_("  打包内容  : ") + str(count) + _(" 个文件"))
            self._append(_("  输出模式  : ") + "、".join(project.build.modes))
            return

        if demo.is_demo(project.source_path):
            self._append(_("（演示项目不会保存工程文件，只做本次测试。）"))
            self._append("")
        else:
            try:
                saved = self.app.save()
            except Exception as exc:  # noqa: BLE001 - 保存失败要原样告诉用户
                messagebox.showerror(_("保存工程失败"), str(exc),
                                     parent=self.winfo_toplevel())
                return
            self._append(_("工程已保存：") + str(saved))
            self._append("")

        self._produced.clear()
        self._set_busy(True)
        self._queue = queue.Queue()
        if action == "build":
            self._open_progress(len(project.build.modes))
        threading.Thread(target=self._worker, args=(action, project),
                         daemon=True).start()
        self._pump_job = self.after(120, self._pump)

    def _worker(self, action: str, project) -> None:
        try:
            modes = list(project.build.modes)
            if action == "generate":
                for mode in modes:
                    script, expected = self._generate(project, mode, len(modes))
                    self._post(_("生成脚本：") + str(script))
                    self._post(_("预期产出：") + str(expected))
                self._post("")
                self._post(_("完成。"))
                return

            makensis = find_makensis()
            self._post(_("使用编译器：") + str(makensis))
            total = len(modes)

            def status_of(one: str, index: int) -> str:
                return _("正在打包… {mode}（{i}/{total}）").format(
                    mode=_(MODE_LABELS[one]), i=index, total=total)

            for index, mode in enumerate(modes, 1):
                script, expected = self._generate(project, mode, total)
                defines = ["PER_USER"] if mode == "perUser" else []
                defines.append("OUTFILE_NAME=" + expected.name)

                self._progress(index - 1, total, status_of(mode, index), expected.name)
                self._post("")
                self._post(_("=== 编译 [") + f"{mode}] {script.name}")
                result = compile_nsi(makensis, script, defines)
                if not result.ok:
                    for line in result.output.rstrip().splitlines():
                        self._post("  " + line)
                    self._post(_("编译失败（退出码 ") + f"{result.returncode}）")
                    return
                if not expected.is_file():
                    self._post(_("编译报告成功，但没有产出：") + str(expected))
                    return
                size_kb = expected.stat().st_size / 1024
                self._post(f"  -> {expected}   ({size_kb:,.0f} KB)")
                if project.build.sign_enabled:
                    from ..engine.signing import sign_file

                    self._post(_("正在签名（Authenticode）…"))
                    signed = sign_file(expected, project.build.sign_cert,
                                       project.build.sign_password,
                                       project.build.sign_timestamp,
                                       project.build.signtool)
                    for line in signed.output.rstrip().splitlines():
                        self._post("  " + line)
                    self._post(_("签名完成。") if signed.ok
                               else _("签名失败（安装包已生成，但没有签名）。"))
                self._produced.append(expected)
                self._progress(index, total, status_of(mode, index), expected.name)

            self._post("")
            self._post(_("打包完成，共") + f" {len(self._produced)} " + _("个安装包。"))
            for path in self._produced:
                self._post("  " + str(path))
        except PackError as exc:
            self._post("")
            self._post(_("错误：") + str(exc))
        except Exception as exc:  # noqa: BLE001 - 兜底，别让线程静默死掉
            self._post("")
            self._post(_("意外错误：") + repr(exc))
        finally:
            self._queue.put(None)

    def _generate(self, project, mode: str, total: int) -> tuple[Path, Path]:
        build_dir = project.resolve("build", "build")
        generator = NsiGenerator(project, mode, build_dir)
        name = output_file_name(project, mode, total)
        text = generator.generate(name)

        script = build_dir / "installer.nsi"
        assets.write_utf8_bom(text, script)

        out_dir = project.output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        return script, out_dir / name

    # -- 其它 ---------------------------------------------------------------

    def open_output(self) -> None:
        import os

        project = self.app.project
        if project is None:
            return
        out_dir = project.output_dir()
        if not out_dir.exists():
            messagebox.showinfo(_("目录还不存在"),
                                f"{out_dir}\n\n" + _("先打包一次就有了。"),
                                parent=self.winfo_toplevel())
            return
        os.startfile(str(out_dir))
