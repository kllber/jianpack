# -*- coding: utf-8 -*-
"""自检：跑一遍容易出错的地方，防止改一处坏一处。

目前覆盖：
  1. 工程文件「读进来 -> 写出去」是否无损（含字段类型）；
  2. 图形界面逐个页面走一遍（on_enter / flush）之后，保存出来的文件类型是否正确；
     —— 这一项是为了拦住「Tk 变量只能存字符串，把 True/False 写成了 "1"/"0"」这类问题；
  3. 早期的坏文件（布尔值被存成字符串）是否还能正常打开。

用法：python tools\\self-test.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core import container  # noqa: E402
from app.core.project import load_project  # noqa: E402
from app.core.serialize import project_to_dict, save_project  # noqa: E402

DEMO = ROOT / "demo" / "feasibility" / "demo.jianpack"

_failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _failed
    if ok:
        print(f"  [通过] {name}")
    else:
        print(f"  [失败] {name}  {detail}")
        _failed += 1


def walk_types(value, path: str = "", out: dict | None = None) -> dict:
    """把 JSON 里每个字段的「类型」摊平成 ``路径 -> 类型名``。"""
    out = {} if out is None else out
    if isinstance(value, dict):
        for key, item in value.items():
            walk_types(item, f"{path}.{key}" if path else key, out)
    elif isinstance(value, list):
        out[path] = f"list[{len(value)}]"
    else:
        # bool 是 int 的子类，必须排在前面判断
        out[path] = type(value).__name__
    return out


def compare_types(before: dict, after: dict, label: str) -> None:
    problems = []
    for key, kind in before.items():
        if key not in after:
            problems.append(f"{key}: 丢失")
        elif after[key] != kind:
            problems.append(f"{key}: {kind} -> {after[key]}")
    if problems:
        check(label, False, "；".join(problems[:6]) + ("…" if len(problems) > 6 else ""))
    else:
        check(label, True)


def wait_loaded(window, timeout: float = 20.0) -> bool:
    """等主窗口后台读工程完成（新版打开工程是异步的，带加载提示）。"""
    import tkinter as tk

    end = time.time() + timeout
    while time.time() < end:
        try:
            window.update()
        except tk.TclError:
            break
        if window.app.project is not None:
            return True
        time.sleep(0.02)
    return window.app.project is not None


def make_workspace() -> Path:
    work = Path(tempfile.mkdtemp(prefix="aipack-self-test-"))
    shutil.copytree(ROOT / "demo" / "feasibility" / "input", work / "input")
    shutil.copytree(ROOT / "demo" / "feasibility" / "assets", work / "assets")
    shutil.copytree(ROOT / "demo" / "feasibility" / "src", work / "src")
    shutil.copy2(DEMO, work / DEMO.name)
    return work


# ---------------------------------------------------------------------------

def test_plain_roundtrip(work: Path) -> None:
    print("\n=== 1. 工程文件读写无损 ===")
    source = work / DEMO.name
    before = json.loads(source.read_text(encoding="utf-8"))

    project = load_project(source)
    target = work / "roundtrip.jianpack"
    save_project(project, target)
    after = json.loads(target.read_text(encoding="utf-8"))

    compare_types(walk_types(before), walk_types(after), "字段类型保持不变")

    reloaded = load_project(target)
    check("重新打开不报错", True)
    check("布尔字段仍是 bool",
          isinstance(reloaded.uninstall.delete_user_data_by_default, bool)
          and isinstance(reloaded.install.allow_change_dir, bool))
    check("安装模式仍是字符串", isinstance(reloaded.install.mode, str))


def test_gui_roundtrip(work: Path) -> None:
    print("\n=== 2. 图形界面逐页走一遍再保存 ===")
    try:
        from app.ui.main_window import STEPS, MainWindow
    except Exception as exc:  # noqa: BLE001
        check("界面可以加载", False, repr(exc))
        return

    source = work / DEMO.name
    before = json.loads(source.read_text(encoding="utf-8"))

    window = MainWindow(source)
    wait_loaded(window)
    window.withdraw()
    window.update()
    layout: list[tuple[int, int, int]] = []
    try:
        def measure(label: int) -> None:
            """量「滚动区里那层内容」的请求尺寸。

            量整页没用 —— 页面里套着 Canvas，它的默认尺寸会把内容尺寸盖住。
            """
            window.update_idletasks()
            for index in range(len(STEPS)):
                inner = window._pages[index].body.inner
                layout.append((label * 10 + index + 1,
                               inner.winfo_reqwidth(), inner.winfo_reqheight()))

        for index in range(len(STEPS)):
            window._select_step(index)      # 切走时会 flush 上一页
            window.update()
        measure(1)

        # 再把三张图片都清掉，专门试「一张图都没选」的情况 ——
        # 这里曾经把 tk.Label 的 width 当成像素用，结果没图时缩略图框
        # 变成 96 个字宽，把整页撑爆。
        project = window.app.project
        keep = (project.app.icon, project.interface.header_image,
                project.interface.welcome.image)
        project.app.icon = None
        project.interface.header_image = None
        project.interface.welcome.image = None
        window._select_step(0)
        window._select_step(3)
        window.update()
        measure(2)

        # 恢复成原样，免得影响后面的类型比对
        (project.app.icon, project.interface.header_image,
         project.interface.welcome.image) = keep

        window.flush_all()
        window.app.save()
    finally:
        window.destroy()

    print("     各页内容请求尺寸 (编号, 宽, 高):", layout)
    too_big = [f"{number}: {w}×{h}" for number, w, h in layout
               if w > 1250 or h > 1400]
    check("没有页面被控件撑爆", not too_big, "；".join(too_big))

    after = json.loads(source.read_text(encoding="utf-8"))
    compare_types(walk_types(before), walk_types(after), "走完界面后字段类型没变")

    reloaded = load_project(source)
    check("界面保存的文件能重新打开", True)
    check("「静默卸载默认」仍是 bool",
          isinstance(reloaded.uninstall.delete_user_data_by_default, bool),
          f"实际是 {reloaded.uninstall.delete_user_data_by_default!r}")


def test_tolerate_broken_bool(work: Path) -> None:
    print("\n=== 3. 早期的坏文件还能打开 ===")
    source = work / DEMO.name
    data = json.loads(source.read_text(encoding="utf-8"))

    cases = [("1", True), ("0", False), ("true", True), ("false", False), (1, True), (0, False)]
    path = work / "broken.jianpack"
    for written, expected in cases:
        data["uninstall"]["deleteUserDataByDefault"] = written
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            project = load_project(path)
            actual = project.uninstall.delete_user_data_by_default
            check(f"{written!r} 被读成 {expected}", actual is expected, f"实际 {actual!r}")
        except Exception as exc:  # noqa: BLE001
            check(f"{written!r} 被读成 {expected}", False, repr(exc))

    print("\n--- 真正非法的值要报错 ---")
    data["uninstall"]["deleteUserDataByDefault"] = "也许吧"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        load_project(path)
        check("非法值被拒绝", False, "居然读进去了")
    except Exception as exc:  # noqa: BLE001
        check("非法值被拒绝", "也许吧" in str(exc), str(exc))


def test_new_project_names(work: Path) -> None:
    """新建工程时对名称的校验（纯函数，好测）。"""
    print("\n=== 4. 工程名称的合法性校验 ===")
    from app.ui.new_project_dialog import NewProjectDialog

    cases = [
        ("我的软件", "C:\\", True),
        ("MyApp", "C:\\", True),
        ("", "C:\\", False),
        ("a/b", "C:\\", False),
        ("a\\b", "C:\\", False),
        ('a"b', "C:\\", False),
        ("a?b", "C:\\", False),
        ("有空格 ", "C:\\", False),
        ("有点.", "C:\\", False),
        ("..", "C:\\", False),
        ("名字", "", False),
    ]
    bad = []
    for name, parent, should_pass in cases:
        ok = not NewProjectDialog._validate(name, parent)
        if ok != should_pass:
            bad.append(f"{name!r}->{ok}")
    check("名称校验符合预期", not bad, "；".join(bad))


def test_start_flow(work: Path) -> None:
    """启动时让用户选「新建 / 打开 / 退出」——三条路都要能走通。"""
    print("\n=== 5. 启动窗口的三种选择 ===")
    import tkinter as tk

    from app.ui import main_window as mw
    from app.ui.start_dialog import StartDialog

    def find_dialog(window):
        for child in window.winfo_children():
            if isinstance(child, StartDialog):
                return child
        return None

    def run_case(choice):
        window = mw.MainWindow()
        box: dict[str, object] = {"path": None}
        jobs: list[str] = []

        def later(ms: int, func) -> str:
            job = window.after(ms, func)
            jobs.append(job)
            return job

        try:
            def poke() -> None:
                dialog = find_dialog(window)
                if dialog is None:
                    later(60, poke)
                    return

                # 注意：StartDialog 构造里会 update() 一次，可能在它还没构造完时
                # 就触发这里。等它稳定下来再销毁，免得踩到「构造中途被销毁」。
                def act() -> None:
                    if dialog.winfo_exists():
                        dialog.result = choice
                        dialog.destroy()

                later(80, act)

            def stop() -> None:
                # 关窗口会清掉工程（并删掉临时工作目录），所以先记下来
                if window.app.project is not None:
                    box["path"] = window.app.project.source_path
                try:
                    window.destroy()
                except tk.TclError:
                    pass

            later(300, poke)
            later(6000, stop)
            window.mainloop()
            return box["path"]
        finally:
            for job in jobs:      # 把还挂着的 after 清掉，免得窗口销毁后回调再触发
                try:
                    window.after_cancel(job)
                except tk.TclError:
                    pass
            try:
                window.destroy()
            except tk.TclError:
                pass     # 走「退出」那条路时主窗口已经自己关掉了

    # --- 选「新建工程」：用一个立即返回的假对话框顶替真实对话框
    project_file = work / "新建的工程.jianpack"

    class InstantDialog(tk.Toplevel):
        def __init__(self, master, settings):
            super().__init__(master)
            self.withdraw()
            self.result = (str(project_file), str(work))
            self.after(0, self.destroy)

    original_dialog = mw.NewProjectDialog
    mw.NewProjectDialog = InstantDialog
    try:
        created = run_case(("new", None))
    finally:
        mw.NewProjectDialog = original_dialog

    check("选「新建工程」-> 建出了工程",
          created is not None and Path(created).name == project_file.name,
          f"实际 {created}")
    check("新建工程只产出一个 .jianpack 文件（单文件容器）",
          project_file.is_file() and container.sniff(project_file) == "container",
          f"实际 {[p.name for p in work.iterdir()] if work.is_dir() else '(没有)'}")
    check("这个文件能重新完整打开",
          load_project(project_file).app.version == "1.0.0")

    # --- 选「打开已有工程」
    opened = run_case(("open", str(DEMO)))
    check("选「打开已有工程」-> 打开了指定工程",
          opened is not None and Path(opened) == DEMO.resolve(), f"实际 {opened}")

    # --- 点「退出」
    cancelled = run_case(None)
    check("点「退出」-> 不进主界面", cancelled is None, f"实际 {cancelled}")


def test_no_flash(work: Path) -> None:
    """启动时主窗口不能先闪一下再被藏掉。

    根因是：只要在 ``withdraw()`` 之前处理过一次空闲事件
    （``update_idletasks`` / ``update``），Tk 就会把主窗口画出来。
    所以这里直接盯着「构造期间有没有强制刷新界面」这件事——
    比抓窗口可见性可靠得多（构造是同步的，等外部采样时窗口早藏起来了）。
    """
    print("\n=== 6. 启动时主窗口不闪现 ===")
    import tkinter as tk

    from app.ui.main_window import MainWindow

    refreshes: list[str] = []
    original = tk.Misc.update_idletasks

    def spy(self, *args, **kwargs):
        # 关键不是「有没有刷新」，而是「刷新的时候窗口是不是还露在外面」。
        # withdraw() 之后随便刷新都不会被用户看见。
        try:
            top = self.winfo_toplevel()
            if isinstance(top, tk.Tk) and top.state() != "withdrawn":
                refreshes.append(type(self).__name__)
        except tk.TclError:
            pass
        return original(self, *args, **kwargs)

    tk.Misc.update_idletasks = spy
    try:
        window = MainWindow()
    finally:
        tk.Misc.update_idletasks = original

    try:
        check("窗口还没藏起来的时候没有强制刷新过界面（否则就会闪一下）",
              not refreshes, f"发生了 {len(refreshes)} 次：{refreshes[:3]}")
        check("构造完主窗口处于隐藏状态", not window.winfo_viewable())
    finally:
        try:
            window.destroy()
        except tk.TclError:
            pass


def test_image_pipeline(work: Path) -> None:
    """图片这条链：读入任意格式 -> 裁剪 -> 转成要求的 BMP / ICO -> 通过校验。"""
    print("\n=== 7. 图片裁剪与格式转换 ===")
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover
        check("Pillow 可用", False, repr(exc))
        return

    from app.engine.assets import (
        TARGETS, check_bitmap, check_icon, load_for_edit, read_bmp_size,
        read_ico_sizes, render_target, save_image,
    )

    # 造一张「大照片」，顺带验证大图会被缩到工作分辨率
    source = work / "测试照片.png"
    photo = Image.new("RGB", (3000, 2000))
    draw = ImageDraw.Draw(photo)
    for y in range(0, 2000, 8):
        draw.rectangle([0, y, 3000, y + 8], fill=(40 + y // 20, 120, 220 - y // 20))
    draw.ellipse([2200, 120, 2860, 780], fill=(255, 225, 120))
    photo.save(source)

    # 带透明通道的图，验证 BMP 是压在白底上而不是变成黑块
    alpha_source = work / "透明图.png"
    rgba = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    ImageDraw.Draw(rgba).ellipse([40, 40, 360, 360], fill=(220, 40, 40, 255))
    rgba.save(alpha_source)

    for key in ("header", "welcome", "icon"):
        target = TARGETS[key]
        image, original = load_for_edit(source)
        check(f"{key}: 大图读完不会返回原尺寸（会先缩到工作分辨率）",
              max(image.size) <= 2400, f"实际 {image.size}，原始 {original}")

        rendered = render_target(image, target, (0, 0, image.width, image.height))
        check(f"{key}: 裁剪结果正好是 {target.size[0]}×{target.size[1]}",
              rendered.size == target.size, f"实际 {rendered.size}")

        dest = work / target.file_name
        save_image(rendered, dest, target)
        check(f"{key}: 文件写出来了", dest.is_file())

        if target.kind == "bmp":
            check(f"{key}: 是合法的 BMP 且尺寸正确",
                  check_bitmap(dest, target.size, key) is None,
                  str(check_bitmap(dest, target.size, key)))
            check(f"{key}: 用标准库也能读出尺寸",
                  read_bmp_size(dest) == target.size, f"实际 {read_bmp_size(dest)}")
        else:
            check(f"{key}: 是合法的 ICO 且含 256 和 16 两档",
                  check_icon(dest, key) is None, str(check_icon(dest, key)))
            sizes = set(read_ico_sizes(dest))
            check(f"{key}: 导出了全部 {len(('16', '24', '32', '48', '64', '128', '256'))} 档尺寸",
                  {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
                   (256, 256)} <= sizes, f"实际 {sorted(sizes)}")

    # 透明图转 BMP：透明区域应该被压成白色，而不是黑
    target = TARGETS["icon"]
    image, _ = load_for_edit(alpha_source)
    rendered = render_target(image, TARGETS["header"], (0, 0, image.width, image.height))
    corner = rendered.getpixel((2, 2))
    check("透明区域压在白底上（不是黑块）",
          all(channel > 200 for channel in corner), f"左上角像素 {corner}")


def test_derived_registry_key(work: Path) -> None:
    """注册表键的派生：中文要保留，空输入不能提前冻结成占位值。"""
    print("\n=== 8. 内部标识（注册表键）的派生 ===")
    from app.core.project import GENERIC_REGKEY, Project

    def derive(name: str, dir_name: str = "") -> tuple[str, str]:
        project = Project(source_path=work / "x.jianpack", base_dir=work)
        project.app.name = name
        project.app.dir_name = dir_name
        project.app.version = "1.0.0"
        project.apply_derived()
        return project.app.dir_name, project.app.registry_key

    cases = [
        ("我的小工具", "", ("我的小工具", "我的小工具")),
        ("大便研究所", "", ("大便研究所", "大便研究所")),
        ("MyApp", "", ("MyApp", "MyApp")),
        ("我的软件 1.0", "", ("我的软件 1.0", "我的软件 1.0")),
        ("记事本++", "", ("记事本++", "记事本++")),
        ("中文名", "MyTool", ("MyTool", "MyTool")),
        ("有\\斜杠", "", ("有\\斜杠", "有_斜杠")),
    ]
    bad = []
    for name, dir_name, expected in cases:
        actual = derive(name, dir_name)
        if actual != expected:
            bad.append(f"{name!r} -> {actual}，期望 {expected}")
    check("中文名不会被删空、特殊字符被换掉", not bad, "；".join(bad))

    check(f"不同中文软件不会共用「{GENERIC_REGKEY}」这个键",
          derive("我的小工具")[1] != derive("大便研究所")[1])

    # 关键：名称还空着的时候不能派生，否则占位值会被写进工程文件后永远不更新
    empty_dir, empty_key = derive("")
    check("应用名为空时不会提前派生（避免占位值被冻结）",
          empty_dir == "" and empty_key == "", f"实际 {(empty_dir, empty_key)!r}")

    # 版本号同理
    project = Project(source_path=work / "y.jianpack", base_dir=work)
    project.apply_derived()
    check("版本号为空时不会派生 fileVersion",
          project.app.file_version == "", f"实际 {project.app.file_version!r}")

    # 遗留工程（键被冻成 App）应该给出警告
    legacy = Project(source_path=work / "z.jianpack", base_dir=work)
    legacy.app.name = "我的软件"
    legacy.app.dir_name = "我的软件"
    legacy.app.version = "1.0.0"
    legacy.app.registry_key = GENERIC_REGKEY
    legacy.apply_derived()
    messages = [p.message for p in legacy.validate() if p.level == "warning"]
    check("遗留的通用键会给出警告",
          any("内部标识" in m for m in messages), f"警告：{messages}")


def test_inline_text_pages(work: Path) -> None:
    """许可协议 / 更新日志可以「直接编辑」，也保留「从文件导入」，两者不能串味。"""
    print("\n=== 9. 协议与日志的内嵌文本 ===")
    import json

    from app.core.project import load_project
    from app.core.serialize import save_project
    from app.engine import assets
    from app.engine.nsi import NsiGenerator

    # --- 老工程兼容：没有 source 字段、但有 file，应当按「文件来源」处理
    legacy = json.loads((work / DEMO.name).read_text(encoding="utf-8"))
    legacy["interface"]["license"].pop("source", None)
    legacy["interface"]["license"].pop("text", None)
    legacy["interface"]["changelog"].pop("source", None)
    legacy["interface"]["changelog"].pop("text", None)
    legacy_path = work / "老工程.jianpack"
    legacy_path.write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")

    old = load_project(legacy_path)
    check("老工程（只有 file）被当成「文件来源」",
          old.interface.license.source == "file"
          and old.interface.changelog.source == "file",
          f"实际 {old.interface.license.source!r}")
    check("老工程校验通过",
          not [p for p in old.validate() if p.level == "error"])

    # --- 新工程：改成直接编辑
    project = load_project(work / DEMO.name)
    project.interface.license.source = "text"
    project.interface.license.text = "第一条：随便用。\n第二条：别干坏事。"
    project.interface.changelog.source = "text"
    # 故意写长，验证不会再被 NSIS 的 1024 字符上限截断
    project.interface.changelog.text = "\n".join(
        f"第 {i:03d} 行：这是一条测试用的更新说明。" for i in range(1, 61))

    check("内嵌模式校验通过",
          not [p for p in project.validate() if p.level == "error"],
          str([p for p in project.validate() if p.level == "error"]))

    target = work / "内嵌文本.jianpack"
    save_project(project, target)
    again = load_project(target)
    check("内嵌文字能正确保存并读回",
          again.interface.license.text == project.interface.license.text
          and again.interface.changelog.text == project.interface.changelog.text)
    check("内容来源也能存下来",
          again.interface.license.source == "text"
          and again.interface.changelog.source == "text")

    # --- 生成器：两种来源都要落到 build/ 里，编码要对
    build_dir = work / "build-inline"
    generator = NsiGenerator(project, "perMachine", build_dir)
    script = generator.generate("x.exe")
    check("内嵌的许可协议被写成了 UTF-8 带 BOM 的文件",
          generator.license_abs is not None
          and assets.read_text_auto(generator.license_abs).replace("\r\n", "\n")
          == project.interface.license.text)
    changelog_file = generator.changelog_abs
    check("内嵌的更新日志被写成了文件",
          changelog_file is not None and changelog_file.is_file())
    if changelog_file is not None:
        raw = changelog_file.read_bytes()
        check("更新日志文件是 UTF-16LE 带 BOM",
              raw[:2] == b"\xff\xfe", f"头两个字节 {raw[:2]!r}")
        written = assets.read_text_auto(changelog_file).replace("\r\n", "\n").strip()
        check("长日志完整写入，没有被截断",
              written == project.interface.changelog.text.strip(),
              f"写入 {len(written)} 字，原文 "
              f"{len(project.interface.changelog.text.strip())} 字")

    # --- 脚本里不能再出现「攒到变量」的写法（那正是 1024 上限的来源）
    check("生成的脚本不靠变量累积日志内容",
          "ChangelogText" not in script and "EM_REPLACESEL" in script,
          "脚本里还有旧的累积写法" if "ChangelogText" in script else "没找到 EM_REPLACESEL")

    # --- 切回文件来源，内容不该丢
    project.interface.changelog.source = "file"
    check("切回文件来源后内嵌正文还在（没被清空）",
          "第 001 行" in project.interface.changelog.text)


def test_preview(work: Path) -> None:
    """右侧实时预览：渲染、跟随配置、跟随输入。"""
    print("\n=== 10. 安装效果预览 ===")
    import tkinter as tk
    from tkinter import ttk

    from app.core.project import load_project
    from app.ui import preview
    from app.ui.main_window import MainWindow

    project = load_project(work / DEMO.name)

    # --- 渲染所有页面
    pages = preview.available_pages(project)
    check("页面清单和配置一致",
          pages[0] == "appinfo"
          and pages[1:4] == ["welcome", "license", "changelog"]
          and pages[-1] == "finish",
          f"实际 {pages}")
    bad = []
    for key in pages + ["instfiles"]:
        if key == "appinfo":
            continue          # 「程序属性」是另一种窗口，尺寸不同，下面单独测
        try:
            image = preview.render(project, key)
            if image.size != (503, 362):
                bad.append(f"{key}: {image.size}")
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{key}: {exc!r}")
    check("每一页安装页面都能渲染成 503×362", not bad, "；".join(bad))

    try:
        info = preview.render(project, "appinfo")
        check("「程序属性」预览能渲染",
              info.size[0] > 300 and info.size[1] > 300, f"实际 {info.size}")
    except Exception as exc:  # noqa: BLE001
        check("「程序属性」预览能渲染", False, repr(exc))

    # --- 关掉某一页，清单要跟着变
    project.interface.changelog.enabled = False
    check("关掉更新日志页后清单里就没有它",
          "changelog" not in preview.available_pages(project))
    project.interface.changelog.enabled = True

    # --- 改配置，画面要变
    before = preview.render(project, "welcome").tobytes()
    project.interface.welcome.title = "完全不一样的标题"
    after = preview.render(project, "welcome").tobytes()
    check("改了欢迎页标题，画面跟着变", before != after)

    # 预览的安装路径要跟随「第 5 步勾选的版本」，而不是那个不再出现在界面上的 install.mode
    project.install.mode = "perMachine"
    project.build.modes = ["perUser"]
    check("预览安装路径跟随第 5 步勾选的版本",
          "AppData\\Local" in preview._sample_dir(project), preview._sample_dir(project))
    project.build.modes = ["perMachine"]
    check("换一个版本预览路径也跟着变",
          "Program Files" in preview._sample_dir(project), preview._sample_dir(project))

    # 程序属性的「语言」跟着第 1 步的多选走
    from app.core.project import LanguageEntry

    project.interface.languages = [LanguageEntry(name="简体中文(中国大陆)", lcid=2052)]
    zh_label = preview._version_language_label(project)
    project.interface.languages = [
        LanguageEntry(name="简体中文(中国大陆)", lcid=2052),
        LanguageEntry(name="日本語", lcid=1041)]
    multi_label = preview._version_language_label(project)
    project.interface.languages = [LanguageEntry(name="English", lcid=1033)]
    en_label = preview._version_language_label(project)
    check("程序属性语言跟随多选设置",
          "简体" in zh_label and "简体" not in en_label
          and "日本語" in multi_label and "简体" in multi_label,
          f"{zh_label!r} / {multi_label!r} / {en_label!r}")
    project.interface.languages = [LanguageEntry(name="简体中文(中国大陆)", lcid=2052)]

    # --- 面板装进主窗口后，编辑区不能被挤坏
    window = MainWindow(str(work / DEMO.name))
    wait_loaded(window)
    window.withdraw()
    window.update()
    try:
        check("主窗口里有预览面板", hasattr(window, "preview_panel"))
        window._select_step(3)
        window.update()
        window.update_idletasks()

        # 窗口是隐藏的，winfo_width() 永远是 1，所以看我们请求的几何尺寸：
        # 预览占了左栏之后，右边编辑区必须仍有足够宽度。
        total_w = int(window.geometry().split("+")[0].split("x")[0])
        content_w = total_w - preview.PANEL_WIDTH
        check("预览占了左栏，右边编辑区仍有足够宽度",
              content_w >= 950, f"编辑区约 {content_w}px（窗口 {total_w}px）")

        check("步骤列表是两列（名称 + 说明）",
              len(window.step_list.get_children()) == 4
              and window.step_list.item("0", "values")[1] != "",
              f"实际 {window.step_list.item('0', 'values')!r}")

        inner = window._pages[3].body.inner
        check("安装界面页没有被撑爆",
              inner.winfo_reqwidth() <= 1250 and inner.winfo_reqheight() <= 1400,
              f"{inner.winfo_reqwidth()}×{inner.winfo_reqheight()}")

        # --- 真正走一遍「改控件 -> 刷新预览」这条链路
        original = window.app.project.interface.welcome.title
        entry = _find_entry(window._pages[3], original)
        check("能找到欢迎页标题的输入框", entry is not None)
        if entry is not None:
            snapshot = preview.render(window.app.project, "welcome").tobytes()
            entry.delete(0, "end")
            entry.insert(0, "从输入框改的标题")
            window._update_preview()          # 相当于防抖到点后的那次刷新
            check("输入框里的改动被收进了模型",
                  window.app.project.interface.welcome.title == "从输入框改的标题",
                  f"实际 {window.app.project.interface.welcome.title!r}")
            check("预览画面随之更新",
                  preview.render(window.app.project, "welcome").tobytes() != snapshot)

        # --- 切第 4 步的子标签，预览要跟着走
        notebook = getattr(window._pages[3], "_notebook", None)
        check("能拿到第 4 步的子标签容器", notebook is not None)
        if notebook is not None:
            notebook.select(1)                 # 许可协议
            deadline = time.time() + 3
            while time.time() < deadline:
                window.update()
                time.sleep(0.02)
                if window.preview_panel._page == "license":
                    break
            check("切到「许可协议」子标签后，预览也切过去了",
                  window.preview_panel._page == "license",
                  f"实际 {window.preview_panel._page}")

        # --- 收起 / 展开都不能出事
        window.preview_var.set(False)
        window.toggle_preview()
        window.update()
        check("收起预览后主窗口仍在", window.winfo_exists() == 1)
        window.preview_var.set(True)
        window.toggle_preview()
        window.update()
        check("重新展开预览也正常", window.preview_panel.winfo_exists() == 1)
    finally:
        try:
            window.destroy()
        except tk.TclError:
            pass


def test_no_maximize(work: Path) -> None:
    """全屏 / 最大化应当被禁用：按钮去掉，被最大化也会自动还原。"""
    print("\n=== 11. 禁用最大化 ===")
    import ctypes
    import tkinter as tk
    from ctypes import wintypes

    from app.ui.main_window import MainWindow

    if sys.platform != "win32":
        check("非 Windows，跳过", True)
        return

    window = MainWindow(str(work / DEMO.name))
    wait_loaded(window)

    def pump(seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            window.update()
            time.sleep(0.02)

    try:
        pump(0.8)

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_long = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
        get_long.restype = ctypes.c_ssize_t
        get_long.argtypes = [wintypes.HWND, ctypes.c_int]
        GWL_STYLE, WS_MAXIMIZEBOX = -16, 0x00010000

        def has_max_box() -> bool:
            hwnd = int(window.tk.call("wm", "frame", window._w), 16)
            return bool(get_long(wintypes.HWND(hwnd), GWL_STYLE) & WS_MAXIMIZEBOX)

        check("标题栏的「最大化」按钮已去掉", not has_max_box())

        before = (window.winfo_width(), window.winfo_height())
        window.state("zoomed")
        pump(1.5)
        after = (window.winfo_width(), window.winfo_height())
        check("强行最大化也会自动还原",
              after[0] < window.winfo_screenwidth() - 5,
              f"{before} -> {after}（屏幕宽 {window.winfo_screenwidth()}）")

        # 走系统菜单那条路（双击标题栏 / Win+↑ 用的就是它）
        hwnd = int(window.tk.call("wm", "frame", window._w), 16)
        user32.SendMessageW.argtypes = [wintypes.HWND, ctypes.c_uint,
                                        ctypes.c_ssize_t, ctypes.c_ssize_t]
        user32.SendMessageW(wintypes.HWND(hwnd), 0x0112, 0xF030, 0)   # SC_MAXIMIZE
        pump(1.5)
        check("模拟「最大化」命令也不生效",
              window.winfo_width() < window.winfo_screenwidth() - 5,
              f"实际宽 {window.winfo_width()}")
    finally:
        try:
            window.destroy()
        except tk.TclError:
            pass


def test_container(work: Path) -> None:
    """单文件工程：文件夹 -> .jianpack 容器 -> 完整打开；输出位置默认桌面。"""
    print("\n=== 14. 单文件工程（.jianpack 容器）===")
    from app.core.paths import desktop_dir
    from app.core.project import Project

    source = work / DEMO.name
    target = work / "打包成单个文件.jianpack"

    project = load_project(source)
    original_name = project.app.name
    original_items = len(project.files.items)
    save_project(project, target, container_mode=True)
    work_dir = project.work_dir
    project.cleanup()

    check("工程能打包成单个 .jianpack 文件",
          target.is_file() and container.sniff(target) == "container")
    check("打包完临时工作目录被清掉",
          work_dir is None or not Path(work_dir).exists())

    again = load_project(target)
    try:
        check("别人拿到这一个文件就能完整打开",
              again.is_container and again.app.name == original_name
              and len(again.files.items) == original_items
              and again.base_dir.is_dir())
        payload = list(again.iter_payload())
        check("解出来的工程能读到要打包的文件",
              bool(payload) and payload[0][0].is_file(),
              f"实际 {payload[:1]}")
    finally:
        again.cleanup()

    # 系统集成 / 代码签名：存进去再读出来要一致
    from app.core.project import AssocEntry, ProtocolEntry, RegEntry

    rich = load_project(work / DEMO.name)
    rich.integration.associations = [
        AssocEntry(ext=".t", description="d", icon="", is_default=False)]
    rich.integration.protocols = [ProtocolEntry(scheme="t", description="dd")]
    rich.integration.registry = [
        RegEntry(root="HKLM", path="Software\\T", name="n", type="REG_DWORD", data="7")]
    rich.interface.finish.autostart_enabled = True
    rich.interface.finish.autostart_default = True
    rich.build.sign_enabled = True
    rich.build.sign_cert = "a.pfx"
    rich.build.sign_password = "pw"
    rich_path = work / "集成.jianpack"
    save_project(rich, rich_path, container_mode=True)
    rich.cleanup()

    rich2 = load_project(rich_path)
    try:
        check("系统集成 / 签名 字段能存取一致",
              rich2.integration.associations[0].ext == ".t"
              and rich2.integration.associations[0].is_default is False
              and rich2.integration.protocols[0].scheme == "t"
              and rich2.integration.registry[0].root == "HKLM"
              and rich2.integration.registry[0].type == "REG_DWORD"
              and rich2.integration.registry[0].data == "7"
              and rich2.interface.finish.autostart_enabled is True
              and rich2.interface.finish.autostart_default is True
              and rich2.build.sign_enabled is True
              and rich2.build.sign_cert == "a.pfx"
              and rich2.build.sign_password == "pw")
    finally:
        rich2.cleanup()

    # 输出位置：留空 = 桌面；填了就用填的
    fresh = Project(source_path=work / "x.jianpack", base_dir=work)
    check("输出位置留空时默认是桌面", fresh.output_dir() == desktop_dir(),
          f"实际 {fresh.output_dir()}")
    fresh.build.output_dir = str(work / "自定义输出")
    check("填了输出位置就用填的",
          fresh.output_dir() == (work / "自定义输出"))

    # 双击 .jianpack（命令行直接拿到文件路径）要当成「打开这个工程」
    from app.cli import normalize_argv

    check("双击 .jianpack 会被当成「打开这个工程」",
          normalize_argv(["C:\\x\\我的软件.jianpack"]) == ["gui", "C:\\x\\我的软件.jianpack"])
    check("没有参数时打开图形界面", normalize_argv([]) == ["gui"])
    check("正常的子命令不受影响",
          normalize_argv(["build", "x.jianpack"]) == ["build", "x.jianpack"])

    from app.core import assoc

    check("文件关联的命令行能拼出来", bool(assoc._app_command()))
    check("文件关联状态可查询", isinstance(assoc.is_associated(), bool))

    # 自带演示项目（单文件容器），供启动窗口第一行使用
    from app.core import demo

    demo_path = demo.demo_project_path()
    check("自带演示项目可用（单文件容器）",
          demo_path is not None and Path(demo_path).is_file()
          and container.sniff(Path(demo_path)) == "container",
          f"实际 {demo_path}")

    # 缓存目录 / 设置文件都应在「软件目录」下，而不是 C 盘任意位置
    from app.core import paths
    from app.core.errors import ProjectFileError
    from app.core.settings import load_settings, save_settings, settings_file

    check("设置文件在软件目录下的 data 里",
          settings_file().parent == paths.data_dir(), f"实际 {settings_file()}")
    check("默认缓存目录 = 软件目录下的 data\\work",
          container.cache_root() == (paths.data_dir() / "work"),
          f"实际 {container.cache_root()}")

    settings = load_settings()
    old_cache = settings.cache_dir
    settings.cache_dir = str(work / "自定义缓存")
    save_settings(settings)
    check("首选项里设了缓存目录就按它来",
          container.cache_root() == (work / "自定义缓存"),
          f"实际 {container.cache_root()}")
    settings.cache_dir = old_cache
    save_settings(settings)

    try:
        container._ensure_space(paths.data_dir(), 1 << 62, "测试")
        check("磁盘空间不足会被拦下", False, "居然没报错")
    except ProjectFileError as exc:
        check("磁盘空间不足会拦下并提示", "磁盘空间不足" in str(exc), str(exc))


def test_demo_readonly(work: Path) -> None:
    """演示项目只读：保存 / 另存为都会被拒绝。"""
    print("\n=== 15. 演示项目只读保护 ===")
    import tkinter as tk

    from app.core import demo
    from app.ui import main_window as mw

    demo_path = demo.demo_project_path()
    check("演示项目被识别为受保护", demo.is_demo(demo_path), f"实际 {demo_path}")
    check("仓库里的示例不算演示项目",
          not demo.is_demo(ROOT / "demo" / "feasibility" / "demo.jianpack"))

    if demo_path is None or not Path(demo_path).is_file():
        check("演示项目存在", False, "没有可用的演示项目")
        return

    original_info = mw.messagebox.showinfo
    original_ask = mw.messagebox.askyesno
    original_saveas = mw.filedialog.asksaveasfilename
    calls = {"save_as": False}
    mw.messagebox.showinfo = lambda *a, **k: None
    mw.messagebox.askyesno = lambda *a, **k: False     # 不新建工程
    mw.filedialog.asksaveasfilename = (
        lambda **k: (calls.__setitem__("save_as", True), "")[1])

    window = None
    try:
        window = mw.MainWindow(str(demo_path))         # 打开时应弹一次提醒（已被替换）
        wait_loaded(window)
        window.withdraw()
        window.update()
        check("打开演示项目后进入只读状态", window._is_demo())

        before = Path(demo_path).stat().st_mtime_ns
        window.save()
        check("演示项目拒绝保存（文件没被改动）",
              Path(demo_path).stat().st_mtime_ns == before)
        window.save_as()
        check("演示项目拒绝另存为（没弹保存对话框）", not calls["save_as"])
    finally:
        mw.messagebox.showinfo = original_info
        mw.messagebox.askyesno = original_ask
        mw.filedialog.asksaveasfilename = original_saveas
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass


def test_tutorial(work: Path) -> None:
    """帮助 → 教程：窗口能开、不阻塞主窗口、章节和配图都在。"""
    print("\n=== 12. 使用教程窗口 ===")
    import tkinter as tk

    from app.ui import tutorial
    from app.ui.main_window import MainWindow

    window = MainWindow(str(work / DEMO.name))
    wait_loaded(window)
    window.withdraw()
    window.update()
    try:
        menubar = window.nametowidget(window.cget("menu"))
        labels: list[str] = []
        for i in range(menubar.index("end") + 1):
            try:
                labels.append(menubar.entrycget(i, "label"))
            except tk.TclError:
                labels.append("")
        help_menu = window.nametowidget(menubar.entrycget(labels.index("帮助"), "menu"))
        items: list[str] = []
        for i in range(help_menu.index("end") + 1):
            try:
                items.append(help_menu.entrycget(i, "label"))
            except tk.TclError:
                items.append("")
        check("帮助菜单里有「教程」", "教程" in items, f"实际 {items}")

        dirty_before = window.app.dirty
        window_tut = window.open_tutorial()
        window.update()
        check("教程窗口被创建出来", bool(window_tut.winfo_exists()))
        check("教程是非模态的（没有抢主窗口的操作权）",
              window_tut.grab_current() is None)
        check("重复点「教程」只开一个窗口", window.open_tutorial() is window_tut)
        check("章节目录和内容对得上",
              len(window_tut.toc.get_children()) == len(tutorial.CHAPTERS)
              and len(tutorial.CHAPTERS) >= 5,
              f"实际 {len(window_tut.toc.get_children())} 个")

        counts = []
        for index in range(len(tutorial.CHAPTERS)):
            window_tut._select_chapter(index)
            window.update()
            counts.append(len(window_tut.inner.winfo_children()))
        check("每一章都能渲染出内容", all(n > 0 for n in counts), f"{counts}")

        missing = [block[1] for chapter in tutorial.CHAPTERS
                   for block in chapter["blocks"]
                   if block[0] == "image"
                   and not (tutorial.asset_root() / block[1]).is_file()]
        check("教程配图都在", not missing, f"缺少 {missing}")

        from app import i18n
        i18n.set_language("en")
        en_root = tutorial.asset_root()
        missing_en = [block[1] for chapter in tutorial.CHAPTERS
                      for block in chapter["blocks"]
                      if block[0] == "image" and not (en_root / block[1]).is_file()]
        check("英文教程配图都在（切英文时自动用英文那套）",
              en_root.name == "en" and not missing_en, f"{en_root}，缺少 {missing_en}")
        i18n.set_language("zh")

        check("打开教程不会弄脏工程", window.app.dirty == dirty_before)

        # 关掉之后还能再开
        window_tut.destroy()
        window.update()
        again = window.open_tutorial()
        window.update()
        check("关掉教程后可以重新打开", bool(again.winfo_exists()))
    finally:
        try:
            window.destroy()
        except tk.TclError:
            pass


def test_startup_ui(work: Path) -> None:
    """欢迎页、首选项、深浅主题、以及「打包内容」这个改名。"""
    print("\n=== 13. 欢迎页 / 首选项 / 主题 / 改名 ===")
    import tkinter as tk

    from app.core.settings import Settings, load_settings, save_settings
    from app import i18n
    from app.ui import theme
    from app.ui.main_window import MainWindow
    from app.ui.pages.files import FilesPage
    from app.ui.preferences_dialog import PreferencesDialog
    from app.ui.welcome_dialog import WelcomeDialog

    check("第 2 步叫「打包内容」", FilesPage.title == "打包内容",
          f"实际 {FilesPage.title!r}")
    check("短名 / 全称正确",
          i18n.app_name() == "简包装"
          and i18n.app_full_name() == "简包装-应用安装向导打包软件",
          f"实际 {i18n.app_name()!r} / {i18n.app_full_name()!r}")

    # --- 设置项：默认值、存读、初始化
    defaults = Settings()
    check("默认是浅色 + 显示欢迎页",
          defaults.theme == "light" and defaults.show_welcome is True
          and defaults.auto_open_last is False)

    changed = Settings()
    changed.theme = "dark"
    changed.language = "en"
    changed.show_welcome = False
    changed.auto_open_last = True
    changed.remember("D:\\某处\\我的软件.jianpack")
    save_settings(changed)
    loaded = load_settings()
    check("新设置项能存下来并读回",
          loaded.theme == "dark" and loaded.language == "en"
          and loaded.show_welcome is False
          and loaded.auto_open_last is True and bool(loaded.recent))

    loaded.reset()
    check("「恢复默认设置」清空记录并还原选项",
          loaded.recent == [] and loaded.theme == "light" and loaded.language == "zh"
          and loaded.show_welcome is True and loaded.auto_open_last is False)
    save_settings(loaded)          # 磁盘恢复默认，后面的窗口才是中文浅色

    # 翻译表：抽查几个术语，确认中英一致
    i18n.set_language("en")
    check("英文翻译可用（术语一致）",
          i18n.t("打包内容") == "Payload"
          and i18n.t("首选项/设置") == "Preferences/Settings"
          and i18n.t("安装设置") == "Install Settings")
    i18n.set_language("zh")
    check("中文直接返回原文", i18n.t("打包内容") == "打包内容")

    window = MainWindow(str(work / DEMO.name))
    wait_loaded(window)
    window.withdraw()
    window.update()
    try:
        menubar = window.nametowidget(window.cget("menu"))
        check("主菜单最后一项是「首选项/设置」",
              menubar.entrycget("end", "label") == "首选项/设置",
              f"实际 {menubar.entrycget('end', 'label')!r}")

        values = window.step_list.item("1", "values")
        check("步骤列表里第 2 步显示为「打包内容」",
              bool(values) and values[0].endswith("打包内容"), f"实际 {values!r}")

        # --- 欢迎页
        window.settings.show_welcome = True
        welcome = WelcomeDialog(window, window.settings)
        window.update()
        check("欢迎页默认不勾「不再显示」", welcome._remember.get() is False)
        welcome._tutorial()
        window.update()
        check("点「打开教程」会记下并关闭窗口",
              welcome.open_tutorial is True and not welcome.winfo_exists())

        welcome2 = WelcomeDialog(window, window.settings)
        welcome2._remember.set(True)
        welcome2._close()
        window.update()
        check("勾「不再显示」后设置被写盘", window.settings.show_welcome is False)

        # 欢迎页左下角的「中/en」按钮：记下目标语言并关闭
        i18n.set_language("zh")
        welcome3 = WelcomeDialog(window, window.settings)
        window.update()
        welcome3._toggle_language()
        check("欢迎页「中/en」按钮会切到英文",
              welcome3.switch_language == "en" and not welcome3.winfo_exists())

        # --- 首选项
        window.settings.theme = "light"
        prefs = PreferencesDialog(window, window.settings)
        window.update()
        prefs.theme_var.set("dark")
        prefs.welcome_var.set(True)
        prefs._save()
        check("首选项保存后主题变为深色、需要重建界面",
              window.settings.theme == "dark" and prefs.saved and prefs.restart_needed)

        prefs2 = PreferencesDialog(window, window.settings)
        prefs2._cancel()
        check("首选项点取消不写入", prefs2.saved is False)

        # --- 启动窗口：第一行固定是演示项目
        from app.ui.start_dialog import StartDialog

        start = StartDialog(window, window.settings, modal=False)
        window.update()
        kids = start.tree.get_children()
        first = kids[0] if kids else None
        check("「最近打开」第一行固定是演示测试项目",
              first == "demo"
              and str(start.tree.item(first, "values")[0]).startswith("演示测试项目"),
              f"实际 {start.tree.item(first, 'values') if first else None}")
        if first is not None:
            start.tree.selection_set(first)
            start._sync_buttons()
            check("演示项目不能被「移除记录」移除",
                  start.forget_button.instate(["disabled"]))
            check("选中演示项目能拿到工程路径",
                  (start._selected_path() or "").endswith(".jianpack"))
        start.destroy()

        # --- 关于页：有可点击的主页 / 邮箱链接
        from app.ui.about_dialog import AboutDialog

        about = AboutDialog(window)
        window.update()
        links: list[str] = []

        def collect(widget) -> None:
            for child in widget.winfo_children():
                try:
                    if child.cget("cursor") == "hand2":
                        links.append(str(child.cget("text")))
                except tk.TclError:
                    pass
                collect(child)

        collect(about)
        check("关于页有可点击的主页 / 邮箱链接",
              "https://github.com/kllber" in links and "1394141383@qq.com" in links,
              f"实际 {links}")
        about.destroy()

        # --- 主题切换本身不该抛错
        theme.activate(window, "dark")
        check("启用深色后取到深色配色",
              theme.is_dark() and theme.c("window") == "#20242b")
        theme.activate(window, "light")
        check("切回浅色", not theme.is_dark())
    finally:
        try:
            window.destroy()
        except tk.TclError:
            pass


def _find_entry(widget, value: str):
    """在控件树里找那个内容等于 value 的输入框。"""
    import tkinter as tk
    from tkinter import ttk

    for child in widget.winfo_children():
        if isinstance(child, ttk.Entry):
            try:
                if child.get() == value:
                    return child
            except tk.TclError:
                pass
        found = _find_entry(child, value)
        if found is not None:
            return found
    return None


def test_validate_robustness(work: Path) -> None:
    """源文件缺失时，校验必须「报错」而不是把异常抛出去。"""
    print("\n=== 16. 校验的健壮性 ===")
    from app.checks import check_project, split
    from app.core.paths import desktop_dir
    from app.core.project import FileItem, Project
    from app.ui.new_project_dialog import NewProjectDialog

    project = Project(source_path=work / "missing-src.jianpack", base_dir=work)
    project.app.name = "源缺失的工程"
    project.app.version = "1.0.0"
    project.files.items = [FileItem(type="folder", source="并没有这个目录", dest=".")]
    project.app.main_exe = ""
    project.apply_derived()

    try:
        problems = check_project(project)
        check("源缺失时校验不抛异常", True)
    except Exception as exc:  # noqa: BLE001
        check("源缺失时校验不抛异常", False, repr(exc))
        return

    errors, _warnings = split(problems)
    check("并且报出阻断级错误", bool(errors), str(errors[:2]))

    class _Dialog:
        class settings:                     # noqa: N801 - 只要有个读得出来的属性即可
            new_project_dir = ""

    check("新建工程默认目录跟随系统桌面（含重定向）",
          Path(NewProjectDialog._default_dir(_Dialog())) == desktop_dir(),
          str(desktop_dir()))


def test_ime_function_key(work: Path) -> None:
    """中文输入法把字母误报成 F1/F5 时，快捷键不能被触发（CPython #125349）。"""
    print("\n=== 17. 输入法误报功能键的过滤 ===")
    import tkinter as tk

    from app.ui.main_window import MainWindow

    window = MainWindow(str(work / DEMO.name))
    wait_loaded(window)
    window.withdraw()
    window.update()

    class _Event:
        def __init__(self, char: str = "", send_event: bool = False,
                     keycode: int = 0) -> None:
            self.char = char
            self.send_event = send_event
            self.keycode = keycode

    try:
        called: list[int] = []
        handler = window._shortcut(lambda: called.append(1), 112)   # 就当是 F1
        handler(_Event(char="p"))            # 打 p + 回车会被错报成 F1，char="p"
        handler(_Event(char="t"))            # 打 t + 回车会被错报成 F5，char="t"
        handler(_Event(keycode=80))          # 键码是字母 P，不是 F1
        check("输入法误报的假功能键不触发快捷键", called == [], str(called))
        handler(_Event(keycode=112))         # 真正的功能键：char 空、键码对得上
        check("真实功能键事件正常触发", called == [1], str(called))
    finally:
        try:
            window.destroy()
        except tk.TclError:
            pass


