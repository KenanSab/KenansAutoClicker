"""The application window: state, wiring, hotkeys and the run controls.

Layout, page content, the input engine and persistence each live in their own
module and are mixed in here, so this file stays about *coordination*.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk

from pynput import keyboard, mouse
from pynput.keyboard import Controller as KeyboardController, Key, KeyCode
from pynput.mouse import Controller as MouseController

from .engine import Engine
from .keys import key_to_label
from .storage import Storage
from .theme import APP_NAME, THEMES, UI_FONT
from .ui_base import UIBase
from .ui_home import HomePage
from .ui_presets import PresetsPage
from .ui_settings import SettingsPage
from .widgets import IconButton


class AutoClickerApp(UIBase, HomePage, SettingsPage, PresetsPage, Engine, Storage):
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

    # ---- tk variables --------------------------------------------------- #
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
        self._bv("adv_hotkeys_open", False)
        self._bv("adv_behav_open", False)
        # presets
        self._sv("preset_search", "")
        self._sv("preset_filter", "All")
        self.status_text = self._sv("status", "Ready")

    # ---- window shell ---------------------------------------------------- #
    def _build_ui(self):
        self.root.title(APP_NAME)
        # sized for the collapsed default view; expanding a section scrolls
        self.root.geometry("600x580")
        self.root.minsize(540, 420)
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
        self.title_lbl = tk.Label(brand, text=APP_NAME,
                                  font=(UI_FONT, 15, "bold"), anchor="w")
        self.title_lbl.pack(anchor="w"); self._reg(self.title_lbl, "title")

        icons = tk.Frame(self.topbar); icons.pack(side="right", padx=16)
        self._reg(icons, "surface")
        self.home_btn = IconButton(icons, "home", lambda: self.show_page("home"))
        self.presets_btn = IconButton(icons, "presets", lambda: self.show_page("presets"))
        self.settings_btn = IconButton(icons, "settings", lambda: self.show_page("settings"))
        self.theme_btn = IconButton(icons, "theme", self.toggle_theme)
        for b in (self.home_btn, self.presets_btn, self.settings_btn, self.theme_btn):
            b.pack(side="left", padx=4)
            self._custom.append(b)

        self.divider = tk.Frame(self.root, height=1); self.divider.pack(fill="x")
        self._reg(self.divider, "border_fill")

        # ---------- pages ----------
        self.container = tk.Frame(self.root); self.container.pack(fill="both", expand=True)
        self._reg(self.container, "bg")
        self.active_canvas = None
        self.pages = {
            "home": self._build_home(),
            "presets": self._build_presets(),
            "settings": self._build_settings(),
        }
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

    # ---- global listener, recording, point picking ----------------------- #
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

    # ---- start / stop ----------------------------------------------------- #
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
        # pages are built before the footer exists, and building a page can
        # trigger a theme pass, so this may run before there is a button
        if not hasattr(self, "action_btn"):
            return
        running = self.mouse_active or self.key_active
        self.action_btn.configure(text="Stop" if running else "Start",
                                  bg=self.C["danger"] if running else self.C["accent"])
        self.status_text.set("Running" if running else "Ready")
        self.cps_lbl.configure(fg=self.C["success"] if running else self.C["muted"])
        try:
            self.status_lbl.configure(fg=self.C["success"] if running else self.C["text"])
        except tk.TclError:
            pass

    def _auto_finished(self):
        if self.mouse_active or self.key_active:
            self.stop_all()
            self.status_text.set("Finished")
            self.root.after(2000, self._refresh_running_ui)

    # ---- counters --------------------------------------------------------- #
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


def main():
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()
