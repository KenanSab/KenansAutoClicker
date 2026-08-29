"""The community preset library, backed by Supabase.

Everything here is optional. With no backend configured the app behaves exactly
as it always did: built-in presets, and the older static index on GitHub. That
matters because the library is a nicety and the app is a tool, so a service
being unreachable, unconfigured, or over quota must never stop someone clicking.

Security note: `ANON_KEY` is compiled into a desktop application, so it is
public by definition. The database is set up on that assumption (see
`supabase/schema.sql`): the key can read approved presets, insert into a queue
it cannot read back, and bump one counter. Nothing else.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .presets import clean_preset

# --------------------------------------------------------------------------- #
#  Configuration
# --------------------------------------------------------------------------- #
#: Filled in once the Supabase project exists. Environment variables override,
#: which is how the tests point at a fake server.
SUPABASE_URL = os.environ.get("KAC_SUPABASE_URL", "")
ANON_KEY = os.environ.get("KAC_SUPABASE_ANON_KEY", "")

TIMEOUT = 8
CACHE_PATH = os.path.join(os.path.expanduser("~"), ".kenans_autoclicker_library.json")
CACHE_MAX_AGE = 60 * 60 * 6          # re-fetch at most every six hours


def configured():
    """Whether a backend has been set up. Everything degrades politely if not."""
    return bool(SUPABASE_URL and ANON_KEY)


def _request(path, method="GET", body=None, token=None, extra_headers=None):
    """One REST call. Returns (parsed_json, error_message)."""
    if not configured():
        return None, "not configured"

    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path.lstrip('/')}"
    headers = {
        "apikey": ANON_KEY,
        "Authorization": f"Bearer {token or ANON_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "KenansAutoClicker",
    }
    headers.update(extra_headers or {})

    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            raw = response.read(2_000_000).decode("utf-8", "replace")
            return (json.loads(raw) if raw.strip() else None), None
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read(500).decode("utf-8", "replace")
        except Exception:
            pass
        if exc.code in (401, 403):
            return None, "not allowed"
        return None, f"HTTP {exc.code}{(': ' + detail[:80]) if detail else ''}"
    except urllib.error.URLError:
        return None, "no connection"
    except (OSError, ValueError):
        return None, "network error"


# --------------------------------------------------------------------------- #
#  Reading the library
# --------------------------------------------------------------------------- #
def fetch_library(sort="installs", limit=200):
    """Approved presets, newest or most installed first.

    Returns (presets, error). On success the result is also cached to disk so
    the library still opens when there is no network.
    """
    order = "installs.desc" if sort == "installs" else "created_at.desc"
    query = urllib.parse.urlencode({
        "select": "id,name,category,description,tags,settings,author,installs,created_at",
        "hidden": "eq.false",
        "order": order,
        "limit": str(min(int(limit), 500)),
    })
    rows, error = _request(f"presets?{query}")
    if error:
        return [], error

    presets = []
    for row in rows or []:
        preset = clean_preset(row, source="community")
        if preset is None:
            continue
        # keep the fields the library needs but the validator does not know about
        preset["id"] = str(row.get("id", ""))[:64]
        try:
            preset["installs"] = max(int(row.get("installs", 0)), 0)
        except (TypeError, ValueError):
            preset["installs"] = 0
        presets.append(preset)

    save_cache(presets)
    return presets, None


def save_cache(presets):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"fetched": time.time(), "presets": presets}, f)
    except OSError:
        pass


def load_cache():
    """The last library we saw, with its age in seconds. Never raises."""
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return [], None
    presets = []
    for row in data.get("presets", []):
        preset = clean_preset(row, source="community")
        if preset is None:
            continue
        preset["id"] = str(row.get("id", ""))[:64]
        preset["installs"] = row.get("installs", 0)
        presets.append(preset)
    fetched = data.get("fetched")
    age = (time.time() - fetched) if isinstance(fetched, (int, float)) else None
    return presets, age


def cache_is_fresh():
    _, age = load_cache()
    return age is not None and age < CACHE_MAX_AGE


# --------------------------------------------------------------------------- #
#  Writing
# --------------------------------------------------------------------------- #
def record_install(preset_id):
    """Bump the install counter. Best effort: never let this interrupt a user."""
    if not configured() or not preset_id:
        return False
    _, error = _request("rpc/increment_installs", method="POST",
                        body={"target": preset_id})
    return error is None


def submit_preset(preset, token, author, author_id):
    """Send a preset to the moderation queue. Requires a signed-in user."""
    if not configured():
        return False, "not configured"
    if not token:
        return False, "sign in first"
    payload = {
        "name": str(preset.get("name", ""))[:60],
        "category": str(preset.get("category", "Community"))[:24],
        "description": str(preset.get("description", ""))[:220],
        "tags": [str(t)[:24] for t in preset.get("tags", [])][:6],
        "settings": preset.get("settings", {}),
        "author": str(author or "unknown")[:40],
        "author_id": str(author_id or "")[:64],
    }
    _, error = _request("submissions", method="POST", body=payload, token=token,
                        extra_headers={"Prefer": "return=minimal"})
    return (error is None), error


def report_preset(preset_id, reason="", reporter_id=None):
    """Flag a preset. Three reports hide it until the maintainer looks."""
    if not configured() or not preset_id:
        return False, "not configured"
    _, error = _request("reports", method="POST",
                        body={"preset_id": preset_id,
                              "reason": str(reason or "")[:200],
                              "reporter_id": reporter_id},
                        extra_headers={"Prefer": "return=minimal"})
    return (error is None), error
