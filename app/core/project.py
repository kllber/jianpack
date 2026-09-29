"""工程文件（``.jianpack``）的数据模型、加载与派生值计算。

字段清单见 ``docs/工程文件格式.md``。这里的约定是：
- 读不懂的结构直接报错，绝不静默忽略用户配过的内容；
- 缺省值在这里补齐，生成器拿到的永远是「填满」的对象；
- 「派生字段」也在这里算出来（目录名、注册表键、fileVersion、主程序）。
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .. import i18n
from ..i18n import t as _
from .errors import Problem, ProjectFileError, error, warning
from .paths import is_inside, resolve_path

FORMAT_VERSION = 1

VERSION_RE = re.compile(r"^\d+(\.\d+){0,3}$")
ILLEGAL_NAME_CHARS = re.compile(r'[\\/:*?"<>|$]')
# 注册表键名几乎什么字符都能用（中文也行），只有这两种必须换掉：
# 反斜杠是路径分隔符，$ 会被 NSIS 当成变量前缀。
REGKEY_UNSAFE = re.compile(r"[\\/$]")
# 早期版本在没有应用名时会把键派生/退化成这个通用词，用来识别遗留工程
GENERIC_REGKEY = "App"


# ---------------------------------------------------------------------------
# 读取辅助
# ---------------------------------------------------------------------------

def _obj(value: Any, where: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ProjectFileError(
            _("{where}: 期望是一个对象 {{...}}").format(where=where))
    return value


def _s(d: dict, key: str, where: str, default: str = "") -> str:
    v = d.get(key, default)
    if v is None:
        return default
    if not isinstance(v, str):
        raise ProjectFileError(
            _("{where}.{key}: 期望字符串，当前是 {value}").format(
                where=where, key=key, value=repr(v)))
    return v


def _s_opt(d: dict, key: str, where: str) -> str | None:
    v = d.get(key)
    if v is None:
        return None
    if not isinstance(v, str):
        raise ProjectFileError(
            _("{where}.{key}: 期望字符串或 null，当前是 {value}").format(
                where=where, key=key, value=repr(v)))
    return v or None


# 布尔值在工程文件里可能被写成这几种形式。写文件时我们只写真正的 true/false，
# 但读的时候要宽容一点：早期版本的设计器会把 True/False 存成 "1"/"0"，
# 手工编辑的人也容易写成 "true"。
_TRUE_WORDS = frozenset({"true", "yes", "on", "1", "是", "真"})
_FALSE_WORDS = frozenset({"false", "no", "off", "0", "否", "假"})


def _b(d: dict, key: str, where: str, default: bool) -> bool:
    v = d.get(key, default)
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, int) and v in (0, 1):
        return bool(v)
    if isinstance(v, str):
        word = v.strip().lower()
        if word in _TRUE_WORDS:
            return True
        if word in _FALSE_WORDS:
            return False
    raise ProjectFileError(
        _("{where}.{key}: 期望 true / false，当前是 {value}").format(
            where=where, key=key, value=repr(v)))


def _str_list(d: dict, key: str, where: str) -> list[str]:
    v = d.get(key)
    if v is None:
        return []
    if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
        raise ProjectFileError(
            _("{where}.{key}: 期望字符串数组，当前是 {value}").format(
                where=where, key=key, value=repr(v)))
    return list(v)


# ---------------------------------------------------------------------------
# 各分节
# ---------------------------------------------------------------------------

@dataclass
class AppInfo:
    name: str = ""
    dir_name: str = ""
    version: str = ""
    file_version: str = ""
    publisher: str = ""
    copyright: str = ""
    homepage: str = ""
    description: str = ""
    registry_key: str = ""
    icon: str | None = None
    main_exe: str = ""
    main_exe_args: str = ""

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "AppInfo":
        return cls(
            name=_s(d, "name", where),
            dir_name=_s(d, "dirName", where),
            version=_s(d, "version", where),
            file_version=_s(d, "fileVersion", where),
            publisher=_s(d, "publisher", where),
            copyright=_s(d, "copyright", where),
            homepage=_s(d, "homepage", where),
            description=_s(d, "description", where),
            registry_key=_s(d, "registryKey", where),
            icon=_s_opt(d, "icon", where),
            main_exe=_s(d, "mainExe", where),
            main_exe_args=_s(d, "mainExeArgs", where),
        )


@dataclass
class FileItem:
    type: str = "folder"
    source: str = ""
    dest: str = "."
    # 文件夹条目是否保留自己的名字：
    #   True  -> 安装到 <dest>\<文件夹名>\...
    #   False -> 只把里面的内容放到 <dest> 下（不保留文件夹名）
    # 对文件条目没有意义。旧工程没有这个字段，按 True（保留）处理。
    keep_folder: bool = True
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "FileItem":
        kind = _s(d, "type", where, "folder")
        if kind not in ("file", "folder"):
            raise ProjectFileError(_('{where}.type: 只能是 "file" 或 "folder"').format(where=where))
        return cls(
            type=kind,
            source=_s(d, "source", where),
            dest=_s(d, "dest", where, "."),
            keep_folder=_b(d, "keepFolder", where, True),
            include=_str_list(d, "include", where),
            exclude=_str_list(d, "exclude", where),
        )


@dataclass
class FilesSection:
    items: list[FileItem] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "FilesSection":
        raw = d.get("items")
        if not isinstance(raw, list):
            raise ProjectFileError(_("{where}.items: 期望数组").format(where=where))
        return cls(items=[FileItem.from_dict(_obj(x, f"{where}.items[{i}]"), f"{where}.items[{i}]")
                          for i, x in enumerate(raw)])


@dataclass
class InstallSection:
    mode: str = "perMachine"
    default_dir: str | None = None
    allow_change_dir: bool = True
    remember_last_dir: bool = True
    estimated_size_auto: bool = True

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "InstallSection":
        mode = _s(d, "mode", where, "perMachine")
        if mode not in ("perMachine", "perUser"):
            raise ProjectFileError(
                _('{where}.mode: 只能是 "perMachine" 或 "perUser"').format(where=where))
        return cls(
            mode=mode,
            default_dir=_s_opt(d, "defaultDir", where),
            allow_change_dir=_b(d, "allowChangeDir", where, True),
            remember_last_dir=_b(d, "rememberLastDir", where, True),
            estimated_size_auto=_b(d, "estimatedSizeAuto", where, True),
        )


@dataclass
class WelcomePage:
    enabled: bool = True
    title: str = "欢迎使用 {appName} 安装向导"
    text: str = ""
    image: str | None = None

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "WelcomePage":
        return cls(
            enabled=_b(d, "enabled", where, True),
            title=_s(d, "title", where, "欢迎使用 {appName} 安装向导"),
            text=_s(d, "text", where),
            image=_s_opt(d, "image", where),
        )


def _source(d: dict, where: str, file: str | None) -> str:
    """内容来源：``text`` = 应用内编辑，``file`` = 从 txt 导入。

    老工程没有这个字段，靠「有没有指定文件」来推断，保证旧工程照常可用。
    """
    value = _s(d, "source", where, "")
    if value in ("text", "file"):
        return value
    return "file" if file else "text"


@dataclass
class LicensePage:
    enabled: bool = False
    source: str = "text"
    text: str = ""
    file: str | None = None
    require_accept: bool = True
    accept_text: str = "我接受许可协议中的条款(&A)"
    text_top: str = "请在使用本软件之前阅读下面的许可协议。"
    text_bottom: str = ""

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "LicensePage":
        base = LicensePage()
        file = _s_opt(d, "file", where)
        return cls(
            enabled=_b(d, "enabled", where, base.enabled),
            source=_source(d, where, file),
            text=_s(d, "text", where),
            file=file,
            require_accept=_b(d, "requireAccept", where, True),
            accept_text=_s(d, "acceptText", where, base.accept_text),
            text_top=_s(d, "textTop", where, base.text_top),
            text_bottom=_s(d, "textBottom", where, base.text_bottom),
        )

    def body(self) -> str | None:
        """内嵌正文；来源是文件时返回 None。空白内容一律当作「没有」。"""
        if self.source != "text":
            return None
        return self.text if self.text.strip() else None


@dataclass
class ChangelogPage:
    enabled: bool = False
    source: str = "text"
    text: str = ""
    file: str | None = None
    title: str = "更新日志"
    subtitle: str = "了解这个版本带来了哪些变化"

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "ChangelogPage":
        base = ChangelogPage()
        file = _s_opt(d, "file", where)
        return cls(
            enabled=_b(d, "enabled", where, base.enabled),
            source=_source(d, where, file),
            text=_s(d, "text", where),
            file=file,
            title=_s(d, "title", where, base.title),
            subtitle=_s(d, "subtitle", where, base.subtitle),
        )

    def body(self) -> str | None:
        if self.source != "text":
            return None
        return self.text if self.text.strip() else None


@dataclass
class DirectoryPage:
    text_top: str = ""
    text_destination: str = "安装到："

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "DirectoryPage":
        return cls(
            text_top=_s(d, "textTop", where),
            text_destination=_s(d, "textDestination", where, "安装到："),
        )


@dataclass
class OptionsPage:
    enabled: bool = True
    title: str = "安装选项"
    subtitle: str = "选择安装时要创建的快捷方式"
    group_text: str = "附加任务"
    intro: str = ""
    hint: str = ""

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "OptionsPage":
        base = OptionsPage()
        return cls(
            enabled=_b(d, "enabled", where, base.enabled),
            title=_s(d, "title", where, base.title),
            subtitle=_s(d, "subtitle", where, base.subtitle),
            group_text=_s(d, "groupText", where, base.group_text),
            intro=_s(d, "intro", where),
            hint=_s(d, "hint", where),
        )


@dataclass
class FinishLink:
    enabled: bool = False
    text: str = ""
    url: str = ""

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "FinishLink":
        return cls(
            enabled=_b(d, "enabled", where, False),
            text=_s(d, "text", where),
            url=_s(d, "url", where),
        )


@dataclass
class FinishPage:
    title: str = "{appName} 安装完成"
    text: str = ""
    run_app: bool = True
    run_text: str = "立即运行 {appName}"
    link: FinishLink = field(default_factory=FinishLink)

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "FinishPage":
        base = FinishPage()
        return cls(
            title=_s(d, "title", where, base.title),
            text=_s(d, "text", where),
            run_app=_b(d, "runApp", where, True),
            run_text=_s(d, "runText", where, base.run_text),
            link=FinishLink.from_dict(_obj(d.get("link"), f"{where}.link"), f"{where}.link"),
        )


@dataclass
class InterfaceSection:
    language: str = "zh-CN"
    branding_text: str = "{appName} 安装程序 v{appVersion}"
    show_abort_warning: bool = True
    show_details: bool = True
    header_image: str | None = None
    welcome: WelcomePage = field(default_factory=WelcomePage)
    license: LicensePage = field(default_factory=LicensePage)
    changelog: ChangelogPage = field(default_factory=ChangelogPage)
    directory_page: DirectoryPage = field(default_factory=DirectoryPage)
    options_page: OptionsPage = field(default_factory=OptionsPage)
    finish: FinishPage = field(default_factory=FinishPage)

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "InterfaceSection":
        return cls(
            language=_s(d, "language", where, "zh-CN"),
            branding_text=_s(d, "brandingText", where, "{appName} 安装程序 v{appVersion}"),
            show_abort_warning=_b(d, "showAbortWarning", where, True),
            show_details=_b(d, "showDetails", where, True),
            header_image=_s_opt(d, "headerImage", where),
            welcome=WelcomePage.from_dict(_obj(d.get("welcome"), f"{where}.welcome"), f"{where}.welcome"),
            license=LicensePage.from_dict(_obj(d.get("license"), f"{where}.license"), f"{where}.license"),
            changelog=ChangelogPage.from_dict(_obj(d.get("changelog"), f"{where}.changelog"), f"{where}.changelog"),
            directory_page=DirectoryPage.from_dict(
                _obj(d.get("directoryPage"), f"{where}.directoryPage"), f"{where}.directoryPage"),
            options_page=OptionsPage.from_dict(
                _obj(d.get("optionsPage"), f"{where}.optionsPage"), f"{where}.optionsPage"),
            finish=FinishPage.from_dict(_obj(d.get("finish"), f"{where}.finish"), f"{where}.finish"),
        )


@dataclass
class ShortcutEntry:
    enabled: bool = True
    default: bool = True
    user_can_toggle: bool = True
    name: str = "{appName}"

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "ShortcutEntry":
        return cls(
            enabled=_b(d, "enabled", where, True),
            default=_b(d, "default", where, True),
            user_can_toggle=_b(d, "userCanToggle", where, True),
            name=_s(d, "name", where, "{appName}"),
        )


@dataclass
class StartMenuShortcut(ShortcutEntry):
    use_folder: bool = True
    uninstall_shortcut: bool = True

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "StartMenuShortcut":
        base = ShortcutEntry.from_dict(d, where)
        return cls(
            enabled=base.enabled, default=base.default,
            user_can_toggle=base.user_can_toggle, name=base.name,
            use_folder=_b(d, "useFolder", where, True),
            uninstall_shortcut=_b(d, "uninstallShortcut", where, True),
        )


@dataclass
class ShortcutsSection:
    desktop: ShortcutEntry = field(default_factory=ShortcutEntry)
    start_menu: StartMenuShortcut = field(default_factory=StartMenuShortcut)

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "ShortcutsSection":
        return cls(
            desktop=ShortcutEntry.from_dict(_obj(d.get("desktop"), f"{where}.desktop"), f"{where}.desktop"),
            start_menu=StartMenuShortcut.from_dict(
                _obj(d.get("startMenu"), f"{where}.startMenu"), f"{where}.startMenu"),
        )


@dataclass
class UninstallSection:
    user_data_path: str = "$APPDATA\\{appName}"
    ask_keep_user_data: bool = True
    keep_user_data_text: str = ""
    delete_user_data_by_default: bool = False
    auto_close: bool = True

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "UninstallSection":
        base = UninstallSection()
        return cls(
            user_data_path=_s(d, "userDataPath", where, base.user_data_path),
            ask_keep_user_data=_b(d, "askKeepUserData", where, True),
            keep_user_data_text=_s(d, "keepUserDataText", where),
            delete_user_data_by_default=_b(d, "deleteUserDataByDefault", where, False),
            auto_close=_b(d, "autoClose", where, True),
        )


@dataclass
class BuildSection:
    output_dir: str = ""                       # 空 = 输出到桌面
    file_name: str = "{appName}-{appVersion}-Setup.exe"
    compression: str = "solid-lzma"
    modes: list[str] = field(default_factory=lambda: ["perMachine"])
    # 代码签名（Authenticode）：不勾选 / 没填证书 = 不签名
    sign_enabled: bool = False
    sign_cert: str = ""                        # .pfx / .p12
    sign_password: str = ""
    sign_timestamp: str = "http://timestamp.digicert.com"
    signtool: str = ""                         # 空 = 自动查找

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "BuildSection":
        compression = _s(d, "compression", where, "solid-lzma")
        if compression not in ("solid-lzma", "lzma", "zlib", "bzip2"):
            raise ProjectFileError(
                _('{where}.compression: 只能是 "solid-lzma" / "lzma" / "zlib" / "bzip2"')
                .format(where=where))
        modes = _str_list(d, "modes", where) or ["perMachine"]
        for m in modes:
            if m not in ("perMachine", "perUser"):
                raise ProjectFileError(
                    _('{where}.modes: 非法值 "{value}"').format(where=where, value=m))
        return cls(
            output_dir=_s(d, "outputDir", where, ""),
            file_name=_s(d, "fileName", where, "{appName}-{appVersion}-Setup.exe"),
            compression=compression,
            modes=modes,
            sign_enabled=_b(d, "signEnabled", where, False),
            sign_cert=_s(d, "signCert", where, ""),
            sign_password=_s(d, "signPassword", where, ""),
            sign_timestamp=_s(d, "signTimestamp", where,
                              "http://timestamp.digicert.com"),
            signtool=_s(d, "signtool", where, ""),
        )


@dataclass
class AssocEntry:
    """一个文件类型关联（扩展名 -> 本程序）。"""

    ext: str = ""              # 例 ".myext"（带不带点都行）
    description: str = ""
    icon: str = ""             # 空 = 用主程序图标
    is_default: bool = True    # 尝试设为默认（只对自定义扩展名有意义）

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "AssocEntry":
        return cls(
            ext=_s(d, "ext", where),
            description=_s(d, "description", where),
            icon=_s(d, "icon", where),
            is_default=_b(d, "isDefault", where, True),
        )


@dataclass
class ProtocolEntry:
    """一个 URL 协议（例 myapp://…）。"""

    scheme: str = ""           # 例 "myapp"
    description: str = ""

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "ProtocolEntry":
        return cls(scheme=_s(d, "scheme", where), description=_s(d, "description", where))


