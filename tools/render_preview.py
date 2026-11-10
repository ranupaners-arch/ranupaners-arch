#!/usr/bin/env python3
"""Render pratinjau README (kartu + tombol [+ pacman]) dengan Chrome headless.

Pemakaian:  python3 tools/render_preview.py <folder-output>
Menghasilkan dark.png, light.png, links_dark.png, links_light.png,
full_dark.png, full_light.png.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/profile-readme-preview")
OUT.mkdir(parents=True, exist_ok=True)
PAGE = {"dark": "#0d1117", "light": "#ffffff"}


def shot(name: str, body: str, bg: str, w: int, h: int) -> None:
    html = OUT / f"_{name}.html"
    html.write_text(f"<html><body style='margin:0;padding:16px;background:{bg}'>"
                    f"<div style='width:{w - 32}px'>{body}</div></body></html>")
    subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu",
                    "--hide-scrollbars", "--virtual-time-budget=1500",
                    f"--window-size={w},{h}", f"--screenshot={OUT / (name + '.png')}",
                    html.as_uri()], check=True, capture_output=True)
    html.unlink()


def img(f: str, w: str = "100%") -> str:
    return f"<img src='{(ROOT / f).as_uri()}' width='{w}' style='display:block'>"


for t, bg in PAGE.items():
    shot(t, img(f"{t}_mode.svg"), bg, 1132, 582)
    links = "<div style='display:flex'>" + "".join(
        img(f"link_{n}_{t}.svg", "33.3%") for n in ("portfolio", "x", "email")) + "</div>"
    shot(f"links_{t}", links, bg, 1132, 92)
    pac = img(f"pacman_{t}.svg") if (ROOT / f"pacman_{t}.svg").exists() else ""
    shot(f"full_{t}", img(f"{t}_mode.svg") + "<div style='height:12px'></div>" + links
         + "<div style='height:12px'></div>" + pac, bg, 1132, 960 if pac else 680)
print(f"pratinjau di {OUT}")
