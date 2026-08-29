"""The community library client.

Two properties matter more than the features here. The app must keep working
perfectly when there is no backend, no network, or no quota left. And the
anonymous key baked into the binary must never be able to do damage, which is
enforced in the database but relied on by this code, so the requests it makes
are pinned.
"""

import json
import time
import urllib.error

import pytest

from kenansautoclicker import cloud


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setattr(cloud, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(cloud, "ANON_KEY", "anon-test-key")
    monkeypatch.setattr(cloud, "CACHE_PATH", str(tmp_path / "cache.json"))
    return cloud


@pytest.fixture
def unconfigured(monkeypatch, tmp_path):
    monkeypatch.setattr(cloud, "SUPABASE_URL", "")
    monkeypatch.setattr(cloud, "ANON_KEY", "")
    monkeypatch.setattr(cloud, "CACHE_PATH", str(tmp_path / "cache.json"))
    return cloud


class FakeResponse:
    def __init__(self, payload, status=200):
        self._raw = json.dumps(payload).encode() if payload is not None else b""
        self.status = status

    def read(self, _n=None):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def patch_http(monkeypatch, result, capture=None):
    def fake(request, timeout=0):
        if capture is not None:
            capture.append(request)
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)
    monkeypatch.setattr(cloud.urllib.request, "urlopen", fake)


ROW = {"id": "abc-123", "name": "Test Preset", "category": "Community",
       "description": "does a thing", "tags": ["testing"],
       "settings": {"click_val": "50"}, "author": "someone", "installs": 7}


# ------------------------------------------------------- degrading politely --
def test_not_configured_by_default(unconfigured):
    assert not cloud.configured()


def test_fetch_without_a_backend_is_quiet(unconfigured):
    presets, error = cloud.fetch_library()
    assert presets == [] and error == "not configured"


def test_install_and_report_without_a_backend_do_not_raise(unconfigured):
    assert cloud.record_install("abc") is False
    ok, _ = cloud.report_preset("abc", "spam")
    assert ok is False


def test_submit_without_a_backend_explains_itself(unconfigured):
    ok, error = cloud.submit_preset({"name": "x"}, "tok", "me", "1")
    assert ok is False and error == "not configured"


@pytest.mark.parametrize("failure,expected", [
    (urllib.error.URLError("down"), "no connection"),
    (urllib.error.HTTPError("u", 500, "boom", None, None), "HTTP 500"),
    (urllib.error.HTTPError("u", 401, "nope", None, None), "not allowed"),
    (OSError("socket"), "network error"),
])
def test_network_failures_are_reported_not_raised(configured, monkeypatch,
                                                  failure, expected):
    patch_http(monkeypatch, failure)
    presets, error = cloud.fetch_library()
    assert presets == []
    assert error.startswith(expected)


# ------------------------------------------------------------------ reading --
def test_fetch_returns_validated_presets(configured, monkeypatch):
    patch_http(monkeypatch, [ROW])
    presets, error = cloud.fetch_library()
    assert error is None
    assert len(presets) == 1
    assert presets[0]["name"] == "Test Preset"
    assert presets[0]["id"] == "abc-123"
    assert presets[0]["installs"] == 7
    assert presets[0]["source"] == "community"


def test_fetch_drops_rows_that_fail_validation(configured, monkeypatch):
    patch_http(monkeypatch, [ROW, {"name": "no settings"}, {"junk": True}])
    presets, _ = cloud.fetch_library()
    assert len(presets) == 1


def test_hostile_row_cannot_smuggle_extra_settings(configured, monkeypatch):
    """A compromised database row still cannot change a user's hotkeys."""
    hostile = dict(ROW, settings={"click_val": "50", "always_top": True,
                                  "separate_hotkeys": True})
    patch_http(monkeypatch, [hostile])
    presets, _ = cloud.fetch_library()
    assert set(presets[0]["settings"]) == {"click_val"}


def test_fetch_only_asks_for_visible_rows(configured, monkeypatch):
    """Hiding is enforced by the database, but the client should not even ask
    for hidden rows, so a policy mistake does not immediately surface them."""
    seen = []
    patch_http(monkeypatch, [ROW], capture=seen)
    cloud.fetch_library()
    assert "hidden=eq.false" in seen[0].full_url


