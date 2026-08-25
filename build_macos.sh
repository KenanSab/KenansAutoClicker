#!/usr/bin/env bash
# Build Kenan's AutoClicker into a macOS app.   Run:  bash build_macos.sh
set -e
python3 -m pip install --upgrade pip
python3 -m pip install pynput pyinstaller
python3 -m PyInstaller --onefile --windowed --name "KenansAutoClicker" KenansAutoClicker.py
echo "Done!  Your app:  dist/KenansAutoClicker.app"
echo "First run: allow it in System Settings > Privacy & Security > Accessibility"
