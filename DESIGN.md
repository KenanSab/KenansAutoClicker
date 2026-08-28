# Design notes

Why this project is built the way it is — the decisions, the trade-offs, and
the bugs that changed my mind.

---

## The problem

Repetitive input is an accessibility barrier before it is a convenience
problem. Interfaces routinely assume a user can click quickly, repeatedly, and
precisely. For someone with RSI, a tremor, or limited hand mobility, that
assumption quietly excludes them.

The same mechanism solves ordinary problems too — stepping through hundreds of
data-entry rows, or hammering a button to reproduce a race condition in QA.

Most auto clickers are closed-source binaries of unclear provenance that ask
you to grant them control of your mouse and keyboard. That is a lot of trust to
ask for, with nothing offered in return. This one is readable, tested, and
shareable.

---

## Decision 1 — show almost nothing by default

The first version put every control on screen: interval, button, click type,
targeting, coordinates, jitter, hold time, burst mode. It was complete, and it
was unusable. Opening it felt like being handed a cockpit.

The rewrite asks a narrower question: **what does someone actually need to
start clicking?** An interval, and which mouse button. That is the entire
default view — four controls including the key presser.

Everything else lives behind a **More options** disclosure: click type,
targeting and coordinates, all the humanisation, limits, countdowns, profiles,
statistics, and the secondary hotkeys.

The trade-off is real. Advanced features are one click less discoverable, and a
power user has to open a section every session (so the open/closed state is
remembered). I took that cost because the alternative — every user paying an
attention tax for features most of them will never touch — is worse.

This went through three iterations before it was right, each one triggered by
the interface being called cluttered. That feedback was correct every time.

---

## Decision 2 — presets are validated, never trusted

A preset is a saved setup that someone else can install in one click. The
moment presets can be shared, they become **untrusted input arriving from the
internet**, and the design has to start there.

Four rules, each enforced in code rather than by convention:

**Allow-listed, not blocklisted.** `PRESET_ALLOWED_KEYS` enumerates the ~28
settings a preset may change — all of them about how clicking and typing
behave. Anything else is dropped during validation.

A blocklist would have been easier and would be wrong. A blocklist has to
correctly predict every dangerous key, forever; every new setting is unsafe by
default until someone remembers to ban it. An allow-list fails closed — a new
setting is inert in presets until deliberately allowed. The security property
holds even when I forget about it, which is the only kind of security property
worth having in a project maintained by one person.

**Never executed.** A preset is data. Nothing in it is evaluated, imported, or
run. There is no code path from preset content to execution.

**Offline by default.** The app makes no network request until you press
*Browse community*. Not on startup, not for update checks, never in the
background. This also keeps antivirus heuristics calm, which matters for an
unsigned PyInstaller binary that is already treated with suspicion.

**Previewed before applying.** Applying a preset shows the exact diff — every
setting, old value → new value — and you choose. No silent state changes.

The blast radius of a malicious preset is therefore "your click interval
changed". [`tests/test_presets.py`](tests/test_presets.py) asserts each rule,
including a hostile preset that tries to rebind hotkeys, enable always-on-top,
and rewrite the statistics; the test asserts every one of those keys is
stripped.

---

## Decision 3 — icons are drawn, not bundled

The interface needs about six icons. The obvious options were an icon font, or
PNGs bundled at several resolutions.

