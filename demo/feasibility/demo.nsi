; ============================================================================
;  「应用安装向导打包软件」 —— 可行性验证 Demo
;
;  这个脚本是最终由设计器（Python + Tkinter）自动生成的东西的手写版本，
;  目的是先验证"生成出来的安装包"到底长什么样、功能是否齐全。
;
;  编译（两种安装模式各出一个包）：
;     makensis /DPER_MACHINE /DOUTFILE_NAME=DemoSetup-PerMachine.exe demo.nsi
;     makensis /DPER_USER    /DOUTFILE_NAME=DemoSetup-PerUser.exe    demo.nsi
; ============================================================================

Unicode true
SetCompressor /SOLID lzma

; ---------------------------------------------------------------------------
; 一、工程参数（将来对应 GUI 里的输入项）
; ---------------------------------------------------------------------------
!define APP_NAME       "我的小工具"
!define APP_VERSION    "1.0.0"
!define APP_PUBLISHER  "示例软件工作室"
!define APP_COPYRIGHT  "Copyright (C) 2026 示例软件工作室"
!define APP_URL        "https://example.com/myapp"
!define APP_EXE        "MyApp.exe"
!define APP_REGKEY     "MyApp"
!define APP_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_REGKEY}"

; ---------------------------------------------------------------------------
; 二、安装模式（由打包时选择）
;     PER_MACHINE -> 装给所有用户，需要管理员权限，装到 Program Files
;     PER_USER    -> 只装给当前用户，免提权，装到 %LOCALAPPDATA%\Programs
; ---------------------------------------------------------------------------
!ifdef PER_USER
  !define REQUEST_LEVEL "user"
  !define INSTALL_BASE  "$LOCALAPPDATA\Programs"
  !define REG_HIVE      "HKCU"
  !define SHELL_VAR     "current"
  !define MODE_LABEL    "仅为当前用户安装（无需管理员权限）"
!else
  !define REQUEST_LEVEL "admin"
  !define INSTALL_BASE  "$PROGRAMFILES64"
  !define REG_HIVE      "HKLM"
  !define SHELL_VAR     "all"
  !define MODE_LABEL    "为所有用户安装（需要管理员权限）"
!endif

!ifndef OUTFILE_NAME
  !define OUTFILE_NAME "DemoSetup.exe"
!endif

!define DIR_NAME "${APP_NAME}"

; ---------------------------------------------------------------------------
; 三、基本信息 / 版权信息（写进 exe 属性，右键可见）
; ---------------------------------------------------------------------------
Name "${APP_NAME}"
OutFile "out\${OUTFILE_NAME}"
RequestExecutionLevel ${REQUEST_LEVEL}
InstallDir "${INSTALL_BASE}\${DIR_NAME}"
InstallDirRegKey ${REG_HIVE} "Software\${APP_REGKEY}" "InstallDir"
ShowInstDetails show
ShowUninstDetails show

VIProductVersion "1.0.0.0"
VIAddVersionKey /LANG=2052 "ProductName"      "${APP_NAME}"
VIAddVersionKey /LANG=2052 "FileDescription"  "${APP_NAME} 安装程序"
VIAddVersionKey /LANG=2052 "FileVersion"      "${APP_VERSION}.0"
VIAddVersionKey /LANG=2052 "ProductVersion"   "${APP_VERSION}.0"
VIAddVersionKey /LANG=2052 "CompanyName"      "${APP_PUBLISHER}"
VIAddVersionKey /LANG=2052 "LegalCopyright"   "${APP_COPYRIGHT}"
VIAddVersionKey /LANG=2052 "OriginalFilename" "${OUTFILE_NAME}"

; ---------------------------------------------------------------------------
; 四、界面外观
; ---------------------------------------------------------------------------
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinMessages.nsh"
!include "FileFunc.nsh"
!include "x64.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON                     "assets\app.ico"
!define MUI_UNICON                   "assets\app.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "assets\welcome.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP       "assets\header.bmp"

BrandingText "${APP_NAME} 安装程序 v${APP_VERSION}"

; ---------------------------------------------------------------------------
; 五、页面流程
; ---------------------------------------------------------------------------

; ---- 1. 欢迎页 ----
!define MUI_WELCOMEPAGE_TITLE "欢迎使用 $(^NameDA) 安装向导"
!define MUI_WELCOMEPAGE_TEXT  "安装向导将引导您完成 $(^NameDA) 的安装。$\r$\n$\r$\n建议在继续之前关闭其他正在运行的程序。安装完成后，您可以从桌面或开始菜单启动本软件。$\r$\n$\r$\n模式：${MODE_LABEL}$\r$\n$\r$\n点击「下一步」继续。"
!insertmacro MUI_PAGE_WELCOME

