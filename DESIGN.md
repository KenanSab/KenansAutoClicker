# Design notes

Why the project is built the way it is: the decisions I made, what I traded
away, and the bugs that changed my mind.

---

## The problem

Repetitive input is an accessibility barrier before it's a convenience problem.
Interfaces usually assume you can click quickly, repeatedly, and accurately. If
you have RSI, a tremor, or limited hand mobility, that assumption quietly shuts
you out.

The same mechanism fixes ordinary problems too: stepping through hundreds of
data-entry rows, or hammering a button to reproduce a race condition in QA.

Most auto clickers are closed-source binaries that ask you to hand over control
of your mouse and keyboard, and give you no way to check what they do with it.
That's a lot of trust for nothing in return. This one is readable and tested.

---

## Decision 1: show almost nothing by default

The first version put every control on screen at once. Interval, button, click
type, targeting, coordinates, jitter, hold time, burst mode. It was complete and
it was unusable. Opening it felt like being handed a cockpit.

The rewrite starts from a narrower question: what do you actually need to start
clicking? An interval, and which mouse button. That's the whole default view,
four controls including the key presser.

Everything else sits behind a **More options** section: click type, targeting
and coordinates, all the humanization, limits, countdowns, profiles, statistics,
and the secondary hotkeys.

There's a real cost to this. Advanced features are one click less discoverable,
and a power user has to open a section to reach them, which is why the app
remembers whether you left it open. I paid that cost because the alternative is
worse: everyone pays attention tax for features most people never touch.

It took three attempts to get right. Each time, the feedback was that the
interface was cluttered, and each time that was correct.

---

## Decision 2: presets are validated, never trusted

A preset is a saved setup someone else can install in one click. As soon as
presets can be shared, they become untrusted input arriving from the internet,
so the design has to start there.

Four rules, all enforced in code rather than by convention.

**Allow-listed, not blocklisted.** `PRESET_ALLOWED_KEYS` lists the 28 settings a
preset is allowed to change. All of them are about how clicking and typing
behave. Anything else gets dropped during validation.

A blocklist would have been easier to write, and it would have been wrong. A
blocklist has to correctly guess every dangerous key in advance and keep
guessing right forever, because anything new is dangerous by default until
someone bans it. An allow-list fails the safe way round: a new setting simply
does nothing in presets until I deliberately allow it. That still holds when I
forget about it, which matters when one person maintains the project.

**Never executed.** A preset is data. Nothing in it gets evaluated, imported, or
run. There's no path from preset content to execution at all.

**Offline by default.** The app makes no network request until you press
*Browse community*. Not at startup, not for update checks, never in the
background. That also keeps antivirus heuristics quiet, which matters for an
unsigned PyInstaller binary that already looks suspicious to them.

**Previewed before applying.** Applying a preset shows the exact diff, every
setting with its old and new value, and you decide. Nothing changes silently.

So the worst a malicious preset can do is change your click interval.
[`tests/test_presets.py`](tests/test_presets.py) checks each rule. One test
feeds the validator a hostile preset that tries to rebind hotkeys, switch on
always-on-top, and rewrite the statistics, then asserts all of it was stripped.

---

## Decision 3: icons are drawn, not bundled

The interface needs about six icons. The obvious choices were an icon font or
PNGs bundled at a few resolutions.

