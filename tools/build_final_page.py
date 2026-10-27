#!/usr/bin/env python3
"""build_final_page.py — 生成「圆明园全景」离线单文件页（React 版）。

步骤：导出网页数据（tools/export_web_data.py）→ 在 web/app 下 ``npm run build:offline``
（Vite + vite-plugin-singlefile，模型以 base64 内联）→ 复制为仓库根目录的
「圆明园全景-打开这个.html」——双击即可打开，离线可用。

前置：web/app 下已执行过 ``npm install``。
用法：python3 tools/build_final_page.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    subprocess.run([sys.executable, str(_ROOT / "tools" / "export_web_data.py")], check=True)
    subprocess.run(["npm", "run", "build:offline"], cwd=_ROOT / "web" / "app", check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
