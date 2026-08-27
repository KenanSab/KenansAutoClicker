"""The Presets page: browse, preview, apply, export and share setups.

A preset only ever describes *how clicking and typing behave*. Applying one
shows exactly what will change first, and can never alter your hotkeys, theme
or window preferences — see `presets.PRESET_ALLOWED_KEYS`.
"""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from .presets import (BUILTIN_PRESETS, RISK_NOTE, clean_preset,
                      export_preset, fetch_community, load_local_presets,
                      save_local_preset)
from .theme import UI_FONT
from .widgets import StaticIcon, draw_icon


class PresetsPage:
    """Builds the Presets page and the preview dialog."""

    # ---- page ----------------------------------------------------------- #
    def _build_presets(self):
        page = tk.Frame(self.container); self._reg(page, "bg")
        body = self._make_scrollable(page)

        card = self._card(body, "Presets")
        intro = tk.Label(card, justify="left", anchor="w", font=(UI_FONT, 9),
                         text="Ready-made setups. Preview shows exactly what "
                              "changes before anything is applied.")
        intro.pack(anchor="w", pady=(0, 10)); self._reg(intro, "muted")

        row = tk.Frame(card); row.pack(fill="x"); self._reg(row, "surface")
        self._field_search(row)

        filt = tk.Frame(card); filt.pack(fill="x", pady=(10, 0))
        self._reg(filt, "surface")
        self._seg(filt, self.vars["preset_filter"],
                  ["All", "Accessibility", "Productivity", "Testing", "Mine"],
                  command=self._render_presets).pack(side="left")

        act = tk.Frame(card); act.pack(fill="x", pady=(12, 0))
        self._reg(act, "surface")
        self._icon_pill(act, "Browse community", self._browse_community).pack(side="left")
        self._icon_pill(act, "Save current as preset",
                        self._export_current).pack(side="left", padx=(8, 0))
        self._icon_pill(act, "Import file", self._import_preset).pack(side="left", padx=(8, 0))

        self.preset_status = tk.Label(card, text="", font=(UI_FONT, 9), anchor="w")
        self.preset_status.pack(anchor="w", pady=(10, 0)); self._reg(self.preset_status, "muted")

        # the list itself lives in its own frame so it can be re-rendered
        self.preset_list = tk.Frame(body); self.preset_list.pack(fill="x")
        self._reg(self.preset_list, "bg")

        self.community_presets = []
        self.local_presets = load_local_presets()
        self._render_presets()

        spacer = tk.Frame(body, height=18); spacer.pack(); self._reg(spacer, "bg")
        return page

    def _field_search(self, parent):
        wrap = tk.Frame(parent, highlightthickness=1, bd=0)
        wrap.pack(fill="x"); self._reg(wrap, "search")
        ico = StaticIcon(wrap, "search", 16, role="faint")
        ico.pack(side="left", padx=(10, 6), pady=8)
        self._custom.append(ico)
        e = tk.Entry(wrap, textvariable=self.vars["preset_search"], relief="flat",
                     font=(UI_FONT, 10), highlightthickness=0, bd=0)
        e.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=8)
        self._reg(e, "search_entry")
        self.vars["preset_search"].trace_add("write", lambda *_: self._render_presets())

    # ---- list rendering -------------------------------------------------- #
    def _all_presets(self):
        out = [dict(p, source="builtin") for p in BUILTIN_PRESETS]
        out += [dict(p, source="mine") for p in self.local_presets]
        out += self.community_presets
        return out

    def _visible_presets(self):
        term = self.vars["preset_search"].get().strip().lower()
        want = self.vars["preset_filter"].get()
        shown = []
        for p in self._all_presets():
            if want == "Mine" and p.get("source") != "mine":
                continue
            if want not in ("All", "Mine") and p.get("category") != want:
                continue
            if term:
                hay = " ".join([p.get("name", ""), p.get("description", ""),
                                p.get("category", ""), p.get("author", ""),
                                " ".join(p.get("tags", []))]).lower()
                if term not in hay:
                    continue
            shown.append(p)
        return shown

    def _render_presets(self):
        for w in self.preset_list.winfo_children():
            w.destroy()
        shown = self._visible_presets()
        if not shown:
            empty = tk.Label(self.preset_list, text="Nothing matches that search.",
                             font=(UI_FONT, 9))
            empty.pack(anchor="w", padx=34, pady=14); self._reg(empty, "muted")
            self.apply_theme()
            return
        for p in shown:
            self._preset_card(p)
        self.apply_theme()

    def _preset_card(self, p):
        C = self.C
        outer = tk.Frame(self.preset_list, highlightthickness=1, bd=0)
        outer.pack(fill="x", padx=18, pady=(12, 0))
        self._reg(outer, "card")

        head = tk.Frame(outer); head.pack(fill="x", padx=16, pady=(13, 0))
        self._reg(head, "surface")
        name = tk.Label(head, text=p.get("name", "Untitled"),
                        font=(UI_FONT, 11, "bold"), anchor="w")
        name.pack(side="left"); self._reg(name, "title")

        badge = tk.Label(head, text=p.get("category", "Community").upper(),
                         font=(UI_FONT, 7, "bold"), padx=7, pady=2)
        badge.pack(side="left", padx=(10, 0)); self._reg(badge, "chip")

        self._icon_pill(head, "Preview", lambda q=p: self._preview_preset(q)).pack(side="right")

        desc = tk.Label(outer, text=p.get("description", ""), font=(UI_FONT, 9),
                        anchor="w", justify="left", wraplength=470)
        desc.pack(fill="x", padx=16, pady=(6, 0)); self._reg(desc, "muted")

        meta = tk.Frame(outer); meta.pack(fill="x", padx=16, pady=(8, 13))
        self._reg(meta, "surface")
        by = tk.Label(meta, text="by " + p.get("author", "unknown"), font=(UI_FONT, 8))
        by.pack(side="left"); self._reg(by, "faint")
        tags = p.get("tags", [])
        if tags:
            t = tk.Label(meta, text="  ·  " + "  ".join(tags), font=(UI_FONT, 8))
            t.pack(side="left"); self._reg(t, "faint")

        if p.get("risky"):
            warn = tk.Frame(outer, highlightthickness=1, bd=0)
            warn.pack(fill="x", padx=16, pady=(0, 13))
            self._reg(warn, "warn_box")
            ico = tk.Canvas(warn, width=16, height=16, highlightthickness=0, bd=0)
            ico.pack(side="left", padx=(10, 8), pady=9)
            ico.configure(bg=C["warn_bg"])
            draw_icon(ico, "alert", 16, C["warn_fg"], stroke=2.0)
            msg = tk.Label(warn, text=RISK_NOTE, font=(UI_FONT, 8), justify="left",
                           anchor="w", wraplength=430)
            msg.pack(side="left", pady=8, padx=(0, 10)); self._reg(msg, "warn_text")

    # ---- preview + apply -------------------------------------------------- #
    #: How each stored value should read in the preview, so the dialog says
    #: "Mouse button: Left -> Right" rather than showing raw variable names.
    FRIENDLY = {
        "mouse_enabled": "Auto clicker", "key_enabled": "Auto key presser",
        "click_val": "Click interval", "click_unit": "Click interval unit",
        "click_rand": "Click randomise (ms)", "mouse_button": "Mouse button",
        "click_type": "Click type", "target_mode": "Click at",
        "fixed_x": "Fixed X", "fixed_y": "Fixed Y", "smooth_move": "Move smoothly",
        "jitter_on": "Jitter", "jitter_px": "Jitter (px)",
        "hold_rand_on": "Random hold", "hold_min": "Hold min (ms)",
        "hold_max": "Hold max (ms)", "burst_on": "Burst mode",
        "burst_n": "Burst size", "burst_pause": "Burst pause (s)",
        "key_mode": "Key mode", "key_value": "Key value",
        "key_val_int": "Key interval", "key_unit": "Key interval unit",
        "key_rand": "Key randomise (ms)", "stop_mode": "Stop after",
        "stop_count": "Stop count", "stop_time": "Stop time (s)",
        "countdown": "Countdown (s)",
    }

    @staticmethod
    def _show(val):
        if isinstance(val, bool):
            return "on" if val else "off"
        return str(val) if str(val) != "" else "(empty)"

    def _diff_for(self, preset):
        """What would actually change, as (label, current, new) rows."""
        rows = []
        for key, new in preset.get("settings", {}).items():
            var = self.vars.get(key)
            if var is None:
                continue
            cur = var.get()
            if isinstance(cur, bool):
                new_cast = bool(new) if isinstance(new, bool) else str(new).lower() in ("1", "true", "yes", "on")
            else:
                new_cast = str(new)
            if cur == new_cast:
                continue
            rows.append((self.FRIENDLY.get(key, key), self._show(cur), self._show(new_cast), key, new_cast))
        return rows

    def _preview_preset(self, preset):
        rows = self._diff_for(preset)
        C = self.C
        win = tk.Toplevel(self.root)
        win.title("Apply preset")
        win.configure(bg=C["bg"])
        win.transient(self.root)
        win.geometry("480x460")
        win.grab_set()

        head = tk.Frame(win, bg=C["surface"], height=64); head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text=preset.get("name", "Preset"), font=(UI_FONT, 13, "bold"),
                 bg=C["surface"], fg=C["text"]).pack(anchor="w", padx=20, pady=(12, 0))
        tk.Label(head, text="by " + preset.get("author", "unknown"), font=(UI_FONT, 8),
                 bg=C["surface"], fg=C["faint"]).pack(anchor="w", padx=20)

        if preset.get("risky"):
            wb = tk.Frame(win, bg=C["warn_bg"])
            wb.pack(fill="x")
            tk.Label(wb, text=RISK_NOTE, font=(UI_FONT, 8), bg=C["warn_bg"],
                     fg=C["warn_fg"], wraplength=440, justify="left",
                     anchor="w").pack(anchor="w", padx=16, pady=10)

        mid = tk.Frame(win, bg=C["bg"]); mid.pack(fill="both", expand=True, padx=20, pady=14)
        if not rows:
            tk.Label(mid, text="Your current settings already match this preset.",
                     font=(UI_FONT, 10), bg=C["bg"], fg=C["muted"]).pack(anchor="w")
        else:
            tk.Label(mid, text=f"This will change {len(rows)} setting"
                              f"{'s' if len(rows) != 1 else ''}:",
                     font=(UI_FONT, 9, "bold"), bg=C["bg"], fg=C["text"]).pack(anchor="w")
            box = tk.Frame(mid, bg=C["surface"], highlightthickness=1,
                           highlightbackground=C["border"])
            box.pack(fill="both", expand=True, pady=(8, 0))
            inner = tk.Frame(box, bg=C["surface"]); inner.pack(fill="both", expand=True,
                                                              padx=14, pady=12)
            for label, cur, new, _k, _v in rows[:14]:
                r = tk.Frame(inner, bg=C["surface"]); r.pack(fill="x", pady=2)
                tk.Label(r, text=label, font=(UI_FONT, 9), bg=C["surface"],
                         fg=C["text"], anchor="w", width=22).pack(side="left")
                tk.Label(r, text=cur, font=(UI_FONT, 9), bg=C["surface"],
                         fg=C["faint"]).pack(side="left")
                tk.Label(r, text="  →  ", font=(UI_FONT, 9), bg=C["surface"],
                         fg=C["faint"]).pack(side="left")
                tk.Label(r, text=new, font=(UI_FONT, 9, "bold"), bg=C["surface"],
                         fg=C["accent"]).pack(side="left")
            if len(rows) > 14:
                tk.Label(inner, text=f"…and {len(rows) - 14} more", font=(UI_FONT, 8),
                         bg=C["surface"], fg=C["faint"]).pack(anchor="w", pady=(6, 0))

        note = tk.Label(win, text="Your hotkeys, theme and window settings are never changed.",
                        font=(UI_FONT, 8), bg=C["bg"], fg=C["faint"])
        note.pack(anchor="w", padx=20)

        foot = tk.Frame(win, bg=C["surface"], height=64); foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)
        cancel = tk.Label(foot, text="Cancel", font=(UI_FONT, 10), bg=C["surface2"],
                          fg=C["text"], padx=18, pady=8, cursor="hand2")
        cancel.pack(side="right", padx=(0, 20), pady=14)
        cancel.bind("<Button-1>", lambda _e: win.destroy())
        if rows:
            ok = tk.Label(foot, text="Apply preset", font=(UI_FONT, 10, "bold"),
                          bg=C["accent"], fg=C["accent_fg"], padx=18, pady=8, cursor="hand2")
            ok.pack(side="right", padx=(0, 10), pady=14)
            ok.bind("<Button-1>", lambda _e: (self._apply_preset(rows, preset), win.destroy()))

    def _apply_preset(self, rows, preset):
        for _label, _cur, _new, key, value in rows:
            var = self.vars.get(key)
            if var is not None:
                try:
                    var.set(value)
                except tk.TclError:
                    pass
        self._sync_flags()
        self._refresh_target_ui(); self._refresh_key_ui(); self._refresh_limit_ui()
        self.status_text.set(f"Applied “{preset.get('name', 'preset')}”")
        self.root.after(2200, self._refresh_running_ui)
        self.show_page("home")

    # ---- community / import / export -------------------------------------- #
    def _browse_community(self):
        self.preset_status.configure(text="Fetching community presets…")

        def work():
            items, err = fetch_community()
            self.root.after(0, lambda: self._community_done(items, err))

        threading.Thread(target=work, daemon=True).start()

    def _community_done(self, items, err):
        if err:
            self.preset_status.configure(
                text=f"Could not reach the library ({err}). Everything else still works.")
            return
        self.community_presets = items
        self.preset_status.configure(
            text=f"Loaded {len(items)} community preset{'s' if len(items) != 1 else ''}.")
        self._render_presets()

    def _export_current(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("Preset", "*.json")],
            initialfile="my_preset.json")
        if not path:
            return
        try:
            export_preset(path, self.vars, name=None)
            self.preset_status.configure(text="Saved. Share it, or open a PR to add it "
                                              "to the community library.")
        except OSError as e:
            messagebox.showerror("Preset", f"Could not save:\n{e}")

    def _import_preset(self):
        path = filedialog.askopenfilename(filetypes=[("Preset", "*.json")])
        if not path:
            return
        try:
            import json
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            messagebox.showerror("Preset", f"Could not read that file:\n{e}")
            return
        preset = clean_preset(data, source="mine")
        if preset is None:
            messagebox.showerror("Preset", "That file isn't a valid preset.")
            return
        save_local_preset(preset)
        self.local_presets = load_local_presets()
        self.vars["preset_filter"].set("Mine")
        self._render_presets()
        self.preset_status.configure(text=f"Imported “{preset['name']}”.")