; ---- 2. 许可协议页 ----
!define MUI_LICENSEPAGE_TEXT_TOP       "请在使用本软件之前阅读下面的许可协议。"
!define MUI_LICENSEPAGE_TEXT_BOTTOM    "勾选「我接受」后点击「下一步」继续安装。"
!define MUI_LICENSEPAGE_CHECKBOX
!define MUI_LICENSEPAGE_CHECKBOX_TEXT  "我接受许可协议中的条款(&A)"
!insertmacro MUI_PAGE_LICENSE "input\许可协议.txt"

; ---- 3. 更新日志页（自定义页面）----
Page custom ChangelogPageCreate ChangelogPageLeave

; ---- 4. 安装位置页 ----
!define MUI_DIRECTORYPAGE_TEXT_TOP "安装向导将把 $(^NameDA) 安装到下面的文件夹中。$\r$\n$\r$\n若要安装到其他位置，请点击「浏览」并选择目标文件夹。"
!define MUI_DIRECTORYPAGE_TEXT_DESTINATION "安装到："
!insertmacro MUI_PAGE_DIRECTORY

; ---- 5. 安装选项页（自定义页面，桌面/开始菜单快捷方式开关）----
Page custom OptionsPageCreate OptionsPageLeave

; ---- 6. 安装进度页 ----
!insertmacro MUI_PAGE_INSTFILES

; ---- 7. 完成页 ----
!define MUI_FINISHPAGE_TITLE     "$(^NameDA) 安装完成"
!define MUI_FINISHPAGE_TEXT      "$(^NameDA) 已经安装到您的电脑上。$\r$\n$\r$\n安装位置：$INSTDIR$\r$\n$\r$\n点击「完成」关闭安装向导。"
!define MUI_FINISHPAGE_RUN       "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT  "立即运行 $(^NameDA)"
!define MUI_FINISHPAGE_LINK      "访问软件主页"
!define MUI_FINISHPAGE_LINK_LOCATION "${APP_URL}"
!insertmacro MUI_PAGE_FINISH

; ---- 卸载页面 ----
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

; ---------------------------------------------------------------------------
; 六、变量
; ---------------------------------------------------------------------------
Var ChangelogText
Var DesktopShortcutCheck
Var StartMenuShortcutCheck
Var CreateDesktopShortcut
Var CreateStartMenuShortcut
Var DeleteUserData

; ---------------------------------------------------------------------------
; 七、初始化
; ---------------------------------------------------------------------------
Function .onInit
  ${If} ${RunningX64}
    SetRegView 64
  ${EndIf}
  SetShellVarContext ${SHELL_VAR}

  ; 把更新日志释放到临时目录，供自定义页面读取
  ; （许可协议由 MUI_PAGE_LICENSE 自行内嵌，不需要在这里释放）
  InitPluginsDir
  File /oname=$PLUGINSDIR\changelog.txt "input\更新日志.txt"

  ; 静默安装（/S）时会跳过自定义页面，这里给默认值
  StrCpy $CreateDesktopShortcut  ${BST_CHECKED}
  StrCpy $CreateStartMenuShortcut ${BST_CHECKED}
  StrCpy $DeleteUserData "0"
FunctionEnd

; ---------------------------------------------------------------------------
; 八、自定义页面：更新日志
; ---------------------------------------------------------------------------
Function ChangelogPageCreate
  !insertmacro MUI_HEADER_TEXT "更新日志" "了解这个版本带来了哪些变化"

  ; 读取更新日志内容（文件是 UTF-16LE，必须用 FileReadUTF16LE）
  StrCpy $ChangelogText ""
  ClearErrors
  FileOpen $0 "$PLUGINSDIR\changelog.txt" r
  IfErrors cl_read_done
cl_read_loop:
  FileReadUTF16LE $0 $1
  IfErrors cl_read_close
  StrCpy $ChangelogText "$ChangelogText$1"
  Goto cl_read_loop
cl_read_close:
  FileClose $0
cl_read_done:

  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}

  ${NSD_CreateRichEdit} 0 0 100% 100% "$ChangelogText"
  Pop $1
  CreateFont $2 "Microsoft YaHei UI" 9
  SendMessage $1 ${WM_SETFONT} $2 1
  SendMessage $1 0x00CF 1 0            ; EM_SETREADONLY
  SetCtlColors $1 0x3C3C3C 0xFFFFFF

  nsDialogs::Show
FunctionEnd

Function ChangelogPageLeave
FunctionEnd

