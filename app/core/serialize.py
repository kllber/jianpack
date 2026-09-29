"""把内存里的工程写回 ``.jianpack``。

读的方向在 :mod:`app.core.project`，这里只负责写。
字段名保持和读的时候完全一致（camelCase），保证「读进来再写出去」是无损的。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .. import APP_NAME, __version__
from . import container
from .project import FORMAT_VERSION, Project

# 老的「文件夹工程」里会准备好的子目录（新工程是单文件，不再建目录）
PROJECT_SUBFOLDERS = ("assets", "payload", "build")


def scaffold_project_folder(project_file: str | Path) -> Path:
    """建好工程需要的子目录，返回工程文件夹。

    工程必须是**一个自包含的文件夹**：``<名称>.jianpack`` 加这几个子目录。
    否则图标、待打包文件、中间产物、安装包会散落在用户选的位置上。
    """
    folder = Path(project_file).expanduser().parent
    folder.mkdir(parents=True, exist_ok=True)
    for name in PROJECT_SUBFOLDERS:
        (folder / name).mkdir(exist_ok=True)
    return folder


def project_to_dict(project: Project) -> dict:
    app = project.app
    files = project.files
    install = project.install
    interface = project.interface
    shortcuts = project.shortcuts
    uninstall = project.uninstall
    build = project.build
    integration = project.integration

    return {
        "formatVersion": FORMAT_VERSION,
        "generator": {"name": APP_NAME, "version": __version__},
        "project": {
            "name": project.project_name,
            "createdAt": project.created_at,
            "modifiedAt": project.modified_at,
        },
        "app": {
            "name": app.name,
            "dirName": app.dir_name,
            "version": app.version,
            "fileVersion": app.file_version,
            "publisher": app.publisher,
            "copyright": app.copyright,
            "homepage": app.homepage,
            "description": app.description,
            "registryKey": app.registry_key,
            "icon": app.icon,
            "mainExe": app.main_exe,
            "mainExeArgs": app.main_exe_args,
        },
        "files": {
            "items": [
                {
                    "type": item.type,
                    "source": item.source,
                    "dest": item.dest,
                    # 只有文件夹条目才有意义
                    **({"keepFolder": item.keep_folder} if item.type == "folder" else {}),
                    "include": list(item.include),
                    "exclude": list(item.exclude),
                }
                for item in files.items
            ]
        },
        "install": {
            "mode": install.mode,
            "defaultDir": install.default_dir,
            "allowChangeDir": install.allow_change_dir,
            "rememberLastDir": install.remember_last_dir,
            "estimatedSizeAuto": install.estimated_size_auto,
        },
        "interface": {
            "language": interface.language,
            "brandingText": interface.branding_text,
            "showAbortWarning": interface.show_abort_warning,
            "showDetails": interface.show_details,
            "headerImage": interface.header_image,
            "welcome": {
                "enabled": interface.welcome.enabled,
                "title": interface.welcome.title,
                "text": interface.welcome.text,
                "image": interface.welcome.image,
            },
            "license": {
                "enabled": interface.license.enabled,
                "source": interface.license.source,
                "text": interface.license.text,
                "file": interface.license.file,
                "requireAccept": interface.license.require_accept,
                "acceptText": interface.license.accept_text,
                "textTop": interface.license.text_top,
                "textBottom": interface.license.text_bottom,
            },
            "changelog": {
                "enabled": interface.changelog.enabled,
                "source": interface.changelog.source,
                "text": interface.changelog.text,
                "file": interface.changelog.file,
                "title": interface.changelog.title,
                "subtitle": interface.changelog.subtitle,
            },
            "directoryPage": {
                "textTop": interface.directory_page.text_top,
                "textDestination": interface.directory_page.text_destination,
            },
            "optionsPage": {
                "enabled": interface.options_page.enabled,
                "title": interface.options_page.title,
                "subtitle": interface.options_page.subtitle,
                "groupText": interface.options_page.group_text,
                "intro": interface.options_page.intro,
                "hint": interface.options_page.hint,
            },
            "finish": {
                "title": interface.finish.title,
                "text": interface.finish.text,
                "runApp": interface.finish.run_app,
                "runText": interface.finish.run_text,
                "link": {
                    "enabled": interface.finish.link.enabled,
                    "text": interface.finish.link.text,
                    "url": interface.finish.link.url,
                },
            },
        },
        "shortcuts": {
            "desktop": {
                "enabled": shortcuts.desktop.enabled,
                "default": shortcuts.desktop.default,
                "userCanToggle": shortcuts.desktop.user_can_toggle,
                "name": shortcuts.desktop.name,
            },
            "startMenu": {
                "enabled": shortcuts.start_menu.enabled,
                "default": shortcuts.start_menu.default,
                "userCanToggle": shortcuts.start_menu.user_can_toggle,
                "name": shortcuts.start_menu.name,
                "useFolder": shortcuts.start_menu.use_folder,
                "uninstallShortcut": shortcuts.start_menu.uninstall_shortcut,
            },
        },
        "uninstall": {
            "userDataPath": uninstall.user_data_path,
            "askKeepUserData": uninstall.ask_keep_user_data,
            "keepUserDataText": uninstall.keep_user_data_text,
            "deleteUserDataByDefault": uninstall.delete_user_data_by_default,
            "autoClose": uninstall.auto_close,
        },
        "build": {
            "outputDir": build.output_dir,
            "fileName": build.file_name,
            "compression": build.compression,
            "modes": list(build.modes),
            "signEnabled": build.sign_enabled,
            "signCert": build.sign_cert,
            "signPassword": build.sign_password,
            "signTimestamp": build.sign_timestamp,
            "signtool": build.signtool,
        },
        "integration": {
            "associations": [
                {"ext": a.ext, "description": a.description, "icon": a.icon,
                 "isDefault": a.is_default}
                for a in integration.associations
            ],
            "protocols": [
                {"scheme": p.scheme, "description": p.description}
                for p in integration.protocols
            ],
            "registry": [
                {"root": r.root, "path": r.path, "name": r.name,
                 "type": r.type, "data": r.data}
                for r in integration.registry
            ],
            "autostart": integration.autostart,
        },
    }


def save_project(project: Project, path: str | Path | None = None,
                 container_mode: bool | None = None) -> Path:
    """把工程写到 ``path``（默认写回原路径）。

    - ``container_mode=True``：压成单个 ``.jianpack``（zip 容器）；
    - ``False``：写成老的纯 JSON（文件夹工程）；
    - ``None``：沿用工程当前模式。

    容器模式下，磁盘上的工作目录（``project.base_dir``）保持不动，只是重新打包。
    """
    target = Path(path) if path else project.source_path
    target = Path(target).expanduser().resolve()

    project.modified_at = _now()
    if not project.created_at:
        project.created_at = project.modified_at

    text = json.dumps(project_to_dict(project), ensure_ascii=False, indent=2) + "\n"
    if container_mode is None:
        container_mode = project.is_container

    if container_mode:
        project.base_dir.mkdir(parents=True, exist_ok=True)
        (project.base_dir / container.PROJECT_JSON).write_bytes(text.encode("utf-8"))
        container.pack(project.base_dir, target)
        project.is_container = True
        project.source_path = target
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))  # JSON 规范要求不带 BOM
        project.is_container = False
        project.source_path = target
        project.base_dir = target.parent
    return target


def _now() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()
