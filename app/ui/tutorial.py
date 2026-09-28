"""「使用教程」窗口。

帮助菜单里的「教程」（``F1``）会打开这个**独立的非模态窗口**：左边是章节目录，
右边图文并茂地讲清楚软件是干什么的、怎么用、以及一些进阶技巧。

几个刻意的选择：

- **不调用 grab_set**：这是「边看边操作」的教程，主窗口必须保持可用；
- **独立窗口**（不 transient）：可以自由挪动，也可以被主窗口盖住；
- 配图是真实界面的截图 + 红圈 / 箭头标注，由 ``tools/make-tutorial-images.py`` 生成；
- 配图缺失时只显示占位提示，绝不让教程窗口打不开。
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .. import i18n
from ..i18n import t as _, app_name
from . import theme
from .tutorial_content import CHAPTERS
from .widgets import APP_FONT, TITLE_FONT, ScrollFrame

BOLD = ("Microsoft YaHei UI", 10, "bold")
CODE_FONT = ("Consolas", 10)


def asset_root() -> Path:
    """教程配图所在目录（源码运行和 PyInstaller 打包都适用）。

    英文界面对应 ``assets/tutorial/en/`` 下那套英文截图。
    """
    from ..core.paths import assets_root

    base = assets_root() / "tutorial"
    if i18n.is_english() and (base / "en").is_dir():
        return base / "en"
    return base


class TutorialWindow(tk.Toplevel):
    """图文教程窗口。"""

    WINDOW_W, WINDOW_H = 1180, 780
    TOC_W = 232
    MAX_IMAGE_W = 840          # 配图最多显示多宽（再宽就等比缩小）

    def __init__(self, master) -> None:
        super().__init__(master)
        self.title(_("使用教程") + " - " + app_name())
        self.configure(background=theme.c("panel"))
        self.minsize(760, 520)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._chapters = CHAPTERS
        self._current = 0
        self._images: dict[str, object] = {}     # 当前章节的 PhotoImage 引用
        self._cache: dict[tuple[str, int], object] = {}
        self._resize_job = None
        self._last_width = 0

        self._build()
        self._select_chapter(0)

        self.update_idletasks()
        self._center(master)
        self.deiconify()
        self.lift()
        self.focus_set()

    # -- 界面搭建 -----------------------------------------------------------

    def _build(self) -> None:
        header = tk.Frame(self, background=theme.c("accent"))
        header.pack(fill="x")
        tk.Label(header, text=_("使用教程"), background=theme.c("accent"), foreground="white",
                 font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w", padx=22, pady=(14, 0))
        tk.Label(header, text=_("从「这是什么」到「进阶技巧」，图文都在这了。"),
                 background=theme.c("accent"), foreground=theme.c("accent_soft"),
                 font=APP_FONT).pack(anchor="w", padx=22, pady=(3, 14))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, width=self.TOC_W, padding=(14, 14, 8, 14))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ttk.Label(left, text=_("章节目录"), font=TITLE_FONT,
                  foreground=theme.c("accent")).pack(anchor="w", pady=(0, 8))

        self.toc = ttk.Treeview(left, columns=("t",), show="tree",
                                selectmode="browse", height=len(self._chapters))
        self.toc.column("t", width=self.TOC_W - 40, stretch=True)
        self.toc.pack(fill="x")
        for index, chapter in enumerate(self._chapters):
            self.toc.insert("", "end", iid=str(index),
                            text=f"  {index + 1}. {_(chapter['title'])}")
        self.toc.bind("<<TreeviewSelect>>", self._on_toc)

        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=12)
        ttk.Label(left, foreground=theme.c("hint"), justify="left",
                  font=("Microsoft YaHei UI", 8), wraplength=self.TOC_W - 40,
                  text=_("配图是真实界面的截图加红圈标注，\n会随软件版本更新。")
                  ).pack(anchor="w")

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.content = ScrollFrame(right, padding=(0, 0, 4, 0))
        self.content.pack(fill="both", expand=True)
        self.inner = self.content.inner

        # 窗口变宽 / 变窄时，配图要重新按新宽度缩放（防抖一下，别拖边就重画）
        self.content.canvas.bind("<Configure>", self._on_content_resize, add="+")

        footer = ttk.Frame(self, padding=(20, 10, 20, 14))
        footer.pack(fill="x")
        ttk.Label(footer, foreground=theme.c("hint"), font=APP_FONT,
                  text=_("教程窗口不挡主界面，可以边看边操作。")).pack(side="left")
        ttk.Button(footer, text=_("关闭"), width=10,
                   command=self.destroy).pack(side="right")

    def _center(self, master) -> None:
        width = min(self.WINDOW_W, max(760, self.winfo_screenwidth() - 80))
        height = min(self.WINDOW_H, max(520, self.winfo_screenheight() - 80))
        if master is not None and master.winfo_viewable():
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 2
            x = max(0, min(x, self.winfo_screenwidth() - width))
            y = max(0, min(y, self.winfo_screenheight() - height))
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = max(0, (self.winfo_screenheight() - height) // 2 - 40)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # -- 章节切换 -----------------------------------------------------------

    def _on_toc(self, _event=None) -> None:
        selection = self.toc.selection()
        if not selection:
            return
        index = int(selection[0])
        if index != self._current:
            self._select_chapter(index)

    def _select_chapter(self, index: int) -> None:
        index = max(0, min(index, len(self._chapters) - 1))
        self._current = index
        self.toc.selection_set(str(index))
        self.toc.see(str(index))
        self._render(index, keep_scroll=0.0)

    # -- 配图 ---------------------------------------------------------------

    def _image_width(self) -> int:
        width = self.content.canvas.winfo_width()
        if width <= 1:
            return self.MAX_IMAGE_W
        return max(320, min(self.MAX_IMAGE_W, width - 26))

    def _photo(self, name: str, width: int):
        key = (name, width)
        if key in self._cache:
            return self._cache[key]

        path = asset_root() / name
        if not path.is_file():
            return None
        try:
            from PIL import Image, ImageTk

            with Image.open(path) as raw:
                image = raw.convert("RGB")
            if image.width > width:
                height = max(1, round(image.height * width / image.width))
                image = image.resize((width, height), Image.LANCZOS)
            photo = ImageTk.PhotoImage(image)
        except Exception:  # noqa: BLE001 - 配图坏了不该让教程打不开
            return None

        self._cache[key] = photo
        return photo

    # -- 渲染 ---------------------------------------------------------------

    def _on_content_resize(self, event) -> None:
        if abs(event.width - self._last_width) < 24:
            return
        self._last_width = event.width
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(180, self._rerender)

    def _rerender(self) -> None:
        self._resize_job = None
        position = self.content.canvas.yview()[0]
        self._render(self._current, keep_scroll=position)

    def destroy(self) -> None:
        """关窗口前把挂起的东西清掉。

        否则：① 防抖的 after 任务会在控件没了之后触发；
        ② ScrollFrame 是 ``bind_all`` 滚轮的，鼠标正停在教程上时关窗口，
         ``<Leave>`` 不一定来得及触发，会留下一个指向已销毁控件的全局绑定。
        """
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except tk.TclError:
                pass
            self._resize_job = None
        try:
            self.content.canvas.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        super().destroy()

    def _render(self, index: int, keep_scroll: float = 0.0) -> None:
        for child in self.inner.winfo_children():
            child.destroy()
        self._images.clear()

        width = self._image_width()
        chapter = self._chapters[index]

        for block in chapter["blocks"]:
            self._render_block(block, width)

        self.content.canvas.yview_moveto(keep_scroll)
        self.inner.update_idletasks()
        self.content.sync_scrollregion()

    def _render_block(self, block: tuple, width: int) -> None:
        kind = block[0]

        if kind == "h1":
            self._title_label(block[1], size=17)
        elif kind == "h2":
            self._title_label(block[1], size=12)
        elif kind == "p":
            self._paragraph(block[1], width)
        elif kind == "bullets":
            for item in block[1]:
                self._bullet(item, width)
        elif kind == "steps":
            for number, item in enumerate(block[1], start=1):
                self._bullet(item, width, marker=f"{number}.")
        elif kind == "note":
            self._note(block[1], width)
        elif kind == "code":
            self._code(block[1], width)
        elif kind == "table":
            self._table(block[1], block[2], width)
        elif kind == "image":
            self._image(block[1], block[2], width)

    def _title_label(self, text: str, size: int) -> None:
        ttk.Label(self.inner, text=_(text),
                  font=("Microsoft YaHei UI", size, "bold"),
                  foreground=theme.c("accent") if size >= 15 else theme.c("text"),
                  justify="left").pack(anchor="w", padx=24, pady=(18 if size >= 15 else 16, 6))

    def _paragraph(self, text: str, width: int) -> None:
        ttk.Label(self.inner, text=_(text), font=APP_FONT, justify="left",
                  wraplength=width).pack(anchor="w", padx=24, pady=5)

    def _bullet(self, text: str, width: int, marker: str = "•") -> None:
        row = ttk.Frame(self.inner)
        row.pack(fill="x", anchor="w", padx=24, pady=2)
        ttk.Label(row, text=marker, font=APP_FONT, foreground=theme.c("accent"),
                  width=2, anchor="n").pack(side="left")
        ttk.Label(row, text=_(text), font=APP_FONT, justify="left",
                  wraplength=width - 20).pack(side="left", fill="x")

    def _note(self, text: str, width: int) -> None:
        box = tk.Frame(self.inner, background=theme.c("note_bg"),
                       highlightbackground=theme.c("note_border"), highlightthickness=1)
        box.pack(fill="x", padx=24, pady=9)
        tk.Label(box, text=_("提示：") + _(text), background=theme.c("note_bg"),
                 foreground=theme.c("note_fg"),
                 font=APP_FONT, justify="left",
                 wraplength=width - 36).pack(anchor="w", padx=12, pady=9)

    def _code(self, text: str, width: int) -> None:
        box = tk.Frame(self.inner, background=theme.c("code_bg"),
                       highlightbackground=theme.c("code_border"), highlightthickness=1)
        box.pack(fill="x", padx=24, pady=9)
        tk.Label(box, text=text, background=theme.c("code_bg"),
                 foreground=theme.c("code_fg"),
                 font=CODE_FONT, justify="left",
                 wraplength=width - 36).pack(anchor="w", padx=12, pady=9)

    def _table(self, headers: list[str], rows: list[list[str]], width: int) -> None:
        frame = ttk.Frame(self.inner)
        frame.pack(anchor="w", padx=24, pady=9)

        for column, head in enumerate(headers):
            ttk.Label(frame, text=_(head), font=BOLD, foreground=theme.c("text"),
                      padding=(10, 6)).grid(row=0, column=column, sticky="w")
        ttk.Separator(frame, orient="horizontal").grid(
            row=1, column=0, columnspan=max(1, len(headers)), sticky="ew", pady=(0, 2))

        for r, row in enumerate(rows, start=2):
            for column, cell in enumerate(row):
                ttk.Label(frame, text=_(cell), font=APP_FONT,
                          padding=(10, 5)).grid(row=r, column=column, sticky="w")

    def _image(self, name: str, caption: str, width: int) -> None:
        holder = ttk.Frame(self.inner)
        holder.pack(anchor="w", padx=24, pady=(10, 16))

        photo = self._photo(name, width)
        if photo is not None:
            self._images[name] = photo
            label = tk.Label(holder, image=photo, borderwidth=1, relief="solid",
                             highlightthickness=0)
            label.pack(anchor="w")
        else:
            placeholder = tk.Frame(holder, height=110, background=theme.c("thumb"),
                                   highlightbackground=theme.c("border"), highlightthickness=1)
            placeholder.pack(anchor="w", fill="x")
            placeholder.pack_propagate(False)
            tk.Label(placeholder, text=_("（教程配图缺失：{name}）").format(name=name),
                     background=theme.c("thumb"), foreground=theme.c("hint"),
                     font=APP_FONT).pack(expand=True)

        ttk.Label(holder, text=_(caption), font=("Microsoft YaHei UI", 9),
                  foreground=theme.c("hint"), justify="left",
                  wraplength=width).pack(anchor="w", pady=(6, 0))