def test_folder_payload_paths(work: Path) -> None:
    """文件夹条目要保留自己的名字（安装到 <dest>\\<文件夹名>\\...）。"""
    print("\n=== 18. 文件夹条目的安装路径 ===")
    from app.core.project import FileItem, Project
    from app.engine.nsi import NsiGenerator

    src = work / "payload-src" / "a"
    (src / "sub").mkdir(parents=True)
    (src / "r.txt").write_text("r", encoding="utf-8")
    (src / "sub" / "t.txt").write_text("t", encoding="utf-8")

    project = Project(source_path=work / "folder-dest.jianpack", base_dir=work)
    project.app.name = "路径测试"
    project.app.version = "1.0.0"
    project.files.items = [FileItem(type="folder", source="payload-src/a", dest=".")]
    project.apply_derived()

    dests = sorted(d for _p, d in project.iter_payload())
    check("放到根部时，文件夹名被保留", dests == ["a/r.txt", "a/sub/t.txt"], str(dests))

    text = NsiGenerator(project, "perMachine", work / "build-folder").generate("x.exe")
    check("生成的脚本把文件夹名并进了 SetOutPath",
          'SetOutPath "$INSTDIR\\a"' in text, "")

    project.files.items = [FileItem(type="folder", source="payload-src/a", dest="docs")]
    dests = sorted(d for _p, d in project.iter_payload())
    check("指定「安装到」时，文件夹名拼在其后",
          dests == ["docs/a/r.txt", "docs/a/sub/t.txt"], str(dests))
    text = NsiGenerator(project, "perMachine", work / "build-folder2").generate("x.exe")
    check("脚本里的 SetOutPath 也带上 docs\\a",
          'SetOutPath "$INSTDIR\\docs\\a"' in text, "")

    # 带 include / exclude 的文件夹（走逐文件列举那条路）
    project.files.items = [FileItem(type="folder", source="payload-src/a", dest=".",
                                    include=["*.txt"], exclude=[])]
    text = NsiGenerator(project, "perMachine", work / "build-folder3").generate("x.exe")
    check("带过滤条件的文件夹也保留文件夹名",
          'SetOutPath "$INSTDIR\\a"' in text
          and 'SetOutPath "$INSTDIR\\a\\sub"' in text, "")

    # 旧工程没有 keepFolder 字段时按「保留」处理（向后兼容）
    check("旧工程缺 keepFolder 时默认保留",
          FileItem.from_dict({"type": "folder", "source": "x"}, "t").keep_folder is True)

    # 取消「保留文件夹名」：内容直接摊到「安装到」目录
    project.files.items = [FileItem(type="folder", source="payload-src/a", dest=".",
                                    keep_folder=False)]
    dests = sorted(d for _p, d in project.iter_payload())
    check("取消保留时，内容摊到目标目录", dests == ["r.txt", "sub/t.txt"], str(dests))
    text = NsiGenerator(project, "perMachine", work / "build-folder4").generate("x.exe")
    check("取消保留后脚本里不再出现 $INSTDIR\\a",
          'SetOutPath "$INSTDIR"' in text and '$INSTDIR\\a' not in text, "")

    # 带过滤 + 取消保留
    project.files.items = [FileItem(type="folder", source="payload-src/a", dest=".",
                                    keep_folder=False, include=["*.txt"])]
    dests = sorted(d for _p, d in project.iter_payload())
    check("取消保留 + 过滤时路径正确", dests == ["r.txt", "sub/t.txt"], str(dests))

    # 存取无损：keepFolder 能写出去、读回来
    from app.core.project import load_project
    from app.core.serialize import save_project

    target = work / "keep-roundtrip.jianpack"
    save_project(project, target)
    reloaded = load_project(target)
    try:
        check("keepFolder=false 能保存并读回",
              reloaded.files.items[0].keep_folder is False)
    finally:
        reloaded.cleanup()


