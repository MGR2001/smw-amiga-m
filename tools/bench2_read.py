#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bench2_read.py - decodifica la captura de player/bench2*.s (mismo formato
que bench.s, otras cargas).

    python tools/bench2_read.py --shot work/bench2.png
"""
import argparse
import os
import sys

from bench_read import read_words, autodetect, SHOT_X, SHOT_Y, SCALE, E_CLOCK, LINES_PER_FRAME

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = [
    ("W0", "nada (coste de medir)"),
    ("W1", "columna nueva, 14 bloques de 3 planos (copia directa)"),
    ("W2", "lista del copper del peor frame (857 entradas)"),
    ("W3", "bobs en PF1: Banzai Bill 64x64 + 4 Rex 16x32, 3 planos"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=os.path.join(HERE, "..", "work", "bench2.png"))
    ap.add_argument("--auto", action="store_true", help="detectar escala y origen (FS-UAE)")
    a = ap.parse_args()
    if a.auto:
        ox, oy, sx, sy = autodetect(a.shot)
        w = read_words(a.shot, ox, oy, sx, sy)
    else:
        w = read_words(a.shot, SHOT_X, SHOT_Y, SCALE)
    if w[0] != 0xA55A or w[18] != 0x5AA5:
        print("FALLO: sincronia %04X / %04X" % (w[0], w[18]))
        return 1
    tpf = w[1]
    tpl = tpf / float(LINES_PER_FRAME)
    print("ticks por frame: %d" % tpf)
    for base, modo in ((2, "BLTPRI apagado"), (10, "BLTPRI encendido")):
        over = w[base + 1]
        print("== %s" % modo)
        for n, (tag, name) in enumerate(NAMES):
            mx, av = w[base + 2 * n], w[base + 1 + 2 * n]
            net = max(0, av - over) if tag != "W0" else av
            print("%-3s %-58s max %6.2f ms  media %6.2f ms  %6.1f lineas  %5.1f %%"
                  % (tag, name, mx / E_CLOCK * 1e3, av / E_CLOCK * 1e3, net / tpl,
                     100.0 * net / tpf))
    return 0


if __name__ == "__main__":
    sys.exit(main())
