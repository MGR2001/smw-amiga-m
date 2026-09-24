#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""m16match.py - Dado un bloque de 16x16 px de la referencia, busca QUE ENTRADA
Map16 (0..511) y QUE PALETA lo producen.

Es la herramienta que cierra la cadena entera de una sola vez:

    referencia (pixeles reales)
        -> indices de paleta (color RGB mas cercano)
        -> comparar contra las 512 entradas Map16 x 8 paletas
        -> decir indice + paleta + flips

Sirve para responder "que tile usa el juego AQUI" sin depender de leer el
desensamblado, y por lo tanto para detectar cuando un handler escribe el tile
equivocado.

OJO con la precision de color: la referencia expande 5->8 bits con `<<3` y
nosotros con replicacion de bits.  Por eso la comparacion se hace SIEMPRE en
espacio de 5 bits (canal >> 3), que es el espacio nativo del SNES.

Uso:
    python m16match.py --screen 0 --col 1 --row 25
    python m16match.py --screen 9 --col 6 --row 20 --pal 4 --top 10
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
    ap.add_argument("--col", type=int, required=True, help="columna 0..15 dentro de la pantalla")
    ap.add_argument("--row", type=int, required=True, help="fila 0..26")
    ap.add_argument("--pal", type=int, default=None, help="limita a una paleta")
    ap.add_argument("--set", type=int, default=0)
    ap.add_argument("--tileset", type=int, default=7)
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--show", action="store_true", help="imprime el mapa de indices")
    a = ap.parse_args()

    from PIL import Image
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
    raw = [[px[x0 + x, y0 + y] for x in range(16)] for y in range(16)]

    def q(c):
        return (c[0] >> 3, c[1] >> 3, c[2] >> 3)

    qraw = [[q(raw[y][x]) for x in range(16)] for y in range(16)]
    qpals = [[q(c) for c in pals[p]] for p in range(8)]

    if a.show:
        for p in (a.pal,) if a.pal is not None else (2,):
            print("mapa de indices de la referencia con pal %d:" % p)
            for y in range(16):
                row = ""
                for x in range(16):
                    cq = qraw[y][x]
                    row += "%X" % min(range(16), key=lambda i: sum(
                        (cq[k] - qpals[p][i][k]) ** 2 for k in range(3)))
                print("   " + row)

    # METRICA: contar aciertos no sirve.  En un bloque de tierra el 89% de los
    # pixeles son el color de base liso, y CUALQUIER tile de tierra acierta
    # esos.  Lo que identifica al tile es el PATRON DE MOTAS.  Por eso:
    #   - se toma como "base" el color modal del bloque de referencia;
    #   - se puntua SOLO la mascara de motas:
    #         +2  mota de la referencia reproducida exactamente
    #         -2  mota de la referencia NO reproducida (falta)
    #         -2  mota de mas (el candidato dibuja donde la referencia es lisa)
    #          0  pixel liso de la referencia no tocado
    #     (los pixeles transparentes del candidato sobre zona lisa no cuentan)
    from collections import Counter
    base = Counter(c for row in qraw for c in row).most_common(1)[0][0]

    def score_entry(mi):
        e = m16.get(mi)
        if e is None:
            return None
        rq = m16.get_raw(mi)
        quads = [(0, 0, 0), (0, 8, 2), (8, 0, 1), (8, 8, 3)]  # column-major
        sc = 0
        hits = misses = extra = 0
        drawn = [[False] * 16 for _ in range(16)]
        col = [[None] * 16 for _ in range(16)]
        pals_used = set()
        for qx, qy, wi in quads:
            if rq[wi] == 0:
                continue
            tile10, pp, _prio, xf, yf = e[wi]
            pals_used.add(pp)
            blk, wi2 = tile10 // 128, tile10 % 128
            if blk >= len(files) or wi2 >= len(gfx[files[blk]]):
                continue
            tt = gfx[files[blk]][wi2]
            for y in range(8):
                ry = tt[7 - y] if yf else tt[y]
                for x in range(8):
                    v = ry[7 - x] if xf else ry[x]
                    if v == 0:
                        continue
                    drawn[qy + y][qx + x] = True
                    col[qy + y][qx + x] = qpals[pp][v & 0x0F]
        for y in range(16):
            for x in range(16):
                ref_dot = qraw[y][x] != base
                if ref_dot:
                    if drawn[y][x] and col[y][x] == qraw[y][x]:
                        sc += 2
                        hits += 1
                    else:
                        sc -= 2
                        misses += 1
                elif drawn[y][x] and col[y][x] != base:
                    sc -= 2
                    extra += 1
        return sc, mi, tuple(sorted(pals_used)), hits, misses, extra

    results = []
    for mi in range(512):
        r = score_entry(mi)
        if r is None:
            continue
        # descarta entradas casi vacias: si no dibujan nada, no puntuan nada
        if r[3] + r[4] + r[5] == 0:
            continue
        results.append(r)
    results.sort(key=lambda r: -r[0])
    print("\nreferencia: pantalla %d col %d fila %d   (base = %s)"
          % (a.screen, a.col, a.row, base))
    for sc, mi, ups, hits, misses, extra in results[:a.top]:
        e = m16.get(mi)
        tiles = []
        for wi in (0, 2, 1, 3):
            tiles.append("----" if m16.get_raw(mi)[wi] == 0
                         else "%03X" % e[wi][0])
        print("  score %5d  (motas ok %3d, faltan %3d, sobran %3d)  "
              "Map16 \$%03X  pal(es)=%s  tiles(TL,BL,TR,BR)=%s"
              % (sc, hits, misses, extra, mi,
                 ",".join(str(u) for u in ups), ",".join(tiles)))


if __name__ == "__main__":
    main()