def test_remove_payload_cleanup(work: Path) -> None:
    """移除条目时，工程内的 payload 副本要被正确识别并（在保存后）真正消失。"""
    print("\n=== 19. 移除条目时清理工程内副本 ===")
    from app.core.project import FileItem, Project, load_project
    from app.core.serialize import save_project

    base = work / "cleanup"
    (base / "payload" / "a").mkdir(parents=True)
    (base / "payload" / "b").mkdir(parents=True)
    (base / "payload" / "a" / "r.txt").write_text("r", encoding="utf-8")
    (base / "payload" / "b" / "z.txt").write_text("z", encoding="utf-8")
    (base / "payload" / "ccc.exe").write_bytes(b"MZ")
    outside = work / "external" / "ext.txt"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("x", encoding="utf-8")

    def rel(paths):
        root = base.resolve()
        return sorted(p.relative_to(root).as_posix() for p in paths)

    project = Project(source_path=base / "p.jianpack", base_dir=base)
    project.app.name = "清理测试"
    project.app.version = "1.0.0"
    item_a = FileItem(type="folder", source="payload/a", dest=".")
    item_b = FileItem(type="folder", source="payload/b", dest=".")
    item_c = FileItem(type="file", source="payload/ccc.exe", dest=".")
    item_ext = FileItem(type="file", source=str(outside), dest=".")
    project.files.items = [item_a, item_b, item_c, item_ext]

    check("工程内副本会被列出待删",
          rel(project.removable_payload_paths([item_a, item_c])) == ["payload/a", "payload/ccc.exe"])
    check("工程外引用不会被删", project.removable_payload_paths([item_ext]) == [])

    item_a2 = FileItem(type="folder", source="payload/a", dest="docs")
    project.files.items = [item_a, item_a2]
    check("仍被其它条目引用时不删", project.removable_payload_paths([item_a]) == [])

    (base / "payload" / "许可.txt").write_text("x", encoding="utf-8")
    lic = FileItem(type="file", source="payload/许可.txt", dest=".")
    project.files.items = [lic]
    project.interface.license.enabled = True
    project.interface.license.source = "file"
    project.interface.license.file = "payload/许可.txt"
    check("协议页还在引用时不删", project.removable_payload_paths([lic]) == [])

    # 完整链路：删条目 + 删副本 -> 存成单文件工程 -> 重新打开，副本确实没了
    project.interface.license.enabled = False
    project.interface.license.file = None
    project.files.items = [item_a, item_b, item_c]
    for path in project.removable_payload_paths([item_a, item_c]):
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    for item in (item_a, item_c):
        project.files.items.remove(item)
    target = work / "cleanup-roundtrip.jianpack"
    save_project(project, target, container_mode=True)
    project.cleanup()

    again = load_project(target)
    try:
        names = {p.relative_to(again.base_dir).as_posix()
                 for p in (again.base_dir / "payload").rglob("*") if p.is_file()}
        check("保存后工程里确实没有那些副本了",
              "payload/a/r.txt" not in names and "payload/ccc.exe" not in names
              and "payload/b/z.txt" in names, str(sorted(names)))
    finally:
        again.cleanup()


