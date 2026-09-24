#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""m16vs.py - Pone lado a lado el bloque de la REFERENCIA y una entrada Map16
concreta renderizada con sus propias paletas.

Es la comparacion mas honesta que se puede hacer: la referencia de un lado, lo
que el ROM dice del otro, ampliado, con los dos mapas de indices impresos para
ver exactamente en que pixel difieren.

Uso:
    python m16vs.py --screen 0 --col 1 --row 25 --idx 0x3F
    python m16vs.py --screen 0 --col 1 --row 25 --idx 0x3F --scale 12
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_REF = r"C:\Users\JC\Downloads\SuperMarioWorldMap02.png"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=_REF)
    ap.add_argument("--screen", type=int, required=True)
    ap.add_argument("--col", type=int, required=True)
    ap.add_argument("--row", type=int, required=True)
    ap.add_argument("--idx", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--set", type=int, default=0)
    ap.add_argument("--tileset", type=int, default=7)
    ap.add_argument("--scale", type=int, default=12)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    from PIL import Image, ImageDraw
    import mklvl
    import palette as palmod
    from lvparse import parse_header, _DEF_SRC
    from map16 import Map16

    lv = os.path.join(_DEF_SRC, "levels", "data", "world_1", "1", "obj.lv")
    h = parse_header(open(lv, "rb").read())
    bank, labels = palmod.load_palette_bank(
        os.path.join(_DEF_SRC, "palettes", "palettes.a"))
    cgram, _bgc = palmod.build_cgram(bank, labels, h["fg_palette"],
                                     h["bg_palette"], h["spr_palette"],
                                     h["bg_color"])
    pals = [[palmod.snes_to_rgb8(c) for c in cgram[p * 16:p * 16 + 16]]
            for p in range(8)]
    files = mklvl.gfx_files_for_tileset(a.tileset)
    gfx = mklvl.load_gfx(os.path.join(_DEF_SRC, "graphics"), files)
    m16 = Map16(set_index=a.set)

    im = Image.open(a.ref).convert("RGB")
    px = im.load()
    x0 = a.screen * 256 + a.col * 16
    y0 = a.row * 16

    # --- referencia 16x16
    ref = Image.new("RGB", (16, 16))
    rp = ref.load()
    for y in range(16):
        for x in range(16):
            rp[x, y] = px[x0 + x, y0 + y]

    # --- candidato
    cand = Image.new("RGB", (16, 16), (24, 24, 32))
    cp = cand.load()
    e = m16.get(a.idx)
    rq = m16.get_raw(a.idx)
    if e is None:
        raise SystemExit("Map16 $%03X sin tabla" % a.idx)
    quads = [(0, 0, 0), (0, 8, 2), (8, 0, 1), (8, 8, 3)]
    print("Map16 $%03X" % a.idx)
    for qx, qy, wi in quads:
        w = rq[wi]
        if w == 0:
            print("   cuadrante %s: VACIO" % ("TL BL TR BR".split()[wi]))
            continue
        tile10, pp, prio, xf, yf = e[wi]
        print("   cuadrante %s: tile $%03X (bloque %d = %s, dentro %d) "
              "pal=%d prio=%d flipX=%d flipY=%d"
              % ("TL BL TR BR".split()[wi], tile10, tile10 // 128,
                 files[tile10 // 128], tile10 % 128, pp, prio, xf, yf))
        tt = gfx[files[tile10 // 128]][tile10 % 128]
        for y in range(8):
            ry = tt[7 - y] if yf else tt[y]
            for x in range(8):
                v = ry[7 - x] if xf else ry[x]
                if v == 0:
                    continue
                cp[qx + x, qy + y] = pals[pp][v & 0x0F]

    S = a.scale
    LBL = 14
    out = Image.new("RGB", (16 * S * 2 + 12, 16 * S + LBL + 4), (255, 0, 255))
    out.paste(ref.resize((16 * S, 16 * S), Image.NEAREST), (0, 0))
    out.paste(cand.resize((16 * S, 16 * S), Image.NEAREST),
              (16 * S + 12, 0))
    dr = ImageDraw.Draw(out)
    dr.text((2, 16 * S + 2), "REFERENCIA", fill=(255, 255, 0))
    dr.text((16 * S + 14, 16 * S + 2), "Map16 $%03X" % a.idx,
            fill=(255, 255, 0))
    dst = a.out or os.path.join(_HERE, "..", "work", "m16vs.png")
    out.save(dst)
    print("-> %s" % dst)


if __name__ == "__main__":
    main()
