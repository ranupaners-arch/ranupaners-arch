#!/usr/bin/env python3
"""Bangun tombol tautan pixel-art: link_<nama>_<tema>.svg (gaya ignaciochiappero).

README menampilkan SVG lewat <img>, jadi tiap tombol adalah gambar sendiri di
dalam <a> sendiri, masing-masing sepertiga lebar kartu (width="33.3%").
Jarak antartombol digambar di dalam gambar supaya tepi luar rata dengan kartu.

Pemakaian:  python3 tools/build_links.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from build_cards import THEMES, WIDTH  # noqa: E402

PX = 3
GAP = 14
SLOT_W = WIDTH / 3
BUTTON_W = 342                       # kelipatan PX
HEIGHT = 20 * PX
LABEL_FONT = 18
ADVANCE = 0.6
ICON_GAP = 12

MONITOR = """
##########
#........#
#.#......#
#..#.....#
#.#......#
#........#
##########
....##....
..######..
"""
MONITOR_CURSOR = """
..........
..........
..........
..........
....###...
"""
XLOGO = """
##......##
.##....##.
..##..##..
...####...
....##....
...####...
..##..##..
.##....##.
##......##
"""
ENVELOPE = """
##########
##......##
#.#....#.#
#..#..#..#
#...##...#
#........#
#........#
##########
"""


def sprite(art: str) -> str:
    """Bitmap '#' -> satu <path> berpusat di (0,0), satu piksel = PX."""
    rows = [r for r in art.strip("\n").split("\n")]
    h, w = len(rows), max(len(r) for r in rows)
    ox, oy = -w * PX / 2, -h * PX / 2
    d = []
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            if row[x] == "#":
                s = x
                while x < len(row) and row[x] == "#":
                    x += 1
                d.append(f"M{ox + s*PX:g} {oy + y*PX:g}h{(x-s)*PX}v{PX}h{-(x-s)*PX}z")
            else:
                x += 1
    return "".join(d)


def monitor() -> str:
    base_rows = len(MONITOR.strip("\n").split("\n"))
    cur = sprite(MONITOR_CURSOR + "\n".join(["." * 10] * (base_rows - 5)))
    return (f'<path d="{sprite(MONITOR)}"/>'
            f'<path d="{cur}"><animate attributeName="opacity" values="1;0" '
            'keyTimes="0;0.5" dur="1.06s" calcMode="discrete" repeatCount="indefinite"/></path>')


def xlogo() -> str:
    # Lompat satu piksel tiap 2 detik.
    return ('<g><animateTransform attributeName="transform" type="translate" '
            f'values="0,0;0,-{PX};0,0" keyTimes="0;0.85;0.92" dur="2s" calcMode="discrete" '
            f'repeatCount="indefinite"/><path d="{sprite(XLOGO)}"/></g>')


def envelope() -> str:
    # Bergetar seperti notifikasi.
    return ('<g><animateTransform attributeName="transform" type="translate" '
            f'values="0,0;-{PX},0;{PX},0;-{PX},0;{PX},0;0,0" keyTimes="0;0.7;0.74;0.78;0.82;0.86" '
            f'dur="2.4s" calcMode="discrete" repeatCount="indefinite"/><path d="{sprite(ENVELOPE)}"/></g>')


LINKS = (("portfolio", "PORTFOLIO", monitor),
         ("x", "X / TWITTER", xlogo),
         ("email", "EMAIL", envelope))


def mix(a: str, b: str, t: float) -> str:
    pa = [int(a[i:i+2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def stepped(x: float, y: float, w: float, h: float) -> str:
    """Persegi panjang bersudut tangga (pixel-art)."""
    return f"M{x+PX:g} {y:g}h{w-2*PX:g}v{PX}h{PX}v{h-2*PX:g}h{-PX}v{PX}h{-(w-2*PX):g}v{-PX}h{-PX}v{-(h-2*PX):g}h{PX}z"


def build(theme: str, slot: int) -> str:
    c = THEMES[theme]
    _, label, icon = LINKS[slot]
    # Tombol ke-i mulai di i*(BUTTON_W+gap) dalam baris; dalam gambarnya sendiri
    # bergeser supaya tombol pertama rata kiri dan terakhir rata kanan.
    gap = (WIDTH - 3 * BUTTON_W) / 2
    x = slot * (BUTTON_W + gap) - slot * SLOT_W
    icon_w = 10 * PX
    label_w = len(label) * LABEL_FONT * ADVANCE
    left = x + (BUTTON_W - icon_w - ICON_GAP - label_w) / 2
    mid = HEIGHT / 2 - 1.5
    outline = mix(c["bg"], c["fg"], 0.18)
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" width="{SLOT_W:.3f}px" height="{HEIGHT}px"
     viewBox="0 0 {SLOT_W:.3f} {HEIGHT}" font-family="ConsolasFallback,Consolas,Menlo,monospace">
<style>
@font-face {{
  src: local('Consolas'), local('Consolas Bold');
  font-family: 'ConsolasFallback';
  font-display: swap;
  size-adjust: 109%;
}}
text {{white-space: pre;}}
.px {{shape-rendering: crispEdges;}}
</style>
<g class="px">
<path d="{stepped(x, 0, BUTTON_W, HEIGHT)}" fill="{outline}"/>
<path d="{stepped(x + PX, PX, BUTTON_W - 2*PX, HEIGHT - 2*PX)}" fill="{c['bg']}"/>
<rect x="{x + 2*PX:g}" y="{HEIGHT - 2*PX}" width="{BUTTON_W - 4*PX}" height="{PX}" fill="{c['key']}"/>
<g fill="{c['key']}" transform="translate({left + icon_w/2:.2f},{mid:g})">{icon()}</g>
</g>
<text x="{left + icon_w + ICON_GAP:.2f}" y="{mid + 0.35*LABEL_FONT:.2f}" font-size="{LABEL_FONT}px" fill="{c['fg']}">{label}</text>
</svg>
"""


def main() -> None:
    for theme in THEMES:
        for slot, (name, *_) in enumerate(LINKS):
            (ROOT / f"link_{name}_{theme}.svg").write_text(build(theme, slot))
    print("link_*_{dark,light}.svg dibangun.")


if __name__ == "__main__":
    main()