def test_splash_and_progress(work: Path) -> None:
    """打开工程时的加载提示：解压进度回调 + 加载窗出现/自动关闭。"""
    print("\n=== 20. 打开工程时的加载提示 ===")
    import tkinter as tk

    from app.core import container, demo
    from app.ui.main_window import MainWindow

    bundled = demo.bundled_demo_path()
    if bundled is not None:
        seen: list[tuple[int, int]] = []
        container.extract(bundled, work / "splash-unz",
                          progress=lambda done, total, name: seen.append((done, total)))
        check("解压会回调进度且计数到位",
              bool(seen) and seen[0][0] == 1 and seen[-1][0] == seen[-1][1],
              f"{seen[:1]}..{seen[-1:]}")
    else:
        check("解压会回调进度（缺演示工程，跳过）", True)

    window = MainWindow(str(work / DEMO.name))
    try:
        check("打开工程时会先显示加载窗", window._splash is not None)
        wait_loaded(window)
        check("加载完成后加载窗自动关闭", window._splash is None)
        check("工程确实加载好了", window.app.project is not None)
    finally:
        try:
            window.destroy()
        except tk.TclError:
            pass


def test_progress_windows(work: Path) -> None:
    """加载窗「延迟显示」+ 打包进度窗的接线。"""
    print("\n=== 21. 加载窗延迟显示 / 打包进度窗 ===")
    import tkinter as tk

    import app.ui.main_window as mw
    from app.ui.main_window import MainWindow

    shown: list[int] = []
    orig_splash = mw.Splash

    class RecSplash(orig_splash):
        def show(self) -> None:
            shown.append(1)
            super().show()

    mw.Splash = RecSplash
    window = None
    try:
        window = MainWindow(str(work / DEMO.name))
        wait_loaded(window)
        check("小工程打开不弹加载窗（不闪一下）", shown == [], str(shown))
        check("加载完成后加载窗已清理", window._splash is None)

        panel = window.build_panel             # 左栏常驻的「开始打包」
        panel._open_progress(2)
        check("能创建打包进度窗", panel._progress_window is not None)
        check("打包进度条是来回滚动的（不会看起来卡住）",
              panel._progress_window is not None
              and str(panel._progress_window.bar.cget("mode")) == "indeterminate")
        panel._update_progress(1, 2, "正在打包…（1/2）", "Out.exe")
        panel._close_progress()
        check("能关闭打包进度窗", panel._progress_window is None)
    finally:
        mw.Splash = orig_splash
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass


