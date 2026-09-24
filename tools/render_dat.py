#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_dat.py - renderiza en el PC el MISMO blob que come la Amiga.

Lee work/demo.dat (paleta + tileset planar) y produce el PNG que deberia
verse en pantalla. Sirve para comparar contra la captura de WinUAE y
distinguir un fallo de datos de un fallo de copper/paleta.

    python render_dat.py --in ../work/demo.dat --cols 40 --rows 32 --planes 4 \
                         --out ../work/expected.png
"""

import argparse
import os
import struct
import sys

from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="../work/demo.dat")
    ap.add_argument("--cols", type=int, default=40)
    ap.add_argument("--rows", type=int, default=32)
    ap.add_argument("--planes", type=int, default=4)
    ap.add_argument("--out", default="../work/expected.png")
    ap.add_argument("--scale", type=int, default=2)
    args = ap.parse_args()

    blob = open(os.path.abspath(args.inp), "rb").read()
    planes = args.planes
    ncol = 1 << planes
    pal_bytes = ncol * 2

    # paleta: palabras big-endian, formato Amiga 0x0RGB
    pal = []
    for i in range(ncol):
        v = struct.unpack_from(">H", blob, i * 2)[0]
        r4 = (v >> 8) & 0xF
        g4 = (v >> 4) & 0xF
        b4 = v & 0xF
        pal.append((r4 * 17, g4 * 17, b4 * 17))

    data = blob[pal_bytes:]
    w = args.cols                 # bytes por linea
    h = args.rows * 8
    plane_size = h * w
    if len(data) < plane_size * planes:
        sys.exit("datos cortos: %d bytes, hacen falta %d"
                 % (len(data), plane_size * planes))

    img = Image.new("RGB", (w * 8, h))
    px = img.load()
    for y in range(h):
        for xb in range(w):
            for bit in range(8):
                x = xb * 8 + bit
                v = 0
                for p in range(planes):
                    off = p * plane_size + y * w + xb
                    if (data[off] >> (7 - bit)) & 1:
                        v |= 1 << p
                px[x, y] = pal[v]

    if args.scale != 1:
        img = img.resize((img.width * args.scale, img.height * args.scale),
                         Image.NEAREST)
    out = os.path.abspath(args.out)
    img.save(out)

    print("paleta:")
    for i, c in enumerate(pal):
        print("  %2d  rgb%s" % (i, c))
    print("pantalla : %d x %d px, %d planos" % (w * 8, h, planes))
    print("esperado : %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
