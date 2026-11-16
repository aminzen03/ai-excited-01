#!/usr/bin/env python3
"""Make the AI judge excited — make.fun bounty ai-excited-01.

A program that writes one image to /output/entry.png.
Pure Python standard library only (zlib, struct, math, os, random).
No network, no randomness without a fixed seed: two runs write byte-identical
output. Image: a phoenix rising over a sunset lake — 1024x1024 PNG.
"""
import math
import os
import random
import struct
import zlib

W, H = 1024, 1024
OUT = "/output/entry.png"
SEED = 20261116

# ---------------------------------------------------------------- pixel buffer
buf = bytearray(W * H * 3)


def _idx(x, y):
    return (y * W + x) * 3


def put(x, y, r, g, b, a=255):
    """Set pixel with source-over alpha blending. a in 0..255."""
    if x < 0 or x >= W or y < 0 or y >= H:
        return
    if a <= 0:
        return
    i = _idx(x, y)
    if a >= 255:
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b
    else:
        inv = 255 - a
        buf[i] = (r * a + buf[i] * inv) // 255
        buf[i + 1] = (g * a + buf[i + 1] * inv) // 255
        buf[i + 2] = (b * a + buf[i + 2] * inv) // 255


def lerp(c1, c2, t):
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def clamp(v, lo=0, hi=255):
    return lo if v < lo else hi if v > hi else v


# ------------------------------------------------------------------ gradients
def vgrad(y0, y1, stops):
    """Fill rows y0..y1 with a vertical multi-stop gradient. stops: [(t, rgb)]."""
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(1, (y1 - y0))
        for k in range(len(stops) - 1):
            t0, c0 = stops[k]
            t1, c1 = stops[k + 1]
            if t0 <= t <= t1:
                f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                r, g, b = lerp(c0, c1, f)
                break
        else:
            r, g, b = stops[-1][1]
        row = y * W * 3
        for x in range(W):
            i = row + x * 3
            buf[i] = r
            buf[i + 1] = g
            buf[i + 2] = b


# -------------------------------------------------------------------- shapes
def fill_circle(cx, cy, rad, color, alpha=255):
    r2 = rad * rad
    for y in range(max(0, cy - rad), min(H, cy + rad + 1)):
        dy = y - cy
        dx = int(math.sqrt(max(0, r2 - dy * dy)))
        for x in range(max(0, cx - dx), min(W, cx + dx + 1)):
            put(x, y, color[0], color[1], color[2], alpha)


def fill_ellipse(cx, cy, rx, ry, color, alpha=255):
    for y in range(max(0, cy - ry), min(H, cy + ry + 1)):
        dy = (y - cy) / ry
        rem = 1.0 - dy * dy
        if rem < 0:
            continue
        dx = int(rx * math.sqrt(rem))
        for x in range(max(0, cx - dx), min(W, cx + dx + 1)):
            put(x, y, color[0], color[1], color[2], alpha)


def fill_rot_ellipse(cx, cy, a, b, ang_deg, color, alpha=255):
    """Rotated ellipse via parametric polygon (24 segments), scanline fill."""
    th = math.radians(ang_deg)
    ct, st = math.cos(th), math.sin(th)
    pts = []
    for k in range(28):
        t = 2.0 * math.pi * k / 28.0
        px = a * math.cos(t)
        py = b * math.sin(t)
        pts.append((cx + int(px * ct - py * st), cy + int(px * st + py * ct)))
    fill_poly(pts, color, alpha)


