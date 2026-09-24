#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""m16find.py - Dado un bloque de 16x16 de la REFERENCIA, encuentra que indice
Map16 lo reproduce EXACTAMENTE.

Es la cadena completa al reves: indice Map16 -> 4 palabras -> (tile, paleta,
flip) -> GFX -> pixeles.  Si algun indice reproduce el bloque de la referencia
pixel a pixel (en espacio de 5 bits), ese es el indice que el handler escribio.

Esto resuelve de una vez la pregunta "que escribe el handler aca" sin trazar
aritmetica de punteros: se lee del oracle.

Uso:
    python m16find.py --screen 3 --col 8 --row 20
    python m16find.py --screen 3 --row 20 --col 5 --cols 8
    python m16find.py --screen 3 --row 20 --col 8 --explain 0x0CD
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_REF = r"C:\Users\JC\Downloads\SuperMarioWorldMap02.png"
TILE = 16

# posicion en pantalla de cada palabra, en el orden en que las guarda la tabla
# Map16 (column-major: word0=TL word1=BL word2=TR word3=BR)
WORD_POS = [(0, 0), (0, 8), (8, 0), (8, 8)]
WORD_NAME = ["TL", "BL", "TR", "BR"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=_REF)
    ap.add_argument("--screen", type=int, required=True)
    ap.add_argument("--row", type=int, required=True)
    ap.add_argument("--col", type=int, default=0)
    ap.add_argument("--cols", type=int, default=1)
    ap.add_argument("--rows", type=int, default=1)
    ap.add_argument("--tileset", type=int, default=7)
    ap.add_argument("--set", type=int, default=None)
    ap.add_argument("--explain", type=lambda s: int(s, 0), default=None,
                    help="solo explica este indice Map16")
    ap.add_argument("--best", type=int, default=0,
                    help="(obsoleto) ya no hace falta")
    ap.add_argument("--explain-all", action="store_true",
                    help="explica todas las coincidencias, no solo la primera")
    a = ap.parse_args()

    from PIL import Image
    import mklvl
    import palette as palmod
    from lvparse import parse_header, _DEF_SRC
    from map16 import Map16, TILESET_SET

    lv = os.path.join(_DEF_SRC, "levels", "data", "world_1", "1", "obj.lv")
    h = parse_header(open(lv, "rb").read())
    bank, labels = palmod.load_palette_bank(
        os.path.join(_DEF_SRC, "palettes", "palettes.a"))
    cgram, bgc = palmod.build_cgram(bank, labels, h["fg_palette"],
                                    h["bg_palette"], h["spr_palette"],
                                    h["bg_color"])
    pals = [[palmod.snes_to_rgb8(c) for c in cgram[p * 16:p * 16 + 16]]
            for p in range(8)]
    pals5 = [[(c[0] >> 3, c[1] >> 3, c[2] >> 3) for c in pal] for pal in pals]
    _bg8 = palmod.snes_to_rgb8(bgc)
    bg5 = (_bg8[0] >> 3, _bg8[1] >> 3, _bg8[2] >> 3)

    files = mklvl.gfx_files_for_tileset(a.tileset)
    gfx = mklvl.load_gfx(os.path.join(_DEF_SRC, "graphics"), files)
    setidx = a.set if a.set is not None else TILESET_SET.get(a.tileset, 0)
    m16 = Map16(set_index=setidx)

    def render_idx(idx):
        """Indice Map16 -> rejilla 16x16 de colores 5-bit.  Los cuadrantes
        vacios se rellenan con el color de fondo (en la referencia el cielo es
        el backdrop, no un tile)."""
        e = m16.get(idx)
        rq = m16.get_raw(idx)
        if e is None or rq is None:
            return None
        out = [[bg5] * 16 for _ in range(16)]
        for wi in range(4):
            if rq[wi] == 0:
                continue
            tile10, p, prio, xf, yf = e[wi]
            b, w = tile10 // 128, tile10 % 128
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

    def explain(idx):
        e = m16.get(idx)
        rq = m16.get_raw(idx)
        print("Map16 $%03X  palabras crudas: %s"
              % (idx, " ".join("$%04X" % w for w in rq)))
        for wi in range(4):
            if rq[wi] == 0:
                print("   %s: VACIO" % WORD_NAME[wi])
                continue
            t, p, pr, xf, yf = e[wi]
            print("   %s: tile $%03X (bloque %d = %s, dentro %d) pal=%d "
                  "prio=%d flipX=%d flipY=%d"
                  % (WORD_NAME[wi], t, t // 128, files[t // 128], t % 128,
                     p, pr, xf, yf))

    if a.explain is not None:
        explain(a.explain)
        return

    im = Image.open(a.ref).convert("RGB")
    px = im.load()

    # Indice inverso: firma del bloque renderizado -> indices Map16 que lo
    # producen.  Asi la busqueda por bloque es O(1) en vez de 512 renders.
    inv = {}
    for idx in sorted(m16.entries):
        r = render_idx(idx)
        if r is None:
            continue
        sig = tuple(c for row in r for c in row)
        inv.setdefault(sig, []).append(idx)

    print("tileset %d -> %s   set_%d   %d indices Map16 (%d firmas distintas)"
          % (a.tileset, files, setidx, len(m16.entries), len(inv)))
    print()

    for j in range(a.rows):
        for i in range(a.cols):
            bx = a.screen * 256 + (a.col + i) * TILE
            by = (a.row + j) * TILE
            ref = tuple((px[bx + x, by + y][0] >> 3, px[bx + x, by + y][1] >> 3,
                         px[bx + x, by + y][2] >> 3)
                        for y in range(16) for x in range(16))
            hits = inv.get(ref, [])
            print("bloque col %2d fila %2d:" % (a.col + i, a.row + j))
            if hits:
                for idx in hits[:4]:
                    print("   EXACTO  Map16 $%03X" % idx)
                    if a.explain_all:
                        explain(idx)
                if len(hits) > 4:
                    print("   (+%d mas: %s)" % (len(hits) - 4,
                          " ".join("$%03X" % h for h in hits[4:10])))
            else:
                print("   ningun indice Map16 reproduce el bloque")


if __name__ == "__main__":
    main()