def test_gate_options(work: Path) -> None:
    """父级选项不勾选时，子级选项要变灰不可编辑（勾回来恢复）。"""
    print("\n=== 22. 父项不勾选时子项变灰 ===")
    import tkinter as tk

    from app.ui.main_window import MainWindow

    def find(widget, text):
        for child in widget.winfo_children():
            try:
                label = child.cget("text")
            except tk.TclError:
                label = None
            if label == text:
                return child
            found = find(child, text)
            if found is not None:
                return found
        return None

    def off(widget) -> bool:
        return widget is not None and bool(widget.instate(["disabled"]))

    window = MainWindow(str(work / DEMO.name))
    wait_loaded(window)
    try:
        inter = window._pages[3]                     # 安装界面
        cb = find(inter, "显示许可协议页")
        check("找到「显示许可协议页」", cb is not None)
        check("默认勾选时子项可用", not off(find(inter, "直接在下面编辑")))
        cb.invoke(); window.update()
        check("取消勾选后子项变灰", off(find(inter, "直接在下面编辑")))
        cb.invoke(); window.update()
        check("勾回来后子项恢复", not off(find(inter, "直接在下面编辑")))

        sc = inter                                  # 快捷方式已并入第 4 步
        desk = find(sc, "启用桌面快捷方式")
        desk.invoke(); window.update()
        check("取消桌面快捷方式后子项变灰", off(find(sc, "默认勾选")))
        desk.invoke(); window.update()
        check("勾回来后子项恢复", not off(find(sc, "默认勾选")))
    finally:
        try:
            window.destroy()
        except tk.TclError:
            pass