@dataclass
class RegEntry:
    """一条自定义注册表项（安装时写入，卸载时删除）。"""

    root: str = "HKCU"         # HKCU | HKLM
    path: str = ""             # 例 Software\MyApp
    name: str = ""             # 空 = 该键的默认值
    type: str = "REG_SZ"       # REG_SZ | REG_EXPAND_SZ | REG_DWORD
    data: str = ""

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "RegEntry":
        root = _s(d, "root", where, "HKCU")
        if root not in ("HKCU", "HKLM"):
            raise ProjectFileError(
                _('{where}.root: 只能是 "HKCU" 或 "HKLM"').format(where=where))
        kind = _s(d, "type", where, "REG_SZ")
        if kind not in ("REG_SZ", "REG_EXPAND_SZ", "REG_DWORD"):
            raise ProjectFileError(
                _("{where}.type: 只能是 REG_SZ / REG_EXPAND_SZ / REG_DWORD")
                .format(where=where))
        return cls(root=root, path=_s(d, "path", where), name=_s(d, "name", where),
                   type=kind, data=_s(d, "data", where))


@dataclass
class IntegrationSection:
    """安装时对系统做的「集成」：文件关联 / URL 协议 / 注册表 / 开机自启。"""

    associations: list[AssocEntry] = field(default_factory=list)
    protocols: list[ProtocolEntry] = field(default_factory=list)
    registry: list[RegEntry] = field(default_factory=list)
    autostart: bool = False

    @classmethod
    def from_dict(cls, d: dict, where: str) -> "IntegrationSection":
        def items(key: str, kind, cast):
            raw = d.get(key)
            if raw is None:
                return []
            if not isinstance(raw, list):
                raise ProjectFileError(
                    _("{where}.{key}: 期望数组").format(where=where, key=key))
            return [cast(_obj(x, f"{where}.{key}[{i}]"), f"{where}.{key}[{i}]")
                    for i, x in enumerate(raw)]

        return cls(
            associations=items("associations", AssocEntry, AssocEntry.from_dict),
            protocols=items("protocols", ProtocolEntry, ProtocolEntry.from_dict),
            registry=items("registry", RegEntry, RegEntry.from_dict),
            autostart=_b(d, "autostart", where, False),
        )


