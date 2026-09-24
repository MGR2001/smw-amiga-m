#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""crop_ref.py - Recorta una zona del mapa de referencia (o de un render) por
coordenadas de PANTALLA / TILE, para comparar 1:1 contra el render.

La referencia `SuperMarioWorldMap02.png` es 5120x720 con el area de juego en
las filas 0..431 (27 filas de tiles x 16 px).  Una pantalla = 16 tiles = 256 px.
Un tile = 16 px.

Uso:
    python crop_ref.py --screen 9 --row 18 --rows 9 --out work/ref_p9.png
    python crop_ref.py --src work/level_final.png --screen 9 --row 18 --rows 9 \
        --out work/mine_p9.png
    python crop_ref.py --side ref --screen 9 --row 18 --rows 9 --out work/p9.png

`--side` arma una imagen con la referencia arriba y el render abajo, con una
linea separadora, para ver de un vistazo si coinciden.
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEF_REF = r"C:\Users\JC\Downloads\SuperMarioWorldMap02.png"
_DEF_MINE = os.path.join(_HERE, "..", "work", "level_final.png")

TILE = 16


def crop(img, screen, row, cols, rows, scale=1):
    x0 = screen * 16 * TILE
    y0 = row * TILE
    box = (x0, y0, x0 + cols * TILE, y0 + rows * TILE)
    c = img.crop(box)
    if scale != 1:
        c = c.resize((c.width * scale, c.height * scale))
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=None)
    ap.add_argument("--screen", type=int, required=True)
    ap.add_argument("--row", type=int, default=0)
    ap.add_argument("--cols", type=int, default=16)
    ap.add_argument("--rows", type=int, default=27)
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--side", choices=["ref", "mine", "both"], default="both")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    from PIL import Image

    parts = []
    if a.side in ("ref", "both"):
        ref = Image.open(_DEF_REF).convert("RGB")
        parts.append(("ref", crop(ref, a.screen, a.row, a.cols, a.rows, a.scale)))
    if a.side in ("mine", "both"):
        mine = Image.open(a.src or _DEF_MINE).convert("RGB")
        parts.append(("mine", crop(mine, a.screen, a.row, a.cols, a.rows, a.scale)))

    if len(parts) == 1:
        out = parts[0][1]
    else:
        W = max(p[1].width for p in parts)
        H = sum(p[1].height for p in parts) + 6
        out = Image.new("RGB", (W, H), (255, 0, 255))
        y = 0
        for _, p in parts:
            out.paste(p, (0, y))
            y += p.height + 6

    dst = a.out or os.path.join(_HERE, "..", "work", "crop.png")
    out.save(dst)
    print("-> %s  (%dx%d)" % (dst, out.width, out.height))
    for n, p in parts:
        print("   %-4s %dx%d" % (n, p.width, p.height))


if __name__ == "__main__":
    main()
