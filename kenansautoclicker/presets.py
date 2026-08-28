"""Preset model: the built-in library, validation, and community fetching.

Presets are plain data. Nothing here executes anything from a preset file, and
only known setting keys survive validation — so a preset from the internet can
change how clicking behaves but can never touch your hotkeys or your machine.
"""

import json
import os
import urllib.error
import urllib.request


PRESET_SCHEMA = 1

#: Where "Browse community" looks. Contacted only when the user clicks it.
COMMUNITY_INDEX_URL = ("https://raw.githubusercontent.com/KenanSab/"
                       "KenansAutoClicker/main/presets/index.json")

#: A preset may only change how clicking/typing behaves. It can never touch
#: your hotkeys, theme, window preferences or statistics — so installing one
#: can't steal your F6 or quietly turn on always-on-top.
PRESET_ALLOWED_KEYS = {
    "mouse_enabled", "click_val", "click_unit", "click_rand",
    "mouse_button", "click_type", "click_action",
    "target_mode", "fixed_x", "fixed_y",
    "smooth_move", "jitter_on", "jitter_px",
    "hold_rand_on", "hold_min", "hold_max",
    "burst_on", "burst_n", "burst_pause",
    "key_enabled", "key_mode", "key_value", "key_val_int", "key_unit", "key_rand",
    "scroll_enabled", "scroll_dir", "scroll_val", "scroll_unit",
    "scroll_amount", "scroll_rand",
    "stop_mode", "stop_count", "stop_time", "countdown",
}

#: Tags that mean "this automates a competitive online game". Those presets get
#: a visible warning, because input automation gets accounts permanently banned.
RISK_TAGS = {"competitive", "online-multiplayer", "pvp", "anticheat"}

RISK_NOTE = ("Automating input in competitive online games usually breaks their "
             "terms of service and can get your account permanently banned.")

