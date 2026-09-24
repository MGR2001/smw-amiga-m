#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_shot.py - compara la captura de WinUAE con el oraculo del PC.

Este es el paso que cierra el bucle de verificacion: si la Amiga y el PC
renderizan el MISMO blob, las dos imagenes tienen que ser identicas pixel a
pixel.  Cualquier diferencia es un bug real (copper, bitplanes, planos,
paleta) y no una impresion subjetiva.

    python tools/verify_shot.py                     # usa work/shot.png
    python tools/verify_shot.py --shot x.png --exp y.png

Config de WinUAE asumida (tools/shot.ps1): ventana 720x568, que da escala
exactamente 2x sobre la pantalla PAL 320x256.  El contenido empieza en
(67,70) dentro de la ventana y mide 640x512.

Salida: 0 si coincide al 100%, 1 si no.
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_WORK = os.path.normpath(os.path.join(_HERE, "..", "work"))

# Offset medido del contenido dentro de la ventana de WinUAE a 720x568.
SHOT_X, SHOT_Y = 67, 70
SHOT_W, SHOT_H = 640, 512


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=os.path.join(_WORK, "shot.png"))
    ap.add_argument("--exp", default=os.path.join(_WORK, "expected.png"))
    ap.add_argument("--x", type=int, default=SHOT_X)
    ap.add_argument("--y", type=int, default=SHOT_Y)
    ap.add_argument("--out", default=os.path.join(_WORK, "compare.png"))
    ap.add_argument("--search", type=int, default=6,
                    help="radio de busqueda del offset (+-N px)")
    args = ap.parse_args()

    from PIL import Image, ImageChops

    if not os.path.exists(args.shot):
        sys.exit("no existe la captura: %s" % args.shot)
    if not os.path.exists(args.exp):
        sys.exit("no existe el oraculo: %s" % args.exp)

    shot = Image.open(args.shot).convert("RGB")
    exp = Image.open(args.exp).convert("RGB")
    if exp.size != (SHOT_W, SHOT_H):
        exp = exp.resize((SHOT_W, SHOT_H), Image.NEAREST)

    best = None
    r = args.search
    for oy in range(args.y - r, args.y + r + 1):
        for ox in range(args.x - r, args.x + r + 1):
            if ox < 0 or oy < 0:
                continue
            if ox + SHOT_W > shot.width or oy + SHOT_H > shot.height:
                continue
            c = shot.crop((ox, oy, ox + SHOT_W, oy + SHOT_H))
            h = ImageChops.difference(c, exp).convert("L").histogram()
            pct = 100.0 * sum(h[:4]) / (SHOT_W * SHOT_H)
            if best is None or pct > best[0]:
                best = (pct, ox, oy, c)

    pct, ox, oy, crop = best
    n = SHOT_W * SHOT_H
    h = ImageChops.difference(crop, exp).convert("L").histogram()
    print("captura    : %s  (%dx%d)" % (args.shot, shot.width, shot.height))
    print("oraculo    : %s" % args.exp)
    print("recorte    : (%d,%d) %dx%d" % (ox, oy, SHOT_W, SHOT_H))
    print("identicos  : %.2f%%   (tolerancia <4/255)" % pct)
    print("muy dist.  : %.2f%%   (>40/255)" % (100.0 * sum(h[41:]) / n))

    if pct < 99.9:
        # diagnostico: que colores sobran/faltan
        import collections
        ec = set(exp.getdata())
        cc = collections.Counter(crop.getdata())
        extra = [(c, k) for c, k in cc.most_common() if c not in ec][:6]
        print()
        print("colores de la captura que NO estan en el oraculo:")
        for c, k in extra:
            print("   %-16s %6d px" % (str(c), k))
        print("(si son solo grises de la ventana, subi --search)")
        if os.environ.get("VERIFY_DUMP"):
            crop.save(args.out)
            sheet = Image.new("RGB", (SHOT_W, SHOT_H * 2 + 6), (220, 40, 40))
            sheet.paste(crop, (0, 0))
            sheet.paste(exp, (0, SHOT_H + 6))
            sheet.save(args.out)
            print("->", args.out)
        return 1

    sheet = Image.new("RGB", (SHOT_W, SHOT_H * 2 + 6), (220, 40, 40))
    sheet.paste(crop, (0, 0))
    sheet.paste(exp, (0, SHOT_H + 6))
    sheet.save(args.out)
    print()
    print("OK - la Amiga reproduce el oraculo exactamente.")
    print("-> %s  (arriba: Amiga en WinUAE | abajo: oraculo PC)" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