def test_cache_buttons(work: Path) -> None:
    """首选项里的「用默认位置」只清路径；「清空缓存文件…」只删本软件的临时工程。"""
    print("\n=== 23. 首选项里的缓存按钮 ===")
    import tkinter as tk

    from app.core import container
    from app.core.settings import load_settings, save_settings
    from app.ui import preferences_dialog as pref

    def find(widget, text):
        for child in widget.winfo_children():
            try:
                label = child.cget("text")
            except tk.TclError:
                label = None
            if label == text:
                return child
            got = find(child, text)
            if got is not None:
                return got
        return None

    cache = work / "pref-cache"
    cache.mkdir(exist_ok=True)
    keep = cache / (container.WORK_PREFIX + "inuse")
    drop = cache / (container.WORK_PREFIX + "dropme")
    foreign = cache / "not-ours"
    for path in (keep, drop, foreign):
        path.mkdir(exist_ok=True)
    (foreign / "x.txt").write_text("x", encoding="utf-8")

    settings = load_settings()
    old_cache = settings.cache_dir
    settings.cache_dir = str(cache)
    save_settings(settings)

    class _Project:
        work_dir = keep          # 假装当前工程正在用它

    class _State:
        project = _Project()

    root = tk.Tk()
    root.withdraw()
    root.app = _State()
    orig_yes = pref.messagebox.askyesno
    orig_info = pref.messagebox.showinfo
    pref.messagebox.askyesno = lambda *a, **k: True
    pref.messagebox.showinfo = lambda *a, **k: None
    try:
        dialog = pref.PreferencesDialog(root, load_settings())
        root.update()
        btn_default = find(dialog, "用默认位置")
        check("有「用默认位置」按钮", btn_default is not None)
        btn_default.invoke(); root.update()
        check("「用默认位置」清空自定义路径", dialog.cache_var.get() == "")

        btn_clear = find(dialog, "清空缓存文件…")
        check("有「清空缓存文件…」按钮", btn_clear is not None)
        btn_clear.invoke(); root.update()
        check("本软件的临时工程被清掉", not drop.exists())
        check("正在使用的那个被跳过", keep.exists())
        check("别人放进缓存的东西不动", (foreign / "x.txt").is_file())
        dialog.destroy()
    finally:
        pref.messagebox.askyesno = orig_yes
        pref.messagebox.showinfo = orig_info
        root.destroy()
        settings.cache_dir = old_cache
        save_settings(settings)


def main() -> int:
    work = make_workspace()
    # 把「本软件的设置 / 数据目录」也引到临时目录 —— 否则自检会往真实的
    # 软件目录里写 settings.json、在临时目录里留缓存工程。
    os.environ["APPDATA"] = str(work / "appdata")
    os.environ["AIPACK_HOME"] = str(work / "apphome")

    print("临时工作目录:", work)
    try:
        test_plain_roundtrip(work)
        test_gui_roundtrip(work)
        test_tolerate_broken_bool(work)
        test_new_project_names(work)
        test_start_flow(work)
        test_no_flash(work)
        test_image_pipeline(work)
        test_derived_registry_key(work)
        test_validate_robustness(work)
        test_inline_text_pages(work)
        test_preview(work)
        test_no_maximize(work)
        test_tutorial(work)
        test_container(work)
        test_demo_readonly(work)
        test_startup_ui(work)
        test_ime_function_key(work)
        test_folder_payload_paths(work)
        test_remove_payload_cleanup(work)
        test_splash_and_progress(work)
        test_progress_windows(work)
        test_gate_options(work)
        test_cache_buttons(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print()
    if _failed:
        print(f"有 {_failed} 项没通过。")
        return 1
    print("全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
