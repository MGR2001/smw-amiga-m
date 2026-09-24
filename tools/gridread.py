#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gridread.py - Lee la GRILLA DE CUADRANTES (8x8) real de la imagen de
referencia.

Un bloque de 16x16 de SMW no es un tile: son CUATRO cuadrantes de 8x8, y cada
cuadrante puede venir de un tile distinto (incluso de un fichero GFX distinto).
Comparar un bloque de 16x16 contra un tile de 8x8 repetido 2x2 no puede dar
match exacto nunca; hay que comparar cuadrante a cuadrante.

Este script, para cada cuadrante de 8x8 de una region dada, busca el
(tile, paleta, flip) que reproduce EXACTO el patron de indices de color de la
referencia (en espacio de 5 bits).  Imprime la grilla resultante: es la forma
de sacarle la geometria a un handler sin trazarlo a mano.

Uso:
    python gridread.py --screen 3 --row 18 --cols 8 --rows 5
    python gridread.py --screen 3 --row 18 --cols 8 --rows 5 --cand C4,C5,5A,5B
    python gridread.py --screen 3 --row 18 --cols 8 --rows 5 --min 64 --verbose
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_REF = r"C:\Users\JC\Downloads\SuperMarioWorldMap02.png"
TILE = 16

# posicion de cada cuadrante dentro del bloque, en el orden en que los guarda
# la tabla Map16 (column-major: word0=TL word1=BL word2=TR word3=BR)
QUADS = [("TL", 0, 0), ("BL", 0, 8), ("TR", 8, 0), ("BR", 8, 8)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=_REF)
    ap.add_argument("--screen", type=int, required=True)
    ap.add_argument("--row", type=int, required=True)
    ap.add_argument("--col", type=int, default=0)
    ap.add_argument("--cols", type=int, default=16)
    ap.add_argument("--rows", type=int, default=1)
    ap.add_argument("--tileset", type=int, default=7)
    ap.add_argument("--cand", default=None,
                    help="tile numbers VRAM candidatos (hex, separados por coma)")
    ap.add_argument("--min", type=int, default=63,
                    help="aciertos minimos sobre 64 (default 63)")
    ap.add_argument("--verbose", action="store_true",
                    help="imprime los 4 mejores de cada cuadrante")
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
    # a 5 bits: la referencia expande 5->8 con <<3
    pals5 = [[(c[0] >> 3, c[1] >> 3, c[2] >> 3) for c in pal] for pal in pals]

    files = mklvl.gfx_files_for_tileset(a.tileset)
    gfx = mklvl.load_gfx(os.path.join(_DEF_SRC, "graphics"), files)

    cands = []
    if a.cand:
        for n in [int(x, 16) for x in a.cand.split(",")]:
            b, w = n // 128, n % 128
            if b < len(files) and w < len(gfx[files[b]]):
                cands.append((n, b, w, gfx[files[b]][w]))
    else:
        for b, f in enumerate(files):
            for t, tt in enumerate(gfx[f]):
                cands.append((b * 128 + t, b, t, tt))

    im = Image.open(a.ref).convert("RGB")
    px = im.load()
    _cache = {}
    print("region: pantalla %d  filas %d..%d  cols %d..%d"
          % (a.screen, a.row, a.row + a.rows - 1, a.col, a.col + a.cols - 1))
    print("tileset %d -> %s   candidatos: %d   umbral: %d/64"
          % (a.tileset, files, len(cands), a.min))
    print()

    for j in range(a.rows):
        for i in range(a.cols):
            bx = a.screen * 256 + (a.col + i) * TILE
            by = (a.row + j) * TILE
            cells = []
            for qn, qx, qy in QUADS:
                ref = tuple((px[bx + qx + x, by + qy + y][0] >> 3,
                             px[bx + qx + x, by + qy + y][1] >> 3,
                             px[bx + qx + x, by + qy + y][2] >> 3)
                            for y in range(8) for x in range(8))
                # cache por firma del cuadrante: la tuberia repite tiles, asi que
                # hay muchas menos firmas distintas que cuadrantes.
                if ref in _cache:
                    cells.append(_cache[ref])
                    if a.verbose:
                        pass
                    continue
                tops = []
                for n, b, t, tt in cands:
                    for p in range(8):
                        pal = pals5[p]
                        for flip in (0, 1, 2, 3):
                            sc = 0
                            for y in range(8):
                                ty = 7 - y if (flip & 2) else y
                                for x in range(8):
                                    tx = 7 - x if (flip & 1) else x
                                    if pal[tt[ty][tx]] == ref[y * 8 + x]:
                                        sc += 1
                            tops.append((sc, n, p, flip))
                tops.sort(key=lambda r: -r[0])
                _cache[ref] = tops[0]
                cells.append(tops[0])
                if a.verbose:
                    print("    col %2d fila %2d %s: %s"
                          % (a.col + i, a.row + j, qn,
                             "  ".join("$%03X p%d f%d %d/64"
                                       % (t[1], t[2], t[3], t[0])
                                       for t in tops[:4])))
            line = []
            for (sc, n, p, flip), (qn, _, _) in zip(cells, QUADS):
                line.append("%s:%s" % (qn, "%03X" % n if sc >= a.min else " .."))
            print("  bloque col %2d fila %2d  %s"
                  % (a.col + i, a.row + j, "  ".join(line)))
            print("      pal/fit %s" % "  ".join(
                "%s:p%d/%d" % (qn, c[2], c[0]) for c, (qn, _, _) in
                zip(cells, QUADS)))


if __name__ == "__main__":
    main()
