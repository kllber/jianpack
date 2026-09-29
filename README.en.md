<p align="center">
  <img src="docs/images/banner.png" alt="JianPack (简包装) — Visual Windows Installer Builder" width="100%">
</p>

<p align="center">
  <a href="https://github.com/kllber/jianpack/releases/latest"><img alt="Version" src="https://img.shields.io/badge/version-0.1.0-2ea44f"></a>
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue"></a>
  <img alt="Platform: Windows 10 / 11" src="https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB">
  <img alt="Engine: NSIS" src="https://img.shields.io/badge/engine-NSIS-orange">
  <a href="https://github.com/kllber/jianpack/releases"><img alt="Downloads" src="https://img.shields.io/github/downloads/kllber/jianpack/total?color=2ea44f"></a>
</p>

<p align="center">
  <a href="README.md"><kbd>简体中文</kbd></a>&nbsp;&nbsp;<a href="README.en.md"><kbd><b>English</b></kbd></a>
</p>

<p align="center">
  <a href="https://github.com/kllber/jianpack/releases/latest"><img alt="Download JianPack v0.1.0" src="https://img.shields.io/badge/Download-JianPack%20v0.1.0-2ea44f?style=for-the-badge&logo=github&logoColor=white"></a>
</p>

---

# JianPack — Application Installer / Setup Builder

A visual installer-builder for Windows, aimed at beginners — it takes the most
commonly used parts of *Inno Setup Compiler* and makes them simple. The **GUI is
bilingual (Chinese / English)**, and the **installers it produces are
dependency-free**: the end user just double-clicks to install — no .NET, Python or
any runtime required.

Under the hood it uses **NSIS** as the packaging engine (zlib-style license, allows
redistribution and commercial use).

![Designer UI](demo/feasibility/screenshots/总览-设计器界面.png)

---

## 1. Current version & feature overview (v0.1.0)

| Area | Capability |
|---|---|
| **4-step wizard** | Basic info → Package contents → Install settings (incl. output & build) → Installer UI |
| **Project file** | `.jianpack` single-file container (essentially a zip: `project.json` + `assets/` + `payload/` …); also compatible with the older "folder project", auto-detected by file header; "Save As" always produces a single file |
| **Double-click to open** | The packaged build auto-associates `.jianpack` (writes HKCU, no admin needed); double-click goes straight to the main window; a one-click repair/remove is in Preferences |
| **Package contents** | Add files/folders; **folders keep their own name by default** (can be turned off in the dialog → place contents only, with live preview); include/exclude filters; main program auto-detected; **removing an item also deletes its copy under the project's `payload\`** (external references are left untouched) |
| **Install settings** | Default/custom install path, allow the user to change it, remember last location, show disk usage; user-data directory; whether to ask about keeping user data on uninstall |
| **Installer UI** | Text and images per page (Welcome / License / Changelog / Install location / Install options / Finish + header image); License and Changelog support "edit inline" or "import from txt"; **the Install options page also holds the desktop / Start Menu shortcut settings**; **unchecking a parent greys out its children** |
| **Start build** | Always-visible bottom-left panel: validate / generate script / start build / open output folder + live log; **build progress window** |
| **Code signing** | After building, signs the installer with `signtool` (Authenticode); bring your own certificate, leave empty to skip |
| **System integration** | Advanced drawer in step 3: **file associations / URL protocols / custom registry entries**; written on install, cleaned on uninstall |
| **App Properties languages** | Step 1 lets you **pick several** languages to list in the installer exe's properties (18 built in; custom name + language ID also supported) |
| **Auto-start on sign-in** | The Finish page can offer an "auto-start" checkbox (optionally checked by default); when ticked it writes the Run key, cleaned up on uninstall |
| **Live preview** | Covers the 7 installer pages plus an **App Properties** preview, follows the edited content and the **variant selected in step 3** automatically; toggle with `Ctrl+P` |
| **Images** | Drop any-format image for icon / header image / welcome image → crop dialog (drag/zoom) → auto-orient, alpha flattened onto white, exported as BMP / multi-size ICO |
| **Loading feedback** | A **loading window** when opening a project: double-click `.jianpack` / app start uses the icon version, opening from inside the app uses a simplified icon-less version; **it is skipped when reading is fast**, shown otherwise with **real extraction progress** |
| **UI** | Bilingual Chinese/English; light/dark themes; **checkboxes are custom-drawn ✓** (unaffected by the system theme) |
| **Preferences** | Language / theme / startup habits / file-association repair / cache directory ("use default location" + "clear cache files…") / restore defaults |
| **Built-in tutorial** | 8 illustrated chapters, in both Chinese and English (images generated from the real UI by a script), in a separate non-modal window |
| **Command line** | `validate` / `generate` / `build` / `pack` / `unpack` |
| **Engine** | Bundled portable NSIS; produced installers are dependency-free; supports silent install/uninstall `/S` |
| **Other** | Ships with a read-only demo project; low disk space is caught early; cache/settings travel with the folder (portable) |

