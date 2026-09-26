#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
imgdiff.py - compara dos capturas del MISMO emulador y la MISMA escala
(antes / despues de optimizar, ida / vuelta del scroll) y dice si son
identicas. Una optimizacion no puede cambiar la imagen: si el diff no es 0,
cambio lo que se ve.

    python3 tools/imgdiff.py work/antes.png work/despues.png [--out work/diff.png]
    python3 tools/imgdiff.py a.png b.png --crop 171,112,851,588   # solo la pantalla

Sale con 0 si son identicas (en la zona), 1 si no. Con --out guarda B con
los pixeles distintos en magenta y la caja que los contiene. Solo PIL (corre
tambien en la PC sin numpy).
"""
import argparse
import sys

from PIL import Image, ImageChops, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--crop", default="", help="x0,y0,x1,y1: comparar solo esa zona")
    ap.add_argument("--out", default="")
    ap.add_argument("--tol", type=int, default=0, help="diferencia por canal que se ignora")
    a = ap.parse_args()
    A = Image.open(a.a).convert("RGB")
    B = Image.open(a.b).convert("RGB")
    if A.size != B.size:
        print("tamanos distintos: %s %s contra %s %s" % (a.a, A.size, a.b, B.size))
        return 1
    if a.crop:
        box = tuple(int(v) for v in a.crop.split(","))
        A, B = A.crop(box), B.crop(box)
    d = ImageChops.difference(A, B).convert("L").point(lambda v: 255 if v > a.tol else 0)
    tot = d.size[0] * d.size[1]
    n = tot - d.histogram()[0]
    if not n:
        print("IDENTICAS (%dx%d)" % d.size)
        return 0
    bbox = d.getbbox()
    print("DISTINTAS: %d px de %d (%.3f %%), caja %s" % (n, tot, 100.0 * n / tot, bbox))
    if a.out:
        o = B.copy()
        o.paste((255, 0, 255), mask=d)
        ImageDraw.Draw(o).rectangle(bbox, outline=(255, 255, 0))
        o.save(a.out)
        print("-> %s" % a.out)
    return 1


if __name__ == "__main__":
    sys.exit(main())
