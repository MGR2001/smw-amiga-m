#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""m16diff.py - Compara NUESTRA grilla Map16 contra la grilla leida de la
imagen de referencia, bloque por bloque.

Como funciona: se construye un indice inverso "firma de pixeles -> indices
Map16 que la producen" (usando los GFX y las paletas reales del ROM) y despues,
para cada bloque de 16x16 del nivel, se busca la firma de la referencia.

  - si la referencia coincide con algun indice Map16 y nosotros escribimos otro
    -> ERROR NUESTRO (nos dice exactamente que bloque y en que coordenada).
  - si la referencia no coincide con ningun indice (porque encima tiene la capa
    de fondo: nubes, cerros, plataformas) -> se ignora; no es informativo.

Los cuadrantes vacios se rellenan con el color de fondo, porque el cielo de la
referencia es el backdrop y no un tile.

Uso:
    python m16diff.py
    python m16diff.py --mine ../work/level_v5.png --screen 11
    python m16diff.py --top 40
"""

import argparse
import collections
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_REF = r"C:\Users\JC\Downloads\SuperMarioWorldMap02.png"
TILE = 16
WORD_POS = [(0, 0), (0, 8), (8, 0), (8, 8)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=_REF)
    ap.add_argument("--mine", default=os.path.join(_HERE, "..", "work",
                                                   "level_v5.png"))
    ap.add_argument("--lv", default=None)
    ap.add_argument("--tileset", type=int, default=7)
    ap.add_argument("--screen", type=int, default=None)
    ap.add_argument("--top", type=int, default=25,
                    help="cuantos bloques erroneos listar por pantalla")
    a = ap.parse_args()

    from PIL import Image
    import mklvl
    import palette as palmod
    from lvparse import parse_header, _DEF_SRC
    from map16 import Map16, TILESET_SET

    lvpath = a.lv or os.path.join(_DEF_SRC, "levels", "data", "world_1", "1",
                                  "obj.lv")
    h = parse_header(open(lvpath, "rb").read())
    bank, labels = palmod.load_palette_bank(
        os.path.join(_DEF_SRC, "palettes", "palettes.a"))
    cgram, bgc = palmod.build_cgram(bank, labels, h["fg_palette"],
                                    h["bg_palette"], h["spr_palette"],
                                    h["bg_color"])
    pals = [[palmod.snes_to_rgb8(c) for c in cgram[p * 16:p * 16 + 16]]
            for p in range(8)]
    pals5 = [[(c[0] >> 3, c[1] >> 3, c[2] >> 3) for c in pal] for pal in pals]
    _b8 = palmod.snes_to_rgb8(bgc)
    bg5 = (_b8[0] >> 3, _b8[1] >> 3, _b8[2] >> 3)

    files = mklvl.gfx_files_for_tileset(a.tileset)
    gfx = mklvl.load_gfx(os.path.join(_DEF_SRC, "graphics"), files)
    setidx = TILESET_SET.get(a.tileset, 0)
    m16 = Map16(set_index=setidx, tileset=a.tileset)

    def render_idx(idx, scr):
        e = m16.get(idx, scr)
        rq = m16.get_raw(idx, scr)
        if e is None or rq is None:
            return None
        out = [[bg5] * 16 for _ in range(16)]
        for wi in range(4):
            if rq[wi] == 0:
                continue
            t, p, prio, xf, yf = e[wi]
            b, w = t // 128, t % 128
            if b >= len(files) or w >= len(gfx[files[b]]):
                continue
            tt = gfx[files[b]][w]
            ox, oy = WORD_POS[wi]
            for y in range(8):
                ty = 7 - y if yf else y
                for x in range(8):
                    tx = 7 - x if xf else x
                    out[oy + y][ox + x] = pals5[p][tt[ty][tx]]
        return out

    # Un indice por (pantalla & 3): las tuberias $133-$13A cambian de paleta
    # segun la pantalla (MAP16AppTable).  Con un unico indice las tuberias
    # lavanda de la referencia caian en "no identificables" y no contaban.
    invs = []
    for var in range(4):
        inv = {}
        for idx in sorted(m16.entries):
            r = render_idx(idx, var)
            if r is None:
                continue
            inv.setdefault(tuple(c for row in r for c in row), []).append(idx)
        invs.append(inv)
    inv = invs[0]

    # OJO: en nuestro Level.M el 0 es el CENTINELA de "vacio", pero el indice
    # Map16 $000 es una entrada real (tiles $70-$73 a paleta 7).  Un bloque que
    # en la referencia es cielo puro coincide con las entradas que renderizan
    # todo transparente ($0C7..$0CA); eso NO es un error nuestro, es que no
    # dibujamos nada y se ve el backdrop.  Hay que tratarlo como acierto.
    ALLBG = tuple([bg5] * 256)

    ref = Image.open(a.ref).convert("RGB")
    rp = ref.load()
    mine = Image.open(a.mine).convert("RGB")
    mp = mine.load()
    sc = mine.width // (h["num_screens"] * 256)

    # nuestra grilla
    _, _, lv = mklvl.build(lvpath, verbose=False)

    print("referencia: %s" % os.path.basename(a.ref))
    print("nuestro   : %s  (escala %d)" % (os.path.basename(a.mine), sc))
    print("indices Map16 con firma: %d" % len(inv))
    print()

    per_screen = collections.Counter()
    total_ok = total_bad = total_unknown = 0
    detalles = collections.defaultdict(list)

    for s in range(h["num_screens"]):
        if a.screen is not None and s != a.screen:
            continue
        for gy in range(lv.H):
            for cx in range(16):
                gx = s * 16 + cx
                x0 = s * 256 + cx * 16
                y0 = gy * 16
                sig = tuple((rp[x0 + x, y0 + y][0] >> 3,
                             rp[x0 + x, y0 + y][1] >> 3,
                             rp[x0 + x, y0 + y][2] >> 3)
                            for y in range(16) for x in range(16))
                exp = invs[s & 3].get(sig)
                ours = lv.get(gx, gy) or 0
                if exp is None:
                    total_unknown += 1
                    continue
                if ours == 0:
                    # no dibujamos nada: es acierto si la referencia es cielo
                    # puro (backdrop), y error si ahi hay algo de verdad.
                    if sig == ALLBG:
                        total_ok += 1
                    else:
                        total_bad += 1
                        per_screen[s] += 1
                        detalles[s].append((cx, gy, exp[0], 0))
                    continue
                if ours in exp:
                    total_ok += 1
                else:
                    total_bad += 1
                    per_screen[s] += 1
                    detalles[s].append((cx, gy, exp[0], ours))

    print("bloques comparables : %d" % (total_ok + total_bad))
    print("  correctos         : %d (%.1f%%)"
          % (total_ok, 100.0 * total_ok / max(1, total_ok + total_bad)))
    print("  erroneos          : %d" % total_bad)
    print("  no identificables : %d (capa de fondo encima)" % total_unknown)
    print()
    print("pantallas con mas bloques erroneos:")
    for s, n in per_screen.most_common(12):
        print("   pantalla %2d: %3d bloques" % (s, n))

    if a.top:
        print()
        for s in sorted(detalles):
            print("=== pantalla %d ===" % s)
            for cx, gy, exp, ours in detalles[s][:a.top]:
                print("   col %2d fila %2d: esperado $%03X  tenemos $%03X"
                      % (cx, gy, exp, ours))
            if len(detalles[s]) > a.top:
                print("   ... y %d mas" % (len(detalles[s]) - a.top))


if __name__ == "__main__":
    main()
