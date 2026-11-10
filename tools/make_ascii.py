#!/usr/bin/env python3
"""Ubah avatar GitHub jadi ASCII art untuk kolom kiri kartu (gaya Andrew6rant).

Latar biru foto dibuang (jadi spasi) supaya wajah menonjol. Piksel terang
gelap dan tepi kontras dipetakan ke karakter rapat, seperti potret
Andrew6rant. Dipakai sekali saat menyiapkan kartu, bukan di workflow.

Pemakaian:  python3 tools/make_ascii.py avatar.png > tools/ascii.txt
"""
import sys

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

SRC = sys.argv[1] if len(sys.argv) > 1 else "avatar.png"
COLS, ROWS = 38, 25
CROP = (100, 112, 360, 460)          # potret: kepala + bahu
RAMP = " .'`^,:;Il!i~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@"


def main() -> None:
    rgb = Image.open(SRC).convert("RGB").crop(CROP)
    rgb = rgb.resize((COLS, ROWS), Image.LANCZOS)
    gray = ImageOps.autocontrast(Image.open(SRC).convert("L").crop(CROP), cutoff=1)
    gray = gray.filter(ImageFilter.SHARPEN)
    gray = ImageEnhance.Contrast(gray).enhance(1.25).resize((COLS, ROWS), Image.LANCZOS)
    edge = Image.open(SRC).convert("L").crop(CROP).filter(ImageFilter.FIND_EDGES)
    edge = ImageOps.autocontrast(edge, cutoff=3).resize((COLS, ROWS), Image.BOX)
    edge = edge.point(lambda v: min(255, int(v * 1.6)))
    cp, gp, ep = rgb.load(), gray.load(), edge.load()
    n = len(RAMP) - 1
    for y in range(ROWS):
        row = ""
        for x in range(COLS):
            r, g, b = cp[x, y]
            if b > r + 45 and b > g + 25:      # latar biru
                row += " "
                continue
            v = max(1 - gp[x, y] / 255, ep[x, y] / 255)
            row += RAMP[max(1, round(v * n))]
        print(row.rstrip())


if __name__ == "__main__":
    main()
