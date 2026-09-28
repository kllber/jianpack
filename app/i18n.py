"""界面语言（中文 / English）。

约定：

- 代码里仍然写中文原文，用 :func:`t`（别名 :data:`_`）包起来；
  选英文时用它查 :data:`EN` 里的翻译，查不到就退回中文（方便排查漏翻）。
- 语言变了要重建界面（和主题一样，见 ``MainWindow._restart``），
  所以所有文案都是在「创建控件时」取翻译，不做运行时热更新。
- **术语保持一致**，常用词统一如下：
    打包内容 Payload / 安装向导 installer / 安装包 installer / 工程 project /
    安装位置安装目录 install folder / 快捷方式 shortcut / 许可协议 license /
    更新日志 changelog / 首选项 Preferences / 教程 tutorial。
"""

from __future__ import annotations

LANGUAGES: tuple[tuple[str, str], ...] = (("zh", "中文"), ("en", "English"))
DEFAULT_LANGUAGE = "zh"

_lang = DEFAULT_LANGUAGE


def normalize(code: str | None) -> str:
    return code if code in dict(LANGUAGES) else DEFAULT_LANGUAGE


def set_language(code: str | None) -> str:
    global _lang
    _lang = normalize(code)
    return _lang


def current() -> str:
    return _lang


def is_english() -> bool:
    return _lang == "en"


def language_name(code: str | None = None) -> str:
    return dict(LANGUAGES).get(normalize(code if code is not None else _lang), "")


def t(text: str) -> str:
    """把中文原文翻成当前语言（中文直接返回原文）。"""
    if _lang == "zh":
        return text
    return EN.get(text, text)


# gettext 风格的短别名，写起来顺手一点
_ = t

ZH_APP_NAME = "简包装-应用安装向导打包软件"
ZH_APP_SHORT = "简包装"
EN_APP_NAME = "JianPack - App Installer Packer"
EN_APP_SHORT = "JianPack"


def app_name() -> str:
    """短名，用于窗口标题 / 任务栏（通常只显示这个）。"""
    return EN_APP_SHORT if _lang == "en" else ZH_APP_SHORT


def app_full_name() -> str:
    """全称，用在欢迎页、启动窗口、关于等能放下全称的地方。"""
    return EN_APP_NAME if _lang == "en" else ZH_APP_NAME


# ---------------------------------------------------------------------------
# 英文词条：键 = 中文原文（必须和源码里 ``_()`` 里的字符串完全一致）
# ---------------------------------------------------------------------------

