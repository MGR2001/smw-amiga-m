#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
copbench_read.py - decodifica la captura de player/copbench.s.

Cada linea de prueba tiene franjas de COLOR01 = k (R=0, G=k>>4, B=k&15),
blanco antes de la primera MOVE y rojo despues de la ultima.  Para cada
linea imprime la secuencia (k, ancho en px lowres) y, por banda, el paso
tipico entre MOVE y la primera k visible en el borde izquierdo.

    python tools/copbench_read.py [--shot work/copbench.png]
"""
import argparse
import os
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SHOT_X, SHOT_Y, SCALE = 67, 70, 2
V0 = 0x2C
BANDS = [("4 planos, WAIT h=$3C", 0x40), ("5 planos, WAIT h=$3C", 0x58),
         ("DPF 6 planos, WAIT h=$3C", 0x70),
         ("DPF 6 planos, WAIT h=$D8 linea anterior", 0x88)]


def decode(px, y):
    runs = []
    for sx in range(320):
        r, g, b = px[SHOT_X + sx * SCALE, SHOT_Y + y * SCALE + 1]
        if (r, g, b) == (255, 255, 255):
            k = "W"
        elif r > 200 and g < 50 and b < 50:
            k = "R"
        elif r < 20:
            k = (round(g / 17) << 4) | round(b / 17)
        else:
            k = "?"
        if runs and runs[-1][0] == k:
            runs[-1][1] += 1
        else:
            runs.append([k, 1])
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=os.path.join(HERE, "..", "work", "copbench.png"))
    a = ap.parse_args()
    px = Image.open(a.shot).convert("RGB").load()
    for name, v in BANDS:
        steps = Counter()
        first = Counter()
        print("==", name)
        for i in range(8):
            y = v + 2 * i - V0
            runs = decode(px, y)
            inner = [w for k, w in runs[1:-1] if isinstance(k, int)]
            steps.update(inner)
            first[runs[0][0]] += 1
            if i < 2:
                print("   linea $%02X:" % (v + 2 * i),
                      " ".join("%s:%d" % (k, w) for k, w in runs))
        print("   anchos de franja (px lowres):", dict(sorted(steps.items())))
        print("   primer valor en x=0:", dict(first))


if __name__ == "__main__":
    main()
