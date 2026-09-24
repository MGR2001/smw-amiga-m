#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
logicbench_read.py - decodifica la captura de player/logicbench.s y da el
coste del frame del jugador (colision 8b, fisica 8a, animacion) por frame: W2 - W1 y W3 - W1.

    python tools/logicbench_read.py --shot work/logicbench.png
    python tools/logicbench_read.py --shot work/logicbench.png --auto   (captura de FS-UAE)
"""
import argparse
import os
import sys

from bench_read import read_words, autodetect, SHOT_X, SHOT_Y, SCALE, E_CLOCK

HERE = os.path.dirname(os.path.abspath(__file__))
CPU_HZ = 7093790.0          # 68000 de una A500 PAL
NAMES = ["nada (coste de medir)", "copiar el estado (576 bytes)",
         "copiar + level_frame, corriendo", "copiar + level_frame, salto"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=os.path.join(HERE, "..", "work", "logicbench.png"))
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
    print("ticks por frame: %d" % tpf)
    base = 2                                # BLTPRI apagado: la CPU no compite con el blitter
    av = [w[base + 1 + 2 * n] for n in range(4)]
    for n in range(4):
        print("W%d %-40s media %6d ticks  %7.3f ms" % (n, NAMES[n], av[n], av[n] / E_CLOCK * 1e3))
    for n, what in ((2, "corriendo"), (3, "salto")):
        t = av[n] - av[1]
        print("level_frame (camara+graficos+jugador+bloques), %-9s: %4d ticks = %6.1f us = ~%5d ciclos de CPU = %5.2f %% de un frame"
              % (what, t, t / E_CLOCK * 1e6, t / E_CLOCK * CPU_HZ, 100.0 * t / tpf))
    return 0


if __name__ == "__main__":
    sys.exit(main())
