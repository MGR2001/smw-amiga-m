#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scroll_read.py - lee la captura de player/scroll.s armado con -DBENCH
(coste por frame del scroll, medido por la Amiga con el timer A de CIA-B).

    vasmm68k_mot -Fbin -m68000 -I player -DBENCH -DSPEED=4 -o work/scrollb.bin player/scroll.s
    python3 tools/mkadf.py --boot work/boot.bin --stage2 work/scrollb.bin \\
        --data work/yi1_s.dat --out work/scrollb.adf
    sh tools/fsuae_shot.sh work/scrollb.adf work/scrollb.png 70
    python3 tools/scroll_read.py --shot work/scrollb.png --auto
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bench_read import read_words, autodetect, SHOT_X, SHOT_Y, SCALE, E_CLOCK  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=os.path.join(HERE, "..", "work", "scrollb.png"))
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
    for base, name in ((2, "con columna nueva"), (5, "sin columna")):
        mx, av, n = w[base], w[base + 1], w[base + 2]
        print("  %-18s %4d frames  media %5d ticks = %5.1f %%   max %5d = %5.1f %%  (%.2f ms)"
              % (name, n, av, 100.0 * av / tpf, mx, 100.0 * mx / tpf, 1000.0 * mx / E_CLOCK))
    return 0


if __name__ == "__main__":
    sys.exit(main())
