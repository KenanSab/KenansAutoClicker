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

### 🖱 Auto clicker
- Left / right / middle button, single or double click
- Precise interval — hours / minutes / seconds / **milliseconds**
- **Click targets:** follow the cursor, a **fixed point**, or a **multi-point
  sequence** — capture any spot with the on-screen **🎯 Pick point** button
- **Smooth movement** — eased, slightly-wobbly travel to the target

### 🎲 Humanization (looks less robotic)
- **Jitter** — random pixel offset around every click
- **Randomized interval** — e.g. `100ms ± 20ms`, so it isn't a dead metronome
- **Random hold time** — vary how long the button stays down
- **Burst mode** — fire N clicks, pause, repeat

### ⌨ Auto key presser
- **Single key** — record any key and spam it
- **Sequence** — cycle a macro like `q w e r`
- **Combo** — send `ctrl+shift+a` as one press
- **Type text** — repeatedly type a whole string
- Its own independent interval + randomization

### 🎮 Control
- **Global hotkeys** — **F6** start/stop and **F9** panic-stop, working even when
  the window isn't focused; all rebindable
- **Toggle** mode *or* **Hold** mode (runs only while you hold the key)
- Optional **separate hotkeys** for mouse (F7) and key (F8)
- **Start countdown**, and **auto-stop** after N actions or N seconds

### 📊 Quality of life
- Live **CPS counter** + all-time click **stats**
- **Save / load profiles**, plus auto-save of your last setup
- **Always on top**, 🏠 Home + ⚙ Settings pages, 🌗 **light / dark** toggle

## ▶️ Usage

1. Enable **Auto Clicker** and/or **Auto Key Presser** on the Home page.
2. For keys, pick a **Mode** — record a key, or type a sequence / combo / text.
3. Set the interval (and any jitter / randomization you want).
4. Press **F6** (or the Start button) to begin, **F6** again to stop.
   **F9** is the panic key — it stops everything instantly.

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

Icons are [Lucide](https://lucide.dev) (ISC License), drawn straight from their
SVG path data onto a canvas — so they stay crisp, follow the theme, and need no
image library.

---

© 2026 Kenan — MIT License. Use responsibly, only where automated input is allowed.
