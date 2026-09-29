# 可行性验证 Demo

这个目录是「应用安装向导打包软件」动手前的**技术验证**。

它不包含任何 GUI 代码，而是用手写的 NSIS 脚本直接编译出一个**真实的安装包**，
用来确认最终要交付给用户的东西长什么样、功能是否齐全。

生成出来的安装包在 `out/` 目录，各页面截图在 `screenshots/` 目录。

![安装向导全部页面](screenshots/总览-安装向导全部页面.png)

---

## 一、结论

**完全可行。** 用 NSIS 作为打包引擎，可以覆盖目前规划的全部需求，
而且生成的安装包是原生小程序（**约 123 KB**），
目标电脑**不需要安装 .NET、Python 或任何运行时**，双击就能装。

---

## 二、怎么跑

### 方式 A：图形界面（推荐）

```powershell
cd <项目根目录>
python aipack.py                                              # 新建工程
python aipack.py gui demo\feasibility\demo.jianpack             # 打开这个示例工程
```

界面按 5 步走：基本信息 → 选择要打包的内容 → 安装设置 → 安装界面 → 快捷方式 → 打包。

### 方式 B：命令行

```powershell
# 只校验工程，不打包
python -m app validate demo\feasibility\demo.jianpack

# 生成 .nsi 脚本 + 编译出安装包
python -m app build demo\feasibility\demo.jianpack
```

产物：

| 文件 | 说明 |
|---|---|
| `out\我的小工具-1.0.0-Setup-PerMachine.exe` | 装给所有用户，装到 `Program Files`，需要管理员权限 |
| `out\我的小工具-1.0.0-Setup-PerUser.exe` | 仅当前用户，装到 `%LOCALAPPDATA%\Programs`，**免提权** |
| `build\installer.nsi` | 生成出来的安装脚本（UTF-8 带 BOM） |

### 方式 C：手写脚本的老路子（保留作参照）

```powershell
cd demo\feasibility

# 1) 编译出两个安装包（走的是手写的 demo.nsi）
powershell -ExecutionPolicy Bypass -File .\build.ps1

# 2) 自动验证：静默安装 -> 检查结果 -> 静默卸载 -> 检查是否卸干净
powershell -ExecutionPolicy Bypass -File .\verify.ps1

# 3) （可选）驱动安装向导走完所有页面并截图
powershell -ExecutionPolicy Bypass -File .\tools\capture-screenshots.ps1 -Prefix g
```

> 需要 NSIS 编译器：`winget install NSIS.NSIS`
> 没有的话会自动去 `vendor\nsis\` 目录找，也可以用 `--makensis` 指定。

双击 `out\` 里的 PerMachine 版本就能看到完整的安装向导。

---

## 三、已验证的功能

| 需求 | 实现方式 | 已验证 |
|---|---|---|
| 中文安装界面 | `MUI_LANGUAGE "SimpChinese"` | ✅ |
| 欢迎页自定义（文案 + 图片） | `MUI_WELCOMEPAGE_*` + 自制 164×314 位图 | ✅ |
| 许可协议页 | `MUI_PAGE_LICENSE`，勾选后才可继续 | ✅ |
| **更新日志页** | `Page custom` + `nsDialogs` + RichEdit | ✅ |
| 安装路径自定义 / 默认路径 | `MUI_PAGE_DIRECTORY` + `InstallDir` | ✅ |
| **桌面快捷方式开关** | 自定义选项页复选框 | ✅ |
| **开始菜单快捷方式开关** | 同上 | ✅ |
| 完成页「立即运行」 | `MUI_FINISHPAGE_RUN` | ✅ |
| 版权 / 公司 / 版本信息 | `VIAddVersionKey`（写进 exe 属性） | ✅ |
| 控制面板卸载项 | 注册表 `...\CurrentVersion\Uninstall\` | ✅ |
| 卸载时是否保留用户数据 | `un.onInit` 里询问 | ✅ |
| 免提权安装 | `RequestExecutionLevel user` + `$LOCALAPPDATA` | ✅ |
| 静默安装 `/S` | NSIS 原生 | ✅ |

`verify.ps1` 的结果（15 项全通过）：

```
=== 1. 静默安装到临时目录
  [通过] 主程序已释放 / 说明文件已释放 / 卸载程序已生成
  [通过] 桌面快捷方式 / 开始菜单快捷方式
  [通过] 卸载注册表项（显示名称、发行者、版本）
  [通过] 用户数据已生成
