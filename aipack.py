#!/usr/bin/env python
"""不安装也能用的入口。

    python aipack.py build demo\\feasibility\\demo.jianpack

安装之后（``pip install -e .``）则可以直接用 ``aipack`` 命令。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
