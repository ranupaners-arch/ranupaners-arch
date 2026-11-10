#!/usr/bin/env python3
"""Bangun dark_mode.svg & light_mode.svg dengan tata letak gaya Andrew6rant.

Kolom kiri: ASCII art avatar (tools/ascii.txt). Kolom kanan: info ala
neofetch dengan titik penyambung yang rata kanan. Nilai dinamis diberi id
(age_data, repo_data, ...) lalu diisi ulang oleh today.py tiap hari.

Pemakaian:  python3 tools/build_cards.py
"""
from __future__ import annotations

import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from today import COL, LINE_W, dots, layout  # noqa: E402

ASCII = (ROOT / "tools" / "ascii.txt").read_text().rstrip("\n").split("\n")

THEMES = {
    "dark": dict(bg="#161b22", fg="#c9d1d9", key="#ffa657", value="#a5d6ff",
                 add="#3fb950", dele="#f85149", cc="#616e7f"),
    "light": dict(bg="#f6f8fa", fg="#24292f", key="#953800", value="#0a3069",
                  add="#1a7f37", dele="#cf222e", cc="#c2cfde"),
}

WIDTH, HEIGHT = 1100, 550
ASCII_X, INFO_X, TOP, LH = 15, 390, 30, 20

USER = "ranupane@kukerjain"
INFO = [
    ("OS", "macOS, Android"),
    ("Uptime", None),
    ("Host", "kukerjain.dev"),
    ("Kernel", "Mahasiswa Pendidikan Bahasa Arab, Institut Muslim Cendekia"),
    ("IDE", "VS Code, Orca, Pencil.dev"),
    None,
    ("Languages.Programming", "Dart, TypeScript, JavaScript, Python"),
    ("Languages.Computer", "HTML, CSS, JSON, YAML, Markdown"),
    ("Languages.Real", "Indonesia, Arab, English"),
    None,
    ("Hobbies.Software", "Web & App Development"),
    ("Hobbies.Real", "Puisi (Aan Mansyur)"),
]
CONTACT = [
    ("Email", "halo@kukerjain.dev"),
    ("Website", "kukerjain.dev"),
    ("X", "@kukerjainweb"),
    ("GitHub", "ranupaners-arch"),
]
# Nilai awal sebelum today.py jalan (akan ditimpa).
SAMPLE = dict(age_data="22 years, 4 months, 16 days", repo_data=0, contrib_data=0,
              star_data=0, commit_data=0, follower_data=0, loc_data=0, loc_add=0, loc_del=0)


def rule(label: str) -> str:
    """'label -————...-—-' sepanjang LINE_W, seperti header Andrew."""
    n = LINE_W - len(label) - len(" -") - len("-—-")
    return " -" + "—" * max(n, 3) + "-—-"


def key(k: str) -> str:
    return ".".join(f'<tspan class="key">{escape(p)}</tspan>' for p in k.split("."))


def tspan(y: int, body: str = "") -> str:
    return f'<tspan x="{INFO_X}" y="{y}" class="cc">. </tspan>{body}'


def kv(y: int, k: str, v: str) -> str:
    d = dots(LINE_W - len(". ") - len(k) - 1 - len(v))
    return tspan(y, f'{key(k)}:<tspan class="cc">{d}</tspan><tspan class="value">{escape(v)}</tspan>')


def build(theme: str) -> str:
    c = THEMES[theme]
    v = layout(SAMPLE)
    s = lambda i: f'<tspan class="value" id="{i}">{escape(v[i])}</tspan>'  # noqa: E731
    d = lambda i: f'<tspan class="cc" id="{i}_dots">{v[i + "_dots"]}</tspan>'  # noqa: E731

    out = [f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,Menlo,monospace" width="{WIDTH}px" height="{HEIGHT}px" font-size="16px">
<style>
@font-face {{
src: local('Consolas'), local('Consolas Bold');
font-family: 'ConsolasFallback';
font-display: swap;
-webkit-size-adjust: 109%;
size-adjust: 109%;
}}
.key {{fill: {c['key']};}}
.value {{fill: {c['value']};}}
.addColor {{fill: {c['add']};}}
.delColor {{fill: {c['dele']};}}
.cc {{fill: {c['cc']};}}
text, tspan {{white-space: pre;}}
</style>
<rect width="{WIDTH}px" height="{HEIGHT}px" fill="{c['bg']}" rx="15"/>
<text x="{ASCII_X}" y="{TOP}" fill="{c['fg']}" class="ascii">"""]
    for i, row in enumerate(ASCII):
        out.append(f'<tspan x="{ASCII_X}" y="{TOP + i * LH}">{escape(row)}</tspan>')
    out.append(f'</text>\n<text x="{INFO_X}" y="{TOP}" fill="{c["fg"]}">')

    y = TOP
    out.append(f'<tspan x="{INFO_X}" y="{y}">{USER}</tspan>{rule(USER)}')
    for item in INFO:
        y += LH
        if item is None:
            out.append(tspan(y))
        elif item[1] is None:
            out.append(tspan(y, f'{key(item[0])}:{d("age_data")}{s("age_data")}'))
        else:
            out.append(kv(y, *item))
    y += 2 * LH
    out.append(f'<tspan x="{INFO_X}" y="{y}">- Contact</tspan>{rule("- Contact")}')
    for item in CONTACT:
        y += LH
        out.append(kv(y, *item))
    y += 2 * LH
    out.append(f'<tspan x="{INFO_X}" y="{y}">- GitHub Stats</tspan>{rule("- GitHub Stats")}')
    y += LH
    out.append(tspan(y, f'{key("Repos")}:{d("repo_data")}{s("repo_data")} {{{key("Contributed")}: '
                        f'{s("contrib_data")}}} | {key("Stars")}:{d("star_data")}{s("star_data")}'))
    y += LH
    out.append(tspan(y, f'{key("Commits")}:{d("commit_data")}{s("commit_data")} | '
                        f'{key("Followers")}:{d("follower_data")}{s("follower_data")}'))
    y += LH
    out.append(tspan(y, f'{key("Lines of Code on GitHub")}:{d("loc_data")}{s("loc_data")} ( '
                        f'<tspan class="addColor" id="loc_add">{v["loc_add"]}</tspan><tspan class="addColor">++</tspan>, '
                        f'<tspan class="delColor" id="loc_del">{v["loc_del"]}</tspan><tspan class="delColor">--</tspan> )'))
    y += 2 * LH
    # Kursor prompt berkedip (seperti kartu ignaciochiappero).
    out.append(f'<tspan x="{INFO_X}" y="{y}" class="key">&gt; </tspan><tspan class="value">█'
               '<animate attributeName="opacity" values="1;0" dur="1.06s" calcMode="discrete" '
               'repeatCount="indefinite"/></tspan>')
    out.append("</text>\n</svg>\n")
    assert y + 20 <= HEIGHT and TOP + (len(ASCII) - 1) * LH + 20 <= HEIGHT
    return "\n".join(out)


def main() -> None:
    for theme in THEMES:
        (ROOT / f"{theme}_mode.svg").write_text(build(theme))
    print(f"dark_mode.svg & light_mode.svg ({WIDTH}x{HEIGHT}) dibangun.")


if __name__ == "__main__":
    main()
