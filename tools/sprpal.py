#!/usr/bin/env python3
"""
sprpal.py - colores que cada paleta de sprite (OAM 0-7 = CGRAM 8-15) usa de
verdad en Yoshi's Island 1: la paleta de work/cgram.txt (BGR15 de la SNES,
pasada al orden R<<10|G<<5|B de las imagenes) cruzada con los colores de
sprite vistos en la referencia (work/sprmask.npy). La paleta 0 es Mario.
Salida: work/pal0703.txt, una linea "p: cccc cccc ..." por paleta.
"""
import os
import re

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")
REF = os.path.join(HERE, "..", "..", "..", "SuperMarioWorldMap02.png")
MARIO = {0x0, 0x7f58, 0x7d0e, 0x2800, 0x7416, 0x7dcd, 0x7fe0, 0x2213, 0x4379,
         0x58ac, 0x10d1}


def main():
    txt = open(os.path.join(WORK, "cgram.txt"), encoding="utf-8").read()
    pals = {}
    for m in re.finditer(r"paleta\s+(\d+)[^\n]*\n\s+((?:\$[0-9A-F]{4}\s*){16})", txt):
        pals[int(m.group(1))] = [int(x, 16) for x in re.findall(r"\$([0-9A-F]{4})", m.group(2))]

    def conv(c):
        return (c & 31) << 10 | ((c >> 5) & 31) << 5 | ((c >> 10) & 31)

    ref = np.array(Image.open(REF).convert("RGB").crop((0, 0, 5120, 432))).astype(np.int64)
    r = (ref[..., 0] >> 3) << 10 | (ref[..., 1] >> 3) << 5 | (ref[..., 2] >> 3)
    d = np.load(os.path.join(WORK, "sprmask.npy"))
    u, c = np.unique(r[d], return_counts=True)
    seen = {int(a) for a, k in zip(u, c) if k >= 6}
    out = []
    for p in range(8):
        cols = {conv(x) for x in pals[8 + p][1:]}
        used = MARIO if p == 0 else cols & seen
        out.append("%d: %s" % (p, " ".join("%04x" % x for x in sorted(used))))
        print("pal %d: %2d en CGRAM, %2d usados en el nivel" % (p, len(cols), len(used)))
    open(os.path.join(WORK, "pal0703.txt"), "w").write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
