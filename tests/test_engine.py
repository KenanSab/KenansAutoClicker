"""Engine behavior: interval maths, limits, humanization and persistence."""

import time

import pytest


# ---------------------------------------------------------------- intervals --
@pytest.mark.parametrize("unit,expected", [("ms", 0.1), ("sec", 100.0), ("min", 6000.0)])
def test_interval_unit_conversion(app, unit, expected):
    app.vars["click_val"].set("100")
    app.vars["click_unit"].set(unit)
    assert app._interval_of("click_val", "click_unit") == pytest.approx(expected)


def test_garbage_interval_does_not_crash(app):
    app.vars["click_val"].set("not a number")
    app._interval_of("click_val", "click_unit")
    app._mouse_cfg()          # must still build a usable config


def test_randomized_interval_never_zero_or_negative(app):
    cfg = app._mouse_cfg()
    cfg["rand"] = 0.05
    for _ in range(500):
        assert app._rand_interval(cfg) >= 0.001


def test_randomized_interval_varies(app):
    cfg = app._mouse_cfg()
    cfg["base"], cfg["rand"] = 0.1, 0.05
    seen = {round(app._rand_interval(cfg), 6) for _ in range(50)}
    assert len(seen) > 1, "randomization produced identical values"


# ------------------------------------------------------------------- limits --
def test_count_limit(app):
    cfg = dict(stop_mode="Count", stop_count=5, stop_time=1)
    assert app._reached_limit(cfg, 5, 0)
    assert not app._reached_limit(cfg, 4, 0)


def test_time_limit(app):
    cfg = dict(stop_mode="Time", stop_count=1, stop_time=0.0)
    assert app._reached_limit(cfg, 0, time.time() - 1)


def test_never_limit(app):
    cfg = dict(stop_mode="Never", stop_count=1, stop_time=1)
    assert not app._reached_limit(cfg, 10 ** 6, 0)


# ------------------------------------------------------------- humanization --
def test_hold_time_handles_reversed_range(app):
    cfg = app._mouse_cfg()
    cfg.update(hold_on=True, hold_min=0.04, hold_max=0.01)   # deliberately swapped
    for _ in range(100):
        assert 0.01 <= app._hold_time(cfg) <= 0.04


def test_hold_time_is_fixed_when_disabled(app):
    cfg = app._mouse_cfg()
    cfg["hold_on"] = False
    assert app._hold_time(cfg) == app._hold_time(cfg)


# ------------------------------------------------------------------ configs --
@pytest.mark.parametrize("mode", ["Cursor", "Fixed", "Multi"])
def test_all_target_modes_build_a_config(app, mode):
    app.vars["target_mode"].set(mode)
    app._refresh_target_ui()
    assert app._mouse_cfg()["target_mode"] == mode


@pytest.mark.parametrize("mode,value", [("Key", ""), ("Sequence", "q w e"),
                                        ("Combo", "ctrl+a"), ("Text", "hello")])
def test_all_key_modes_build_a_config(app, mode, value):
    app.vars["key_mode"].set(mode)
    app.vars["key_value"].set(value)
    app._refresh_key_ui()
    assert app._key_cfg()["mode"] == mode


def test_starting_with_nothing_enabled_is_safe(app):
    """Must refuse politely rather than spawning threads that do nothing."""
    app.vars["mouse_enabled"].set(False)
    app.vars["key_enabled"].set(False)
    app.start_all()
    assert not app.mouse_active and not app.key_active
    app.stop_all()


def test_stop_all_clears_both_flags(app):
    app.mouse_active = app.key_active = True
    app.stop_all()
    assert not app.mouse_active and not app.key_active


# -------------------------------------------------------------- persistence --
def test_settings_round_trip(app):
    app.points = [(10, 20), (30, 40)]
    app.total_clicks = 1234
    app.vars["click_val"].set("250")
    app.vars["key_mode"].set("Combo")
    data = app._collect()

    app.points = []
    app.total_clicks = 0
    app.vars["click_val"].set("1")
    app.vars["key_mode"].set("Key")

    app._apply(data)
    assert app.points == [(10, 20), (30, 40)]
    assert app.total_clicks == 1234
    assert app.vars["click_val"].get() == "250"
    assert app.vars["key_mode"].get() == "Combo"


def test_config_file_round_trip(app):
    app.vars["click_val"].set("321")
    app._save_config()
    app.vars["click_val"].set("1")
    app._load_config()
    assert app.vars["click_val"].get() == "321"


def test_config_from_an_older_version_is_survivable(app):
    """Old configs use variable names this build no longer has. Loading one
    must not crash — it should simply keep the current defaults."""
    stale = {
        "click_ms": "50", "click_h": "0",             # gone in this version
        "target_mode": "Follow cursor",               # renamed value
        "key_mode": "Single key", "stop_mode": "count",
        "activation": "hold",
        "_points": [[1, 2]], "_total_clicks": 7,
    }
    app._apply(stale)
    app._mouse_cfg()
    app._key_cfg()
    assert app.total_clicks == 7


def test_hotkeys_survive_a_config_round_trip(app):
    from pynput.keyboard import Key
    app.master_hotkey = Key.f4
    data = app._collect()
    app.master_hotkey = Key.f6
    app._apply(data)
    assert app.master_hotkey == Key.f4
