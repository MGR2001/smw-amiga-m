#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tilematch.py - Identifica de que GFX y que tile sale un bloque 8x8 concreto
de la imagen de referencia.

Problema que resuelve: un handler de tiles.s escribe un tile number T.  El tile
number es un indice de 10 bits a VRAM; el bloque de VRAM ($0000/$0800/$1000/
$1800) lo determina T // 128, y el fichero GFX de cada bloque sale de
OBJECTGFXLIST[tileset*4 + i] (game.s:4802-4831).  Cuando el tile renderizado no
se parece a la referencia, hay que distinguir entre:

    (a) el handler escribe el tile number equivocado, o
    (b) el tile number es correcto pero el mapeo bloque->fichero esta mal.

Este script ataca (b) de forma directa: toma los pixeles REALES de la
referencia, los convierte a indices de paleta (buscando el color RGB mas
cercano dentro de la paleta del Map16) y los compara contra TODOS los tiles de
TODOS los ficheros GFX cargados.  El que mejor puntua es el que el hardware
esta usando de verdad.

Uso:
    python tilematch.py --screen 9 --col 6 --row 20 --half r --pal 4
    python tilematch.py --screen 9 --col 6 --row 20 --half r --pal 4 --top 8
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_REF = r"C:\Users\JC\Downloads\SuperMarioWorldMap02.png"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=_REF)
    ap.add_argument("--screen", type=int, required=True)
    ap.add_argument("--col", type=int, required=True, help="columna dentro de la pantalla 0..15")
    ap.add_argument("--row", type=int, required=True, help="fila 0..26")
    ap.add_argument("--half", choices=["l", "r"], default="l",
                    help="mitad izquierda o derecha del tile")
    ap.add_argument("--pal", type=int, default=None,
                    help="paleta Map16 a usar (si no, se prueban todas)")
    ap.add_argument("--tileset", type=int, default=7)
    ap.add_argument("--top", type=int, default=6)
    a = ap.parse_args()

    from PIL import Image
    import mklvl
    import palette as palmod
    from lvparse import parse_header, _DEF_SRC

    lv = os.path.join(_DEF_SRC, "levels", "data", "world_1", "1", "obj.lv")
    h = parse_header(open(lv, "rb").read())
    bank, labels = palmod.load_palette_bank(
        os.path.join(_DEF_SRC, "palettes", "palettes.a"))
    cgram, _bgc = palmod.build_cgram(bank, labels, h["fg_palette"],
                                     h["bg_palette"], h["spr_palette"],
                                     h["bg_color"])
    pals = [[palmod.snes_to_rgb8(c) for c in cgram[p * 16:p * 16 + 16]]
            for p in range(8)]

    im = Image.open(a.ref).convert("RGB")
    px = im.load()
    x0 = a.screen * 256 + a.col * 16 + (8 if a.half == "r" else 0)
    y0 = a.row * 16
    ref = [[px[x0 + x, y0 + y] for x in range(8)] for y in range(8)]

    files = mklvl.gfx_files_for_tileset(a.tileset)
    gfx = mklvl.load_gfx(os.path.join(_DEF_SRC, "graphics"), files)
    print("tileset %d -> bloques: %s" % (a.tileset, files))

    # indices de paleta de la referencia, por color RGB mas cercano
    def nearest(c, pal):
        best, bd = 0, 1 << 30
        for i, p in enumerate(pal):
            d = (c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2 + (c[2] - p[2]) ** 2
            if d < bd:
                bd, best = d, i
        return best, bd

    pal_list = [a.pal] if a.pal is not None else list(range(8))
    results = []
    for p in pal_list:
        pal = pals[p]
        idx = [[0] * 8 for _ in range(8)]
        err = 0
        for y in range(8):
            for x in range(8):
                v, d = nearest(ref[y][x], pal)
                idx[y][x] = v
                err += d
        # Se compara el INDICE de paleta, no la mascara: la mascara sola da
        # falsos positivos (muchos tiles son 100% opacos).  El indice distingue.
        for b, f in enumerate(files):
            for t, tt in enumerate(gfx[f]):
                for flip in (0, 1, 2, 3):
                    sc = 0
                    for y in range(8):
                        for x in range(8):
                            v = tt[y][x]
                            if flip & 1:
                                v = tt[y][7 - x]
                            if flip & 2:
                                v = tt[7 - y][x]
                            if v == idx[y][x]:
                                sc += 1
                    results.append((sc, p, b, f, t, flip, err))
    results.sort(key=lambda r: -r[0])
    print("\nreferencia: pantalla %d col %d fila %d mitad %s"
          % (a.screen, a.col, a.row, a.half))
    for r in results[:a.top]:
        sc, p, b, f, t, flip, err = r
        tnum = b * 128 + t
        print("  aciertos %2d/64  pal=%d  bloque=%d fichero=%-6s tile=%-3d "
              "(num VRAM $%03X)  flip=%d  (err_pal=%d)"
              % (sc, p, b, f, t, tnum, flip, err))


if __name__ == "__main__":
    main()
