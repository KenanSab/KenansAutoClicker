"""Shared layout primitives: cards, rows, scrolling, control factories.

Every page is built from these, so spacing and alignment stay consistent.
"""

import tkinter as tk
from tkinter import ttk

from .theme import THEMES, TOUCHPAD_SPEED, UI_FONT
from .widgets import Disclosure, IconButton, Segmented, Toggle


class UIBase:
    """Layout helpers mixed into the application window."""


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

    def _scroll_pixels(self, canvas, dy):
        """Scroll by an exact pixel amount, clamped to the content."""
        box = canvas.bbox("all")
        if not box:
            return
        total = box[3] - box[1]
        view = canvas.winfo_height()
        if total <= view:
            return                       # nothing to scroll
        top = canvas.yview()[0] * total + dy
        top = max(0.0, min(float(total - view), top))
        canvas.yview_moveto(top / total)

    def _bind_wheel(self):
        """Route every kind of scroll input to whichever page is visible.

        Three separate things have to be handled:
          * <MouseWheel>     — a real wheel. Windows sends multiples of 120,
                               macOS sends small integers.
          * <Button-4/5>     — how X11 reports a wheel.
          * <TouchpadScroll> — what Tk 8.7+ on macOS sends for a precision
                               trackpad. It does NOT also send <MouseWheel>,
                               so binding only the above leaves every MacBook
                               unable to scroll.
        bind_all is global, so there is one handler routed via active_canvas
        rather than one binding per page (a second page would replace the first).
        """
        def canvas_now():
            return getattr(self, "active_canvas", None)

        def wheel(event):
            canvas = canvas_now()
            if canvas is None:
                return
            num = getattr(event, "num", 0)
            delta = getattr(event, "delta", 0) or 0
            if num == 4:
                step = -3
            elif num == 5:
                step = 3
            elif delta:
                step = (-delta / 120 * 3) if abs(delta) >= 120 else (-delta * 3)
            else:
                return
            step = int(step)
            if step == 0:               # never let rounding swallow a scroll
                step = -1 if (delta or -num) > 0 else 1
            canvas.yview_scroll(step, "units")

        def touchpad(event):
            canvas = canvas_now()
            if canvas is None:
                return
            # Tk packs both axes into one int; its own helper unpacks them.
            try:
                dx, dy = self.root.tk.call("::tk::PreciseScrollDeltas", event.delta)
                dy = int(dy)
            except (tk.TclError, ValueError, TypeError):
                return
            if dy:
                self._scroll_pixels(canvas, -dy * TOUCHPAD_SPEED)

        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind_all(seq, wheel)
        try:
            self.root.bind_all("<TouchpadScroll>", touchpad)
        except tk.TclError:
            pass                         # older Tk: wheel bindings cover it


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
            "search": dict(bg=C["search_bg"], highlightbackground=C["border"],
                           highlightcolor=C["accent"]),
            "search_entry": dict(bg=C["search_bg"], fg=C["text"],
                                 insertbackground=C["text"]),
            "warn_box": dict(bg=C["warn_bg"], highlightbackground=C["warn_border"],
                             highlightcolor=C["warn_border"]),
            "warn_text": dict(bg=C["warn_bg"], fg=C["warn_fg"]),
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
        for b, which in ((self.home_btn, "home"),
                         (self.presets_btn, "presets"),
                         (self.settings_btn, "settings")):
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
