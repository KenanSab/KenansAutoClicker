"""Interface behavior: what is visible by default, where rows sit, scrolling.

Several of these pin bugs that actually shipped, so the comments say which.
"""

import tkinter as tk

import pytest

from kenansautoclicker.widgets import Disclosure, IconButton, Segmented, Toggle

ADV = ("adv_click_open", "adv_key_open", "adv_hotkeys_open", "adv_behav_open")


def _collapse_all(app):
    for name in ADV:
        app.vars[name].set(False)
    app.vars["key_mode"].set("Key"); app._refresh_key_ui()
    app.vars["target_mode"].set("Cursor"); app._refresh_target_ui()
    app.root.update()


def _y(app, widget):
    app.root.update_idletasks(); app.root.update()
    return widget.winfo_rooty()


# ------------------------------------------------------- minimal by default --
def test_default_view_hides_advanced_controls(app):
    """The default view must stay minimal: no targeting, no coordinates."""
    _collapse_all(app)
    app.root.deiconify(); app.root.geometry("600x580")
    app.show_page("home"); app.root.update()
    for name in ("target_row", "pos_row", "points_row"):
        assert not getattr(app, name).winfo_ismapped(), f"{name} shown by default"
    assert app.key_row.winfo_ismapped()
    assert not app.key_mode_row.winfo_ismapped()
    app.root.withdraw()


def test_settings_shows_only_the_main_hotkey(app):
    _collapse_all(app)
    app.root.deiconify()
    app.show_page("settings"); app.root.update()
    assert app.hk_master.winfo_ismapped()
    assert not app.limit_row.winfo_ismapped()
    app.show_page("home"); app.root.withdraw()


# ------------------------------------------------------------- row ordering --
def test_position_rows_sit_under_click_at(app):
    """Regression: pack() re-appends at the end, so these once rendered in the
    middle of the interval group instead of under their own heading."""
    app.root.deiconify(); app.root.geometry("600x580")
    app.show_page("home")
    app.vars["adv_click_open"].set(True)
    for mode, attr in (("Fixed", "pos_row"), ("Multi", "points_row")):
        app.vars["target_mode"].set(mode); app._refresh_target_ui()
        gap = _y(app, getattr(app, attr)) - _y(app, app.target_row)
        assert 0 < gap < 80, f"{attr} sits {gap}px from 'Click at'"
    _collapse_all(app); app.root.withdraw()


def test_key_rows_sit_beside_their_headings(app):
    """The key chip is basic and the value field is advanced, so they live in
    different containers and must each pack next to their own sibling."""
    app.root.deiconify(); app.root.geometry("600x580")
    app.show_page("home")
    app.vars["adv_key_open"].set(True)

    app.vars["key_mode"].set("Key"); app._refresh_key_ui()
    gap = _y(app, app.key_interval_row) - _y(app, app.key_row)
    assert 0 < gap < 80

    for mode in ("Sequence", "Combo", "Text"):
        app.vars["key_mode"].set(mode); app._refresh_key_ui()
        gap = _y(app, app.keyval_row) - _y(app, app.key_mode_row)
        assert 0 < gap < 80, f"value row {gap}px from Mode in {mode}"
    _collapse_all(app); app.root.withdraw()


# ---------------------------------------------------------------- scrolling --
def test_every_page_owns_a_canvas(app):
    for name in ("home", "presets", "settings"):
        app.show_page(name); app.root.update()
        assert app.active_canvas is app.pages[name].canvas


def _touchpad_supported(root):
    """Whether this Tk knows the event at all.

    <TouchpadScroll> arrived in Tk 8.7; Ubuntu still ships 8.6, where merely
    *querying* the binding succeeds but binding or generating it raises. So the
    probe has to attempt a real bind.
    """
    try:
        root.bind("<TouchpadScroll>", lambda _e: None)
    except tk.TclError:
        return False
    root.unbind("<TouchpadScroll>")
    return True


def test_touchpad_scroll_is_bound(app):
    """Tk 8.7+ on macOS sends <TouchpadScroll> and NOT <MouseWheel> for a
    precision trackpad. Binding only <MouseWheel> shipped once and left every
    MacBook unable to scroll at all."""
    if not _touchpad_supported(app.root):
        pytest.skip("this Tk predates TouchpadScroll; MouseWheel covers it")
    assert app.root.bind_all("<TouchpadScroll>"), "trackpads cannot scroll"


def test_wheel_is_bound(app):
    assert app.root.bind_all("<MouseWheel>")


def _pack_delta(dy):
    """Encode dy the way Tk packs TouchpadScroll deltas."""
    return (0 << 16) | (dy & 0xFFFF)


