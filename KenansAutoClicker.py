"""
Kenan's AutoClicker
===================
A fast, feature-packed auto-clicker + auto-key presser for Windows / macOS / Linux.

Highlights
----------
Humanization : jitter, randomized interval, random click-hold, smooth (eased) moves.
Targeting    : follow cursor, fixed point, or a multi-point sequence (with on-screen "Pick").
Modes        : toggle or hold-to-run, burst mode, start countdown, auto-stop by time/count,
               live CPS counter, all-time click stats.
Keys         : single key, key sequence (macro), key combo (Ctrl+Shift+X), or type-text mode.
Power        : global hotkeys (start/stop, panic, optional separate mouse/key keys),
               save/load profiles, always-on-top, light / dark theme.

Requirements
------------
Only one third-party dependency: pynput      ->   pip install pynput

Run it
------
    python KenansAutoClicker.py

Build a standalone app (single executable)
------------------------------------------
    pip install pynput pyinstaller
  Windows  ->  py -m PyInstaller --onefile --windowed --name "KenansAutoClicker" KenansAutoClicker.py
               result: dist\\KenansAutoClicker.exe
  macOS    ->  python3 -m PyInstaller --onefile --windowed --name "KenansAutoClicker" KenansAutoClicker.py
               result: dist/KenansAutoClicker  (grant Accessibility permission)
"""

import json
import math
import os
import random
import re
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from pynput import mouse, keyboard
    from pynput.mouse import Button, Controller as MouseController
    from pynput.keyboard import Controller as KeyboardController, Key, KeyCode
except ImportError:  # pragma: no cover
    raise SystemExit("\nMissing dependency 'pynput'.\nInstall it with:  pip install pynput\n")


APP_NAME = "Kenan's AutoClicker"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".kenans_autoclicker.json")

UI_FONT = "Segoe UI"          # falls back gracefully on macOS / Linux


# --------------------------------------------------------------------------- #
#  Palettes
# --------------------------------------------------------------------------- #
THEMES = {
    "dark": {
        "bg": "#0b0d13", "surface": "#141821", "surface2": "#1c2130", "raised": "#232a3b",
        "border": "#262c3b", "text": "#eef1f7", "muted": "#8b95a7", "faint": "#5d6779",
        "accent": "#6b8afd", "accent_soft": "#1e2740", "accent_fg": "#ffffff",
        "success": "#34d399", "danger": "#f87171", "field": "#0f131b",
        "track": "#2b3246",
    },
    "light": {
        "bg": "#f5f7fb", "surface": "#ffffff", "surface2": "#f1f3f9", "raised": "#e8ecf5",
        "border": "#e2e6ef", "text": "#131722", "muted": "#6b7280", "faint": "#9aa3b2",
        "accent": "#4f6ef7", "accent_soft": "#e8edff", "accent_fg": "#ffffff",
        "success": "#059669", "danger": "#dc2626", "field": "#f8fafc",
        "track": "#d3d9e6",
    },
}


# --------------------------------------------------------------------------- #
#  Key helpers
# --------------------------------------------------------------------------- #
# Some Key members only exist on certain platforms (e.g. Key.insert is absent on
# macOS), so every entry is resolved defensively and simply skipped if missing.
_KEY_ALIASES = {
    "space": "space", "enter": "enter", "return": "enter", "tab": "tab",
    "esc": "esc", "escape": "esc", "backspace": "backspace", "delete": "delete",
    "del": "delete", "insert": "insert", "up": "up", "down": "down",
    "left": "left", "right": "right", "home": "home", "end": "end",
    "pageup": "page_up", "pagedown": "page_down", "capslock": "caps_lock",
    "shift": "shift", "ctrl": "ctrl", "control": "ctrl", "alt": "alt",
    "cmd": "cmd", "win": "cmd", "super": "cmd", "meta": "cmd",
}
for _i in range(1, 21):
    _KEY_ALIASES[f"f{_i}"] = f"f{_i}"

NAMED_KEYS = {}
for _alias, _attr in _KEY_ALIASES.items():
    _k = getattr(Key, _attr, None)
    if _k is not None:
        NAMED_KEYS[_alias] = _k


def key_to_label(key):
    if key is None:
        return "None"
    if isinstance(key, KeyCode):
        if key.char is not None:
            return key.char.upper() if len(key.char) == 1 else repr(key.char)
        return f"<{key.vk}>"
    if isinstance(key, Key):
        return key.name.replace("_", " ").title()
    return str(key)


def key_to_str(key):
    if isinstance(key, KeyCode):
        return ("c:" + key.char) if key.char is not None else ("v:" + str(key.vk))
    if isinstance(key, Key):
        return "k:" + key.name
    return "k:f6"


def key_from_str(s):
    try:
        kind, val = s.split(":", 1)
        if kind == "c":
            return KeyCode.from_char(val)
        if kind == "v":
            return KeyCode.from_vk(int(val))
        if kind == "k":
            return getattr(Key, val)
    except Exception:
        pass
    return Key.f6


def parse_token(tok):
    tok = tok.strip().lower()
    if not tok:
        return None
    if tok in NAMED_KEYS:
        return NAMED_KEYS[tok]
    return KeyCode.from_char(tok[0])


def parse_sequence(text):
    """'q w e r' or 'q,w,e,r' -> list of keys, tapped in order."""
    return [k for k in (parse_token(t) for t in text.replace(",", " ").split()) if k]


def parse_combo(text):
    """'ctrl+shift+a' -> keys held together, released in reverse."""
    return [k for k in (parse_token(t) for t in text.replace(" ", "").split("+") if t) if k]


# --------------------------------------------------------------------------- #
#  Custom widgets
# --------------------------------------------------------------------------- #
class Toggle(tk.Canvas):
    """A modern pill switch bound to a BooleanVar."""

    W, H = 42, 24

    def __init__(self, parent, variable, command=None, **kw):
        super().__init__(parent, width=self.W, height=self.H, highlightthickness=0,
                         bd=0, cursor="hand2", **kw)
        self.var = variable
        self.command = command
        self.C = THEMES["dark"]
        self.bind("<Button-1>", self._click)
        self.var.trace_add("write", lambda *_: self.redraw())

    def _click(self, _e=None):
        self.var.set(not self.var.get())
        if self.command:
            self.command()

    def _pill(self, x0, y0, x1, y1, color):
        r = (y1 - y0) / 2
        self.create_oval(x0, y0, x0 + 2 * r, y1, fill=color, outline=color)
        self.create_oval(x1 - 2 * r, y0, x1, y1, fill=color, outline=color)
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=color, outline=color)

    def redraw(self):
        C = self.C
        self.delete("all")
        on = bool(self.var.get())
        self.configure(bg=self._parent_bg())
        self._pill(1, 3, self.W - 1, self.H - 3, C["accent"] if on else C["track"])
        kx = self.W - 12 if on else 12
        self.create_oval(kx - 8, 4, kx + 8, self.H - 4, fill="#ffffff", outline="#ffffff")

    def _parent_bg(self):
        try:
            return self.master.cget("bg")
        except tk.TclError:
            return self.C["surface"]

    def refresh_theme(self, C):
        self.C = C
        self.redraw()