; ---------------------------------------------------------------------------
; 九、自定义页面：安装选项
; ---------------------------------------------------------------------------
Function OptionsPageCreate
  !insertmacro MUI_HEADER_TEXT "安装选项" "选择安装时要创建的快捷方式"

  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}

  ${NSD_CreateGroupBox} 0 0 100% 100% "附加任务"
  Pop $0

  ${NSD_CreateLabel} 12u 18u 88% 20u "安装向导可以为 $(^NameDA) 创建下面的快捷方式，方便您随时启动。"
  Pop $0
  SetCtlColors $0 0x646464 transparent

  ${NSD_CreateCheckbox} 12u 46u 88% 12u "在桌面创建 $(^NameDA) 的快捷方式(&D)"
  Pop $DesktopShortcutCheck
  ${NSD_Check} $DesktopShortcutCheck

  ${NSD_CreateCheckbox} 12u 64u 88% 12u "在开始菜单创建 $(^NameDA) 的快捷方式(&S)"
  Pop $StartMenuShortcutCheck
  ${NSD_Check} $StartMenuShortcutCheck

  ${NSD_CreateLabel} 12u 92u 88% 16u "提示：无论是否创建快捷方式，都可以在「控制面板 - 程序和功能」中卸载本软件。"
  Pop $0
  SetCtlColors $0 0x969696 transparent

  nsDialogs::Show
FunctionEnd

Function OptionsPageLeave
  ${NSD_GetState} $DesktopShortcutCheck   $CreateDesktopShortcut
  ${NSD_GetState} $StartMenuShortcutCheck $CreateStartMenuShortcut
FunctionEnd

; ---------------------------------------------------------------------------
; 十、安装
; ---------------------------------------------------------------------------
Section "主程序" SecMain
  SectionIn RO

  SetOutPath "$INSTDIR"
  SetOverwrite on
  File /r "input\*.*"

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; 记住安装位置，方便下次安装时作为默认值
  WriteRegStr ${REG_HIVE} "Software\${APP_REGKEY}" "InstallDir" "$INSTDIR"

  ; 控制面板「程序和功能」中的卸载条目
  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "DisplayName"     "${APP_NAME}"
  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "DisplayVersion"  "${APP_VERSION}"
  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "DisplayIcon"     "$INSTDIR\${APP_EXE}"
  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "Publisher"       "${APP_PUBLISHER}"
  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "URLInfoAbout"    "${APP_URL}"
  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr   ${REG_HIVE} "${APP_UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD ${REG_HIVE} "${APP_UNINST_KEY}" "NoModify" 1
  WriteRegDWORD ${REG_HIVE} "${APP_UNINST_KEY}" "NoRepair" 1

  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD ${REG_HIVE} "${APP_UNINST_KEY}" "EstimatedSize" "$0"
SectionEnd

Section "快捷方式" SecShortcut
  SectionIn RO

  ${If} $CreateStartMenuShortcut == ${BST_CHECKED}
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
                   "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\卸载 ${APP_NAME}.lnk" \
                   "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
  ${EndIf}

  ${If} $CreateDesktopShortcut == ${BST_CHECKED}
    CreateShortCut "$DESKTOP\${APP_NAME}.lnk" \
                   "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  ${EndIf}
SectionEnd

; ---------------------------------------------------------------------------
; 十一、卸载
; ---------------------------------------------------------------------------
Function un.onInit
  ${If} ${RunningX64}
    SetRegView 64
  ${EndIf}
  SetShellVarContext ${SHELL_VAR}

  MessageBox MB_YESNO|MB_ICONQUESTION \
    "是否同时删除 $(^NameDA) 的配置和用户数据？$\r$\n$\r$\n选择「否」将保留这些数据，以便日后重新安装时继续使用。" \
    /SD IDNO IDYES un_del_data IDNO un_keep_data
  StrCpy $DeleteUserData "0"
  Goto un_init_done
un_del_data:
  StrCpy $DeleteUserData "1"
un_keep_data:
un_init_done:
FunctionEnd

Section "Uninstall"
  ; 开始菜单
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\卸载 ${APP_NAME}.lnk"
  RMDir  "$SMPROGRAMS\${APP_NAME}"

  ; 桌面
  Delete "$DESKTOP\${APP_NAME}.lnk"

  ; 程序文件
  RMDir /r "$INSTDIR"

  ; 注册表
  DeleteRegKey ${REG_HIVE} "${APP_UNINST_KEY}"
  DeleteRegKey ${REG_HIVE} "Software\${APP_REGKEY}"

  ; 用户数据（由用户在卸载确认时决定是否保留）
  ${If} $DeleteUserData == "1"
    RMDir /r "$APPDATA\${APP_NAME}"
  ${EndIf}

  ; 兜底：如果安装目录空了就删掉
  RMDir "$INSTDIR"
SectionEnd
