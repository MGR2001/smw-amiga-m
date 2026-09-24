#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cmp_ref.py - Compara el render contra la referencia de SNES y localiza las
diferencias por pantalla.

La referencia (`SuperMarioWorldMap02.png`) trae el area de juego en las filas
0..431 y una leyenda debajo.  Se compara solo 0..431.

Salida:
    - un PNG "diff": el render con los pixeles distintos marcados en magenta,
      para ver de un vistazo DONDE esta el problema;
    - un ranking de pantallas por cantidad de pixeles distintos.

Uso:
    python cmp_ref.py --mine work/level_final.png --out work/diff.png
    python cmp_ref.py --mine work/level_final.png --screen 9 --out work/diff9.png
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REF = r"C:\Users\JC\Downloads\SuperMarioWorldMap02.png"
GAME_H = 27 * 16          # 432: solo el area de juego


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=_REF)
    ap.add_argument("--mine", default=os.path.join(_HERE, "..", "work",
                                                   "level_final.png"))
    ap.add_argument("--out", default=os.path.join(_HERE, "..", "work",
                                                  "diff.png"))
    ap.add_argument("--screen", type=int, default=None,
                    help="limita la comparacion a una pantalla")
    ap.add_argument("--tol", type=int, default=0,
                    help="tolerancia por canal (0 = exacto)")
    ap.add_argument("--bits", type=int, default=5,
                    help="precision de comparacion.  5 (por defecto) compara en "
                         "el espacio nativo del SNES (canal >> 3), que es lo "
                         "unico comparable: la referencia expande 5->8 bits con "
                         "`<<3` y nosotros con replicacion de bits, asi que a 8 "
                         "bits TODO difiere por 1..7 unidades.  Usar 8 para "
                         "comparar los bytes crudos.")
    ap.add_argument("--mask", choices=["none", "ref", "mine"], default="none",
                    help="'mine': solo compara los pixeles donde NUESTRO render "
                         "dibujo algo (distinto del fondo).  Es la metrica util "
                         "mientras falte la capa de fondo, porque un objeto "
                         "nuestro SIEMPRE deberia estar tapando lo de atras.")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    from PIL import Image
    import palette as palmod
    from lvparse import parse_header, _DEF_SRC

    lv = os.path.join(_DEF_SRC, "levels", "data", "world_1", "1", "obj.lv")
    h = parse_header(open(lv, "rb").read())
    bank, labels = palmod.load_palette_bank(
        os.path.join(_DEF_SRC, "palettes", "palettes.a"))
    cgram, bgc = palmod.build_cgram(bank, labels, h["fg_palette"],
                                    h["bg_palette"], h["spr_palette"],
                                    h["bg_color"])
    backdrop = palmod.snes_to_rgb8(bgc)

    ref = Image.open(a.ref).convert("RGB")
    mine = Image.open(a.mine).convert("RGB")
    if mine.height != GAME_H:
        mine = mine.crop((0, 0, mine.width, min(GAME_H, mine.height)))
    W = min(ref.width, mine.width)
    rp, mp = ref.load(), mine.load()

    sh = 8 - a.bits

    def q(c):
        return (c[0] >> sh, c[1] >> sh, c[2] >> sh)

    palette = None
    if a.mask == "ref":
        palette = set()
        for p in range(8):
            for c in cgram[p * 16:p * 16 + 16]:
                palette.add(q(palmod.snes_to_rgb8(c)))

    def is_fg(c):
        qc = q(c)
        for p in palette:
            if all(abs(qc[i] - p[i]) <= 2 for i in range(3)):
                return True
        return False

    sh = 8 - a.bits

    def q(c):
        return (c[0] >> sh, c[1] >> sh, c[2] >> sh)

    def is_bg(c):
        qb = q(backdrop)
        qc = q(c)
        return all(abs(qc[i] - qb[i]) <= 1 for i in range(3))

    x0, x1 = 0, W
    if a.screen is not None:
        x0, x1 = a.screen * 256, min(W, (a.screen + 1) * 256)

    out = Image.new("RGB", (x1 - x0, GAME_H))
    op = out.load()
    per_screen = {}
    total = 0
    total_fg = 0
    for y in range(GAME_H):
        for x in range(x0, x1):
            c1, c2 = rp[x, y], mp[x, y]
            q1, q2 = q(c1), q(c2)
            d = max(abs(q1[i] - q2[i]) for i in range(3))
            if a.mask == "none":
                fg = True
            elif a.mask == "ref":
                fg = is_fg(c1)
            else:
                fg = not is_bg(c2)
            if fg:
                total_fg += 1
            if d > a.tol and fg:
                total += 1
                op[x - x0, y] = (255, 0, 255)
                per_screen[(x // 256)] = per_screen.get((x // 256), 0) + 1
            else:
                op[x - x0, y] = c2
    if a.scale != 1:
        out = out.resize((out.width * a.scale, out.height * a.scale),
                         Image.NEAREST)
    out.save(a.out)
    if not a.quiet:
        print("comparado %dx%d px  ->  %d distintos (%.2f%%)"
              % (x1 - x0, GAME_H, total, 100.0 * total / max(1, total_fg)))
        print("  (base = %d px enmascarados; fondo del nivel = %s)"
              % (total_fg, backdrop))
        print("diff -> %s" % a.out)
        print("pantallas con mas diferencia:")
        for s, c in sorted(per_screen.items(), key=lambda kv: -kv[1])[:10]:
            print("   pantalla %2d : %6d px" % (s, c))


if __name__ == "__main__":
    main()
