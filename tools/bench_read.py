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


def read_words(path, ox, oy, sc, scy=None):
    im = Image.open(path).convert("L")
    px = im.load()
    scy = sc if scy is None else scy
    words = []
    for i in range(NROWS):
        y = int(round(oy + (8 + 12 * i + 4) * scy))
        v = 0
        for k in range(16):
            x = int(round(ox + ((2 + k) * 16 + 8) * sc))
            v = (v << 1) | (1 if px[x, y] > 128 else 0)
        words.append(v)
    return words


def autodetect(path):
    """(ox, oy, sx, sy) de una captura con cualquier escala (FS-UAE en cloud
    escala x2.125, WinUAE x2): las filas de bits son las bandas blancas y la
    fila 0 es la sincronia $A55A (bits 0 y 14 a 1)."""
    im = Image.open(path).convert("L")
    w, h = im.size
    px = im.load()
    rows = [y for y in range(h) if any(px[x, y] > 128 for x in range(0, w, 2))]
    bands, start = [], None
    rows_set = set(rows)
    for y in range(h + 1):
        if y in rows_set and start is None:
            start = y
        elif y not in rows_set and start is not None:
            bands.append((start, y - 1))
            start = None
    if len(bands) < NROWS:
        raise SystemExit("autodetect: %d bandas blancas, esperaba %d" % (len(bands), NROWS))
    bands = bands[:NROWS]
    c0 = (bands[0][0] + bands[0][1]) / 2.0
    c18 = (bands[NROWS - 1][0] + bands[NROWS - 1][1]) / 2.0
    sy = (c18 - c0) / (12.0 * (NROWS - 1))
    oy = c0 - 12 * sy
    yc = int(round(c0))
    runs, x = [], 0
    while x < w:
        if px[x, yc] > 128:
            x0 = x
            while x < w and px[x, yc] > 128:
                x += 1
            runs.append((x0, x - 1))
        x += 1
    # $A55A = 1010 0101 0101 1010: el primer tramo es el bit 0, el ultimo el 14
    sx = (runs[-1][0] - runs[0][0]) / (14.0 * 16)
    ox = runs[0][0] - 32 * sx
    return ox, oy, sx, sy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=os.path.join(_WORK, "shot.png"))
    ap.add_argument("--x", type=int, default=SHOT_X)
    ap.add_argument("--y", type=int, default=SHOT_Y)
    ap.add_argument("--auto", action="store_true", help="detectar escala y origen (FS-UAE)")
    a = ap.parse_args()

    if a.auto:
        ox, oy, sx, sy = autodetect(a.shot)
        w = read_words(a.shot, ox, oy, sx, sy)
    else:
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
