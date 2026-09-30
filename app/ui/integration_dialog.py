"""「系统集成」里增删条目的通用小对话框。

字段用 ``(key, 标签, 类型)`` 描述，类型支持 ``text`` / ``combo`` / ``check``。
确定后结果放在 ``result``（dict），取消时为 ``None``。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme
from ..i18n import t as _
from .widgets import APP_FONT

BOLD = ("Microsoft YaHei UI", 10, "bold")


class EntryDialog(tk.Toplevel):
    def __init__(self, master, title: str, fields: list[dict],
                 values: dict | None = None) -> None:
        super().__init__(master)
        self.result: dict | None = None
        self._fields = fields
        self._vars: dict[str, tk.Variable] = {}

        self.title(title)
        self.resizable(False, False)
        self.configure(background=theme.c("panel"))
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())
        if master is not None and master.winfo_viewable():
            self.transient(master)

        self._build(values or {})
        self.update_idletasks()
        self._center()
        self.deiconify()
        self.lift()
        self.update()
        self.grab_set()
        self.focus_set()
        # 阻塞到用户点「确定 / 取消」为止：调用方都是构造完就直接读 result，
        # 不阻塞的话它们会在对话框还开着的时候就往下走（等于什么都没做）。
        self.wait_window(self)

    # -- 界面 ---------------------------------------------------------------

    def _build(self, values: dict) -> None:
        body = ttk.Frame(self, padding=(20, 16, 20, 0))
        body.pack(fill="both", expand=True)

        for field in self._fields:
            key = field["key"]
            ttk.Label(body, text=_(field["label"]), font=BOLD).pack(anchor="w", pady=(8, 2))
            current = values.get(key, field.get("default", ""))

            if field.get("kind") == "check":
                var: tk.Variable = tk.BooleanVar(value=bool(current))
                ttk.Checkbutton(body, variable=var).pack(anchor="w")
            elif field.get("kind") == "combo":
                options = field["options"]
                labels = {value: _(text) for value, text in options}
                var = tk.StringVar(value=labels.get(current, _(options[0][1])))
                var.value_map = {_(text): value for value, text in options}  # type: ignore[attr-defined]
                ttk.Combobox(body, textvariable=var, state="readonly", width=36,
                             values=[_(text) for _v, text in options]).pack(anchor="w")
            else:
                var = tk.StringVar(value=str(current or ""))
                ttk.Entry(body, textvariable=var, width=44).pack(anchor="w",
                                                                 fill="x", expand=True)

            if field.get("hint"):
                ttk.Label(body, text=_(field["hint"]), foreground=theme.c("hint"),
                          justify="left", wraplength=380,
                          font=("Microsoft YaHei UI", 8)).pack(anchor="w")
            self._vars[key] = var

        footer = ttk.Frame(self, padding=(20, 14, 20, 16))
        footer.pack(fill="x")
        ttk.Button(footer, text=_("确定"), width=12, command=self._ok).pack(side="right")
        ttk.Button(footer, text=_("取消"), width=10,
                   command=self._cancel).pack(side="right", padx=(0, 8))

    # -- 动作 ---------------------------------------------------------------

    def _ok(self) -> None:
        result: dict = {}
        for field in self._fields:
            key = field["key"]
            var = self._vars[key]
            if field.get("kind") == "combo":
                mapping = getattr(var, "value_map", {})
                result[key] = mapping.get(var.get(), var.get())
            elif field.get("kind") == "check":
                result[key] = bool(var.get())
            else:
                result[key] = str(var.get()).strip()
        self.result = result
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _center(self) -> None:
        width = max(self.winfo_reqwidth(), 440)
        height = self.winfo_reqheight()
        master = self.master
        if master is not None and master.winfo_viewable():
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = max(0, (self.winfo_screenheight() - height) // 2 - 60)
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
