# Kenan's AutoClicker

An open-source input automation tool for **accessibility, repetitive work, and
software testing** — anything that otherwise means clicking or pressing the
same thing hundreds of times.

Built with Python and tkinter. Runs on Windows, macOS and Linux.

[![Build](https://github.com/KenanSab/KenansAutoClicker/actions/workflows/build.yml/badge.svg)](https://github.com/KenanSab/KenansAutoClicker/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Why this exists

Repetitive input is a real accessibility barrier. People with RSI, tremors, or
limited hand mobility struggle with tasks that assume fast, repeated clicking.
The same mechanism also solves ordinary problems: stepping through hundreds of
data-entry rows, or stress-testing a button in QA.

This project makes that automation **easy to set up, transparent about what it
is doing, and shareable** — so a setup that works for one person can be used by
everyone else in one click.

---

## Download

Windows `.exe` and macOS builds are produced automatically by GitHub Actions.

- **[Releases](../../releases)** — grab `KenansAutoClicker.exe` (Windows) or
  `KenansAutoClicker-macOS.zip` (Mac)
- No release yet? **Actions** tab → newest run → **Artifacts**

> Windows will show *"Windows protected your PC"* for any new unsigned app.
> Click **More info → Run anyway**. Code-signing certificates cost hundreds of
> dollars a year, which isn't practical for a free tool.

---

## Presets

The feature that makes this more than another auto clicker.

A **preset** is a ready-made setup — an interval, a button, a key, whatever
humanisation it needs — packaged so someone else can use it immediately.

**Built in:**

| Category | Presets |
|---|---|
| Accessibility | Assisted Click · Dwell Click · Key Repeat Assist |
| Productivity | Form Filler · Keep Screen Awake · Bulk Confirm |
| Testing | UI Stress Test · Repeatable QA Run · Human-like Clicking |

**From the community:** press **Browse community** to load presets contributed
by other people. The app only contacts the network when you press that button —
never on startup.

**Share your own:** *Save current as preset*, then open a pull request. See
[CONTRIBUTING.md](CONTRIBUTING.md). Your username appears on the preset card.

### Presets are safe by construction

A preset can only change **how clicking and typing behave**. It cannot touch
your hotkeys, theme, window settings or statistics — the app validates every
preset against an allow-list and discards anything else, whether it came from
a file or the internet. Nothing in a preset is ever executed as code.

Before anything is applied you get a **preview** showing exactly which settings
change and what they change to.

### A note on games

Presets for games are allowed, but **automating input in competitive online
games usually breaks their terms of service and can get your account
permanently banned.** Presets tagged `competitive` display that warning on
their card. Single-player, idle and AFK presets are fine.

---

## Features

**Auto clicker** — left / right / middle, single or double, interval from
milliseconds to minutes. Click at the cursor, a fixed point, or cycle through
a sequence of points you pick on screen.

**Auto key presser** — a single key, a sequence (`q w e r`), a combo
(`ctrl+shift+a`), or repeatedly typed text.

**Humanisation** — jitter, randomised intervals, variable hold time, smooth
eased movement, and burst mode, for input that isn't a dead metronome.

**Control** — global **F6** start/stop and **F9** panic stop that work even
when the window isn't focused, both rebindable. Toggle or hold-to-run.
Auto-stop after a number of actions or seconds, with an optional countdown.

**Quality of life** — live CPS counter, all-time stats, save/load profiles,
always-on-top, light and dark themes.

---

## Run from source

```bash
pip install -r requirements.txt
python KenansAutoClicker.py
```

## Build it yourself

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "KenansAutoClicker" KenansAutoClicker.py
```

## Tests

```bash
pip install pytest
python -m pytest tests/ -q
```

85 tests covering preset validation, the input engine, key parsing,
persistence, and interface behaviour.

---

## Permissions

- **macOS** — allow the app under *System Settings → Privacy & Security →
  Accessibility* so it can send clicks and keystrokes. Unsigned build, so
  right-click → **Open** the first time.
- **Windows / Linux** — nothing extra.

---

## Project layout

```
kenansautoclicker/
├── app.py           window, state, hotkeys, start/stop
├── engine.py        timing, humanisation, click/key loops
├── presets.py       preset model, validation, community fetch
├── ui_base.py       cards, rows, scrolling, theming
├── ui_home.py       Home page
├── ui_presets.py    Presets page
├── ui_settings.py   Settings page
├── widgets.py       switches, segmented pickers, disclosures
├── icons.py         Lucide icons + SVG path renderer
├── keys.py          key naming and parsing
└── storage.py       config and profiles
presets/             community preset library
tests/               pytest suite
```

---

## Credits

Created by **Kenan** — [github.com/KenanSab](https://github.com/KenanSab)

Icons are [Lucide](https://lucide.dev) (ISC License), rendered from their SVG
path data onto a canvas so they stay crisp and follow the theme without
needing an image library.

Licensed under the [MIT License](LICENSE) — free to use, modify and share,
including commercially, as long as the copyright notice is kept.

---

*Use responsibly, and only where automated input is permitted.*