---

## 2. Quick start

### GUI

```powershell
python aipack.py                                     # open (startup window appears first)
python aipack.py gui demo\feasibility\demo.jianpack    # open a specific project directly
```

- **Startup chooser**: New project / Open existing / Recent (the first row is always the
  bundled "demo project", shown in blue and not removable) / Quit.
- On first launch a **welcome page** appears (one-line intro + "Open tutorial", a
  "don't show again" checkbox, and a Chinese/English switch at the bottom-left).
- Then follow the 5 steps. Click "Start build" on the last page.

![Startup window](demo/feasibility/screenshots/启动窗口-有记录.png)

### Command line

```powershell
# 1) Install the NSIS compiler (once; not needed for the packaged build, NSIS is bundled)
winget install NSIS.NSIS

# 2) Validate the project
python -m app validate demo\feasibility\demo.jianpack

# 3) Generate the script and compile
python -m app build demo\feasibility\demo.jianpack
```

Or use `aipack.py` from any directory (no dependency on the current directory):

```powershell
python "D:\...\应用安装向导打包软件项目\aipack.py" build "D:\...\demo.jianpack"
```

After `pip install -e .` you can use the `aipack` command directly.

### Building standalone exes

```powershell
python tools\vendor-nsis.py     # copy the system NSIS into vendor\nsis (one time)
python tools\build-exe.py       # produce the two packages under dist\
```

Output:

```
dist\
├── 简包装\     GUI version (double-click to run, includes _internal)
└── aipack\     CLI version (great for scripting, includes _internal)
```

**How to distribute: zip up the whole `dist\<folder>` and send it. The recipient just
double-clicks the exe inside.** No Python, NSIS or any runtime needed on their side.

> **Why a folder and not a single exe**: with `--onefile`, every launch extracts the
> bundled 4 MB NSIS into a temp directory (which real-time protection then scans
> file-by-file) — measured at 30+ seconds to start. Switching to onedir brought it to
> 0.5 seconds. Compressed it's only about 12 MB anyway.

> **When trimming `vendor\nsis`**: do not delete `Contrib\UIs` — MUI2's
> `MUI_INTERFACE` loads `Contrib\UIs\modern.exe`; deleting it makes compilation fail
> outright. `makensis` lookup order: explicit path → `MAKENSIS` env var → bundled
> `vendor\nsis` → system-installed NSIS → `PATH`.

---

## 3. UI & workflow highlights

### The 4-step wizard

| Step | What you can do |
|---|---|
| 1. Basic info | App name, install directory name, version, file version, internal identifier, company/author, copyright, homepage, description, program icon |
| 2. Package contents | Add files/folders, adjust the post-install location (**a folder can keep its name or place contents only**), specify the main program, remove items |
| 3. Install settings | Install path / allow the user to change it / remember last location / disk usage / user data / uninstall prompt; **system integration (advanced)**; **which versions to build**; **output settings** (location / file name / compression); **code signing (advanced)** |
| 4. Installer UI | Text and images for each page; License/Changelog edited inline or imported from txt; header image; **the Install options page sets the desktop / Start Menu shortcuts**; **the Finish page can offer an "auto-start" checkbox** |

**Starting the build**: an always-visible panel at the **bottom-left** (validate / generate
script / start build / open output folder + live log) — not a wizard step, clickable anytime.

**Build variants are chosen in step 3 (important)**:
- **Install for "all users / current user only"**: ticked under "Which versions to build" —
  **both can be produced at once**. The live preview draws according to the first one ticked.
- With more than one, the file name automatically gets a `-PerMachine` / `-PerUser` suffix.

### Layout

```
┌──────────────┬────────────────────────────────────┐
│ Build steps   │                                    │
│ 1. Basic info │                                    │
│ 2. ...        │        Editor (takes all the rest) │
│ ...           │                                    │
├──────────────┤                                    │
│ Preview       │                                    │
│  [Installer]  │                                    │
└──────────────┴────────────────────────────────────┘
```

The left column has a fixed width; the editor takes the remaining width. **When the
window is wide enough, group boxes automatically flow into two columns** (single column
when narrow). The title bar's "maximize" button was removed (the layout is designed for
a normal window width, and filling the screen looks empty), but you can still drag the
border to resize; if it gets maximized by other means it is automatically restored.

