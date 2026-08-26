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


# --------------------------------------------------------------------------- #
#  Theme palettes
# --------------------------------------------------------------------------- #
THEMES = {
    "dark": {
        "bg": "#0f1115", "surface": "#181b22", "surface2": "#20242e", "border": "#2a2f3a",
        "text": "#e6e9ef", "muted": "#9aa4b2", "accent": "#4f8cff", "accent_fg": "#ffffff",
        "success": "#37c871", "danger": "#ff5c5c", "field": "#12151b",
    },
    "light": {
        "bg": "#f4f6fb", "surface": "#ffffff", "surface2": "#eef1f7", "border": "#d9dee8",
        "text": "#1b1f27", "muted": "#5c6675", "accent": "#2f6bff", "accent_fg": "#ffffff",
        "success": "#1fa85a", "danger": "#e23b3b", "field": "#ffffff",
    },
}


# --------------------------------------------------------------------------- #
#  Key helpers: labels, string codec, and a parser for sequences / combos
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
    """Serialize a pynput key for JSON."""
    if isinstance(key, KeyCode):
        if key.char is not None:
            return "c:" + key.char
        return "v:" + str(key.vk)
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
    """'q w e r' or 'q,w,e,r' -> list of key objects (each tapped in order)."""
    raw = text.replace(",", " ").split()
    return [k for k in (parse_token(t) for t in raw) if k is not None]


def parse_combo(text):
    """'ctrl+shift+a' -> list of keys pressed together then released in reverse."""
    raw = text.replace(" ", "").split("+")
    return [k for k in (parse_token(t) for t in raw if t) if k is not None]


