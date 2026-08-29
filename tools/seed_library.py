"""Load the presets from this repository into a fresh Supabase project.

Run once, from your own machine, with the service_role key. That key bypasses
row-level security, which is exactly why it is passed as an argument and never
written to a file or committed.

    python3 tools/seed_library.py --url https://YOURS.supabase.co --key <service_role>
"""

import argparse
import glob
import json
import os
import sys
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from kenansautoclicker.presets import BUILTIN_PRESETS, clean_preset   # noqa: E402


def collect():
    """Built-in presets, plus every JSON file in presets/ except the index."""
    out, seen = [], set()
    for raw in BUILTIN_PRESETS:
        preset = clean_preset(raw, source="builtin")
        if preset and preset["name"] not in seen:
            seen.add(preset["name"])
            out.append(preset)
    for path in sorted(glob.glob(os.path.join(REPO, "presets", "*.json"))):
        if os.path.basename(path) == "index.json":
            continue
        try:
            with open(path, encoding="utf-8") as f:
                preset = clean_preset(json.load(f), source="community")
        except (OSError, ValueError):
            continue
        if preset and preset["name"] not in seen:
            seen.add(preset["name"])
            out.append(preset)
    return out


def push(url, key, presets, dry_run=False):
    rows = [{
        "name": p["name"], "category": p["category"],
        "description": p["description"], "tags": p["tags"],
        "settings": p["settings"], "author": p["author"], "risky": p["risky"],
    } for p in presets]

    if dry_run:
        print(json.dumps(rows, indent=2)[:2000])
        print(f"\n(dry run) would insert {len(rows)} presets")
        return True

    request = urllib.request.Request(
        f"{url.rstrip('/')}/rest/v1/presets",
        data=json.dumps(rows).encode(),
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(f"inserted {len(rows)} presets (HTTP {response.status})")
            return True
    except urllib.error.HTTPError as exc:
        print(f"failed: HTTP {exc.code}\n{exc.read(600).decode('utf-8', 'replace')}")
    except urllib.error.URLError as exc:
        print(f"failed: {exc}")
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="https://YOURS.supabase.co")
    parser.add_argument("--key", help="service_role key (omit with --dry-run)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be sent and stop")
    args = parser.parse_args()

    if not args.dry_run and not args.key:
        parser.error("--key is required unless you pass --dry-run")

    presets = collect()
    print(f"collected {len(presets)} presets")
    ok = push(args.url, args.key or "", presets, dry_run=args.dry_run)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