Instead, [`icons.py`](kenansautoclicker/icons.py) contains a small SVG path
renderer — a tokeniser, cubic-bézier flattening, and endpoint-to-centre
elliptical arc conversion — that draws [Lucide](https://lucide.dev)'s real path
data straight onto a Tk canvas.

That sounds like more work than it is (~150 lines), and it buys three things:
icons stay crisp at any size and any DPI, they take the theme colour for free,
and the dependency list stays at exactly one package. Bundling an image library
to display six glyphs would have roughly doubled the install footprint.

An earlier version drew the icons by hand with lines and circles. They looked
approximately right and subtly wrong. Using the real path data from a
professional icon set was both easier and better.

---

## The bug that taught me the most

**Symptom:** scrolling did not work. Reported three separate times.

**What I believed:** it was fixed. I had written tests. The tests passed.

Two real bugs were found and fixed along the way — `bind_all` is global, so
binding the mouse wheel once per page meant the second page silently replaced
the first; and macOS wheel deltas are small integers, so the Windows-shaped
`delta / 120` arithmetic rounded to a scroll of exactly zero pixels.

Both were genuine. Neither was the problem. Scrolling still did not work.

**What the tests were actually testing.** My test fired
`event_generate("<MouseWheel>", delta=-120)` and asserted the canvas moved. It
did move. But `event_generate` synthesises an event *inside* Tk and dispatches
it through the binding table directly. It proves the handler works if the event
arrives. It says nothing about whether the event ever arrives.

I had tested my code, then concluded something about the system.

**Finding it.** I built a harness that produced a *real* OS-level scroll — the
same thing a trackpad generates — and logged everything Tk delivered:

```
wheel events Tk delivered: 101
    ('TouchpadScroll', 1,     'Frame')
    ('TouchpadScroll', 65538, 'Frame')
    ('TouchpadScroll', 65538, 'Frame')
    ...
```

101 events. Every one a `<TouchpadScroll>`. Zero `<MouseWheel>`.

**Root cause.** Tk 8.7 introduced a separate event for precision trackpads. On
macOS, a two-finger scroll delivers `<TouchpadScroll>` and **does not** also
deliver `<MouseWheel>`. Binding only the wheel leaves every MacBook unable to
scroll — while passing every synthetic test, because the synthetic test names
the event it fires.

`TouchpadScroll` also packs both axes into one integer, so the handler asks Tk's
own `::tk::PreciseScrollDeltas` to unpack it rather than reimplementing the bit
layout, and scrolls by exact pixels for the smooth precision the hardware
provides.

**What I took from it.** A passing test is evidence about the thing it tests.
Mine tested a handler and I read it as testing scrolling. The gap between those
two claims is exactly where the bug lived — at the boundary between my code and
the system, which is the one place synthetic input cannot reach.

The [test](tests/test_ui.py) now asserts the binding exists and skips itself on
Tk versions that predate the event, with a comment explaining why it matters.
The comment is the point: the next person to touch that code needs to know that
removing the binding breaks an entire platform silently.

---

## Two smaller platform lessons

**`Key.insert` does not exist on macOS.** The key-name table was built by
listing every key eagerly, which raised `AttributeError` at import time — the
app crashed on launch, on macOS, every time. Platform-specific enum members have
to be resolved defensively. Now missing keys are skipped, and a test asserts
none of the entries are `None`.

**Creating and destroying a Tk root per test aborts the interpreter on macOS**
— exit code 133, no output, no traceback. The fixture builds one window for the
whole session and resets its state between tests instead. Slightly less
isolation, in exchange for a suite that runs at all.

---

## Architecture

```
kenansautoclicker/
├── app.py           window, state, hotkeys, start/stop wiring
├── engine.py        timing, humanisation, the click/key loops
├── presets.py       preset model, validation, community fetching
├── ui_base.py       cards, rows, scrolling, theming
├── ui_home.py       Home page
├── ui_presets.py    Presets page
├── ui_settings.py   Settings page
├── widgets.py       switches, segmented pickers, disclosures, icon buttons
├── icons.py         Lucide icons + an SVG path renderer
├── keys.py          key naming, serialisation, sequence/combo parsing
├── storage.py       config and profile persistence
└── theme.py         colour palettes
```

It began as a single 1,800-line file. Splitting it was not cosmetic: the input
engine can now be reasoned about without constructing a window, presets can be
tested without an interface at all, and adding the Presets page meant adding one
module rather than editing a monolith.

The split immediately surfaced a latent bug — `engine.py` caught `tk.TclError`
without importing `tkinter`, so any non-numeric value typed into an interval
field would have raised `NameError` instead of being handled. It had been
invisible inside the single file, where the import happened to exist.

---

## What I would do next

**A macro recorder.** Record real clicks and keystrokes with their timing and
replay them. It is the natural completion of presets: instead of configuring a
setup by hand, do the task once and save it.

**Dwell clicking that detects rest.** The current dwell preset is on a timer.
Real assistive dwell clicking fires when the pointer has genuinely stopped
moving, which is more useful and harder to get right.

**Per-application profiles.** Switch presets automatically based on the focused
window.

---

## Credits

Icons by [Lucide](https://lucide.dev) (ISC). Input handling by
[pynput](https://pypi.org/project/pynput/). Everything else is the Python
standard library.
