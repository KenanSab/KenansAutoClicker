"""Custom Tk widgets: switches, segmented pickers, disclosures, icon buttons."""

import tkinter as tk

from .icons import LUCIDE, draw_icon, parse_svg_path
from .theme import THEMES, UI_FONT


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
        name = {"home": "house", "settings": "settings",
                "presets": "layers"}.get(
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


class StaticIcon(tk.Canvas):
    """A non-interactive Lucide icon that follows the theme."""

    def __init__(self, parent, name, size=16, role="muted"):
        super().__init__(parent, width=size, height=size,
                         highlightthickness=0, bd=0)
        self.name = name
        self.size = size
        self.role = role
        self.C = THEMES["dark"]

    def refresh_theme(self, C):
        self.C = C
        self.delete("all")
        try:
            self.configure(bg=self.master.cget("bg"))
        except tk.TclError:
            pass
        draw_icon(self, self.name, self.size, C.get(self.role, C["muted"]), stroke=2.0)
