"""Presets are the one place untrusted data enters the app, so validation,
the blast radius of applying one, and the risk warnings are all pinned here.
"""

import json

import pytest

from kenansautoclicker.presets import (BUILTIN_PRESETS, PRESET_ALLOWED_KEYS,
                                       RISK_TAGS, clean_preset,
                                       fetch_community, load_local_presets,
                                       save_local_preset, settings_from_vars)


# --------------------------------------------------------------- validation --
def test_builtin_presets_are_all_valid():
    for raw in BUILTIN_PRESETS:
        assert clean_preset(raw, source="builtin") is not None, raw.get("name")


def test_builtin_presets_only_touch_allowed_keys():
    for raw in BUILTIN_PRESETS:
        unknown = set(raw["settings"]) - PRESET_ALLOWED_KEYS
        assert not unknown, f"{raw['name']} sets {unknown}"


def test_builtin_preset_names_are_unique():
    names = [p["name"] for p in BUILTIN_PRESETS]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("junk", [
    None, [], "a string", 42,
    {},                                        # no name
    {"name": "x"},                             # no settings
    {"name": "x", "settings": "not a dict"},
    {"name": "", "settings": {"click_val": "5"}},
    {"name": "x", "settings": {}},             # empty after filtering
])
def test_clean_preset_rejects_junk(junk):
    assert clean_preset(junk) is None


def test_clean_preset_strips_disallowed_keys():
    """A preset from the internet must not be able to rebind hotkeys, flip the
    theme, turn on always-on-top or rewrite the user's statistics."""
    hostile = {
        "name": "looks innocent",
        "settings": {
            "click_val": "50",
            "always_top": True,          # not allowed
            "_theme": "light",           # not allowed
            "_total_clicks": 999999,     # not allowed
            "separate_hotkeys": True,    # not allowed
            "adv_click_open": True,      # not allowed
        },
    }
    out = clean_preset(hostile)
    assert set(out["settings"]) == {"click_val"}


def test_clean_preset_truncates_hostile_strings():
    out = clean_preset({
        "name": "n" * 500,
        "description": "d" * 5000,
        "author": "a" * 500,
        "tags": ["t" * 200] * 50,
        "settings": {"click_val": "9" * 500},
    })
    assert len(out["name"]) <= 60
    assert len(out["description"]) <= 220
    assert len(out["author"]) <= 40
    assert len(out["tags"]) <= 6
    assert len(out["settings"]["click_val"]) <= 40


def test_clean_preset_preserves_booleans():
    out = clean_preset({"name": "b", "settings": {"jitter_on": True,
                                                  "mouse_enabled": False}})
    assert out["settings"]["jitter_on"] is True
    assert out["settings"]["mouse_enabled"] is False


# ------------------------------------------------------------------- risk ----
@pytest.mark.parametrize("tag", sorted(RISK_TAGS))
def test_competitive_tags_are_flagged_risky(tag):
    out = clean_preset({"name": "x", "tags": [tag],
                        "settings": {"click_val": "10"}})
    assert out["risky"] is True


def test_ordinary_presets_are_not_flagged():
    out = clean_preset({"name": "x", "tags": ["accessibility"],
                        "settings": {"click_val": "10"}})
    assert out["risky"] is False


def test_no_builtin_preset_is_risky():
    """The shipped library is accessibility/productivity/testing only."""
    for raw in BUILTIN_PRESETS:
        assert not clean_preset(raw)["risky"], raw["name"]


# ---------------------------------------------------------------- storage ----
def test_local_presets_round_trip(tmp_path, monkeypatch):
    from kenansautoclicker import presets as mod
    monkeypatch.setattr(mod, "LOCAL_PRESET_PATH", str(tmp_path / "p.json"))
    assert load_local_presets() == []
    p = clean_preset({"name": "Mine", "settings": {"click_val": "42"}}, source="mine")
    save_local_preset(p)
    back = load_local_presets()
    assert len(back) == 1 and back[0]["name"] == "Mine"
    assert back[0]["settings"]["click_val"] == "42"


def test_saving_same_name_replaces(tmp_path, monkeypatch):
    from kenansautoclicker import presets as mod
    monkeypatch.setattr(mod, "LOCAL_PRESET_PATH", str(tmp_path / "p.json"))
    save_local_preset(clean_preset({"name": "A", "settings": {"click_val": "1"}}))
    save_local_preset(clean_preset({"name": "A", "settings": {"click_val": "2"}}))
    back = load_local_presets()
    assert len(back) == 1 and back[0]["settings"]["click_val"] == "2"


def test_corrupt_local_file_is_survivable(tmp_path, monkeypatch):
    from kenansautoclicker import presets as mod
    path = tmp_path / "p.json"
    path.write_text("{{{ not json at all")
    monkeypatch.setattr(mod, "LOCAL_PRESET_PATH", str(path))
    assert load_local_presets() == []


# --------------------------------------------------------------- community ---
class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload.encode() if isinstance(payload, str) else payload
        self.status = status

    def read(self, _n=None):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_urlopen(monkeypatch, result):
    from kenansautoclicker import presets as mod

    def fake(_req, timeout=0):
        if isinstance(result, Exception):
            raise result
        return _FakeResponse(result)

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)


def test_fetch_community_parses_index(monkeypatch):
    _patch_urlopen(monkeypatch, json.dumps({"presets": [
        {"name": "Community One", "settings": {"click_val": "7"}},
        {"name": "Community Two", "settings": {"click_val": "8"}},
    ]}))
    items, err = fetch_community()
    assert err is None and len(items) == 2
    assert items[0]["source"] == "community"


def test_fetch_community_accepts_bare_list(monkeypatch):
    _patch_urlopen(monkeypatch, json.dumps(
        [{"name": "Solo", "settings": {"click_val": "7"}}]))
    items, err = fetch_community()
    assert err is None and len(items) == 1


def test_fetch_community_drops_invalid_entries(monkeypatch):
    _patch_urlopen(monkeypatch, json.dumps({"presets": [
        {"name": "Good", "settings": {"click_val": "7"}},
        {"nope": True},
        "not even an object",
    ]}))
    items, err = fetch_community()
    assert err is None and len(items) == 1


def test_fetch_community_reports_bad_json(monkeypatch):
    _patch_urlopen(monkeypatch, "not json")
    items, err = fetch_community()
    assert items == [] and err == "bad index format"


def test_fetch_community_survives_no_network(monkeypatch):
    import urllib.error
    _patch_urlopen(monkeypatch, urllib.error.URLError("offline"))
    items, err = fetch_community()
    assert items == [] and err == "no connection"


def test_fetch_community_survives_http_error(monkeypatch):
    import urllib.error
    _patch_urlopen(monkeypatch,
                   urllib.error.HTTPError("u", 404, "nope", None, None))
    items, err = fetch_community()
    assert items == [] and err == "HTTP 404"


# --------------------------------------------------------------- snapshot ----
def test_settings_from_vars_only_exports_allowed(app):
    snap = settings_from_vars(app.vars)
    assert set(snap) <= PRESET_ALLOWED_KEYS
    assert "always_top" not in snap
    assert "click_val" in snap
