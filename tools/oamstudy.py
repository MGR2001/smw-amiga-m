#!/usr/bin/env python3
"""
oamstudy.py - D8 opcion (d): con los sprites REALES de una partida de
Yoshi's Island 1 (work/oam_yi1.txt, grabado por oamrec.py), cuanto hardware
de sprites de la Amiga hace falta por linea.

Modelo Amiga (medido en copbench.s):
  * 8 canales de 16 px, 4 columnas de 15 colores (adosados) o 8 de 3.
  * El copper corre cada canal entre lineas (SPRxPOS) y recarga los colores
    17-31 en el borrado (~6 MOVE libres) y a mitad de linea (1 MOVE/16 px).
Por linea de pantalla de cada frame:
  * columnas = minimo de ventanas de 16 px que cubren todas las teselas OAM
    de la linea (caja de la tesela, conservador);
  * colores = union de los colores que cada paleta OAM de la linea usa de
    verdad en el nivel (paleta de $0703 en WRAM cruzada con los colores de
    sprite vistos en la referencia) + los de Mario;
  * grupos = objetos separados por >= SEP px en la linea: entre grupos el
    copper puede recargar colores, asi que lo que cuenta es el grupo con
    mas colores.

    python tools/oamstudy.py [--pal work/pal0703.txt]
"""
import argparse
import os
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")
SEP = 48


def parse(path, level=None):
    """Formato de oambot.lua: frame modo translevel camL1x camL1y camL2x
    camL2y mariox marioy powerup oam(5 bytes c/u) slots(7 bytes c/u)."""
    frames = []
    for ln in open(path):
        p = ln.rstrip("\n").split(" ")
        if len(p) < 10:
            continue
        if level is not None and int(p[2], 16) != level:
            continue
        mode = int(p[1], 16)
        cam = (int(p[3], 16), int(p[4], 16))
        mario = (int(p[7], 16), int(p[8], 16), int(p[9], 16))
        oam = bytes.fromhex(p[10]) if len(p) > 10 else b""
        tiles = []
        for i in range(len(oam) // 5):
            x, y, t, a, h = oam[5 * i:5 * i + 5]
            size = 16 if h & 2 else 8
            if h & 1:
                x -= 256
            if y >= 224 and y < 240:
                continue
            if y >= 240:
                y -= 256
            if x + size <= 0 or x >= 256:
                continue
            tiles.append((x, y, size, (a >> 1) & 7, t, a))
        frames.append(dict(mode=mode, cam=cam, mario=mario, tiles=tiles))
    return frames


def cover(iv, w=16):
    """minimo de ventanas de ancho w que cubren los intervalos [a, b)."""
    n = 0
    end = -10 ** 9
    for a, b in sorted(iv):
        while b > end:
            s = max(a, end)
            n += 1
            end = s + w
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oam", default=os.path.join(WORK, "oam_yi1.txt"))
    ap.add_argument("--pal", default=os.path.join(WORK, "pal0703.txt"))
    ap.add_argument("--level", type=lambda s: int(s, 16), default=None,
                    help="translevel en hex; por defecto el que tiene mas frames")
    a = ap.parse_args()
    if a.level is None:
        cnt = Counter(ln.split(" ")[2] for ln in open(a.oam) if ln.count(" ") >= 9)
        a.level = int(cnt.most_common(1)[0][0], 16)
        print("frames por translevel:", dict(cnt))
    frames = parse(a.oam, a.level)
    print(f"translevel {a.level:02X}: {len(frames)} frames")

    # colores usados por paleta de sprite (0-7)
    used = {}
    if os.path.exists(a.pal):
        for ln in open(a.pal):
            k, cols = ln.split(":")
            used[int(k)] = set(int(c, 16) for c in cols.split())
    ncol = lambda pals: len(set().union(*[used.get(p, set(range(15))) for p in pals])) \
        if used else 15 * len(pals)

    col_hist = Counter()
    grp_hist = Counter()
    line_total = 0
    worst = (0, None)
    frames_over = 0
    for fi, f in enumerate(frames):
        over = False
        for y in range(224):
            on = [t for t in f["tiles"] if t[1] <= y < t[1] + t[2]]
            if not on:
                continue
            line_total += 1
            iv = [(max(0, t[0]), min(256, t[0] + t[2])) for t in on]
            c = cover(iv)
            col_hist[min(c, 12)] += 1
            # grupos separados por >= SEP px
            groups = []
            for t in sorted(on):
                if groups and t[0] < groups[-1][1] + SEP:
                    groups[-1][1] = max(groups[-1][1], t[0] + t[2])
                    groups[-1][2].add(t[3])
                else:
                    groups.append([t[0], t[0] + t[2], {t[3]}])
            g = max(ncol(gr[2]) for gr in groups)
            grp_hist[min(g, 40)] += 1
            if c > 4 or g > 15:
                over = True
            if c > worst[0]:
                worst = (c, fi, y)
        frames_over += over
    print(f"lineas con sprites: {line_total}")
    print("columnas de 16 px por linea:", dict(sorted(col_hist.items())))
    print(f"  > 4 (adosados): {sum(v for k, v in col_hist.items() if k > 4)} lineas; "
          f"> 8: {sum(v for k, v in col_hist.items() if k > 8)}")
    print("colores del grupo mas cargado por linea:", dict(sorted(grp_hist.items())))
    print(f"  > 15: {sum(v for k, v in grp_hist.items() if k > 15)} lineas")
    print(f"frames con alguna linea fuera de presupuesto: {frames_over} de {len(frames)}")
    print(f"peor linea: {worst[0]} columnas (frame {worst[1]}, y {worst[2]})")


if __name__ == "__main__":
    main()
