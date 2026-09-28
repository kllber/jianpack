"""资源文件处理：编码转换 + 尺寸校验。

NSIS 对几个文件有硬性要求（都是实测踩出来的坑）：
- 许可协议：UTF-8 **带 BOM**
- 更新日志：UTF-16LE **带 BOM**（配 FileReadUTF16LE 使用）
- 欢迎页位图：164×314 的 BMP
- 页头位图：150×57 的 BMP
- 图标：.ico 且至少要有 256×256 和 16×16

这里的转换只写进工程的 ``build/`` 目录，绝不动用户的原始文件。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from ..core.errors import ProjectFileError
from ..i18n import t as _

WELCOME_BITMAP_SIZE = (164, 314)
HEADER_BITMAP_SIZE = (150, 57)
ICON_REQUIRED_SIZES = {(256, 256), (16, 16)}

# 生成 .ico 时包含的各档尺寸
ICON_EXPORT_SIZES = (16, 24, 32, 48, 64, 128, 256)


# ---------------------------------------------------------------------------
# 图片目标规格：界面上「选图片」时按这些要求裁剪/转换
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImageTarget:
    key: str
    title: str
    size: tuple[int, int]
    file_name: str          # 输出到工程的 assets\ 里的固定文件名
    kind: str               # "bmp" | "ico"
    hint: str


TARGETS: dict[str, ImageTarget] = {
    "icon": ImageTarget(
        key="icon",
        title="程序图标",
        size=(256, 256),
        file_name="app.ico",
        kind="ico",
        hint="正方形。程序会自动导出 16 / 24 / 32 / 48 / 64 / 128 / 256 各档尺寸，"
             "Windows 在桌面、任务栏、文件列表里都会挑合适的用。",
    ),
    "header": ImageTarget(
        key="header",
        title="内页页头图片",
        size=(150, 57),
        file_name="header.bmp",
        kind="bmp",
        hint="横条，出现在许可协议 / 更新日志 / 安装位置等内页的左上角。",
    ),
    "welcome": ImageTarget(
        key="welcome",
        title="欢迎页左侧图片",
        size=(164, 314),
        file_name="welcome.bmp",
        kind="bmp",
        hint="竖版，只出现在欢迎页和完成页的左侧。",
    ),
}


def load_for_edit(source: Path, max_side: int = 2400):
    """读入图片、摆正方向、必要时缩到工作分辨率，供裁剪界面使用。

    返回 ``(PIL.Image, 原始尺寸)``。原图很大时先缩小是为了让拖动流畅；
    对这几个目标尺寸来说 2400px 已经远远够用。
    """
    Image, ImageOps = _pil()
    try:
        image = Image.open(source)
        image = ImageOps.exif_transpose(image) or image      # 手机照片会带旋转信息
        original_size = image.size
        image = image.convert("RGBA")
    except OSError as exc:
        raise ProjectFileError(_("读不了这张图片：{exc}").format(exc=exc)) from exc

    if max(image.size) > max_side:
        ratio = max_side / max(image.size)
        image = image.resize((max(1, int(image.width * ratio)),
                              max(1, int(image.height * ratio))), Image.LANCZOS)
    return image, original_size


def render_target(image, target: ImageTarget, box: tuple[float, float, float, float]):
    """按裁剪框（工作图坐标）裁出目标尺寸的成品。"""
    Image, ImageOps = _pil()
    left, top, right, bottom = box
    left = max(0, min(left, image.width - 1))
    top = max(0, min(top, image.height - 1))
    right = max(left + 1, min(right, image.width))
    bottom = max(top + 1, min(bottom, image.height))

    cropped = image.crop((int(round(left)), int(round(top)),
                          int(round(right)), int(round(bottom))))
    resized = cropped.resize(target.size, Image.LANCZOS)

    if target.kind == "bmp":
        # BMP 没有透明通道，透明区域压在白色上，免得变成黑块
        canvas = Image.new("RGB", target.size, (255, 255, 255))
        canvas.paste(resized, (0, 0), resized)
        return canvas
    return resized.convert("RGBA")


def save_image(image, dest: Path, target: ImageTarget) -> None:
    """把成品写到工程里。"""
    Image, _ = _pil()
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        if target.kind == "bmp":
            image.convert("RGB").save(dest, format="BMP")
        else:
            base = image.convert("RGBA" if image.mode == "RGBA" else "RGB")
            if base.mode != "RGBA":
                base = base.convert("RGBA")
            base.save(dest, format="ICO",
                      sizes=[(size, size) for size in ICON_EXPORT_SIZES])
    except OSError as exc:
        raise ProjectFileError(_("保存图片失败：{exc}").format(exc=exc)) from exc


def _pil():
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover - 正常安装不会走到
        raise ProjectFileError(
            _("缺少 Pillow，无法处理图片。请先安装：pip install Pillow")) from exc
    return Image, ImageOps


def read_text_auto(path: Path) -> str:
    """按 BOM 猜编码读文本，兜底用 GBK（老的中文 Windows 记事本）。"""
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw[3:].decode("utf-8")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk")


def write_utf8_bom(text: str, dest: Path) -> None:
    """写 UTF-8 带 BOM（NSIS 的 .nsi 和许可协议需要）。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))


def write_utf16le_bom(text: str, dest: Path) -> None:
    """写 UTF-16LE 带 BOM（更新日志需要，供 FileReadUTF16LE 读取）。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = text.replace("\r\n", "\n").replace("\n", "\r\n")
    dest.write_bytes(b"\xff\xfe" + body.encode("utf-16-le"))


def read_bmp_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        head = handle.read(26)
    if len(head) < 26 or head[:2] != b"BM":
        raise ProjectFileError(_("{name}: 不是有效的 BMP 文件").format(name=path.name))
    width = struct.unpack_from("<i", head, 18)[0]
    height = struct.unpack_from("<i", head, 22)[0]
    return width, abs(height)


def read_ico_sizes(path: Path) -> list[tuple[int, int]]:
    with path.open("rb") as handle:
        header = handle.read(6)
        if len(header) < 6:
            raise ProjectFileError(_("{name}: 不是有效的 ICO 文件").format(name=path.name))
        reserved, kind, count = struct.unpack("<HHH", header)
        if reserved != 0 or kind != 1:
            raise ProjectFileError(_("{name}: 不是有效的 ICO 文件").format(name=path.name))
        sizes: list[tuple[int, int]] = []
        for _ in range(count):
            entry = handle.read(16)
            if len(entry) < 16:
                break
            sizes.append((entry[0] or 256, entry[1] or 256))
    return sizes


def check_bitmap(path: Path, expected: tuple[int, int], where: str) -> str | None:
    try:
        actual = read_bmp_size(path)
    except (ProjectFileError, OSError) as exc:
        return f"{where}: {exc}"
    if actual != expected:
        return _("{where}: 位图尺寸必须是 {w}×{h}，当前为 {aw}×{ah}").format(
            where=where, w=expected[0], h=expected[1], aw=actual[0], ah=actual[1])
    return None


def check_icon(path: Path, where: str) -> str | None:
    try:
        sizes = read_ico_sizes(path)
    except (ProjectFileError, OSError) as exc:
        return f"{where}: {exc}"
    if not sizes:
        return _("{where}: 图标里没有任何图像").format(where=where)
    missing = [s for s in ICON_REQUIRED_SIZES if s not in sizes]
    if missing:
        need = "、".join(f"{w}×{h}" for w, h in sorted(missing, reverse=True))
        return _("{where}: 图标缺少 {need} 尺寸（Windows 要求小图标和 256 大图标都要有）").format(
            where=where, need=need)
    return None
