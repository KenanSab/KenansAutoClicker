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
        self.click_interval_row = ctrl.row
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["click_val"], 6),
            self._unit(ctrl, self.vars["click_unit"])])
        self.speed_hint = tk.Label(c, text="", font=(UI_FONT, 8), anchor="w",
                                   justify="left")
        self.speed_hint.pack(anchor="w"); self._reg(self.speed_hint, "warn_text")
        for name in ("click_val", "click_unit"):
            self.vars[name].trace_add("write", lambda *_: self._refresh_speed_hint())

        ctrl = self._row(c, "Button")
        self.click_button_row = ctrl.row
        self._seg(ctrl, self.vars["mouse_button"], ["Left", "Right", "Middle"]).pack(side="right")

        ctrl = self._row(c, "Action", "hold keeps it down, dwell clicks where you rest")
        self._seg(ctrl, self.vars["click_action"], ["Click", "Hold", "Dwell"],
                  command=self._refresh_action_ui).pack(side="right")

        ctrl = self._row(c, "Rest for", "how long before a dwell click fires")
        self.dwell_row = ctrl.row
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["dwell_secs"], 5),
            self._unit_label(ctrl, "sec, within"),
            self._entry(ctrl, self.vars["dwell_px"], 4),
            self._unit_label(ctrl, "px")])

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

        # saved coordinates silently break when the display changes, so say so
        self.point_warn = tk.Frame(adv, highlightthickness=1, bd=0)
        self._reg(self.point_warn, "warn_box")
        self.point_warn_lbl = tk.Label(self.point_warn, text="", font=(UI_FONT, 8),
                                       justify="left", anchor="w", wraplength=380)
        self.point_warn_lbl.pack(side="left", padx=10, pady=8)
        self._reg(self.point_warn_lbl, "warn_text")
        self.point_fix_btn = self._icon_pill(self.point_warn, "Rescale",
                                             self._rescale_points)

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

        self.key_sep = self._sep(k)
        adv_k = self._disclosure(k, "More options", self.vars["adv_key_open"])

        ctrl = self._row(adv_k, "Mode", "sequence, combo or typed text")
        self.key_mode_row = ctrl.row
        self._seg(ctrl, self.vars["key_mode"], ["Key", "Hold", "Sequence", "Combo", "Text"],
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

        # ============ SCROLL ============
        sc = self._card(body, "Auto Scroll", self.vars["scroll_enabled"])

        ctrl = self._row(sc, "Direction")
        self._seg(ctrl, self.vars["scroll_dir"], ["Up", "Down"]).pack(side="right")

        ctrl = self._row(sc, "Interval")
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["scroll_val"], 6),
            self._unit(ctrl, self.vars["scroll_unit"])])

        self._sep(sc)
        adv_s = self._disclosure(sc, "More options", self.vars["adv_scroll_open"])

        ctrl = self._row(adv_s, "Amount", "notches per scroll")
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["scroll_amount"], 4)])

        ctrl = self._row(adv_s, "Randomize interval", "keeps the rhythm human")
        self._right_stack(ctrl, [
            self._pm(ctrl),
            self._entry(ctrl, self.vars["scroll_rand"], 5),
            self._unit_label(ctrl, "ms")])

        # ============ MACRO ============
        mc = self._card(body, "Macro", self.vars["macro_enabled"])

        ctrl = self._row(mc, "Recording")
        self.macro_lbl = tk.Label(ctrl, text="nothing recorded yet", font=(UI_FONT, 9))
        self._reg(self.macro_lbl, "muted")
        self.macro_rec_btn = self._icon_pill(ctrl, "Record", self._toggle_recording)
        self._right_stack(ctrl, [self.macro_lbl, self.macro_rec_btn])

        self.macro_hint = tk.Label(mc, font=(UI_FONT, 8), anchor="w", justify="left",
                                   text="Recording starts after a countdown and stops "
                                        "on the record hotkey, so the click that starts "
                                        "it is not part of the macro.")
        self.macro_hint.pack(anchor="w"); self._reg(self.macro_hint, "faint")

        ctrl = self._row(mc, "Repeat", "0 means until you stop it")
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["macro_repeat"], 5),
            self._unit_label(ctrl, "times")])

        self._sep(mc)
        adv_m = self._disclosure(mc, "More options", self.vars["adv_macro_open"])

        ctrl = self._row(adv_m, "Speed", "2 plays it twice as fast")
        self._right_stack(ctrl, [
            self._entry(ctrl, self.vars["macro_speed"], 5),
            self._unit_label(ctrl, "x")])

        ctrl = self._row(adv_m, "Record movement", "smoother, but larger files")
        self._toggle(ctrl, self.vars["macro_moves"]).pack(side="right")

        ctrl = self._row(adv_m, "Macro file")
        self._right_stack(ctrl, [
            self._icon_pill(ctrl, "Save", self._save_macro),
            self._icon_pill(ctrl, "Load", self._load_macro)])

        spacer = tk.Frame(body, height=18); spacer.pack(); self._reg(spacer, "bg")
        return page


    # ---- conditional UI ------------------------------------------------- #
    def _refresh_point_warning(self):
        """Show or hide the display-change warning under the points."""
        if not hasattr(self, "point_warn"):
            return
        warning = self._point_warning()
        self.point_warn.pack_forget()
        self.point_fix_btn.pack_forget()
        if warning and self.vars["target_mode"].get() in ("Fixed", "Multi"):
            message, can_rescale = warning
            self.point_warn_lbl.configure(text=message)
            if can_rescale:
                self.point_fix_btn.pack(side="right", padx=(0, 10))
            self.point_warn.pack(fill="x", pady=(2, 6))

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

    def _refresh_action_ui(self):
        """Only Click uses an interval; only Dwell uses the rest settings."""
        action = self.vars["click_action"].get()
        self.click_interval_row.pack_forget()
        self.dwell_row.pack_forget()
        self.speed_hint.pack_forget()

        if action == "Click":
            self.click_interval_row.pack(fill="x", pady=5,
                                         before=self.click_button_row)
            self._refresh_speed_hint()
        elif action == "Dwell":
            self.dwell_row.pack(fill="x", pady=5)

    def _refresh_speed_hint(self):
        """Warn when the interval is faster than most software will register.

        A common complaint about auto clickers is that nothing happens at very
        high speeds, because the target application silently drops the extra
        clicks. Saying so is friendlier than letting people conclude the app is
        broken.
        """
        if not hasattr(self, "speed_hint"):
            return
        if self.vars["click_action"].get() != "Click":
            self.speed_hint.pack_forget()
            return
        secs = self._interval_of("click_val", "click_unit")
        if 0 < secs < 0.01:
            self.speed_hint.configure(
                text=f"About {1 / secs:.0f} clicks per second. Many apps and "
                     "games ignore clicks this fast.")
            self.speed_hint.pack(anchor="w", before=self.click_button_row)
        else:
            self.speed_hint.pack_forget()

    def _refresh_key_ui(self):
        """Rebuild the key rows for the chosen mode.

        The rows live in two different containers: the key chip and interval are
        basic controls on the card, while the value field sits in the advanced
        section. `before=`/`after=` only work between siblings, so each row is
        anchored against something in its own parent that is always packed.
        """
        mode = self.vars["key_mode"].get()
        hints = {"Sequence": "space or comma separated, e.g.  q w e r",
                 "Combo": "join with +, e.g.  ctrl+shift+a",
                 "Text": "any words, typed out each time"}
        holding = mode == "Hold"
        needs_value = mode not in ("Key", "Hold")

        for row in (self.key_row, self.keyval_row, self.key_interval_row):
            row.pack_forget()
        self.keyval_hint.pack_forget()

        # --- on the card, anchored to its divider ---
        if not needs_value:
            self.key_row.pack(fill="x", pady=5, before=self.key_sep)
        # holding a key down is continuous, so an interval means nothing
        if not holding:
            self.key_interval_row.pack(fill="x", pady=5, before=self.key_sep)

        # --- in the advanced section, anchored to the mode row ---
        if needs_value:
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
