"""本软件自己的设置（和工程文件无关）。

存最近打开过的工程、界面主题、语言、缓存目录这些「使用习惯」。

存放位置：**软件目录下的 ``data\\settings.json``**（便携、随文件夹一起搬走）。
只有软件目录不可写（比如解压到了 Program Files）时，才回退到
``%APPDATA%\\简包装\\settings.json``。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from ..i18n import t as _
from . import paths
from .errors import ProjectFileError

APP_DIR_NAME = "简包装"
MAX_RECENT = 12


def legacy_settings_dir() -> Path:
    """老版本放设置的目录（只读回退 / 迁移用）。"""
    base = os.environ.get("APPDATA") or os.environ.get("USERPROFILE") or str(Path.home())
    return Path(base) / APP_DIR_NAME


def settings_file() -> Path:
    """设置文件路径：优先软件目录下的 ``data``，不可写才回退。"""
    preferred = paths.data_dir()
    if paths.is_writable(preferred):
        return preferred / "settings.json"
    return legacy_settings_dir() / "settings.json"


THEMES = ("light", "dark")
LANGUAGES = ("zh", "en")
# 日期顺序：年-月-日（默认，中国习惯）/ 月-日-年（美国）/ 日-月-年（欧洲）
DATE_FORMATS = ("ymd", "mdy", "dmy")


@dataclass
class Settings:
    recent: list[str] = field(default_factory=list)
    new_project_dir: str = ""
    show_preview: bool = True
    show_welcome: bool = True          # 启动时是否弹欢迎页
    theme: str = "light"               # "light" | "dark"
    language: str = "zh"               # "zh" | "en"
    auto_open_last: bool = False       # 启动时自动打开最近一次打开的工程
    cache_dir: str = ""                # 缓存目录；空 = 软件目录下的 data\work
    date_format: str = "ymd"           # 日期顺序："ymd" | "mdy" | "dmy"

    # -- 使用习惯 -----------------------------------------------------------

    def reset(self) -> None:
        """恢复出厂设置（「首选项 → 初始化软件」用）。"""
        defaults = Settings()
        self.recent = list(defaults.recent)
        self.new_project_dir = defaults.new_project_dir
        self.show_preview = defaults.show_preview
        self.show_welcome = defaults.show_welcome
        self.theme = defaults.theme
        self.language = defaults.language
        self.auto_open_last = defaults.auto_open_last
        self.cache_dir = defaults.cache_dir
        self.date_format = defaults.date_format

    # -- 最近打开 -----------------------------------------------------------

    def remember(self, path: str | Path) -> None:
        """把工程排到最近列表最前面（去重、限量）。"""
        text = str(Path(path).expanduser())
        self.recent = [text] + [p for p in self.recent if p.lower() != text.lower()]
        del self.recent[MAX_RECENT:]

    def forget(self, path: str | Path) -> None:
        text = str(Path(path).expanduser())
        self.recent = [p for p in self.recent if p.lower() != text.lower()]

    def existing(self) -> list[tuple[str, bool]]:
        """返回 ``(路径, 是否还存在)``。找不到的文件也留着，只是标记出来。"""
        return [(p, Path(p).is_file()) for p in self.recent]


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def load_settings() -> Settings:
    # 优先软件目录；没有就读老的 APPDATA 位置（自动迁移，下次保存写到新位置）
    data = _read_json(settings_file())
    migrated = False
    if data is None:
        data = _read_json(legacy_settings_dir() / "settings.json")
        migrated = data is not None
    if data is None:
        return Settings()

    def flag(key: str, default: bool) -> bool:
        value = data.get(key)
        return default if value is None else bool(value)

    recent = data.get("recent")
    if not isinstance(recent, list):
        recent = []
    new_project_dir = data.get("newProjectDir")
    theme = data.get("theme")
    language = data.get("language")
    cache_dir = data.get("cacheDir")
    date_format = data.get("dateFormat")

    show_welcome = flag("showWelcome", True)
    if migrated:
        # 便携副本的第一次运行：即使旧位置把「欢迎页」关掉了，也先显示一次新手引导，
        # 免得新用户拿到软件后完全没有指引。不想看的人勾一下「以后不再显示」即可。
        show_welcome = True

    return Settings(
        recent=[p for p in recent if isinstance(p, str)],
        new_project_dir=new_project_dir if isinstance(new_project_dir, str) else "",
        show_preview=flag("showPreview", True),
        show_welcome=show_welcome,
        theme=theme if theme in THEMES else "light",
        language=language if language in LANGUAGES else "zh",
        auto_open_last=flag("autoOpenLast", False),
        cache_dir=cache_dir if isinstance(cache_dir, str) else "",
        date_format=date_format if date_format in DATE_FORMATS else "ymd",
    )


def save_settings(settings: Settings) -> None:
    path = settings_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "recent": settings.recent,
            "newProjectDir": settings.new_project_dir,
            "showPreview": settings.show_preview,
            "showWelcome": settings.show_welcome,
            "theme": settings.theme,
            "language": settings.language,
            "autoOpenLast": settings.auto_open_last,
            "cacheDir": settings.cache_dir,
            "dateFormat": settings.date_format,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise ProjectFileError(_("保存设置失败：{exc}").format(exc=exc)) from exc
