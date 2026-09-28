# 第三方组件声明 / Third-Party Notices

**简包装（JianPack）** 本身遵循 **Apache License 2.0**（见仓库根目录的 `LICENSE`）。
但它在分发时会**捆绑若干第三方组件**，这些组件各自由其原始许可授权。本文件列出
**分发版（便携包 / exe）** 中包含的第三方组件及其许可。

> 本文件即 Apache-2.0 第 4(d) 条所指的「署名声明（NOTICE）」。若你要再次分发本软件，
> 请连同 `LICENSE`、`NOTICE` 与本文件一起保留。

| 组件 | 用途 | 许可 | 许可原文 |
|---|---|---|---|
| **Python 3.14** | 运行时 | PSF-2.0 | <https://docs.python.org/3/license.html> |
| **Tcl/Tk**（Tkinter） | 图形界面 | TCL（BSD 类） | <https://www.tcl.tk/software/tcltk/license.html> |
| **Pillow** | 图片处理 | HPND | <https://github.com/python-pillow/Pillow/blob/main/LICENSE> |
| **PyInstaller**（bootloader） | 打包成 exe | GPL-2.0-or-later（含特殊例外） | <https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt> |
| **NSIS** | 安装包引擎（内嵌便携版） | zlib/libpng（LZMA 模块为 CPL-1.0，含特殊例外） | `vendor/nsis/COPYING` |
| **OpenSSL**（libcrypto / libssl） | 加密 / TLS | Apache-2.0 | <https://www.openssl.org/source/license.html> |
| **zlib** | 压缩 | Zlib | <https://zlib.net/zlib_license.html> |
| **libffi** | 外部函数接口 | MIT | <https://github.com/libffi/libffi/blob/master/LICENSE> |
| **Expat** | XML 解析 | MIT | <https://github.com/libexpat/libexpat/blob/master/expat/COPYING> |
| **bzip2** | 压缩 | bzip2-1.0.6（BSD 类） | <https://sourceware.org/bzip2/> |
| **xz / liblzma** | LZMA 压缩 | Public Domain / 0BSD | <https://tukaani.org/xz/> |
| **Zstandard** | zstd 压缩 | BSD-3-Clause | <https://github.com/facebook/zstd/blob/dev/LICENSE> |
| **libmpdec** | 十进制运算 | BSD-2-Clause | <https://www.bytereef.org/mpdecimal/license.html> |
| **Microsoft Visual C++ 运行库**（VCRUNTIME140.dll 等） | C 运行时 | Microsoft 可再分发条款 | <https://visualstudio.microsoft.com/license-terms/> |

### 说明

- 表中的「**特殊例外**」指组件作者明确允许把其二进制**打包进你的程序并分发**，
  **不会**因此要求你的代码开源（PyInstaller 与 NSIS 的 LZMA 模块都属于这种情况）。
- 各组件的**完整许可与版权声明**可在上表链接的官方页面 / 仓库中查阅。
- 本软件对上述组件的使用均为「原样」使用，未做修改；对 NSIS 则是以内嵌便携版形式
  调用其编译器。
- 若发现遗漏或与实际分发版本不符，请以实际分发版本中的文件为准，并反馈到
  <https://github.com/kllber/jianpack/issues>。
