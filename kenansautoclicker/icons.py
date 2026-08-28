"""Lucide icons, drawn from their real SVG path data.

Icons are Lucide (https://lucide.dev), ISC License, Copyright (c) Lucide
Contributors. Rendering the paths onto a canvas keeps them crisp at any size
and lets them take the theme color, without depending on an image library.
"""

import math
import re


LUCIDE = {
    "house": [
        "M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8",
        "M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 "
        "2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    ],
    "settings": [
        "M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 "
        "0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 "
        "2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 "
        "2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 "
        "6.051a2.34 2.34 0 0 0 3.319-1.915",
        "circle:12,12,3",
    ],
    "sun": [
        "circle:12,12,4",
        "M12 2v2", "M12 20v2", "m4.93 4.93 1.41 1.41", "m17.66 17.66 1.41 1.41",
        "M2 12h2", "M20 12h2", "m6.34 17.66-1.41 1.41", "m19.07 4.93-1.41 1.41",
    ],
    "moon": [
        "M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 "
        "8.268 8.268c.344-.215.825-.004.803.401",
    ],
    "chevron-right": ["m9 18 6-6-6-6"],
    "chevron-down": ["m6 9 6 6 6-6"],
    "layers": [
        "M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 "
        "1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z",
        "M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12",
        "M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17",
    ],
    "search": ["m21 21-4.34-4.34", "circle:11,11,8"],
    "download": [
        "M12 15V3",
        "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4",
        "m7 10 5 5 5-5",
    ],
    "alert": [
        "m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3",
        "M12 9v4", "M12 17h.01",
    ],
    "crosshair": [
        "circle:12,12,10",
        "line:22,12,18,12", "line:6,12,2,12", "line:12,6,12,2", "line:12,22,12,18",
    ],
}

# --------------------------------------------------------------------------- #
#  Presets
# --------------------------------------------------------------------------- #


_PATH_TOKENS = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def _cubic(p0, p1, p2, p3, steps=14):
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        pts.append((u * u * u * p0[0] + 3 * u * u * t * p1[0]
                    + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                    u * u * u * p0[1] + 3 * u * u * t * p1[1]
                    + 3 * u * t * t * p2[1] + t * t * t * p3[1]))
    return pts


def _arc(x1, y1, rx, ry, phi_deg, large, sweep, x2, y2, steps=18):
    """SVG elliptical arc -> points (endpoint to center parameterisation, F.6.5)."""
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [(x2, y2)]
    phi = math.radians(phi_deg)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    co = math.sqrt(max(num / den, 0.0)) if den else 0.0
    if large == sweep:
        co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2.0
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2.0

    def ang(ux, uy, vx, vy):
        d = math.hypot(ux, uy) * math.hypot(vx, vy)
        if d == 0:
            return 0.0
        a = math.acos(max(-1.0, min(1.0, (ux * vx + uy * vy) / d)))
        return -a if (ux * vy - uy * vx) < 0 else a

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    th1 = ang(1, 0, ux, uy)
    dth = ang(ux, uy, vx, vy)
    if not sweep and dth > 0:
        dth -= 2 * math.pi
    elif sweep and dth < 0:
        dth += 2 * math.pi
    pts = []
    for i in range(1, steps + 1):
        t = th1 + dth * i / steps
        ct, st = math.cos(t), math.sin(t)
        pts.append((cx + rx * ct * cp - ry * st * sp,
                    cy + rx * ct * sp + ry * st * cp))
    return pts


def parse_svg_path(d):
    """Flatten an SVG path string into a list of polylines."""
    toks = [(c, n) for c, n in _PATH_TOKENS.findall(d)]
    i = 0
    cmd = None
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    prev_c2 = None
    lines = []
    poly = []

    def nums(k):
        nonlocal i
        out = []
        while len(out) < k and i < len(toks) and toks[i][0] == "":
            out.append(float(toks[i][1]))
            i += 1
        return out

    while i < len(toks):
        if toks[i][0]:
            cmd = toks[i][0]
            i += 1
        rel = cmd.islower()
        c = cmd.upper()

        if c == "M":
            v = nums(2)
            if len(v) < 2:
                break
            cur = (cur[0] + v[0], cur[1] + v[1]) if rel else (v[0], v[1])
            if len(poly) > 1:
                lines.append(poly)
            poly = [cur]
            start = cur
            cmd = "l" if rel else "L"        # subsequent pairs are implicit lineto
        elif c in "LHV":
            if c == "L":
                v = nums(2)
                if len(v) < 2:
                    break
                cur = (cur[0] + v[0], cur[1] + v[1]) if rel else (v[0], v[1])
            elif c == "H":
                v = nums(1)
                if not v:
                    break
                cur = (cur[0] + v[0], cur[1]) if rel else (v[0], cur[1])
            else:
                v = nums(1)
                if not v:
                    break
                cur = (cur[0], cur[1] + v[0]) if rel else (cur[0], v[0])
            poly.append(cur)
        elif c in "CS":
            if c == "C":
                v = nums(6)
                if len(v) < 6:
                    break
                p1 = (cur[0] + v[0], cur[1] + v[1]) if rel else (v[0], v[1])
                p2 = (cur[0] + v[2], cur[1] + v[3]) if rel else (v[2], v[3])
                p3 = (cur[0] + v[4], cur[1] + v[5]) if rel else (v[4], v[5])
            else:
                v = nums(4)
                if len(v) < 4:
                    break
                p1 = (2 * cur[0] - prev_c2[0], 2 * cur[1] - prev_c2[1]) if prev_c2 else cur
                p2 = (cur[0] + v[0], cur[1] + v[1]) if rel else (v[0], v[1])
                p3 = (cur[0] + v[2], cur[1] + v[3]) if rel else (v[2], v[3])
            poly.extend(_cubic(cur, p1, p2, p3))
            prev_c2, cur = p2, p3
            continue
        elif c == "A":
            v = nums(7)
            if len(v) < 7:
                break
            end = (cur[0] + v[5], cur[1] + v[6]) if rel else (v[5], v[6])
            poly.extend(_arc(cur[0], cur[1], v[0], v[1], v[2],
                             int(v[3]), int(v[4]), end[0], end[1]))
            cur = end
        elif c == "Z":
            if poly:
                poly.append(start)
                lines.append(poly)
                poly = [start]
            cur = start
        else:
            i += 1
            continue
        if c != "C" and c != "S":
            prev_c2 = None

    if len(poly) > 1:
        lines.append(poly)
    return lines


def draw_icon(canvas, name, size, color, stroke=2.0):
    """Render a Lucide icon onto `canvas`, scaled from its 24x24 grid."""
    k = size / 24.0
    w = max(stroke * k, 1.0)
    for shape in LUCIDE.get(name, []):
        if shape.startswith("circle:"):
            cx, cy, r = (float(v) for v in shape[7:].split(","))
            canvas.create_oval((cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k,
                               outline=color, width=w)
        elif shape.startswith("line:"):
            x1, y1, x2, y2 = (float(v) for v in shape[5:].split(","))
            canvas.create_line(x1 * k, y1 * k, x2 * k, y2 * k,
                               fill=color, width=w, capstyle="round")
        else:
            for poly in parse_svg_path(shape):
                if len(poly) > 1:
                    flat = [v * k for pt in poly for v in pt]
                    canvas.create_line(*flat, fill=color, width=w,
                                       capstyle="round", joinstyle="round",
                                       smooth=False)
