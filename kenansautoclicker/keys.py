"""Key naming, serialisation and the parsers for sequences and combos."""

from pynput.keyboard import Key, KeyCode


_KEY_ALIASES = {
    "space": "space", "enter": "enter", "return": "enter", "tab": "tab",
    "esc": "esc", "escape": "esc", "backspace": "backspace", "delete": "delete",
    "del": "delete", "insert": "insert", "up": "up", "down": "down",
    "left": "left", "right": "right", "home": "home", "end": "end",
    "pageup": "page_up", "pagedown": "page_down", "capslock": "caps_lock",
    "shift": "shift", "ctrl": "ctrl", "control": "ctrl", "alt": "alt",
    "cmd": "cmd", "win": "cmd", "super": "cmd", "meta": "cmd",
}
for _i in range(1, 21):
    _KEY_ALIASES[f"f{_i}"] = f"f{_i}"

NAMED_KEYS = {}
for _alias, _attr in _KEY_ALIASES.items():
    _k = getattr(Key, _attr, None)
    if _k is not None:
        NAMED_KEYS[_alias] = _k


def key_to_label(key):
    if key is None:
        return "None"
    if isinstance(key, KeyCode):
        if key.char is not None:
            return key.char.upper() if len(key.char) == 1 else repr(key.char)
        return f"<{key.vk}>"
    if isinstance(key, Key):
        return key.name.replace("_", " ").title()
    return str(key)


def key_to_str(key):
    if isinstance(key, KeyCode):
        return ("c:" + key.char) if key.char is not None else ("v:" + str(key.vk))
    if isinstance(key, Key):
        return "k:" + key.name
    return "k:f6"


def key_from_str(s):
    try:
        kind, val = s.split(":", 1)
        if kind == "c":
            return KeyCode.from_char(val)
        if kind == "v":
            return KeyCode.from_vk(int(val))
        if kind == "k":
            return getattr(Key, val)
    except Exception:
        pass
    return Key.f6


def parse_token(tok):
    tok = tok.strip().lower()
    if not tok:
        return None
    if tok in NAMED_KEYS:
        return NAMED_KEYS[tok]
    return KeyCode.from_char(tok[0])


def parse_sequence(text):
    """'q w e r' or 'q,w,e,r' -> list of keys, tapped in order."""
    return [k for k in (parse_token(t) for t in text.replace(",", " ").split()) if k]


def parse_combo(text):
    """'ctrl+shift+a' -> keys held together, released in reverse."""
    return [k for k in (parse_token(t) for t in text.replace(" ", "").split("+") if t) if k]
