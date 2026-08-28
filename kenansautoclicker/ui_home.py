"""The Home page: the two things people actually came for, plus opt-in extras."""

import tkinter as tk

from .keys import key_to_label
from .theme import UI_FONT


class HomePage:
    """Builds the Home page and the rows that appear conditionally."""


    # ---- HOME ---------------------------------------------------------- #
    def _build_home(self):
        page = tk.Frame(self.container); self._reg(page, "bg")
        body = self._make_scrollable(page)

        # ============ CLICKER ============
        # Only the two things every autoclicker needs are visible; everything
        # else — click type, targeting, coordinates, humanization — is opt-in.
        c = self._card(body, "Auto Clicker", self.vars["mouse_enabled"])

        ctrl = self._row(c, "Interval")
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["click_val"], 6),
            self._unit(ctrl, self.vars["click_unit"])])

        ctrl = self._row(c, "Button")
        self._seg(ctrl, self.vars["mouse_button"], ["Left", "Right", "Middle"]).pack(side="right")

        # ---- everything below is collapsed by default ----
        self._sep(c)
        adv = self._disclosure(c, "More options", self.vars["adv_click_open"])

        ctrl = self._row(adv, "Click")
        self._seg(ctrl, self.vars["click_type"], ["Single", "Double"]).pack(side="right")

        ctrl = self._row(adv, "Click at")
        self.target_row = ctrl.row
        self._seg(ctrl, self.vars["target_mode"], ["Cursor", "Fixed", "Multi"],
                  command=self._refresh_target_ui).pack(side="right")

        # --- Fixed point: pick + X/Y (packed under "Click at" on demand) ---
        ctrl = self._row(adv, "Position")
        self.pos_row = ctrl.row
        self._right_stack(ctrl, [
            self._icon_pill(ctrl, "Pick point", self._pick_point),
            self._entry(ctrl, self.vars["fixed_x"], 5),
            self._unit_label(ctrl, "x"),
            self._entry(ctrl, self.vars["fixed_y"], 5),
            self._unit_label(ctrl, "y")])

        # --- Multi point: add to a list ---
        ctrl = self._row(adv, "Points", "clicked in order, looping")
        self.points_row = ctrl.row
        self.points_lbl = tk.Label(ctrl, text="none yet", font=(UI_FONT, 9))
        self._reg(self.points_lbl, "muted")
        self._right_stack(ctrl, [
            self._icon_pill(ctrl, "Add point", self._pick_point),
            self.points_lbl,
            self._icon_pill(ctrl, "Clear", self._clear_points)])

        self._sub(adv, "Humanize")

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

        # Basic: which key, and how fast. Modes and randomization are opt-in.
        ctrl = self._row(k, "Key")
        self.key_row = ctrl.row
        self.key_display = tk.Label(ctrl, text=key_to_label(self.spam_key),
                                    font=(UI_FONT, 10, "bold"), width=7, padx=10, pady=5)
        self._reg(self.key_display, "chip")
        self._right_stack(ctrl, [
            self.key_display,
            self._icon_pill(ctrl, "Record", lambda: self._start_recording("spam"))])

        ctrl = self._row(k, "Interval")
        self.key_interval_row = ctrl.row
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["key_val_int"], 6),
            self._unit(ctrl, self.vars["key_unit"])])

        self._sep(k)
        adv_k = self._disclosure(k, "More options", self.vars["adv_key_open"])

        ctrl = self._row(adv_k, "Mode", "sequence, combo or typed text")
        self.key_mode_row = ctrl.row
        self._seg(ctrl, self.vars["key_mode"], ["Key", "Sequence", "Combo", "Text"],
                  command=self._refresh_key_ui).pack(side="right")

        ctrl = self._row(adv_k, "Value")
        self.keyval_row = ctrl.row
        self.keyval_entry = self._entry(ctrl, self.vars["key_value"], 24)
        self.keyval_entry.pack(side="right")
        self.keyval_hint = tk.Label(adv_k, text="", font=(UI_FONT, 8), anchor="w")
        self._reg(self.keyval_hint, "faint")

        ctrl = self._row(adv_k, "Randomize interval", "keeps the rhythm human")
        self._right_stack(ctrl, [
            self._pm(ctrl),
            self._entry(ctrl, self.vars["key_rand"], 5),
            self._unit_label(ctrl, "ms")])

        spacer = tk.Frame(body, height=18); spacer.pack(); self._reg(spacer, "bg")
        return page


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
        # `before`/`after` only work between siblings, and these two rows live in
        # different containers: the key chip is basic, the value field is advanced.
        if mode == "Key":
            self.key_row.pack(fill="x", pady=5, before=self.key_interval_row)
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
