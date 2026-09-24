#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mkmapbin.py - vuelca el buffer Map16 de un nivel (el que arma mklvl.py) con
el MISMO layout que la WRAM de la SNES, para la colision de Mario (8b):

    bytes [0, n*$1B0)        = $7E:C800...  byte bajo del indice Map16
    bytes [n*$1B0, 2n*$1B0)  = $7F:C800...  byte alto (pagina)

Pantalla s en C800 + s*$1B0 (DATA_00BA60/BA9C), celda y*16 + x. Una celda
vacia vale $025 (P26), no 0.

    python tools/mkmapbin.py [--lv ...] [--out work/yi1_map16.bin]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mklvl                                    # noqa: E402
from lvparse import _DEF_SRC                    # noqa: E402

SCR = 0x1B0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lv", default=os.path.join(_DEF_SRC, "levels", "data", "world_1", "1", "obj.lv"))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "work", "yi1_map16.bin"))
    a = ap.parse_args()
    h, objs, lv = mklvl.build(a.lv, verbose=False)
    n = h["num_screens"]
    lo = bytearray([0x25] * (n * SCR))
    hi = bytearray(n * SCR)
    for gy in range(lv.H):
        for gx in range(lv.W):
            w = lv.get(gx, gy)
            if not w:
                continue
            o = (gx >> 4) * SCR + gy * 16 + (gx & 15)
            lo[o] = w & 0xFF
            hi[o] = (w >> 8) & 1
    open(a.out, "wb").write(lo + hi)
    print("%d pantallas -> %s (%d bytes)" % (n, a.out, 2 * n * SCR))


if __name__ == "__main__":
    main()
