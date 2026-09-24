#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_pipe.py - Diagnostico de las tuberias del render de Yoshi's Island 1.

Hace dos cosas independientes para separar "tile equivocado" de "colocacion
equivocada":

  A) Recorta la zona de cada tuberia del render completo (work/level.png) y la
     amplia con NEAREST -> work/pipe_crop_N.png
  B) Renderiza cada entrada Map16 usada por las tuberias como un sprite 16x16
     aislado -> work/m16_XXX.png.  Si el sprite aislado ya sale garbled, el
     problema esta en la cadena Map16 -> GFX -> VRAM (indice/bloque/paleta).
     Si el sprite sale bien, el problema esta en el handler (posicion/page).
"""

import os
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image

import mklvl
import palette as palmod
from map16 import Map16, TILESET_SET

WORK = os.path.join(HERE, "..", "work")
SRC = mklvl._DEF_SRC

# tuberias verticales del nivel (gx, gy, alto, tipo)
PIPES = [
    (7, 1, 21, 2, 0),
    (7, 8, 22, 1, 1),
    (8, 11, 20, 3, 0),
    (17, 12, 20, 3, 0),
]

# indices Map16 que el handler escribe
PIPE_IDX = [0x133, 0x134, 0x135, 0x136, 0x139, 0x13A]
# y los mismos sin el bit de pagina, para comparar
PIPE_IDX_P0 = [0x033, 0x034, 0x035, 0x036, 0x039, 0x03A]


def main():
    lv_path = os.path.join(SRC, "levels", "data", "world_1", "1", "obj.lv")
    h, objs, lv = mklvl.build(lv_path)
    ts = h["tileset"]
    files = mklvl.gfx_files_for_tileset(ts)
    print("tileset %d -> %s" % (ts, files))
    gfx = mklvl.load_gfx(os.path.join(SRC, "graphics"), files)

    setidx = TILESET_SET.get(ts, 0)
    m16 = Map16(set_index=setidx)

    bank, labels = palmod.load_palette_bank(
        os.path.join(SRC, "palettes", "palettes.a"))
    cgram, bgc = palmod.build_cgram(
        bank, labels, h["fg_palette"], h["bg_palette"],
        h["spr_palette"], h["bg_color"])
    pals = [[palmod.snes_to_rgb8(c) for c in cgram[p * 16:p * 16 + 16]]
            for p in range(8)]

    QUAD = [(0, 0), (8, 0), (0, 8), (8, 8)]

    # ---------------------------------------------------------------- B
    print("\n=== B) entradas Map16 aisladas ===")
    for idx in PIPE_IDX + PIPE_IDX_P0:
        e = m16.get(idx)
        if e is None:
            print("$%03X: SIN ENTRADA" % idx)
            continue
        desc = " ".join("t%03d/p%d%s%s" % (t, p, "/fx" if xf else "",
                                           "/fy" if yf else "")
                        for (t, p, pr, xf, yf) in e)
        print("$%03X: %s" % (idx, desc))
        img = Image.new("RGB", (16, 16), (255, 0, 255))
        px = img.load()
        for (qdx, qdy), (tile10, p, prio, xf, yf) in zip(QUAD, e):
            if tile10 == 0:
                continue
            block = tile10 // 128
            within = tile10 % 128
            if block >= len(files) or within >= len(gfx[files[block]]):
                print("   !! tile %d fuera de rango (bloque %d)" % (tile10, block))
                continue
            t = gfx[files[block]][within]
            colors = pals[p]
            for y in range(8):
                row = t[7 - y] if yf else t[y]
                for x in range(8):
                    v = row[7 - x] if xf else row[x]
                    if v == 0:
                        continue
                    px[qdx + x, qdy + y] = colors[v & 0x0F]
        out = os.path.join(WORK, "m16_%03X.png" % idx)
        img.resize((16 * 12, 16 * 12), Image.NEAREST).save(out)

    # ---------------------------------------------------------------- A
    print("\n=== A) recortes del render ===")
    full = os.path.join(WORK, "level.png")
    if not os.path.exists(full):
        print("no existe %s, salto el recorte" % full)
        return
    im = Image.open(full)
    print("render completo: %s" % (im.size,))
    scale = 2
    for i, (scr, tx, ty, hh, tp) in enumerate(PIPES):
        gx = scr * 16 + tx
        # ventana: 2 tiles de ancho + margen, alto+2 tiles
        x0 = (gx - 1) * 8 * scale
        y0 = (ty - 1) * 8 * scale
        x1 = x0 + 4 * 8 * scale
        y1 = y0 + (hh + 3) * 8 * scale
        x0 = max(0, x0); y0 = max(0, y0)
        c = im.crop((x0, y0, x1, y1))
        c = c.resize((c.width * 4, c.height * 4), Image.NEAREST)
        out = os.path.join(WORK, "pipe_crop_%d.png" % i)
        c.save(out)
        print("pipe %d  pant=%d gx=%d gy=%d alto=%d tipo=%d -> %s (%s)"
              % (i, scr, gx, ty, hh, tp, out, c.size))

    # volcado del buffer en la zona de cada tuberia
    print("\n=== buffer Map16 alrededor de cada tuberia ===")
    for i, (scr, tx, ty, hh, tp) in enumerate(PIPES):
        gx = scr * 16 + tx
        print("-- pipe %d (gx=%d gy=%d alto=%d tipo=%d)" % (i, gx, ty, hh, tp))
        for y in range(ty, min(ty + hh + 1, lv.H)):
            row = []
            for x in range(gx, gx + 2):
                w = lv.get(x, y)
                row.append("$%03X" % w if w is not None else "----")
            print("     y=%2d  %s" % (y, "  ".join(row)))


if __name__ == "__main__":
    main()