### Live preview

Always present below the left column. It follows the page you're currently editing, or
you can pick one from the dropdown; it lists only the pages that **will actually
appear**. It's drawn to the real layout (window 503×362 etc.), though fonts/line breaks
may differ by a line or two from the final installer. The menu "View → Show install
preview" (`Ctrl+P`) toggles it, and the choice is remembered.

![Live preview](demo/feasibility/screenshots/预览-welcome.png)

### You don't have to make the images yourself

For the program icon, inner-page header image and welcome image: drop in any format
(PNG/JPG/BMP/GIF/WEBP), drag/zoom in the crop dialog, see the real result on the right,
and on confirm it is automatically converted to 150×57 / 164×314 BMP and a 256×256
multi-size ICO. **The original image is never modified.**

![Adjusting the header image](demo/feasibility/screenshots/图片裁剪-页头图.png)

### Loading feedback & build progress

- **Opening a project**: a loading window appears first (double-click/startup = icon
  version; opening from inside the app = simplified icon-less version). **If reading is
  fast (small project) it is skipped**, to avoid a "flash that looks like a bug"; once
  shown it stays at least ~0.8 seconds and shows real extraction progress.
- **Starting a build**: an icon progress window appears, showing which variant is being
  compiled + a scrolling progress bar + the output file name, and closes automatically
  on completion/failure.

### Preferences (`Ctrl+,`)

UI language (Chinese/English, reloads the UI on switch) · theme (light/dark) · startup
habits (welcome page, auto-open last project, show preview by default) · file
association (repair/remove) · cache directory (**"use default location" only clears the
path, not the files**; **"clear cache files…" deletes cached temporary projects, skipping
the one in use**) · "restore defaults" = reset.

### Built-in tutorial

Menu "Help → Tutorial" (`F1`): a table of contents on the left and illustrated text on
the right, in both Chinese and English, in a separate non-modal window that doesn't
block the main window. The images are generated from the real UI by
`tools\make-tutorial-images.py`.

---

## 4. What the generated installer looks like

A Chinese install wizard: Welcome → License → Changelog → Choose install location →
Install options → Progress → Finish.

![All installer pages](demo/feasibility/screenshots/总览-安装向导全部页面.png)

Two install modes (both can be produced at once in step 3):

| | For all users | Current user only |
|---|---|---|
| Location | `Program Files` | `%LOCALAPPDATA%\Programs` |
| Privileges | Requires admin (UAC) | No elevation, just double-click |
| Shortcuts | Visible to all users | Current user only |
| Registry | `HKLM` | `HKCU` |

- Normal uninstall: written into "Control Panel → Programs and Features", with icon,
  version and publisher; optionally keep user data.
- Silent install: `/S` (both install and uninstall).
- Small: the example package is about 100 KB (excluding your program files).
- Text variables: `{appName}` `{appVersion}` … are replaced at build time;
  `$INSTDIR` `$APPDATA` … are replaced by NSIS at install time.

