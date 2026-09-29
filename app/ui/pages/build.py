"""第 5 步：打包。"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ...checks import check_project, split
from ...core import demo
from ...core.errors import PackError
from ...engine import assets
from ...engine.makensis import compile_nsi, find_makensis
from ...engine.nsi import MODE_LABELS, NsiGenerator, output_file_name
from .. import theme
from ...i18n import t as _
from ..splash import Splash
from ..widgets import hint_label, section
from .base import StepPage

MODE_TEXT = (
    ("perMachine", "为所有用户安装（需要管理员权限，装到 Program Files）"),
    ("perUser", "仅当前用户安装（免提权，装到 %LOCALAPPDATA%\\Programs）"),
)


class BuildPage(StepPage):
    title = "打包"
    description = "输出设置与编译"
    subtitle = "校验配置、生成安装脚本、编译出安装包"

    def build(self, parent: ttk.Frame) -> None:
        self.window = None                 # 主窗口会填进来
        self._busy = False
        self._queue: queue.Queue = queue.Queue()
        self._produced: list[Path] = []
        self._pump_job = None              # 日志泵的 after 句柄（关窗口时要取消）
        self._progress_window = None       # 打包进度提示窗口（Splash）

        build = self.app.project.build

        output = self.section(parent, "输出设置")
        self.path(output, "输出位置", build, "output_dir", mode="dir", optional=True,
                  hint="留空 = 输出到桌面；也可以填绝对路径（相对路径按工程文件所在目录算）")
        self.text(output, "文件名", build, "file_name",
                  hint="可以用 {appName} {appVersion}。勾选多个版本时会自动加 "
                       "-PerMachine / -PerUser 后缀，避免互相覆盖。")
        self.combo(output, "压缩方式", build, "compression", [
            ("solid-lzma", "lzma 整体压缩（体积最小，推荐）"),
            ("lzma", "lzma 逐文件压缩"),
            ("zlib", "zlib（压缩最快，体积偏大）"),
            ("bzip2", "bzip2"),
        ])

        modes = self.section(parent, "要生成哪些版本")
        self.mode_vars: dict[str, tk.BooleanVar] = {}
        for key, text in MODE_TEXT:
            var = tk.BooleanVar(value=key in build.modes)
            ttk.Checkbutton(modes, text=_(text), variable=var).pack(anchor="w", pady=2)
            var.trace_add("write", lambda *_: self.app.touch())
            self.mode_vars[key] = var

        sign = self.section(parent, "代码签名")
        sign_on = self.check(sign, "打包后自动签名（Authenticode）", build, "sign_enabled",
                             hint="需要你自己有数字证书；不勾选就完全跳过。")
        sign_body = ttk.Frame(sign)
        sign_body.pack(fill="x")
        self.path(sign_body, "证书文件", build, "sign_cert", mode="file",
                  patterns=[("证书文件", "*.pfx *.p12"), ("所有文件", "*.*")],
                  hint=".pfx / .p12 数字证书文件")
        self.text(sign_body, "证书密码", build, "sign_password",
                  hint="会保存在工程文件里（明文），请自行妥善保管")
        self.text(sign_body, "时间戳服务器", build, "sign_timestamp",
                  hint="留空则不添加时间戳")
        self.path(sign_body, "signtool 路径", build, "signtool", mode="file",
                  hint="留空则自动查找（PATH / Windows SDK）")
        self.gate(sign_body, lambda: bool(sign_on.get()), [sign_on])

        actions = self.section(parent, "开始")
        row = ttk.Frame(actions)
        row.pack(fill="x")
        self.check_button = ttk.Button(row, text=_("校验工程"), width=12,
                                       command=lambda: self.run("validate"))
        self.check_button.pack(side="left")
        self.gen_button = ttk.Button(row, text=_("只生成脚本"), width=12,
                                     command=lambda: self.run("generate"))
        self.gen_button.pack(side="left", padx=(6, 0))
        self.build_button = ttk.Button(row, text=_("开始打包"), width=12,
                                       command=lambda: self.run("build"))
        self.build_button.pack(side="left", padx=(6, 0))
        ttk.Button(row, text=_("打开输出目录"),
                   command=self.open_output).pack(side="left", padx=(12, 0))

        hint_label(actions, "打包前会自动保存工程。首次打包如果没装 NSIS，"
                            "程序会提示用 winget install NSIS.NSIS 安装。")

        log_section = self.section(parent, "日志")
        holder = ttk.Frame(log_section)
        holder.pack(fill="both", expand=True)
        self.log = tk.Text(holder, height=15, wrap="none", state="disabled",
                           font=("Consolas", 9), background=theme.c("log"),
                           foreground=theme.c("text"), insertbackground=theme.c("text"),
                           relief="solid", borderwidth=1)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    # -- 同步 ---------------------------------------------------------------

    def flush(self) -> None:
        super().flush()
        modes = [key for key, var in self.mode_vars.items() if var.get()]
        self.app.project.build.modes = modes or ["perMachine"]

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
        """工作线程里调用，把日志丢进队列。"""
        self._queue.put(("log", text))

    def _progress(self, done: int, total: int, status: str, file: str = "") -> None:
        """工作线程里调用，更新打包进度窗（没有进度窗时会被忽略）。"""
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

    # -- 打包进度窗 ---------------------------------------------------------

    def _open_progress(self, total: int) -> None:
        try:
            splash = Splash(self, with_icon=True, status=_("正在打包…"),
                            file_name=self.app.project.project_name)
            # 编译进度拿不到逐文件百分比（makensis 不提供），所以用「来回滚动」的
            # 进度条表示「正在干活」；具体编到第几个版本看上面的文字（1/2）。
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
        state = "disabled" if busy else "!disabled"
        for button in (self.check_button, self.gen_button, self.build_button):
            button.state([state])

    # -- 主流程 -------------------------------------------------------------

    def run(self, action: str) -> None:
        if self._busy:
            return
        if self.window is not None:
            self.window.flush_all()

        project = self.app.project
        project.apply_derived()

        problems = check_project(project)
        errors, warnings = split(problems)

        self._clear_log()
        # 每行本身已经带了 [错误] / [警告] 前缀（Problem.__str__），别再叠一层
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
            # 演示项目不能保存，但允许直接拿当前配置测试打包效果
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
                    from ...engine.signing import sign_file

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
        out_dir = project.output_dir()
        if not out_dir.exists():
            messagebox.showinfo(_("目录还不存在"),
                                f"{out_dir}\n\n" + _("先打包一次就有了。"),
                                parent=self.winfo_toplevel())
            return
        os.startfile(str(out_dir))