# ---------------------------------------------------------------------------
# 顶层工程
# ---------------------------------------------------------------------------

@dataclass
class Project:
    source_path: Path
    base_dir: Path
    format_version: int = FORMAT_VERSION
    generator: dict = field(default_factory=dict)
    project_name: str = ""
    created_at: str = ""
    modified_at: str = ""
    app: AppInfo = field(default_factory=AppInfo)
    files: FilesSection = field(default_factory=FilesSection)
    install: InstallSection = field(default_factory=InstallSection)
    interface: InterfaceSection = field(default_factory=InterfaceSection)
    shortcuts: ShortcutsSection = field(default_factory=ShortcutsSection)
    uninstall: UninstallSection = field(default_factory=UninstallSection)
    build: BuildSection = field(default_factory=BuildSection)
    integration: IntegrationSection = field(default_factory=IntegrationSection)
    # 单文件工程（zip 容器）：保存在 source_path；运行时文件在 base_dir。
    is_container: bool = False
    work_dir: Path | None = None           # 本软件独占的临时目录，关闭时要删

    # -- 输出位置 -----------------------------------------------------------

    def output_dir(self) -> Path:
        """安装包输出到哪。

        留空 = 当前用户的桌面（跟随 OneDrive 重定向）；填了就用填的，
        相对路径按「工程文件所在目录」解析。
        """
        from .paths import desktop_dir

        raw = (self.build.output_dir or "").strip()
        if not raw:
            return desktop_dir()
        expanded = os.path.expandvars(os.path.expanduser(raw))
        path = Path(expanded)
        if not path.is_absolute():
            path = self.source_path.parent / path
        return path

    def cleanup(self) -> None:
        """删掉本软件自己的临时工作目录（容器工程才有）。"""
        if self.work_dir is not None:
            from . import container

            container.cleanup(self.work_dir)
            self.work_dir = None

    # -- 派生 ---------------------------------------------------------------

    def apply_derived(self) -> None:
        """补齐派生字段。必须在 ``validate`` 之前调用。

        注意：**输入为空时不要派生**。否则「刚新建、还没填应用名」那一刻就会把占位值
        算出来并存进工程文件，之后再也不会更新（``registryKey`` 就吃过这个亏：
        被冻成通用的 ``App``，导致不同软件在控制面板里互相覆盖卸载项）。
        """
        app = self.app
        if not app.dir_name:
            app.dir_name = app.name
        if not app.registry_key and app.dir_name:
            app.registry_key = _derive_registry_key(app.dir_name)
        if not app.file_version and app.version:
            app.file_version = _pad_version(app.version)
        if not app.description:
            app.description = app.name
        if not self.project_name:
            self.project_name = app.name
        if not self.uninstall.keep_user_data_text:
            self.uninstall.keep_user_data_text = (
                "是否同时删除 {appName} 的配置和用户数据？\n\n"
                "选择「否」将保留这些数据，以便日后重新安装时继续使用。"
            )
        if not self.interface.finish.text:
            self.interface.finish.text = (
                "{appName} 已经安装到您的电脑上。\n\n安装位置：$INSTDIR\n\n"
                "点击「完成」关闭安装向导。"
            )
        if not self.interface.directory_page.text_top:
            self.interface.directory_page.text_top = (
                "安装向导将把 {appName} 安装到下面的文件夹中。\n\n"
                "若要安装到其他位置，请点击「浏览」并选择目标文件夹。"
            )
        if not self.interface.welcome.text:
            self.interface.welcome.text = (
                "安装向导将引导您完成 {appName} 的安装。\n\n"
                "建议在继续之前关闭其他正在运行的程序。安装完成后，"
                "您可以从桌面或开始菜单启动本软件。\n\n点击「下一步」继续。"
            )

    # -- 遍历打包内容 --------------------------------------------------------

    def iter_payload(self) -> Iterator[tuple[Path, str]]:
        """产出 ``(源文件绝对路径, 安装目录内的相对路径)``。"""
        for idx, item in enumerate(self.files.items):
            where = f"files.items[{idx}].source"
            if not item.source:
                raise ProjectFileError(_("{where}: 未填写").format(where=where))
            src = resolve_path(self.base_dir, item.source, where=where)
            if not src.exists():
                raise ProjectFileError(
                    _("{where}: 找不到 {source}").format(where=where, source=item.source))
            dest = "" if item.dest.strip() in ("", ".", "./", ".\\") else item.dest.replace("\\", "/").strip("/")

            if item.type == "file":
                if not src.is_file():
                    raise ProjectFileError(
                        _("{where}: {source} 不是文件").format(
                            where=where, source=item.source))
                yield src, _join_dest(dest, src.name)
                continue

            if not src.is_dir():
                raise ProjectFileError(
                    _("{where}: {source} 不是文件夹").format(
                        where=where, source=item.source))
            # 保留文件夹名 -> <dest>\<文件夹名>\...；否则只把内容放进 dest。
            base = _join_dest(dest, src.name) if item.keep_folder else dest
            for path in sorted(src.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(src).as_posix()
                if item.include and not _matches_any(rel, path.name, item.include):
                    continue
                if item.exclude and _matches_any(rel, path.name, item.exclude):
                    continue
                yield path, _join_dest(base, rel)

    def root_exe_candidates(self) -> list[str]:
        """安装目录**根部**的所有 .exe（用于自动识别主程序）。"""
        found: list[str] = []
        for path, dest in self.iter_payload():
            if "/" in dest:
                continue
            if path.suffix.lower() == ".exe":
                found.append(dest)
        return found

    def removable_payload_paths(self, removed: list["FileItem"]) -> list[Path]:
        """移除这些条目时，可以一并从工程里删掉的副本。

        只挑「位于工程 ``payload\\`` 下、确实存在、且没有任何剩余条目 /
        许可协议 / 更新日志还在引用」的路径：

        - 引用工程外原位置的（用户当初选了「直接引用」）不在 payload 下，不会被删；
        - 还被别的条目引用的（共享同一份副本）也不会被删。
        """
        base = self.base_dir.resolve()
        payload_root = (base / "payload").resolve()
        removed_ids = {id(item) for item in removed}

        referenced: list[Path] = []
        for item in self.files.items:
            if id(item) in removed_ids or not item.source:
                continue
            try:
                referenced.append(resolve_path(base, item.source,
                                                where="files.items[].source"))
            except ProjectFileError:
                pass
        for value in (self.interface.license.file, self.interface.changelog.file):
            if value:
                try:
                    referenced.append(resolve_path(base, value, where="interface"))
                except ProjectFileError:
                    pass

        found: list[Path] = []
        for item in removed:
            if not item.source:
                continue
            try:
                src = resolve_path(base, item.source, where="files.items[].source")
            except ProjectFileError:
                continue
            if not (src == payload_root or payload_root in src.parents):
                continue                      # 不在工程 payload 里，别动
            if not src.exists():
                continue
            if any(src == ref or src in ref.parents for ref in referenced):
                continue                      # 还有别的地方在用它
            found.append(src)
        return found

    def autodetect_main_exe(self) -> tuple[str, str | None]:
        """返回 ``(识别出的主程序, 提示信息)``。"""
        candidates = self.root_exe_candidates()
        if not candidates:
            return "", _("安装目录根部没有找到任何 .exe")
        if len(candidates) > 1:
            joiner = ", " if i18n.is_english() else "、"
            return "", _("安装目录根部有多个 .exe，无法自动识别：{list}").format(
                list=joiner.join(candidates))
        return candidates[0], None

    # -- 校验 ---------------------------------------------------------------

    def validate(self) -> list[Problem]:
        problems: list[Problem] = []
        add = problems.append
        app = self.app

        if not app.name.strip():
            add(error("app.name", _("不能为空")))
        elif ILLEGAL_NAME_CHARS.search(app.name):
            add(error("app.name", _("不能包含 \\ / : * ? \" < > | $ 这些字符")))

        for field_name, value in (("app.dirName", app.dir_name),
                                  ("app.registryKey", app.registry_key)):
            if ILLEGAL_NAME_CHARS.search(value):
                add(error(field_name,
                          _("不能包含 \\ / : * ? \" < > | $ 这些字符（当前值：{value}）")
                          .format(value=value)))
            if value.strip() != value or value.endswith("."):
                add(error(field_name,
                          _("不能以空格或句点结尾（当前值：{value}）").format(value=value)))

        if not app.version.strip():
            add(error("app.version", _("不能为空")))
        elif not VERSION_RE.match(app.version):
            add(error("app.version",
                      _("必须是 1 / 1.0 / 1.0.0 / 1.0.0.0 这样的数字版本号，当前为 {version}")
                      .format(version=app.version)))

        if not re.match(r"^\d+(\.\d+){3}$", app.file_version or ""):
            add(error("app.fileVersion",
                      _("必须是 a.b.c.d 四段数字，当前为 {version}")
                      .format(version=app.file_version)))

        if not self.files.items:
            add(error("files.items", _("至少要选一个文件或文件夹")))

        # 打包源文件存在性 + 主程序识别
        try:
            payload = list(self.iter_payload())
        except ProjectFileError as exc:
            add(error("files.items", str(exc)))
            payload = []

        if not payload:
            add(error("files.items", _("打包内容为空")))

        if not app.main_exe:
            # 自动识别要再遍历一次打包内容；如果源本来就读不了（上面已经记过一条错误），
            # 这里不能再把异常抛出去，否则校验会整个崩掉、用户看不到任何提示。
            try:
                detected, hint = self.autodetect_main_exe()
            except ProjectFileError as exc:
                detected, hint = "", str(exc)
            if detected:
                app.main_exe = detected
            else:
                add(error("app.mainExe",
                          _("没有指定主程序，且无法自动识别：{hint}").format(hint=hint)))
        elif payload:
            normalized = app.main_exe.replace("\\", "/").lstrip("./")
            if not any(dest == normalized for _, dest in payload):
                add(error("app.mainExe",
                          _("在打包内容里找不到 {exe}（该路径是安装目录内的相对路径）")
                          .format(exe=app.main_exe)))

        # 引用的资源文件
        add(self._check_asset("app.icon", app.icon, exts={".ico"},
                              howto=_("在第 1 步「基本信息 → 图标」里重新选一个 .ico")))
        add(self._check_asset("interface.headerImage", self.interface.header_image, exts={".bmp"},
                              howto=_("在第 4 步「安装界面 → 通用」里重新选，或点「清除」")))
        add(self._check_asset("interface.welcome.image", self.interface.welcome.image, exts={".bmp"},
                              howto=_("在第 4 步「安装界面 → 欢迎页」里重新选，或点「清除」")))

        if self.interface.license.enabled:
            page = self.interface.license
            if page.source == "file":
                if page.file:
                    add(self._check_asset("interface.license.file", page.file, exts=None,
                                          howto=_("在第 4 步「安装界面 → 许可协议」里重新选择，"
                                                  "或改成「直接在下面编辑」")))
                else:
                    add(error("interface.license.file",
                              _("勾选了「显示许可协议页」并选了「从 txt 文件导入」，"
                                "但没有选文件——请在第 4 步「安装界面 → 许可协议」里选一个 .txt，"
                                "或改成「直接在下面编辑」")))
            elif not page.body():
                add(error("interface.license.text",
                          _("勾选了「显示许可协议页」并选了「直接编辑」，但正文是空的——"
                            "请在第 4 步「安装界面 → 许可协议」里写上条款内容")))

        if self.interface.changelog.enabled:
            page = self.interface.changelog
            if page.source == "file":
                if page.file:
                    add(self._check_asset("interface.changelog.file", page.file, exts=None,
                                          howto=_("在第 4 步「安装界面 → 更新日志」里重新选择，"
                                                  "或改成「直接在下面编辑」")))
                else:
                    add(error("interface.changelog.file",
                              _("勾选了「显示更新日志页」并选了「从 txt 文件导入」，"
                                "但没有选文件——请在第 4 步「安装界面 → 更新日志」里选一个 .txt，"
                                "或改成「直接在下面编辑」")))
            elif not page.body():
                add(error("interface.changelog.text",
                          _("勾选了「显示更新日志页」并选了「直接编辑」，但正文是空的——"
                            "请在第 4 步「安装界面 → 更新日志」里写上更新内容")))

        # 警告项
        if (app.registry_key == GENERIC_REGKEY
                and app.dir_name and app.dir_name != GENERIC_REGKEY):
            add(warning("app.registryKey",
                        _("内部标识是通用的「{key}」——"
                          "装两个不同的软件时，它们在控制面板里会互相覆盖卸载项。"
                          "建议把这个字段清空，让它按安装目录名自动生成。")
                        .format(key=GENERIC_REGKEY)))
        if not app.publisher:
            add(warning("app.publisher", _("没填发行者，控制面板的卸载列表里会显示「未知发布者」")))
        if not app.copyright:
            add(warning("app.copyright", _("没填版权信息，程序属性里会缺少版权声明")))
        if not app.icon:
            add(warning("app.icon", _("没提供图标，安装包会用 NSIS 默认图标，辨识度低")))
        if not self.install.allow_change_dir and not self.install.default_dir:
            add(warning("install.allowChangeDir",
                        _("关闭了「安装位置」页，但 defaultDir 留空仍会按模式自动选择路径")))
        if self.build.sign_enabled and not self.build.sign_cert:
            add(error("build.signCert",
                      _("勾选了「打包后自动签名」，但没有选择证书文件（.pfx / .p12）")))

        for where, value in self._outside_references():
            add(warning(where, _("引用了工程目录之外的位置（{value}），"
                                 "把工程拷到别的电脑后这条引用会失效").format(value=value)))

        return [p for p in problems if p is not None]

    def _check_asset(self, where: str, relative: str | None, exts: set[str] | None,
                     howto: str = "") -> Problem | None:
        if not relative:
            return None
        try:
            path = resolve_path(self.base_dir, relative, where=where)
        except ProjectFileError as exc:
            return error(where, str(exc))
        if not path.exists():
            message = _("找不到文件：{relative}").format(relative=relative)
            if howto:
                message += f"\n         —— {howto}"
            return error(where, message)
        if not path.is_file():
            return error(where, _("不是文件：{relative}").format(relative=relative))
        if exts and path.suffix.lower() not in exts:
            return error(where, _("扩展名必须是 {exts}，当前为 {suffix}").format(
                exts="/".join(sorted(exts)), suffix=path.suffix))
        return None

    def _outside_references(self) -> list[tuple[str, str]]:
        """列出引用了工程目录之外的路径（这些会让工程不可搬移）。"""
        found: list[tuple[str, str]] = []
        checks = [
            ("app.icon", self.app.icon),
            ("interface.headerImage", self.interface.header_image),
            ("interface.welcome.image", self.interface.welcome.image),
            ("interface.license.file",
             self.interface.license.file if self.interface.license.enabled else None),
            ("interface.changelog.file",
             self.interface.changelog.file if self.interface.changelog.enabled else None),
        ]
        for idx, item in enumerate(self.files.items):
            checks.append((f"files.items[{idx}].source", item.source or None))

        for where, value in checks:
            if not value:
                continue
            try:
                path = resolve_path(self.base_dir, value, where=where)
            except ProjectFileError:
                continue
            if not is_inside(self.base_dir, path):
                found.append((where, value))
        return found

    def resolve(self, where: str, relative: str) -> Path:
        return resolve_path(self.base_dir, relative, where=where)


# ---------------------------------------------------------------------------
# 加载入口
# ---------------------------------------------------------------------------

def load_project(path: str | Path, progress=None) -> Project:
    """读取并校验工程文件。结构性问题直接抛 :class:`ProjectFileError`。

    支持两种 ``.jianpack``：单文件容器（``PK`` 开头的 zip）和老的 foldered
    工程（纯 JSON）。容器会先解到一份临时工作目录，之后所有路径都以它为准。

    ``progress`` 可选，转交给 :func:`app.core.container.extract`，用于显示解压进度。
    """
    from . import container

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ProjectFileError(_("工程文件不存在：{path}").format(path=source))

    kind = container.sniff(source)
    work_dir: Path | None = None
    if kind == "container":
        work_dir = container.make_work_dir()
        try:
            container.extract(source, work_dir, progress=progress)
        except ProjectFileError:
            container.cleanup(work_dir)
            raise
        raw = (work_dir / container.PROJECT_JSON).read_bytes()
        base_dir = work_dir
    else:
        raw = source.read_bytes()
        base_dir = source.parent

    if raw[:3] == b"\xef\xbb\xbf":
        if work_dir is not None:
            container.cleanup(work_dir)
        raise ProjectFileError(
            _("工程文件带有 UTF-8 BOM，JSON 不允许。请另存为「UTF-8 无 BOM」。"))

    try:
        data = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        container.cleanup(work_dir)
        raise ProjectFileError(
            _("工程文件不是 UTF-8 编码：{exc}").format(exc=exc)) from exc
    except json.JSONDecodeError as exc:
        container.cleanup(work_dir)
        raise ProjectFileError(
            _("JSON 语法错误（第 {line} 行第 {col} 列）：{msg}").format(
                line=exc.lineno, col=exc.colno, msg=exc.msg)) from exc

    if not isinstance(data, dict):
        container.cleanup(work_dir)
        raise ProjectFileError(_("工程文件的顶层必须是对象 {...}"))

    version = data.get("formatVersion")
    if not isinstance(version, int):
        container.cleanup(work_dir)
        raise ProjectFileError(_("缺少 formatVersion 字段"))
    if version > FORMAT_VERSION:
        container.cleanup(work_dir)
        raise ProjectFileError(
            _("此工程由更新版本的程序创建（formatVersion={version}，本程序支持到 {max}），"
              "请升级后再打开。").format(version=version, max=FORMAT_VERSION))

    gen = data.get("generator")
    meta = _obj(data.get("project"), "project")
    try:
        project = Project(
            source_path=source,
            base_dir=base_dir,
            format_version=version,
            generator=gen if isinstance(gen, dict) else {},
            project_name=_s(meta, "name", "project"),
            created_at=_s(meta, "createdAt", "project"),
            modified_at=_s(meta, "modifiedAt", "project"),
            app=AppInfo.from_dict(_obj(data.get("app"), "app"), "app"),
            files=FilesSection.from_dict(_obj(data.get("files"), "files"), "files"),
            install=InstallSection.from_dict(_obj(data.get("install"), "install"), "install"),
            interface=InterfaceSection.from_dict(_obj(data.get("interface"), "interface"), "interface"),
            shortcuts=ShortcutsSection.from_dict(_obj(data.get("shortcuts"), "shortcuts"), "shortcuts"),
            uninstall=UninstallSection.from_dict(_obj(data.get("uninstall"), "uninstall"), "uninstall"),
            build=BuildSection.from_dict(_obj(data.get("build"), "build"), "build"),
            integration=IntegrationSection.from_dict(
                _obj(data.get("integration"), "integration"), "integration"),
            is_container=kind == "container",
            work_dir=work_dir,
        )
    except ProjectFileError:
        container.cleanup(work_dir)
        raise
    project.apply_derived()
    return project


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def _pad_version(version: str) -> str:
    parts = [p for p in re.split(r"[.\-+]", version) if p.isdigit()]
    parts = (parts + ["0", "0", "0", "0"])[:4]
    return ".".join(parts)


def _derive_registry_key(dir_name: str) -> str:
    """从安装目录名派生注册表键。保留中文等 Unicode 字符。"""
    return REGKEY_UNSAFE.sub("_", dir_name).strip().strip(".")


def _join_dest(dest: str, name: str) -> str:
    return f"{dest}/{name}" if dest else name


def _matches_any(rel: str, basename: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(basename, pattern):
            return True
        # 让 "**/*.pdb" 也能匹配根目录下的 x.pdb
        if pattern.startswith("**/") and fnmatch.fnmatch(rel, pattern[3:]):
            return True
    return False
