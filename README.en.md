<p align="center">
  <img src="docs/images/banner.png" alt="JianPack (简包装) — Visual Windows Installer Builder" width="100%">
</p>

<p align="center">
  <a href="https://github.com/kllber/jianpack/releases/latest"><img alt="Version" src="https://img.shields.io/badge/version-0.2.0-2ea44f"></a>
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
  <a href="https://github.com/kllber/jianpack/releases/latest"><img alt="Download JianPack v0.2.0" src="https://img.shields.io/badge/Download-JianPack%20v0.2.0-2ea44f?style=for-the-badge&logo=github&logoColor=white"></a>
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

## 1. Meet JianPack

It turns "a ready-made program inside a folder" into an installer — send it to someone
and they **double-click to install**: no unzipping, no hunting for the exe. Everything is
done by filling in a few fields and clicking — **no script to write**.

The main window has just 4 areas (see the screenshot above):

- **Versions** (top-left): save one project as several versions and switch back anytime;
- **Build Steps** (top-right): the table of contents of the 4-step wizard; the editor is right below;
- **Installer Preview** (middle-left): draws what the installer will look like, updating live as you edit;
- **Start Build** (bottom-left): validate / generate script / build / open output folder, plus a live log.

## 2. Strengths & positioning

Compared with tools like Inno Setup Compiler or hand-written NSIS scripts, JianPack takes
the "good enough and easy to pick up" route:

- **No scripting** — every feature is a field or a switch in the UI, so even beginners get a tidy installer;
- **Bilingual** — both the GUI and the built-in tutorial ship in Chinese and English;
- **Portable & dependency-free** — the app is one folder with a bundled portable NSIS; copy it to another PC and nothing needs installing;
- **Single-file project** — icon, program files, UI settings and version history all live in one `.jianpack`;
- **Versioning** — keep several versions in one project and switch with one click (rare among peers);
- **What you see is what you get** — a live preview on the left; drop any image format and it is auto-cropped to spec.

To be honest about where it **falls short** today: no script-level customization, no
incremental upgrade / patch / auto-update, and the set of installer pages is basically
fixed. If you need those, Inno Setup Compiler will fit better.

![Generated installer](demo/feasibility/screenshots/总览-安装向导全部页面.png)

## 3. Quick start (4 steps)

1. Launch it and click "New Project" in the start window; enter a name and location (only **one** `.jianpack` file is created).
2. Walk the wizard's **4 steps**:

   **① Basic Info** → **② Payload** → **③ Install Settings** → **④ Installer UI**

   (app name, the files to package, install location & output, each page's text and images.)
3. Click "**Start Build**" in the always-visible bottom-left panel. The installer goes to the **Desktop** by default.

> **Want more detail?** Press **F1** in the app (or Help → Tutorial): a **6-chapter
> illustrated tutorial** walks you from "what is this" all the way to advanced tips, in
> both languages — you can follow along while working.

![Start window](demo/feasibility/screenshots/启动窗口-有记录.png)

## 4. Features at a glance

- **Project & versions**: single-file `.jianpack`; version iterate / switch (only the last 2 versions keep their program files, older ones are auto-"retired"); double-click a project file to open it.
- **Install settings**: default / custom install path, allow the user to change it, remember last location; user data & uninstall prompt; both install modes can be generated at once; silent install/uninstall `/S`.
- **Installer UI**: text and images for Welcome / License / Changelog / Location / Options / Finish; License & Changelog edited inline or imported from txt; header and welcome images; an **auto-start** checkbox on the Finish page.
- **System integration & signing**: file associations, URL protocols, custom registry entries (written on install, cleaned on uninstall); automatic code signing (Authenticode, bring your own certificate).
- **Preview & images**: live preview on the left; drop any image format for the icon / header / welcome image and it is cropped to BMP and a multi-size ICO.
- **And more**: bilingual UI, light / dark themes, and a command-line build (below).

Every option is explained in the in-app tutorial (**F1, 6 chapters**).

![Live preview](demo/feasibility/screenshots/预览-welcome.png)

## 5. Download & run

Get the portable build from [Releases](https://github.com/kllber/jianpack/releases/latest):
`jianpack-vX.Y.Z-portable.zip`. Unzip and run **`简包装.exe`**; the whole folder can be moved
around freely. A command-line build is included under `aipack\`.

- **Requirements**: Windows 10 / 11 (64-bit); no Python, NSIS or any runtime needed.
- **Settings & cache** live in `data\` inside the app folder, so it stays portable.

Command line (`aipack\aipack.exe`):

```text
aipack validate  project.jianpack   validate only, no build
aipack generate  project.jianpack   generate the .nsi script only
aipack build     project.jianpack   generate and compile the installer
aipack pack      folder project     pack a project into one .jianpack
aipack unpack    project.jianpack   unpack a single project into a folder
```

## 6. License / author

- Author: **kllber**　·　GitHub: <https://github.com/kllber>　·　Email: 1394141383@qq.com
- License: **Apache-2.0** (see [LICENSE](LICENSE) and [NOTICE](NOTICE); third-party components in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md))

This is an **open-source tool** — feel free to use, share and report issues. Developed with
assistance from **DeepSeek V4.1 Flash**.

> **Disclaimer**: provided "as is", without warranty of any kind. Make sure you have the
> right to package the content and comply with applicable laws; the author is not liable for
> any direct or indirect consequences of using this software.
