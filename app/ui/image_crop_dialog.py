"""图片裁剪对话框。

用户丢进来一张随便什么格式的照片（PNG / JPG / BMP…），这里让他拖动、缩放，
框住想要的部分，程序再转成安装向导要求的那种 BMP（或 .ico）。

几个刻意的选择：
- **只做「铺满」不做「留边」**：这几个位置的图片尺寸是写死的，留白反而难看；
- **实时看效果**：右边永远显示导出后的真实样子，所见即所得；
- **原图不动**：裁剪结果另存到工程的 ``assets\\`` 里，用户选的原图不会被改。
"""

from __future__ import annotations

import math
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageTk

from ..engine.assets import ImageTarget, load_for_edit, render_target
from . import theme
from ..i18n import t as _
from .widgets import APP_FONT

BOLD = ("Microsoft YaHei UI", 10, "bold")

CANVAS_W = 540
CANVAS_H = 320
PAD = 18
ZOOM_STEPS = 1000
MAX_ZOOM_FACTOR = 8.0

IMAGE_TYPES = [
    ("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff"),
    ("所有文件", "*.*"),
]


class ImageCropDialog(tk.Toplevel):
    def __init__(self, master, source: Path, target: ImageTarget) -> None:
        super().__init__(master)
        self.target = target
        self.source = Path(source)
        # 确定后是裁剪好的 PIL 图片，取消是 None
        self.result: Image.Image | None = None

        self.work, self.original_size = load_for_edit(self.source)

        self._photo = None
        self._preview_photo = None
        self._image_item: int | None = None
        self._drag: tuple[int, int, float, float] | None = None
        self._syncing = False

        self.title(_("调整") + _(target.title))
        self.resizable(False, False)
        self.configure(background=theme.c("panel"))
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

        if master is not None and master.winfo_viewable():
            self.transient(master)

        self._compute_geometry()
        self._build()
        self._reset_view()

        self.update_idletasks()
        self._center()
        self.deiconify()
        self.lift()
        self.update()
        self.grab_set()
        self.focus_force()

    # -- 几何 ---------------------------------------------------------------

    def _compute_geometry(self) -> None:
        """算出「框」在画布上的显示位置和尺寸（保持目标宽高比）。"""
        target_w, target_h = self.target.size
        avail_w = CANVAS_W - 2 * PAD
        avail_h = CANVAS_H - 2 * PAD
        fit = min(avail_w / target_w, avail_h / target_h)

        self.frame_w = max(1, int(target_w * fit))
        self.frame_h = max(1, int(target_h * fit))
        self.frame_x = (CANVAS_W - self.frame_w) // 2
        self.frame_y = (CANVAS_H - self.frame_h) // 2

        # 最小缩放 = 图片刚好盖满框
        self.z_min = max(self.frame_w / self.work.width, self.frame_h / self.work.height)
        self.z_max = self.z_min * MAX_ZOOM_FACTOR
        self.z = self.z_min
        self.offset_x = self.frame_x + (self.frame_w - self.work.width * self.z) / 2
        self.offset_y = self.frame_y + (self.frame_h - self.work.height * self.z) / 2

    def _center(self) -> None:
        width = max(self.winfo_reqwidth(), 840)
        height = max(self.winfo_reqheight(), 560)
        master = self.master
        if master is not None and master.winfo_viewable():
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = max(0, (self.winfo_screenheight() - height) // 2 - 60)
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    # -- 界面 ---------------------------------------------------------------

    def _build(self) -> None:
        header = tk.Frame(self, background=theme.c("accent"))
        header.pack(fill="x")
        tk.Label(header, text=_("调整") + _(self.target.title), background=theme.c("accent"),
                 foreground="white", font=("Microsoft YaHei UI", 13, "bold")
                 ).pack(anchor="w", padx=22, pady=(13, 0))
        tk.Label(header, text=f"{_('导出尺寸')} {self.target.size[0]} × {self.target.size[1]}　"
                             f"{_('原图')} {self.original_size[0]} × {self.original_size[1]}"
                             f"　{self.source.name}",
                 background=theme.c("accent"), foreground=theme.c("accent_soft"), font=APP_FONT
                 ).pack(anchor="w", padx=22, pady=(2, 12))

        body = ttk.Frame(self, padding=(20, 14, 20, 0))
        body.pack(fill="both", expand=True)

        ttk.Label(body,
                  text=_("拖动图片调整位置，滚轮或下面的滑块缩放。框内就是要导出的内容。"),
                  foreground=theme.c("hint")).pack(anchor="w", pady=(0, 8))

        columns = ttk.Frame(body)
        columns.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(columns, width=CANVAS_W, height=CANVAS_H,
                                background=theme.c("thumb"), highlightthickness=0)
        self.canvas.pack(side="left")
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_wheel)

        right = ttk.Frame(columns, padding=(16, 6, 0, 0))
        right.pack(side="left", fill="y")
        ttk.Label(right, text=_("效果预览"), font=BOLD).pack(anchor="w")
        zoom = self._preview_zoom()
        ttk.Label(right, text=f"{_('实际大小')} {self.target.size[0]} × {self.target.size[1]}"
                             + (_("，下面放大 {zoom} 倍显示").format(zoom=zoom) if zoom > 1 else ""),
                  foreground=theme.c("hint")).pack(anchor="w", pady=(2, 6))
        self.preview = tk.Label(right, background=theme.c("preview_bg"),
                                borderwidth=1, relief="solid")
        self.preview.pack(anchor="w")
        ttk.Label(right, text=_(self.target.hint), foreground=theme.c("hint"),
                  wraplength=250, justify="left").pack(anchor="w", pady=(10, 0))

        controls = ttk.Frame(body)
        controls.pack(fill="x", pady=(12, 0))
        ttk.Label(controls, text=_("缩放"), font=BOLD).pack(side="left")
        self.scale = ttk.Scale(controls, from_=0, to=ZOOM_STEPS, orient="horizontal",
                               command=self._on_scale)
        self.scale.pack(side="left", fill="x", expand=True, padx=(10, 10))
        ttk.Button(controls, text=_("重置"), width=8, command=self._reset_view).pack(side="left")

        footer = ttk.Frame(self, padding=(20, 14, 20, 16))
        footer.pack(fill="x")
        ttk.Button(footer, text=_("确定"), width=12, command=self._confirm).pack(side="right")
        ttk.Button(footer, text=_("取消"), width=10,
                   command=self._cancel).pack(side="right", padx=(0, 8))
        ttk.Label(footer,
                  text=_("用户的原始图片不会被改动，结果会另存到工程的 assets 目录里。"),
                  foreground=theme.c("hint")).pack(side="left")

    def _preview_zoom(self) -> int:
        return max(1, min(3, 200 // max(1, self.target.size[1])))

    # -- 视图状态 -----------------------------------------------------------

    def _reset_view(self) -> None:
        self.z = self.z_min
        self.offset_x = self.frame_x + (self.frame_w - self.work.width * self.z) / 2
        self.offset_y = self.frame_y + (self.frame_h - self.work.height * self.z) / 2
        self._clamp()
        self._sync_scale()
        self._redraw(full=True)

    def _clamp(self) -> None:
        drawn_w = self.work.width * self.z
        drawn_h = self.work.height * self.z
        self.offset_x = min(self.frame_x, max(self.frame_x + self.frame_w - drawn_w, self.offset_x))
        self.offset_y = min(self.frame_y, max(self.frame_y + self.frame_h - drawn_h, self.offset_y))

    def _source_box(self) -> tuple[float, float, float, float]:
        """框对应的原图区域（工作图坐标）。"""
        return (
            (self.frame_x - self.offset_x) / self.z,
            (self.frame_y - self.offset_y) / self.z,
            (self.frame_x + self.frame_w - self.offset_x) / self.z,
            (self.frame_y + self.frame_h - self.offset_y) / self.z,
        )

    # -- 绘制 ---------------------------------------------------------------

    def _redraw(self, full: bool = False) -> None:
        drawn_w = max(1, int(self.work.width * self.z))
        drawn_h = max(1, int(self.work.height * self.z))

        if full or self._image_item is None:
            shown = self.work.resize((drawn_w, drawn_h), Image.LANCZOS)
            if shown.mode == "RGBA":                 # Canvas 不认透明，先压到浅色底上
                backdrop = Image.new("RGB", shown.size, (233, 237, 244))
                backdrop.paste(shown, (0, 0), shown)
                shown = backdrop
            self._photo = ImageTk.PhotoImage(shown)
            if self._image_item is None:
                self._image_item = self.canvas.create_image(
                    self.offset_x, self.offset_y, anchor="nw", image=self._photo)
            else:
                self.canvas.itemconfigure(self._image_item, image=self._photo)
        self.canvas.coords(self._image_item, self.offset_x, self.offset_y)

        self.canvas.delete("overlay")
        for x0, y0, x1, y1 in (
            (0, 0, CANVAS_W, self.frame_y),
            (0, self.frame_y + self.frame_h, CANVAS_W, CANVAS_H),
            (0, self.frame_y, self.frame_x, self.frame_y + self.frame_h),
            (self.frame_x + self.frame_w, self.frame_y, CANVAS_W, self.frame_y + self.frame_h),
        ):
            self.canvas.create_rectangle(x0, y0, x1, y1, fill="#6b7688", outline="",
                                         stipple="gray50", tags="overlay")
        self.canvas.create_rectangle(self.frame_x, self.frame_y,
                                     self.frame_x + self.frame_w,
                                     self.frame_y + self.frame_h,
                                     outline=theme.c("accent"), width=2, tags="overlay")
        self._update_preview()

    def _update_preview(self) -> None:
        rendered = render_target(self.work, self.target, self._source_box())
        zoom = self._preview_zoom()
        if zoom > 1:
            rendered = rendered.resize((rendered.width * zoom, rendered.height * zoom),
                                       Image.NEAREST)
        self._preview_photo = ImageTk.PhotoImage(rendered)
        self.preview.configure(image=self._preview_photo)

    def _sync_scale(self) -> None:
        self._syncing = True
        try:
            if self.z_max > self.z_min:
                ratio = math.log(self.z / self.z_min) / math.log(self.z_max / self.z_min)
            else:
                ratio = 0.0
            self.scale.set(max(0.0, min(1.0, ratio)) * ZOOM_STEPS)
        finally:
            self._syncing = False

    # -- 交互 ---------------------------------------------------------------

    def _on_press(self, event) -> None:
        self._drag = (event.x, event.y, self.offset_x, self.offset_y)

    def _on_motion(self, event) -> None:
        if self._drag is None:
            return
        x0, y0, ox0, oy0 = self._drag
        self.offset_x = ox0 + (event.x - x0)
        self.offset_y = oy0 + (event.y - y0)
        self._clamp()
        self._redraw(full=False)

    def _on_release(self, _event) -> None:
        self._drag = None

    def _on_wheel(self, event) -> None:
        factor = 1.12 if event.delta > 0 else 1 / 1.12
        self._set_zoom(self.z * factor)

    def _on_scale(self, value) -> None:
        if self._syncing:
            return
        ratio = float(value) / ZOOM_STEPS
        if self.z_max > self.z_min:
            self._set_zoom(self.z_min * (self.z_max / self.z_min) ** ratio)

    def _set_zoom(self, new_z: float) -> None:
        """缩放时保持框中心对准的原图位置不变，画面才不会乱跑。"""
        new_z = max(self.z_min, min(self.z_max, new_z))
        if abs(new_z - self.z) < 1e-9:
            return
        center_x = self.frame_x + self.frame_w / 2
        center_y = self.frame_y + self.frame_h / 2
        source_x = (center_x - self.offset_x) / self.z
        source_y = (center_y - self.offset_y) / self.z

        self.z = new_z
        self.offset_x = center_x - source_x * self.z
        self.offset_y = center_y - source_y * self.z
        self._clamp()
        self._sync_scale()
        self._redraw(full=True)

    # -- 收尾 ---------------------------------------------------------------

    def _confirm(self) -> None:
        self.result = render_target(self.work, self.target, self._source_box())
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
