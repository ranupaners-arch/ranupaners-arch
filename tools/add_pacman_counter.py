#!/usr/bin/env python3
"""Tambah hitungan commit berjalan ke SVG pacman (abozanona/pacman-contribution-graph).

Tiap kotak kontribusi di SVG punya <animate attributeName="fill"> yang
mengganti warnanya ke warna kosong saat pacman memakannya. Skrip ini:
  1. Membaca waktu makan tiap kotak (c-<minggu>-<hari>) dari keyTimes.
  2. Mengambil jumlah kontribusi per hari lewat GraphQL contributionCalendar
     (sumber data yang sama dengan generator) dan memetakannya ke kotak
     dengan rumus tanggal yang sama (53 minggu, berakhir di minggu ini).
  3. Menyisipkan "Commit: N" di bawah grid. N naik tepat saat kotak dimakan,
     sinkron dengan dur & repeatCount animasi pacman (SMIL, tanpa JS).
  4. Generator memakan kotak terakhir tepat di frame terakhir lalu langsung
     mengulang, jadi semua animasi diberi jeda HOLD_MS di akhir (keyTimes
     diskalakan, nilai terakhir ditahan) agar total akhir sempat terlihat.

Pemakaian (token hanya dari env, tidak pernah ditulis ke berkas):
  ACCESS_TOKEN=... USER_NAME=ranupaners-arch \
  python3 tools/add_pacman_counter.py pacman_dark.svg:dark pacman_light.svg:light
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.request

USER_NAME = os.environ.get("USER_NAME") or "ranupaners-arch"
GRID_WIDTH = 53
EXTRA_H = 26                      # ruang tambahan di bawah grid untuk penghitung
PALETTE = {                        # sama dengan kartu neofetch
    "dark": {"key": "#ffa657", "value": "#a5d6ff", "cc": "#616e7f"},
    "light": {"key": "#953800", "value": "#0a3069", "cc": "#8c959f"},
}
FONT = "ConsolasFallback,Consolas,Menlo,monospace"
MARK = "pacman-counter"
HOLD_MS = 3000                     # jeda di akhir putaran untuk menampilkan total


def fetch_calendar() -> dict[dt.date, int]:
    token = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("ERROR: set ACCESS_TOKEN atau GITHUB_TOKEN di environment.")
    query = """query($login: String!) { user(login: $login) { contributionsCollection {
      contributionCalendar { weeks { contributionDays { date contributionCount } } } } } }"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": USER_NAME}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if data.get("errors"):
        sys.exit(f"GraphQL error: {data['errors']}")
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {dt.date.fromisoformat(d["date"]): d["contributionCount"]
            for w in weeks for d in w["contributionDays"]}


