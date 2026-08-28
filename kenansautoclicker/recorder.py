"""Recording and replaying real input.

An interval is fine for repeating one action. Anything with structure, like
"click here, wait, type this, click there", is far easier to demonstrate than
to configure. So this records what you actually did and plays it back.

Events are stored as plain dictionaries with an offset in seconds from the
start of the recording, which makes a macro a readable JSON file that can be
inspected, edited by hand, and shared.
"""

import json
import threading
import time

from pynput import keyboard, mouse
from pynput.keyboard import Key, KeyCode
from pynput.mouse import Button

from .keys import key_from_str, key_to_str

MACRO_SCHEMA = 1

#: Anything faster than this is treated as instant during playback. Recorded
#: gaps of a few milliseconds are mostly measurement noise, and sleeping on
#: them makes playback drift slower than the original.
MIN_GAP = 0.004

#: Recording every mouse movement produces enormous files for no benefit, so
#: moves are sampled no more often than this.
MOVE_SAMPLE = 0.03


def _button_name(button):
    return str(button).rsplit(".", 1)[-1]


def _button_from_name(name):
    return {"left": Button.left, "right": Button.right,
            "middle": Button.middle}.get(str(name).lower(), Button.left)


class Recorder:
    """Captures mouse and keyboard events with their timing.

    The recorder deliberately ignores the hotkey used to stop it, so the act of
    stopping does not end up inside the recording and replay itself later.
    """

    def __init__(self, capture_moves=False, ignore_keys=()):
        self.events = []
        self.capture_moves = capture_moves
        self.ignore_keys = set(ignore_keys)
        self._start = None
        self._last_move = 0.0
        self._mouse_listener = None
        self._key_listener = None
        self.recording = False

    # ---- lifecycle ------------------------------------------------------- #
    def start(self):
        self.events = []
        self._start = time.time()
        self._last_move = 0.0
        self.recording = True
        self._mouse_listener = mouse.Listener(on_click=self._on_click,
                                              on_move=self._on_move,
                                              on_scroll=self._on_scroll)
        self._key_listener = keyboard.Listener(on_press=self._on_press,
                                               on_release=self._on_release)
        for listener in (self._mouse_listener, self._key_listener):
            listener.daemon = True
            listener.start()

    def stop(self):
        self.recording = False
        for listener in (self._mouse_listener, self._key_listener):
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
        self._mouse_listener = self._key_listener = None
        return self.events

    # ---- capture --------------------------------------------------------- #
    def _t(self):
        return round(time.time() - self._start, 4)

    def _add(self, event):
        if self.recording:
            self.events.append(event)

    def _on_click(self, x, y, button, pressed):
        self._add({"t": self._t(), "type": "click", "x": int(x), "y": int(y),
                   "button": _button_name(button), "down": bool(pressed)})

    def _on_scroll(self, x, y, dx, dy):
        self._add({"t": self._t(), "type": "scroll", "x": int(x), "y": int(y),
                   "dx": int(dx), "dy": int(dy)})

    def _on_move(self, x, y):
        if not self.capture_moves:
            return
        now = time.time()
        if now - self._last_move < MOVE_SAMPLE:
            return
        self._last_move = now
        self._add({"t": self._t(), "type": "move", "x": int(x), "y": int(y)})

    def _on_press(self, key):
        if key in self.ignore_keys:
            return
        self._add({"t": self._t(), "type": "key", "key": key_to_str(key),
                   "down": True})

    def _on_release(self, key):
        if key in self.ignore_keys:
            return
        self._add({"t": self._t(), "type": "key", "key": key_to_str(key),
                   "down": False})


