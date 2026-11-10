#!/usr/bin/env python3
"""Ubah avatar GitHub jadi potret ASCII untuk kolom kiri kartu (gaya Andrew6rant).

Langkah:
  1. Latar kain biru dibuang lewat segmentasi hue/saturasi (HSV) -> spasi.
  2. Crop ketat kepala + bahu.
  3. CLAHE + unsharp mask supaya rambut, kacamata, alis, hidung, dan mulut
     kontras; tepi (Sobel) ditambahkan agar garis wajah dan kerah terlihat.
  4. Gelap -> karakter rapat (ramp " .:-=+*#%@"), seperti potret Andrew.

Grid 50 x 37 karakter untuk font 12px / baris 14px (rasio glyph ~0.52).
Dipakai sekali saat menyiapkan kartu, bukan di workflow.
Butuh: pip install opencv-python-headless numpy

Pemakaian:  python3 tools/make_ascii.py avatar.png > tools/ascii.txt
"""
import sys

import cv2
import numpy as np

SRC = sys.argv[1] if len(sys.argv) > 1 else "avatar.png"   # avatar 400x400
COLS, ROWS = 50, 37
CROP = (106, 100, 294, 370)          # x0, y0, x1, y1 pada avatar 400px
RAMP = " .:-=+*#%@"                  # terang -> rapat
CLIP, SHARP, EDGE_W, GAMMA = 5.0, 1.2, 0.9, 1.15


def foreground(img: np.ndarray) -> np.ndarray:
    """Mask orang (1) vs latar biru (0): komponen terbesar non-biru."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    blue = ((hsv[..., 0] > 95) & (hsv[..., 0] < 135) & (hsv[..., 1] > 90)).astype(np.uint8)
    blue = cv2.morphologyEx(blue, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(1 - blue)
    fg = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    return cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))


def main() -> None:
    img = cv2.imread(SRC)
    if img.shape[:2] != (400, 400):
        img = cv2.resize(img, (400, 400), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    eq = cv2.createCLAHE(clipLimit=CLIP, tileGridSize=(6, 6)).apply(gray)
    eq = cv2.addWeighted(eq, 1 + SHARP, cv2.GaussianBlur(eq, (0, 0), 3), -SHARP, 0)
    soft = cv2.GaussianBlur(gray, (0, 0), 1.5)
    edge = np.hypot(cv2.Sobel(soft, cv2.CV_32F, 1, 0), cv2.Sobel(soft, cv2.CV_32F, 0, 1))
    edge = np.clip(edge / np.percentile(edge, 97), 0, 1)

    x0, y0, x1, y1 = CROP
    size = (COLS, ROWS)
    dark = cv2.resize(1 - eq[y0:y1, x0:x1] / 255.0, size, interpolation=cv2.INTER_AREA)
    edge = cv2.resize(edge[y0:y1, x0:x1], size, interpolation=cv2.INTER_AREA)
    mask = cv2.resize(foreground(img)[y0:y1, x0:x1].astype(float), size, interpolation=cv2.INTER_AREA)
    val = np.clip(np.maximum(dark ** GAMMA, edge * EDGE_W), 0, 1)

    n = len(RAMP) - 1
    for y in range(ROWS):
        row = "".join(RAMP[max(1, round(val[y, x] * n))] if mask[y, x] > 0.5 else " "
                      for x in range(COLS))
        print(row.rstrip())


if __name__ == "__main__":
    main()
