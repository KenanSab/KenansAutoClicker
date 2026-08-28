"""Record the README demo animation.

Drives the real application through a short scripted tour, captures a frame at
each step, and assembles them into a GIF with ffmpeg. Regenerating the demo is
therefore a command rather than a screen-recording session, so it can be redone
whenever the interface changes.

    python3 tools/make_demo.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter as tk

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

WORK = tempfile.mkdtemp(prefix="kac-demo-")
from kenansautoclicker import presets as P, storage        # noqa: E402

storage.CONFIG_PATH = os.path.join(WORK, "cfg.json")
P.LOCAL_PRESET_PATH = os.path.join(WORK, "presets.json")

from kenansautoclicker.app import AutoClickerApp           # noqa: E402

OUT = os.path.join(REPO, "docs", "demo.gif")
WIDTH, HEIGHT = 600, 620      # short enough to clear the Dock
POS = "+120+40"
FPS = 2                       # a slideshow pace; each frame is a beat


def main():
    root = tk.Tk()
    app = AutoClickerApp(root)
    root.geometry(f"{WIDTH}x{HEIGHT}{POS}")
    root.update()

    frames = []

    def shot(hold=1):
        """Capture the window, repeating the frame to hold it on screen.

        The geometry is re-asserted every time: the app sizes itself to its
        content on startup, and an over-tall window ends up with the Dock
        sitting on top of it in the capture.
        """
        root.geometry(f"{WIDTH}x{HEIGHT}{POS}")
        root.update()
        root.lift()
        root.update()
        time.sleep(0.35)
        x, y = root.winfo_rootx(), root.winfo_rooty()
        w, h = root.winfo_width(), root.winfo_height()
        for _ in range(hold):
            path = os.path.join(WORK, f"f{len(frames):03d}.png")
            subprocess.run(["screencapture", "-x", "-R", f"{x},{y},{w},{h}", path],
                           check=True)
            frames.append(path)

    # 1. the plain default view
    app.show_page("home")
    shot(3)

    # 2. holding instead of clicking
    app.vars["click_action"].set("Hold")
    app._refresh_action_ui()
    shot(2)

    # 3. dwell, with its own settings appearing
    app.vars["click_action"].set("Dwell")
    app._refresh_action_ui()
    shot(3)
    app.vars["click_action"].set("Click")
    app._refresh_action_ui()

    # 4. the advanced section opening
    app.vars["adv_click_open"].set(True)
    shot(3)
    app.vars["adv_click_open"].set(False)

    # 5. auto scroll switched on
    app.vars["scroll_enabled"].set(True)
    shot(2)

    # 6. a recorded macro
    app.macro_events = [
        {"t": i * 0.4, "type": "click", "x": 400, "y": 300,
         "button": "left", "down": i % 2 == 0} for i in range(14)
    ]
    app.vars["macro_enabled"].set(True)
    app._refresh_macro_label()
    canvas = app.pages["home"].canvas
    canvas.yview_moveto(1.0)
    shot(3)
    canvas.yview_moveto(0)

    # 7. the preset library
    app.show_page("presets")
    shot(3)

    # 8. previewing a preset, which is the idea worth showing
    app._preview_preset(P.clean_preset(P.BUILTIN_PRESETS[0]))
    root.update()
    time.sleep(0.4)
    dialog = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    # sit the dialog over the app so the frame is the same size as every other
    # one, and so the animation reads as a dialog opening rather than a cut
    dialog.geometry(f"480x440+{120 + 60}+{40 + 90}")
    dialog.update()
    time.sleep(0.4)
    shot(4)
    dialog.destroy()

    # 9. light theme, back home
    app.show_page("home")
    app.toggle_theme()
    shot(3)

    root.destroy()
    print(f"captured {len(frames)} frames")

    # --- normalize -----------------------------------------------------------
    # Captures are not all the same size, because the preview dialog is smaller
    # than the window. A mid-stream resolution change breaks the palette filter
    # and silently collapses the animation to a handful of frames, so every
    # frame is padded onto one canvas first.
    widths, heights = [], []
    for path in frames:
        info = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                              capture_output=True, text=True).stdout
        widths.append(int(info.split("pixelWidth:")[1].split()[0]))
        heights.append(int(info.split("pixelHeight:")[1].split()[0]))
    box_w, box_h = max(widths), max(heights)

    padded = []
    for i, path in enumerate(frames):
        out = os.path.join(WORK, f"p{i:03d}.png")
        subprocess.run(["sips", "--padToHeightWidth", str(box_h), str(box_w),
                        "--padColor", "0B0D13", path, "--out", out],
                       check=True, capture_output=True)
        padded.append(out)
    print(f"normalized {len(padded)} frames to {box_w}x{box_h}")

    # --- assemble -----------------------------------------------------------
    chain = ("scale=720:-1:flags=lanczos,split[a][b];"
             "[a]palettegen=max_colors=128[p];"
             "[b][p]paletteuse=dither=bayer:bayer_scale=3")
    result = subprocess.run(
        ["ffmpeg", "-y", "-framerate", str(FPS), "-start_number", "0",
         "-i", os.path.join(WORK, "p%03d.png"),
         "-filter_complex", chain, "-loop", "0", OUT],
        capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr[-1200:])
        raise SystemExit("ffmpeg failed")

    # a GIF that quietly lost its frames still looks like a success, so check
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of",
         "default=noprint_wrappers=1:nokey=1", OUT],
        capture_output=True, text=True)
    written = int((probe.stdout or "0").strip() or 0)
    size = os.path.getsize(OUT)
    print(f"wrote {os.path.relpath(OUT, REPO)}  {size / 1024:.0f} KB, {written} frames")
    if written < len(frames) * 0.9:
        raise SystemExit(f"only {written} of {len(frames)} frames survived")
    if size > 8 * 1024 * 1024:
        print("  warning: over 8MB, GitHub will be slow to render it")


if __name__ == "__main__":
    keep = "--keep" in sys.argv
    try:
        main()
    finally:
        if keep:
            print("frames kept in", WORK)
        else:
            shutil.rmtree(WORK, ignore_errors=True)