BUILTIN_PRESETS = [
    # ---------------- Accessibility ----------------
    {
        "name": "Assisted Click",
        "category": "Accessibility",
        "author": "Kenan's AutoClicker",
        "description": "One gentle click per second, for anyone who finds "
                       "repeated clicking painful or difficult.",
        "tags": ["accessibility", "assistive", "rsi"],
        "settings": {
            "mouse_enabled": True, "click_val": "1", "click_unit": "sec",
            "mouse_button": "Left", "click_type": "Single",
            "target_mode": "Cursor", "key_enabled": False, "stop_mode": "Never",
        },
    },
    {
        "name": "Dwell Click",
        "category": "Accessibility",
        "author": "Kenan's AutoClicker",
        "description": "Clicks every 2 seconds wherever the pointer is resting, "
                       "so you can click by hovering instead of pressing.",
        "tags": ["accessibility", "assistive", "dwell"],
        "settings": {
            "mouse_enabled": True, "click_val": "2", "click_unit": "sec",
            "mouse_button": "Left", "click_type": "Single",
            "target_mode": "Cursor", "key_enabled": False, "stop_mode": "Never",
        },
    },
    {
        "name": "Key Repeat Assist",
        "category": "Accessibility",
        "author": "Kenan's AutoClicker",
        "description": "Repeats a key for you instead of holding it down. Record "
                       "the key you need, then start.",
        "tags": ["accessibility", "assistive", "keyboard"],
        "settings": {
            "mouse_enabled": False, "key_enabled": True, "key_mode": "Key",
            "key_val_int": "60", "key_unit": "ms", "stop_mode": "Never",
        },
    },
    # ---------------- Productivity ----------------
    {
        "name": "Form Filler (Tab loop)",
        "category": "Productivity",
        "author": "Kenan's AutoClicker",
        "description": "Sends Tab, Tab, Enter twice a second — for stepping "
                       "through repetitive data-entry forms.",
        "tags": ["productivity", "data-entry", "forms"],
        "settings": {
            "mouse_enabled": False, "key_enabled": True, "key_mode": "Sequence",
            "key_value": "tab tab enter", "key_val_int": "500", "key_unit": "ms",
            "stop_mode": "Never",
        },
    },
    {
        "name": "Keep Screen Awake",
        "category": "Productivity",
        "author": "Kenan's AutoClicker",
        "description": "Taps Shift once a minute so the machine doesn't sleep or "
                       "show you as idle. Shift does nothing in most apps.",
        "tags": ["productivity", "idle", "presentation"],
        "settings": {
            "mouse_enabled": False, "key_enabled": True, "key_mode": "Sequence",
            "key_value": "shift", "key_val_int": "1", "key_unit": "min",
            "stop_mode": "Never",
        },
    },
    {
        "name": "Bulk Confirm",
        "category": "Productivity",
        "author": "Kenan's AutoClicker",
        "description": "Presses Enter twice a second to work through a long run "
                       "of confirmation dialogs.",
        "tags": ["productivity", "bulk", "dialogs"],
        "settings": {
            "mouse_enabled": False, "key_enabled": True, "key_mode": "Sequence",
            "key_value": "enter", "key_val_int": "500", "key_unit": "ms",
            "stop_mode": "Count", "stop_count": "50",
        },
    },
    {
        "name": "Hold to Aim",
        "category": "Accessibility",
        "author": "Kenan's AutoClicker",
        "description": "Holds the left mouse button down until you stop, so you "
                       "don't have to keep it pressed yourself.",
        "tags": ["accessibility", "assistive", "hold"],
        "settings": {
            "mouse_enabled": True, "click_action": "Hold",
            "mouse_button": "Left", "target_mode": "Cursor",
            "key_enabled": False, "scroll_enabled": False, "stop_mode": "Never",
        },
    },
    {
        "name": "Slow Reading Scroll",
        "category": "Accessibility",
        "author": "Kenan's AutoClicker",
        "description": "Scrolls down a little every two seconds, for reading long "
                       "pages without having to scroll by hand.",
        "tags": ["accessibility", "reading", "scroll"],
        "settings": {
            "mouse_enabled": False, "key_enabled": False,
            "scroll_enabled": True, "scroll_dir": "Down",
            "scroll_val": "2", "scroll_unit": "sec", "scroll_amount": "2",
            "stop_mode": "Never",
        },
    },
    # ---------------- Testing / dev ----------------
    {
        "name": "UI Stress Test",
        "category": "Testing",
        "author": "Kenan's AutoClicker",
        "description": "Fast jittered clicking to hammer a control and surface "
                       "double-fire or race-condition bugs.",
        "tags": ["testing", "qa", "stress"],
        "settings": {
            "mouse_enabled": True, "click_val": "20", "click_unit": "ms",
            "mouse_button": "Left", "click_type": "Single",
            "target_mode": "Cursor", "jitter_on": True, "jitter_px": "4",
            "key_enabled": False, "stop_mode": "Count", "stop_count": "500",
        },
    },
    {
        "name": "Repeatable QA Run",
        "category": "Testing",
        "author": "Kenan's AutoClicker",
        "description": "Exactly 100 evenly spaced clicks with a 3 second "
                       "countdown, so a manual test is reproducible.",
        "tags": ["testing", "qa", "reproducible"],
        "settings": {
            "mouse_enabled": True, "click_val": "250", "click_unit": "ms",
            "mouse_button": "Left", "click_type": "Single",
            "target_mode": "Cursor", "key_enabled": False,
            "stop_mode": "Count", "stop_count": "100", "countdown": "3",
        },
    },
    {
        "name": "Human-like Clicking",
        "category": "Testing",
        "author": "Kenan's AutoClicker",
        "description": "Irregular timing, jitter and varied hold length — useful "
                       "for testing how software reacts to non-robotic input.",
        "tags": ["testing", "humanize", "research"],
        "settings": {
            "mouse_enabled": True, "click_val": "400", "click_unit": "ms",
            "click_rand": "150", "mouse_button": "Left", "click_type": "Single",
            "target_mode": "Cursor", "jitter_on": True, "jitter_px": "3",
            "hold_rand_on": True, "hold_min": "40", "hold_max": "110",
            "key_enabled": False, "stop_mode": "Never",
        },
    },
]