Instead [`icons.py`](kenansautoclicker/icons.py) has a small SVG path renderer
in it: a tokenizer, cubic-bézier flattening, and endpoint-to-center elliptical
arc conversion. It draws [Lucide](https://lucide.dev)'s actual path data onto a
Tk canvas.

That's less work than it sounds (about 150 lines) and it buys three things. The
icons stay sharp at any size and any DPI, they pick up the theme color for free,
and the dependency list stays at exactly one package. Adding an image library to
display six glyphs would have roughly doubled the install size.

An earlier version drew the icons by hand out of lines and circles. They came
out approximately right and subtly wrong. Using real path data from a proper
icon set turned out to be both easier and better.

---

## The bug that taught me the most

**Symptom:** scrolling didn't work. Reported three separate times.

**What I believed:** that I'd fixed it. I had written tests. They passed.

Two real bugs did turn up on the way. `bind_all` is global, so binding the mouse
wheel once per page meant the second page silently replaced the first. And macOS
wheel deltas are small integers, so my Windows-shaped `delta / 120` arithmetic
rounded down to a scroll of exactly zero pixels.

Both were genuine bugs. Neither was the problem. Scrolling still didn't work.

**What my tests were actually testing.** The test fired
`event_generate("<MouseWheel>", delta=-120)` and checked the canvas moved. It
did move. But `event_generate` creates an event inside Tk and pushes it straight
through the binding table. It proves the handler works *if the event arrives*.
It says nothing about whether the event ever arrives.

I had tested my own code and then drawn a conclusion about the system.

**Finding it.** I wrote a harness that produced a real OS-level scroll, the same
thing a trackpad generates, and logged everything Tk actually delivered:

```
wheel events Tk delivered: 101
    ('TouchpadScroll', 1,     'Frame')
    ('TouchpadScroll', 65538, 'Frame')
    ('TouchpadScroll', 65538, 'Frame')
    ...
```

101 events. All of them `<TouchpadScroll>`. Not one `<MouseWheel>`.

**Root cause.** Tk 8.7 added a separate event for precision trackpads. On macOS
a two-finger scroll sends `<TouchpadScroll>` and does *not* also send
`<MouseWheel>`. Binding only the wheel leaves every MacBook unable to scroll,
while still passing every synthetic test, because a synthetic test names the
event it fires.

`TouchpadScroll` packs both axes into a single integer, so the handler calls
Tk's own `::tk::PreciseScrollDeltas` to unpack it rather than reimplementing the
bit layout, then scrolls by exact pixels to keep the precision the hardware
gives you.

**What I took from it.** A passing test is evidence about the thing it tests,
and nothing more. Mine tested a handler and I read it as testing scrolling. The
gap between those two claims is exactly where the bug was living: at the
boundary between my code and the operating system, which is the one place
synthetic input can't reach.

The [test](tests/test_ui.py) now checks the binding exists, and skips itself on
older Tk versions that don't have the event. There's a comment above it saying
why. The comment is the important part, because the next person to touch that
code needs to know that deleting one line breaks an entire platform in a way
nothing will catch.

---

## Holding, and the failure I most wanted to avoid

Holding a button down is a two-line feature and a genuinely dangerous one. If
the app ever stops without releasing, the button stays physically pressed. The
user is then dragging across their own desktop with no obvious cause and no
clear way to stop it, because the app that did it is no longer running.

So the release is not written at the end of the function. It sits in a `finally`
block, which runs whether the loop exits normally, the thread is torn down, or
something raises on the way. The press is tracked with a flag so a release is
only attempted if a press actually happened, and the release itself is wrapped
in its own `except` because failing to release loudly is no better than failing
quietly.

The same shape covers held keys.

[`tests/test_hold_scroll.py`](tests/test_hold_scroll.py) checks that stopping
releases the button, that holding presses exactly once rather than repeatedly,
and that an exception raised mid-hold still ends with the button released.

---

## Two smaller platform lessons

**`Key.insert` doesn't exist on macOS.** I built the key-name table by listing
every key up front, which threw `AttributeError` at import time. The app crashed
on launch, on macOS, every single time. Platform-specific enum members have to
be looked up defensively. Missing keys are now skipped, and a test asserts none
of the entries came out as `None`.

**Creating and destroying a Tk root per test aborts Python on macOS.** Exit code
133, no output, no traceback, nothing to go on. The fixture now builds one window
for the whole session and resets its state between tests instead. That's weaker
isolation, traded for a test suite that runs at all.

---

## Architecture

```
kenansautoclicker/
├── app.py           window, state, hotkeys, start/stop wiring
├── engine.py        timing, humanization, the click/key loops
├── presets.py       preset model, validation, community fetching
├── ui_base.py       cards, rows, scrolling, theming
├── ui_home.py       Home page
├── ui_presets.py    Presets page
├── ui_settings.py   Settings page
├── widgets.py       switches, segmented pickers, disclosures, icon buttons
├── icons.py         Lucide icons and the SVG path renderer
├── keys.py          key naming, serialization, sequence/combo parsing
├── storage.py       config and profile persistence
└── theme.py         color palettes
```

It started as one 1,800-line file. Splitting it wasn't cosmetic. The input engine
can now be reasoned about without building a window, presets can be tested with
no interface at all, and adding the Presets page meant writing one new module
instead of editing a monolith.

The split immediately exposed a bug that had been hiding. `engine.py` catches
`tk.TclError` but never imported `tkinter`, so typing a non-numeric value into an
interval field would have raised `NameError` instead of being handled. Inside the
single file the import happened to already be there, so nothing ever failed.

---

## What I'd do next

**A macro recorder.** Record real clicks and keystrokes with their timing and
play them back. It's the natural finish to presets: instead of configuring a
setup by hand, do the task once and save what you did.

**Dwell clicking that detects rest.** The dwell preset currently runs on a timer.
Proper assistive dwell clicking fires when the pointer has genuinely stopped
moving, which is more useful and considerably harder to get right.

**Per-application profiles.** Switch presets automatically depending on which
window has focus.

---

## Credits

Icons by [Lucide](https://lucide.dev) (ISC). Input handling by
[pynput](https://pypi.org/project/pynput/). Everything else is the Python
standard library.