# --------------------------------------------------------------------------- #
#  Application
# --------------------------------------------------------------------------- #
class AutoClickerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme_name = "dark"
        self.C = THEMES[self.theme_name]

        # per-feature run flags (mouse and key run independently)
        self.mouse_active = False
        self.key_active = False
        self.click_thread = None
        self.key_thread = None

        # counters
        self.run_clicks = 0           # clicks since this run started (for CPS)
        self.total_clicks = 0         # all-time, persisted
        self._cps_last_count = 0
        self._cps_last_time = time.time()

        # recording / picking state
        self.recording_target = None  # 'spam' | 'master' | 'panic' | 'mouse_hk' | 'key_hk'
        self._point_pick = None       # 'fixed' | 'multi' while capturing a screen point

        # configurable keys (plain attrs, read from the listener thread)
        self.spam_key = KeyCode.from_char("a")
        self.master_hotkey = Key.f6
        self.panic_hotkey = Key.f9
        self.mouse_hotkey = Key.f7
        self.key_hotkey = Key.f8

        # mirrored plain flags (updated from Tk widgets, read in listener thread)
        self._hold_mode = False
        self._separate = False
        self._master_down = self._mouse_hk_down = self._key_hk_down = False

        self.points = []             # list of (x, y) for multi-point mode

        # controllers
        self.mouse_ctl = MouseController()
        self.kbd_ctl = KeyboardController()

        self._themed = []
        self.vars = {}               # name -> tk var (for save/load)

        self._build_ui()
        self._load_config()
        self._start_global_listener()
        self.apply_theme()
        self._tick_cps()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- tk var helpers ------------------------------------------------ #
    def _sv(self, name, default):
        v = tk.StringVar(value=default); self.vars[name] = v; return v

    def _bv(self, name, default):
        v = tk.BooleanVar(value=default); self.vars[name] = v; return v

    def _init_vars(self):
        # mouse
        self._bv("mouse_enabled", True)
        self._sv("click_h", "0"); self._sv("click_m", "0"); self._sv("click_s", "0"); self._sv("click_ms", "100")
        self._sv("click_rand", "0")
        self._sv("mouse_button", "Left"); self._sv("click_type", "Single")
        self._sv("target_mode", "Follow cursor")
        self._sv("fixed_x", "0"); self._sv("fixed_y", "0")
        self._bv("smooth_move", False)
        self._bv("jitter_on", False); self._sv("jitter_px", "3")
        self._bv("hold_rand_on", False); self._sv("hold_min", "10"); self._sv("hold_max", "40")
        self._bv("burst_on", False); self._sv("burst_n", "10"); self._sv("burst_pause", "1.0")
        # key
        self._bv("key_enabled", False)
        self._sv("key_mode", "Single key")
        self._sv("key_value", "")
        self._sv("key_h", "0"); self._sv("key_m", "0"); self._sv("key_s", "0"); self._sv("key_ms", "100")
        self._sv("key_rand", "0")
        # global / settings
        self._sv("activation", "toggle")           # toggle | hold
        self._bv("separate_hotkeys", False)
        self._sv("stop_mode", "none")              # none | count | time
        self._sv("stop_count", "100"); self._sv("stop_time", "10")
        self._sv("countdown", "0")
        self._bv("always_top", False)
        self.status_text = self._sv("status", "Idle")

    # ---- window / layout ---------------------------------------------- #
    def _build_ui(self):
        self.root.title(APP_NAME)
        self.root.geometry("620x780")
        self.root.minsize(560, 640)
        self._init_vars()
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        # top bar
        self.topbar = tk.Frame(self.root, height=58); self.topbar.pack(fill="x")
        self.topbar.pack_propagate(False); self._reg(self.topbar, "surface")
        self.title_lbl = tk.Label(self.topbar, text=f"  ⚡  {APP_NAME}",
                                  font=("Segoe UI", 14, "bold"), anchor="w")
        self.title_lbl.pack(side="left", padx=10); self._reg(self.title_lbl, "title")
        self.theme_btn = self._icon_button(self.topbar, "☾", self.toggle_theme)
        self.settings_btn = self._icon_button(self.topbar, "⚙", lambda: self.show_page("settings"))
        self.home_btn = self._icon_button(self.topbar, "⌂", lambda: self.show_page("home"))
        self.theme_btn.pack(side="right", padx=(2, 12))
        self.settings_btn.pack(side="right", padx=2)
        self.home_btn.pack(side="right", padx=2)

        # page container
        self.container = tk.Frame(self.root); self.container.pack(fill="both", expand=True)
        self._reg(self.container, "bg")
        self.pages = {"home": self._build_home(), "settings": self._build_settings()}
        self.show_page("home")

        # bottom action bar
        self.actionbar = tk.Frame(self.root, height=78); self.actionbar.pack(fill="x", side="bottom")
        self.actionbar.pack_propagate(False); self._reg(self.actionbar, "surface")
        left = tk.Frame(self.actionbar); left.pack(side="left", padx=16); self._reg(left, "surface")
        self.status_lbl = tk.Label(left, textvariable=self.status_text, font=("Segoe UI", 10), anchor="w")
        self.status_lbl.pack(anchor="w"); self._reg(self.status_lbl, "muted")
        self.cps_var = tk.StringVar(value="CPS: 0.0   •   Total: 0")
        self.cps_lbl = tk.Label(left, textvariable=self.cps_var, font=("Segoe UI", 9), anchor="w")
        self.cps_lbl.pack(anchor="w"); self._reg(self.cps_lbl, "muted")
        self.action_btn = tk.Button(self.actionbar, text="▶  Start  (F6)", font=("Segoe UI", 12, "bold"),
                                    relief="flat", cursor="hand2", command=self.master_toggle,
                                    bd=0, padx=24, pady=10)
        self.action_btn.pack(side="right", padx=16, pady=16); self._reg(self.action_btn, "primary")

    def _make_scrollable(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0, bd=0); self._reg(canvas, "bg")
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas); self._reg(inner, "bg")
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

        def _wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)) if e.delta else (-1 if e.num == 4 else 1), "units")
        canvas.bind_all("<MouseWheel>", _wheel)
        canvas.bind_all("<Button-4>", _wheel); canvas.bind_all("<Button-5>", _wheel)
        return inner

    # ---- HOME ---------------------------------------------------------- #
    def _build_home(self):
        page = tk.Frame(self.container); self._reg(page, "bg")
        body = self._make_scrollable(page)

        # ===== Auto Clicker =====
        _, c = self._card(body, "🖱  Auto Clicker")
        self._checkbox(c, "Enable mouse clicking", self.vars["mouse_enabled"]).grid(
            row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))
        self._interval_row(c, 1, "click_h", "click_m", "click_s", "click_ms", "click_rand")

        o = tk.Frame(c); self._reg(o, "surface"); o.grid(row=2, column=0, columnspan=6, sticky="w", pady=(10, 0))
        self._field_label(o, "Button").grid(row=0, column=0, padx=(0, 6))
        self._combo(o, self.vars["mouse_button"], ["Left", "Right", "Middle"], 8).grid(row=0, column=1, padx=(0, 16))
        self._field_label(o, "Type").grid(row=0, column=2, padx=(0, 6))
        self._combo(o, self.vars["click_type"], ["Single", "Double"], 8).grid(row=0, column=3)

        # target
        t = tk.Frame(c); self._reg(t, "surface"); t.grid(row=3, column=0, columnspan=6, sticky="w", pady=(10, 0))
        self._field_label(t, "Click at").grid(row=0, column=0, padx=(0, 6))
        self._combo(t, self.vars["target_mode"],
                    ["Follow cursor", "Fixed point", "Multi-point sequence"], 18).grid(row=0, column=1, padx=(0, 12))
        self._field_label(t, "X").grid(row=0, column=2, padx=(0, 4))
        self._entry(t, self.vars["fixed_x"], 6).grid(row=0, column=3, padx=(0, 6))
        self._field_label(t, "Y").grid(row=0, column=4, padx=(0, 4))
        self._entry(t, self.vars["fixed_y"], 6).grid(row=0, column=5, padx=(0, 8))
        self._soft_button(t, "🎯 Pick point", self._pick_point).grid(row=0, column=6)
        self._checkbox(t, "Move smoothly to target", self.vars["smooth_move"]).grid(
            row=1, column=0, columnspan=7, sticky="w", pady=(6, 0))

        pf = tk.Frame(c); self._reg(pf, "surface"); pf.grid(row=4, column=0, columnspan=6, sticky="w", pady=(6, 0))
        self._field_label(pf, "Points").grid(row=0, column=0, sticky="nw", padx=(0, 6))
        self.points_lbl = tk.Label(pf, text="(none)", font=("Segoe UI", 9), justify="left", anchor="w")
        self.points_lbl.grid(row=0, column=1, sticky="w"); self._reg(self.points_lbl, "muted")
        self._soft_button(pf, "Clear", self._clear_points).grid(row=0, column=2, padx=(10, 0))

        # jitter / hold / burst
        j = tk.Frame(c); self._reg(j, "surface"); j.grid(row=5, column=0, columnspan=6, sticky="w", pady=(10, 0))
        self._checkbox(j, "Jitter ±", self.vars["jitter_on"]).grid(row=0, column=0, sticky="w")
        self._entry(j, self.vars["jitter_px"], 5).grid(row=0, column=1, padx=(4, 2))
        self._field_label(j, "px").grid(row=0, column=2, padx=(0, 16))
        self._checkbox(j, "Random hold", self.vars["hold_rand_on"]).grid(row=0, column=3, sticky="w")
        self._entry(j, self.vars["hold_min"], 5).grid(row=0, column=4, padx=(4, 2))
        self._field_label(j, "–").grid(row=0, column=5)
        self._entry(j, self.vars["hold_max"], 5).grid(row=0, column=6, padx=(2, 2))
        self._field_label(j, "ms").grid(row=0, column=7)

        b = tk.Frame(c); self._reg(b, "surface"); b.grid(row=6, column=0, columnspan=6, sticky="w", pady=(8, 0))
        self._checkbox(b, "Burst mode:", self.vars["burst_on"]).grid(row=0, column=0, sticky="w")
        self._entry(b, self.vars["burst_n"], 5).grid(row=0, column=1, padx=(4, 2))
        self._field_label(b, "clicks, then pause").grid(row=0, column=2, padx=(0, 6))
        self._entry(b, self.vars["burst_pause"], 5).grid(row=0, column=3, padx=(0, 2))
        self._field_label(b, "s").grid(row=0, column=4)

        # ===== Auto Key Presser =====
        _, k = self._card(body, "⌨  Auto Key Presser")
        self._checkbox(k, "Enable key pressing", self.vars["key_enabled"]).grid(
            row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))
        m = tk.Frame(k); self._reg(m, "surface"); m.grid(row=1, column=0, columnspan=6, sticky="w")
        self._field_label(m, "Mode").grid(row=0, column=0, padx=(0, 6))
        self._combo(m, self.vars["key_mode"],
                    ["Single key", "Sequence", "Combo", "Type text"], 14).grid(row=0, column=1, padx=(0, 12))
        self.key_display = tk.Label(m, text=key_to_label(self.spam_key), font=("Segoe UI", 10, "bold"),
                                    width=8, padx=8, pady=4)
        self.key_display.grid(row=0, column=2, padx=(0, 8)); self._reg(self.key_display, "chip")
        self._soft_button(m, "Record", lambda: self._start_recording("spam")).grid(row=0, column=3)

        vrow = tk.Frame(k); self._reg(vrow, "surface"); vrow.grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))
        self.keyval_hint = self._field_label(vrow, "Sequence / combo / text")
        self.keyval_hint.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self._entry(vrow, self.vars["key_value"], 30).grid(row=0, column=1, sticky="w")
        hint = tk.Label(k, font=("Segoe UI", 8), justify="left", anchor="w",
                        text="Sequence: q w e r   •   Combo: ctrl+shift+a   •   Text: any words")
        hint.grid(row=3, column=0, columnspan=6, sticky="w", pady=(4, 0)); self._reg(hint, "muted")

        self._interval_row(k, 4, "key_h", "key_m", "key_s", "key_ms", "key_rand")
        return page

    # ---- SETTINGS ------------------------------------------------------ #
    def _build_settings(self):
        page = tk.Frame(self.container); self._reg(page, "bg")
        body = self._make_scrollable(page)

        _, a = self._card(body, "🎮  Activation")
        self._radio(a, "Toggle  (press hotkey to start, press again to stop)",
                    self.vars["activation"], "toggle", self._sync_flags).grid(row=0, column=0, sticky="w")
        self._radio(a, "Hold  (runs only while you hold the hotkey)",
                    self.vars["activation"], "hold", self._sync_flags).grid(row=1, column=0, sticky="w", pady=(4, 0))

        _, h = self._card(body, "🎯  Hotkeys")
        self.hk_master = self._hotkey_row(h, 0, "Start / Stop", "master")
        self.hk_panic = self._hotkey_row(h, 1, "Panic (stop now)", "panic")
        self._checkbox(h, "Use separate hotkeys for mouse and key", self.vars["separate_hotkeys"],
                       self._sync_flags).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 2))
        self.hk_mouse = self._hotkey_row(h, 3, "Mouse only", "mouse_hk")
        self.hk_key = self._hotkey_row(h, 4, "Key only", "key_hk")

        _, s = self._card(body, "⏱  Stop after / Countdown")
        self._radio(s, "Never stop (until I stop it)", self.vars["stop_mode"], "none").grid(row=0, column=0, columnspan=3, sticky="w")
        self._radio(s, "After", self.vars["stop_mode"], "count").grid(row=1, column=0, sticky="w")
        self._entry(s, self.vars["stop_count"], 7).grid(row=1, column=1, padx=6)
        self._field_label(s, "actions").grid(row=1, column=2, sticky="w")
        self._radio(s, "After", self.vars["stop_mode"], "time").grid(row=2, column=0, sticky="w")
        self._entry(s, self.vars["stop_time"], 7).grid(row=2, column=1, padx=6)
        self._field_label(s, "seconds").grid(row=2, column=2, sticky="w")
        cd = tk.Frame(s); self._reg(cd, "surface"); cd.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self._field_label(cd, "Start countdown").grid(row=0, column=0, padx=(0, 6))
        self._entry(cd, self.vars["countdown"], 5).grid(row=0, column=1)
        self._field_label(cd, "seconds").grid(row=0, column=2, padx=(6, 0))

        _, w = self._card(body, "🪟  Window & Profiles")
        self._checkbox(w, "Always on top", self.vars["always_top"], self._apply_always_top).grid(
            row=0, column=0, columnspan=3, sticky="w")
        self._soft_button(w, "💾 Save profile…", self._save_profile).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self._soft_button(w, "📂 Load profile…", self._load_profile).grid(row=1, column=1, sticky="w", padx=8, pady=(8, 0))
        note = tk.Label(w, font=("Segoe UI", 8), anchor="w",
                        text="Your last settings are also saved automatically on exit.")
        note.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0)); self._reg(note, "muted")

        _, st = self._card(body, "📊  Stats")
        self.stat_lbl = tk.Label(st, text="All-time clicks: 0", font=("Segoe UI", 10), anchor="w")
        self.stat_lbl.grid(row=0, column=0, sticky="w"); self._reg(self.stat_lbl, "muted")
        self._soft_button(st, "Reset", self._reset_stats).grid(row=0, column=1, padx=(12, 0))

        _, ab = self._card(body, "ℹ  About")
        about = tk.Label(ab, justify="left", anchor="w", font=("Segoe UI", 9),
                         text=(f"{APP_NAME}\nAuto clicker + key presser with humanization, macros,\n"
                               "profiles and global hotkeys.  Built with Python + tkinter + pynput."))
        about.grid(row=0, column=0, sticky="w"); self._reg(about, "muted")
        return page

    def _hotkey_row(self, parent, row, label, target):
        f = tk.Frame(parent); self._reg(f, "surface"); f.grid(row=row, column=0, columnspan=4, sticky="w", pady=2)
        self._field_label(f, label).grid(row=0, column=0, sticky="w", padx=(0, 8))
        disp = tk.Label(f, text=key_to_label(getattr(self, {
            "master": "master_hotkey", "panic": "panic_hotkey",
            "mouse_hk": "mouse_hotkey", "key_hk": "key_hotkey"}[target])),
            font=("Segoe UI", 10, "bold"), width=8, padx=8, pady=4)
        disp.grid(row=0, column=1, padx=(0, 8)); self._reg(disp, "chip")
        self._soft_button(f, "Rebind", lambda: self._start_recording(target)).grid(row=0, column=2)
        return disp

    # ---- small widget builders ---------------------------------------- #
    def _card(self, parent, title):
        outer = tk.Frame(parent, highlightthickness=1, bd=0); outer.pack(fill="x", padx=16, pady=(16, 0))
        self._reg(outer, "card")
        head = tk.Label(outer, text=title, font=("Segoe UI", 11, "bold"), anchor="w")
        head.pack(fill="x", padx=16, pady=(12, 4)); self._reg(head, "title")
        inner = tk.Frame(outer); inner.pack(fill="x", padx=16, pady=(4, 14)); self._reg(inner, "surface")
        return outer, inner

    def _interval_row(self, parent, row, hn, mn, sn, msn, randn):
        f = tk.Frame(parent); self._reg(f, "surface"); f.grid(row=row, column=0, columnspan=8, sticky="w")
        self._field_label(f, "Interval").grid(row=0, column=0, columnspan=10, sticky="w", pady=(0, 4))
        for i, (lab, name) in enumerate([("hours", hn), ("mins", mn), ("secs", sn), ("ms", msn)]):
            self._entry(f, self.vars[name], 5).grid(row=1, column=i * 2, padx=(0, 4))
            self._field_label(f, lab).grid(row=1, column=i * 2 + 1, padx=(0, 12))
        self._field_label(f, "randomize ±").grid(row=1, column=8, padx=(4, 4))
        self._entry(f, self.vars[randn], 5).grid(row=1, column=9)
        self._field_label(f, "ms").grid(row=1, column=10, padx=(4, 0))

    def _icon_button(self, parent, glyph, command):
        b = tk.Button(parent, text=glyph, command=command, relief="flat", bd=0, cursor="hand2",
                      font=("Segoe UI", 15), width=3, height=1); self._reg(b, "icon"); return b

    def _soft_button(self, parent, text, command):
        b = tk.Button(parent, text=text, command=command, relief="flat", bd=0, cursor="hand2",
                      font=("Segoe UI", 9), padx=10, pady=4); self._reg(b, "soft"); return b

    def _field_label(self, parent, text):
        l = tk.Label(parent, text=text, font=("Segoe UI", 9)); self._reg(l, "muted"); return l

    def _entry(self, parent, var, width):
        e = tk.Entry(parent, textvariable=var, width=width, relief="flat", justify="center",
                     font=("Segoe UI", 10), highlightthickness=1, bd=4); self._reg(e, "field"); return e

    def _combo(self, parent, var, values, width):
        c = ttk.Combobox(parent, textvariable=var, values=values, width=width, state="readonly",
                         font=("Segoe UI", 10)); return c

    def _checkbox(self, parent, text, var, command=None):
        c = tk.Checkbutton(parent, text=text, variable=var, font=("Segoe UI", 10), anchor="w",
                           relief="flat", bd=0, highlightthickness=0, cursor="hand2", command=command)
        self._reg(c, "check"); return c

    def _radio(self, parent, text, var, value, command=None):
        r = tk.Radiobutton(parent, text=text, variable=var, value=value, font=("Segoe UI", 10),
                           anchor="w", relief="flat", bd=0, highlightthickness=0, cursor="hand2", command=command)
        self._reg(r, "check"); return r

    # ---- theming ------------------------------------------------------- #
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
        self.style.configure("TCombobox", fieldbackground=C["field"], background=C["surface2"],
                             foreground=C["text"], arrowcolor=C["text"], bordercolor=C["border"], relief="flat")
        self.style.map("TCombobox", fieldbackground=[("readonly", C["field"])],
                      foreground=[("readonly", C["text"])])
        self.style.configure("TScrollbar", background=C["surface2"], troughcolor=C["bg"],
                             bordercolor=C["bg"], arrowcolor=C["muted"])
        self.theme_btn.configure(text="☀" if self.theme_name == "dark" else "☾")

    def _apply_role(self, w, role, C):
        r = {
            "bg": dict(bg=C["bg"]),
            "surface": dict(bg=C["surface"]),
            "surface2": dict(bg=C["surface2"]),
            "card": dict(bg=C["surface"], highlightbackground=C["border"], highlightcolor=C["border"]),
            "title": dict(bg=C["surface"], fg=C["text"]),
            "muted": dict(bg=C["surface"], fg=C["muted"]),
            "field": dict(bg=C["field"], fg=C["text"], insertbackground=C["text"],
                          highlightbackground=C["border"], highlightcolor=C["accent"]),
            "chip": dict(bg=C["surface2"], fg=C["accent"]),
            "check": dict(bg=C["surface"], fg=C["text"], activebackground=C["surface"],
                          activeforeground=C["text"], selectcolor=C["field"]),
            "icon": dict(bg=C["surface"], fg=C["muted"], activebackground=C["surface2"], activeforeground=C["accent"]),
            "soft": dict(bg=C["surface2"], fg=C["text"], activebackground=C["border"], activeforeground=C["text"]),
            "primary": dict(bg=C["accent"], fg=C["accent_fg"], activebackground=C["accent"], activeforeground=C["accent_fg"]),
        }.get(role)
        if r:
            w.configure(**r)

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.C = THEMES[self.theme_name]
        self.apply_theme()

    def show_page(self, name):
        for p in self.pages.values():
            p.pack_forget()
        self.pages[name].pack(fill="both", expand=True)

    def _apply_always_top(self):
        try:
            self.root.attributes("-topmost", bool(self.vars["always_top"].get()))
        except tk.TclError:
            pass

    def _sync_flags(self):
        self._hold_mode = self.vars["activation"].get() == "hold"
        self._separate = bool(self.vars["separate_hotkeys"].get())

    # ---- global listener, recording, point picking -------------------- #
    def _start_global_listener(self):
        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.daemon = True
        self.listener.start()

    def _on_press(self, key):
        if self.recording_target:
            self._capture_key(key)
            return
        if key == self.panic_hotkey:
            self.root.after(0, self.stop_all)
            return
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
        if target == "spam":
            self.spam_key = key
        elif target == "master":
            self.master_hotkey = key
        elif target == "panic":
            self.panic_hotkey = key
        elif target == "mouse_hk":
            self.mouse_hotkey = key
        elif target == "key_hk":
            self.key_hotkey = key
        self.root.after(0, self._refresh_key_labels)

    def _start_recording(self, target):
        self.recording_target = target
        self.status_text.set("Press a key…")
        if target == "spam":
            self.key_display.configure(text="…")

    def _refresh_key_labels(self):
        self.key_display.configure(text=key_to_label(self.spam_key))
        for disp, k in [(self.hk_master, self.master_hotkey), (self.hk_panic, self.panic_hotkey),
                        (self.hk_mouse, self.mouse_hotkey), (self.hk_key, self.key_hotkey)]:
            disp.configure(text=key_to_label(k))
        self.status_text.set("Idle" if not (self.mouse_active or self.key_active) else "Running…")
        self.action_btn.configure(text=f"▶  Start  ({key_to_label(self.master_hotkey)})"
                                  if not (self.mouse_active or self.key_active)
                                  else f"■  Stop  ({key_to_label(self.master_hotkey)})")

    def _pick_point(self):
        self.status_text.set("Click anywhere on screen to capture the point…")
        mode = self.vars["target_mode"].get()

        def on_click(x, y, button, pressed):
            if pressed:
                self.root.after(0, lambda: self._got_point(x, y, mode))
                return False  # stop listener after one click
        ml = mouse.Listener(on_click=on_click); ml.daemon = True; ml.start()

    def _got_point(self, x, y, mode):
        x, y = int(x), int(y)
        if mode == "Multi-point sequence":
            self.points.append((x, y))
        else:
            self.vars["fixed_x"].set(str(x)); self.vars["fixed_y"].set(str(y))
            self.points = [(x, y)] if mode == "Fixed point" else self.points
        self._refresh_points()
        self.status_text.set(f"Captured ({x}, {y})")

    def _clear_points(self):
        self.points = []; self._refresh_points()

    def _refresh_points(self):
        self.points_lbl.configure(text="  ".join(f"({x},{y})" for x, y in self.points) or "(none)")

    # ---- numeric helpers ---------------------------------------------- #
    @staticmethod
    def _num(var, default=0.0):
        try:
            return float(var.get())
        except (ValueError, tk.TclError):
            return default

    def _base_interval(self, hn, mn, sn, msn):
        return max(self._num(self.vars[hn]) * 3600 + self._num(self.vars[mn]) * 60 +
                   self._num(self.vars[sn]) + self._num(self.vars[msn]) / 1000.0, 0.0)

    # ---- config snapshots (read on main thread) ----------------------- #
    def _mouse_cfg(self):
        return dict(
            button={"Left": Button.left, "Right": Button.right, "Middle": Button.middle}[self.vars["mouse_button"].get()],
            count=2 if self.vars["click_type"].get() == "Double" else 1,
            base=self._base_interval("click_h", "click_m", "click_s", "click_ms"),
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
            base=self._base_interval("key_h", "key_m", "key_s", "key_ms"),
            rand=self._num(self.vars["key_rand"]) / 1000.0,
            hold_on=bool(self.vars["hold_rand_on"].get()),
            hold_min=self._num(self.vars["hold_min"]) / 1000.0,
            hold_max=self._num(self.vars["hold_max"]) / 1000.0,
            **self._stop_cfg())

    def _stop_cfg(self):
        return dict(stop_mode=self.vars["stop_mode"].get(),
                    stop_count=max(int(self._num(self.vars["stop_count"])), 1),
                    stop_time=max(self._num(self.vars["stop_time"]), 0.1))

    # ---- start / stop -------------------------------------------------- #
    def master_toggle(self):
        if self.mouse_active or self.key_active:
            self.stop_all()
        else:
            self.start_all()

    def start_all(self, countdown=True):
        want_mouse = bool(self.vars["mouse_enabled"].get())
        want_key = bool(self.vars["key_enabled"].get())
        if not want_mouse and not want_key:
            self.status_text.set("Enable the mouse or key feature first."); return
        cd = int(self._num(self.vars["countdown"])) if countdown else 0
        if cd > 0:
            self._countdown(cd, want_mouse, want_key)
        else:
            self._begin(want_mouse, want_key)

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
            self.click_thread = threading.Thread(target=self._click_loop, args=(self._mouse_cfg(),), daemon=True)
            self.click_thread.start()
        if want_key and not self.key_active:
            self.key_active = True
            self.key_thread = threading.Thread(target=self._key_loop, args=(self._key_cfg(),), daemon=True)
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
        self.action_btn.configure(
            text=f"{'■  Stop' if running else '▶  Start'}  ({key_to_label(self.master_hotkey)})",
            bg=self.C["danger"] if running else self.C["accent"],
            activebackground=self.C["danger"] if running else self.C["accent"])
        self.status_text.set("Running…" if running else "Idle")

    # ---- action primitives -------------------------------------------- #
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
            ease = t * t * (3 - 2 * t)  # smoothstep
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
        if cfg["stop_mode"] == "count" and done >= cfg["stop_count"]:
            return True
        if cfg["stop_mode"] == "time" and (time.time() - start) >= cfg["stop_time"]:
            return True
        return False

    # ---- loops (background threads) ----------------------------------- #
    def _click_loop(self, cfg):
        start = time.time(); done = 0; idx = 0; burst = 0
        while self.mouse_active:
            # resolve target + optional jitter
            if cfg["target_mode"] == "Fixed point":
                tx, ty = cfg["fixed"]; move = True
            elif cfg["target_mode"] == "Multi-point sequence" and cfg["points"]:
                tx, ty = cfg["points"][idx % len(cfg["points"])]; idx += 1; move = True
            else:
                tx, ty = self.mouse_ctl.position; move = cfg["jitter"] > 0
            if cfg["jitter"]:
                tx += random.randint(-cfg["jitter"], cfg["jitter"])
                ty += random.randint(-cfg["jitter"], cfg["jitter"])
            if move:
                self._move_to(tx, ty, cfg["smooth"])
            # click (respect single/double + hold time)
            hold = self._hold_time(cfg)
            for c in range(cfg["count"]):
                self.mouse_ctl.press(cfg["button"]); time.sleep(hold); self.mouse_ctl.release(cfg["button"])
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
                if cfg["mode"] == "Type text":
                    if cfg["value"]:
                        self.kbd_ctl.type(cfg["value"])
                elif cfg["mode"] == "Sequence":
                    for k in (seq or []):
                        self._tap(k, cfg); time.sleep(0.01)
                elif cfg["mode"] == "Combo":
                    for k in (combo or []):
                        self.kbd_ctl.press(k)
                        time.sleep(0.005)
                    for k in reversed(combo or []):
                        self.kbd_ctl.release(k)
                else:  # Single key
                    self._tap(cfg["single"], cfg)
            except Exception:
                pass
            done += 1
            if self._reached_limit(cfg, done, start):
                self.root.after(0, self._auto_finished); break
            self._sleep(self._rand_interval(cfg), lambda: self.key_active)

    def _tap(self, key, cfg):
        self.kbd_ctl.press(key); time.sleep(self._hold_time(cfg)); self.kbd_ctl.release(key)

    def _auto_finished(self):
        if self.mouse_active or self.key_active:
            self.stop_all()
            self.status_text.set("Finished (limit reached).")

    # ---- CPS / stats ticker ------------------------------------------- #
    def _tick_cps(self):
        now = time.time(); dt = now - self._cps_last_time
        cps = (self.run_clicks - self._cps_last_count) / dt if dt > 0 else 0
        self._cps_last_count = self.run_clicks; self._cps_last_time = now
        self.cps_var.set(f"CPS: {cps:4.1f}   •   Total: {self.total_clicks}")
        if hasattr(self, "stat_lbl"):
            self.stat_lbl.configure(text=f"All-time clicks: {self.total_clicks}")
        self.root.after(500, self._tick_cps)

    def _reset_stats(self):
        self.total_clicks = 0
        self.cps_var.set("CPS: 0.0   •   Total: 0")

    # ---- profiles / persistence --------------------------------------- #
    def _collect(self):
        data = {name: v.get() for name, v in self.vars.items() if name != "status"}
        data["_points"] = self.points
        data["_total_clicks"] = self.total_clicks
        data["_keys"] = {
            "spam": key_to_str(self.spam_key), "master": key_to_str(self.master_hotkey),
            "panic": key_to_str(self.panic_hotkey), "mouse": key_to_str(self.mouse_hotkey),
            "key": key_to_str(self.key_hotkey)}
        data["_theme"] = self.theme_name
        return data

    def _apply(self, data):
        for name, v in self.vars.items():
            if name in data:
                try:
                    v.set(data[name])
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
        self.theme_name = data.get("_theme", self.theme_name); self.C = THEMES[self.theme_name]
        self._sync_flags(); self._apply_always_top()
        self._refresh_points(); self._refresh_key_labels(); self.apply_theme()

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self._apply(json.load(f))
            except Exception:
                pass
        self._sync_flags()

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
                self.status_text.set("Profile saved.")
            except Exception as e:
                messagebox.showerror(APP_NAME, f"Could not save:\n{e}")

    def _load_profile(self):
        path = filedialog.askopenfilename(filetypes=[("Profile", "*.json")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._apply(json.load(f))
                self.status_text.set("Profile loaded.")
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
