"""Keeping saved click points honest across display changes.

The most reported failure in auto clickers is saved coordinates quietly
clicking in the wrong place after the display setup changes: a different
resolution, a monitor unplugged, a laptop docked. Nothing warns you, because
a coordinate is just a pair of numbers and every pair looks valid.

So points are stored with the screen geometry they were captured on. If that
geometry no longer matches, the app can say so, and offer to scale the points
instead of silently clicking into empty space.
"""


def current_geometry(root):
    """The screen size this Tk session sees, as (width, height).

    Tk reports the primary display. That is enough to notice a resolution
    change, which is the common case; points on a secondary monitor simply fall
    outside these bounds, which `looks_offscreen` treats as worth mentioning
    rather than as an error.
    """
    try:
        return (int(root.winfo_screenwidth()), int(root.winfo_screenheight()))
    except Exception:
        return (0, 0)


def geometry_changed(saved, current):
    """True when saved points were captured on a differently sized screen."""
    if not saved or not current:
        return False
    if len(saved) != 2 or saved[0] <= 0 or saved[1] <= 0:
        return False
    return tuple(saved) != tuple(current)


def scale_points(points, saved, current):
    """Rescale points proportionally from one screen size to another."""
    if not geometry_changed(saved, current):
        return list(points)
    sw, sh = saved
    cw, ch = current
    if sw <= 0 or sh <= 0:
        return list(points)
    fx, fy = cw / sw, ch / sh
    return [(int(round(x * fx)), int(round(y * fy))) for x, y in points]


def looks_offscreen(points, current, margin=2):
    """Points that fall outside the primary screen.

    On a multi-monitor desktop these can be perfectly valid, so this is used to
    inform rather than to block: it is the difference between "this may not
    work" and pretending everything is fine.
    """
    if not current or current == (0, 0):
        return []
    w, h = current
    return [(x, y) for x, y in points
            if x < -margin or y < -margin or x > w + margin or y > h + margin]


def describe(points, saved, current):
    """A short warning for the interface, or None when everything is fine.

    Returns (message, can_rescale).
    """
    if not points:
        return None
    if geometry_changed(saved, current):
        return (f"These points were saved on a {saved[0]}x{saved[1]} screen and "
                f"yours is now {current[0]}x{current[1]}. They may click in the "
                f"wrong place.", True)
    off = looks_offscreen(points, current)
    if off:
        n = len(off)
        return (f"{n} point{'s' if n != 1 else ''} fall outside your main "
                f"screen. That is fine on a multi-monitor setup, but will miss "
                f"if that display is disconnected.", False)
    return None
