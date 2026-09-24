#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quadtest.py - Compara las dos hipotesis de orden de cuadrantes de una entrada
Map16 (row-major TL,TR,BL,BR  vs  column-major TL,BL,TR,BR) y ademas muestra
los tiles crudos involucrados, para decidir cual es la correcta mirando.

Uso: python quadtest.py --idx 0x133 0x134 0x135 0x136 --tiles 0 1 16 17 32 33
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw

import mklvl
import palette as palmod
from map16 import Map16, TILESET_SET

WORK = os.path.join(HERE, "..", "work")
SRC = mklvl._DEF_SRC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idx", nargs="+", default=["0x133", "0x134", "0x135", "0x136"])
    ap.add_argument("--tiles", nargs="+", type=int, default=list(range(0, 40)))
    ap.add_argument("--tileset", type=int, default=7)
    ap.add_argument("--scale", type=int, default=14)
    ap.add_argument("--lv", default=os.path.join(
        SRC, "levels", "data", "world_1", "1", "obj.lv"))
    a = ap.parse_args()

    h, objs, lv = mklvl.build(a.lv)
    files = mklvl.gfx_files_for_tileset(a.tileset)
    gfx = mklvl.load_gfx(os.path.join(SRC, "graphics"), files)
    m16 = Map16(set_index=TILESET_SET.get(a.tileset, 0))

    bank, labels = palmod.load_palette_bank(
        os.path.join(SRC, "palettes", "palettes.a"))
    cgram, bgc = palmod.build_cgram(
        bank, labels, h["fg_palette"], h["bg_palette"],
        h["spr_palette"], h["bg_color"])
    pals = [[palmod.snes_to_rgb8(c) for c in cgram[p * 16:p * 16 + 16]]
            for p in range(8)]

    S = a.scale
    CELL = 8 * S
    GAP = 12
    LBL = 18

    def tile_img(tile10):
        """devuelve una Image 8x8 (x1) o None"""
        block = tile10 // 128
        within = tile10 % 128
        if block >= len(files) or within >= len(gfx[files[block]]):
            return None
        return gfx[files[block]][within]

    def blit(dst, dr, t, pal, ox, oy, xf=0, yf=0):
        colors = pals[pal]
        for y in range(8):
            row = t[7 - y] if yf else t[y]
            for x in range(8):
                v = row[7 - x] if xf else row[x]
                if v == 0:
                    continue
                for sy in range(S):
                    for sx in range(S):
                        dst.putpixel((ox + x * S + sx, oy + y * S + sy),
                                     colors[v & 0x0F])

    # ---- fila 1: tiles crudos ----
    tiles = a.tiles
    W = max(len(tiles) * (CELL + GAP) + GAP,
            len(a.idx) * (CELL * 2 + GAP + 30) + GAP)
    # cabecera + fila de tiles + titulo + 2 filas de hipotesis (CELL*2 de alto)
    H = LBL + GAP + CELL + GAP + LBL + LBL + 2 * (CELL * 2 + LBL) + GAP
    img = Image.new("RGB", (W, H), (28, 28, 36))
    dr = ImageDraw.Draw(img)

    dr.text((GAP, 2), "TILES CRUDOS (obj-2, paleta 5)", fill=(255, 220, 60))
    for i, tn in enumerate(tiles):
        ox = GAP + i * (CELL + GAP)
        oy = LBL + GAP
        t = tile_img(tn)
        if t is None:
            dr.rectangle([ox, oy, ox + CELL - 1, oy + CELL - 1], fill=(255, 0, 0))
        else:
            blit(img, dr, t, 5, ox, oy)
        dr.text((ox + 2, oy + CELL + 1), "%d" % tn, fill=(120, 200, 255))

    # ---- fila 2 y 3: las dos hipotesis ----
    y0 = LBL + GAP + CELL + GAP + LBL + LBL
    dr.text((GAP, y0 - LBL), "ROW-MAJOR  TL,TR,BL,BR   |   COLUMN-MAJOR  TL,BL,TR,BR",
            fill=(255, 220, 60))

    for row_i, (name, order) in enumerate([
            ("row-major", [0, 1, 2, 3]),
            ("col-major", [0, 2, 1, 3])]):
        oy = y0 + row_i * (CELL * 2 + LBL)
        ox = GAP
        for istr in a.idx:
            idx = int(istr, 0)
            e = m16.get(idx)
            dr.text((ox, oy - 12), "$%03X" % idx, fill=(255, 160, 200))
            if e is not None:
                for k, qi in enumerate(order):
                    tile10, pal, prio, xf, yf = e[qi]
                    qdx = (k % 2) * CELL
                    qdy = (k // 2) * CELL
                    if tile10 == 0:
                        continue
                    t = tile_img(tile10)
                    if t is None:
                        continue
                    blit(img, dr, t, pal, ox + qdx, oy + qdy, xf, yf)
            ox += CELL * 2 + GAP + 30

    out = os.path.join(WORK, "quadtest.png")
    img.save(out)
    print("-> %s  (%dx%d)" % (out, img.width, img.height))

    # volcado textual
    print("\nentradas:")
    for istr in a.idx:
        idx = int(istr, 0)
        e = m16.get(idx)
        if e is None:
            print("  $%03X  sin entrada" % idx)
            continue
        print("  $%03X  row-major %s" % (idx, " ".join(
            "t%03d/p%d" % (t, p) for (t, p, pr, xf, yf) in e)))
        print("         col-major %s" % " ".join(
            "t%03d/p%d" % (e[i][0], e[i][1]) for i in (0, 2, 1, 3)))


if __name__ == "__main__":
    main()