# --------------------------------------------------------------------------- #
#  Icons — Lucide (https://lucide.dev), ISC License, Copyright (c) Lucide
#  Contributors. The strings below are Lucide's own 24x24 path data, drawn onto
#  a tk.Canvas by the tiny renderer beneath them. Doing it this way keeps the
#  icons crisp at any size, lets them take the theme colour, and avoids pulling
#  in an image library just to show six glyphs.
# --------------------------------------------------------------------------- #
LUCIDE = {
    "house": [
        "M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8",
        "M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 "
        "2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    ],
    "settings": [
        "M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 "
        "0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 "
        "2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 "
        "2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 "
        "6.051a2.34 2.34 0 0 0 3.319-1.915",
        "circle:12,12,3",
    ],
    "sun": [
        "circle:12,12,4",
        "M12 2v2", "M12 20v2", "m4.93 4.93 1.41 1.41", "m17.66 17.66 1.41 1.41",
        "M2 12h2", "M20 12h2", "m6.34 17.66-1.41 1.41", "m19.07 4.93-1.41 1.41",
    ],
    "moon": [
        "M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 "
        "8.268 8.268c.344-.215.825-.004.803.401",
    ],
    "chevron-right": ["m9 18 6-6-6-6"],
    "chevron-down": ["m6 9 6 6 6-6"],
    "crosshair": [
        "circle:12,12,10",
        "line:22,12,18,12", "line:6,12,2,12", "line:12,6,12,2", "line:12,22,12,18",
    ],
}

_PATH_TOKENS = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def _cubic(p0, p1, p2, p3, steps=14):
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        pts.append((u * u * u * p0[0] + 3 * u * u * t * p1[0]
                    + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                    u * u * u * p0[1] + 3 * u * u * t * p1[1]
                    + 3 * u * t * t * p2[1] + t * t * t * p3[1]))
    return pts


def _arc(x1, y1, rx, ry, phi_deg, large, sweep, x2, y2, steps=18):
    """SVG elliptical arc -> points (endpoint to centre parameterisation, F.6.5)."""
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [(x2, y2)]
    phi = math.radians(phi_deg)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    co = math.sqrt(max(num / den, 0.0)) if den else 0.0
    if large == sweep:
        co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2.0
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2.0

    def ang(ux, uy, vx, vy):
        d = math.hypot(ux, uy) * math.hypot(vx, vy)
        if d == 0:
            return 0.0
        a = math.acos(max(-1.0, min(1.0, (ux * vx + uy * vy) / d)))
        return -a if (ux * vy - uy * vx) < 0 else a

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    th1 = ang(1, 0, ux, uy)
    dth = ang(ux, uy, vx, vy)
    if not sweep and dth > 0:
        dth -= 2 * math.pi
    elif sweep and dth < 0:
        dth += 2 * math.pi
    pts = []
    for i in range(1, steps + 1):
        t = th1 + dth * i / steps
        ct, st = math.cos(t), math.sin(t)
        pts.append((cx + rx * ct * cp - ry * st * sp,
                    cy + rx * ct * sp + ry * st * cp))
    return pts


def parse_svg_path(d):
    """Flatten an SVG path string into a list of polylines."""
    toks = [(c, n) for c, n in _PATH_TOKENS.findall(d)]
    i = 0
    cmd = None
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    prev_c2 = None
    lines = []
    poly = []

    def nums(k):
        nonlocal i
        out = []
        while len(out) < k and i < len(toks) and toks[i][0] == "":
            out.append(float(toks[i][1]))
            i += 1
        return out

    while i < len(toks):
        if toks[i][0]:
            cmd = toks[i][0]
            i += 1
        rel = cmd.islower()
        c = cmd.upper()

        if c == "M":
            v = nums(2)
            if len(v) < 2:
                break
            cur = (cur[0] + v[0], cur[1] + v[1]) if rel else (v[0], v[1])
            if len(poly) > 1:
                lines.append(poly)
            poly = [cur]
            start = cur
            cmd = "l" if rel else "L"        # subsequent pairs are implicit lineto
        elif c in "LHV":
            if c == "L":
                v = nums(2)
                if len(v) < 2:
                    break
                cur = (cur[0] + v[0], cur[1] + v[1]) if rel else (v[0], v[1])
            elif c == "H":
                v = nums(1)
                if not v:
                    break
                cur = (cur[0] + v[0], cur[1]) if rel else (v[0], cur[1])
            else:
                v = nums(1)
                if not v:
                    break
                cur = (cur[0], cur[1] + v[0]) if rel else (cur[0], v[0])
            poly.append(cur)
        elif c in "CS":
            if c == "C":
                v = nums(6)
                if len(v) < 6:
                    break
                p1 = (cur[0] + v[0], cur[1] + v[1]) if rel else (v[0], v[1])
                p2 = (cur[0] + v[2], cur[1] + v[3]) if rel else (v[2], v[3])
                p3 = (cur[0] + v[4], cur[1] + v[5]) if rel else (v[4], v[5])
            else:
                v = nums(4)
                if len(v) < 4:
                    break
                p1 = (2 * cur[0] - prev_c2[0], 2 * cur[1] - prev_c2[1]) if prev_c2 else cur
                p2 = (cur[0] + v[0], cur[1] + v[1]) if rel else (v[0], v[1])
                p3 = (cur[0] + v[2], cur[1] + v[3]) if rel else (v[2], v[3])
            poly.extend(_cubic(cur, p1, p2, p3))
            prev_c2, cur = p2, p3
            continue
        elif c == "A":
            v = nums(7)
            if len(v) < 7:
                break
            end = (cur[0] + v[5], cur[1] + v[6]) if rel else (v[5], v[6])
            poly.extend(_arc(cur[0], cur[1], v[0], v[1], v[2],
                             int(v[3]), int(v[4]), end[0], end[1]))
            cur = end
        elif c == "Z":
            if poly:
                poly.append(start)
                lines.append(poly)
                poly = [start]
            cur = start
        else:
            i += 1
            continue
        if c != "C" and c != "S":
            prev_c2 = None

    if len(poly) > 1:
        lines.append(poly)
    return lines


def draw_icon(canvas, name, size, color, stroke=2.0):
    """Render a Lucide icon onto `canvas`, scaled from its 24x24 grid."""
    k = size / 24.0
    w = max(stroke * k, 1.0)
    for shape in LUCIDE.get(name, []):
        if shape.startswith("circle:"):
            cx, cy, r = (float(v) for v in shape[7:].split(","))
            canvas.create_oval((cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k,
                               outline=color, width=w)
        elif shape.startswith("line:"):
            x1, y1, x2, y2 = (float(v) for v in shape[5:].split(","))
            canvas.create_line(x1 * k, y1 * k, x2 * k, y2 * k,
                               fill=color, width=w, capstyle="round")
        else:
            for poly in parse_svg_path(shape):
                if len(poly) > 1:
                    flat = [v * k for pt in poly for v in pt]
                    canvas.create_line(*flat, fill=color, width=w,
                                       capstyle="round", joinstyle="round",
                                       smooth=False)


class IconButton(tk.Canvas):
    """A clickable Lucide icon that follows the theme."""

    def __init__(self, parent, kind, command, size=34):
        super().__init__(parent, width=size, height=size, highlightthickness=0,
                         bd=0, cursor="hand2")
        self.kind = kind          # 'home' | 'settings' | 'theme'
        self.command = command
        self.size = size
        self.active = False
        self.theme_is_dark = True
        self.C = THEMES["dark"]
        self.bind("<Button-1>", lambda _e: command())
        self.bind("<Enter>", lambda _e: self.draw(hover=True))
        self.bind("<Leave>", lambda _e: self.draw())

    def draw(self, hover=False):
        C = self.C
        self.delete("all")
        self.configure(bg=self._bg())
        fg = C["accent"] if self.active else (C["text"] if hover else C["muted"])
        name = {"home": "house", "settings": "settings"}.get(
            self.kind, "sun" if self.theme_is_dark else "moon")
        glyph = self.size * 0.62
        self._offset_draw(name, glyph, (self.size - glyph) / 2, fg)

    def _offset_draw(self, name, glyph, pad, fg):
        k = glyph / 24.0
        for shape in LUCIDE.get(name, []):
            if shape.startswith("circle:"):
                cx, cy, r = (float(v) for v in shape[7:].split(","))
                self.create_oval(pad + (cx - r) * k, pad + (cy - r) * k,
                                 pad + (cx + r) * k, pad + (cy + r) * k,
                                 outline=fg, width=max(2.0 * k, 1.0))
            elif shape.startswith("line:"):
                x1, y1, x2, y2 = (float(v) for v in shape[5:].split(","))
                self.create_line(pad + x1 * k, pad + y1 * k, pad + x2 * k, pad + y2 * k,
                                 fill=fg, width=max(2.0 * k, 1.0), capstyle="round")
            else:
                for poly in parse_svg_path(shape):
                    if len(poly) > 1:
                        flat = [pad + v * k for pt in poly for v in pt]
                        self.create_line(*flat, fill=fg, width=max(2.0 * k, 1.0),
                                         capstyle="round", joinstyle="round")

    def _bg(self):
        try:
            return self.master.cget("bg")
        except tk.TclError:
            return self.C["surface"]

    def refresh_theme(self, C, is_dark=None):
        self.C = C
        if is_dark is not None:
            self.theme_is_dark = is_dark
        self.draw()


class Disclosure(tk.Frame):
    """A collapsible section: a clickable arrow + title revealing `.body`."""

    def __init__(self, parent, text, variable):
        super().__init__(parent, highlightthickness=0, bd=0)
        self.var = variable
        self.C = THEMES["dark"]

        self.header = tk.Frame(self, cursor="hand2")
        self.header.pack(fill="x")
        self.arrow = tk.Canvas(self.header, width=14, height=14,
                               highlightthickness=0, bd=0, cursor="hand2")
        self.arrow.pack(side="left", padx=(0, 8))
        self.label = tk.Label(self.header, text=text, font=(UI_FONT, 9, "bold"),
                              cursor="hand2", anchor="w")
        self.label.pack(side="left")

        self.body = tk.Frame(self, highlightthickness=0, bd=0)

        for w in (self.header, self.arrow, self.label):
            w.bind("<Button-1>", self._toggle)
        self.var.trace_add("write", lambda *_: self.sync())

    def _toggle(self, _e=None):
        self.var.set(not self.var.get())

    def sync(self):
        if self.var.get():
            self.body.pack(fill="x", pady=(8, 0))
        else:
            self.body.pack_forget()
        self.draw()

    def draw(self):
        self.arrow.delete("all")
        self.arrow.configure(bg=self.header.cget("bg"))
        draw_icon(self.arrow, "chevron-down" if self.var.get() else "chevron-right",
                  14, self.C["muted"], stroke=2.4)

    def refresh_theme(self, C):
        self.C = C
        self.configure(bg=C["surface"])
        self.header.configure(bg=C["surface"])
        self.body.configure(bg=C["surface"])
        self.label.configure(bg=C["surface"], fg=C["muted"])
        self.draw()


class Segmented(tk.Frame):
    """A row of mutually exclusive pill buttons bound to a StringVar."""

    def __init__(self, parent, variable, options, command=None, width=None):
        super().__init__(parent, highlightthickness=0, bd=0)
        self.var = variable
        self.options = list(options)
        self.command = command
        self.C = THEMES["dark"]
        self.btns = {}
        for opt in self.options:
            b = tk.Label(self, text=opt, font=(UI_FONT, 9), cursor="hand2",
                         padx=12, pady=5)
            if width:
                b.configure(width=width)
            b.pack(side="left", padx=(0, 3))
            b.bind("<Button-1>", lambda _e, o=opt: self._pick(o))
            self.btns[opt] = b
        self.var.trace_add("write", lambda *_: self.redraw())

    def _pick(self, opt):
        self.var.set(opt)
        if self.command:
            self.command()

    def redraw(self):
        C = self.C
        cur = self.var.get()
        self.configure(bg=self._parent_bg())
        for opt, b in self.btns.items():
            if opt == cur:
                b.configure(bg=C["accent"], fg=C["accent_fg"], font=(UI_FONT, 9, "bold"))
            else:
                b.configure(bg=C["surface2"], fg=C["muted"], font=(UI_FONT, 9))

    def _parent_bg(self):
        try:
            return self.master.cget("bg")
        except tk.TclError:
            return self.C["surface"]

    def refresh_theme(self, C):
        self.C = C
        self.redraw()


# --------------------------------------------------------------------------- #
#  Application
# --------------------------------------------------------------------------- #
class AutoClickerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme_name = "dark"
        self.C = THEMES[self.theme_name]

        self.mouse_active = False
        self.key_active = False
        self.click_thread = None
        self.key_thread = None

        self.run_clicks = 0
        self.total_clicks = 0
        self._cps_last_count = 0
        self._cps_last_time = time.time()

        self.recording_target = None

        self.spam_key = KeyCode.from_char("a")
        self.master_hotkey = Key.f6
        self.panic_hotkey = Key.f9
        self.mouse_hotkey = Key.f7
        self.key_hotkey = Key.f8

        self._hold_mode = False
        self._separate = False
        self._master_down = self._mouse_hk_down = self._key_hk_down = False

        self.points = []

        self.mouse_ctl = MouseController()
        self.kbd_ctl = KeyboardController()

        self._themed = []     # (widget, role)
        self._custom = []     # widgets exposing refresh_theme
        self.vars = {}

        self._build_ui()
        self._load_config()
        self._start_global_listener()
        self.apply_theme()
        self._tick_cps()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- vars ---------------------------------------------------------- #
    def _sv(self, name, default):
        v = tk.StringVar(value=default); self.vars[name] = v; return v

    def _bv(self, name, default):
        v = tk.BooleanVar(value=default); self.vars[name] = v; return v

    def _init_vars(self):
        # mouse
        self._bv("mouse_enabled", True)
        self._sv("click_val", "100"); self._sv("click_unit", "ms")
        self._sv("click_rand", "0")
        self._sv("mouse_button", "Left"); self._sv("click_type", "Single")
        self._sv("target_mode", "Cursor")
        self._sv("fixed_x", "0"); self._sv("fixed_y", "0")
        self._bv("smooth_move", False)
        self._bv("jitter_on", False); self._sv("jitter_px", "3")
        self._bv("hold_rand_on", False); self._sv("hold_min", "10"); self._sv("hold_max", "40")
        self._bv("burst_on", False); self._sv("burst_n", "10"); self._sv("burst_pause", "1")
        self._bv("adv_click_open", False)
        # key
        self._bv("key_enabled", False)
        self._sv("key_mode", "Key")
        self._sv("key_value", "")
        self._sv("key_val_int", "100"); self._sv("key_unit", "ms")
        self._sv("key_rand", "0")
        self._bv("adv_key_open", False)
        # settings
        self._sv("activation", "Toggle")
        self._bv("separate_hotkeys", False)
        self._sv("stop_mode", "Never")
        self._sv("stop_count", "100"); self._sv("stop_time", "10")
        self._sv("countdown", "0")
        self._bv("always_top", False)
        self.status_text = self._sv("status", "Ready")

    # ---- shell --------------------------------------------------------- #
    def _build_ui(self):
        self.root.title(APP_NAME)
        self.root.geometry("600x760")
        self.root.minsize(560, 620)
        self._init_vars()
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        # define the slim scrollbar style up front — widgets reference it on creation
        try:
            self.style.layout("App.Vertical.TScrollbar", [
                ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                    ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        except tk.TclError:
            pass

        # ---------- header ----------
        self.topbar = tk.Frame(self.root, height=64)
        self.topbar.pack(fill="x"); self.topbar.pack_propagate(False)
        self._reg(self.topbar, "surface")

        brand = tk.Frame(self.topbar); brand.pack(side="left", padx=20)
        self._reg(brand, "surface")
        self.title_lbl = tk.Label(brand, text="Kenan's AutoClicker",
                                  font=(UI_FONT, 15, "bold"), anchor="w")
        self.title_lbl.pack(anchor="w"); self._reg(self.title_lbl, "title")

        icons = tk.Frame(self.topbar); icons.pack(side="right", padx=16)
        self._reg(icons, "surface")
        self.home_btn = IconButton(icons, "home", lambda: self.show_page("home"))
        self.settings_btn = IconButton(icons, "settings", lambda: self.show_page("settings"))
        self.theme_btn = IconButton(icons, "theme", self.toggle_theme)
        for b in (self.home_btn, self.settings_btn, self.theme_btn):
            b.pack(side="left", padx=4)
            self._custom.append(b)

        self.divider = tk.Frame(self.root, height=1); self.divider.pack(fill="x")
        self._reg(self.divider, "border_fill")

        # ---------- pages ----------
        self.container = tk.Frame(self.root); self.container.pack(fill="both", expand=True)
        self._reg(self.container, "bg")
        self.active_canvas = None
        self.pages = {"home": self._build_home(), "settings": self._build_settings()}
        self._bind_wheel()
        self.show_page("home")

        # ---------- footer ----------
        self.footdiv = tk.Frame(self.root, height=1); self.footdiv.pack(fill="x", side="bottom")
        self._reg(self.footdiv, "border_fill")

        self.actionbar = tk.Frame(self.root, height=84)
        self.actionbar.pack(fill="x", side="bottom"); self.actionbar.pack_propagate(False)
        self._reg(self.actionbar, "surface")

        left = tk.Frame(self.actionbar); left.pack(side="left", padx=20)
        self._reg(left, "surface")
        self.status_lbl = tk.Label(left, textvariable=self.status_text,
                                   font=(UI_FONT, 11, "bold"), anchor="w")
        self.status_lbl.pack(anchor="w"); self._reg(self.status_lbl, "title")
        self.cps_var = tk.StringVar(value="0.0 CPS  ·  0 total")
        self.cps_lbl = tk.Label(left, textvariable=self.cps_var, font=(UI_FONT, 9), anchor="w")
        self.cps_lbl.pack(anchor="w", pady=(2, 0)); self._reg(self.cps_lbl, "muted")

        self.action_btn = tk.Label(self.actionbar, text="Start", font=(UI_FONT, 12, "bold"),
                                   cursor="hand2", padx=38, pady=12)
        self.action_btn.pack(side="right", padx=20)
        self.action_btn.bind("<Button-1>", lambda _e: self.master_toggle())
        self._reg(self.action_btn, "primary")

    def _make_scrollable(self, parent):
        """Wrap `parent` in a scrolling canvas and remember it for wheel routing."""
        canvas = tk.Canvas(parent, highlightthickness=0, bd=0); self._reg(canvas, "bg")
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview,
                           style="App.Vertical.TScrollbar")
        inner = tk.Frame(canvas); self._reg(inner, "bg")
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        parent.canvas = canvas          # show_page() routes the wheel to this
        return inner

    def _bind_wheel(self):
        """One global wheel handler, dispatched to whichever page is visible.

        Binding per-page would not work: bind_all is global, so a second page's
        binding replaces the first. Wheel deltas also differ per platform —
        Windows sends multiples of 120, macOS sends small integers, and X11
        sends Button-4/5 instead.
        """
        def wheel(event):
            canvas = getattr(self, "active_canvas", None)
            if canvas is None:
                return
            num = getattr(event, "num", 0)
            delta = getattr(event, "delta", 0) or 0
            if num == 4:
                step = -3
            elif num == 5:
                step = 3
            elif delta:
                # Windows sends multiples of 120; macOS sends small numbers.
                step = (-delta / 120 * 3) if abs(delta) >= 120 else (-delta * 3)
            else:
                return
            step = int(step)
            if step == 0:               # never let rounding swallow a scroll
                step = -1 if (delta or -num) > 0 else 1
            canvas.yview_scroll(step, "units")

        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind_all(seq, wheel)

    # ---- layout primitives --------------------------------------------- #
    def _card(self, parent, title, toggle_var=None):
        """A padded surface block with an optional switch in its header."""
        outer = tk.Frame(parent, highlightthickness=1, bd=0)
        outer.pack(fill="x", padx=18, pady=(14, 0))
        self._reg(outer, "card")

        head = tk.Frame(outer); head.pack(fill="x", padx=18, pady=(15, 0))
        self._reg(head, "surface")
        lbl = tk.Label(head, text=title, font=(UI_FONT, 11, "bold"), anchor="w")
        lbl.pack(side="left"); self._reg(lbl, "title")
        if toggle_var is not None:
            t = Toggle(head, toggle_var)
            t.pack(side="right"); self._custom.append(t)

        body = tk.Frame(outer); body.pack(fill="x", padx=18, pady=(12, 16))
        self._reg(body, "surface")
        return body

    def _row(self, parent, label, hint=None):
        """One setting line: label (+optional hint) on the left, controls right."""
        r = tk.Frame(parent); r.pack(fill="x", pady=5)
        self._reg(r, "surface")
        lf = tk.Frame(r); lf.pack(side="left", anchor="w")
        self._reg(lf, "surface")
        l = tk.Label(lf, text=label, font=(UI_FONT, 10), anchor="w")
        l.pack(anchor="w"); self._reg(l, "label")
        if hint:
            h = tk.Label(lf, text=hint, font=(UI_FONT, 8), anchor="w")
            h.pack(anchor="w"); self._reg(h, "faint")
        ctrl = tk.Frame(r); ctrl.pack(side="right", anchor="e")
        self._reg(ctrl, "surface")
        ctrl.row = r          # so callers can re-pack the whole line
        return ctrl

    def _right_stack(self, ctrl, widgets):
        """Pack widgets right-aligned, so trailing controls line up across rows."""
        for w in reversed(widgets):
            w.pack(side="right", padx=(4, 0))

    def _sep(self, parent):
        s = tk.Frame(parent, height=1); s.pack(fill="x", pady=9)
        self._reg(s, "border_fill")

    def _sub(self, parent, text):
        l = tk.Label(parent, text=text.upper(), font=(UI_FONT, 8, "bold"), anchor="w")
        l.pack(anchor="w", pady=(10, 2)); self._reg(l, "faint")

    def _disclosure(self, parent, text, var):
        """A collapsed section. Returns the body to pack rows into."""
        d = Disclosure(parent, text, var)
        d.pack(fill="x", pady=(4, 0))
        d.sync()
        self._custom.append(d)
        return d.body

    # ---- HOME ---------------------------------------------------------- #
    def _build_home(self):
        page = tk.Frame(self.container); self._reg(page, "bg")
        body = self._make_scrollable(page)

        # ============ CLICKER ============
        c = self._card(body, "Auto Clicker", self.vars["mouse_enabled"])

        ctrl = self._row(c, "Interval")
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["click_val"], 6),
            self._unit(ctrl, self.vars["click_unit"])])

        ctrl = self._row(c, "Button")
        self._seg(ctrl, self.vars["mouse_button"], ["Left", "Right", "Middle"]).pack()

        ctrl = self._row(c, "Click")
        self._seg(ctrl, self.vars["click_type"], ["Single", "Double"]).pack()

        self._sep(c)

        ctrl = self._row(c, "Click at")
        self.target_row = ctrl.row
        self._seg(ctrl, self.vars["target_mode"], ["Cursor", "Fixed", "Multi"],
                  command=self._refresh_target_ui).pack()

        # --- Fixed point: pick + X/Y (packed under "Click at" on demand) ---
        ctrl = self._row(c, "Position")
        self.pos_row = ctrl.row
        self._right_stack(ctrl, [
            self._icon_pill(ctrl, "Pick point", self._pick_point),
            self._entry(ctrl, self.vars["fixed_x"], 5),
            self._unit_label(ctrl, "x"),
            self._entry(ctrl, self.vars["fixed_y"], 5),
            self._unit_label(ctrl, "y")])

        # --- Multi point: add to a list ---
        ctrl = self._row(c, "Points", "clicked in order, looping")
        self.points_row = ctrl.row
        self.points_lbl = tk.Label(ctrl, text="none yet", font=(UI_FONT, 9))
        self._reg(self.points_lbl, "muted")
        self._right_stack(ctrl, [
            self._icon_pill(ctrl, "Add point", self._pick_point),
            self.points_lbl,
            self._icon_pill(ctrl, "Clear", self._clear_points)])

        # ---- collapsed by default: humanization & extras ----
        self._sep(c)
        adv = self._disclosure(c, "Humanize & advanced", self.vars["adv_click_open"])

        ctrl = self._row(adv, "Randomize interval", "keeps the rhythm human")
        self._right_stack(ctrl, [
            self._pm(ctrl),
            self._entry(ctrl, self.vars["click_rand"], 5),
            self._unit_label(ctrl, "ms")])

        ctrl = self._row(adv, "Jitter", "random pixel wobble")
        self._right_stack(ctrl, [
            self._pm(ctrl),
            self._entry(ctrl, self.vars["jitter_px"], 4),
            self._unit_label(ctrl, "px"),
            self._toggle(ctrl, self.vars["jitter_on"])])

        ctrl = self._row(adv, "Random hold", "vary how long it presses")
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["hold_min"], 4),
            self._unit_label(ctrl, "–"),
            self._entry(ctrl, self.vars["hold_max"], 4),
            self._unit_label(ctrl, "ms"),
            self._toggle(ctrl, self.vars["hold_rand_on"])])

        ctrl = self._row(adv, "Move smoothly", "glide like a real hand")
        self._toggle(ctrl, self.vars["smooth_move"]).pack(side="right")

        ctrl = self._row(adv, "Burst", "click a batch, then rest")
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["burst_n"], 4),
            self._unit_label(ctrl, "×, rest"),
            self._entry(ctrl, self.vars["burst_pause"], 4),
            self._unit_label(ctrl, "s"),
            self._toggle(ctrl, self.vars["burst_on"])])

        # ============ KEY ============
        k = self._card(body, "Auto Key Presser", self.vars["key_enabled"])

        ctrl = self._row(k, "Mode")
        self.key_mode_row = ctrl.row
        self._seg(ctrl, self.vars["key_mode"], ["Key", "Sequence", "Combo", "Text"],
                  command=self._refresh_key_ui).pack(side="right")

        ctrl = self._row(k, "Key")
        self.key_row = ctrl.row
        self.key_display = tk.Label(ctrl, text=key_to_label(self.spam_key),
                                    font=(UI_FONT, 10, "bold"), width=7, padx=10, pady=5)
        self._reg(self.key_display, "chip")
        self._right_stack(ctrl, [
            self.key_display,
            self._icon_pill(ctrl, "Record", lambda: self._start_recording("spam"))])

        ctrl = self._row(k, "Value")
        self.keyval_row = ctrl.row
        self.keyval_entry = self._entry(ctrl, self.vars["key_value"], 24)
        self.keyval_entry.pack(side="right")
        self.keyval_hint = tk.Label(k, text="", font=(UI_FONT, 8), anchor="w")
        self.keyval_hint.pack(anchor="w"); self._reg(self.keyval_hint, "faint")

        self._sep(k)

        ctrl = self._row(k, "Interval")
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["key_val_int"], 6),
            self._unit(ctrl, self.vars["key_unit"])])

        adv_k = self._disclosure(k, "Advanced", self.vars["adv_key_open"])
        ctrl = self._row(adv_k, "Randomize interval", "keeps the rhythm human")
        self._right_stack(ctrl, [
            self._pm(ctrl),
            self._entry(ctrl, self.vars["key_rand"], 5),
            self._unit_label(ctrl, "ms")])

        spacer = tk.Frame(body, height=18); spacer.pack(); self._reg(spacer, "bg")
        return page

    # ---- SETTINGS ------------------------------------------------------ #
    def _build_settings(self):
        page = tk.Frame(self.container); self._reg(page, "bg")
        body = self._make_scrollable(page)

        a = self._card(body, "Activation")
        ctrl = self._row(a, "Mode", "hold = runs only while the key is held")
        self._seg(ctrl, self.vars["activation"], ["Toggle", "Hold"],
                  command=self._sync_flags).pack(side="right")

        h = self._card(body, "Hotkeys")
        self.hk_master = self._hotkey_row(h, "Start / stop", "master")
        self.hk_panic = self._hotkey_row(h, "Panic stop", "panic")
        self._sep(h)
        ctrl = self._row(h, "Separate keys", "control mouse and keyboard apart")
        self._toggle(ctrl, self.vars["separate_hotkeys"], self._sync_flags).pack(side="right")
        self.hk_mouse = self._hotkey_row(h, "Mouse only", "mouse_hk")
        self.hk_key = self._hotkey_row(h, "Key only", "key_hk")

        s = self._card(body, "Limits")
        ctrl = self._row(s, "Stop after")
        self._seg(ctrl, self.vars["stop_mode"], ["Never", "Count", "Time"],
                  command=self._refresh_limit_ui).pack(side="right")
        ctrl = self._row(s, "Value")
        self.limit_row = ctrl.row
        self.limit_unit = tk.Label(ctrl, text="", font=(UI_FONT, 9))
        self.limit_unit.pack(side="right", padx=(6, 0)); self._reg(self.limit_unit, "muted")
        self.limit_entry_c = self._entry(ctrl, self.vars["stop_count"], 7)
        self.limit_entry_t = self._entry(ctrl, self.vars["stop_time"], 7)

        ctrl = self._row(s, "Countdown", "delay before it starts")
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["countdown"], 5),
            self._unit_label(ctrl, "s")])

        w = self._card(body, "Window")
        ctrl = self._row(w, "Always on top")
        self._toggle(ctrl, self.vars["always_top"], self._apply_always_top).pack(side="right")

        p = self._card(body, "Profiles")
        ctrl = self._row(p, "Saved setups", "your last setup is remembered automatically")
        self._right_stack(ctrl, [
            self._icon_pill(ctrl, "Save", self._save_profile),
            self._icon_pill(ctrl, "Load", self._load_profile)])

        st = self._card(body, "Stats")
        ctrl = self._row(st, "All-time actions")
        self.stat_lbl = tk.Label(ctrl, text="0", font=(UI_FONT, 12, "bold"))
        self._reg(self.stat_lbl, "title")
        self._right_stack(ctrl, [
            self.stat_lbl,
            self._icon_pill(ctrl, "Reset", self._reset_stats)])

        ab = self._card(body, "About")
        about = tk.Label(ab, justify="left", anchor="w", font=(UI_FONT, 9),
                         text="Auto clicker + key presser with humanization, macros,\n"
                              "profiles and global hotkeys.\n\n"
                              "Python · tkinter · pynput")
        about.pack(anchor="w"); self._reg(about, "muted")

        spacer = tk.Frame(body, height=18); spacer.pack(); self._reg(spacer, "bg")
        return page

    def _hotkey_row(self, parent, label, target):
        ctrl = self._row(parent, label)
        disp = tk.Label(ctrl, text=key_to_label(self._hk_of(target)),
                        font=(UI_FONT, 10, "bold"), width=7, padx=10, pady=5)
        self._reg(disp, "chip")
        self._right_stack(ctrl, [
            disp,
            self._icon_pill(ctrl, "Rebind", lambda: self._start_recording(target))])
        return disp

    def _hk_of(self, target):
        return {"master": self.master_hotkey, "panic": self.panic_hotkey,
                "mouse_hk": self.mouse_hotkey, "key_hk": self.key_hotkey}[target]

    # ---- control factories --------------------------------------------- #
    def _toggle(self, parent, var, command=None):
        t = Toggle(parent, var, command); self._custom.append(t); return t

    def _seg(self, parent, var, options, command=None):
        s = Segmented(parent, var, options, command); self._custom.append(s); return s

    def _entry(self, parent, var, width):
        e = tk.Entry(parent, textvariable=var, width=width, relief="flat", justify="center",
                     font=(UI_FONT, 10), highlightthickness=1, bd=6)
        self._reg(e, "field"); return e

    def _unit(self, parent, var):
        return self._seg(parent, var, ["ms", "sec", "min"])

    def _unit_label(self, parent, text):
        l = tk.Label(parent, text=text, font=(UI_FONT, 9)); self._reg(l, "muted"); return l

    def _pm(self, parent):
        """The '±' prefix. Left unpacked so callers control placement."""
        l = tk.Label(parent, text="±", font=(UI_FONT, 10))
        self._reg(l, "muted"); return l

    def _icon_pill(self, parent, text, command):
        b = tk.Label(parent, text=text, font=(UI_FONT, 9), cursor="hand2", padx=12, pady=5)
        b.bind("<Button-1>", lambda _e: command())
        self._reg(b, "soft"); return b

    # ---- conditional UI ------------------------------------------------- #
    def _refresh_target_ui(self):
        """Show the position controls that match the chosen target, in place."""
        mode = self.vars["target_mode"].get()
        self.pos_row.pack_forget()
        self.points_row.pack_forget()
        if mode == "Fixed":
            self.pos_row.pack(fill="x", pady=5, after=self.target_row)
        elif mode == "Multi":
            self.points_row.pack(fill="x", pady=5, after=self.target_row)
        self._refresh_points()

    def _refresh_key_ui(self):
        mode = self.vars["key_mode"].get()
        hints = {"Sequence": "space or comma separated  —  e.g.  q w e r",
                 "Combo": "join with +  —  e.g.  ctrl+shift+a",
                 "Text": "any words, typed out each time"}
        self.key_row.pack_forget()
        self.keyval_row.pack_forget()
        self.keyval_hint.pack_forget()
        # pack right below Mode, not at the end of the card
        if mode == "Key":
            self.key_row.pack(fill="x", pady=5, after=self.key_mode_row)
        else:
            self.keyval_row.pack(fill="x", pady=5, after=self.key_mode_row)
            self.keyval_hint.configure(text=hints.get(mode, ""))
            self.keyval_hint.pack(anchor="w", after=self.keyval_row)

    def _refresh_limit_ui(self):
        mode = self.vars["stop_mode"].get()
        self.limit_entry_c.pack_forget(); self.limit_entry_t.pack_forget()
        self.limit_row.pack_forget()
        if mode == "Never":
            return
        self.limit_row.pack(fill="x", pady=5)
        if mode == "Count":
            self.limit_entry_c.pack(side="right"); self.limit_unit.configure(text="actions")
        else:
            self.limit_entry_t.pack(side="right"); self.limit_unit.configure(text="seconds")

    # ---- theming -------------------------------------------------------- #
    def _reg(self, widget, role):
        self._themed.append((widget, role))

    def apply_theme(self):
        C = self.C
        self.root.configure(bg=C["bg"])
        for w, role in self._themed:
            try:
                self._apply_role(w, role, C)
            except tk.TclError:
                pass
        for w in self._custom:
            try:
                if isinstance(w, IconButton):
                    w.refresh_theme(C, is_dark=(self.theme_name == "dark"))
                else:
                    w.refresh_theme(C)
            except tk.TclError:
                pass
        # a flat, arrow-less scrollbar that blends into the page
        self.style.configure("App.Vertical.TScrollbar", troughcolor=C["bg"],
                             background=C["track"], bordercolor=C["bg"],
                             darkcolor=C["track"], lightcolor=C["track"],
                             relief="flat", borderwidth=0, arrowsize=0, width=8)
        self.style.map("App.Vertical.TScrollbar",
                       background=[("active", C["faint"]), ("!active", C["track"])])
        self._refresh_running_ui()

    def _apply_role(self, w, role, C):
        roles = {
            "bg": dict(bg=C["bg"]),
            "surface": dict(bg=C["surface"]),
            "border_fill": dict(bg=C["border"]),
            "card": dict(bg=C["surface"], highlightbackground=C["border"],
                         highlightcolor=C["border"]),
            "title": dict(bg=C["surface"], fg=C["text"]),
            "label": dict(bg=C["surface"], fg=C["text"]),
            "muted": dict(bg=C["surface"], fg=C["muted"]),
            "faint": dict(bg=C["surface"], fg=C["faint"]),
            "field": dict(bg=C["field"], fg=C["text"], insertbackground=C["text"],
                          highlightbackground=C["border"], highlightcolor=C["accent"],
                          disabledbackground=C["surface2"]),
            "chip": dict(bg=C["accent_soft"], fg=C["accent"]),
            "icon": dict(bg=C["surface"], fg=C["muted"]),
            "soft": dict(bg=C["surface2"], fg=C["text"]),
            "primary": dict(bg=C["accent"], fg=C["accent_fg"]),
        }
        if role in roles:
            w.configure(**roles[role])

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.C = THEMES[self.theme_name]
        self.apply_theme()

    def show_page(self, name):
        for p in self.pages.values():
            p.pack_forget()
        page = self.pages[name]
        page.pack(fill="both", expand=True)
        self.active_canvas = getattr(page, "canvas", None)
        for b, which in ((self.home_btn, "home"), (self.settings_btn, "settings")):
            b.active = (which == name)
            b.draw()

    def _apply_always_top(self):
        try:
            self.root.attributes("-topmost", bool(self.vars["always_top"].get()))
        except tk.TclError:
            pass

    def _sync_flags(self):
        self._hold_mode = self.vars["activation"].get() == "Hold"
        self._separate = bool(self.vars["separate_hotkeys"].get())

    # ---- listener / recording / picking --------------------------------- #
    def _start_global_listener(self):
        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.daemon = True
        self.listener.start()

    def _on_press(self, key):
        if self.recording_target:
            self._capture_key(key); return
        if key == self.panic_hotkey:
            self.root.after(0, self.stop_all); return
        if key == self.master_hotkey and not self._master_down:
            self._master_down = True
            if self._hold_mode:
                self.root.after(0, lambda: self.start_all(countdown=False))
            else:
                self.root.after(0, self.master_toggle)
            return
        if self._separate:
            if key == self.mouse_hotkey and not self._mouse_hk_down:
                self._mouse_hk_down = True
                self.root.after(0, lambda: self._toggle_one("mouse"))
            elif key == self.key_hotkey and not self._key_hk_down:
                self._key_hk_down = True
                self.root.after(0, lambda: self._toggle_one("key"))

    def _on_release(self, key):
        if key == self.master_hotkey:
            self._master_down = False
            if self._hold_mode:
                self.root.after(0, self.stop_all)
        elif key == self.mouse_hotkey:
            self._mouse_hk_down = False
        elif key == self.key_hotkey:
            self._key_hk_down = False

    def _capture_key(self, key):
        target = self.recording_target
        self.recording_target = None
        setattr(self, {"spam": "spam_key", "master": "master_hotkey", "panic": "panic_hotkey",
                       "mouse_hk": "mouse_hotkey", "key_hk": "key_hotkey"}[target], key)
        self.root.after(0, self._refresh_key_labels)

    def _start_recording(self, target):
        self.recording_target = target
        self.status_text.set("Press any key…")
        if target == "spam":
            self.key_display.configure(text="…")

    def _refresh_key_labels(self):
        self.key_display.configure(text=key_to_label(self.spam_key))
        for disp, t in ((self.hk_master, "master"), (self.hk_panic, "panic"),
                        (self.hk_mouse, "mouse_hk"), (self.hk_key, "key_hk")):
            disp.configure(text=key_to_label(self._hk_of(t)))
        self._refresh_running_ui()

    def _pick_point(self):
        self.status_text.set("Click anywhere on screen…")
        mode = self.vars["target_mode"].get()

        def on_click(x, y, button, pressed):
            if pressed:
                self.root.after(0, lambda: self._got_point(x, y, mode))
                return False
        ml = mouse.Listener(on_click=on_click); ml.daemon = True; ml.start()

    def _got_point(self, x, y, mode):
        x, y = int(x), int(y)
        if mode == "Multi":
            self.points.append((x, y))
        else:
            self.vars["fixed_x"].set(str(x)); self.vars["fixed_y"].set(str(y))
            self.points = [(x, y)]
        self._refresh_points()
        self.status_text.set(f"Saved ({x}, {y})")
        self.root.after(1200, self._refresh_running_ui)

    def _clear_points(self):
        self.points = []; self._refresh_points()

    def _refresh_points(self):
        txt = "  ".join(f"({x},{y})" for x, y in self.points) or "none yet"
        if len(txt) > 46:
            txt = f"{len(self.points)} points saved"
        self.points_lbl.configure(text=txt)

    # ---- numbers -------------------------------------------------------- #
    @staticmethod
    def _num(var, default=0.0):
        try:
            return float(var.get())
        except (ValueError, tk.TclError):
            return default

    def _interval_of(self, val_name, unit_name):
        mult = {"ms": 0.001, "sec": 1.0, "min": 60.0}.get(self.vars[unit_name].get(), 0.001)
        return max(self._num(self.vars[val_name]) * mult, 0.0)

    # ---- config snapshots ------------------------------------------------ #
    def _mouse_cfg(self):
        return dict(
            button={"Left": Button.left, "Right": Button.right,
                    "Middle": Button.middle}[self.vars["mouse_button"].get()],
            count=2 if self.vars["click_type"].get() == "Double" else 1,
            base=self._interval_of("click_val", "click_unit"),
            rand=self._num(self.vars["click_rand"]) / 1000.0,
            target_mode=self.vars["target_mode"].get(),
            fixed=(int(self._num(self.vars["fixed_x"])), int(self._num(self.vars["fixed_y"]))),
            points=list(self.points),
            smooth=bool(self.vars["smooth_move"].get()),
            jitter=int(self._num(self.vars["jitter_px"])) if self.vars["jitter_on"].get() else 0,
            hold_on=bool(self.vars["hold_rand_on"].get()),
            hold_min=self._num(self.vars["hold_min"]) / 1000.0,
            hold_max=self._num(self.vars["hold_max"]) / 1000.0,
            burst_on=bool(self.vars["burst_on"].get()),
            burst_n=max(int(self._num(self.vars["burst_n"])), 1),
            burst_pause=self._num(self.vars["burst_pause"]),
            **self._stop_cfg())

    def _key_cfg(self):
        return dict(
            mode=self.vars["key_mode"].get(),
            value=self.vars["key_value"].get(),
            single=self.spam_key,
            base=self._interval_of("key_val_int", "key_unit"),
            rand=self._num(self.vars["key_rand"]) / 1000.0,
            hold_on=bool(self.vars["hold_rand_on"].get()),
            hold_min=self._num(self.vars["hold_min"]) / 1000.0,
            hold_max=self._num(self.vars["hold_max"]) / 1000.0,
            **self._stop_cfg())

    def _stop_cfg(self):
        return dict(stop_mode=self.vars["stop_mode"].get(),
                    stop_count=max(int(self._num(self.vars["stop_count"])), 1),
                    stop_time=max(self._num(self.vars["stop_time"]), 0.1))

    # ---- start / stop ---------------------------------------------------- #
    def master_toggle(self):
        self.stop_all() if (self.mouse_active or self.key_active) else self.start_all()

    def start_all(self, countdown=True):
        want_mouse = bool(self.vars["mouse_enabled"].get())
        want_key = bool(self.vars["key_enabled"].get())
        if not want_mouse and not want_key:
            self.status_text.set("Turn on a feature first")
            self.root.after(1800, self._refresh_running_ui)
            return
        cd = int(self._num(self.vars["countdown"])) if countdown else 0
        self._countdown(cd, want_mouse, want_key) if cd > 0 else self._begin(want_mouse, want_key)

    def _countdown(self, n, want_mouse, want_key):
        if n <= 0:
            self._begin(want_mouse, want_key); return
        self.status_text.set(f"Starting in {n}…")
        self.root.after(1000, lambda: self._countdown(n - 1, want_mouse, want_key))

    def _begin(self, want_mouse, want_key):
        self.run_clicks = 0
        self._cps_last_count = 0
        self._cps_last_time = time.time()
        if want_mouse and not self.mouse_active:
            self.mouse_active = True
            self.click_thread = threading.Thread(target=self._click_loop,
                                                 args=(self._mouse_cfg(),), daemon=True)
            self.click_thread.start()
        if want_key and not self.key_active:
            self.key_active = True
            self.key_thread = threading.Thread(target=self._key_loop,
                                               args=(self._key_cfg(),), daemon=True)
            self.key_thread.start()
        self._refresh_running_ui()

    def _toggle_one(self, which):
        if which == "mouse":
            if self.mouse_active:
                self.mouse_active = False
            elif self.vars["mouse_enabled"].get():
                self._begin(True, False)
        else:
            if self.key_active:
                self.key_active = False
            elif self.vars["key_enabled"].get():
                self._begin(False, True)
        self._refresh_running_ui()

    def stop_all(self):
        self.mouse_active = False
        self.key_active = False
        self._refresh_running_ui()

    def _refresh_running_ui(self):
        running = self.mouse_active or self.key_active
        self.action_btn.configure(text="Stop" if running else "Start",
                                  bg=self.C["danger"] if running else self.C["accent"])
        self.status_text.set("Running" if running else "Ready")
        self.cps_lbl.configure(fg=self.C["success"] if running else self.C["muted"])
        try:
            self.status_lbl.configure(fg=self.C["success"] if running else self.C["text"])
        except tk.TclError:
            pass

    # ---- primitives ------------------------------------------------------ #
    def _sleep(self, seconds, check):
        end = time.time() + max(seconds, 0)
        while check() and time.time() < end:
            time.sleep(min(0.02, max(end - time.time(), 0)))

    def _move_to(self, x, y, smooth):
        if not smooth:
            self.mouse_ctl.position = (x, y); return
        sx, sy = self.mouse_ctl.position
        steps = max(int(math.hypot(x - sx, y - sy) / 40), 6)
        for i in range(1, steps + 1):
            t = i / steps
            ease = t * t * (3 - 2 * t)
            self.mouse_ctl.position = (sx + (x - sx) * ease + random.uniform(-1, 1),
                                       sy + (y - sy) * ease + random.uniform(-1, 1))
            time.sleep(0.005)

    def _hold_time(self, cfg):
        if cfg["hold_on"]:
            lo, hi = sorted((cfg["hold_min"], cfg["hold_max"]))
            return random.uniform(lo, hi)
        return 0.008

    def _rand_interval(self, cfg):
        iv = cfg["base"] + (random.uniform(-cfg["rand"], cfg["rand"]) if cfg["rand"] else 0)
        return max(iv, 0.001)

    def _reached_limit(self, cfg, done, start):
        if cfg["stop_mode"] == "Count" and done >= cfg["stop_count"]:
            return True
        if cfg["stop_mode"] == "Time" and (time.time() - start) >= cfg["stop_time"]:
            return True
        return False

    # ---- loops ----------------------------------------------------------- #
    def _click_loop(self, cfg):
        start = time.time(); done = 0; idx = 0; burst = 0
        while self.mouse_active:
            if cfg["target_mode"] == "Fixed":
                tx, ty = cfg["fixed"]; move = True
            elif cfg["target_mode"] == "Multi" and cfg["points"]:
                tx, ty = cfg["points"][idx % len(cfg["points"])]; idx += 1; move = True
            else:
                tx, ty = self.mouse_ctl.position; move = cfg["jitter"] > 0
            if cfg["jitter"]:
                tx += random.randint(-cfg["jitter"], cfg["jitter"])
                ty += random.randint(-cfg["jitter"], cfg["jitter"])
            if move:
                self._move_to(tx, ty, cfg["smooth"])
            hold = self._hold_time(cfg)
            for c in range(cfg["count"]):
                self.mouse_ctl.press(cfg["button"]); time.sleep(hold)
                self.mouse_ctl.release(cfg["button"])
                if c < cfg["count"] - 1:
                    time.sleep(0.03)
            done += 1; self.run_clicks += 1; self.total_clicks += 1
            if self._reached_limit(cfg, done, start):
                self.root.after(0, self._auto_finished); break
            if cfg["burst_on"]:
                burst += 1
                if burst >= cfg["burst_n"]:
                    burst = 0
                    self._sleep(cfg["burst_pause"], lambda: self.mouse_active)
                    continue
            self._sleep(self._rand_interval(cfg), lambda: self.mouse_active)

    def _key_loop(self, cfg):
        start = time.time(); done = 0
        seq = parse_sequence(cfg["value"]) if cfg["mode"] == "Sequence" else None
        combo = parse_combo(cfg["value"]) if cfg["mode"] == "Combo" else None
        while self.key_active:
            try:
                if cfg["mode"] == "Text":
                    if cfg["value"]:
                        self.kbd_ctl.type(cfg["value"])
                elif cfg["mode"] == "Sequence":
                    for k in (seq or []):
                        self._tap(k, cfg); time.sleep(0.01)
                elif cfg["mode"] == "Combo":
                    for k in (combo or []):
                        self.kbd_ctl.press(k); time.sleep(0.005)
                    for k in reversed(combo or []):
                        self.kbd_ctl.release(k)
                else:
                    self._tap(cfg["single"], cfg)
            except Exception:
                pass
            done += 1; self.run_clicks += 1; self.total_clicks += 1
            if self._reached_limit(cfg, done, start):
                self.root.after(0, self._auto_finished); break
            self._sleep(self._rand_interval(cfg), lambda: self.key_active)

    def _tap(self, key, cfg):
        self.kbd_ctl.press(key); time.sleep(self._hold_time(cfg)); self.kbd_ctl.release(key)

    def _auto_finished(self):
        if self.mouse_active or self.key_active:
            self.stop_all()
            self.status_text.set("Finished")
            self.root.after(2000, self._refresh_running_ui)

    # ---- ticker ---------------------------------------------------------- #
    def _tick_cps(self):
        now = time.time(); dt = now - self._cps_last_time
        cps = (self.run_clicks - self._cps_last_count) / dt if dt > 0 else 0
        self._cps_last_count = self.run_clicks; self._cps_last_time = now
        self.cps_var.set(f"{cps:.1f} CPS  ·  {self.total_clicks:,} total")
        if hasattr(self, "stat_lbl"):
            self.stat_lbl.configure(text=f"{self.total_clicks:,}")
        self.root.after(500, self._tick_cps)

    def _reset_stats(self):
        self.total_clicks = 0
        self.cps_var.set("0.0 CPS  ·  0 total")

    # ---- persistence ------------------------------------------------------ #
    def _collect(self):
        data = {n: v.get() for n, v in self.vars.items() if n != "status"}
        data["_points"] = self.points
        data["_total_clicks"] = self.total_clicks
        data["_keys"] = {"spam": key_to_str(self.spam_key), "master": key_to_str(self.master_hotkey),
                         "panic": key_to_str(self.panic_hotkey), "mouse": key_to_str(self.mouse_hotkey),
                         "key": key_to_str(self.key_hotkey)}
        data["_theme"] = self.theme_name
        return data

    def _apply(self, data):
        for n, v in self.vars.items():
            if n in data:
                try:
                    v.set(data[n])
                except tk.TclError:
                    pass
        self.points = [tuple(p) for p in data.get("_points", [])]
        self.total_clicks = int(data.get("_total_clicks", 0))
        ks = data.get("_keys", {})
        if ks:
            self.spam_key = key_from_str(ks.get("spam", "c:a"))
            self.master_hotkey = key_from_str(ks.get("master", "k:f6"))
            self.panic_hotkey = key_from_str(ks.get("panic", "k:f9"))
            self.mouse_hotkey = key_from_str(ks.get("mouse", "k:f7"))
            self.key_hotkey = key_from_str(ks.get("key", "k:f8"))
        self.theme_name = data.get("_theme", self.theme_name)
        self.C = THEMES[self.theme_name]
        self._sync_flags(); self._apply_always_top()
        self._refresh_points(); self._refresh_key_labels()
        self._refresh_target_ui(); self._refresh_key_ui(); self._refresh_limit_ui()
        self.apply_theme()

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self._apply(json.load(f))
            except Exception:
                pass
        self._sync_flags()
        self._refresh_target_ui(); self._refresh_key_ui(); self._refresh_limit_ui()

    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._collect(), f, indent=2)
        except Exception:
            pass

    def _save_profile(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("Profile", "*.json")],
                                            initialfile="my_profile.json")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._collect(), f, indent=2)
                self.status_text.set("Profile saved")
                self.root.after(1600, self._refresh_running_ui)
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Could not save:\n{e}")

    def _load_profile(self):
        path = filedialog.askopenfilename(filetypes=[("Profile", "*.json")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._apply(json.load(f))
                self.status_text.set("Profile loaded")
                self.root.after(1600, self._refresh_running_ui)
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Could not load:\n{e}")

    def _on_close(self):
        self.stop_all()
        self._save_config()
        self.root.destroy()


def main():
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