def test_touchpad_scroll_moves_both_directions(app):
    if not _touchpad_supported(app.root):
        pytest.skip("this Tk predates TouchpadScroll")
    if not app.root.tk.call("info", "procs", "::tk::PreciseScrollDeltas"):
        pytest.skip("no PreciseScrollDeltas helper")
    app.root.deiconify(); app.root.geometry("600x420")
    app.vars["adv_click_open"].set(True); app.vars["adv_key_open"].set(True)
    app.show_page("home"); app.root.update_idletasks(); app.root.update()

    canvas = app.active_canvas
    canvas.yview_moveto(0.5); app.root.update()
    mid = canvas.yview()[0]

    # Tk's convention is `yview scroll -deltaY`, so negative dy scrolls down
    app.root.event_generate("<TouchpadScroll>", delta=_pack_delta(-40))
    app.root.update()
    assert canvas.yview()[0] > mid

    app.root.event_generate("<TouchpadScroll>", delta=_pack_delta(40))
    app.root.event_generate("<TouchpadScroll>", delta=_pack_delta(40))
    app.root.update()
    assert canvas.yview()[0] < mid + 0.2

    canvas.yview_moveto(0)
    _collapse_all(app); app.root.withdraw()


def test_pixel_scrolling_clamps(app):
    canvas = app.active_canvas
    app._scroll_pixels(canvas, -99999)
    assert canvas.yview()[0] >= 0.0
    app._scroll_pixels(canvas, 99999)
    assert canvas.yview()[0] <= 1.0
    canvas.yview_moveto(0)


# ----------------------------------------------------------------- widgets --
def test_toggle_flips_its_variable(app):
    for w in app._custom:
        if isinstance(w, Toggle):
            before = w.var.get()
            w._click()
            assert w.var.get() != before
            w._click()
            return
    pytest.fail("no Toggle found")


def test_segmented_selects(app):
    for w in app._custom:
        if isinstance(w, Segmented) and w.var is app.vars["mouse_button"]:
            w._pick("Right")
            assert app.vars["mouse_button"].get() == "Right"
            w._pick("Left")
            return
    pytest.fail("no mouse-button Segmented found")


def test_disclosures_open_and_close(app):
    found = [w for w in app._custom if isinstance(w, Disclosure)]
    assert found, "no disclosure sections"
    for d in found:
        d.var.set(False); app.root.update()
        assert not d.body.winfo_ismapped()
        d._toggle(); app.root.update()
        assert d.body.winfo_ismapped()
        d._toggle(); app.root.update()


def test_icons_draw_in_both_themes(app):
    buttons = [w for w in app._custom if isinstance(w, IconButton)]
    assert len(buttons) == 4, "home, presets, settings, theme"
    for b in buttons:
        for dark in (True, False):
            b.refresh_theme(app.C, is_dark=dark)
            assert b.find_all(), f"{b.kind} drew nothing"


def test_no_emoji_in_source():
    """Emoji render differently per OS, so the interface must not rely on them."""
    import glob
    import os
    pkg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "kenansautoclicker")
    for path in glob.glob(os.path.join(pkg, "*.py")):
        text = open(path, encoding="utf-8").read()
        bad = {c for c in text if ord(c) > 0x2100 and c not in "–—±×·’→"}
        assert not bad, f"{os.path.basename(path)} contains {bad}"


# ------------------------------------------------------------------ themes --
def test_theme_toggle_round_trip(app):
    start = app.theme_name
    app.toggle_theme(); app.root.update()
    assert app.theme_name != start
    app.toggle_theme(); app.root.update()
    assert app.theme_name == start


def test_all_pages_survive_theme_change(app):
    for page in ("home", "presets", "settings"):
        app.show_page(page)
        app.toggle_theme(); app.root.update()
        app.toggle_theme(); app.root.update()


# ------------------------------------------------------------- window size --
def test_scroll_card_exists_on_home(app):
    """Auto Scroll is a top-level feature, not something buried in a section."""
    app.root.deiconify()
    app.show_page("home"); app.root.update_idletasks(); app.root.update()
    labels = []

    def walk(w):
        for ch in w.winfo_children():
            if isinstance(ch, tk.Label):
                try:
                    labels.append(ch.cget("text"))
                except tk.TclError:
                    pass
            walk(ch)

    walk(app.pages["home"])
    assert "Auto Scroll" in labels, "the Auto Scroll card is missing from Home"
    app.root.withdraw()


def test_collapsed_home_fits_without_scrolling(app):
    """Every card must be reachable at the default size.

    Adding the third card once pushed Auto Scroll below the fold, where it was
    effectively invisible. The window now measures its content, so this asserts
    the measurement actually worked.
    """
    for name in ADV:
        app.vars[name].set(False)
    app.root.deiconify()
    app.show_page("home")
    app._fit_window()
    app.root.update_idletasks(); app.root.update()

    canvas = app.pages["home"].canvas
    box = canvas.bbox("all")
    overflow = (box[3] - box[1]) - canvas.winfo_height()
    screen = app.root.winfo_screenheight()
    # on a very short display the clamp wins, and that is correct behaviour
    if app.root.winfo_height() < int(screen * 0.85) - 2:
        assert overflow <= 2, f"home overflows by {overflow}px at the default size"
    app.root.withdraw()
