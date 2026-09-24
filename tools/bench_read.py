#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bench_read.py - decodifica los resultados de player/bench.s de una captura.

bench.s dibuja 19 palabras de 16 bits como filas de celdas blancas/negras
(1 plano, 320x256).  Fila i: lineas 8+12*i .. +7; el bit 15 esta en la
palabra 2 de la linea (x = 32..47), el bit 0 en la palabra 17.

La captura de WinUAE (tools/shot.ps1) tiene la pantalla a escala 2x con el
origen en (67,70): los mismos valores que usa verify_shot.py.

    python tools/bench_read.py                 # work/shot.png
    python tools/bench_read.py --shot x.png

Sale con 1 si las palabras de sincronia ($A55A / $5AA5) no aparecen: eso
significa que la captura no es la pantalla de resultados.
"""

import argparse
import os
import sys

from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
_WORK = os.path.normpath(os.path.join(_HERE, "..", "work"))

SHOT_X, SHOT_Y, SCALE = 67, 70, 2
E_CLOCK = 709379.0          # Hz del CIA en una Amiga PAL
LINES_PER_FRAME = 312
NROWS = 19

NAMES = [
    ("W0", "nada (coste de medir)"),
    ("W1", "columna nueva, 14 bloques (scroll de 16 px)"),
    ("W2", "recomposicion completa con paralaje (fondo + 160 bloques)"),
    ("W3", "bobs: Banzai Bill 64x64 + 4 Rex 16x32"),
]


def read_words(path, ox, oy, sc):
    im = Image.open(path).convert("L")
    px = im.load()
    words = []
    for i in range(NROWS):
        y = oy + (8 + 12 * i + 4) * sc
        v = 0
        for k in range(16):
            x = ox + ((2 + k) * 16 + 8) * sc
            v = (v << 1) | (1 if px[x, y] > 128 else 0)
        words.append(v)
    return words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=os.path.join(_WORK, "shot.png"))
    ap.add_argument("--x", type=int, default=SHOT_X)
    ap.add_argument("--y", type=int, default=SHOT_Y)
    a = ap.parse_args()

    w = read_words(a.shot, a.x, a.y, SCALE)
    if w[0] != 0xA55A or w[18] != 0x5AA5:
        print("FALLO: sincronia %04X / %04X (esperaba A55A / 5AA5)" % (w[0], w[18]))
        print("       la captura no es la pantalla de resultados de bench.s")
        return 1

    tpf = w[1]
    exp = E_CLOCK / 50.0
    print("sincronia        : OK")
    print("ticks por frame  : %d  (esperado %.0f para 50 Hz PAL: %+.2f%%)"
          % (tpf, exp, 100.0 * (tpf - exp) / exp))
    tpl = tpf / float(LINES_PER_FRAME)

    for base, modo in ((2, "BLTPRI apagado (la CPU compite por el bus)"),
                       (10, "BLTPRI encendido (blitter nasty)")):
        over = w[base + 1]
        print()
        print("== %s" % modo)
        print("%-3s %-58s %8s %8s %7s %7s" % ("", "carga", "max ms", "media ms",
                                              "lineas", "% frame"))
        res = {}
        for n, (tag, name) in enumerate(NAMES):
            mx, av = w[base + 2 * n], w[base + 1 + 2 * n]
            net = max(0, av - over) if tag != "W0" else av
            res[tag] = net
            print("%-3s %-58s %8.2f %8.2f %7.1f %6.1f%%"
                  % (tag, name, mx / E_CLOCK * 1e3, av / E_CLOCK * 1e3,
                     net / tpl, 100.0 * net / tpf))
        print("presupuesto por frame (50 Hz = %d ticks):" % tpf)
        for vel in (1, 3):
            c = res["W1"] * vel / 16.0 + res["W3"]
            print("  sin paralaje, scroll %d px/frame + bobs : %5.1f%% del frame"
                  % (vel, 100.0 * c / tpf))
        c = res["W2"] + res["W3"]
        print("  paralaje (recomponer todo) + bobs      : %5.1f%% del frame  -> %s"
              % (100.0 * c / tpf, "cabe a 50 Hz" if c < tpf else
                 ("cabe a 25 Hz" if c < 2 * tpf else
                  ("cabe a 16.7 Hz" if c < 3 * tpf else "NO cabe ni a 16.7 Hz"))))
    print()
    print("(lineas y % frame = media menos W0, el coste de medir)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
