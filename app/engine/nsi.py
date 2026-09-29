"""把工程（:class:`~app.core.project.Project`）翻译成 NSIS 脚本。

生成脚本前会先把用户提供的许可协议 / 更新日志转码到 ``build/`` 目录，
因为 NSIS 对这两个文件的编码有硬性要求（见 :mod:`app.engine.assets`）。

设计上刻意让产物尽量像人手写的脚本：一个 ``.nsi`` 通过 ``!ifdef PER_USER``
切换安装模式，编译两次即可得到两个安装包。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .. import APP_NAME, __version__
from ..core.errors import ProjectFileError
from ..i18n import t as _
from ..core.project import Project
from . import assets
from .textutil import expand_placeholders, render

MODE_LABELS = {
    "perMachine": "为所有用户安装（需要管理员权限）",
    "perUser": "仅当前用户安装（无需管理员权限）",
}

MODE_SUFFIX = {
    "perMachine": "PerMachine",
    "perUser": "PerUser",
}

COMPRESSOR = {
    "solid-lzma": "SetCompressor /SOLID lzma",
    "lzma": "SetCompressor lzma",
    "zlib": "SetCompressor zlib",
    "bzip2": "SetCompressor bzip2",
}


def output_file_name(project: Project, mode: str, total_modes: int) -> str:
    """算出这个模式的安装包文件名。"""
    table = placeholder_table(project, mode)
    name = expand_placeholders(project.build.file_name, table, "build.fileName").strip()
    if not name:
        raise ProjectFileError(_("build.fileName: 不能为空"))
    if len(name) > 200:
        raise ProjectFileError(_("build.fileName: 太长了"))

    if total_modes > 1:
        stem, dot, ext = name.rpartition(".")
        if dot:
            name = f"{stem}-{MODE_SUFFIX[mode]}.{ext}"
        else:
            name = f"{name}-{MODE_SUFFIX[mode]}"
    return name


def placeholder_table(project: Project, mode: str) -> dict[str, str]:
    app = project.app
    return {
        "appName": app.name,
        "appVersion": app.version,
        "appPublisher": app.publisher,
        "appCopyright": app.copyright,
        "appHomepage": app.homepage,
        "appDescription": app.description,
        "installDirName": app.dir_name,
        "installMode": MODE_LABELS[mode],
    }


def version_lang_ids(languages) -> list[str]:
    """程序属性「语言」要写的 NSIS LANG 号（去重、按出现顺序）。

    英语-美国（1033）不写 —— NSIS 自带一个默认块就是它，属性里总会显示。
    """
    ids: list[str] = []
    for entry in languages or []:
        lcid = getattr(entry, "lcid", 0)
        if not lcid or lcid == 1033:
            continue
        value = str(lcid)
        if value not in ids:
            ids.append(value)
    return ids


class NsiGenerator:
    def __init__(self, project: Project, mode: str, build_dir: Path) -> None:
        if mode not in MODE_LABELS:
            raise ProjectFileError(_("未知的安装模式：{mode}").format(mode=mode))
        self.p = project
        self.mode = mode
        self.build_dir = Path(build_dir)
        self.table = placeholder_table(project, mode)
        self.out: list[str] = []

        self.license_abs: Path | None = None
        self.changelog_abs: Path | None = None
        self.license_text: str | None = None
        self.changelog_text: str | None = None

        # 页面是否需要出现（这两项要看过内容才知道，由 _prepare 决定）
        self.has_license = False
        self.has_changelog = False
        self.has_welcome = project.interface.welcome.enabled
        self.has_directory = project.install.allow_change_dir
        self.shortcut_sections = [
            s for s in (project.shortcuts.desktop, project.shortcuts.start_menu) if s.enabled
        ]
        self.has_options = bool(project.interface.options_page.enabled and self.shortcut_sections)

    # -- 对外入口 -----------------------------------------------------------

    def generate(self, output_name: str) -> str:
        self._prepare()
        self._emit_header()
        self._emit_app_defines()
        self._emit_mode_block()
        self._emit_compiler_and_meta(output_name)
        self._emit_interface_defines()
        self._emit_pages()
        self._emit_autostart_function()
        self._emit_variables()
        self._emit_on_init()
        if self.has_changelog:
            self._emit_changelog_page()
        if self.has_options:
            self._emit_options_page()
        self._emit_install_sections()
        self._emit_uninstall()
        text = "\n".join(self.out).rstrip() + "\n"
        return text

    # -- 预处理 -------------------------------------------------------------

    def _prepare(self) -> None:
        """先定下「哪几页要出现」和两份文本的内容，后面各处直接读这里的结果。"""
        interface = self.p.interface
        self.license_text = self._page_text(
            interface.license, "interface.license.file")
        self.changelog_text = self._page_text(
            interface.changelog, "interface.changelog.file")

        # 内容为空就不该出现这一页（少一页，总好过生成出空白页面或编译报错）
        self.has_license = bool(interface.license.enabled and self.license_text)
        self.has_changelog = bool(interface.changelog.enabled and self.changelog_text)
        self.has_options = bool(interface.options_page.enabled and self.shortcut_sections)

        self._stage_files()

    def _page_text(self, page, where: str) -> str | None:
        """取一份文本：来源是「文件」就转码读入，来源是「直接编辑」就用内嵌正文。"""
        if getattr(page, "source", "text") == "file":
            if not page.file:
                return None
            try:
                src = self.p.resolve(where, page.file)
            except ProjectFileError:
                raise
            try:
                return assets.read_text_auto(src)
            except OSError as exc:
                raise ProjectFileError(
                _("{where}: 读不了 {file}：{exc}").format(
                    where=where, file=page.file, exc=exc)) from exc
        return page.body()

    def _stage_files(self) -> None:
        """把两份文本写到 build/ 目录，编码按 NSIS 的要求来。"""
        self.build_dir.mkdir(parents=True, exist_ok=True)

        if self.has_license and self.license_text is not None:
            self.license_abs = self.build_dir / "license.txt"
            assets.write_utf8_bom(self.license_text, self.license_abs)

        if self.has_changelog and self.changelog_text is not None:
            self.changelog_abs = self.build_dir / "changelog.txt"
            assets.write_utf16le_bom(self.changelog_text, self.changelog_abs)

    # -- 输出辅助 -----------------------------------------------------------

    def add(self, *parts: str) -> None:
        self.out.append("".join(str(x) for x in parts))

    def blank(self) -> None:
        self.out.append("")

    def comment(self, text: str) -> None:
        self.out.append("; " + text)

    def r(self, text: str, where: str) -> str:
        """展开占位符 + NSIS 转义。"""
        return render(text, self.table, where)

    def define(self, name: str, value: str, where: str, indent: str = "") -> None:
        self.out.append(f'{indent}!define {name} "{self.r(value, where)}"')

    @staticmethod
    def _abs(path: Path | str) -> str:
        return str(path).replace("/", "\\")

    # -- 各段落 -------------------------------------------------------------

    def _emit_header(self) -> None:
        p = self.p
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.out.append("; " + "=" * 74)
        self.comment("  " + p.app.name + " 安装脚本")
        self.comment(f"  由「{APP_NAME}」v{__version__} 自动生成，请不要手工修改")
        self.comment(f"  源工程: {p.source_path.name}")
        self.comment(f"  目标模式: {self.mode}（编译时加 /DPER_USER 得到「仅当前用户安装」版本）")
        self.comment(f"  生成于: {now}")
        self.out.append("; " + "=" * 74)
        self.blank()
        self.add("Unicode true")
        self.add(COMPRESSOR[self.p.build.compression])
        self.blank()

    def _emit_app_defines(self) -> None:
        app = self.p.app
        self.comment("------ 应用信息 ------")
        self.define("APP_NAME", app.name, "app.name")
        self.define("APP_VERSION", app.version, "app.version")
        self.define("APP_PUBLISHER", app.publisher, "app.publisher")
        self.define("APP_COPYRIGHT", app.copyright, "app.copyright")
        self.define("APP_URL", app.homepage, "app.homepage")
        self.define("APP_DESC", app.description, "app.description")
        self.define("APP_EXE", app.main_exe, "app.mainExe")
        self.define("APP_EXE_ARGS", app.main_exe_args, "app.mainExeArgs")
        self.define("APP_REGKEY", app.registry_key, "app.registryKey")
        self.define("DIR_NAME", app.dir_name, "app.dirName")
        # 这两个里有 ${...}，不能走 r()（会被当成未知占位符），直接拼
        self.add('!define APP_UNINST_KEY "Software\\Microsoft\\Windows\\CurrentVersion'
                 '\\Uninstall\\${APP_REGKEY}"')
        self.blank()

    def _emit_mode_block(self) -> None:
        self.comment("------ 安装模式（编译时用 /DPER_USER 切换）------")
        self.add("!ifdef PER_USER")
        self.add('  !define REQUEST_LEVEL "user"')
        self.add('  !define INSTALL_BASE  "$LOCALAPPDATA\\Programs"')
        self.add('  !define REG_HIVE      "HKCU"')
        self.add('  !define SHELL_VAR     "current"')
        self.blank()
        self.add("!else")
        self.add('  !define REQUEST_LEVEL "admin"')
        self.add('  !define INSTALL_BASE  "$PROGRAMFILES64"')
        self.add('  !define REG_HIVE      "HKLM"')
        self.add('  !define SHELL_VAR     "all"')
        self.blank()
        self.add("!endif")

        custom = self.p.install.default_dir
        if custom:
            self.add(f'!define INSTALL_DIR_FULL "{self.r(custom, "install.defaultDir")}"')
        else:
            self.add('!define INSTALL_DIR_FULL "${INSTALL_BASE}\\${DIR_NAME}"')
        self.blank()

    def _emit_compiler_and_meta(self, output_name: str) -> None:
        app = self.p.app
        interface = self.p.interface
        out_dir = self.p.output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / output_name

        self.add(f'!ifndef OUTFILE_NAME')
        self.add(f'  !define OUTFILE_NAME "{self.r(output_name, "build.fileName")}"')
        self.add(f'!endif')
        self.blank()

        self.add('Name "${APP_NAME}"')
        self.add(f'OutFile "{self._abs(out_path)}"')
        self.add("RequestExecutionLevel ${REQUEST_LEVEL}")
        self.add('InstallDir "${INSTALL_DIR_FULL}"')
        if self.p.install.remember_last_dir:
            self.add('InstallDirRegKey ${REG_HIVE} "Software\\${APP_REGKEY}" "InstallDir"')
        detail = "show" if interface.show_details else "nevershow"
        self.add(f"ShowInstDetails {detail}")
        self.add(f"ShowUninstDetails {detail}")
        self.blank()

        self.add(f'VIProductVersion "{self.r(app.file_version, "app.fileVersion")}"')
        keys = [
            ("ProductName", app.name, "app.name"),
            ("FileDescription", app.description, "app.description"),
            ("FileVersion", app.file_version, "app.fileVersion"),
            ("ProductVersion", app.version, "app.version"),
            ("CompanyName", app.publisher, "app.publisher"),
            ("LegalCopyright", app.copyright, "app.copyright"),
            ("OriginalFilename", output_name, "build.fileName"),
        ]
        for key, value, where in keys:
            self.out.append(f'VIAddVersionKey "{key}" "{self.r(value, where)}"')
        for lang in version_lang_ids(interface.languages):
            for key, value, where in keys:
                self.out.append(f'VIAddVersionKey /LANG={lang} "{key}" "{self.r(value, where)}"')
        for key, value, where in keys:
            self.out.append(f'VIAddVersionKey "{key}" "{self.r(value, where)}"')
        if lang:
            for key, value, where in keys:
                self.out.append(f'VIAddVersionKey /LANG={lang} "{key}" "{self.r(value, where)}"')
        self.blank()

    def _emit_interface_defines(self) -> None:
        interface = self.p.interface
        self.comment("------ 安装界面 ------")
        self.add('!include "MUI2.nsh"')
        self.add('!include "LogicLib.nsh"')
        self.add('!include "WinMessages.nsh"')
        self.add('!include "FileFunc.nsh"')
        self.add('!include "x64.nsh"')
        self.blank()

        if interface.show_abort_warning:
            self.add("!define MUI_ABORTWARNING")
        if self.p.app.icon:
            icon = self._abs(self.p.resolve("app.icon", self.p.app.icon))
            self.add(f'!define MUI_ICON   "{icon}"')
            self.add(f'!define MUI_UNICON "{icon}"')
        if self.has_welcome and interface.welcome.image:
            image = self._abs(self.p.resolve("interface.welcome.image", interface.welcome.image))
            self.add(f'!define MUI_WELCOMEFINISHPAGE_BITMAP "{image}"')
        if interface.header_image:
            image = self._abs(self.p.resolve("interface.headerImage", interface.header_image))
            self.add("!define MUI_HEADERIMAGE")
            self.add(f'!define MUI_HEADERIMAGE_BITMAP "{image}"')
        self.blank()
        self.define("MUI_BRANDING", interface.branding_text, "interface.brandingText")
        self.add("BrandingText \"${MUI_BRANDING}\"")
        self.blank()

    def _emit_pages(self) -> None:
        interface = self.p.interface

        if self.has_welcome:
            self.comment("------ 1. 欢迎页 ------")
            self.define("MUI_WELCOMEPAGE_TITLE", interface.welcome.title, "interface.welcome.title")
            self.define("MUI_WELCOMEPAGE_TEXT", interface.welcome.text, "interface.welcome.text")
            self.add("!insertmacro MUI_PAGE_WELCOME")
            self.blank()

        if self.has_license:
            self.comment("------ 2. 许可协议页 ------")
            self.define("MUI_LICENSEPAGE_TEXT_TOP", interface.license.text_top, "interface.license.textTop")
            if interface.license.text_bottom:
                self.define("MUI_LICENSEPAGE_TEXT_BOTTOM",
                            interface.license.text_bottom, "interface.license.textBottom")
            if interface.license.require_accept:
                self.add("!define MUI_LICENSEPAGE_CHECKBOX")
                self.define("MUI_LICENSEPAGE_CHECKBOX_TEXT",
                            interface.license.accept_text, "interface.license.acceptText")
            self.add(f'!insertmacro MUI_PAGE_LICENSE "{self._abs(self.license_abs)}"')
            self.blank()

        if self.has_changelog:
            self.comment("------ 3. 更新日志页（自定义页面）------")
            self.add("Page custom ChangelogPageCreate ChangelogPageLeave")
            self.blank()

        if self.has_directory:
            self.comment("------ 4. 安装位置页 ------")
            self.define("MUI_DIRECTORYPAGE_TEXT_TOP",
                        interface.directory_page.text_top, "interface.directoryPage.textTop")
            self.define("MUI_DIRECTORYPAGE_TEXT_DESTINATION",
                        interface.directory_page.text_destination, "interface.directoryPage.textDestination")
            self.add("!insertmacro MUI_PAGE_DIRECTORY")
            self.blank()

        if self.has_options:
            self.comment("------ 5. 安装选项页（自定义页面）------")
            self.add("Page custom OptionsPageCreate OptionsPageLeave")
            self.blank()

        self.comment("------ 6. 安装进度页 ------")
        self.add("!insertmacro MUI_PAGE_INSTFILES")
        self.blank()

        self.comment("------ 7. 完成页 ------")
        finish = interface.finish
        self.define("MUI_FINISHPAGE_TITLE", finish.title, "interface.finish.title")
        self.define("MUI_FINISHPAGE_TEXT", finish.text, "interface.finish.text")
        if finish.run_app and self.p.app.main_exe:
            self.add('!define MUI_FINISHPAGE_RUN "$INSTDIR\\${APP_EXE}"')
            self.define("MUI_FINISHPAGE_RUN_TEXT", finish.run_text, "interface.finish.runText")
        if finish.autostart_enabled:
            # 借 MUI2 的「显示说明文件」复选框来做「开机自启」：勾选时调用我们
            # 自己的函数（MUI_FINISHPAGE_SHOWREADME_FUNCTION），所以那个「文件」
            # 值用不到，留空即可。
            self.add('!define MUI_FINISHPAGE_SHOWREADME ""')
            self.define("MUI_FINISHPAGE_SHOWREADME_TEXT", finish.autostart_text,
                        "interface.finish.autostartText")
            self.add("!define MUI_FINISHPAGE_SHOWREADME_FUNCTION JianPackAutostart")
            if not finish.autostart_default:
                self.add("!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED")
        if finish.link.enabled and finish.link.url:
            self.define("MUI_FINISHPAGE_LINK", finish.link.text, "interface.finish.link.text")
            self.define("MUI_FINISHPAGE_LINK_LOCATION", finish.link.url, "interface.finish.link.url")
        self.add("!insertmacro MUI_PAGE_FINISH")
        self.blank()

        self.comment("------ 卸载页面 ------")
        self.add("!insertmacro MUI_UNPAGE_CONFIRM")
        self.add("!insertmacro MUI_UNPAGE_INSTFILES")
        self.blank()

        self.comment("------ 语言 ------")
        self.add('!insertmacro MUI_LANGUAGE "SimpChinese"')
        self.blank()

    def _emit_variables(self) -> None:
        self.comment("------ 变量 ------")
        if self.has_changelog:
            self.add("Var ChangelogLine")
        if self.has_options:
            self.add("Var DesktopShortcutCheck")
            self.add("Var StartMenuShortcutCheck")
        self.add("Var CreateDesktopShortcut")
        self.add("Var CreateStartMenuShortcut")
        if self.p.uninstall.ask_keep_user_data and self.p.uninstall.user_data_path:
            self.add("Var DeleteUserData")
        self.blank()

    def _emit_on_init(self) -> None:
        uninstall = self.p.uninstall
        self.comment("------ 初始化 ------")
        self.add("Function .onInit")
        self.add("  ${If} ${RunningX64}")
        self.add("    SetRegView 64")
        self.add("  ${EndIf}")
        self.add("  SetShellVarContext ${SHELL_VAR}")

        if self.has_changelog:
            self.blank()
            self.comment("  把更新日志释放到临时目录（必须是 UTF-16LE，供 FileReadUTF16LE 读取）")
            self.add("  InitPluginsDir")
            self.add(f'  File /oname=$PLUGINSDIR\\changelog.txt "{self._abs(self.changelog_abs)}"')

        self.blank()
        self.comment("  静默安装（/S）会跳过自定义页面，这里给默认值")
        self._add_default_state("CreateDesktopShortcut", self.p.shortcuts.desktop.default,
                                self.p.shortcuts.desktop.enabled)
        self._add_default_state("CreateStartMenuShortcut", self.p.shortcuts.start_menu.default,
                                self.p.shortcuts.start_menu.enabled)
        if uninstall.ask_keep_user_data and uninstall.user_data_path:
            default = "1" if uninstall.delete_user_data_by_default else "0"
            self.add(f'  StrCpy $DeleteUserData "{default}"')
        self.add("FunctionEnd")
        self.blank()

    def _add_default_state(self, var: str, default: bool, enabled: bool) -> None:
        checked = default and enabled
        value = "${BST_CHECKED}" if checked else "${BST_UNCHECKED}"
        self.add(f"  StrCpy ${var} {value}")

    def _emit_changelog_page(self) -> None:
        interface = self.p.interface.changelog
        self.comment("------ 自定义页面：更新日志 ------")
        self.add("Function ChangelogPageCreate")
        self.out.append(f'  !insertmacro MUI_HEADER_TEXT "{self.r(interface.title, "interface.changelog.title")}" '
                        f'"{self.r(interface.subtitle, "interface.changelog.subtitle")}"')
        self.add("  nsDialogs::Create 1018")
        self.add("  Pop $0")
        self.add("  ${If} $0 == error")
        self.add("    Abort")
        self.add("  ${EndIf}")
        self.blank()
        self.add('  ${NSD_CreateRichEdit} 0 0 100% 100% ""')
        self.add("  Pop $1")
        self.add('  CreateFont $2 "Microsoft YaHei UI" 9')
        self.add("  SendMessage $1 ${WM_SETFONT} $2 1")
        self.add("  SetCtlColors $1 0x3C3C3C 0xFFFFFF")
        self.blank()
        self.add("  ; 一行一行直接塞进控件，不先攒到变量里 ——")
        self.add("  ; NSIS 的变量默认只有 1024 个字符，长日志会被悄悄截断。")
        self.add("  ClearErrors")
        self.add('  FileOpen $0 "$PLUGINSDIR\\changelog.txt" r')
        self.add("  IfErrors cl_read_done")
        self.add("cl_read_loop:")
        self.add("  FileReadUTF16LE $0 $ChangelogLine")
        self.add("  IfErrors cl_read_close")
        self.add('  SendMessage $1 ${EM_REPLACESEL} 0 "STR:$ChangelogLine"')
        self.add("  Goto cl_read_loop")
        self.add("cl_read_close:")
        self.add("  FileClose $0")
        self.add("cl_read_done:")
        self.add("  SendMessage $1 0x00CF 1 0            ; EM_SETREADONLY")
        self.blank()
        self.add("  nsDialogs::Show")
        self.add("FunctionEnd")
        self.blank()
        self.add("Function ChangelogPageLeave")
        self.add("FunctionEnd")
        self.blank()

    def _emit_options_page(self) -> None:
        options = self.p.interface.options_page
        desktop = self.p.shortcuts.desktop
        start_menu = self.p.shortcuts.start_menu

        self.comment("------ 自定义页面：安装选项 ------")
        self.add("Function OptionsPageCreate")
        self.out.append(f'  !insertmacro MUI_HEADER_TEXT "{self.r(options.title, "interface.optionsPage.title")}" '
                        f'"{self.r(options.subtitle, "interface.optionsPage.subtitle")}"')
        self.blank()
        self.add("  nsDialogs::Create 1018")
        self.add("  Pop $0")
        self.add("  ${If} $0 == error")
        self.add("    Abort")
        self.add("  ${EndIf}")
        self.blank()
        if options.group_text:
            self.out.append(f'  ${{NSD_CreateGroupBox}} 0 0 100% 100% '
                            f'"{self.r(options.group_text, "interface.optionsPage.groupText")}"')
            self.add("  Pop $0")
            self.blank()
        if options.intro:
            self.out.append(f'  ${{NSD_CreateLabel}} 12u 18u 88% 20u '
                            f'"{self.r(options.intro, "interface.optionsPage.intro")}"')
            self.add("  Pop $0")
            self.add("  SetCtlColors $0 0x646464 transparent")
            self.blank()

        if desktop.enabled:
            label = "在桌面创建 " + "{" + "shortcutName" + "}" + " 的快捷方式(&D)"
            label = label.replace("{shortcutName}", desktop.name)
            self.out.append(f'  ${{NSD_CreateCheckbox}} 12u 46u 88% 12u "{self.r(label, "shortcuts.desktop.name")}"')
            self.add("  Pop $DesktopShortcutCheck")
            self.add("  ${NSD_Check} $DesktopShortcutCheck" if desktop.default
                     else "  ${NSD_Uncheck} $DesktopShortcutCheck")
            if not desktop.user_can_toggle:
                self.add("  EnableWindow $DesktopShortcutCheck 0")
            self.blank()

        if start_menu.enabled:
            label = "在开始菜单创建 " + start_menu.name + " 的快捷方式(&S)"
            self.out.append(f'  ${{NSD_CreateCheckbox}} 12u 64u 88% 12u "{self.r(label, "shortcuts.startMenu.name")}"')
            self.add("  Pop $StartMenuShortcutCheck")
            self.add("  ${NSD_Check} $StartMenuShortcutCheck" if start_menu.default
                     else "  ${NSD_Uncheck} $StartMenuShortcutCheck")
            if not start_menu.user_can_toggle:
                self.add("  EnableWindow $StartMenuShortcutCheck 0")
            self.blank()

        if options.hint:
            self.out.append(f'  ${{NSD_CreateLabel}} 12u 92u 88% 16u '
                            f'"{self.r(options.hint, "interface.optionsPage.hint")}"')
            self.add("  Pop $0")
            self.add("  SetCtlColors $0 0x969696 transparent")
            self.blank()
        self.add("  nsDialogs::Show")
        self.add("FunctionEnd")
        self.blank()

        self.add("Function OptionsPageLeave")
        if desktop.enabled:
            if desktop.user_can_toggle:
                self.add("  ${NSD_GetState} $DesktopShortcutCheck $CreateDesktopShortcut")
            else:
                value = "${BST_CHECKED}" if desktop.default else "${BST_UNCHECKED}"
                self.add(f"  ; 不允许用户修改，按工程设定强制取值")
                self.add(f"  StrCpy $CreateDesktopShortcut {value}")
        if start_menu.enabled:
            if start_menu.user_can_toggle:
                self.add("  ${NSD_GetState} $StartMenuShortcutCheck $CreateStartMenuShortcut")
            else:
                value = "${BST_CHECKED}" if start_menu.default else "${BST_UNCHECKED}"
                self.add(f"  ; 不允许用户修改，按工程设定强制取值")
                self.add(f"  StrCpy $CreateStartMenuShortcut {value}")
        self.add("FunctionEnd")
        self.blank()

    def _emit_autostart_function(self) -> None:
        """完成页勾了「开机自启」时写 Run 键（由 MUI2 在完成页调用）。"""
        if not self.p.interface.finish.autostart_enabled:
            return
        self.comment("------ 完成页：勾选「开机自启」时写入 Run 键 ------")
        self.add("Function JianPackAutostart")
        self.add('  WriteRegStr ${REG_HIVE} '
                 '"Software\\Microsoft\\Windows\\CurrentVersion\\Run" '
                 '"${APP_NAME}" "$\\"$INSTDIR\\${APP_EXE}$\\""')
        self.add("FunctionEnd")
        self.blank()

    def _emit_install_sections(self) -> None:
        app = self.p.app
        uninstall = self.p.uninstall

        self.comment("------ 安装 ------")
        self.add('Section "主程序" SecMain')
        self.add("  SectionIn RO")
        self.blank()
        self._emit_payload()
        self.blank()
        self.add('  WriteUninstaller "$INSTDIR\\Uninstall.exe"')
        self.blank()

        if self.p.install.remember_last_dir:
            self.add('  WriteRegStr ${REG_HIVE} "Software\\${APP_REGKEY}" "InstallDir" "$INSTDIR"')
            self.blank()

        self.comment('  控制面板「程序和功能」里的卸载条目')
        self.add('  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "DisplayName"     "${APP_NAME}"')
        self.add('  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "DisplayVersion"  "${APP_VERSION}"')
        self.add('  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "DisplayIcon"     "$INSTDIR\\${APP_EXE}"')
        self.add('  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "Publisher"       "${APP_PUBLISHER}"')
        self.add('  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "URLInfoAbout"    "${APP_URL}"')
        self.add('  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "InstallLocation" "$INSTDIR"')
        self.add('  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "UninstallString" '
                 '"$\\"$INSTDIR\\Uninstall.exe$\\""')
        self.add('  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "QuietUninstallString" '
                 '"$\\"$INSTDIR\\Uninstall.exe$\\" /S"')
        self.add('  WriteRegDWORD ${REG_HIVE} "${APP_UNINST_KEY}" "NoModify" 1')
        self.add('  WriteRegDWORD ${REG_HIVE} "${APP_UNINST_KEY}" "NoRepair" 1')
        if self.p.install.estimated_size_auto:
            self.blank()
            self.add('  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2')
            self.add('  IntFmt $0 "0x%08X" $0')
            self.add('  WriteRegDWORD ${REG_HIVE} "${APP_UNINST_KEY}" "EstimatedSize" "$0"')
        self.add("SectionEnd")
        self.blank()

        if self.shortcut_sections:
            self._emit_shortcut_section()
        self.blank()

        self._emit_integration_section()

    def _emit_integration_section(self) -> None:
        """文件关联 / URL 协议 / 注册表 / 开机自启（安装时写入）。"""
        itg = self.p.integration
        if not (itg.associations or itg.protocols or itg.registry):
            return

        app_exe = "$INSTDIR\\${APP_EXE}"

        self.add('Section "系统集成" SecIntegration')
        self.add("  SectionIn RO")
        self.blank()

        for entry in itg.associations:
            ext = entry.ext.strip()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = "." + ext
            prog = "${APP_REGKEY}" + ext
            desc = self.r(entry.description or self.p.app.name, "integration.associations[].description")
            icon = entry.icon.strip()
            icon_path = (f"$INSTDIR\\{self.r(icon, 'integration.associations[].icon')}"
                         if icon else app_exe)
            self.comment("  文件关联 " + ext)
            self.add(f'  WriteRegStr ${{REG_HIVE}} "Software\\Classes\\{prog}" "" "{desc}"')
            self.add(f'  WriteRegStr ${{REG_HIVE}} "Software\\Classes\\{prog}\\DefaultIcon" '
                     f'"" "{icon_path},0"')
            self.add(f'  WriteRegStr ${{REG_HIVE}} "Software\\Classes\\{prog}\\shell\\open\\command" '
                     f'"" "$\\"{app_exe}$\\" $\\"%1$\\""')
            self.add(f'  WriteRegStr ${{REG_HIVE}} "Software\\Classes\\{ext}\\OpenWithProgids" '
                     f'"{prog}" ""')
            if entry.is_default:
                self.add(f'  WriteRegStr ${{REG_HIVE}} "Software\\Classes\\{ext}" "" "{prog}"')
            self.blank()

        for entry in itg.protocols:
            scheme = entry.scheme.strip()
            if not scheme:
                continue
            desc = self.r(entry.description or self.p.app.name, "integration.protocols[].description")
            self.comment("  URL 协议 " + scheme)
            self.add(f'  WriteRegStr ${{REG_HIVE}} "Software\\Classes\\{scheme}" "" '
                     f'"URL:{scheme} Protocol"')
            self.add(f'  WriteRegStr ${{REG_HIVE}} "Software\\Classes\\{scheme}" "URL Protocol" ""')
            self.add(f'  WriteRegStr ${{REG_HIVE}} "Software\\Classes\\{scheme}\\DefaultIcon" '
                     f'"" "{app_exe},0"')
            self.add(f'  WriteRegStr ${{REG_HIVE}} "Software\\Classes\\{scheme}\\shell\\open\\command" '
                     f'"" "$\\"{app_exe}$\\" $\\"%1$\\""')
            self.blank()

        for entry in itg.registry:
            path = entry.path.strip().strip("\\")
            if not path:
                continue
            hive = "HKCU" if entry.root == "HKCU" else "HKLM"
            name = self.r(entry.name.strip(), "integration.registry[].name")
            self.comment("  注册表 " + entry.root + "\\" + path)
            if entry.type == "REG_DWORD":
                try:
                    number = int(str(entry.data).strip() or "0", 0)
                except ValueError:
                    number = 0
                self.add(f'  WriteRegDWORD {hive} "{path}" "{name}" {number}')
            else:
                command = ("WriteRegExpandStr" if entry.type == "REG_EXPAND_SZ"
                           else "WriteRegStr")
                data = self.r(entry.data, "integration.registry[].data")
                if name:
                    self.add(f'  {command} {hive} "{path}" "{name}" "{data}"')
                else:
                    self.add(f'  {command} {hive} "{path}" "" "{data}"')
            self.blank()

        self.add("SectionEnd")

    def _emit_payload(self) -> None:
        """输出打包内容的复制指令。

        没有 include/exclude 的文件夹用 ``File /r``（紧凑，且能保留空目录）；
        带过滤条件的则逐个文件列举。
        """
        for item in self.p.files.items:
            src = self.p.resolve("files.items[].source", item.source)
            # 文件夹默认保留自己的名字，也可以只放内容（见 FileItem.keep_folder）
            folder_dest = _join_dest(item.dest, src.name) if item.keep_folder else item.dest

            if item.type == "folder" and not item.include and not item.exclude:
                self.add(f'  SetOutPath "{self._dest_dir(folder_dest)}"')
                self.add(f'  File /r "{self._abs(src)}\\*.*"')
                self.blank()
            elif item.type == "file":
                self.add(f'  SetOutPath "{self._dest_dir(item.dest)}"')
                self.add(f'  File "{self._abs(src)}"')
            else:
                self._emit_filtered_folder(item, src)

    def _emit_filtered_folder(self, item, src: Path) -> None:
        """逐文件列举，顺带把空目录用 CreateDirectory 补回来。"""
        folder_dest = _join_dest(item.dest, src.name) if item.keep_folder else item.dest
        base = self._dest_rel(folder_dest)
        groups: dict[str, list[Path]] = {}
        empty_dirs: list[str] = []

        for path in sorted(src.rglob("*")):
            if path.is_dir():
                if not any(child.is_file() for child in path.rglob("*")):
                    rel = path.relative_to(src).as_posix()
                    empty_dirs.append(_join_rel(base, rel))
                continue
            rel = path.relative_to(src).as_posix()
            if item.include and not _matches(rel, path.name, item.include):
                continue
            if item.exclude and _matches(rel, path.name, item.exclude):
                continue
            inner = rel.rsplit("/", 1)[0] if "/" in rel else ""
            groups.setdefault(_join_rel(base, inner), []).append(path)

        for key in sorted(groups):
            self.add(f'  SetOutPath "{self._dest_dir(key)}"')
            for path in groups[key]:
                self.add(f'  File "{self._abs(path)}"')
        for rel_dir in sorted(empty_dirs):
            self.add(f'  CreateDirectory "{self._dest_dir(rel_dir)}"')
        self.blank()

    def _dest_rel(self, dest: str) -> str:
        stripped = dest.strip()
        if stripped in ("", ".", "./", ".\\"):
            return ""
        return stripped.replace("\\", "/").strip("/")

    def _dest_dir(self, dest: str) -> str:
        rel = self._dest_rel(dest)
        return "$INSTDIR" + (f"\\{rel.replace('/', chr(92))}" if rel else "")

    def _emit_shortcut_section(self) -> None:
        desktop = self.p.shortcuts.desktop
        start_menu = self.p.shortcuts.start_menu
        self.add('Section "快捷方式" SecShortcut')
        self.add("  SectionIn RO")
        self.blank()

        if start_menu.enabled:
            name = self.r(start_menu.name, "shortcuts.startMenu.name")
            self.add("  ${If} $CreateStartMenuShortcut == ${BST_CHECKED}")
            if start_menu.use_folder:
                self.out.append(f'    CreateDirectory "$SMPROGRAMS\\{name}"')
                target_dir = f"$SMPROGRAMS\\{name}"
            else:
                target_dir = "$SMPROGRAMS"
            self.out.append(f'    CreateShortCut "{target_dir}\\{name}.lnk" '
                            f'"$INSTDIR\\${{APP_EXE}}" "" "$INSTDIR\\${{APP_EXE}}" 0')
            if start_menu.uninstall_shortcut:
                self.out.append(f'    CreateShortCut "{target_dir}\\卸载 {name}.lnk" '
                                f'"$INSTDIR\\Uninstall.exe" "" "$INSTDIR\\Uninstall.exe" 0')
            self.add("  ${EndIf}")
            self.blank()

        if desktop.enabled:
            name = self.r(desktop.name, "shortcuts.desktop.name")
            self.add("  ${If} $CreateDesktopShortcut == ${BST_CHECKED}")
            self.out.append(f'    CreateShortCut "$DESKTOP\\{name}.lnk" '
                            f'"$INSTDIR\\${{APP_EXE}}" "" "$INSTDIR\\${{APP_EXE}}" 0')
            self.add("  ${EndIf}")
            self.blank()

        self.add("SectionEnd")

    def _emit_integration_uninstall(self) -> None:
        """把安装时写进去的「系统集成」在卸载时清理干净。"""
        itg = self.p.integration
        for entry in itg.associations:
            ext = entry.ext.strip()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = "." + ext
            prog = "${APP_REGKEY}" + ext
            self.add(f'  DeleteRegKey ${{REG_HIVE}} "Software\\Classes\\{prog}"')
            self.add(f'  DeleteRegValue ${{REG_HIVE}} '
                     f'"Software\\Classes\\{ext}\\OpenWithProgids" "{prog}"')
            if entry.is_default:
                self.add(f'  DeleteRegValue ${{REG_HIVE}} "Software\\Classes\\{ext}" ""')
        for entry in itg.protocols:
            scheme = entry.scheme.strip()
            if scheme:
                self.add(f'  DeleteRegKey ${{REG_HIVE}} "Software\\Classes\\{scheme}"')
        for entry in itg.registry:
            path = entry.path.strip().strip("\\")
            if not path:
                continue
            hive = "HKCU" if entry.root == "HKCU" else "HKLM"
            name = entry.name.strip()
            if name:
                self.add(f'  DeleteRegValue {hive} "{path}" "{name}"')
            else:
                self.add(f'  DeleteRegKey {hive} "{path}"')

    def _emit_uninstall(self) -> None:
        desktop = self.p.shortcuts.desktop
        start_menu = self.p.shortcuts.start_menu
        uninstall = self.p.uninstall
        has_userdata = bool(uninstall.user_data_path)
        ask = bool(uninstall.ask_keep_user_data and has_userdata)

        self.comment("------ 卸载 ------")
        if ask:
            text = self.r(uninstall.keep_user_data_text, "uninstall.keepUserDataText")
            default_id = "IDYES" if uninstall.delete_user_data_by_default else "IDNO"
            self.add("Function un.onInit")
            self.add("  ${If} ${RunningX64}")
            self.add("    SetRegView 64")
            self.add("  ${EndIf}")
            self.add("  SetShellVarContext ${SHELL_VAR}")
            self.blank()
            self.out.append(f'  MessageBox MB_YESNO|MB_ICONQUESTION "{text}" '
                            f'/SD {default_id} IDYES un_del_data IDNO un_keep_data')
            self.add('  StrCpy $DeleteUserData "0"')
            self.add("  Goto un_init_done")
            self.add("un_del_data:")
            self.add('  StrCpy $DeleteUserData "1"')
            self.add("un_keep_data:")
            self.add("un_init_done:")
            self.add("FunctionEnd")
        else:
            self.add("Function un.onInit")
            self.add("  ${If} ${RunningX64}")
            self.add("    SetRegView 64")
            self.add("  ${EndIf}")
            self.add("  SetShellVarContext ${SHELL_VAR}")
            self.add("FunctionEnd")
        self.blank()

        self.add('Section "Uninstall"')
        if start_menu.enabled:
            name = self.r(start_menu.name, "shortcuts.startMenu.name")
            if start_menu.use_folder:
                self.out.append(f'  Delete "$SMPROGRAMS\\{name}\\{name}.lnk"')
                if start_menu.uninstall_shortcut:
                    self.out.append(f'  Delete "$SMPROGRAMS\\{name}\\卸载 {name}.lnk"')
                self.out.append(f'  RMDir  "$SMPROGRAMS\\{name}"')
            else:
                self.out.append(f'  Delete "$SMPROGRAMS\\{name}.lnk"')
                if start_menu.uninstall_shortcut:
                    self.out.append(f'  Delete "$SMPROGRAMS\\卸载 {name}.lnk"')
        if desktop.enabled:
            name = self.r(desktop.name, "shortcuts.desktop.name")
            self.out.append(f'  Delete "$DESKTOP\\{name}.lnk"')
        self.blank()
        self.add("  ; 系统集成")
        if self.p.interface.finish.autostart_enabled:
            self.add('  DeleteRegValue ${REG_HIVE} '
                     '"Software\\Microsoft\\Windows\\CurrentVersion\\Run" "${APP_NAME}"')
        self._emit_integration_uninstall()
        self.add("  ; 程序文件")
        self.add('  RMDir /r "$INSTDIR"')
        self.blank()
        self.add("  ; 注册表")
        self.add('  DeleteRegKey ${REG_HIVE} "${APP_UNINST_KEY}"')
        if self.p.install.remember_last_dir:
            self.add('  DeleteRegKey ${REG_HIVE} "Software\\${APP_REGKEY}"')
        self.blank()

        if ask:
            user_data = self.r(uninstall.user_data_path, "uninstall.userDataPath")
            self.add("  ; 用户数据（由用户在卸载确认时决定是否保留）")
            self.add('  ${If} $DeleteUserData == "1"')
            self.out.append(f'    RMDir /r "{user_data}"')
            self.add("  ${EndIf}")
            self.blank()
        elif has_userdata and uninstall.delete_user_data_by_default:
            user_data = self.r(uninstall.user_data_path, "uninstall.userDataPath")
            self.add("  ; 用户数据")
            self.out.append(f'  RMDir /r "{user_data}"')
            self.blank()

        self.add("  ; 兜底：安装目录如果空了就删掉")
        self.add('  RMDir "$INSTDIR"')
        if uninstall.auto_close and self.p.interface.show_details:
            self.add("  SetAutoClose true")
        self.add("SectionEnd")


def _join_dest(dest: str, name: str) -> str:
    """把条目名拼到「安装到」路径后面。

    空 / "." / "./" 都表示安装目录根部。
    """
    stripped = (dest or "").strip()
    if stripped in ("", ".", "./", ".\\"):
        return name
    return stripped.replace("\\", "/").strip("/") + "/" + name


def _join_rel(base: str, inner: str) -> str:
    if base and inner:
        return f"{base}/{inner}"
    return base or inner


def _matches(rel: str, basename: str, patterns: list[str]) -> bool:
    import fnmatch
    for pattern in patterns:
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(basename, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatch(rel, pattern[3:]):
            return True
    return False