def clean_preset(raw, source="community"):
    """Validate one preset coming from disk or the internet.

    Everything here is untrusted text, so nothing is executed and only known
    setting keys survive. Returns None if the entry is unusable.
    """
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()[:60]
    if not name:
        return None
    settings = raw.get("settings")
    if not isinstance(settings, dict):
        return None
    clean = {}
    for key, val in settings.items():
        if key not in PRESET_ALLOWED_KEYS:
            continue
        if isinstance(val, bool):
            clean[key] = val
        elif isinstance(val, (int, float, str)):
            clean[key] = str(val)[:40]
    if not clean:
        return None
    tags = [str(t).strip().lower()[:24] for t in raw.get("tags", [])
            if isinstance(t, (str, int, float))][:6]
    return {
        "name": name,
        "category": str(raw.get("category", "Community")).strip()[:24] or "Community",
        "author": str(raw.get("author", "unknown")).strip()[:40] or "unknown",
        "description": " ".join(str(raw.get("description", "")).split())[:220],
        "tags": tags,
        "settings": clean,
        "source": source,
        "risky": bool(set(tags) & RISK_TAGS),
    }


# --------------------------------------------------------------------------- #
#  Local storage
# --------------------------------------------------------------------------- #
LOCAL_PRESET_PATH = os.path.join(os.path.expanduser("~"),
                                 ".kenans_autoclicker_presets.json")


def load_local_presets():
    """Presets the user imported or saved. Never raises."""
    try:
        with open(LOCAL_PRESET_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for raw in data if isinstance(data, list) else []:
        p = clean_preset(raw, source="mine")
        if p:
            out.append(p)
    return out


def save_local_preset(preset):
    """Add one preset to the local library, replacing any of the same name."""
    existing = [p for p in load_local_presets() if p["name"] != preset["name"]]
    existing.append(preset)
    try:
        with open(LOCAL_PRESET_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    except OSError:
        pass
    return existing


def settings_from_vars(tk_vars):
    """Snapshot the current setup as preset settings (allowed keys only)."""
    out = {}
    for key in sorted(PRESET_ALLOWED_KEYS):
        var = tk_vars.get(key)
        if var is None:
            continue
        try:
            out[key] = var.get()
        except Exception:
            continue
    return out


def export_preset(path, tk_vars, name=None, author=None, description="", tags=None):
    """Write the current setup to `path` in the community preset format."""
    payload = {
        "schema": PRESET_SCHEMA,
        "name": name or os.path.splitext(os.path.basename(path))[0][:60],
        "category": "Community",
        "author": author or "unknown",
        "description": description,
        "tags": list(tags or []),
        "settings": settings_from_vars(tk_vars),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


# --------------------------------------------------------------------------- #
#  Community library
# --------------------------------------------------------------------------- #
def fetch_community(url=COMMUNITY_INDEX_URL, timeout=8):
    """Fetch and validate the community index.

    Contacted only when the user asks for it. Returns (presets, error_message);
    the error is a short string so the interface can say what went wrong
    instead of failing silently.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KenansAutoClicker"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return [], f"HTTP {resp.status}"
            raw = resp.read(512_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return [], f"HTTP {e.code}"
    except urllib.error.URLError:
        return [], "no connection"
    except (OSError, ValueError):
        return [], "network error"

    try:
        data = json.loads(raw)
    except ValueError:
        return [], "bad index format"

    entries = data.get("presets") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return [], "bad index format"

    out = []
    for raw_entry in entries[:300]:
        p = clean_preset(raw_entry, source="community")
        if p:
            out.append(p)
    return out, None