def fill_poly(pts, color, alpha=255):
    """Scanline polygon fill (even-odd)."""
    if not pts:
        return
    ys = [p[1] for p in pts]
    y0, y1 = max(0, min(ys)), min(H - 1, max(ys))
    n = len(pts)
    for y in range(y0, y1 + 1):
        xs = []
        for k in range(n):
            x1, y1p = pts[k]
            x2, y2p = pts[(k + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                xs.append(x1 + (y - y1p) * (x2 - x1) / (y2p - y1p))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa, xb = int(math.ceil(xs[k])), int(math.floor(xs[k + 1]))
            for x in range(max(0, xa), min(W - 1, xb) + 1):
                put(x, y, color[0], color[1], color[2], alpha)


def thick_line(x0, y0, x1, y1, rad, color, alpha=255):
    """A thick line drawn as a chain of filled circles."""
    dist = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(dist / max(1, rad // 2)))
    for k in range(steps + 1):
        t = k / steps
        fill_circle(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t),
                    rad, color, alpha)


def bezier(p0, p1, p2, steps):
    pts = []
    for k in range(steps + 1):
        t = k / steps
        u = 1.0 - t
        pts.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return pts


def sparkle(cx, cy, arm, color, alpha=255):
    thick_line(cx - arm, cy, cx + arm, cy, 1, color, alpha)
    thick_line(cx, cy - arm, cx, cy + arm, 1, color, alpha)
    put(cx, cy, color[0], color[1], color[2], alpha)


# --------------------------------------------------------------------- scene
SKY_STOPS = [
    (0.00, (11, 16, 53)),
    (0.35, (42, 26, 94)),
    (0.55, (123, 45, 139)),
    (0.75, (232, 67, 147)),
    (1.00, (255, 126, 61)),
]
LAKE_STOPS = [
    (0.00, (232, 126, 61)),
    (0.30, (123, 45, 107)),
    (0.65, (43, 26, 74)),
    (1.00, (11, 16, 53)),
]
SUN = (512, 565)
HORIZON = 640


def draw_sky():
    vgrad(0, HORIZON, SKY_STOPS)


def draw_stars(rng):
    for _ in range(170):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, 520)
        r = rng.choice((1, 1, 1, 2))
        a = rng.randint(120, 255)
        col = rng.choice(((255, 255, 255), (255, 244, 200), (200, 225, 255)))
        fill_circle(x, y, r, col, a)
        if rng.random() < 0.06:
            sparkle(x, y, rng.randint(3, 5), col, a)


def draw_clouds():
    clouds = [
        (190, 140, 110, 20, (255, 150, 180), 82),
        (830, 110, 120, 22, (255, 190, 150), 74),
        (660, 250, 100, 16, (255, 150, 180), 86),
        (320, 330, 90, 15, (255, 190, 150), 78),
        (890, 380, 80, 14, (255, 150, 180), 72),
    ]
    for cx, cy, rx, ry, col, a in clouds:
        fill_ellipse(cx, cy, rx, ry, col, a)


def draw_sun():
    # glow: radial falloff in a bounding box
    gx, gy, gr = SUN[0], SUN[1], 340
    for y in range(max(0, gy - gr), min(HORIZON + 60, gy + gr + 1)):
        dy = y - gy
        for x in range(max(0, gx - gr), min(W, gx + gr + 1)):
            dx = x - gx
            d = math.sqrt(dx * dx + dy * dy)
            if d < gr:
                f = 1.0 - d / gr
                put(x, y, 255, 179, 71, int(96 * f * f))
    # disc: concentric rings, bright core to warm edge
    for r in range(106, 0, -4):
        t = r / 106.0
        col = lerp((255, 243, 196), (255, 126, 61), t)
        fill_circle(SUN[0], SUN[1], r, col)


def draw_lake():
    vgrad(HORIZON, H - 1, LAKE_STOPS)


def ridge_y(x, base, a1, f1, p1, a2, f2, p2):
    return base + a1 * math.sin(x * f1 + p1) + a2 * math.sin(x * f2 + p2)


def draw_mountains():
    # far ridge
    pts = [(x, int(ridge_y(x, 600, 46, 0.006, 1.2, 18, 0.017, 4.0)))
           for x in range(0, W + 1, 8)]
    pts += [(W, HORIZON), (0, HORIZON)]
    fill_poly(pts, (59, 42, 107))
    # snow caps on far peaks
    for x in range(40, W - 40, 8):
        y = ridge_y(x, 600, 46, 0.006, 1.2, 18, 0.017, 4.0)
        yl = ridge_y(x - 8, 600, 46, 0.006, 1.2, 18, 0.017, 4.0)
        yr = ridge_y(x + 8, 600, 46, 0.006, 1.2, 18, 0.017, 4.0)
        if y < yl and y < yr and y < 566:
            fill_poly([(x, int(y) + 4), (x - 26, int(y) + 34),
                       (x + 26, int(y) + 34)], (232, 228, 255), 235)
    # near ridge
    pts = [(x, int(ridge_y(x, 622, 30, 0.009, 3.1, 12, 0.023, 0.7)))
           for x in range(0, W + 1, 8)]
    pts += [(W, HORIZON), (0, HORIZON)]
    fill_poly(pts, (36, 26, 74))


def draw_reflection():
    # sun column on the lake
    for y in range(HORIZON, H):
        fall = 1.0 - (y - HORIZON) / (H - HORIZON)
        wob = 0.75 + 0.25 * math.sin(y * 0.11)
        half = int(62 * (0.6 + 0.4 * math.sin(y * 0.05 + 1.0)))
        for x in range(SUN[0] - half, SUN[0] + half + 1):
            edge = 1.0 - abs(x - SUN[0]) / max(1, half)
            a = int(150 * fall * wob * edge)
            put(x, y, 255, 170, 80, a)
    # ripples
    rng = random.Random(SEED + 7)
    for y in range(HORIZON + 14, H - 4, 13):
        base_a = 34 + int(34 * (1.0 - (y - HORIZON) / (H - HORIZON)))
        for x in range(50, W - 50):
            w = 0.55 + 0.45 * math.sin(x * 0.045 + y * 0.35)
            if rng.random() < 0.5:
                col = (255, 190, 120) if abs(x - SUN[0]) < 90 else (170, 150, 220)
                put(x, y + int(2 * math.sin(x * 0.03 + y)), col[0], col[1],
                    col[2], int(base_a * w))


FEATHER_COLORS = [
    (255, 209, 102),  # gold
    (255, 123, 47),   # orange
    (255, 94, 58),    # flame
    (217, 4, 41),     # deep red
    (53, 240, 208),   # cyan accent tip
]


def draw_phoenix():
    # wing base shapes (dark crimson, behind feathers — kept inside the fan)
    fill_poly([(478, 415), (335, 195), (210, 255), (255, 425), (370, 475),
               (460, 450)], (107, 18, 48))
    fill_poly([(546, 415), (689, 195), (814, 255), (769, 425), (654, 475),
               (564, 450)], (107, 18, 48))
    # feather fans, radiating from the shoulders
    for side in (-1, 1):
        sx = 478 if side < 0 else 546
        sy = 415
        for k in range(9):
            # angles sweep upward-outward; 0 = east, screen y down
            ang = (-168 + k * 11) if side < 0 else (-12 - k * 11)
            # mirror: left wing angles point up-left, right wing up-right
            if side < 0:
                ang = -180 + (k * 11) + 12  # -168 .. -80
            else:
                ang = -12 - k * 11          # -12 .. -100
            leng = 200 + 130 * math.sin(math.pi * (k + 0.5) / 9.0)
            if k == 0:  # outer accent feather: slimmer, shorter
                leng *= 0.88
            th = math.radians(ang)
            dx, dy = math.cos(th), math.sin(th)
            cx = sx + dx * leng * 0.52
            cy = sy + dy * leng * 0.52
            col = FEATHER_COLORS[4] if k == 0 else FEATHER_COLORS[k % 4]
            fill_rot_ellipse(int(cx), int(cy), int(leng * 0.55),
                             18 if k == 0 else 27, ang, col)
            # spine line
            thick_line(sx, sy, int(sx + dx * leng * 0.92),
                       int(sy + dy * leng * 0.92), 2, (107, 18, 48), 150)
    # tail plumes: three flowing bezier ribbons, gold -> cyan tips
    tails = [
        ((512, 500), (380, 640), (300, 780)),
        ((512, 505), (512, 660), (512, 800)),
        ((512, 500), (644, 640), (724, 780)),
    ]
    for p0, p1, p2 in tails:
        pts = bezier(p0, p1, p2, 110)  # dense steps -> smooth ribbon, no beads
        for k, (px, py) in enumerate(pts):
            t = k / max(1, len(pts) - 1)
            col = lerp((255, 209, 102), (53, 240, 208), t * t)
            rad = max(3, int(17 * (1.0 - t) + 3))
            fill_circle(int(px), int(py), rad, col)
    # body
    fill_rot_ellipse(512, 425, 46, 96, -8, (139, 30, 63))
    fill_rot_ellipse(512, 425, 34, 80, -8, (171, 41, 77))
    # gold chest highlight
    fill_rot_ellipse(498, 395, 14, 34, -8, (255, 209, 102), 110)
    # head + beak + crest
    fill_circle(512, 318, 27, (255, 209, 102))
    fill_circle(512, 318, 23, (139, 30, 63))
    fill_poly([(530, 310), (560, 322), (530, 330)], (255, 209, 102))
    for k, (dx, dy) in enumerate(((-14, -18), (-20, -8), (-22, 2))):
        thick_line(500, 300, 500 + dx, 300 + dy, 2, (255, 209, 102), 230)
    # eye
    fill_circle(521, 311, 5, (255, 255, 255))
    fill_circle(522, 311, 2, (10, 10, 20))


def draw_foreground():
    fill_poly([(0, H), (0, 905), (120, 940), (260, 985), (330, H)],
              (18, 10, 46))
    fill_poly([(W, H), (W, 915), (905, 945), (780, 990), (700, H)],
              (18, 10, 46))
    # pines on the rocks
    for bx, by, s in ((90, 905, 46), (180, 940, 36), (930, 915, 44),
                      (845, 945, 34)):
        fill_poly([(bx, by - s), (bx - s // 2, by), (bx + s // 2, by)],
                  (14, 8, 38))
        fill_poly([(bx, by - s * 2 // 3), (bx - s // 3, by - s // 3),
                   (bx + s // 3, by - s // 3)], (14, 8, 38))


def draw_vignette():
    col_f = [1.0 - 0.30 * ((x - W / 2) / (W / 2)) ** 2 for x in range(W)]
    row_f = [1.0 - 0.30 * ((y - H / 2) / (H / 2)) ** 2 for y in range(H)]
    for y in range(H):
        rf = row_f[y]
        base = y * W * 3
        for x in range(W):
            f = col_f[x] * rf
            i = base + x * 3
            buf[i] = int(buf[i] * f)
            buf[i + 1] = int(buf[i + 1] * f)
            buf[i + 2] = int(buf[i + 2] * f)


# ------------------------------------------------------------------ png out
def png_chunk(typ, data):
    return (struct.pack(">I", len(data)) + typ + data +
            struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))


def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: None
        raw += buf[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) +
            png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
            png_chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def main():
    rng = random.Random(SEED)
    draw_sky()
    draw_stars(rng)
    draw_clouds()
    draw_sun()
    draw_lake()
    draw_mountains()
    draw_reflection()
    draw_phoenix()
    draw_foreground()
    draw_vignette()
    size = write_png(OUT)
    print("wrote %s (%d bytes, %dx%d)" % (OUT, size, W, H))


if __name__ == "__main__":
    main()
