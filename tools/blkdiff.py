#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blkdiff.py - Compara numericamente UN bloque de 16x16 de la referencia contra
un bloque de nuestro render, en espacio de 5 bits, e imprime las dos rejillas
de indices de color para ver pixel por pixel donde difieren.

Por que 5 bits: la referencia expande 5->8 bits con `v << 3` y nuestro
palette.snes_to_rgb8 usa replicacion de bits (`v<<3 | v>>2`).  Comparar en 8
bits hace que TODO difiera por 1..7 unidades.  En 5 bits (`c >> 3`) la
comparacion es significativa.

Uso:
    python blkdiff.py --screen 0 --col 1 --row 25
    python blkdiff.py --screen 0 --col 1 --row 25 --tiles 2
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_REF = r"C:\Users\JC\Downloads\SuperMarioWorldMap02.png"
_DEF_MINE = os.path.join(_HERE, "..", "work", "level_now.png")
TILE = 16


def quant(c):
    """RGB 8-bit -> 5-bit por canal (lo que la referencia realmente guarda)."""
    return (c[0] >> 3, c[1] >> 3, c[2] >> 3)


def grid(img, x0, y0, n):
    px = img.load()
    return [[quant(px[x0 + x, y0 + y]) for x in range(n)] for y in range(n)]


def letters(g, n):
    """Rejilla -> letras, una por color distinto, ordenadas por frecuencia."""
    freq = {}
    for row in g:
        for c in row:
            freq[c] = freq.get(c, 0) + 1
    order = sorted(freq, key=lambda c: -freq[c])
    alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    sym = {c: alpha[i % len(alpha)] for i, c in enumerate(order)}
    return [[sym[c] for c in row] for row in g], order, sym


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=_REF)
    ap.add_argument("--mine", default=_DEF_MINE)
    ap.add_argument("--screen", type=int, default=0)
    ap.add_argument("--col", type=int, default=0)
    ap.add_argument("--row", type=int, default=0)
    ap.add_argument("--tiles", type=int, default=1)
    a = ap.parse_args()

    from PIL import Image
    ref = Image.open(a.ref).convert("RGB")
    mine = Image.open(a.mine).convert("RGB")
    print("ref  %s  %s" % (ref.size, os.path.basename(a.ref)))
    print("mine %s  %s" % (mine.size, os.path.basename(a.mine)))

    n = a.tiles * TILE
    x0 = a.screen * 16 * TILE + a.col * TILE
    y0 = a.row * TILE

    # el render puede estar a escala 2
    sm = mine.width // (20 * 16 * TILE)
    sm = sm if sm >= 1 else 1
    print("escala del render detectada: %d" % sm)

    gr = grid(ref, x0, y0, n)
    gm = grid(mine, x0 * sm, y0 * sm, n * sm)
    if sm > 1:
        gm = [[gm[y * sm][x * sm] for x in range(n)] for y in range(n)]

    # alfabeto unico para los dos
    allc = {}
    for g in (gr, gm):
        for row in g:
            for c in row:
                allc[c] = allc.get(c, 0) + 1
    order = sorted(allc, key=lambda c: -allc[c])
    alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    sym = {c: alpha[i % len(alpha)] for i, c in enumerate(order)}

    def show(name, g):
        print("\n--- %s ---" % name)
        for row in g:
            print("  " + "".join(sym[c] for c in row))

    show("REFERENCIA (5-bit)", gr)
    show("NUESTRO RENDER (5-bit)", gm)

    print("\n--- leyenda (5-bit -> 8-bit aprox) ---")
    for c in order:
        print("  %s = %s   (~%3d,%3d,%3d)" % (sym[c], c, c[0] << 3,
                                              c[1] << 3, c[2] << 3))

    bad = 0
    for y in range(n):
        for x in range(n):
            if gr[y][x] != gm[y][x]:
                bad += 1
    print("\ndistintos: %d / %d (%.1f%%)" % (bad, n * n, 100.0 * bad / (n * n)))

    # mapa de diferencias
    print("\n--- donde difieren (# = distinto) ---")
    for y in range(n):
        print("  " + "".join("#" if gr[y][x] != gm[y][x] else "."
                             for x in range(n)))


if __name__ == "__main__":
    main()