**Output location**: by default it outputs to the **Desktop** (following OneDrive-style
redirection); step 3 "Output location" can change it to any directory (relative paths are
resolved against the project file's directory), leave it empty to go back to the Desktop.

---

## 5. Portability & data locations

```
<app folder>\
├── 简包装.exe
├── _internal\           runtime (contains assets: icons, tutorial images, demo project; vendor\nsis)
└── data\                created at runtime
    ├── settings.json    settings (recent files, language, theme, cache dir…)
    └── work\            cache: extracted projects + compilation intermediates (cleared on exit)
```

Settings, cache and the demo project all live inside the app folder, so the whole folder
can be moved around freely. Only when the app folder is not writable (e.g. extracted into
`Program Files`) does it fall back to `%APPDATA%\简包装`. Low disk space is caught early
with a prompt.

---

## 6. Recent changes (what this round did)

**New features**
- **Loading window** when opening a project (icon / simplified icon-less) + **real
  extraction progress** + delayed display.
- **Build progress window** (counts variants + progress bar + output file name).
- Package contents: a **"keep folder name" toggle per folder item** (dialog with live
  preview + a new list column).
- **Unchecking a parent greys out children** (fully wired across steps 3/4/5; values are
  retained).
- Cache in Preferences: button renamed to "**use default location**", added "**clear
  cache files…**".
- Checkboxes changed to **custom-drawn ✓** (some themes used to draw them as ✗).

**Behavior changes**
- "Install mode" **moved from step 3 to a multi-select in step 3**; the preview follows
  step 3, eliminating the "preview doesn't match the result" issue.
- Removing an item now **cleans up the project's `payload\` copy**, so no orphan files
  are left and the "overwrite?" prompt no longer keeps appearing.
- **The full tutorial image set (Chinese and English) was regenerated** and the text was
  synced.

**Important bugs fixed**
- In a Chinese IME, typing `p`/`t` then Enter would wrongly trigger "Tutorial"/"Build".
- Validation crashed outright when a source file was missing and no main program was set.
- After adding a folder, files were **flattened** into the install root (folder name lost).
- Opening a large project gave **no feedback** (solved by the loading window).

---

## 7. Verification / self-test (must run after changes)

```powershell
python tools\self-test.py                        # regression self-test: must be 0 failures, clean stderr
python -m app validate demo\feasibility\demo.jianpack
python -m app build    demo\feasibility\demo.jianpack
powershell -ExecutionPolicy Bypass -File demo\feasibility\verify.ps1   # 15/15
python tools\gui-build-test.py demo\feasibility\demo.jianpack            # actually run a build in the GUI
python tools\build-exe.py                                              # exes under dist\ don't depend on system NSIS
```

`self-test.py` covers: lossless project read/write, page-by-page UI walkthrough, startup
flow, image crop/conversion, embedded text, preview linkage, layout boundaries, tutorial
window, preferences, light/dark themes, single-file projects and temp-dir cleanup,
read-only protection of the demo project, cache/settings locations, low-disk-space
interception, double-click path detection, folder install paths, removed-item cleanup,
loading/progress windows, parent→child greying, cache buttons, etc. (groups 1–23).

---

## 8. Directory structure

```
app/                       Designer core (Python, stdlib + Pillow)
├── core/                  Project layer
│   ├── project.py         .jianpack data model, loading, derived values, validation, folder install paths
│   ├── serialize.py       Write to disk (reading lives in project.py)
│   ├── container.py       Single-file .jianpack pack/unpack/progress/safety checks
│   ├── assoc.py           .jianpack file association (HKCU, double-click to open)
│   ├── settings.py        App settings (recent files, language, theme, cache dir…)
│   ├── paths.py           Path resolution + Desktop directory
│   └── errors.py          Error types
├── engine/                Packaging layer
│   ├── nsi.py             Project -> NSIS script (including folder keep-name handling)
│   ├── assets.py          Encoding conversion + icon/bitmap size checks
│   ├── textutil.py        Placeholder expansion + NSIS string escaping
│   └── makensis.py        Locate and invoke makensis.exe
├── ui/                    GUI
│   ├── main_window.py     Main window, step navigation, opening projects (async + loading window)
│   ├── splash.py          Loading window / build progress window (icon and simplified variants)
│   ├── start_dialog.py    Startup chooser
│   ├── welcome_dialog.py  Startup welcome page
│   ├── preferences_dialog.py  Preferences (incl. cache buttons)
│   ├── new_project_dialog.py  New project
│   ├── item_dest_dialog.py    Change install location + "keep folder name"
│   ├── image_crop_dialog.py   Image cropping
│   ├── preview.py         Live install preview
│   ├── build_panel.py     Always-visible bottom-left "Start build" panel (buttons + log)
│   ├── tutorial.py / tutorial_content.py  Tutorial window and content
│   ├── theme.py           Light/dark theme (incl. custom-drawn ✓ checkboxes)
│   ├── i18n.py            Chinese/English text table
│   ├── resources.py / state.py / widgets.py
│   └── pages/             The 4 step pages (base.py holds the generic "grey out children" mechanism)
├── checks.py              Unified validation entry (shared by CLI and GUI)
├── cli.py                 Command-line entry
└── __main__.py            python -m app

docs/工程文件格式.md        .jianpack spec (field quick reference, validation rules, NSIS mapping)
tools/                     Dev & acceptance scripts (see above)
demo/feasibility/          Feasibility demo (also the generator's first test case)
data/                      The software's own data (created at runtime)
assets/                    App icons + demo + tutorial images
design/简装-图标/          Icon design drafts
vendor/nsis/               Portable NSIS shipped with the app (zlib-style license)
dist/                      Build output
```

---

## 9. Author / open source

- Author: **kllber**
- GitHub: <https://github.com/kllber>
- Email: 1394141383@qq.com
- License: **Apache-2.0** (see [LICENSE](LICENSE) and [NOTICE](NOTICE))

This is an **open-source tool** — use it, distribute it, and report issues. Development
was assisted by **DeepSeek V4.1 Flash**.

> **Disclaimer**: This software is provided "as is", without any express or implied
> warranty. Make sure you have the legal right to whatever you package, and comply with
> all applicable laws and regulations; the user bears any direct or indirect consequences
> of using this software.