class Player:
    """Replays a recording, optionally faster, slower, or on a loop."""

    def __init__(self, mouse_ctl, keyboard_ctl):
        self.mouse = mouse_ctl
        self.kbd = keyboard_ctl
        self._held_buttons = []
        self._held_keys = []

    def play(self, events, should_continue, speed=1.0, repeat=1,
             on_finished=None):
        """Replay `events` until they run out or `should_continue()` goes False.

        Anything the macro pressed is released at the end, whatever happens.
        A recording can legitimately end mid-drag, and a stuck button would
        otherwise outlive the app.
        """
        speed = max(float(speed), 0.05)
        try:
            loops = 0
            while should_continue() and (repeat <= 0 or loops < repeat):
                previous = 0.0
                for event in events:
                    if not should_continue():
                        break
                    gap = (event.get("t", 0) - previous) / speed
                    if gap > MIN_GAP:
                        self._sleep(gap, should_continue)
                    previous = event.get("t", 0)
                    if should_continue():
                        self._perform(event)
                loops += 1
        finally:
            self._release_everything()
            if on_finished is not None:
                on_finished()

    def _sleep(self, seconds, should_continue):
        end = time.time() + seconds
        while should_continue() and time.time() < end:
            time.sleep(min(0.02, max(end - time.time(), 0)))

    def _perform(self, event):
        kind = event.get("type")
        try:
            if kind == "move":
                self.mouse.position = (event["x"], event["y"])
            elif kind == "click":
                self.mouse.position = (event["x"], event["y"])
                button = _button_from_name(event.get("button", "left"))
                if event.get("down"):
                    self.mouse.press(button)
                    self._held_buttons.append(button)
                else:
                    self.mouse.release(button)
                    if button in self._held_buttons:
                        self._held_buttons.remove(button)
            elif kind == "scroll":
                self.mouse.position = (event["x"], event["y"])
                self.mouse.scroll(event.get("dx", 0), event.get("dy", 0))
            elif kind == "key":
                key = key_from_str(event.get("key", ""))
                if event.get("down"):
                    self.kbd.press(key)
                    self._held_keys.append(key)
                else:
                    self.kbd.release(key)
                    if key in self._held_keys:
                        self._held_keys.remove(key)
        except Exception:
            pass          # one bad event should not abandon the whole macro

    def _release_everything(self):
        for button in list(self._held_buttons):
            try:
                self.mouse.release(button)
            except Exception:
                pass
        for key in list(self._held_keys):
            try:
                self.kbd.release(key)
            except Exception:
                pass
        self._held_buttons.clear()
        self._held_keys.clear()


# --------------------------------------------------------------------------- #
#  Files
# --------------------------------------------------------------------------- #
def summarize(events):
    """A one-line description of a recording, for the interface."""
    if not events:
        return "nothing recorded yet"
    clicks = sum(1 for e in events if e.get("type") == "click" and e.get("down"))
    keys = sum(1 for e in events if e.get("type") == "key" and e.get("down"))
    scrolls = sum(1 for e in events if e.get("type") == "scroll")
    seconds = max((e.get("t", 0) for e in events), default=0)
    parts = []
    if clicks:
        parts.append(f"{clicks} click{'s' if clicks != 1 else ''}")
    if keys:
        parts.append(f"{keys} key{'s' if keys != 1 else ''}")
    if scrolls:
        parts.append(f"{scrolls} scroll{'s' if scrolls != 1 else ''}")
    if not parts:
        parts.append(f"{len(events)} events")
    return ", ".join(parts) + f"  ·  {seconds:.1f}s"


def clean_events(raw):
    """Validate a macro loaded from disk. Unknown or malformed events are cut."""
    if not isinstance(raw, list):
        return []
    out = []
    for event in raw[:20000]:
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind not in ("click", "key", "move", "scroll"):
            continue
        try:
            clean = {"type": kind, "t": max(float(event.get("t", 0)), 0.0)}
            if kind in ("click", "move", "scroll"):
                clean["x"] = int(event.get("x", 0))
                clean["y"] = int(event.get("y", 0))
            if kind == "click":
                clean["button"] = str(event.get("button", "left"))[:10]
                clean["down"] = bool(event.get("down"))
            elif kind == "scroll":
                clean["dx"] = max(-50, min(50, int(event.get("dx", 0))))
                clean["dy"] = max(-50, min(50, int(event.get("dy", 0))))
            elif kind == "key":
                clean["key"] = str(event.get("key", ""))[:40]
                clean["down"] = bool(event.get("down"))
        except (TypeError, ValueError):
            continue
        out.append(clean)
    return out


def save_macro(path, events, name=None):
    payload = {"schema": MACRO_SCHEMA, "name": name or "macro",
               "events": events}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
    return payload


def load_macro(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get("events") if isinstance(data, dict) else data
    return clean_events(raw)
