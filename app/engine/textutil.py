"""把工程里的文字翻译成 NSIS 脚本里的字符串。

两件事：
1. **占位符展开**：``{appName}`` 这类花括号由本程序在打包时替换；
2. **NSIS 转义**：``$`` 和 ``"`` 在 NSIS 里有特殊含义，必须转义，
   但 ``$INSTDIR`` / ``$APPDATA`` 这类运行期常量要原样保留。
"""

from __future__ import annotations

import re

from ..core.errors import ProjectFileError
from ..i18n import t as _

PLACEHOLDER_RE = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")

# NSIS 里可以原样透传的运行期常量
NSIS_CONSTANTS = frozenset({
    "INSTDIR", "OUTDIR", "EXEDIR", "EXEFILE", "EXEPATH",
    "PROGRAMFILES", "PROGRAMFILES32", "PROGRAMFILES64",
    "COMMONFILES", "COMMONFILES32", "COMMONFILES64",
    "DESKTOP", "SMPROGRAMS", "SMSTARTUP", "STARTMENU", "QUICKLAUNCH",
    "TEMPLATES", "DOCUMENTS", "SENDTO", "RECENT", "FAVORITES",
    "MUSIC", "PICTURES", "VIDEOS", "NETHOOD", "FONTS", "ADMINTOOLS",
    "APPDATA", "LOCALAPPDATA", "PROFILE", "TEMP", "PLUGINSDIR",
    "WINDIR", "SYSDIR", "SYSTEM32", "NSISDIR", "HWNDPARENT",
    "LANGUAGE", "CMDLINE", "CD", "0", "1", "2", "3", "4",
})

# $INSTDIR / $0 / $R0 / ${FOO}
NSIS_VAR_RE = re.compile(r"\$(?:\{[A-Za-z0-9_]+\}|R\d|\d|[A-Za-z_][A-Za-z0-9_]*)")


def expand_placeholders(text: str, table: dict[str, str], where: str) -> str:
    """把 ``{xxx}`` 换成实际值；遇到不认识的占位符直接报错。"""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in table:
            known = "、".join(sorted(table))
            raise ProjectFileError(
                _("{where}: 未知的占位符 {{{key}}}（可用：{known}）").format(
                    where=where, key=key, known=known))
        return table[key]

    return PLACEHOLDER_RE.sub(replace, text)


def escape_nsis(text: str) -> str:
    """转义 ``$`` 与 ``"``，保留白名单里的 NSIS 运行期常量。"""
    out: list[str] = []
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch == "$":
            match = NSIS_VAR_RE.match(text, i)
            if match and _is_known_constant(match.group(0)):
                out.append(match.group(0))
                i = match.end()
            else:
                out.append("$$")
                i += 1
        elif ch == '"':
            out.append('$\\"')
            i += 1
        elif ch == "\r":
            i += 1
        elif ch == "\n":
            out.append("$\\r$\\n")
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def render(text: str, table: dict[str, str], where: str) -> str:
    """展开占位符 + 转义，一步到位。"""
    return escape_nsis(expand_placeholders(text, table, where))


def unwrap_nsis_string(text: str) -> str:
    """给 ``!define`` 用：返回去掉首尾引号后可直接内嵌的字符串。"""
    return text


def _is_known_constant(token: str) -> bool:
    body = token[1:]
    if body.startswith("{"):
        return True  # ${...} 是编译期 define，交给 makensis 处理
    if body.isdigit() or (len(body) == 2 and body[0] == "R" and body[1].isdigit()):
        return True
    return body.upper() in NSIS_CONSTANTS
