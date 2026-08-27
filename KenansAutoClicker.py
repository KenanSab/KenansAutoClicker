"""Kenan's AutoClicker — entry point.

Run with:      python KenansAutoClicker.py
Or as module:  python -m kenansautoclicker

The application itself lives in the `kenansautoclicker` package; this file is
the launcher PyInstaller builds from.
"""

import sys

try:
    from pynput import keyboard, mouse          # noqa: F401  (checked early)
except ImportError:
    raise SystemExit(
        "\nMissing dependency 'pynput'.\n"
        "Install it with:  pip install -r requirements.txt\n"
    )

from kenansautoclicker.app import main

if __name__ == "__main__":
    sys.exit(main())