def test_sort_switches_the_ordering(configured, monkeypatch):
    seen = []
    patch_http(monkeypatch, [ROW], capture=seen)
    cloud.fetch_library(sort="installs")
    cloud.fetch_library(sort="new")
    assert "installs.desc" in seen[0].full_url
    assert "created_at.desc" in seen[1].full_url


def test_limit_is_capped(configured, monkeypatch):
    seen = []
    patch_http(monkeypatch, [ROW], capture=seen)
    cloud.fetch_library(limit=99999)
    assert "limit=500" in seen[0].full_url


# -------------------------------------------------------------------- cache --
def test_successful_fetch_populates_the_cache(configured, monkeypatch):
    patch_http(monkeypatch, [ROW])
    cloud.fetch_library()
    cached, age = cloud.load_cache()
    assert len(cached) == 1 and cached[0]["name"] == "Test Preset"
    assert age is not None and age < 5


def test_cache_survives_the_backend_disappearing(configured, monkeypatch):
    patch_http(monkeypatch, [ROW])
    cloud.fetch_library()
    patch_http(monkeypatch, urllib.error.URLError("offline"))
    live, error = cloud.fetch_library()
    assert live == [] and error == "no connection"
    cached, _ = cloud.load_cache()
    assert len(cached) == 1, "cache should still hold the last good library"


def test_missing_cache_is_not_an_error(configured):
    presets, age = cloud.load_cache()
    assert presets == [] and age is None


def test_corrupt_cache_is_not_an_error(configured, tmp_path):
    with open(cloud.CACHE_PATH, "w") as f:
        f.write("{{{ not json")
    presets, age = cloud.load_cache()
    assert presets == [] and age is None


def test_freshness_check(configured, monkeypatch):
    patch_http(monkeypatch, [ROW])
    cloud.fetch_library()
    assert cloud.cache_is_fresh()
    with open(cloud.CACHE_PATH) as f:
        data = json.load(f)
    data["fetched"] = time.time() - (cloud.CACHE_MAX_AGE + 60)
    with open(cloud.CACHE_PATH, "w") as f:
        json.dump(data, f)
    assert not cloud.cache_is_fresh()


# ------------------------------------------------------------------ writing --
def test_install_counter_uses_the_narrow_function(configured, monkeypatch):
    """Installs are counted through a function, because the anonymous key has
    no update rights on the table itself."""
    seen = []
    patch_http(monkeypatch, None, capture=seen)
    assert cloud.record_install("abc-123") is True
    assert seen[0].full_url.endswith("/rpc/increment_installs")
    assert json.loads(seen[0].data)["target"] == "abc-123"


def test_submitting_requires_a_token(configured):
    ok, error = cloud.submit_preset({"name": "x", "settings": {}}, None, "me", "1")
    assert ok is False and "sign in" in error


def test_submission_goes_to_the_queue_with_the_users_token(configured, monkeypatch):
    seen = []
    patch_http(monkeypatch, None, capture=seen)
    ok, error = cloud.submit_preset(
        {"name": "Mine", "settings": {"click_val": "5"}, "tags": ["x"]},
        "user-token", "kenan", "42")
    assert ok and error is None
    assert seen[0].full_url.endswith("/submissions")
    assert seen[0].headers["Authorization"] == "Bearer user-token"
    body = json.loads(seen[0].data)
    assert body["author"] == "kenan" and body["author_id"] == "42"


def test_submission_fields_are_truncated(configured, monkeypatch):
    seen = []
    patch_http(monkeypatch, None, capture=seen)
    cloud.submit_preset({"name": "n" * 500, "description": "d" * 900,
                         "tags": ["t"] * 40, "settings": {"click_val": "1"}},
                        "tok", "a" * 200, "1")
    body = json.loads(seen[0].data)
    assert len(body["name"]) <= 60
    assert len(body["description"]) <= 220
    assert len(body["tags"]) <= 6
    assert len(body["author"]) <= 40


def test_reporting_does_not_need_a_sign_in(configured, monkeypatch):
    seen = []
    patch_http(monkeypatch, None, capture=seen)
    ok, error = cloud.report_preset("abc-123", "spam")
    assert ok and error is None
    assert seen[0].full_url.endswith("/reports")
    assert json.loads(seen[0].data)["preset_id"] == "abc-123"


def test_report_reason_is_truncated(configured, monkeypatch):
    seen = []
    patch_http(monkeypatch, None, capture=seen)
    cloud.report_preset("abc", "why " * 200)
    assert len(json.loads(seen[0].data)["reason"]) <= 200