=== 2. 静默卸载（保留用户数据）
  [通过] 安装目录已删除 / 快捷方式已删除 / 注册表项已删除
  [通过] 用户数据按预期保留
```

---

## 四、踩到的坑（正式开发时要注意）

这几条都是实测撞出来的，直接影响生成器的写法：

1. **`MUI_PAGE_LICENSE` 的许可协议路径必须在编译期就存在**，
   不能写成 `$PLUGINSDIR\license.txt` 这种运行期路径，否则 makensis 直接报错。
   许可协议文件要用 **UTF-8 带 BOM** 保存。

2. **自定义页面读文件要小心编码。** `FileRead` 不认 UTF-8 BOM，也不认 UTF-16LE BOM；
   更新日志文件必须存成 **UTF-16LE（带 BOM）**，并且用 **`FileReadUTF16LE`** 读取，
   否则页面上的中文全是乱码。

3. **NSIS 字符串变量默认上限 1024 字符。** 更新日志如果拼进变量再显示，超过就会被截断。
   正式版要么换用大字符串版 NSIS，要么分段塞进控件。

4. **`InstallDirRegKey` 会记住上次的安装路径。** 这是设计如此（方便用户升级时找到旧位置），
   但升级/测试时容易被残留注册表带偏，卸载程序必须把它清干净。

5. **`.nsi` 脚本本身要存成 UTF-8 带 BOM**，否则脚本里的中文文案会乱码。

6. **没有代码签名证书的话，Windows SmartScreen 会提示「未知发布者」。**
   这是所有自研打包工具的通病，需要提前跟使用者说明。

7. **`RequestExecutionLevel admin` 的安装包在无人值守环境下会触发 UAC 弹窗**，
   所以自动化测试只能跑「仅当前用户安装」那个版本。

> 另：`tools\capture-screenshots.ps1` 驱动安装向导时，**必须用
> `PostMessage(WM_COMMAND, IDOK)`，不能用 `BM_CLICK`**。
> `BM_CLICK` 会产生延迟的重复点击，导致自定义页面刚创建就被瞬间跳过——
> 这个坑排查了很久，记在这里免得以后再踩。

---

## 五、目录结构

```
demo/feasibility/
├── build.ps1                  构建：生成资源 -> 编译示例程序 -> 编译两个安装包
├── verify.ps1                 自动化验证：静默安装 / 卸载 / 检查残留
├── demo.jianpack                工程文件（见 docs/工程文件格式.md）
├── demo.nsi                   安装脚本（将来由 Python 设计器自动生成）
├── assets/                    图标与 MUI 位图（由 src/make_assets.py 生成）
│   ├── app.ico                程序图标，多尺寸
│   ├── welcome.bmp            欢迎页左侧竖版位图 164×314
│   └── header.bmp             内页顶部横版位图 150×57
├── input/                     模拟"用户在 GUI 里选中的待打包文件"
│   ├── MyApp.exe              用系统自带 csc.exe 编译的示例程序
│   ├── 许可协议.txt            UTF-8 带 BOM
│   ├── 更新日志.txt            UTF-16LE 带 BOM
│   └── 使用说明.txt            UTF-8 带 BOM
├── src/                       源文件（不会被打包进去）
│   ├── MyApp.cs               示例程序源码（含版权信息声明）
│   ├── make_assets.py         用 Pillow 生成图标和位图
│   ├── make_overview.py       把页面截图拼成总览图
│   └── *.txt                  文本素材
├── tools/
│   └── capture-screenshots.ps1  驱动安装向导逐页截图
├── build/                     生成器产出的中间文件（.nsi、转码后的文本）
├── out/                       编译产物（安装包）
└── screenshots/               页面截图
```

---

## 六、下一步

前两步已经完成，剩下的都在项目根目录做：

1. ~~工程模型~~ ✅ `app/core/project.py`（字段定义见 `docs/工程文件格式.md`）
2. ~~脚本生成器~~ ✅ `app/engine/nsi.py`（`python -m app build`）
3. **Tkinter 向导界面**：新建工程 → 选文件 → 配置界面 → 打包
4. **打包分发**：用 PyInstaller 把设计器打包成单个 exe，`makensis.exe` 一起塞进去
