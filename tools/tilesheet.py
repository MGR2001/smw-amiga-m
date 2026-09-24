#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tilesheet.py - Renderiza los tiles CRUDOS de un fichero GFX como grilla
numerada, usando una paleta fija.  Sirve para ver que forma tiene cada tile
y asi poder decidir a mano el orden de los cuadrantes de una entrada Map16.

Uso: python tilesheet.py --gfx obj-2 --pal 5 [--from 0 --to 63]
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw

import mklvl
import palette as palmod

WORK = os.path.join(HERE, "..", "work")
SRC = mklvl._DEF_SRC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gfx", default="obj-2")
    ap.add_argument("--tileset", type=int, default=7)
    ap.add_argument("--pal", type=int, default=5)
    ap.add_argument("--from", dest="frm", type=int, default=0)
    ap.add_argument("--to", type=int, default=63)
    ap.add_argument("--cols", type=int, default=16)
    ap.add_argument("--scale", type=int, default=6)
    ap.add_argument("--out", default=None)
    ap.add_argument("--lv", default=os.path.join(
        SRC, "levels", "data", "world_1", "1", "obj.lv"))
    a = ap.parse_args()

    h, objs, lv = mklvl.build(a.lv)
    files = mklvl.gfx_files_for_tileset(a.tileset)
    gfx = mklvl.load_gfx(os.path.join(SRC, "graphics"), files)

    bank, labels = palmod.load_palette_bank(
        os.path.join(SRC, "palettes", "palettes.a"))
    cgram, bgc = palmod.build_cgram(
        bank, labels, h["fg_palette"], h["bg_palette"],
        h["spr_palette"], h["bg_color"])
    pals = [[palmod.snes_to_rgb8(c) for c in cgram[p * 16:p * 16 + 16]]
            for p in range(8)]
    colors = pals[a.pal]

    # indice del fichero dentro de la lista de bloques
    if a.gfx not in files:
        raise SystemExit("%s no esta en %s" % (a.gfx, files))
    fi = files.index(a.gfx)
    tiles = gfx[a.gfx]
    base = fi * 128
    print("bloque %d -> tiles VRAM %d..%d" % (fi, base, base + 127))

    n = a.to - a.frm + 1
    rows = (n + a.cols - 1) // a.cols
    CELL = 8
    PAD = 2
    cw, ch = CELL + PAD, CELL + PAD + 8
    img = Image.new("RGB", (a.cols * cw, rows * ch), (30, 30, 38))
    dr = ImageDraw.Draw(img)

    for i in range(n):
        tn = a.frm + i
        if tn >= len(tiles):
            break
        cx = (i % a.cols) * cw
        cy = (i // a.cols) * ch
        t = tiles[tn]
        for y in range(8):
            for x in range(8):
                v = t[y][x]
                if v == 0:
                    continue
                img.putpixel((cx + x, cy + y), colors[v & 0x0F])
        dr.text((cx, cy + 8 + 1), "%d" % tn, fill=(255, 220, 60))

    out = a.out or os.path.join(WORK, "tiles_%s_pal%d.png" % (a.gfx, a.pal))
    img.resize((img.width * a.scale, img.height * a.scale),
               Image.NEAREST).save(out)
    print("-> %s" % out)


if __name__ == "__main__":
    main()
