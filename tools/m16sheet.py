#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m16sheet.py - Renderiza la tabla Map16 completa como una grilla.

Test auto-validante: si la cadena Map16 -> GFX -> VRAM -> paleta esta bien,
la grilla tiene que mostrar la hoja de bloques de SMW reconocible (pipes,
bloques, monedas, escaleras, etc.) en orden.  Si sale ruido, la lectura de
la tabla o el mapeo de tiles esta mal.

Uso:  python m16sheet.py [--set 0] [--tileset 7] [--out fichero.png]
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image

import mklvl
import palette as palmod
from map16 import Map16, TILESET_SET

WORK = os.path.join(HERE, "..", "work")
SRC = mklvl._DEF_SRC

QUAD = [(0, 0), (8, 0), (0, 8), (8, 8)]
# orden en que se leen las 4 palabras de la entrada Map16
ORDERS = {
    "row": [0, 1, 2, 3],   # TL,TR,BL,BR  (row-major)
    "col": [0, 2, 1, 3],   # TL,BL,TR,BR  (column-major)
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=int, default=0)
    ap.add_argument("--tileset", type=int, default=7)
    ap.add_argument("--lv", default=os.path.join(
        SRC, "levels", "data", "world_1", "1", "obj.lv"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--order", choices=["row", "col"], default="row")
    ap.add_argument("--from", dest="frm", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--to", dest="to", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--cols", type=int, default=32)
    ap.add_argument("--scale", type=int, default=3)
    a = ap.parse_args()

    h, objs, lv = mklvl.build(a.lv)
    ts = a.tileset
    files = mklvl.gfx_files_for_tileset(ts)
    print("tileset %d -> %s" % (ts, files))
    gfx = mklvl.load_gfx(os.path.join(SRC, "graphics"), files)

    m16 = Map16(set_index=a.set)
    n = len(m16.entries)
    frm = 0 if a.frm is None else a.frm
    to = n - 1 if a.to is None else a.to
    print("set_%d: %d entradas (rango $%03X..$%03X)" % (a.set, n, frm, to))

    bank, labels = palmod.load_palette_bank(
        os.path.join(SRC, "palettes", "palettes.a"))
    cgram, bgc = palmod.build_cgram(
        bank, labels, h["fg_palette"], h["bg_palette"],
        h["spr_palette"], h["bg_color"])
    pals = [[palmod.snes_to_rgb8(c) for c in cgram[p * 16:p * 16 + 16]]
            for p in range(8)]

    COLS = a.cols
    CELL = 16
    SCALE = a.scale
    ORDER = ORDERS[a.order]
    cnt = to - frm + 1
    rows = (cnt + COLS - 1) // COLS
    LBL = 11
    img = Image.new("RGB", (COLS * CELL, rows * (CELL + LBL)), (24, 24, 32))
    px = img.load()
    from PIL import ImageDraw
    dr = ImageDraw.Draw(img)

    for k, idx in enumerate(range(frm, to + 1)):
        e = m16.get(idx)
        if e is None:
            continue
        bx = (k % COLS) * CELL
        by = (k // COLS) * (CELL + LBL)
        dr.text((bx + 1, by + CELL + 1), "%03X" % idx, fill=(255, 220, 60))
        eq = [e[i] for i in ORDER]
        rq = [m16.get_raw(idx)[i] for i in ORDER]
        for (qdx, qdy), (tile10, p, prio, xf, yf), rw in zip(QUAD, eq, rq):
            if rw == 0:
                continue
            block = tile10 // 128
            within = tile10 % 128
            if block >= len(files) or within >= len(gfx[files[block]]):
                # marca roja: tile fuera de rango
                for y in range(8):
                    for x in range(8):
                        px[bx + qdx + x, by + qdy + y] = (255, 0, 0)
                continue
            t = gfx[files[block]][within]
            colors = pals[p]
            for y in range(8):
                row = t[7 - y] if yf else t[y]
                for x in range(8):
                    v = row[7 - x] if xf else row[x]
                    if v == 0:
                        continue
                    px[bx + qdx + x, by + qdy + y] = colors[v & 0x0F]

    out = a.out or os.path.join(WORK, "m16sheet_set%d.png" % a.set)
    img.resize((img.width * SCALE, img.height * SCALE), Image.NEAREST).save(out)
    print("-> %s  (%d entradas, %dx%d celdas)" % (out, cnt, COLS, rows))


if __name__ == "__main__":
    main()
