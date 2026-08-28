"""Macro recording and playback."""

import json

import pytest
from pynput.keyboard import Key, KeyCode
from pynput.mouse import Button

from kenansautoclicker.recorder import (Player, Recorder, clean_events,
                                        load_macro, save_macro, summarize)


class FakeCtl:
    def __init__(self):
        self.events = []
        self.position = (0, 0)

    def press(self, thing):
        self.events.append(("press", thing))

    def release(self, thing):
        self.events.append(("release", thing))

    def scroll(self, dx, dy):
        self.events.append(("scroll", dx, dy))

    @property
    def held(self):
        down = []
        for e in self.events:
            if e[0] == "press":
                down.append(e[1])
            elif e[0] == "release" and e[1] in down:
                down.remove(e[1])
        return down


def _clicks(n=2):
    out = []
    for i in range(n):
        out.append({"t": i * 0.05, "type": "click", "x": 10 + i, "y": 20,
                    "button": "left", "down": True})
        out.append({"t": i * 0.05 + 0.01, "type": "click", "x": 10 + i, "y": 20,
                    "button": "left", "down": False})
    return out


# ------------------------------------------------------------------ capture --
def test_recorder_starts_empty():
    r = Recorder()
    assert r.events == []
    assert not r.recording


def test_recorder_ignores_the_stop_hotkey():
    """The key used to stop recording must not end up inside the recording,
    or every playback would press it and stop itself."""
    r = Recorder(ignore_keys={Key.f6})
    r._start = 0
    r.recording = True
    r._on_press(Key.f6)
    r._on_release(Key.f6)
    r._on_press(KeyCode.from_char("a"))
    kinds = [e["key"] for e in r.events]
    assert all("f6" not in k for k in kinds), r.events
    assert len(r.events) == 1


def test_recorder_drops_moves_unless_asked():
    r = Recorder(capture_moves=False)
    r._start = 0
    r.recording = True
    for i in range(10):
        r._on_move(i, i)
    assert r.events == []


def test_recorder_samples_movement_when_enabled():
    r = Recorder(capture_moves=True)
    r._start = 0
    r.recording = True
    for i in range(50):
        r._on_move(i, i)          # no delay: sampling should discard most
    assert 0 < len(r.events) < 50


def test_recorder_captures_clicks_and_scrolls():
    r = Recorder()
    r._start = 0
    r.recording = True
    r._on_click(5, 6, Button.left, True)
    r._on_click(5, 6, Button.left, False)
    r._on_scroll(1, 2, 0, -3)
    kinds = [e["type"] for e in r.events]
    assert kinds == ["click", "click", "scroll"]
    assert r.events[0]["button"] == "left"
    assert r.events[2]["dy"] == -3


def test_stopped_recorder_accepts_nothing_more():
    r = Recorder()
    r._start = 0
    r.recording = True
    r._on_click(1, 1, Button.left, True)
    r.recording = False
    r._on_click(2, 2, Button.left, True)
    assert len(r.events) == 1


# ----------------------------------------------------------------- playback --
def test_playback_reproduces_clicks():
    m, k = FakeCtl(), FakeCtl()
    Player(m, k).play(_clicks(2), lambda: True, speed=50, repeat=1)
    assert len([e for e in m.events if e[0] == "press"]) == 2
    assert not m.held


def test_playback_repeats():
    m, k = FakeCtl(), FakeCtl()
    Player(m, k).play(_clicks(1), lambda: True, speed=50, repeat=3)
    assert len([e for e in m.events if e[0] == "press"]) == 3


def test_playback_stops_when_asked():
    m, k = FakeCtl(), FakeCtl()
    state = {"go": True}

    def keep():
        # allow one event through, then stop
        if len(m.events) >= 1:
            state["go"] = False
        return state["go"]

    Player(m, k).play(_clicks(10), keep, speed=50, repeat=1)
    assert len(m.events) < 20


def test_playback_releases_a_button_left_down():
    """A recording can end mid-drag. Playback must not leave it pressed."""
    m, k = FakeCtl(), FakeCtl()
    half_drag = [{"t": 0, "type": "click", "x": 1, "y": 1,
                  "button": "left", "down": True}]      # never released
    Player(m, k).play(half_drag, lambda: True, speed=50, repeat=1)
    assert not m.held, "playback left the mouse button down"


def test_playback_releases_a_key_left_down():
    m, k = FakeCtl(), FakeCtl()
    half = [{"t": 0, "type": "key", "key": "c:a", "down": True}]
    Player(m, k).play(half, lambda: True, speed=50, repeat=1)
    assert not k.held, "playback left a key pressed"


def test_playback_survives_a_broken_event():
    m, k = FakeCtl(), FakeCtl()
    events = [{"t": 0, "type": "click"},                       # no coordinates
              {"t": 0.01, "type": "click", "x": 1, "y": 1,
               "button": "left", "down": True},
              {"t": 0.02, "type": "click", "x": 1, "y": 1,
               "button": "left", "down": False}]
    Player(m, k).play(events, lambda: True, speed=50, repeat=1)
    assert any(e[0] == "press" for e in m.events), "one bad event ended the macro"


def test_on_finished_always_runs():
    m, k = FakeCtl(), FakeCtl()
    called = []
    Player(m, k).play([], lambda: True, speed=1, repeat=1,
                      on_finished=lambda: called.append(True))
    assert called


# ---------------------------------------------------------------- validation --
def test_clean_events_drops_unknown_types():
    out = clean_events([{"type": "explode", "t": 0},
                        {"type": "click", "t": 0, "x": 1, "y": 1}])
    assert len(out) == 1 and out[0]["type"] == "click"


def test_clean_events_rejects_non_lists():
    assert clean_events({"nope": True}) == []
    assert clean_events("string") == []
    assert clean_events(None) == []


def test_clean_events_clamps_scroll():
    out = clean_events([{"type": "scroll", "t": 0, "x": 0, "y": 0,
                         "dx": 99999, "dy": -99999}])
    assert abs(out[0]["dx"]) <= 50 and abs(out[0]["dy"]) <= 50


def test_clean_events_refuses_negative_time():
    out = clean_events([{"type": "click", "t": -5, "x": 1, "y": 1}])
    assert out[0]["t"] >= 0


def test_macro_file_round_trip(tmp_path):
    path = tmp_path / "m.json"
    events = _clicks(3)
    save_macro(str(path), events, name="test")
    back = load_macro(str(path))
    assert len(back) == len(events)
    assert back[0]["type"] == "click"


def test_loading_a_hostile_macro_is_safe(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"events": [
        {"type": "click", "t": 0, "x": 1, "y": 1},
        {"type": "__import__", "t": 0},
        "not even an object",
        {"type": "key", "t": 0, "key": "x" * 5000, "down": True},
    ]}))
    out = load_macro(str(path))
    assert all(e["type"] in ("click", "key") for e in out)
    assert all(len(e.get("key", "")) <= 40 for e in out)


# ------------------------------------------------------------------ summary --
def test_summarize_counts_things():
    text = summarize(_clicks(3))
    assert "3 clicks" in text


def test_summarize_handles_empty():
    assert "nothing" in summarize([]).lower()
