"""
Kenan's AutoClicker
===================
A fast, single-file auto-clicker + auto-key presser for Windows / macOS / Linux.

Features
--------
* Mouse auto-clicker: pick button (left / right / middle), single or double click,
  and a precise interval (hours / minutes / seconds / milliseconds).
* Auto-key presser: record ANY key and have it spammed at your chosen interval.
* Global hotkey (F6 by default) to start / stop from anywhere, even when the
  window is not focused. The hotkey is rebindable in Settings.
* Repeat "until stopped" or a fixed number of times.
* Clean UI with a Home page, a Settings page, and a light / dark theme toggle
  in the top-right corner.

Requirements
------------
Only one third-party dependency: pynput
    pip install pynput

Run it
------
    python KenansAutoClicker.py

Build a standalone app (single executable)
------------------------------------------
    pip install pynput pyinstaller

  Windows  ->  py -m PyInstaller --onefile --windowed --name "KenansAutoClicker" KenansAutoClicker.py
               result: dist\\KenansAutoClicker.exe
  macOS    ->  python3 -m PyInstaller --onefile --windowed --name "KenansAutoClicker" KenansAutoClicker.py
               result: dist/KenansAutoClicker
               (grant Accessibility permission in
                System Settings > Privacy & Security > Accessibility)

Everything below is standard-library tkinter + pynput. One file, no extras.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk

try:
    from pynput import mouse, keyboard
    from pynput.mouse import Button, Controller as MouseController
    from pynput.keyboard import Controller as KeyboardController, Key, KeyCode
except ImportError:  # pragma: no cover - friendly message if dependency missing
    raise SystemExit(
        "\nMissing dependency 'pynput'.\n"
        "Install it with:  pip install pynput\n"
    )


APP_NAME = "Kenan's AutoClicker"


# --------------------------------------------------------------------------- #
#  Theme palettes
# --------------------------------------------------------------------------- #
THEMES = {
    "dark": {
        "bg":        "#0f1115",
        "surface":   "#181b22",
        "surface2":  "#20242e",
        "border":    "#2a2f3a",
        "text":      "#e6e9ef",
        "muted":     "#9aa4b2",
        "accent":    "#4f8cff",
        "accent_fg": "#ffffff",
        "success":   "#37c871",
        "danger":    "#ff5c5c",
        "field":     "#12151b",
    },
    "light": {
        "bg":        "#f4f6fb",
        "surface":   "#ffffff",
        "surface2":  "#eef1f7",
        "border":    "#d9dee8",
        "text":      "#1b1f27",
        "muted":     "#5c6675",
        "accent":    "#2f6bff",
        "accent_fg": "#ffffff",
        "success":   "#1fa85a",
        "danger":    "#e23b3b",
        "field":     "#ffffff",
    },
}


# --------------------------------------------------------------------------- #
#  Key <-> label helpers
# --------------------------------------------------------------------------- #
def key_to_label(key):
    """Human-readable name for a pynput key object."""
    if key is None:
        return "None"
    if isinstance(key, KeyCode):
        if key.char is not None:
            return key.char.upper() if len(key.char) == 1 else repr(key.char)
        return f"<{key.vk}>"
    if isinstance(key, Key):
        return key.name.replace("_", " ").title()
    return str(key)


# --------------------------------------------------------------------------- #
#  Main application
# --------------------------------------------------------------------------- #
class AutoClickerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme_name = "dark"
        self.C = THEMES[self.theme_name]

        # engine state
        self.running = False
        self.click_thread = None
        self.key_thread = None

        # recording state (for capturing a key press)
        self.recording_target = None   # None | "spam" | "hotkey"

        # configurable keys
        self.hotkey = Key.f6
        self.spam_key = KeyCode.from_char("a")

        # controllers
        self.mouse_ctl = MouseController()
        self.kbd_ctl = KeyboardController()

        # widget registries so we can re-theme on the fly
        self._themed = []          # list of (widget, role) tuples
        self.cards = []

        self._build_ui()
        self._start_global_listener()
        self.apply_theme()

    # ------------------------------------------------------------------ #
    #  Tk variables
    # ------------------------------------------------------------------ #
    def _init_vars(self):
        # mouse
        self.mouse_enabled = tk.BooleanVar(value=True)
        self.click_h = tk.StringVar(value="0")
        self.click_m = tk.StringVar(value="0")
        self.click_s = tk.StringVar(value="0")
        self.click_ms = tk.StringVar(value="100")
        self.mouse_button = tk.StringVar(value="Left")
        self.click_type = tk.StringVar(value="Single")

        # key
        self.key_enabled = tk.BooleanVar(value=False)
        self.key_h = tk.StringVar(value="0")
        self.key_m = tk.StringVar(value="0")
        self.key_s = tk.StringVar(value="0")
        self.key_ms = tk.StringVar(value="100")

        # global
        self.repeat_mode = tk.StringVar(value="until")   # "until" | "count"
        self.repeat_count = tk.StringVar(value="10")
        self.status_text = tk.StringVar(value="Idle")

    # ------------------------------------------------------------------ #
    #  UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        self.root.title(APP_NAME)
        self.root.geometry("560x620")
        self.root.minsize(520, 600)

        self._init_vars()
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        # ----- top bar --------------------------------------------------
        self.topbar = tk.Frame(self.root, height=58)
        self.topbar.pack(fill="x", side="top")
        self.topbar.pack_propagate(False)
        self._reg(self.topbar, "surface")

        self.title_lbl = tk.Label(self.topbar, text=f"  ⚡  {APP_NAME}",
                                   font=("Segoe UI", 14, "bold"), anchor="w")
        self.title_lbl.pack(side="left", padx=10)
        self._reg(self.title_lbl, "title")

        # right-side icon buttons
        self.theme_btn = self._icon_button(self.topbar, "☾", self.toggle_theme)
        self.settings_btn = self._icon_button(self.topbar, "⚙", lambda: self.show_page("settings"))
        self.home_btn = self._icon_button(self.topbar, "⌂", lambda: self.show_page("home"))
        self.theme_btn.pack(side="right", padx=(2, 12))
        self.settings_btn.pack(side="right", padx=2)
        self.home_btn.pack(side="right", padx=2)

        # ----- container for pages -------------------------------------
        self.container = tk.Frame(self.root)
        self.container.pack(fill="both", expand=True)
        self._reg(self.container, "bg")

        self.pages = {}
        self.pages["home"] = self._build_home()
        self.pages["settings"] = self._build_settings()
        self.show_page("home")

        # ----- bottom action bar ---------------------------------------
        self.actionbar = tk.Frame(self.root, height=78)
        self.actionbar.pack(fill="x", side="bottom")
        self.actionbar.pack_propagate(False)
        self._reg(self.actionbar, "surface")

        self.status_lbl = tk.Label(self.actionbar, textvariable=self.status_text,
                                   font=("Segoe UI", 10))
        self.status_lbl.pack(side="left", padx=16)
        self._reg(self.status_lbl, "muted")

        self.action_btn = tk.Button(self.actionbar, text="▶  Start  (F6)",
                                    font=("Segoe UI", 12, "bold"),
                                    relief="flat", cursor="hand2",
                                    command=self.toggle, bd=0, padx=24, pady=10)
        self.action_btn.pack(side="right", padx=16, pady=16)
        self._reg(self.action_btn, "primary")

    def _build_home(self):
        page = tk.Frame(self.container)
        self._reg(page, "bg")

        # --- Mouse card ------------------------------------------------
        card, body = self._card(page, "🖱  Auto Clicker")
        self.mouse_chk = self._checkbox(body, "Enable mouse clicking", self.mouse_enabled)
        self.mouse_chk.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        self._interval_row(body, 1, self.click_h, self.click_m, self.click_s, self.click_ms)

        opt = tk.Frame(body); self._reg(opt, "surface")
        opt.grid(row=2, column=0, columnspan=4, sticky="w", pady=(12, 0))
        self._field_label(opt, "Button").grid(row=0, column=0, padx=(0, 8))
        self._combo(opt, self.mouse_button, ["Left", "Right", "Middle"], 8).grid(row=0, column=1, padx=(0, 20))
        self._field_label(opt, "Type").grid(row=0, column=2, padx=(0, 8))
        self._combo(opt, self.click_type, ["Single", "Double"], 8).grid(row=0, column=3)

        # --- Key card --------------------------------------------------
        card2, body2 = self._card(page, "⌨  Auto Key Presser")
        self.key_chk = self._checkbox(body2, "Enable key spamming", self.key_enabled)
        self.key_chk.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        keyrow = tk.Frame(body2); self._reg(keyrow, "surface")
        keyrow.grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 4))
        self._field_label(keyrow, "Key to spam").pack(side="left", padx=(0, 10))
        self.key_display = tk.Label(keyrow, text=key_to_label(self.spam_key),
                                    font=("Segoe UI", 10, "bold"), width=10,
                                    relief="flat", padx=10, pady=4)
        self.key_display.pack(side="left", padx=(0, 10))
        self._reg(self.key_display, "chip")
        self.record_btn = tk.Button(keyrow, text="Record key", relief="flat",
                                    cursor="hand2", bd=0, padx=12, pady=4,
                                    command=lambda: self._start_recording("spam"))
        self.record_btn.pack(side="left")
        self._reg(self.record_btn, "soft")

        self._interval_row(body2, 2, self.key_h, self.key_m, self.key_s, self.key_ms)

        return page

    def _build_settings(self):
        page = tk.Frame(self.container)
        self._reg(page, "bg")

        # --- Hotkey card ----------------------------------------------
        card, body = self._card(page, "🎯  Start / Stop Hotkey")
        row = tk.Frame(body); self._reg(row, "surface")
        row.grid(row=0, column=0, sticky="w")
        self._field_label(row, "Current hotkey").pack(side="left", padx=(0, 10))
        self.hotkey_display = tk.Label(row, text=key_to_label(self.hotkey),
                                       font=("Segoe UI", 10, "bold"), width=10,
                                       relief="flat", padx=10, pady=4)
        self.hotkey_display.pack(side="left", padx=(0, 10))
        self._reg(self.hotkey_display, "chip")
        self.hotkey_btn = tk.Button(row, text="Rebind", relief="flat", cursor="hand2",
                                    bd=0, padx=12, pady=4,
                                    command=lambda: self._start_recording("hotkey"))
        self.hotkey_btn.pack(side="left")
        self._reg(self.hotkey_btn, "soft")

        # --- Repeat card ----------------------------------------------
        card2, body2 = self._card(page, "🔁  Repeat")
        r1 = self._radio(body2, "Repeat until stopped", self.repeat_mode, "until")
        r1.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        r2 = self._radio(body2, "Repeat", self.repeat_mode, "count")
        r2.grid(row=1, column=0, sticky="w")
        self.count_entry = self._entry(body2, self.repeat_count, 6)
        self.count_entry.grid(row=1, column=1, padx=8)
        self._field_label(body2, "times").grid(row=1, column=2, sticky="w")

        # --- About card ------------------------------------------------
        card3, body3 = self._card(page, "ℹ  About")
        about = tk.Label(
            body3, justify="left", anchor="w",
            font=("Segoe UI", 9),
            text=(f"{APP_NAME}\n"
                  "A fast, no-nonsense auto clicker and key presser.\n"
                  "Press the global hotkey any time to start or stop —\n"
                  "even while another window is focused.\n\n"
                  "Built with Python + tkinter + pynput."),
        )
        about.grid(row=0, column=0, sticky="w")
        self._reg(about, "muted")

        return page

    # ------------------------------------------------------------------ #
    #  Reusable widget builders
    # ------------------------------------------------------------------ #
    def _card(self, parent, title):
        outer = tk.Frame(parent, highlightthickness=1, bd=0)
        outer.pack(fill="x", padx=16, pady=(16, 0))
        self._reg(outer, "card")
        self.cards.append(outer)

        head = tk.Label(outer, text=title, font=("Segoe UI", 11, "bold"), anchor="w")
        head.pack(fill="x", padx=16, pady=(12, 4))
        self._reg(head, "title")

        body = tk.Frame(outer)
        body.pack(fill="x", padx=16, pady=(4, 14))
        self._reg(body, "surface")
        return outer, body

    def _interval_row(self, parent, row, vh, vm, vs, vms):
        holder = tk.Frame(parent); self._reg(holder, "surface")
        holder.grid(row=row, column=0, columnspan=4, sticky="w")
        self._field_label(holder, "Interval").grid(row=0, column=0, sticky="w", pady=(0, 4), columnspan=8)
        specs = [("hours", vh), ("mins", vm), ("secs", vs), ("ms", vms)]
        for i, (name, var) in enumerate(specs):
            e = self._entry(holder, var, 5)
            e.grid(row=1, column=i * 2, padx=(0, 4))
            lab = self._field_label(holder, name)
            lab.grid(row=1, column=i * 2 + 1, padx=(0, 14))

    def _icon_button(self, parent, glyph, command):
        b = tk.Button(parent, text=glyph, command=command, relief="flat",
                      bd=0, cursor="hand2", font=("Segoe UI", 15),
                      width=3, height=1)
        self._reg(b, "icon")
        return b

    def _field_label(self, parent, text):
        lab = tk.Label(parent, text=text, font=("Segoe UI", 9))
        self._reg(lab, "muted")
        return lab

    def _entry(self, parent, var, width):
        e = tk.Entry(parent, textvariable=var, width=width, relief="flat",
                     justify="center", font=("Segoe UI", 10),
                     highlightthickness=1, bd=4)
        self._reg(e, "field")
        return e

    def _combo(self, parent, var, values, width):
        c = ttk.Combobox(parent, textvariable=var, values=values, width=width,
                         state="readonly", font=("Segoe UI", 10))
        self._reg(c, "combo")
        return c

    def _checkbox(self, parent, text, var):
        c = tk.Checkbutton(parent, text=text, variable=var, font=("Segoe UI", 10),
                           anchor="w", relief="flat", bd=0, highlightthickness=0,
                           cursor="hand2")
        self._reg(c, "check")
        return c

    def _radio(self, parent, text, var, value):
        r = tk.Radiobutton(parent, text=text, variable=var, value=value,
                           font=("Segoe UI", 10), anchor="w", relief="flat",
                           bd=0, highlightthickness=0, cursor="hand2")
        self._reg(r, "check")
        return r

    # ------------------------------------------------------------------ #
    #  Theming
    # ------------------------------------------------------------------ #
    def _reg(self, widget, role):
        self._themed.append((widget, role))

    def apply_theme(self):
        C = self.C
        self.root.configure(bg=C["bg"])
        for widget, role in self._themed:
            try:
                self._apply_role(widget, role, C)
            except tk.TclError:
                pass

        # ttk combobox styling
        self.style.configure("TCombobox",
                             fieldbackground=C["field"], background=C["surface2"],
                             foreground=C["text"], arrowcolor=C["text"],
                             bordercolor=C["border"], relief="flat")
        self.style.map("TCombobox",
                      fieldbackground=[("readonly", C["field"])],
                      foreground=[("readonly", C["text"])])
        self.theme_btn.configure(text="☀" if self.theme_name == "dark" else "☾")

    def _apply_role(self, w, role, C):
        if role == "bg":
            w.configure(bg=C["bg"])
        elif role == "surface":
            w.configure(bg=C["surface"])
        elif role == "surface2":
            w.configure(bg=C["surface2"])
        elif role == "card":
            w.configure(bg=C["surface"], highlightbackground=C["border"],
                        highlightcolor=C["border"])
        elif role == "title":
            w.configure(bg=C["surface"], fg=C["text"])
        elif role == "muted":
            w.configure(bg=C["surface"], fg=C["muted"])
        elif role == "field":
            w.configure(bg=C["field"], fg=C["text"], insertbackground=C["text"],
                        highlightbackground=C["border"], highlightcolor=C["accent"])
        elif role == "chip":
            w.configure(bg=C["surface2"], fg=C["accent"])
        elif role == "check":
            w.configure(bg=C["surface"], fg=C["text"], activebackground=C["surface"],
                        activeforeground=C["text"], selectcolor=C["field"])
        elif role == "icon":
            w.configure(bg=C["surface"], fg=C["muted"], activebackground=C["surface2"],
                        activeforeground=C["accent"])
        elif role == "soft":
            w.configure(bg=C["surface2"], fg=C["text"], activebackground=C["border"],
                        activeforeground=C["text"])
        elif role == "primary":
            w.configure(bg=C["accent"], fg=C["accent_fg"],
                        activebackground=C["accent"], activeforeground=C["accent_fg"])
        elif role == "combo":
            pass  # handled by ttk style

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.C = THEMES[self.theme_name]
        self.apply_theme()

    def show_page(self, name):
        for p in self.pages.values():
            p.pack_forget()
        self.pages[name].pack(fill="both", expand=True)

    # ------------------------------------------------------------------ #
    #  Key recording + global hotkey listener
    # ------------------------------------------------------------------ #
    def _start_global_listener(self):
        self.listener = keyboard.Listener(on_press=self._on_global_key)
        self.listener.daemon = True
        self.listener.start()

    def _on_global_key(self, key):
        # capture mode?
        if self.recording_target == "spam":
            self.spam_key = key
            self.recording_target = None
            self.root.after(0, self._finish_record_spam)
            return
        if self.recording_target == "hotkey":
            self.hotkey = key
            self.recording_target = None
            self.root.after(0, self._finish_record_hotkey)
            return
        # normal hotkey handling
        if key == self.hotkey:
            self.root.after(0, self.toggle)

    def _start_recording(self, target):
        self.recording_target = target
        if target == "spam":
            self.record_btn.configure(text="Press a key…")
            self.key_display.configure(text="…")
        else:
            self.hotkey_btn.configure(text="Press a key…")
            self.hotkey_display.configure(text="…")

    def _finish_record_spam(self):
        self.key_display.configure(text=key_to_label(self.spam_key))
        self.record_btn.configure(text="Record key")

    def _finish_record_hotkey(self):
        self.hotkey_display.configure(text=key_to_label(self.hotkey))
        self.hotkey_btn.configure(text="Rebind")

    # ------------------------------------------------------------------ #
    #  Engine: start / stop
    # ------------------------------------------------------------------ #
    def _interval_seconds(self, vh, vm, vs, vms):
        def num(v):
            try:
                return float(v.get() or 0)
            except ValueError:
                return 0.0
        secs = num(vh) * 3600 + num(vm) * 60 + num(vs) + num(vms) / 1000.0
        return max(secs, 0.001)  # never a zero-length busy loop

    def _repeat_limit(self):
        if self.repeat_mode.get() == "until":
            return None
        try:
            n = int(float(self.repeat_count.get()))
            return max(n, 1)
        except ValueError:
            return None

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self):
        if self.running:
            return
        if not self.mouse_enabled.get() and not self.key_enabled.get():
            self.status_text.set("Enable the mouse or key feature first.")
            return

        self.running = True
        limit = self._repeat_limit()
        self.action_btn.configure(text="■  Stop  (F6)", bg=self.C["danger"],
                                  activebackground=self.C["danger"])
        self.status_text.set("Running…")

        if self.mouse_enabled.get():
            self.click_thread = threading.Thread(
                target=self._click_loop, args=(limit,), daemon=True)
            self.click_thread.start()
        if self.key_enabled.get():
            self.key_thread = threading.Thread(
                target=self._key_loop, args=(limit,), daemon=True)
            self.key_thread.start()

    def stop(self):
        self.running = False
        self.action_btn.configure(text="▶  Start  (F6)", bg=self.C["accent"],
                                  activebackground=self.C["accent"])
        self.status_text.set("Idle")

    # ------------------------------------------------------------------ #
    #  Engine loops (run on background threads)
    # ------------------------------------------------------------------ #
    def _click_loop(self, limit):
        button_map = {"Left": Button.left, "Right": Button.right, "Middle": Button.middle}
        button = button_map.get(self.mouse_button.get(), Button.left)
        count = 2 if self.click_type.get() == "Double" else 1
        interval = self._interval_seconds(self.click_h, self.click_m, self.click_s, self.click_ms)

        done = 0
        while self.running:
            self.mouse_ctl.click(button, count)
            done += 1
            if limit is not None and done >= limit:
                self.root.after(0, self._auto_finished)
                break
            self._sleep(interval)

    def _key_loop(self, limit):
        interval = self._interval_seconds(self.key_h, self.key_m, self.key_s, self.key_ms)
        key = self.spam_key
        done = 0
        while self.running:
            try:
                self.kbd_ctl.press(key)
                self.kbd_ctl.release(key)
            except Exception:
                pass
            done += 1
            if limit is not None and done >= limit:
                self.root.after(0, self._auto_finished)
                break
            self._sleep(interval)

    def _sleep(self, interval):
        """Sleep in small slices so Stop is responsive on long intervals."""
        end = time.time() + interval
        while self.running and time.time() < end:
            time.sleep(min(0.02, end - time.time()))

    def _auto_finished(self):
        if self.running:
            self.stop()
            self.status_text.set("Finished (repeat count reached).")


def main():
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
