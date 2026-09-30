"""步骤页基类。

约定很简单：
- 页面在构造时把控件绑到模型字段上；
- 切走时主窗口调 :meth:`flush`，把控件里的值写回模型；
- 切回来时调 :meth:`on_enter`，需要重新读模型的页面覆写它。

这样「模型永远是唯一的真相」，也不用给每个字段写两遍同步代码。
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

from .. import theme
from ... import i18n
from ...i18n import t as _
from ..widgets import APP_FONT, ScrollFrame, TITLE_FONT, hint_label, keep_wheel_inside


class StepPage(ttk.Frame):
    title = ""
    subtitle = ""
    description = ""      # 左侧步骤列表里的一句话说明

    # 页面宽度超过这个值，分组框就排成两列
    TWO_COLUMN_MIN_WIDTH = 1300

    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app
        self._flush_actions: list[Callable[[], None]] = []
        self._enter_actions: list[Callable[[], None]] = []
        self._images: dict[str, object] = {}
        self._last_radio_var: tk.StringVar | None = None
        self._sections: list[ttk.LabelFrame] = []
        self._section_box: ttk.Frame | None = None
        self._two_columns = False

        header = ttk.Frame(self)
        header.pack(fill="x", padx=20, pady=(16, 0))
        ttk.Label(header, text=_(self.title), font=TITLE_FONT,
                  foreground=theme.c("accent")).pack(anchor="w")
        if self.subtitle:
            ttk.Label(header, text=_(self.subtitle), foreground=theme.c("hint"),
                      font=APP_FONT).pack(anchor="w", pady=(3, 0))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=(10, 0))

        self.body = ScrollFrame(self)
        self.body.pack(fill="both", expand=True)

        self.form = ttk.Frame(self.body.inner)
        self.form.pack(fill="both", expand=True, padx=20, pady=12)

        # 页面是用 place(relwidth=1) 铺满容器的，尺寸只随窗口变，
        # 不会因为内容变化而触发 —— 拿它来决定单列还是两列是安全的。
        self.bind("<Configure>", self._on_resize, add="+")

        self.build(self.form)

    # -- 分组框 -------------------------------------------------------------

    def section(self, _parent, title: str) -> ttk.LabelFrame:
        """建一个分组框。

        宽屏时分组会自动排成两列 —— 既用上了宽度，输入框也不会被拉成
        一条长线，页面高度还能省一半。
        """
        frame = ttk.LabelFrame(self._section_host(), text=" " + _(title) + " ",
                               padding=(12, 8, 12, 10))
        self._sections.append(frame)
        self._place_sections()
        return frame

    def _section_host(self) -> ttk.Frame:
        # 懒创建：在它之前 pack 的提示文字还在上面，之后 pack 的子标签页
        # 还在下面 —— 页面原有的顺序不会被打乱。
        if self._section_box is None:
            self._section_box = ttk.Frame(self.form)
            self._section_box.pack(fill="x")
        return self._section_box

    def _place_sections(self) -> None:
        if self._section_box is None:
            return
        two = self._two_columns and len(self._sections) > 1
        self._section_box.columnconfigure(0, weight=1)
        self._section_box.columnconfigure(1, weight=1 if two else 0)

        for frame in self._sections:
            frame.pack_forget()
            frame.grid_forget()

        count = len(self._sections)
        for index, frame in enumerate(self._sections):
            if not two:
                frame.pack(fill="x", pady=(6, 10))
                continue
            row, column = divmod(index, 2)
            # 奇数个分组时，最后那个横跨两列，免得右边空一块
            span = 2 if (count % 2 == 1 and index == count - 1) else 1
            frame.grid(row=row, column=column, columnspan=span, sticky="new",
                       padx=(0, 0 if span == 2 else 12), pady=(6, 10))

    def _on_resize(self, event) -> None:
        wide = event.width >= self.TWO_COLUMN_MIN_WIDTH
        if wide != self._two_columns:
            self._two_columns = wide
            self._place_sections()
            self.body.sync_scrollregion()

    # -- 按父选项启用 / 禁用子选项 -------------------------------------------

    def gate(self, container, should_enable, watch=None) -> None:
        """按 ``should_enable()`` 的真假，启用 / 禁用 ``container`` 里的控件。

        父选项没勾时，把子选项变灰不可编辑（文字也跟着变灰），让用户一眼看出
        「要先勾上上面那个，这些才生效」。``watch`` 里的变量一变就重新判断；
        每次切回本页也会重新判断一次。

        注意：变灰只是**不让编辑**，值仍然保存在工程里（重新勾上不用重填）。
        """
        def apply(*_args) -> None:
            self._set_enabled(container, bool(should_enable()))

        for var in (watch or []):
            var.trace_add("write", apply)
        self._enter_actions.append(apply)
        apply()

    def _set_enabled(self, widget, on: bool) -> None:
        for child in widget.winfo_children():
            try:
                if isinstance(child, (ttk.Entry, ttk.Combobox, ttk.Button,
                                      ttk.Checkbutton, ttk.Radiobutton,
                                      ttk.Scale, ttk.Spinbox)):
                    child.state(["!disabled"] if on else ["disabled"])
                elif isinstance(child, tk.Text):
                    child.configure(state="normal" if on else "disabled",
                                    background=theme.c("field") if on else theme.c("thumb"))
                elif isinstance(child, (ttk.Label, tk.Label)):
                    # 记住原来的前景色，重新启用时原样还回去（提示文字本来就是灰的）
                    if not hasattr(child, "_jc_fg"):
                        child._jc_fg = child.cget("foreground") or theme.c("text")
                    child.configure(foreground=child._jc_fg if on else theme.c("hint"))
            except tk.TclError:
                pass
            self._set_enabled(child, on)

    # -- 子类实现 -----------------------------------------------------------

    def build(self, parent: ttk.Frame) -> None:  # pragma: no cover - 由子类覆写
        raise NotImplementedError

    def on_enter(self) -> None:
        """切回本页时调用。图片字段之类的回填动作在这里跑。"""
        for action in self._enter_actions:
            action()

    # -- 同步 ---------------------------------------------------------------

    def flush(self) -> None:
        """把控件里的值写回模型。"""
        for action in self._flush_actions:
            action()

    # -- 控件工厂 -----------------------------------------------------------

    def _row(self, parent, label: str, label_width: int = 15) -> ttk.Frame:
        holder = ttk.Frame(parent)
        holder.pack(fill="x", pady=3)
        # 英文标签更长，留宽一点，免得被截断（布局本来就是靠右侧输入框自适应）
        width = label_width + (7 if i18n.is_english() else 0)
        ttk.Label(holder, text=_(label), width=width, anchor="nw",
                  font=APP_FONT).pack(side="left")
        column = ttk.Frame(holder)
        column.pack(side="left", fill="x", expand=True)
        return column

    def text(self, parent, label: str, obj, attr: str, hint: str = "",
             width: int = 52, height: int = 0, label_width: int = 15):
        column = self._row(parent, label, label_width)
        value = getattr(obj, attr) or ""

        if height:
            widget = tk.Text(column, height=height, wrap="word", font=APP_FONT,
                             relief="solid", borderwidth=1, undo=True, width=1,
                             background=theme.c("field"), foreground=theme.c("text"),
                             insertbackground=theme.c("text"))
            widget.insert("1.0", value)
            widget.pack(fill="x")
            # 滚轮只滚这个文本框自己，别把外层可滚动页面也带着滚
            keep_wheel_inside(widget)
            widget.bind("<KeyRelease>", lambda _e: self.app.touch())
            self._flush_actions.append(
                lambda: setattr(obj, attr, widget.get("1.0", "end-1c")))
            if hint:
                hint_label(column, hint, pady=(2, 0))
            return widget

        var = tk.StringVar(value=value)
        ttk.Entry(column, textvariable=var, width=width).pack(fill="x")
        var.trace_add("write", lambda *_: self.app.touch())
        self._flush_actions.append(lambda: setattr(obj, attr, var.get().strip()))
        if hint:
            hint_label(column, hint, pady=(2, 0))
        return var

    def check(self, parent, label: str, obj, attr: str, hint: str = "") -> tk.BooleanVar:
        var = tk.BooleanVar(value=bool(getattr(obj, attr)))
        ttk.Checkbutton(parent, text=_(label), variable=var).pack(anchor="w", pady=2)
        var.trace_add("write", lambda *_: self.app.touch())
        self._flush_actions.append(lambda: setattr(obj, attr, bool(var.get())))
        if hint:
            # 先翻再缩进：hint_label 是按整串查表的，前面加空格会查不到
            hint_label(parent, "      " + _(hint))
        return var

    def radio(self, parent, label: str, obj, attr: str,
              options: list[tuple[object, str]], hint: str = "",
              on_change: Callable[[object], None] | None = None) -> tk.StringVar:
        """单选按钮组。

        注意：Tk 的变量只能存字符串，所以这里用「显示文本」当中间值，
        写回模型时再映射回原始取值——否则 ``True`` 会被存成 ``"1"``、
        ``False`` 会变成 ``"0"``，保存出来的工程文件就坏了。

        ``on_change`` 会拿到**原始取值**（而不是显示文本），方便页面据此联动。
        """
        column = self._row(parent, label)
        current = getattr(obj, attr)
        values = [value for value, _label in options]
        texts = [_(text) for _value, text in options]

        var = tk.StringVar(value=texts[values.index(current)] if current in values else texts[0])
        for text in texts:
            ttk.Radiobutton(column, text=text, value=text, variable=var).pack(anchor="w", pady=1)

        def selected() -> object:
            chosen = var.get()
            return values[texts.index(chosen)] if chosen in texts else current

        def changed(*_args) -> None:
            self.app.touch()
            if on_change is not None:
                on_change(selected())

        var.trace_add("write", changed)
        self._flush_actions.append(lambda: setattr(obj, attr, selected()))
        self._last_radio_var = var          # 供页面里的联动逻辑使用
        if hint:
            hint_label(column, hint, pady=(3, 0))
        return var

    def combo(self, parent, label: str, obj, attr: str,
              options: list[tuple[str, str]], hint: str = "",
              width: int = 32, label_width: int = 15) -> tk.StringVar:
        column = self._row(parent, label, label_width)
        value_to_text = {value: _(text) for value, text in options}
        text_to_value = {_(text): value for value, text in options}
        var = tk.StringVar(value=value_to_text.get(getattr(obj, attr), ""))

        ttk.Combobox(column, textvariable=var, state="readonly", width=width,
                     values=[_(text) for _value, text in options]).pack(anchor="w")

        def flush() -> None:
            setattr(obj, attr, text_to_value.get(var.get(), getattr(obj, attr)))

        var.trace_add("write", lambda *_: self.app.touch())
        self._flush_actions.append(flush)
        if hint:
            hint_label(column, hint, pady=(2, 0))
        return var

    def path(self, parent, label: str, obj, attr: str, mode: str = "file",
             patterns: list[tuple[str, str]] | None = None, hint: str = "",
             import_subdir: str | None = None, label_width: int = 15,
             optional: bool = True):
        column = self._row(parent, label, label_width)
        line = ttk.Frame(column)
        line.pack(fill="x")

        var = tk.StringVar(value=getattr(obj, attr) or "")
        ttk.Entry(line, textvariable=var).pack(side="left", fill="x", expand=True)

        def _filetypes() -> list[tuple[str, str]]:
            pairs = patterns or [("所有文件", "*.*")]
            return [(_(name), pattern) for name, pattern in pairs]

        def browse() -> None:
            top = self.winfo_toplevel()
            if mode == "dir":
                chosen = filedialog.askdirectory(parent=top, title=_("选择文件夹"))
            elif mode == "save":
                chosen = filedialog.asksaveasfilename(
                    parent=top, title=_("保存为"), filetypes=_filetypes())
            else:
                chosen = filedialog.askopenfilename(
                    parent=top, title=_("选择文件"), filetypes=_filetypes())
            if not chosen:
                return
            if import_subdir:
                relative = self.app.import_path(top, chosen, import_subdir)
                if relative is None:
                    return
                var.set(relative)
            else:
                var.set(self.app.relative_display(chosen))
            self.app.touch()

        def clear() -> None:
            var.set("")
            self.app.touch()

        ttk.Button(line, text=_("浏览…"), width=8, command=browse).pack(side="left", padx=(6, 0))
        if optional:
            ttk.Button(line, text=_("清除"), width=6, command=clear).pack(side="left", padx=(4, 0))

        var.trace_add("write", lambda *_: self.app.touch())
        self._flush_actions.append(
            lambda: setattr(obj, attr,
                            (var.get().strip() or None) if optional else var.get().strip()))
        if hint:
            hint_label(column, hint, pady=(2, 0))
        return var

    def image_field(self, parent, label: str, obj, attr: str, target_key: str,
                    hint: str = "", label_width: int = 15):
        """图片字段：带缩略图和尺寸校验，点「选择图片…」会弹出裁剪窗口。

        用户给什么格式都行（PNG / JPG / BMP…），裁完自动转成安装向导要求的
        BMP 或 .ico，存到工程的 ``assets\\`` 里，原图不动。
        """
        import tkinter as tk
        from tkinter import messagebox

        from ...core.errors import ProjectFileError
        from ...engine.assets import TARGETS, check_bitmap, check_icon, save_image
        from ..image_crop_dialog import IMAGE_TYPES, ImageCropDialog

        target = TARGETS[target_key]
        key = f"{id(obj)}:{attr}"
        column = self._row(parent, label, label_width)

        line = tk.Frame(column, background=theme.c("window"))
        line.pack(fill="x", anchor="w")

        # 注意：tk.Label 的 width/height 在显示**文字**时是「字符/行」，
        # 只有显示图片时才是像素。所以这里用固定像素尺寸的容器把缩略图框住，
        # 绝不能直接给 Label 设 width=96 —— 那会变成 96 个字宽，把页面撑爆。
        thumb_box = tk.Frame(line, width=96, height=54, background=theme.c("thumb"),
                             highlightbackground=theme.c("border"), highlightthickness=1)
        thumb_box.pack(side="left")
        thumb_box.pack_propagate(False)
        preview = tk.Label(thumb_box, background=theme.c("thumb"), foreground=theme.c("hint"),
                           font=("Microsoft YaHei UI", 8), text=_("未选择"))
        preview.pack(fill="both", expand=True)

        info = tk.Frame(line, background=theme.c("window"))
        info.pack(side="left", fill="x", expand=True, padx=(10, 0))
        status = ttk.Label(info, text="", foreground=theme.c("hint"), font=APP_FONT,
                           wraplength=360, justify="left")
        status.pack(anchor="w")
        detail = ttk.Label(info, text="", foreground=theme.c("hint"), font=APP_FONT,
                           wraplength=360, justify="left")
        detail.pack(anchor="w", pady=(2, 0))

        buttons = ttk.Frame(line)
        buttons.pack(side="right", padx=(10, 0))

        def refresh() -> None:
            relative = getattr(obj, attr)
            self._images.pop(key, None)
            status.configure(foreground=theme.c("hint"))
            detail.configure(foreground=theme.c("hint"))

            if not relative:
                preview.configure(image="", text=_("未选择"))
                status.configure(text=_("还没有选择图片"))
                detail.configure(text=_(target.hint))
                return

            path = self.app.base_dir / relative
            if not path.is_file():
                preview.configure(image="", text=_("找不到"))
                status.configure(text=_("找不到文件：{relative}").format(relative=relative),
                                 foreground=theme.c("danger"))
                detail.configure(text=_("重新选一张，或者点「清除」。"))
                return

            _put_thumbnail(self, preview, path, key)
            status.configure(text=relative)

            if target.kind == "bmp":
                message = check_bitmap(path, target.size, target.title)
            else:
                message = check_icon(path, target.title)
            if message:
                status.configure(foreground=theme.c("danger"))
                detail.configure(text=message)
            else:
                detail.configure(text=_("尺寸符合要求（{w} × {h}）").format(
                    w=target.size[0], h=target.size[1]))

        def pick() -> None:
            top = self.winfo_toplevel()
            chosen = filedialog.askopenfilename(
                parent=top, title=_("选择{title}").format(title=_(target.title)),
                filetypes=[(_(name), pattern) for name, pattern in IMAGE_TYPES])
            if not chosen:
                return
            try:
                dialog = ImageCropDialog(top, Path(chosen), target)
            except ProjectFileError as exc:
                messagebox.showerror(_("打不开这张图片"), str(exc), parent=top)
                return
            self.wait_window(dialog)
            if dialog.result is None:
                return

            dest = self.app.base_dir / "assets" / target.file_name
            try:
                save_image(dialog.result, dest, target)
            except ProjectFileError as exc:
                messagebox.showerror(_("保存失败"), str(exc), parent=top)
                return

            setattr(obj, attr, f"assets/{target.file_name}")
            refresh()
            self.app.touch()

        def clear() -> None:
            setattr(obj, attr, None)
            refresh()
            self.app.touch()

        ttk.Button(buttons, text=_("选择图片…"), width=11, command=pick).pack()
        ttk.Button(buttons, text=_("清除"), width=11, command=clear).pack(pady=(4, 0))

        if hint:
            hint_label(column, hint, pady=(4, 0))
        self._enter_actions.append(refresh)
        refresh()


def _put_thumbnail(page, widget, path: Path, key: str) -> None:
    """把图片缩进小预览框里。失败就退回文字，不让界面崩。

    只改 image / text，**不改 width / height** —— 那个在显示文字时是字符单位。
    """
    try:
        from PIL import Image, ImageTk

        with Image.open(path) as raw:
            image = raw.convert("RGBA")
        image.thumbnail((96, 54), Image.LANCZOS)
        backdrop = Image.new("RGB", image.size, theme.rgb("thumb"))
        backdrop.paste(image, (0, 0), image)
        photo = ImageTk.PhotoImage(backdrop)
        page._images[key] = photo          # 必须留引用，否则会被回收成空白
        widget.configure(image=photo, text="")
    except Exception:  # noqa: BLE001 - 缩略图失败不影响功能
        widget.configure(image="", text=_("(预览失败)"))
