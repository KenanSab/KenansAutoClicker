# Contributing

Thanks for wanting to help. The easiest and most valuable contribution is a
**preset** — a ready-made setup someone else can use in one click.

---

## Adding a preset

### 1. Build it in the app

Set up the clicker / key presser the way you want it, then go to
**Presets → Save current as preset**. That writes a `.json` file with your
current settings already filled in.

### 2. Edit the details

Open the file and fill in the blanks:

```json
{
  "schema": 1,
  "name": "Spreadsheet Row Entry",
  "category": "Productivity",
  "author": "your-github-username",
  "description": "What it does, and when someone would want it. One or two sentences.",
  "tags": ["productivity", "data-entry"],
  "settings": {
    "key_enabled": true,
    "key_mode": "Sequence",
    "key_value": "enter",
    "key_val_int": "1",
    "key_unit": "sec"
  }
}
```

| Field | Notes |
|---|---|
| `name` | Short and descriptive. Max 60 characters. |
| `category` | `Accessibility`, `Productivity`, `Testing`, `Gaming`, or `Community`. |
| `author` | Your GitHub username — this is shown on the preset card, so you get credit. |
| `description` | Max 220 characters. Say what it does *and* who it's for. |
| `tags` | Up to 6, lowercase. Used for search. |
| `settings` | Only keys from the allow-list below. Anything else is ignored. |

### 3. Open a pull request

1. Fork the repo
2. Drop your file in `presets/`
3. Add the same object to the `presets` array in `presets/index.json`
4. Open a PR

That's it. Once merged, it appears for everyone under **Browse community**.

---

## What a preset may change

A preset can only describe **how clicking and typing behave**. It can never
touch hotkeys, the theme, window preferences, or statistics — the app strips
anything else out before applying it.

Allowed keys:

```
mouse_enabled   click_val     click_unit    click_rand
mouse_button    click_type    target_mode   fixed_x      fixed_y
smooth_move     jitter_on     jitter_px
hold_rand_on    hold_min      hold_max
burst_on        burst_n       burst_pause
key_enabled     key_mode      key_value     key_val_int  key_unit  key_rand
stop_mode       stop_count    stop_time     countdown
```

---

## Presets for online games

Presets are accepted for games, but be honest in the description about what
the preset does.

**Automating input in competitive online games usually breaks their terms of
service and can get accounts permanently banned.** If your preset targets a
competitive multiplayer game, tag it `competitive` so the app shows a warning
on the card. Presets that hide what they do, or that are framed as a way to
evade anti-cheat, will be rejected.

Single-player, idle, and AFK presets are welcome and don't need the tag.

---

## Code contributions

```bash
pip install -r requirements.txt
pip install pytest
python -m pytest tests/ -q      # 85 tests, all should pass
python KenansAutoClicker.py     # run it
```

The code is split by responsibility:

| Module | What lives there |
|---|---|
| `app.py` | Window, state, hotkeys, start/stop wiring |
| `engine.py` | Timing, humanization, the click/key loops |
| `presets.py` | Preset model, validation, community fetching |
| `ui_base.py` | Cards, rows, scrolling, theming |
| `ui_home.py` / `ui_settings.py` / `ui_presets.py` | Page content |
| `widgets.py` | Switches, segmented pickers, disclosures, icon buttons |
| `icons.py` | Lucide icons + the SVG path renderer |
| `keys.py` / `storage.py` | Key parsing; saving and loading |

Please add a test with behavior changes. If you're fixing a bug, a test that
fails before your fix is the most useful thing you can include.
