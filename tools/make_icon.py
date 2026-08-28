"""Generate the application icon.

The icon is drawn with the same canvas code the app uses for its interface, so
it stays consistent with the product and needs no image library. It is written
out as a PNG, then packaged as .icns for macOS and .ico for Windows.

Run from the repository root:

    python3 tools/make_icon.py
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import tkinter as tk

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from kenansautoclicker.theme import THEMES          # noqa: E402

OUT = os.path.join(REPO, "docs")
SIZE = 512                                          # drawn at 1x, captured at 2x


def draw(canvas, s):
    """A cursor with a click ripple, on the app's accent color."""
    C = THEMES["dark"]
    k = s / 512.0

    def P(*v):
        return [x * k for x in v]

    # rounded square backdrop
    r = 112 * k
    canvas.create_oval(0, 0, 2 * r, 2 * r, fill=C["accent"], outline=C["accent"])
    canvas.create_oval(s - 2 * r, 0, s, 2 * r, fill=C["accent"], outline=C["accent"])
    canvas.create_oval(0, s - 2 * r, 2 * r, s, fill=C["accent"], outline=C["accent"])
    canvas.create_oval(s - 2 * r, s - 2 * r, s, s, fill=C["accent"], outline=C["accent"])
    canvas.create_rectangle(r, 0, s - r, s, fill=C["accent"], outline=C["accent"])
    canvas.create_rectangle(0, r, s, s - r, fill=C["accent"], outline=C["accent"])

    # Click ripple: arcs radiating from the cursor tip. The radii are chosen so
    # the widest arc still clears the artwork edge; anything larger is clipped
    # by the canvas and the icon looks broken at small sizes.
    tip_x, tip_y = 200, 240
    for radius, width in ((130, 22), (185, 18)):
        canvas.create_arc(*P(tip_x - radius, tip_y - radius,
                             tip_x + radius, tip_y + radius),
                          start=28, extent=104, style="arc",
                          outline="#ffffff", width=width * k)

    # cursor arrow
    canvas.create_polygon(
        *P(200, 240, 200, 429, 245, 386, 277, 451, 310, 434, 277, 370, 337, 362),
        fill="#ffffff", outline="#ffffff", width=8 * k, joinstyle="round")


def render_png(path, size):
    root = tk.Tk()
    root.overrideredirect(True)
    root.geometry(f"{size}x{size}+60+60")
    canvas = tk.Canvas(root, width=size, height=size, highlightthickness=0,
                       bg=THEMES["dark"]["bg"])
    canvas.pack()
    draw(canvas, size)
    root.update()
    root.lift()
    root.update()
    time.sleep(0.6)
    x, y = root.winfo_rootx(), root.winfo_rooty()
    subprocess.run(["screencapture", "-x", "-R", f"{x},{y},{size},{size}", path],
                   check=True)
    root.destroy()
    return path


def write_ico(png_paths, out_path):
    """Write a Windows .ico containing PNG-compressed entries.

    Vista and later accept PNG data directly inside an ICO, so the file is a
    small header plus the PNGs themselves. That avoids needing an image library
    purely to produce one icon.
    """
    images = []
    for path in png_paths:
        with open(path, "rb") as f:
            images.append(f.read())

    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)        # reserved, type=icon, count
    # each directory entry is 16 bytes: 4 bytes of dimensions, 4 of plane/depth,
    # then two 32-bit fields for the image size and its offset
    ENTRY = 16
    offset = 6 + ENTRY * count
    entries, blobs = b"", b""
    for data, path in zip(images, png_paths):
        side = int(os.path.basename(path).split("_")[-1].split(".")[0])
        entries += struct.pack(
            "<BBBBHHII",
            0 if side >= 256 else side,               # 0 means 256
            0 if side >= 256 else side,
            0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    with open(out_path, "wb") as f:
        f.write(header + entries + blobs)
    return out_path


def main():
    os.makedirs(OUT, exist_ok=True)
    work = tempfile.mkdtemp(prefix="kac-icon-")
    try:
        master = render_png(os.path.join(work, "master.png"), SIZE)

        # a single PNG for the README and any web use
        shutil.copy(master, os.path.join(OUT, "icon.png"))

        sizes = [16, 32, 48, 64, 128, 256, 512]
        scaled = []
        for side in sizes:
            path = os.path.join(work, f"icon_{side}.png")
            subprocess.run(["sips", "-z", str(side), str(side), master, "--out", path],
                           check=True, capture_output=True)
            scaled.append(path)

        # --- macOS ---
        iconset = os.path.join(work, "KenansAutoClicker.iconset")
        os.makedirs(iconset, exist_ok=True)
        for side in (16, 32, 128, 256, 512):
            subprocess.run(["sips", "-z", str(side), str(side), master,
                            "--out", os.path.join(iconset, f"icon_{side}x{side}.png")],
                           check=True, capture_output=True)
            subprocess.run(["sips", "-z", str(side * 2), str(side * 2), master,
                            "--out", os.path.join(iconset, f"icon_{side}x{side}@2x.png")],
                           check=True, capture_output=True)
        icns = os.path.join(OUT, "icon.icns")
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)

        # --- Windows ---
        ico = write_ico([p for p in scaled if int(os.path.basename(p).split("_")[-1]
                                                  .split(".")[0]) <= 256],
                        os.path.join(OUT, "icon.ico"))

        for path in (os.path.join(OUT, "icon.png"), icns, ico):
            print(f"  {os.path.relpath(path, REPO):22} {os.path.getsize(path):>8,} bytes")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
