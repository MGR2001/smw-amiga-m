#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
copcal_fine.py - lee la captura de player/copcal.s con COPCAL_FINE=1
(h de un WAIT de a 2 y retardos de BPLCON1). Para cada prueba imprime
TODAS las transiciones de color de la linea, a resolucion de captura,
convertidas a x de pantalla: x = (cx - x0) / sc. Asi se ven a la vez la
x donde cambia COLOR01 y, con -DPATTERN, las rayas de 1 px del contenido
(COLOR09 = $444) y el borde izquierdo de la DIW (COLOR00 -> otro).

    COPCAL_FINE=1 python3 tools/copcal.py gen
    vasmm68k_mot -Fbin -m68000 -I player -I work -DPATTERN -o work/X.bin player/copcal.s
    ... mkadf + fsuae_shot ...
    COPCAL_FINE=1 python3 tools/copcal_fine.py --shot work/X.png
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("COPCAL_FINE", "1")
import copcal                                   # noqa: E402



def c12(p):
    return (int(p[0]) // 17) << 8 | (int(p[1]) // 17) << 4 | int(p[2]) // 17


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", required=True)
    ap.add_argument("--x0", type=float, default=171.375)
    ap.add_argument("--y0", type=float, default=112.0)
    ap.add_argument("--sc", type=float, default=2.125)
    ap.add_argument("--stripes", action="store_true",
                    help="imprimir tambien las rayas (fase mod 16)")
    a = ap.parse_args()
    img = np.asarray(Image.open(a.shot).convert("RGB")).astype(int)
    for i, (name, seq) in enumerate(copcal.TESTS):
        v = copcal.V0 + i * copcal.STEP + 1
        cy = int(a.y0 + (v - 0x2C + 0.5) * a.sc)
        row = [c12(p) for p in img[cy]]
        tr = []
        for cx in range(1, len(row)):
            if row[cx] != row[cx - 1]:
                tr.append((cx, row[cx - 1], row[cx]))
        # borde izquierdo: primer paso desde negro
        left = next((cx for cx, p, c in tr if p == 0x000), None)
        # cambio de COLOR01: primer paso a rojo (o de blanco a otra cosa no gris)
        red = [cx for cx, p, c in tr if c == 0xF00 and p != 0xF00]
        grn = [(cx - a.x0) / a.sc for cx, p, c in tr if c == 0x0F0]
        redx = [(cx - a.x0) / a.sc for cx in red]
        # rayas: pasos a gris dentro de la DIW (inicio de la raya)
        st = [(cx - a.x0) / a.sc for cx, p, c in tr if c == 0x444 and left and cx > left]
        ph = sorted({round(x) % 16 for x in st})
        s = "%2d %-18s borde cx=%s (x=%.2f)  rojo en x=%s" % (
            i, name, left, (left - a.x0) / a.sc if left else -1,
            " ".join("%.2f" % x for x in redx))
        if grn:
            s += "  verde en x=%s" % " ".join("%.2f" % x for x in grn)
        if a.stripes:
            s += "  rayas: n=%d fase=%s" % (len(st), ph)
            if len(st) > 2:
                s += " paso=%.4f" % ((st[-1] - st[0]) / (len(st) - 1) / 16 * a.sc)
        print(s)


if __name__ == "__main__":
    main()
