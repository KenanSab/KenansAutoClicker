"""Holding and auto-scrolling.

Holding is the riskiest thing this app does. A button or key left physically
pressed keeps acting on whatever the user does next, with no obvious way to
stop it, so most of these tests are about the release actually happening.
"""

import threading
import time

import pytest


class FakeMouse:
    """Records presses, releases and scrolls instead of touching the machine."""

    def __init__(self):
        self.events = []
        self.position = (0, 0)

    def press(self, button):
        self.events.append(("press", button))

    def release(self, button):
        self.events.append(("release", button))

    def scroll(self, dx, dy):
        self.events.append(("scroll", dx, dy))

    def click(self, button, count=1):
        self.events.append(("click", button, count))

    @property
    def held(self):
        """Buttons currently down."""
        down = []
        for e in self.events:
            if e[0] == "press":
                down.append(e[1])
            elif e[0] == "release" and e[1] in down:
                down.remove(e[1])
        return down


class FakeKeyboard(FakeMouse):
    def type(self, text):
        self.events.append(("type", text))


@pytest.fixture
def fake(app, monkeypatch):
    m, k = FakeMouse(), FakeKeyboard()
    monkeypatch.setattr(app, "mouse_ctl", m)
    monkeypatch.setattr(app, "kbd_ctl", k)
    return m, k


def _run(fn, cfg, stop_after=0.12):
    """Run a loop in a thread and let it settle."""
    t = threading.Thread(target=fn, args=(cfg,), daemon=True)
    t.start()
    time.sleep(stop_after)
    return t


# ------------------------------------------------------------------ holding --
def test_hold_mouse_presses_once_and_releases_on_stop(app, fake):
    mouse, _ = fake
    app.vars["click_action"].set("Hold")
    app.mouse_active = True
    t = _run(app._hold_mouse, app._mouse_cfg())

    assert mouse.held, "button should be down while running"
    presses = [e for e in mouse.events if e[0] == "press"]
    assert len(presses) == 1, "hold must press once, not repeatedly"

    app.mouse_active = False
    t.join(timeout=2)
    assert not mouse.held, "button still down after stopping"


def test_hold_key_presses_once_and_releases_on_stop(app, fake):
    _, kbd = fake
    app.vars["key_mode"].set("Hold")
    app.key_active = True
    t = _run(app._hold_key, app._key_cfg())

    assert kbd.held, "key should be down while running"
    assert len([e for e in kbd.events if e[0] == "press"]) == 1

    app.key_active = False
    t.join(timeout=2)
    assert not kbd.held, "key still down after stopping"


def test_hold_releases_even_if_the_wait_raises(app, fake):
    """The release lives in a `finally`, so an exception must not strand it."""
    mouse, _ = fake
    app.mouse_active = True

    calls = {"n": 0}
    real_sleep = time.sleep

    def boom(_seconds):
        calls["n"] += 1
        if calls["n"] > 2:
            raise RuntimeError("thread torn down")
        real_sleep(0.01)

    import kenansautoclicker.engine as engine
    orig = engine.time.sleep
    engine.time.sleep = boom
    try:
        with pytest.raises(RuntimeError):
            app._hold_mouse(app._mouse_cfg())
    finally:
        engine.time.sleep = orig
        app.mouse_active = False

    assert not mouse.held, "exception left the button pressed"


def test_stop_all_clears_the_scroll_flag_too(app):
    app.mouse_active = app.key_active = app.scroll_active = True
    app.stop_all()
    assert not (app.mouse_active or app.key_active or app.scroll_active)


def test_hold_does_not_use_an_interval(app):
    """Interval is meaningless while holding, so the row is hidden."""
    app.root.deiconify()
    app.show_page("home")
    app.vars["click_action"].set("Hold"); app._refresh_action_ui()
    app.root.update_idletasks(); app.root.update()
    assert not app.click_interval_row.winfo_ismapped()

    app.vars["click_action"].set("Click"); app._refresh_action_ui()
    app.root.update_idletasks(); app.root.update()
    assert app.click_interval_row.winfo_ismapped()
    app.root.withdraw()


def test_key_hold_hides_its_interval_but_keeps_the_key_chip(app):
    app.root.deiconify()
    app.show_page("home")
    app.vars["adv_key_open"].set(True)
    app.vars["key_mode"].set("Hold"); app._refresh_key_ui()
    app.root.update_idletasks(); app.root.update()
    assert app.key_row.winfo_ismapped(), "still need to pick which key"
    assert not app.key_interval_row.winfo_ismapped()

    app.vars["key_mode"].set("Key"); app._refresh_key_ui()
    app.root.update_idletasks(); app.root.update()
    assert app.key_interval_row.winfo_ismapped()
    app.vars["adv_key_open"].set(False)
    app.root.withdraw()


# ---------------------------------------------------------------- scrolling --
def test_scroll_loop_scrolls_repeatedly(app, fake):
    mouse, _ = fake
    app.vars["scroll_val"].set("10")
    app.vars["scroll_unit"].set("ms")
    app.scroll_active = True
    t = _run(app._scroll_loop, app._scroll_cfg())
    app.scroll_active = False
    t.join(timeout=2)

    scrolls = [e for e in mouse.events if e[0] == "scroll"]
    assert len(scrolls) > 1, "auto scroll should repeat"


@pytest.mark.parametrize("direction,sign", [("Up", 1), ("Down", -1)])
def test_scroll_direction(app, direction, sign):
    app.vars["scroll_dir"].set(direction)
    app.vars["scroll_amount"].set("3")
    cfg = app._scroll_cfg()
    assert cfg["dy"] == 3 * sign


def test_scroll_amount_is_at_least_one(app):
    for bad in ("0", "-5", "not a number", ""):
        app.vars["scroll_amount"].set(bad)
        assert abs(app._scroll_cfg()["dy"]) >= 1


def test_scroll_respects_a_count_limit(app, fake):
    mouse, _ = fake
    app.vars["scroll_val"].set("1")
    app.vars["scroll_unit"].set("ms")
    app.vars["stop_mode"].set("Count")
    app.vars["stop_count"].set("3")
    app.scroll_active = True
    t = _run(app._scroll_loop, app._scroll_cfg(), stop_after=0.4)
    t.join(timeout=2)
    app.scroll_active = False

    scrolls = [e for e in mouse.events if e[0] == "scroll"]
    assert len(scrolls) == 3, f"expected exactly 3 scrolls, got {len(scrolls)}"


def test_starting_with_only_scroll_enabled_works(app):
    app.vars["mouse_enabled"].set(False)
    app.vars["key_enabled"].set(False)
    app.vars["scroll_enabled"].set(True)
    app.start_all(countdown=False)
    try:
        assert app.scroll_active, "scroll alone should be able to start"
    finally:
        app.stop_all()


def test_nothing_enabled_still_refuses(app):
    app.vars["mouse_enabled"].set(False)
    app.vars["key_enabled"].set(False)
    app.vars["scroll_enabled"].set(False)
    app.start_all(countdown=False)
    assert not (app.mouse_active or app.key_active or app.scroll_active)