EN: dict[str, str] = {
    # -- 通用 / 主题名 --
    "浅色": "Light",
    "深色": "Dark",

    # -- main_window：菜单 --
    "文件": "File",
    "工具": "Tools",
    "视图": "View",
    "帮助": "Help",
    "首选项/设置": "Preferences/Settings",
    "新建工程…": "New Project…",
    "打开工程…": "Open Project…",
    "保存": "Save",
    "另存为…": "Save As…",
    "退出": "Exit",
    "校验工程": "Validate Project",
    "打开输出目录": "Open Output Folder",
    "显示安装预览": "Show Installer Preview",
    "教程": "Tutorial",
    "关于": "About",
    "一个开源的应用安装包制作工具：把文件夹里的程序打成一个安装包，"
    "对方双击就能装。底层使用 NSIS，生成的安装包零依赖。":
        "An open-source installer builder: turn a folder of programs into an installer that "
        "installs with a double-click. Powered by NSIS; the installer has no runtime dependency.",
    "作者：": "Author: ",
    "邮箱：": "Email: ",
    "许可：": "License: ",
    "本软件是开源工具，欢迎使用、分发和反馈问题。":
        "This software is an open-source tool — feel free to use it, share it and report issues.",
    "免责声明：本软件按「现状」提供，不附带任何明示或暗示的担保。"
    "请确保你拥有所打包内容的合法权利，并遵守相关法律法规；"
    "因使用本软件产生的任何直接或间接后果由使用者自行承担。":
        "Disclaimer: this software is provided \"as is\", without warranty of any kind. Make sure "
        "you have the right to package the content and comply with applicable laws; the author is "
        "not liable for any direct or indirect consequences of using this software.",
    "开发过程中使用了 DeepSeek V4.1 Flash 进行辅助创作。":
        "Developed with assistance from DeepSeek V4.1 Flash.",
    "GitHub：": "GitHub: ",

    # -- main_window：状态栏 / 标题 / 弹窗 --
    "打包步骤": "Build Steps",
    "< 上一步": "< Back",
    "下一步 >": "Next >",
    "有未保存的改动": "unsaved changes",
    "已保存": "saved",
    "未命名工程": "Untitled Project",
    "当前项目：": "Current project: ",
    "工程：{path}    （{state}）": "Project: {path}    ({state})",
    "已保存到 {path}": "Saved to {path}",
    "正在保存工程…": "Saving project…",
    "把 .jianpack 关联到本程序（双击即可打开）":
        "Associate .jianpack with this app (double-click to open)",
    "设置文件关联失败": "Failed to Set File Association",
    "打开失败": "Open Failed",
    "保存失败": "Save Failed",
    "正在打开工程…": "Opening project…",
    "正在启动…": "Starting…",
    "正在打包…": "Building…",
    "正在打包… {mode}（{i}/{total}）": "Building… {mode} ({i}/{total})",
    "（提示：打包进度窗创建失败，不影响打包）":
        "(Note: the build progress window could not be created; the build is unaffected)",
    "还没有打开任何工程": "No project is open",
    "找不到文件": "File Not Found",
    "路径不存在：\n{path}": "The path does not exist:\n{path}",
    "这个位置在工程目录之外": "This Location Is Outside the Project Folder",
    "{path}\n\n把这个文件复制一份到工程目录里吗？\n\n"
    "「是」  —— 复制到工程的 {subdir}\\ 目录。\n"
    "        好处：整个工程文件夹可以随意搬移、压缩、发给别人。\n\n"
    "「否」  —— 直接引用原来的位置。\n"
    "        注意：工程一旦移走（或发到别的电脑）就会失效。":
        "{path}\n\nCopy this file into the project folder?\n\n"
        "Yes  — copy it into the project's {subdir}\\ folder.\n"
        "        Benefit: the whole project folder can be moved, zipped and shared.\n\n"
        "No   — reference the original location.\n"
        "        Note: the reference breaks if the project is moved or sent elsewhere.",
    "同名文件已存在": "A File With the Same Name Already Exists",
    "{name} 已经在 {subdir}\\ 里了，覆盖它吗？":
        "{name} is already in {subdir}\\ — overwrite it?",
    "复制失败": "Copy Failed",
    "还有未保存的改动": "Unsaved Changes",
    "工程「{name}」有未保存的改动，要先保存吗？":
        "The project \"{name}\" has unsaved changes. Save before continuing?",
    "校验没通过": "Validation Failed",
    "发现 {n} 个问题，详情见下方日志。":
        "Found {n} issue(s). See the log below.",
    "切换界面前需要先保存工程，但保存失败了：\n{exc}\n\n设置已经记下了，下次打开软件时生效。":
        "The project must be saved before switching the interface, but saving failed:\n{exc}\n\n"
        "The setting is stored and will take effect next time you open the app.",
    "把工程文件（.jianpack）编译成 Windows 安装包。\n"
    "底层使用 NSIS，生成出来的安装包不需要任何运行时依赖。\n\n"
    "Python {python}":
        "Compiles a project file (.jianpack) into a Windows installer.\n"
        "Powered by NSIS; the generated installer needs no runtime dependency.\n\n"
        "Python {python}",

    # -- base（步骤页公共）--
    "未选择": "Not set",
    "还没有选择图片": "No image selected",
    "找不到": "Not found",
    "找不到文件：{relative}": "File not found: {relative}",
    "文本文件": "Text file",
    "（还没有选择文件）": "(no file selected)",
    "（找不到文件：{file}）": "(file not found: {file})",
    "（这个文件读不出来）": "(cannot read this file)",
    "（正文是空的）": "(text is empty)",
    "重新选一张，或者点「清除」。": "Pick another image, or click Clear.",
    "尺寸符合要求（{w} × {h}）": "Size OK ({w} × {h})",
    "(预览失败)": "(preview failed)",
    "（预览失败）": "(preview failed)",
    "浏览…": "Browse…",
    "清除": "Clear",
    "选择图片…": "Choose Image…",
    "选择{title}": "Choose {title}",

    # -- engine TARGETS 的标题 / 提示（在界面里翻）--
    "欢迎页左侧图片": "Welcome left image",
    "正方形。程序会自动导出 16 / 24 / 32 / 48 / 64 / 128 / 256 各档尺寸，"
    "Windows 在桌面、任务栏、文件列表里都会挑合适的用。":
        "Square. Exported at 16 / 24 / 32 / 48 / 64 / 128 / 256 px; "
        "Windows picks the right size for the desktop, taskbar and file lists.",
    "横条，出现在许可协议 / 更新日志 / 安装位置等内页的左上角。":
        "A horizontal strip shown at the top-left of the inner pages.",
    "竖版，只出现在欢迎页和完成页的左侧。":
        "A vertical image shown on the left of the Welcome and Finish pages.",

    # -- 第 1 步：基本信息 --
    "基本信息": "Basic Info",
    "应用名称、版本、版权与图标": "Name, version, copyright, icon",
    "这些信息会出现在安装向导、快捷方式和「控制面板 - 程序和功能」里":
        "Shown in the installer, shortcuts and \"Apps & features\" in Control Panel",
    "带 * 的是必填项，其余留空也能打包，只是信息会少一些。":
        "Fields marked * are required; the rest can be left empty.",
    "应用标识": "App Identity",
    "应用名称 *": "App name *",
    "安装向导里显示的名字，例如「我的小工具」":
        "The name shown in the installer, e.g. \"My Tool\"",
    "安装目录名": "Install folder name",
    "装到磁盘上的文件夹名，例如 MyApp。留空则同应用名。"
    "中文软件建议用英文，中文路径在命令行和日志里容易出问题。":
        "Folder name on disk, e.g. MyApp. Defaults to the app name. "
        "An ASCII name is recommended for non-English apps.",
    "版本号 *": "Version *",
    "显示用版本，例如 1.0.0 / 1.0.0.1": "Display version, e.g. 1.0.0 / 1.0.0.1",
    "程序文件版本": "File version",
    "写进 exe 属性，必须是 a.b.c.d 四段数字。留空则按版本号自动补齐。":
        "Written into the exe properties; must be four numbers a.b.c.d. "
        "Defaults to a padded version.",
    "内部标识": "Internal ID",
    "注册表和卸载项用的键名，留空则同安装目录名。只能用字母、数字、- _ .":
        "Registry/uninstall key. Defaults to the install folder name. "
        "Letters, digits, - _ . only.",
    "版权与联系方式": "Copyright & Contact",
    "公司 / 作者": "Company / Author",
    "留空的话，控制面板的卸载列表里会显示「未知发布者」":
        "If empty, the uninstall list shows \"Unknown publisher\"",
    "版权信息": "Copyright",
    "例如 Copyright (C) 2026 示例软件工作室":
        "e.g. Copyright (C) 2026 Example Software Studio",
    "官网地址": "Website",
    "会写进程序属性和卸载项的「访问支持」":
        "Written into the program properties and the uninstall entry",
    "一句话描述": "Short description",
    "显示在程序属性里": "Shown in the program properties",
    "图标": "Icon",
    "程序图标": "App icon",
    "会用在安装包、桌面快捷方式、开始菜单和「程序和功能」列表里。":
        "Used for the installer, desktop shortcut, Start menu and Apps & features.",

    # -- 第 2 步：打包内容 --
    "打包内容": "Payload",
    "添加要装到用户电脑上的文件": "Add files to install",
    "把要装到用户电脑上的文件加进来，还可以调整它们在安装目录里的位置":
        "Add the files to install, and adjust where they land in the install folder",
    "选中的文件和文件夹会被打进安装包。若选的位置在工程目录之外，"
    "程序会问你要不要复制一份进工程——复制进来的话，"
    "整个工程文件夹就可以随意搬移、压缩、发给别人了。":
        "Selected files and folders are packed into the installer. If a source is outside "
        "the project folder, you'll be asked whether to copy it in — copying makes the whole "
        "project folder portable.",
    "添加文件…": "Add Files…",
    "添加文件夹…": "Add Folder…",
    "修改安装位置…": "Change Install Location…",
    "移除": "Remove",
    "上移": "Move Up",
    "下移": "Move Down",
    "类型": "Type",
    "来源": "Source",
    "安装到": "Installs to",
    "文件夹": "Folder",
    "文件": "File",
    "双击某一行可以修改它的安装位置和「保留文件夹名」。"
    "「安装到」写的是这个条目在安装目录里的路径，「.」表示安装目录根部。"
    "文件夹条目默认保留自己的名字（装成 安装目录\\a\\…）；"
    "取消「保留文件夹名」则只把里面的内容放到该目录。":
        "Double-click a row to change where an item installs and whether to keep the folder "
        "name. \"Installs to\" is the item's path inside the install folder; \".\" is the install "
        "folder root. Folder items keep their own name by default (installed as install "
        "folder\\a\\…); clear \"Keep folder name\" to place only the contents in that folder.",
    "主程序": "Main program",
    "重新识别": "Detect Again",
    "安装完成后「立即运行」和快捷方式都指向这个文件。留空则自动使用安装目录根部唯一的 .exe。":
        "The \"Run now\" checkbox and shortcuts point to this file. Leave empty to auto-detect "
        "the single .exe in the install root.",
    "已识别": "Detected",
    "主程序：{detected}": "Main program: {detected}",
    "无法自动识别": "Cannot Auto-detect",
    "没有选中": "Nothing Selected",
    "请先在列表里选中要移除的条目。": "Select the rows you want to remove first.",
    "请选中一项": "Select One Row",
    "上移/下移一次只能移动一条。": "Move Up/Down works on one row at a time.",
    "一次只能修改一条的安装位置。": "Change the install location of one row at a time.",
    "移除并删除工程里的副本": "Remove and Delete the Project Copies",
    "以下内容是当初复制进工程的，移除后会连同工程里的副本一起删除：\n\n"
    "{list}\n\n确定移除吗？":
        "The following items were copied into the project. Removing them will also delete "
        "those copies from the project:\n\n{list}\n\nRemove them?",
    "安装位置": "Install Location",
    "这个条目在安装目录里的位置：": "Where this item goes in the install folder:",
    "「.」表示安装目录根部，也可以写子目录，例如 docs 或 runtime\\bin。":
        "\".\" is the install folder root; you can also use a subfolder such as docs or "
        "runtime\\bin.",
    "保留文件夹名": "Keep folder name",
    "勾选后装成 安装目录\\{name}\\…；取消勾选则只把里面的内容"
    "放到上面的目录里（不再多一层「{name}」）。":
        "Checked: installs as install folder\\{name}\\…. Unchecked: only the contents go into "
        "the folder above (no extra \"{name}\" level).",
    "安装后": "After install",
    "安装后：{path}": "Installs to: {path}",
    "安装目录": "install folder",
    "是": "Yes",
    "否": "No",

    # -- 第 3 步：安装设置 --
    "安装设置": "Install Settings",
    "安装模式、安装路径、卸载": "Install mode, location, uninstall",
    "安装路径、用户数据与卸载": "Install location, user data and uninstall",
    "决定装到哪里、要不要管理员权限、卸载时怎么处理用户数据":
        "Where it installs, whether admin rights are needed, and how user data is handled",
    "决定默认装到哪、卸载时怎么处理用户数据（装给谁在第 6 步选）":
        "Where it installs by default and how user data is handled on uninstall "
        "(who it installs for is chosen in step 6)",
    "装给「所有用户」还是「仅当前用户」在第 6 步「打包」里选，"
    "两种版本也能同时生成。这一页只管安装路径、用户数据和卸载。":
        "\"For all users\" or \"current user only\" is chosen in step 6 (Build); you can build "
        "both. This page only handles the install location, user data and uninstall.",
    "安装模式": "Install Mode",
    "模式": "Mode",
    "为所有用户安装（装到 Program Files，安装时会弹 UAC 要管理员权限）":
        "Install for all users (Program Files; UAC admin prompt on install)",
    "仅当前用户安装（装到 %LOCALAPPDATA%\\Programs，免提权，双击就装）":
        "Install for the current user only (%LOCALAPPDATA%\\Programs; no admin, just double-click)",
    "两种模式可以同时生成，在第 6 步「打包」里勾选。":
        "You can build both; choose them in step 6 (Build).",
    "安装位置": "Install Location",
    "使用默认路径（按安装模式自动选择）": "Use the default path (chosen by install mode)",
    "自定义路径": "Custom path",
    "可以用 $PROGRAMFILES64 / $LOCALAPPDATA 这类变量，也可以用 {appName}。\n"
    "例如：  D:\\软件\\{appName}      或      $PROGRAMFILES64\\MyCorp\\{appName}":
        "You can use variables like $PROGRAMFILES64 / $LOCALAPPDATA, and {appName}.\n"
        "e.g.  D:\\Apps\\{appName}   or   $PROGRAMFILES64\\MyCorp\\{appName}",
    "允许用户在安装时修改安装位置": "Let the user change the install location",
    "关掉的话就不显示「安装位置」页，强制装到上面的路径":
        "When off, the Install Location page is hidden and the path above is forced",
    "记住上次安装的位置": "Remember the last install location",
    "写进注册表，下次安装（比如升级）时自动带出来":
        "Stored in the registry and reused on the next install (e.g. an upgrade)",
    "在「程序和功能」里显示占用空间": "Show the disk usage in Apps & features",
    "用户数据与卸载": "User Data & Uninstall",
    "用户数据目录": "User data folder",
    "程序运行时存放配置/数据的地方，例如 $APPDATA\\{appName}。留空表示没有独立的数据目录。":
        "Where the app stores its config/data, e.g. $APPDATA\\{appName}. "
        "Leave empty if there is no separate data folder.",
    "卸载时询问是否保留用户数据": "Ask whether to keep user data on uninstall",
    "询问文案": "Prompt text",
    "卸载时弹出的询问内容": "Message shown when uninstalling",
    "静默卸载默认": "Silent uninstall default",
    "保留用户数据（推荐）": "Keep user data (recommended)",
    "连用户数据一起删除": "Delete user data as well",
    "命令行静默卸载（Uninstall.exe /S）时按这个选项走":
        "Used by the command-line silent uninstall (Uninstall.exe /S)",

    # -- 第 4 步：安装界面 --
    "安装界面": "Installer UI",
    "各页面的文案与图片": "Text and images for each page",
    "自定义安装向导里每一页的文字和图片，留空就用默认内容":
        "Customize the text and images of every installer page; empty means default",
    "通用": "General",
    "文字里可以用这些占位符：{appName} {appVersion} {appPublisher} "
    "{appHomepage} {installMode}；"
    "也可以用 $INSTDIR 这类安装时才会确定的路径。":
        "You can use placeholders {appName} {appVersion} {appPublisher} "
        "{appHomepage} {installMode}, and install-time paths like $INSTDIR.",
    "底部状态栏": "Bottom status bar",
    "安装向导最下面那行小字": "The small line at the bottom of the installer",
    "安装中途取消时二次确认": "Confirm before cancelling the install",
    "显示安装过程日志": "Show the install log",
    "关掉之后安装界面更简洁，只留进度条": "Turn off for a cleaner page with just a progress bar",
    "内页页头图片": "Header image",
    "出现在许可协议 / 更新日志 / 安装位置等内页的左上角。不选也可以，页头就只显示标题文字。":
        "Shown at the top-left of inner pages (License / Changelog / Location). Optional.",
    "欢迎页": "Welcome",
    "许可协议": "License",
    "更新日志": "Changelog",
    "安装位置页": "Location Page",
    "安装选项页": "Options Page",
    "完成页": "Finish",
    "显示欢迎页": "Show the welcome page",
    "标题": "Title",
    "正文": "Text",
    "左侧图片": "Left image",
    "只出现在欢迎页和完成页的左侧。留空则用默认蓝色背景。":
        "Shown on the left of the Welcome and Finish pages. Empty uses the default blue.",
    "显示许可协议页": "Show the license page",
    "内容来源": "Content source",
    "直接在下面编辑": "Edit below",
    "从 txt 文件导入": "Import from a .txt file",
    "协议正文": "License text",
    "协议文件": "License file",
    "直接在这里写条款，改起来最快。换行和空行都按原样显示。":
        "Write the terms here. Line breaks are kept as-is.",
    "不用管编码，程序会自动转成 NSIS 需要的格式":
        "No need to worry about encoding; converted automatically",
    "读入编辑器（改成直接编辑）": "Load into editor (switch to editing)",
    "必须勾选「我接受」才能继续": "Require checking \"I accept\" to continue",
    "勾选文案": "Checkbox text",
    "上方提示": "Text above",
    "下方提示": "Text below",
    "显示在协议框上方的小字": "Small text above the license box",
    "显示在协议框下方的小字": "Small text below the license box",
    "显示更新日志页": "Show the changelog page",
    "日志正文": "Changelog text",
    "日志文件": "Changelog file",
    "每次发新版改这里就行。写多长都不会被截断。":
        "Update this for each release. There is no length limit.",
    "副标题": "Subtitle",
    "注意：如果第 3 步关掉了「允许用户修改安装位置」，这一页不会显示。":
        "Note: this page is hidden if \"Let the user change the install location\" is off in step 3.",
    "上方说明": "Text above",
    "输入框标签": "Field label",
    "显示安装选项页": "Show the options page",
    "只有第 5 步里至少启用了快捷方式时才会显示":
        "Only shown when at least one shortcut is enabled in step 5",
    "分组框标题": "Group box title",
    "说明": "Intro",
    "底部提示": "Hint at the bottom",
    "提供「立即运行」复选框": "Offer a \"Run now\" checkbox",
    "复选框文字": "Checkbox text",
    "显示超链接": "Show a hyperlink",
    "链接文字": "Link text",
    "链接地址": "Link URL",
    "可以用 $INSTDIR 显示安装位置": "You can use $INSTDIR to show the install location",
    "填官网地址，一般是 {appHomepage}": "Usually {appHomepage}",
    "两种来源随时切换，两边的内容都会保留；打包时只用当前选中的那一种。":
        "Both sources are kept; only the selected one is used when building.",
    "还没选文件": "No file selected",
    "先选一个 {noun} 的 txt 文件。": "Choose a .txt file for {noun} first.",
    "读不了这个文件": "Cannot Read File",
    "{noun}正文": "{noun} text",
    "{noun}文件": "{noun} file",
    "协议": "the license",
    "日志": "the changelog",

    # -- 第 5 步：快捷方式 --
    "快捷方式": "Shortcuts",
    "桌面 / 开始菜单快捷方式": "Desktop / Start menu shortcuts",
    "决定安装时创建哪些快捷方式，以及用户能不能自己改":
        "Which shortcuts to create, and whether the user can change them",
    "「允许用户修改」如果关掉，安装选项页上对应的复选框会变成灰色不可点，"
    "一律按「默认勾选」执行。":
        "If \"let the user change it\" is off, the matching checkbox on the Options page is "
        "greyed out and the \"checked by default\" value is used.",
    "桌面快捷方式": "Desktop shortcut",
    "启用桌面快捷方式": "Enable the desktop shortcut",
    "默认勾选": "Checked by default",
    "允许用户在安装时修改": "Let the user change it during setup",
    "快捷方式名称": "Shortcut name",
    "不带 .lnk 后缀": "Without the .lnk suffix",
    "开始菜单快捷方式": "Start menu shortcut",
    "启用开始菜单快捷方式": "Enable the Start menu shortcut",
    "放在同名子文件夹里": "Put it in a same-named subfolder",
    "开始菜单里会多一层文件夹，例如「开始菜单\\我的小工具\\我的小工具」":
        "Adds a folder level, e.g. Start menu\\My Tool\\My Tool",
    "同时放一个「卸载」快捷方式": "Also add an \"Uninstall\" shortcut",

    # -- 第 6 步：打包 --
    "打包": "Build",
    "输出设置与编译": "Output settings and compile",
    "校验配置、生成安装脚本、编译出安装包":
        "Validate, generate the script and compile the installer",
    "输出设置": "Output Settings",
    "输出目录": "Output folder",
    "相对工程目录，例如 out": "Relative to the project folder, e.g. out",
    "文件名": "File name",
    "可以用 {appName} {appVersion}。勾选多个版本时会自动加 "
    "-PerMachine / -PerUser 后缀，避免互相覆盖。":
        "You can use {appName} {appVersion}. With several variants a -PerMachine / -PerUser "
        "suffix is added automatically.",
    "压缩方式": "Compression",
    "lzma 整体压缩（体积最小，推荐）": "lzma solid (smallest, recommended)",
    "lzma 逐文件压缩": "lzma per file",
    "zlib（压缩最快，体积偏大）": "zlib (fastest, larger)",
    "要生成哪些版本": "Which variants to build",
    "为所有用户安装（需要管理员权限，装到 Program Files）":
        "For all users (admin rights, installs to Program Files)",
    "仅当前用户安装（免提权，装到 %LOCALAPPDATA%\\Programs）":
        "Current user only (no admin, installs to %LOCALAPPDATA%\\Programs)",
    "开始": "Start",
    "只生成脚本": "Generate Script Only",
    "开始打包": "Start Build",
    "打包前会自动保存工程。首次打包如果没装 NSIS，"
    "程序会提示用 winget install NSIS.NSIS 安装。":
        "The project is saved before building. If NSIS is missing, the app suggests "
        "winget install NSIS.NSIS.",
    "日志": "Log",
    "警告  ": "WARN  ",
    "错误  ": "ERROR  ",
    "校验没通过，请先按上面的提示修改。": "Validation failed; fix the issues above first.",
    "校验通过，可以打包了。": "Validation passed. Ready to build.",
    "  应用名称  : ": "  App name  : ",
    "  安装目录名: ": "  Folder   : ",
    "  主程序    : ": "  Main exe : ",
    "  打包内容  : ": "  Payload  : ",
    "  输出模式  : ": "  Variants : ",
    " 个文件": " file(s)",
    "工程已保存：": "Project saved: ",
    "生成脚本：": "Script: ",
    "预期产出：": "Expected: ",
    "完成。": "Done.",
    "使用编译器：": "Compiler: ",
    "=== 编译 [": "=== Compile [",
    "编译失败（退出码 ": "Compile failed (exit code ",
    "编译报告成功，但没有产出：": "Compile reported success but produced nothing: ",
    "打包完成，共": "Build complete: ",
    "个安装包。": " installer(s).",
    "错误：": "Error: ",
    "意外错误：": "Unexpected error: ",
    "目录还不存在": "Folder Does Not Exist",
    "先打包一次就有了。": "It appears after the first build.",

    # -- 启动窗口 --
    "把一个工程编译成 Windows 安装包": "Compile a project into a Windows installer",
    "新建工程": "New Project",
    "打开已有工程…": "Open Project…",
    "最近打开": "Recent",
    "还没有打开过任何工程。\n\n点上面的「新建工程」从零开始，"
    "或者用「打开已有工程…」选一个 .jianpack 文件。":
        "No projects yet.\n\nClick \"New Project\" to start from scratch, "
        "or use \"Open Project…\" to pick a .jianpack file.",
    "工程": "Project",
    "位置": "Location",
    "（找不到）": " (missing)",
    "打开选中的工程": "Open Selected",
    "移除记录": "Forget",
    "找不到工程文件": "Project Not Found",
    "{path}\n\n这个位置已经打不开了（文件被移动、删除，或者所在磁盘没插上）。\n"
    "可以用「移除记录」把它从列表里去掉。":
        "{path}\n\nThis location can no longer be opened (moved, deleted, or the drive is "
        "unplugged). Use \"Forget\" to remove it from the list.",
    "安装打包工程": "Installer Project",
    "所有文件": "All files",
    "选择文件夹": "Choose a folder",
    "保存为": "Save as",
    "选择文件": "Choose a file",
    "打开工程": "Open Project",
    "选择要打包的文件": "Choose files to pack",
    "选择要打包的文件夹": "Choose a folder to pack",

    # -- 新建工程 --
    "工程名称": "Project name",
    "会用这个名字建一个同名文件夹，工程文件和数据都放在里面。":
        "A folder with this name is created to hold the project file and data.",
    "会在下面这个位置创建「名称.jianpack」这一个工程文件。":
        "A single project file \"<name>.jianpack\" is created in the location below.",
    "图标、待打包的文件、界面设置等都会装在这一个文件里，"
    "发送、备份、搬移都只搬它。":
        "The icon, the files to package and all settings are stored inside this single file — "
        "send, back up or move just this one file.",
    "存放位置": "Location",
    "将要创建": "Will create",
    "（把上面两项填好）": "(fill in the two fields above)",
    "里面会有 {name}.jianpack，以及 {detail}。":
        "It will contain {name}.jianpack and {detail}.",
    "请填写工程名称。": "Please enter a project name.",
    "工程名称不合法。": "That project name is not allowed.",
    "工程名称不能包含 \\ / : * ? \" < > | 这些字符。":
        "The project name cannot contain \\ / : * ? \" < > |.",
    "工程名称不能以空格或句点结尾。":
        "The project name cannot end with a space or a dot.",
    "请填写存放位置。": "Please choose a location.",
    "我的软件": "My Software",
    "图标、欢迎页图片": "icon, welcome image",
    "要打包进去的文件": "the files to pack",
    "生成的脚本等中间产物": "generated scripts and intermediates",
    "最终编译出来的安装包": "the final installer",
    "创建": "Create",
    "取消": "Cancel",
    "还差一点": "Not Quite",
    "这个位置已经有同名工程了": "A Project Already Exists Here",
    "{project_file}\n\n换个名字，或者换个存放位置。":
        "{project_file}\n\nChoose a different name or location.",
    "文件夹已经存在": "Folder Already Exists",
    "{folder}\n\n这个文件夹已经存在，而且里面有东西。\n"
    "继续会在里面创建工程文件和子目录，确定吗？":
        "{folder}\n\nThe folder already exists and is not empty.\n"
        "Continue to create the project file and subfolders inside it?",
    "选择存放位置": "Choose a location",

    # -- 图片裁剪 --
    "调整": "Adjust",
    "拖动图片调整位置，滚轮或下面的滑块缩放。框内就是要导出的内容。":
        "Drag to move, scroll or use the slider to zoom. The frame is what gets exported.",
    "效果预览": "Preview",
    "实际大小": "Actual size",
    "，下面放大 {zoom} 倍显示": ", shown {zoom}× below",
    "缩放": "Zoom",
    "重置": "Reset",
    "确定": "OK",
    "导出尺寸": "Export size",
    "原图": "Source",
    "用户的原始图片不会被改动，结果会另存到工程的 assets 目录里。":
        "Your original image is untouched; the result is saved into the project's assets folder.",
    "打不开这张图片": "Cannot Open This Image",
    "选择": "Choose",
    "调整内页页头图片": "Adjust header image",
    "调整欢迎页图片": "Adjust welcome image",
    "调整程序图标": "Adjust app icon",

    # -- 欢迎页 --
    "欢迎使用": "Welcome to",
    "把文件夹里的程序，一键打成中文安装包。":
        "Turn a folder of programs into a ready-to-run installer.",
    "对方双击就能装，能选安装路径、建快捷方式，还能在「程序和功能」里正常卸载。":
        "They double-click to install, can pick the location, get shortcuts and can cleanly "
        "uninstall from Apps & features.",
    "第一次使用？点下面的「打开教程」看图文教程；"
    "平时也可以从菜单「帮助 → 教程」（F1）打开。":
        "New here? Click \"Open Tutorial\" below for the illustrated guide. You can also open "
        "it any time from Help → Tutorial (F1).",
    "以后不再显示这个欢迎页": "Don't show this welcome page again",
    "打开教程": "Open Tutorial",
    "知道了": "Got it",

    # -- 首选项 / 设置 --
    "首选项 / 设置": "Preferences / Settings",
    "调成自己顺手的用法": "Make the app work the way you like",
    "界面主题": "Theme",
    "浅色（默认）": "Light (default)",
    "深色": "Dark",
    "切换主题后界面会重新加载一次（工程会先自动保存）。":
        "The interface reloads after switching (the project is saved first).",
    "使用习惯": "Habits",
    "启动时显示欢迎页": "Show the welcome page on startup",
    "启动时自动打开上次打开的工程（跳过启动窗口）":
        "Open the last project on startup (skip the start window)",
    "默认显示「安装效果预览」": "Show the installer preview by default",
    "初始化": "Reset",
    "恢复默认设置会清空「最近打开」记录，并把上面这些选项重置为出厂值。":
        "Restoring defaults clears the \"Recent\" list and resets the options above.",
    "恢复默认设置…": "Restore Defaults…",
    "恢复默认设置": "Restore Defaults",
    "会清空「最近打开」记录，并把主题、欢迎页等选项恢复成默认值。\n\n确定继续吗？":
        "This clears the \"Recent\" list and restores the theme, welcome page and other "
        "options to their defaults.\n\nContinue?",
    "保存设置失败": "Saving Settings Failed",
    "界面语言": "Language",
    "文件关联": "File Association",
    "已关联到本程序（双击 .jianpack 即可打开）":
        "Associated with this app (double-click .jianpack to open)",
    "关联指向了别的位置，建议点「立即关联 / 修复」":
        "The association points elsewhere — click \"Associate / Repair\"",
    "尚未关联，点「立即关联 / 修复」即可":
        "Not associated yet — click \"Associate / Repair\"",
    "（当前是源码运行，关联会指向开发用的脚本）":
        "(Running from source; the association will point to the dev script)",
    "立即关联 / 修复": "Associate / Repair",
    "取消关联": "Remove Association",
    "缓存 / 临时目录": "Cache / Temp Folder",
    "留空 = 软件目录下的 data\\work。\n"
    "解开单文件工程、编译中间产物都放这里；换目录后下次打开工程时生效。\n"
    "「用默认位置」只清掉自定义路径，不会删除文件。":
        "Empty = data\\work under the app folder.\n"
        "Extracted projects and build intermediates go here; the change takes effect next "
        "time a project is opened.\n"
        "\"Use default location\" only clears the custom path; it does not delete files.",
    "用默认位置": "Use default location",
    "清空缓存文件…": "Clear Cache Files…",
    "清空缓存": "Clear Cache",
    "缓存里没有可清理的内容。": "There is nothing to clean in the cache folder.",
    "将删除缓存目录里的 {n} 个临时工程，约释放 {size}。\n\n继续吗？":
        "This will delete {n} temporary project(s) from the cache folder, freeing about "
        "{size}.\n\nContinue?",
    "已清理 {n} 项，约释放 {size}。": "Cleaned {n} item(s), freeing about {size}.",
    "选择缓存目录": "Choose Cache Folder",
    "演示测试项目": "Demo Project",
    "演示项目": "Demo Project",
    "这是随软件自带的演示项目，不能从列表里移除。":
        "This is the built-in demo project and cannot be removed from the list.",
    "演示项目（只读，不能保存）": "Demo project (read-only, cannot be saved)",
    "这是随软件自带的演示项目，只用来了解软件怎么用，不能保存修改。\n\n"
    "想基于它做一个自己的工程，请点「文件 → 新建工程」。":
        "This is the built-in demo project — it is only for learning how the app works and "
        "cannot be saved.\n\nTo make your own project, choose File → New Project.",
    "演示项目不能保存": "Demo Project Can't Be Saved",
    "这是随软件自带的演示项目，不能保存修改。\n\n要新建一个自己的工程吗？":
        "This is the built-in demo project and cannot be saved.\n\nCreate a new project of "
        "your own?",
    "（演示项目不会保存工程文件，只做本次测试。）":
        "(The demo project won't save the project file; this is a one-off test.)",
    "界面语言会立即切换（工程会先自动保存）。":
        "The interface language switches immediately (the project is saved first).",
    "语言 / Language": "语言 / Language",

    # -- 实时预览（含预览里画的安装向导示意图）--
    "安装效果预览": "Installer Preview",
    "   跟着编辑内容实时变": "   updates as you edit",
    "按真实版式绘制的示意图，用来确认文案和图片效果；\n"
    "字体和换行位置可能和最终安装程序差一两行。":
        "A mockup drawn to the real layout, to check text and images;\n"
        "font and line wrapping may differ slightly from the final installer.",
    "（还没有打开工程）": "(no project open)",
    "预览画不出来：\n{exc}": "Cannot render the preview:\n{exc}",
    "安装选项": "Options",
    "安装过程": "Installing",
    "许可证协议": "License Agreement",
    "在安装 {name} 之前，请阅读许可证条款。":
        "Please read the license terms before installing {name}.",
    "选择安装位置": "Choose Install Location",
    "选择 {name} 的安装文件夹。": "Choose the install folder for {name}.",
    "正在安装": "Installing",
    "正在安装 {name}，请稍候。": "Installing {name}, please wait.",
    "所需空间: 34.0 KB": "Space required: 34.0 KB",
    "可用空间: 26.9 GB": "Space available: 26.9 GB",
    "输出文件夹: {dir}": "Output folder: {dir}",
    "文件: {exe}": "File: {exe}",
    "创建快捷方式: 桌面": "Create shortcut: Desktop",
    "创建快捷方式: 开始菜单": "Create shortcut: Start menu",
    "要阅读协议的其余部分，请按 [PgDn] 键向下翻页。":
        "Press [PgDn] to scroll down and read the rest of the agreement.",
    "我接受许可协议中的条款": "I accept the terms of the license agreement",
    "在桌面创建 {name} 的快捷方式(&D)": "Create a desktop shortcut for {name} (&D)",
    "在开始菜单创建 {name} 的快捷方式(&S)": "Create a Start menu shortcut for {name} (&S)",
    "{name} 安装": "{name} Setup",
    "为所有用户安装（需要管理员权限）": "For all users (admin rights required)",
    "仅当前用户安装（无需管理员权限）": "Current user only (no admin rights)",
    "上一步": "Back",
    "下一步": "Next",
    "取消": "Cancel",
    "安装": "Install",
    "完成": "Finish",
    "浏览(&B)...": "Browse (&B)...",

    # -- 教程窗口外壳 --
    "使用教程": "Tutorial",
    "从「这是什么」到「进阶技巧」，图文都在这了。":
        "From \"what is this\" to advanced tips, all illustrated.",
    "章节目录": "Contents",
    "配图是真实界面的截图加红圈标注，\n会随软件版本更新。":
        "Images are real screenshots with red highlights,\nrefreshed with each release.",
    "教程窗口不挡主界面，可以边看边操作。":
        "This window does not block the main window, so you can follow along.",
    "关闭": "Close",
    "（教程配图缺失：{name}）": "(tutorial image missing: {name})",
    "提示：": "Tip: ",

    # -- 教程正文（中文原文 -> English）--
    "它能帮你做什么": "What it can do for you",
    "快速上手：6 步做出安装包": "Quick start: an installer in 6 steps",
    "图片不用自己做": "Images: no prep needed",
    "实时预览：改完立刻看到效果": "Live preview: see changes instantly",
    "进阶用法": "Advanced usage",
    "常见问题与排错": "FAQ & troubleshooting",

    "这个软件把「一个文件夹里做好的程序」打成一个中文安装包——"
    "把它发给别人，对方双击就能装，不用解压、不用自己在一堆文件中找 exe。":
        "This app turns \"a ready-made program in a folder\" into an installer. "
        "Send it to someone and they double-click to install — no unzipping, no hunting for the exe.",
    "它对标 Inno Setup Compiler，但只做最常用的部分，界面全中文。"
    "底层使用 NSIS 作为打包引擎，生成出来的是原生安装程序，"
    "对方不需要安装 .NET、Python 或任何运行时。":
        "It is modeled after Inno Setup Compiler but keeps only the common parts, with a "
        "localized interface. It uses NSIS as the packaging engine, and the result is a native "
        "installer — no .NET, Python or any runtime required.",
    "安装位置：用户可以自己选装到哪个文件夹":
        "Install location: the user can pick a folder",
    "快捷方式：桌面、开始菜单，还可以让用户在安装时自己勾选":
        "Shortcuts: desktop and Start menu, optionally chosen by the user during setup",
    "正常卸载：写进「控制面板 → 程序和功能」，带图标、版本、发行者":
        "Clean uninstall: listed in Apps & features with icon, version and publisher",
    "中文安装向导：欢迎页、许可协议、更新日志、完成页都能自己写":
        "Installer wizard: write your own welcome, license, changelog and finish pages",
    "静默安装：支持 /S 参数，方便批量部署":
        "Silent install: supports /S for batch deployment",
    "体积小：官方示例的安装包约 100 KB（不含你自己的程序文件）":
        "Small: the sample installer is about 100 KB (excluding your own files)",
    "主界面分三块：① 左边「打包步骤」，② 中间填写内容，"
    "③ 左下方是「安装效果预览」。":
        "The main window has three parts: ① Build Steps on the left, ② the form in the middle, "
        "③ the Installer Preview at the lower left.",
    "菜单在哪": "Where is the menu",
    "顶部菜单栏依次是：文件、工具、视图、帮助、首选项/设置。"
    "本教程在「帮助 → 教程」里，也可以直接按 F1 打开；"
    "最右边的「首选项/设置」可以换浅色/深色主题、开关欢迎页、"
    "恢复默认设置。":
        "The menu bar is: File, Tools, View, Help, Preferences/Settings. This tutorial lives "
        "under Help → Tutorial, and F1 opens it too. The right-most Preferences/Settings "
        "switches light/dark theme, toggles the welcome page and restores defaults.",
    "第一次打开软件会先弹一个欢迎页，上面有「打开教程」的按钮，"
    "以后不想再看到它，在欢迎页上勾「不再显示」就行。":
        "On first launch a welcome page appears with an \"Open Tutorial\" button. To stop seeing "
        "it, tick \"Don't show this welcome page again\" there.",
    "「帮助 → 教程」打开本教程。教程是一个独立窗口，"
    "主界面不会被挡住，可以边看边操作。":
        "Help → Tutorial opens this guide. It is a separate window that does not block the main "
        "window, so you can read and work at the same time.",
    "教程窗口不会打断你正在编辑的工程，重复点「教程」也只会打开一个窗口。":
        "The tutorial never interrupts the project you are editing, and clicking Tutorial again "
        "just reuses the same window.",

    "第一次打开软件会先出现「启动窗口」，让你决定要做什么。":
        "On launch you first see the start window, which asks what you want to do.",
    "启动窗口：① 新建工程；② 打开已有工程；"
    "③ 从「最近打开」里双击一个工程。":
        "Start window: ① New Project, ② Open Project, ③ double-click a recent project.",
    "点「新建工程」时，先填工程名称和保存位置（例如桌面）。"
    "软件会建一个同名文件夹，把工程文件和数据目录都放进去，"
    "之后整个文件夹可以随意搬移、压缩、备份。":
        "With New Project, enter a name and a location (e.g. Desktop). A folder of that name is "
        "created to hold the project file and data folders, and the whole folder can be moved, "
        "zipped or backed up freely.",
    "进入主界面后，按左边这 6 步走就行。下面逐步来看。":
        "In the main window, just follow the 6 steps on the left. Let's go through them.",
    "第 1 步：基本信息": "Step 1: Basic Info",
    "填应用名称、版本、公司/作者、图标等。带 * 的是必填项。"
    "图标会用在安装包、桌面快捷方式和「程序和功能」列表里。":
        "Fill in the app name, version, company/author, icon and so on. Fields marked * are "
        "required. The icon is used for the installer, the desktop shortcut and Apps & features.",
    "第 1 步：① 应用名称是必填项；② 安装目录名建议中文软件填成英文；"
    "③ 版本号也是必填项；④ 程序图标可以先跳过，后面再来处理。":
        "Step 1: ① App name is required; ② prefer an ASCII install folder name; "
        "③ the version is required too; ④ the app icon can wait.",
    "第 2 步：打包内容": "Step 2: Payload",
    "点「添加文件…」或「添加文件夹…」，把要装到用户电脑上的东西加进来。"
    "它们在安装目录里的位置也可以在这里调整。":
        "Click Add Files… or Add Folder… to add what should be installed. You can also adjust "
        "where each item lands in the install folder.",
    "第 2 步：① 用「添加文件 / 添加文件夹」把内容加进来；"
    "② 在列表里可以调整每一项的安装位置；"
    "③ 下方「主程序」决定安装完成后运行哪个 exe，留空会自动识别根目录里唯一的 exe。":
        "Step 2: ① add files/folders; ② adjust each item's install location in the list; "
        "③ Main program decides which exe runs after install (empty auto-detects the only exe).",
    "第 3 步：安装设置": "Step 3: Install Settings",
    "选安装模式、默认安装路径，以及卸载时怎么处理用户数据。":
        "Choose the install mode, the default path, and how user data is handled on uninstall.",
    "第 3 步：① 选安装模式——「为所有用户安装」需要管理员权限、安装时会弹 UAC；"
    "「仅当前用户安装」免提权，双击就装；② 也可以自定义安装路径；"
    "③ 关掉「允许用户修改安装位置」就不显示安装位置页。":
        "Step 3: ① pick the mode — all users needs admin (UAC); current user needs no admin; "
        "② you can set a custom path; ③ turning off the location page hides it.",
    "设置默认安装路径、用户数据与卸载选项。"
    "「装给所有用户还是仅当前用户」不在这里选，而是第 6 步的输出选项。":
        "Set the default install path, user data and uninstall options. Whether it installs for "
        "all users or just the current user is not chosen here — that's an output option in step 6.",
    "第 3 步：①「使用默认路径」会按安装模式自动选一个位置，取消后可以自己填；"
    "②「允许用户修改安装位置」关掉后，安装时不显示安装位置页；"
    "③ 下面设置用户数据目录，以及卸载时是否询问保留数据。":
        "Step 3: ① \"Use the default path\" picks a location by install mode; clear it to enter "
        "your own; ② turning off \"let the user change the install location\" hides that page; "
        "③ below, set the user data folder and whether to ask about keeping it on uninstall.",
    "第 4 步：安装界面": "Step 4: Installer UI",
    "安装向导每一页的文案和图片都能改。上面选子标签"
    "（欢迎页 / 许可协议 / 更新日志 / …），下面写文字、换图片。":
        "Every page of the installer can be customized. Pick a tab above (Welcome / License / "
        "Changelog / …) and edit the text and images below.",
    "第 4 步：① 用标签页切换各个页面；② 在这里改当前页的标题等文案；"
    "③ 欢迎页左侧图片是竖版的，留空就用默认蓝色背景。":
        "Step 4: ① switch pages with the tabs; ② edit the current page's text here; "
        "③ the welcome left image is vertical; empty uses the default blue.",
    "第 5 步：快捷方式": "Step 5: Shortcuts",
    "决定安装时创建哪些快捷方式，以及用户能不能自己勾选。":
        "Decide which shortcuts are created and whether the user can change them.",
    "第 5 步：① 启用桌面快捷方式；②「允许用户在安装时修改」关掉后，"
    "安装选项页上对应的复选框会变灰；③ 开始菜单快捷方式同理。":
        "Step 5: ① enable the desktop shortcut; ② turning off \"let the user change it\" greys "
        "out the matching checkbox on the Options page; ③ the Start menu shortcut works the same.",
    "第 6 步：打包": "Step 6: Build",
    "选好这次要生成哪些版本，点「开始打包」，日志会实时输出。"
    "首次打包如果本机没装 NSIS，程序会提示怎么装。":
        "Choose the variants to build and click Start Build; the log updates live. If NSIS is not "
        "installed, the app tells you how to get it.",
    "第 6 步：① 勾选「要生成哪些版本」；② 点「开始打包」；"
    "③ 日志会实时输出编译过程，产物出现在工程的 out 目录里。":
        "Step 6: ① tick the variants to build; ② click Start Build; ③ the log shows the compile "
        "in real time and the output lands in the project's out folder.",
    "打包前会自动保存工程。完成后点「打开输出目录」就能看到安装包。":
        "The project is saved before building. When done, click Open Output Folder.",

    "程序图标、内页页头图片、欢迎页图片这三处，都不需要自己先做成规定尺寸。"
    "点「选择图片…」丢一张随便什么格式的图进去就行"
    "（PNG / JPG / BMP / GIF / WEBP 都可以）。":
        "The app icon, the inner-page header and the welcome image don't need to be pre-sized. "
        "Click Choose Image… and drop in any format (PNG / JPG / BMP / GIF / WEBP).",
    "① 框内就是要导出的内容，拖动图片调整位置；② 右侧实时显示导出的真实效果；"
    "③ 用滚轮或滑块缩放；④ 确定后自动转成要求的格式。":
        "① the frame is what gets exported, drag to move; ② the right side previews the real "
        "result; ③ zoom with the wheel or slider; ④ OK converts it to the required format.",
    "自动摆正：手机照片的旋转信息会被处理": "Auto-orient: phone photo rotation is handled",
    "透明区域会被压到白底上，不会变成黑块":
        "Transparent areas are flattened onto white, not black",
    "确定后自动转成安装向导要求的 BMP；图标自动导出 7 档尺寸的 .ico":
        "OK produces the required BMP; icons export a 7-size .ico",
    "原图不会被改动，结果另存到工程的 assets 目录里":
        "Your original image is untouched; the result goes into the project's assets folder",
    "尺寸由软件自动处理：内页页头 150×57、欢迎页图 164×314、"
    "图标 256×256（含 16~256 多档）。":
        "Sizes are handled for you: header 150×57, welcome 164×314, icon 256×256 (sizes 16–256).",

    "主界面左下方常驻一块「安装效果预览」。你改标题、正文、图片、快捷方式，"
    "它都会跟着变，不用打完包再装一遍才知道长什么样。":
        "The Installer Preview sits at the lower left. As you edit titles, text, images and "
        "shortcuts it updates, so you don't have to build and install to see the result.",
    "① 左下方是实时预览；② 下拉框可以切换要看哪一页；"
    "③ 在右边改动（例如协议文字），左边的预览立刻跟着变。":
        "① the live preview is at the lower left; ② the dropdown switches pages; ③ edit on the "
        "right (e.g. the license text) and the preview updates instantly.",
    "只列出真正会出现的页面（比如关掉了许可协议页，它就不在列表里）":
        "Only pages that will actually appear are listed (disable the license page and it "
        "disappears from the list)",
    "可以用菜单「视图 → 显示安装预览」（Ctrl+P）隐藏或显示":
        "Show or hide it via View → Show Installer Preview (Ctrl+P)",
    "显示与否会被记住，下次打开还是上次的选择":
        "The choice is remembered for next time",
    "预览是按真实版式绘制的示意图：窗口尺寸、页头位图、按钮位置都是从真实"
    "安装程序里量出来的，但字体和中文换行位置仍可能和最终安装程序差一两行。":
        "The preview is a mockup drawn to the real layout: window size, header bitmap and button "
        "positions are measured from a real installer, but fonts and line wrapping may differ "
        "by a line or two.",
    "生成出来的安装包里，各页大致就是这个样子。":
        "The pages of the generated installer look roughly like this.",

    "两种安装模式，可以一次都生成": "Two install modes; you can build both",
    "为所有用户安装": "For all users",
    "仅当前用户安装": "Current user only",
    "权限": "Rights",
    "需要管理员（弹 UAC）": "Admin required (UAC)",
    "免提权，双击就装": "None; just double-click",
    "所有用户可见": "Visible to all users",
    "仅当前用户": "Current user only",
    "注册表": "Registry",
    "在第 3 步选默认模式，到第 6 步勾选这次要生成哪些版本。"
    "勾了多个时，文件名会自动加 -PerMachine / -PerUser 后缀，避免互相覆盖。":
        "Pick the default mode in step 3 and the variants in step 6. With several variants a "
        "-PerMachine / -PerUser suffix is added to avoid overwriting.",
    "在第 6 步「打包」里勾选这次要生成哪些版本（两种都勾也行）。"
    "勾了多个时，文件名会自动加 -PerMachine / -PerUser 后缀，避免互相覆盖。":
        "In step 6 (Build) tick the variants to build (both is fine). With several variants a "
        "-PerMachine / -PerUser suffix is added automatically to avoid overwriting.",
    "静默安装（方便批量部署）": "Silent install (for batch deployment)",
    "生成的安装包支持 NSIS 标准的 /S 参数，安装过程不弹界面；"
    "卸载程序同样支持 /S。":
        "The installer supports the standard NSIS /S flag for a UI-less install; the uninstaller "
        "supports /S too.",
    "工程是自包含的": "The project is self-contained",
    "所有相对路径都以工程文件所在目录为基准。"
    "把整个工程文件夹拷走、压缩、发给别人，都还能正常打开和打包。":
        "All relative paths are based on the project file's folder. Copy, zip or send the whole "
        "folder and it still opens and builds.",
    "工程文件夹：.jianpack 是工程文件，assets 放图标和位图，"
    "payload 放要打包的文件，build 和 out 是自动生成的中间产物与成品。":
        "Project folder: the .jianpack is the project file, assets holds icons/bitmaps, payload "
        "holds the files to pack, build and out are generated.",
    "文字里的两种变量": "Two kinds of variables in text",
    "{appName} {appVersion} {appPublisher} 这类占位符，"
    "在打包时由本软件替换成实际内容":
        "Placeholders like {appName} {appVersion} {appPublisher} are replaced by this app "
        "when building",
    "$INSTDIR $APPDATA $PROGRAMFILES64 这类写法会原样保留，"
    "安装时由 NSIS 替换成真实路径":
        "Forms like $INSTDIR $APPDATA $PROGRAMFILES64 are kept as-is and replaced by NSIS "
        "at install time",
    "许可协议与更新日志：两种来源": "License and changelog: two sources",
    "可以「直接在下面编辑」，也可以「从 txt 文件导入」。两边的内容都会保留，"
    "随时切换不会丢东西；打包时只用当前选中的那一种。"
    "编码由软件自动转换成 NSIS 需要的格式，不用自己另存成 ANSI 或 UTF-16。":
        "You can Edit below or Import from a .txt file. Both are kept so switching never loses "
        "anything; only the selected one is used when building. Encoding is converted for you.",
    "卸载与用户数据": "Uninstall and user data",
    "安装时会写进「程序和功能」，卸载项带图标、版本、发行者。"
    "卸载时可以选择保留用户数据；静默卸载（/S）按你在第 3 步设的默认选项走。":
        "Install registers an entry in Apps & features with icon, version and publisher. The "
        "uninstaller can keep user data; a silent uninstall (/S) follows the default from step 3.",
    "命令行与批量打包": "Command line and batch builds",
    "除了图形界面，也可以用命令行完成同样的事：":
        "Besides the GUI you can do the same from the command line:",
    "安装一次之后还可以直接用 aipack 命令。"
    "把设计器打包成 exe 分发时，会把便携版 NSIS 一起带上，"
    "换电脑也不用装任何东西。":
        "After installing once you can use the aipack command. The packaged exe bundles a "
        "portable NSIS, so nothing is needed on other machines.",
    "首选项 / 设置": "Preferences / Settings",
    "菜单最右边的「首选项/设置」里可以调这些使用习惯：":
        "The right-most Preferences/Settings menu customizes these habits:",
    "界面主题：浅色 / 深色（切换后界面会重新加载一次）":
        "Theme: light / dark (the interface reloads after switching)",
    "启动时是否显示欢迎页": "Show the welcome page on startup",
    "启动时是否自动打开上次打开的工程（跳过启动窗口）":
        "Open the last project on startup (skip the start window)",
    "是否默认显示「安装效果预览」": "Show the Installer Preview by default",
    "「恢复默认设置」：清空最近打开记录并把上面选项重置为出厂值":
        "Restore Defaults: clears the recent list and resets the options above",

    "打包时提示找不到主程序": "Build says the main program is missing",
    "在第 2 步「打包内容 → 主程序」里手动选一个；"
    "或者让安装目录根部只有一个 .exe（留空时软件会自动识别唯一的那个）。":
        "Pick one in step 2 (Payload → Main program), or keep a single .exe in the install root "
        "(empty auto-detects the only one).",
    "提示找不到 makensis.exe": "\"makensis.exe not found\"",
    "说明本机没有 NSIS。用 winget install NSIS.NSIS 安装一个即可。"
    "如果你用的是「文件夹版」的分发包，已经把便携版 NSIS 带在里面了，"
    "正常不会出现这个提示。":
        "NSIS is not installed. Install it with winget install NSIS.NSIS. The folder-style "
        "distribution bundles a portable NSIS, so this normally never appears.",
    "提示图片尺寸不对": "An image is reported as the wrong size",
    "不要手工替换 assets 里的图片。回到对应的「图片字段」点「选择图片…」"
    "重新裁剪，软件会自动导出正确尺寸和格式。":
        "Don't replace images in assets by hand. Use the matching image field's Choose Image… "
        "to re-crop; the app exports the correct size and format.",
    "工程换了电脑就打不开了": "The project won't open on another PC",
    "多半是工程里引用了工程目录之外的文件（绝对路径，或用 .. 跳出去）。"
    "添加文件时选「复制进工程」，整个文件夹就是自包含的了。"
    "第 6 步校验时也会对这类引用给出警告。":
        "It likely references files outside the project folder (absolute paths or ..). Choose "
        "\"copy into the project\" when adding files to keep it self-contained. Step 6 warns "
        "about such references.",
    "控制面板里的卸载项互相覆盖": "Uninstall entries overwrite each other",
    "检查第 1 步的「内部标识」。不同的软件要有不同的标识；"
    "留空的话会按安装目录名自动生成。":
        "Check the Internal ID in step 1. Different apps need different IDs; empty derives it "
        "from the install folder name.",
    "预览和最终安装程序有点不一样": "The preview differs slightly from the final installer",
    "预览是按真实版式画的示意图，字体渲染和中文换行位置可能差一两行，"
    "以最终安装程序为准。":
        "The preview is a mockup drawn to the real layout; font rendering and line wrapping may "
        "differ by a line or two. Trust the final installer.",

    # -- 教程正文：新增/改版的内容 --
    "工程就是一个文件": "A project is a single file",
    "它对标 Inno Setup Compiler，但只做最常用的部分，界面全中文（也可以切英文）。"
    "底层使用 NSIS 作为打包引擎，生成出来的是原生安装程序，"
    "对方不需要安装 .NET、Python 或任何运行时。":
        "It is modeled after Inno Setup Compiler but keeps only the common parts, with a "
        "localized interface (Chinese or English). It uses NSIS as the packaging engine, and the "
        "result is a native installer — no .NET, Python or any runtime required.",
    "安装向导：欢迎页、许可协议、更新日志、完成页都能自己写":
        "Installer wizard: write your own welcome, license, changelog and finish pages",
    "顶部菜单栏依次是：文件、工具、视图、帮助、首选项/设置。"
    "本教程在「帮助 → 教程」里，也可以直接按 F1 打开；"
    "最右边的「首选项/设置」可以换界面语言和主题、开关欢迎页、"
    "修复文件关联、恢复默认设置。":
        "The menu bar is: File, Tools, View, Help, Preferences/Settings. This tutorial lives "
        "under Help → Tutorial, and F1 opens it too. The right-most Preferences/Settings switches "
        "the language and theme, toggles the welcome page, repairs the file association and "
        "restores defaults.",
    "第一次打开会看到欢迎页": "First launch: the welcome page",
    "第一次打开软件会先弹一个欢迎页，一句话说明软件作用，并提醒教程在哪。"
    "点「打开教程」就能看这份图文教程；不想再看到它，勾上「不再显示」即可。"
    "左下角的「中/en」按钮可以随时切换中英文界面。":
        "On first launch a welcome page appears: one line about what the app does and a pointer "
        "to this tutorial. Click \"Open Tutorial\" to read it; tick \"Don't show again\" to hide "
        "it. The \"中/en\" button at the lower left switches the interface language anytime.",
    "欢迎页：① 打开教程；② 勾选以后不再显示；③ 左下角一键切换中英文。":
        "Welcome page: ① Open Tutorial; ② don't show it again; ③ one-click language switch "
        "at the lower left.",

    "启动窗口：① 新建工程；② 打开已有工程；"
    "③ 「最近打开」第一行固定是自带的演示项目，双击就能打开。":
        "Start window: ① New Project; ② Open Project; ③ the first row of \"Recent\" is always "
        "the built-in demo project — double-click to open it.",
    "第一次用可以先双击「演示测试项目」——那是一个完整的示例工程，"
    "可以随便改、试试预览和打包，但它是「只读」的、不能保存（免得把示例改坏）。"
    "想正式做工程，点「新建工程」照着它填就行。它固定排在最近打开的第一行，不能删除。":
        "New users can double-click \"Demo Project\" first — a complete sample project you can "
        "freely edit, preview and build, but it is read-only and cannot be saved (so the sample "
        "stays intact). To make a real project, click New Project and copy the ideas over. It is "
        "always the first row of Recent and cannot be removed.",
    "点「新建工程」时，先填工程名称和存放位置，软件只会创建「一个工程文件」"
    "（图标、待打包的文件、界面设置都在这个文件里，详见后面「工程就是一个文件」）。":
        "When you click New Project, enter a name and a location; the app creates just "
        "\"one project file\" (icon, files to package and settings are all inside it — see "
        "\"A project is a single file\" below).",
    "选好这次要生成哪些版本，点「开始打包」，日志会实时输出。"
    "两种版本都勾上，会各出一个安装包（文件名自动加 -PerMachine / -PerUser 后缀）。"
    "首次打包如果本机没装 NSIS，程序会提示怎么装。":
        "Choose the variants to build and click Start Build; the log updates live. Ticking both "
        "variants produces two installers (with automatic -PerMachine / -PerUser suffixes). If "
        "NSIS is missing, the app tells you how to get it.",
    "第 6 步：① 勾选「要生成哪些版本」；② 点「开始打包」；"
    "③ 日志会实时输出编译过程。":
        "Step 6: ① tick the variants to build; ② click Start Build; ③ the log shows the compile "
        "in real time.",
    "安装包默认输出到桌面；在第 6 步「输出位置」里填一个目录就按填的走，留空恢复桌面。":
        "The installer is written to the Desktop by default; set a folder in step 6 \"Output "
        "location\" to change it, or clear it to go back to the Desktop.",

    "新建的工程只有一个文件：「我的软件.jianpack」。"
    "程序图标、要打包的文件、界面设置等全都装在这一个文件里"
    "（内部是 zip 容器，但平时不用管）。":
        "A new project is a single file: \"MySoftware.jianpack\". The app icon, the files to package "
        "and all settings live inside it (it is a zip container internally, but you never need "
        "to care).",
    "一个工程 = 一个文件：里面装着工程配置、图标和要打包的文件。":
        "One project = one file: it holds the project settings, icon and the files to package.",
    "发给别人：只发这一个 .jianpack 文件，对方打开就是完整工程":
        "Share it: send this one .jianpack file and the other side opens the complete project",
    "备份、搬移、换电脑：只搬这一个文件":
        "Back up, move or switch PC: just move this one file",
    "中间产物（生成的脚本等）放在临时目录里，不进工程文件":
        "Intermediate files (generated scripts etc.) live in a temp folder, not in the project file",
    "中间产物（生成的脚本、解开的文件）放在缓存目录里，不进工程文件":
        "Intermediate files (generated scripts, extracted files) live in the cache folder, "
        "not in the project file",
    "缓存目录：解开工程、编译中间产物放哪（默认在软件目录下的 data\\work）；"
    "「清空缓存文件…」能一键删掉这些临时目录（正在用的会跳过）":
        "Cache folder: where extracted projects and build intermediates go "
        "(default: data\\work under the app folder); \"Clear Cache Files…\" deletes these temp "
        "folders in one click (the one in use is skipped)",
    "双击 .jianpack 直接打开": "Double-click a .jianpack to open it",
    "打包版启动时会把 .jianpack 自动关联到本程序，之后「双击工程文件」"
    "就能打开软件并直接进入主界面（跳过欢迎页和启动窗口）。"
    "万一关联坏了（比如软件换了位置），去「首选项/设置 → 文件关联」"
    "点一下「立即关联 / 修复」即可。":
        "The packaged app associates .jianpack with itself on startup, so after that, "
        "\"double-clicking a project file\" opens the app straight to the main window "
        "(skipping the welcome page and the start window). If the association breaks (e.g. the app "
        "was moved), open Preferences/Settings → File Association and click \"Associate / Repair\".",
    "工程文件用的是它自己的图标，和软件图标不一样，方便一眼区分工程文件和程序。":
        "Project files use their own icon, different from the app icon, so you can tell a project "
        "file from a program at a glance.",
    "安装包输出到哪": "Where the installer goes",
    "默认输出到桌面；在第 6 步「输出位置」里填一个目录就按那个目录走，"
    "留空又恢复成桌面。":
        "By default it goes to the Desktop; set a folder in step 6 \"Output location\" to use that "
        "folder, or clear it to go back to the Desktop.",

    "① 下拉框可以切换要看哪一页；② 左下方是实时预览；"
    "③ 在右边改动（例如协议文字），左边的预览立刻跟着变。":
        "① the dropdown switches pages; ② the live preview is at the lower left; ③ edit on the "
        "right (e.g. the license text) and the preview updates instantly.",

    "首选项：① 界面语言（中文 / English，立即切换）；② 界面主题（浅色 / 深色）；"
    "③ 使用习惯；④ 文件关联修复；⑤ 缓存目录与「清空缓存文件…」；⑥ 恢复默认设置。":
        "Preferences: ① language (Chinese / English, applied immediately); ② theme (light / "
        "dark); ③ habits; ④ file association repair; ⑤ cache folder and \"Clear Cache Files…\"; "
        "⑥ restore defaults.",
    "界面语言：中文 / English，切换后界面会重新加载一次":
        "Language: Chinese / English (the interface reloads after switching)",

    "工程文件的更多玩法": "More things you can do with a project file",
    "除了双击打开，单文件工程还能用命令行处理：":
        "Besides double-clicking, a single-file project can be handled from the command line:",
    "「pack」把老的文件夹工程打成单文件；「unpack」把单文件解回文件夹，"
    "方便手工改或放进版本库。":
        "\"pack\" turns an old folder project into a single file; \"unpack\" extracts a single "
        "file back into a folder (handy for manual edits or version control).",
    "关于与开源": "About & open source",
    "「帮助 → 关于」里有作者信息、GitHub 主页、联系邮箱和许可信息（都可以直接点开），"
    "以及开源说明和免责声明。":
        "Help → About shows the author, the GitHub page, the email and the license "
        "(all clickable), plus the open-source note and the disclaimer.",

    "双击 .jianpack 没反应 / 图标不对": "Double-clicking .jianpack does nothing / wrong icon",
    "多半是文件关联坏了（比如软件换了位置）。到「首选项/设置 → 文件关联」"
    "点一下「立即关联 / 修复」就好。":
        "The file association is probably broken (e.g. the app was moved). Open "
        "Preferences/Settings → File Association and click \"Associate / Repair\".",
    "正经的工程是自包含的单文件，拷过去就能开。如果打不开，"
    "多半是里边引用了工程目录之外的文件（绝对路径，或用 .. 跳出去）。"
    "添加文件时选「复制进工程」，整个文件就是自包含的了。":
        "A proper project is a self-contained single file that opens anywhere. If it won't open, "
        "it likely references files outside the project (absolute paths or ..). Choose \"copy into "
        "the project\" when adding files to keep it self-contained.",

    # -- 教程示意图 t13 里画的文字 --
    "一个自包含的工程文件夹": "A self-contained project folder",
    "我的软件.jianpack": "MySoftware.jianpack",
    "工程文件（所有路径都以这个目录为基准）":
        "Project file (all paths are relative to this folder)",
    "assets\\": "assets\\",
    "图标、欢迎页图片、页头图片": "Icons, welcome image, header image",
    "payload\\": "payload\\",
    "要打包进安装包的文件": "Files to pack into the installer",
    "build\\": "build\\",
    "生成的 .nsi 等中间产物（自动）": "Generated .nsi and other intermediates (auto)",
    "out\\": "out\\",
    "最终编译出来的安装包（自动）": "The final installer (auto)",

    # ---- 内核 / 引擎提示（磁盘、工程读写、校验、图片、编译器）----
    "磁盘空间不足，无法{what}。\n需要约 {need}，可用 {free}。\n"
    "请清理磁盘，或在「首选项/设置 → 缓存目录」里换一个盘。":
        "Not enough disk space to {what}.\nNeeds about {need}, only {free} free.\n"
        "Free up some space, or pick another drive in Preferences/Settings → Cache Folder.",
    "创建缓存目录": "create the cache folder",
    "解开这个工程": "extract this project",
    "保存工程": "save the project",

    "这个工程文件打不开（不是有效的 .jianpack 容器）：{exc}":
        "Cannot open this project (not a valid .jianpack container): {exc}",
    "这个 .jianpack 里没有 project.json，可能不是本软件的工程。":
        "This .jianpack has no project.json — it may not be a project from this app.",
    "这个 .jianpack 里没有 project.json。": "This .jianpack has no project.json.",
    "读不了这个工程文件：{exc}": "Cannot read this project file: {exc}",
    "保存工程失败：{exc}": "Saving the project failed: {exc}",
    "工程文件里有非法路径，已拒绝：{name}":
        "The project contains an illegal path, rejected: {name}",
    "工程文件里有越界路径，已拒绝：{name}":
        "The project contains an out-of-bounds path, rejected: {name}",
    "工作目录里没有 project.json，无法打包。":
        "The working folder has no project.json; cannot pack.",

    "{where}: 期望是一个对象 {{...}}": "{where}: expected an object {{...}}",
    "{where}.{key}: 期望字符串，当前是 {value}":
        "{where}.{key}: expected a string, got {value}",
    "{where}.{key}: 期望字符串或 null，当前是 {value}":
        "{where}.{key}: expected a string or null, got {value}",
    "{where}.{key}: 期望 true / false，当前是 {value}":
        "{where}.{key}: expected true / false, got {value}",
    "{where}.{key}: 期望字符串数组，当前是 {value}":
        "{where}.{key}: expected an array of strings, got {value}",
    '{where}.type: 只能是 "file" 或 "folder"':
        '{where}.type: must be "file" or "folder"',
    "{where}.items: 期望数组": "{where}.items: expected an array",
    '{where}.mode: 只能是 "perMachine" 或 "perUser"':
        '{where}.mode: must be "perMachine" or "perUser"',
    '{where}.compression: 只能是 "solid-lzma" / "lzma" / "zlib" / "bzip2"':
        '{where}.compression: must be "solid-lzma" / "lzma" / "zlib" / "bzip2"',
    '{where}.modes: 非法值 "{value}"': '{where}.modes: invalid value "{value}"',

    "{where}: 未填写": "{where}: not filled in",
    "{where}: 找不到 {source}": "{where}: cannot find {source}",
    "{where}: {source} 不是文件": "{where}: {source} is not a file",
    "{where}: {source} 不是文件夹": "{where}: {source} is not a folder",
    "安装目录根部没有找到任何 .exe": "No .exe found in the install root.",
    "安装目录根部有多个 .exe，无法自动识别：{list}":
        "Multiple .exe files in the install root; cannot auto-detect: {list}",

    "不能为空": "cannot be empty",
    "不能包含 \\ / : * ? \" < > | $ 这些字符":
        "cannot contain \\ / : * ? \" < > | $",
    "不能包含 \\ / : * ? \" < > | $ 这些字符（当前值：{value}）":
        "cannot contain \\ / : * ? \" < > | $ (current: {value})",
    "不能以空格或句点结尾（当前值：{value}）":
        "cannot end with a space or a dot (current: {value})",
    "必须是 1 / 1.0 / 1.0.0 / 1.0.0.0 这样的数字版本号，当前为 {version}":
        "must be a numeric version like 1 / 1.0 / 1.0.0 / 1.0.0.0, current: {version}",
    "必须是 a.b.c.d 四段数字，当前为 {version}":
        "must be four numbers a.b.c.d, current: {version}",
    "至少要选一个文件或文件夹": "select at least one file or folder",
    "打包内容为空": "the payload is empty",
    "没有指定主程序，且无法自动识别：{hint}":
        "No main program specified and it cannot be auto-detected: {hint}",
    "在打包内容里找不到 {exe}（该路径是安装目录内的相对路径）":
        "{exe} is not in the payload (the path is relative to the install folder)",

    "在第 1 步「基本信息 → 图标」里重新选一个 .ico":
        "Pick a .ico again in step 1 (Basic Info → Icon).",
    "在第 4 步「安装界面 → 通用」里重新选，或点「清除」":
        "Pick it again in step 4 (Installer UI → General), or click Clear.",
    "在第 4 步「安装界面 → 欢迎页」里重新选，或点「清除」":
        "Pick it again in step 4 (Installer UI → Welcome), or click Clear.",
    "在第 4 步「安装界面 → 许可协议」里重新选择，或改成「直接在下面编辑」":
        "Choose it again in step 4 (Installer UI → License), or switch to \"Edit below\".",
    "勾选了「显示许可协议页」并选了「从 txt 文件导入」，"
    "但没有选文件——请在第 4 步「安装界面 → 许可协议」里选一个 .txt，"
    "或改成「直接在下面编辑」":
        "The license page is on with \"Import from a .txt file\" selected, but no file is chosen. "
        "Pick a .txt in step 4 (Installer UI → License), or switch to \"Edit below\".",
    "勾选了「显示许可协议页」并选了「直接编辑」，但正文是空的——"
    "请在第 4 步「安装界面 → 许可协议」里写上条款内容":
        "The license page is on with \"Edit below\" selected, but the text is empty. Write the "
        "terms in step 4 (Installer UI → License).",
    "在第 4 步「安装界面 → 更新日志」里重新选择，或改成「直接在下面编辑」":
        "Choose it again in step 4 (Installer UI → Changelog), or switch to \"Edit below\".",
    "勾选了「显示更新日志页」并选了「从 txt 文件导入」，"
    "但没有选文件——请在第 4 步「安装界面 → 更新日志」里选一个 .txt，"
    "或改成「直接在下面编辑」":
        "The changelog page is on with \"Import from a .txt file\" selected, but no file is "
        "chosen. Pick a .txt in step 4 (Installer UI → Changelog), or switch to \"Edit below\".",
    "勾选了「显示更新日志页」并选了「直接编辑」，但正文是空的——"
    "请在第 4 步「安装界面 → 更新日志」里写上更新内容":
        "The changelog page is on with \"Edit below\" selected, but the text is empty. Write the "
        "changes in step 4 (Installer UI → Changelog).",

    "内部标识是通用的「{key}」——装两个不同的软件时，"
    "它们在控制面板里会互相覆盖卸载项。"
    "建议把这个字段清空，让它按安装目录名自动生成。":
        "The internal ID is the generic \"{key}\" — two different apps would overwrite each "
        "other's uninstall entry in Control Panel. Clear this field to derive it from the install "
        "folder name.",
    "没填发行者，控制面板的卸载列表里会显示「未知发布者」":
        "No publisher set; the uninstall list shows \"Unknown publisher\".",
    "没填版权信息，程序属性里会缺少版权声明":
        "No copyright set; the program properties will lack a copyright notice.",
    "没提供图标，安装包会用 NSIS 默认图标，辨识度低":
        "No icon provided; the installer will use the default NSIS icon.",
    "关闭了「安装位置」页，但 defaultDir 留空仍会按模式自动选择路径":
        "The Location page is off, but defaultDir is empty, so the path is still chosen by mode.",
    "引用了工程目录之外的位置（{value}），把工程拷到别的电脑后这条引用会失效":
        "References a location outside the project folder ({value}); the reference breaks if the "
        "project is copied to another PC.",

    "找不到文件：{relative}": "File not found: {relative}",
    "不是文件：{relative}": "Not a file: {relative}",
    "扩展名必须是 {exts}，当前为 {suffix}":
        "Extension must be {exts}, got {suffix}",

    "工程文件不存在：{path}": "Project file not found: {path}",
    "工程文件带有 UTF-8 BOM，JSON 不允许。请另存为「UTF-8 无 BOM」。":
        "The project file has a UTF-8 BOM, which JSON does not allow. Save it as "
        "\"UTF-8 without BOM\".",
    "工程文件不是 UTF-8 编码：{exc}": "The project file is not UTF-8: {exc}",
    "JSON 语法错误（第 {line} 行第 {col} 列）：{msg}":
        "JSON syntax error (line {line}, column {col}): {msg}",
    "工程文件的顶层必须是对象 {...}": "The project file's root must be an object {...}",
    "缺少 formatVersion 字段": "Missing the formatVersion field",
    "此工程由更新版本的程序创建（formatVersion={version}，本程序支持到 {max}），"
    "请升级后再打开。":
        "This project was created by a newer version (formatVersion={version}; this app supports "
        "up to {max}). Please update first.",

    "{where}: 路径为空": "{where}: empty path",
    "保存设置失败：{exc}": "Saving settings failed: {exc}",

    "读不了这张图片：{exc}": "Cannot read this image: {exc}",
    "保存图片失败：{exc}": "Saving the image failed: {exc}",
    "缺少 Pillow，无法处理图片。请先安装：pip install Pillow":
        "Pillow is missing, so images cannot be processed. Install it with: pip install Pillow",
    "{name}: 不是有效的 BMP 文件": "{name}: not a valid BMP file",
    "{name}: 不是有效的 ICO 文件": "{name}: not a valid ICO file",
    "{where}: 位图尺寸必须是 {w}×{h}，当前为 {aw}×{ah}":
        "{where}: bitmap size must be {w}×{h}, got {aw}×{ah}",
    "{where}: 图标里没有任何图像": "{where}: the icon contains no images",
    "{where}: 图标缺少 {need} 尺寸（Windows 要求小图标和 256 大图标都要有）":
        "{where}: the icon is missing {need} (Windows needs both the small icon and the 256 "
        "large icon)",

    "指定的 makensis 不存在：{path}": "The specified makensis does not exist: {path}",
    "找不到 makensis.exe。\n"
    "  官方安装：winget install NSIS.NSIS\n"
    "  或把便携版放到 vendor\\nsis\\ 目录\n"
    "  或用 --makensis 指定路径 / 设置环境变量 MAKENSIS":
        "Cannot find makensis.exe.\n"
        "  Official install: winget install NSIS.NSIS\n"
        "  Or put a portable copy under vendor\\nsis\\\n"
        "  Or pass --makensis <path> / set the MAKENSIS environment variable",

    "错误": "Error",
    "警告": "Warning",
    "build.fileName: 不能为空": "build.fileName: cannot be empty",
    "build.fileName: 太长了": "build.fileName: too long",
    "未知的安装模式：{mode}": "Unknown install mode: {mode}",
    "{where}: 读不了 {file}：{exc}": "{where}: cannot read {file}: {exc}",
    "{where}: 未知的占位符 {{{key}}}（可用：{known}）":
        "{where}: unknown placeholder {{{key}}} (available: {known})",
}
