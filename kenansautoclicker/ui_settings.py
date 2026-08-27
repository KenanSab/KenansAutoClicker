"""The Settings page: one hotkey up front, everything else behind a disclosure."""

import tkinter as tk

from .keys import key_to_label
from .theme import UI_FONT


class SettingsPage:
    """Builds the Settings page."""


    # ---- SETTINGS ------------------------------------------------------ #
    def _build_settings(self):
        page = tk.Frame(self.container); self._reg(page, "bg")
        body = self._make_scrollable(page)

        # Basic: the one hotkey everybody needs. The rest is opt-in.
        h = self._card(body, "Hotkey")
        self.hk_master = self._hotkey_row(h, "Start / stop", "master")

        self._sep(h)
        adv_h = self._disclosure(h, "More hotkeys", self.vars["adv_hotkeys_open"])
        self.hk_panic = self._hotkey_row(adv_h, "Panic stop", "panic")
        ctrl = self._row(adv_h, "Separate keys", "control mouse and keyboard apart")
        self._toggle(ctrl, self.vars["separate_hotkeys"], self._sync_flags).pack(side="right")
        self.hk_mouse = self._hotkey_row(adv_h, "Mouse only", "mouse_hk")
        self.hk_key = self._hotkey_row(adv_h, "Key only", "key_hk")

        b = self._card(body, "Behaviour")
        ctrl = self._row(b, "Activation", "hold = runs only while the key is held")
        self._seg(ctrl, self.vars["activation"], ["Toggle", "Hold"],
                  command=self._sync_flags).pack(side="right")

        self._sep(b)
        adv_b = self._disclosure(b, "More options", self.vars["adv_behav_open"])

        ctrl = self._row(adv_b, "Stop after")
        self._seg(ctrl, self.vars["stop_mode"], ["Never", "Count", "Time"],
                  command=self._refresh_limit_ui).pack(side="right")
        ctrl = self._row(adv_b, "Value")
        self.limit_row = ctrl.row
        self.limit_unit = tk.Label(ctrl, text="", font=(UI_FONT, 9))
        self.limit_unit.pack(side="right", padx=(6, 0)); self._reg(self.limit_unit, "muted")
        self.limit_entry_c = self._entry(ctrl, self.vars["stop_count"], 7)
        self.limit_entry_t = self._entry(ctrl, self.vars["stop_time"], 7)

        ctrl = self._row(adv_b, "Countdown", "delay before it starts")
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["countdown"], 5),
            self._unit_label(ctrl, "s")])

        ctrl = self._row(adv_b, "Always on top")
        self._toggle(ctrl, self.vars["always_top"], self._apply_always_top).pack(side="right")

        ctrl = self._row(adv_b, "Profiles", "your last setup is remembered automatically")
        self._right_stack(ctrl, [
            self._icon_pill(ctrl, "Save", self._save_profile),
            self._icon_pill(ctrl, "Load", self._load_profile)])

        ctrl = self._row(adv_b, "All-time actions")
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
