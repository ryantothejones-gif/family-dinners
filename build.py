"""Package Family Dinners into a single Windows .exe with PyInstaller.

    pip install pyinstaller pywebview
    python build.py

Produces dist/FamilyDinners.exe. The app drives the family-dinners project folder on
disk (its collector.py + build_site.py are stdlib-only and run in-process), so keep the
project where it is - or point the app at it with the FAMILY_DINNERS_ROOT env var.
"""
from __future__ import annotations

import subprocess
import sys

NAME = "FamilyDinners"


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", NAME,
        "--collect-all", "webview",
        "app.py",
    ]
    print(" ".join(cmd))
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print("PyInstaller not found. Install it:  pip install pyinstaller", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
