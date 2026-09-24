#!/usr/bin/env python3
"""
d8demote.py - D8 opcion (d): en las lineas de la partida grabada que piden
mas de 4 columnas de sprite (Banzai Bill + Mario + Rex), se puede pasar UNO
de los objetos a bob en PF1 sin perder colores?

Por linea de pantalla y candidato (Mario = paleta OAM 0, Banzai = 1,
Rex = 3):
  * caja del objeto en esa linea = union de sus teselas OAM;
  * colores que pide esa linea del objeto = colores de la fila
    correspondiente del grafico real (referencia; Mario: su peor fila, 4);
  * alcanza si (colores - los que el terreno ya tiene vivos en todo el tramo)
    <= registros de PF1 libres en [x - GAP, x + ancho + GAP] (asignacion de
    la capa 1 de dpfsplit.py) Y quedan <= 4 columnas sin el.

    python tools/d8demote.py
"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage

import dpfsplit as d
from oamstudy import parse, cover

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")
REF = os.path.join(HERE, "..", "..", "..", "SuperMarioWorldMap02.png")
GAP = 48
MARIO_ROW = 4           # peor numero de colores en una fila de 16 px de Mario


def c15(a):
    a = a.astype(np.int64)
    return (a[..., 0] >> 3) << 10 | (a[..., 1] >> 3) << 5 | (a[..., 2] >> 3)


def ref_rows(x_start):
    ref = c15(np.array(Image.open(REF).convert("RGB").crop((0, 0, 5120, 432))))
    m = np.load(os.path.join(WORK, "sprmask.npy"))
    lab, _ = ndimage.label(ndimage.binary_closing(m, np.ones((5, 5))))
    for i, sl in enumerate(ndimage.find_objects(lab)):
        if sl[1].start == x_start:
            mm = (lab[sl] == i + 1) & m[sl]
            return [set(ref[sl][j][mm[j]].tolist()) for j in range(mm.shape[0]) if mm[j].any()]
    raise SystemExit("objeto no encontrado en x=%d" % x_start)


def main():
    rows = {1: ref_rows(3228), 3: ref_rows(748)}      # Banzai, Rex
    fg = np.load(os.path.join(WORK, "fg15.npy"))
    ivs = [d.allocate(fg[y], GAP)[2] for y in range(fg.shape[0])]
    frames = parse(os.path.join(WORK, "oam_yi1.txt"), 0x29)

    tot = 0
    solved = {0: 0, 1: 0, 3: 0}
    any_ok = 0
    bad_frames = set()
    for fi, f in enumerate(frames):
        cx, cy = f["cam"]
        for y in range(224):
            on = [t for t in f["tiles"] if t[1] <= y < t[1] + t[2]]
            if not on:
                continue
            if cover([(max(0, t[0]), min(256, t[0] + t[2])) for t in on]) <= 4:
                continue
            tot += 1
            ok_line = False
            for pal in (3, 1, 0):
                mine = [t for t in on if t[3] == pal]
                rest = [t for t in on if t[3] != pal]
                if not mine:
                    continue
                if cover([(max(0, t[0]), min(256, t[0] + t[2])) for t in rest]) > 4:
                    continue
                xa = cx + min(t[0] for t in mine)
                xb = cx + max(t[0] + t[2] for t in mine) - 1
                ly = cy + y
                if not (0 <= ly < fg.shape[0]):
                    continue
                top = min(t[1] for t in mine)
                if pal == 0:
                    need_cols, cols = MARIO_ROW, set()
                else:
                    rr = rows[pal]
                    cols = rr[min(len(rr) - 1, max(0, y - top))]
                    need_cols = None
                live = [iv for iv in ivs[ly] if iv[4] is not None and
                        iv[0] <= xb + GAP and iv[1] + GAP >= xa]
                covered = {iv[2] for iv in live if iv[0] <= xa and iv[1] >= xb}
                free = 7 - len({iv[4] for iv in live})
                need = need_cols if pal == 0 else len(cols - covered)
                if need <= free:
                    solved[pal] += 1
                    ok_line = True
            if ok_line:
                any_ok += 1
            else:
                bad_frames.add(fi)
    print(f"lineas con > 4 columnas: {tot}")
    for pal, name in ((3, "Rex"), (1, "Banzai Bill"), (0, "Mario")):
        print(f"  se resuelve pasando {name:11s} a bob en PF1: {solved[pal]:5d} "
              f"({100 * solved[pal] / max(tot, 1):5.1f} %)")
    print(f"  con alguno de los tres: {any_ok} ({100 * any_ok / max(tot, 1):.1f} %)")
    print(f"  frames que quedan con alguna linea sin resolver: {len(bad_frames)} de {len(frames)}")


if __name__ == "__main__":
    main()
