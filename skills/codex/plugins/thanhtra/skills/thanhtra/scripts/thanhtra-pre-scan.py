#!/usr/bin/env python3
"""Compatibility wrapper for the Thanh Tra deterministic pre-scan engine.

Resolution order:
1. Repo checkout (symlink install): tìm package thanhtra/ ở các thư mục cha.
2. CLI trên PATH (copy install): exec `thanhtra prescan ...`.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def find_repo_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "thanhtra" / "core" / "prescan.py").exists():
            return parent
    return None


def main() -> int:
    root = find_repo_root()
    if root is not None:
        sys.path.insert(0, str(root))
        from thanhtra.core.prescan import main as prescan_main

        return prescan_main()

    cli = shutil.which("thanhtra")
    if cli is not None:
        os.execv(cli, [cli, "prescan", *sys.argv[1:]])

    sys.stderr.write(
        "thanhtra-pre-scan: không tìm thấy Thanh Tra core (package thanhtra/) lẫn CLI `thanhtra` trên PATH.\n"
        "Cài CLI từ repo checkout: ./scripts/install.sh (symlink vào ~/.local/bin).\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
