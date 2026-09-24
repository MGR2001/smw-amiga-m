#!/usr/bin/env python3
"""
copsim.py - D8 opcion (d): la lista del copper COMPLETA de cada frame de la
partida grabada (work/oam_yi1.txt), con todas las cargas juntas, contra el
presupuesto medido en copbench.s (DPF 6 planos, 320 px):

  * borrado horizontal: HBL MOVE por linea (15 menos el WAIT);
  * a mitad de linea: una ranura cada 16 px de pantalla.

Cargas por linea de pantalla:
  capa 1  color inicial de cada indice que cambia (borrado) y los cambios a
          mitad de linea con su ventana (asignacion fija de dpfsplit.py);
  capa 2  colores del fondo que cambian respecto de la linea anterior del
          fondo (borrado);
  sprites colores 17-31 que cambian (los de la fila de cada objeto en esa
          linea; asignacion estable) y SPRxPOS cuando una columna se corre.
          Pueden ir al borrado o a una ranura antes del borde izquierdo del
          objeto;
Reparto: primero lo que solo puede ir al borrado, despues plazo mas cercano
primero en las ranuras. Lo que no entra se cuenta como fallo.

Aproximaciones: filas de color de Rex/Banzai de la referencia (la pose del
mapa); Mario = el bloque 16x32 con mas pixeles de su hoja de graficos.

    python tools/copsim.py [--hbl 14] [--margin 8]
"""
import argparse
import os
from collections import Counter

import numpy as np
from PIL import Image

import dpfsplit as d
from oamstudy import parse
from d8demote import ref_rows

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")
SLOT = 16
SCREEN = 256
GAP = 48


def c15(a):
    a = a.astype(np.int64)
    return (a[..., 0] >> 3) << 10 | (a[..., 1] >> 3) << 5 | (a[..., 2] >> 3)


