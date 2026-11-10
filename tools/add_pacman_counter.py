#!/usr/bin/env python3
"""Tambah hitungan commit berjalan ke SVG pacman (abozanona/pacman-contribution-graph).

Tiap kotak kontribusi di SVG punya <animate attributeName="fill"> yang
mengganti warnanya ke warna kosong saat pacman memakannya. Skrip ini:
  1. Membaca waktu makan tiap kotak (c-<minggu>-<hari>) dari keyTimes.
  2. Mengambil jumlah kontribusi per hari lewat GraphQL contributionCalendar
     (sumber data yang sama dengan generator) dan memetakannya ke kotak
     dengan rumus tanggal yang sama (53 minggu, berakhir di minggu ini).
  3. Menyisipkan "Commit: N" di bawah grid. Saat kotak dimakan, angka
     bergulir naik satu-satu (gaya odometer, melambat di akhir), berkilau
     kuning sambil membesar sedikit, dan "+N" kecil melayang lalu memudar.
     Semua SMIL (tanpa JS), sinkron dengan dur & repeatCount pacman.
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
import math
import os
import re
import sys
import urllib.request

USER_NAME = os.environ.get("USER_NAME") or "ranupaners-arch"
GRID_WIDTH = 53
EXTRA_H = 26                      # ruang tambahan di bawah grid untuk penghitung
PALETTE = {                        # sama dengan kartu neofetch; flash = kilau saat makan
    "dark": {"key": "#ffa657", "value": "#a5d6ff", "cc": "#616e7f", "flash": "#ffd33d"},
    "light": {"key": "#953800", "value": "#0a3069", "cc": "#8c959f", "flash": "#bf8700"},
}
FONT = "ConsolasFallback,Consolas,Menlo,monospace"
MARK = "pacman-counter"
HOLD_MS = 3000                     # jeda di akhir putaran untuk menampilkan total
TICK = 0.05                        # detik per langkah angka bergulir (20 fps)
EASE = 0.3                         # porsi sisa yang ditambahkan tiap langkah
FLOAT_S = 0.7                      # lama "+N" melayang lalu hilang


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


def ms(d: str) -> float:
    return float(d[:-2]) if d.endswith("ms") else float(d.rstrip("s")) * 1000


def roll_frames(events: list[tuple[float, int]], length: float) -> list[tuple[float, int]]:
    """Simulasikan angka yang 'mengejar' total sebenarnya (gaya odometer).

    Tiap TICK detik angka naik ceil(sisa * EASE): kenaikan kecil langsung
    selesai, kenaikan besar bergulir ~0.5-1 detik lalu melambat tepat di
    total. Kalau kotak berikutnya dimakan saat masih bergulir, target ikut
    naik (berantai), jadi tidak pernah meloncat dan selalu berakhir tepat.
    """
    frames, shown, i, target, t = [(0.0, 0)], 0, 0, 0, 0.0
    while t < length:
        while i < len(events) and events[i][0] <= t + 1e-9:
            target = events[i][1]
            i += 1
        if shown < target:
            shown += max(1, math.ceil((target - shown) * EASE))
            frames.append((t, shown))
        t = round(t + TICK, 6)
    return frames


def pulse_track(starts: list[float], length: float, rise: float, fall: float,
                peak: str, base: str) -> tuple[str, str]:
    """keyTimes/values linear: naik ke `peak` lalu kembali ke `base` per event."""
    pts = [(0.0, base)]
    for j, t in enumerate(starts):
        nxt = starts[j + 1] if j + 1 < len(starts) else length
        if t <= pts[-1][0]:
            continue
        pts.append((t, base))
        a = min(t + rise, nxt - 1e-3)
        pts.append((a, peak))
        b = min(a + fall, nxt - 2e-3)
        if b > a:
            pts.append((b, base))
    if pts[-1][0] < length:
        pts.append((length, pts[-1][1]))
    kt = ";".join(f"{x / length:.5f}" for x, _ in pts)
    return kt, ";".join(v for _, v in pts)


def counter_svg(events: list[tuple[float, int]], length_ms: float, rep: str,
                theme: str, y: float) -> str:
    """events: (detik dimakan, total berjalan) pada linimasa sepanjang length_ms."""
    c = PALETTE[theme]
    L = length_ms / 1000
    dur = f"{length_ms:.0f}ms"
    vx = len("Commit: ") * 8.4                           # 14px monospace ~0.6em
    total = events[-1][1] if events else 0
    px = vx + len(f"{total:,}") * 8.4 + 10                # posisi "+N"
    head = f'dur="{dur}" repeatCount="{rep}"'
    parts = [f'<g id="{MARK}" font-family="{FONT}" font-size="14px">',
             f'<text x="0" y="{y}" fill="{c["key"]}">Commit<tspan fill="{c["cc"]}">:</tspan></text>']

    # Angka bergulir: satu <text> per nilai, tampil diskret pada jendela waktunya.
    starts = [t for t, _ in events]
    kt, vals = pulse_track(starts, L, 0.06, 0.35, c["flash"], c["value"])
    skt, svals = pulse_track(starts, L, 0.06, 0.30, "1.22", "1")
    parts.append(f'<g transform="translate({vx:.1f},{y})"><g fill="{c["value"]}">'
                 f'<animate attributeName="fill" {head} calcMode="linear" keyTimes="{kt}" values="{vals}"/>'
                 f'<animateTransform attributeName="transform" type="scale" {head} calcMode="linear" '
                 f'keyTimes="{skt}" values="{svals}"/>')
    frames = roll_frames(events, L)
    for j, (t, v) in enumerate(frames):
        nxt = frames[j + 1][0] if j + 1 < len(frames) else None
        if j == 0:
            anim = f'values="visible;hidden" keyTimes="0;{nxt / L:.5f}"' if nxt is not None else ""
        elif nxt is None:
            anim = f'values="hidden;visible" keyTimes="0;{t / L:.5f}"'
        else:
            anim = f'values="hidden;visible;hidden" keyTimes="0;{t / L:.5f};{nxt / L:.5f}"'
        a = f'<animate attributeName="visibility" {head} calcMode="discrete" {anim}/>' if anim else ""
        parts.append(f'<text visibility="{"visible" if j == 0 else "hidden"}">{v:,}{a}</text>')
    parts.append("</g></g>")

    # "+N" kecil yang naik dan memudar di samping angka.
    prev = 0
    for j, (t, v) in enumerate(events):
        n, prev = v - prev, v
        nxt = events[j + 1][0] if j + 1 < len(events) else L
        # Hanya satu "+N" tampil: yang lama hilang saat kotak berikutnya dimakan.
        a, b = t / L, max(min(t + FLOAT_S, nxt, L), t + 0.02) / L
        parts.append(
            f'<text x="{px:.1f}" y="{y}" font-size="12px" fill="{c["flash"]}" opacity="0">+{n:,}'
            f'<animate attributeName="opacity" {head} calcMode="linear" '
            f'keyTimes="0;{a:.5f};{a + 0.00001:.5f};{b:.5f};1" values="0;0;1;0;0"/>'
            f'<animateTransform attributeName="transform" type="translate" {head} calcMode="linear" '
            f'keyTimes="0;{a:.5f};{b:.5f};1" values="0,0;0,0;0,-12;0,-12"/></text>')
    parts.append("</g>")
    return "".join(parts), len(frames)


def add_hold(svg: str, dur: str) -> str:
    """Perpanjang semua animasi ber-dur `dur` sebanyak HOLD_MS, tahan frame akhir."""
    d = ms(dur)
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
    svg = add_hold(svg, dur)
    D = ms(dur)
    sec = [(t * D / 1000, v) for t, v in events]
    block, nframes = counter_svg(sec, D + HOLD_MS, rep, theme, h + 12)
    svg = svg.replace("</svg>", block + "</svg>")
    open(path, "w", encoding="utf-8").write(svg)
    print(f"{path}: {len(events)} event, {nframes} frame angka, total {total:,} (kalender {sum(counts.values()):,})")
    return total


def main() -> None:
    calendar = fetch_calendar()
    for arg in sys.argv[1:]:
        path, theme = arg.rsplit(":", 1)
        process(path, theme, calendar)


if __name__ == "__main__":
    main()