def cell_counts(svg: str, calendar: dict[dt.date, int]) -> dict[tuple[int, int], int]:
    """Petakan tanggal ke kotak persis seperti buildGrid() di generator."""
    m = re.search(r"<generatedOn>([^<]+)</generatedOn>", svg)
    today = dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).date() if m else dt.date.today()
    latest = max((d for d, c in calendar.items() if c > 0), default=today)
    end = max(today, latest)
    weekday = (end.weekday() + 1) % 7                    # Minggu = 0 (getUTCDay)
    start = end - dt.timedelta(days=(GRID_WIDTH - 1) * 7 + weekday)
    cells = {}
    for d, c in calendar.items():
        if start <= d <= end and c > 0:
            cells[((d - start).days // 7, (d.weekday() + 1) % 7)] = c
    return cells


def eat_times(svg: str) -> tuple[dict[tuple[int, int], float], str, str]:
    """Waktu (0..1) tiap kotak berubah ke warna kosong, plus dur & repeatCount."""
    times, dur, rep = {}, None, "indefinite"
    pat = re.compile(r'<rect id="c-(\d+)-(\d+)"[^>]*fill="([^"]+)">\s*<animate attributeName="fill" '
                     r'dur="([^"]+)" repeatCount="([^"]+)"[^>]*?values="([^"]+)"\s*keyTimes="([^"]+)"')
    for m in pat.finditer(svg):
        x, y, empty, dur, rep, values, keys = m.groups()
        vals, kts = values.split(";"), [float(k) for k in keys.split(";")]
        for v, k in zip(vals[1:], kts[1:]):
            if v == empty:
                times[(int(x), int(y))] = k
                break
    if dur is None:
        dur = re.search(r'id="pacman"[\s\S]*?dur="([^"]+)"', svg).group(1)
    return times, dur, rep


def counter_svg(events: list[tuple[float, int]], dur: str, rep: str, theme: str, y: float) -> str:
    c = PALETTE[theme]
    label = "Commit: "
    vx = len(label) * 8.4                                 # 14px monospace ~0.6em
    parts = [f'<g id="{MARK}" font-family="{FONT}" font-size="14px">',
             f'<text x="0" y="{y}" fill="{c["key"]}">Commit<tspan fill="{c["cc"]}">:</tspan></text>']
    steps = [(0.0, 0)] + events
    for i, (t, v) in enumerate(steps):
        nxt = steps[i + 1][0] if i + 1 < len(steps) else None
        if i == 0 and nxt is None:
            anim = ""
        elif i == 0:
            anim = f'values="visible;hidden" keyTimes="0;{nxt:.4f}"'
        elif nxt is None:
            anim = f'values="hidden;visible" keyTimes="0;{t:.4f}"'
        else:
            anim = f'values="hidden;visible;hidden" keyTimes="0;{t:.4f};{nxt:.4f}"'
        vis = "visible" if i == 0 else "hidden"
        a = (f'<animate attributeName="visibility" dur="{dur}" repeatCount="{rep}" '
             f'calcMode="discrete" {anim}/>') if anim else ""
        parts.append(f'<text x="{vx:.1f}" y="{y}" fill="{c["value"]}" visibility="{vis}">{v:,}{a}</text>')
    parts.append("</g>")
    return "".join(parts)


def add_hold(svg: str, dur: str) -> str:
    """Perpanjang semua animasi ber-dur `dur` sebanyak HOLD_MS, tahan frame akhir."""
    d = float(dur.rstrip("ms")) if dur.endswith("ms") else float(dur.rstrip("s")) * 1000
    scale = d / (d + HOLD_MS)

    def fix(m: re.Match) -> str:
        tag = m.group(0)
        if f'dur="{dur}"' not in tag or "keyTimes" not in tag:
            return tag
        kt = re.search(r'keyTimes="([^"]+)"', tag)
        vs = re.search(r'values="([^"]+)"', tag)
        keys = [float(k) * scale for k in kt.group(1).split(";")]
        vals = vs.group(1).split(";")
        keys.append(1.0)
        vals.append(vals[-1])
        tag = tag.replace(kt.group(0), 'keyTimes="' + ";".join(f"{k:.5f}" for k in keys) + '"')
        tag = tag.replace(vs.group(0), 'values="' + ";".join(vals) + '"')
        return tag.replace(f'dur="{dur}"', f'dur="{d + HOLD_MS:.0f}ms"')

    return re.sub(r"<animate(?:Transform)?\b[^>]*>", fix, svg)


def process(path: str, theme: str, calendar: dict[dt.date, int]) -> int:
    svg = open(path, encoding="utf-8").read()
    if MARK in svg:
        sys.exit(f"{path}: penghitung sudah ada (jalankan pada SVG hasil generator).")
    times, dur, rep = eat_times(svg)
    counts = cell_counts(svg, calendar)
    missing = [k for k in counts if k not in times]
    if missing:
        print(f"PERINGATAN {path}: {len(missing)} kotak berisi kontribusi tidak dimakan: {missing[:5]}")
    byt: dict[float, int] = {}
    for k, t in times.items():
        if counts.get(k, 0) > 0:
            byt[t] = byt.get(t, 0) + counts[k]
    events, total = [], 0
    for t in sorted(byt):
        total += byt[t]
        events.append((t, total))

    m = re.search(r'<svg width="(\d+)" height="(\d+)"', svg)
    w, h = int(m.group(1)), int(m.group(2))
    svg = svg.replace(m.group(0), f'<svg width="{w}" height="{h + EXTRA_H}"', 1)
    svg = svg.replace("</svg>", counter_svg(events, dur, rep, theme, h + 12) + "</svg>")
    svg = add_hold(svg, dur)
    open(path, "w", encoding="utf-8").write(svg)
    print(f"{path}: {len(events)} langkah, total {total:,} (kalender {sum(counts.values()):,})")
    return total


def main() -> None:
    calendar = fetch_calendar()
    for arg in sys.argv[1:]:
        path, theme = arg.rsplit(":", 1)
        process(path, theme, calendar)


if __name__ == "__main__":
    main()
