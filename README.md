# ⚡ Kenan's AutoClicker

A fast, clean **auto-clicker** *and* **auto-key presser** with a global
start/stop hotkey. Pick a key and it spams it until you stop. Works on
Windows, macOS, and Linux.

---

## ⬇️ Download

**Windows (.exe) & macOS builds are made automatically by GitHub Actions.**

- Go to the **[Releases](../../releases)** page and grab the latest
  `KenansAutoClicker.exe` (Windows) or `KenansAutoClicker-macOS.zip` (Mac).
- No release yet? Open the **Actions** tab → newest run → **Artifacts** and
  download the build from there.

> To cut a release, push a tag: `git tag v1.0.0 && git push --tags`.
> The workflow builds the `.exe`, builds the Mac app, and attaches both to the release.

---

## ✨ Features

- 🖱 **Auto clicker** — left / right / middle button, single or double click,
  precise interval (hours / minutes / seconds / milliseconds).
- ⌨ **Auto key presser** — record **any** key and spam it at your chosen speed.
- 🎯 **Global hotkey** — press **F6** anywhere to start / stop, even when the
  window isn't focused. Rebindable in Settings.
- 🔁 **Repeat** — run until stopped, or a fixed number of times.
- 🏠 **Home + ⚙ Settings pages**, with a 🌗 **light / dark** toggle top-right.

## ▶️ Usage

1. Enable **Auto Clicker** and/or **Auto Key Presser** on the Home page.
2. For key spamming, click **Record key** and press the key you want spammed.
3. Set the interval.
4. Press **F6** (or the Start button) to begin, **F6** again to stop.

## 🛠 Run from source

```bash
pip install -r requirements.txt
python KenansAutoClicker.py
```

## 📦 Build it yourself

- **Windows:** double-click `build_windows.bat` → `dist\KenansAutoClicker.exe`
- **macOS:** `bash build_macos.sh` → `dist/KenansAutoClicker.app`

## 🔐 Permissions

- **macOS:** on first run, allow it under
  *System Settings → Privacy & Security → Accessibility* so it can send clicks
  and key presses. (Unsigned build → right-click the app → **Open** the first time.)
- **Windows / Linux:** nothing extra.

## 🧰 Tech

Python · tkinter · [pynput](https://pypi.org/project/pynput/)

---

© 2026 Kenan — MIT License. Use responsibly, only where automated input is allowed.