def mario_rows():
    a = c15(np.array(Image.open(os.path.join(WORK, "_pv_mario_0.png")).convert("RGB")))
    u, n = np.unique(a, return_counts=True)
    bg = u[n.argmax()]
    best = None
    for y0 in range(0, a.shape[0] - 31, 8):
        for x0 in range(0, a.shape[1] - 15, 8):
            blk = a[y0:y0 + 32, x0:x0 + 16]
            k = int((blk != bg).sum())
            if best is None or k > best[0]:
                best = (k, blk)
    blk = best[1]
    return [set(r[r != bg].tolist()) for r in blk]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hbl", type=int, default=14)
    ap.add_argument("--margin", type=int, default=8)
    a = ap.parse_args()

    fg = np.load(os.path.join(WORK, "fg15.npy"))
    bg = np.load(os.path.join(WORK, "bg512.npy"))
    H, W = fg.shape
    ivs = [d.allocate(fg[y], GAP)[2] for y in range(H)]
    # capa 2: colores por linea del fondo y cargas respecto de la anterior
    bg_sets = [set(bg[y][bg[y] != d.SKY].tolist()) for y in range(H)]
    bg_loads = [len(bg_sets[y] - bg_sets[y - 1]) if y else len(bg_sets[0]) for y in range(H)]

    rows = {0: mario_rows(), 1: ref_rows(3228), 3: ref_rows(748)}
    generic = rows[3]
    frames = parse(os.path.join(WORK, "oam_yi1.txt"), 0x29)

    hist_hbl = Counter()
    hist_mid = Counter()
    per_frame = []
    fails = 0
    fail_frames = set()
    lines = 0
    for fi, f in enumerate(frames):
        cx, cy = f["cam"]
        state_fg = {}
        spr_regs = {}                   # color -> registro 17-31
        prev_pos = {}
        entries = 0
        # objetos: agrupar teselas por paleta y cercania (una columna/objeto)
        objs = []
        for t in sorted(f["tiles"]):
            for o in objs:
                if o["pal"] == t[3] and abs(o["x"] - t[0]) <= 16 and \
                        t[1] <= o["y1"] + 1 and t[1] + t[2] >= o["y0"] - 1:
                    o["x"] = min(o["x"], t[0])
                    o["x1"] = max(o["x1"], t[0] + t[2])
                    o["y0"] = min(o["y0"], t[1])
                    o["y1"] = max(o["y1"], t[1] + t[2])
                    break
            else:
                objs.append(dict(pal=t[3], x=t[0], x1=t[0] + t[2], y0=t[1], y1=t[1] + t[2]))
        for sy in range(224):
            ly = cy + sy
            if not (0 <= ly < H):
                continue
            lines += 1
            lo, hi = cx, cx + SCREEN
            # --- capa 1
            first, last = {}, {}
            mids = []
            vis = [iv for iv in ivs[ly] if iv[4] is not None and iv[1] >= lo and iv[0] < hi]
            by_reg = {}
            for iv in vis:
                by_reg.setdefault(iv[4], []).append(iv)
            for r_, lst in by_reg.items():
                lst.sort()
                first[r_] = lst[0][2]
                last[r_] = lst[-1][2]
                for p_, c_ in zip(lst, lst[1:]):
                    if p_[2] != c_[2]:
                        mids.append((p_[1] + 1 - lo + a.margin, c_[0] - lo - a.margin))
            hbl_only = sum(1 for r_, c_ in first.items() if state_fg.get(r_) != c_)
            state_fg.update(last)
            # --- capa 2 (la linea del fondo avanza con la camara L2; aprox. = ly)
            hbl_only += bg_loads[min(ly, H - 1)]
            # --- sprites
            spr_loads = []                       # (plazo en pantalla)
            need_cols = set()
            for o in objs:
                if not (o["y0"] <= sy < o["y1"]):
                    continue
                rr = rows.get(o["pal"], generic)
                cols = rr[min(len(rr) - 1, sy - o["y0"])]
                for c_ in cols:
                    need_cols.add(c_)
                    if c_ not in spr_regs:
                        spr_loads.append(max(0, o["x"]) - a.margin)
                key = (o["pal"], o["y0"])
                if key in prev_pos and prev_pos[key] != o["x"]:
                    spr_loads.append(-1)         # SPRxPOS: solo borrado
                prev_pos[key] = o["x"]
            # asignacion estable: soltar colores que no se usan en la linea
            for c_ in list(spr_regs):
                if c_ not in need_cols and len(spr_regs) + len(need_cols) > 15:
                    del spr_regs[c_]
            for c_ in need_cols:
                spr_regs.setdefault(c_, True)
            # --- reparto
            hbl_free = a.hbl - hbl_only
            bad = 0
            if hbl_free < 0:
                bad += -hbl_free
                hbl_free = 0
            spr_loads.sort()
            # los de plazo mas corto al borrado; el resto a ranuras
            to_slots = []
            for dl in spr_loads:
                if hbl_free > 0:
                    hbl_free -= 1
                elif dl >= 0:
                    to_slots.append((0, dl))
                else:
                    bad += 1
            slots = list(range(0, SCREEN, SLOT))
            used = set()
            for wa, wb in sorted(mids + to_slots, key=lambda t: t[1]):
                for sx in slots:
                    if sx not in used and wa <= sx <= wb:
                        used.add(sx)
                        break
                else:
                    bad += 1
            hist_hbl[a.hbl - hbl_free] += 1
            hist_mid[len(used)] += 1
            entries += 1 + (a.hbl - hbl_free) + len(used)
            if bad:
                fails += bad
                fail_frames.add(fi)
        per_frame.append(entries)

    print(f"{len(frames)} frames, {lines} lineas")
    print("MOVE en el borrado por linea:", dict(sorted(hist_hbl.items())))
    print("ranuras a mitad de linea usadas:", dict(sorted(hist_mid.items())))
    print(f"cargas que no entran: {fails} en {len(fail_frames)} frames")
    pf = np.array(per_frame)
    print(f"entradas de copper por frame (WAIT + MOVE): media {pf.mean():.0f}, "
          f"max {pf.max()}  -> lista de {pf.max() * 4} bytes")
    np.save(os.path.join(WORK, "copsim_entries.npy"), pf)


if __name__ == "__main__":
    main()
