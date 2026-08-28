"""Loading and saving: the remembered setup, and named profile files."""

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox

from .keys import key_from_str, key_to_str
from .theme import APP_NAME, THEMES

#: Where the remembered setup lives between runs.
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".kenans_autoclicker.json")


class Storage:
    """Config and profile persistence, mixed into the app."""


    # ---- persistence ------------------------------------------------------ #
    def _collect(self):
        data = {n: v.get() for n, v in self.vars.items() if n != "status"}
        data["_points"] = self.points
        data["_points_geometry"] = self.points_geometry
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
        geom = data.get("_points_geometry")
        self.points_geometry = list(geom) if isinstance(geom, (list, tuple)) and len(geom) == 2 else None
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
        self._refresh_action_ui()
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
        self._refresh_action_ui()

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
