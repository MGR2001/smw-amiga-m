#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_d.py - renderiza en el PC el blob de la etapa 5 (work/yi1_d.dat,
tools/mkleveld.py) SIN mirar nada mas, como lo va a ver la Amiga.

1. Nivel entero, copper ideal (todas las cargas entran): cada pixel de la
   capa 1 toma el color del ultimo evento de su registro que empezo antes;
   donde la capa 1 es 0 se ve la capa 2 (repetida cada 512 px) y donde las
   dos son 0, el cielo. Se compara con la imagen ideal que dejo mkleveld
   (work/yi1_d_ideal.npy): tiene que dar 0 pixeles distintos.
2. Encuadres de camara (cam_x cada --step px): el copper carga en el
   borrado el color con el que cada registro entra en pantalla, y los
   cambios a mitad de linea en ranuras cada --slot px con +-margen
   (plazo mas cercano primero, como dpfsplit.frame_line). Una carga que no
   entra deja el color anterior. Cuenta los pixeles mal y las cargas.

    python tools/render_d.py [--step 4] [--png work/yi1_d_nivel.png]
"""
import argparse
import os
import struct

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")
SCREEN_W = 256
P = 512


def load(path):
    b = open(path, "rb").read()
    if b[:4] != b"SMWD":
        raise SystemExit("no es un blob SMWD")
    ver, W, H, nblk, cols, rows, sky = struct.unpack_from(">7H", b, 4)
    offs = struct.unpack_from(">6I", b, 18)
    d = dict(W=W, H=H, nblk=nblk, cols=cols, rows=rows, sky=sky)
    blk = np.frombuffer(b, np.uint8, nblk * 96, offs[0]).reshape(nblk, 16, 3, 2)
    bits = np.unpackbits(blk, axis=3)                       # nblk,16,3,16
    d["blocks"] = (bits[:, :, 0] | bits[:, :, 1] << 1 | bits[:, :, 2] << 2).astype(np.int8)
    d["map"] = np.frombuffer(b, np.uint8, rows * cols, offs[1]).reshape(rows, cols)
    lix = struct.unpack_from(">%dH" % (H + 1), b, offs[2])
    ev = []
    for y in range(H):
        ev.append([struct.unpack_from(">HHBBH", b, offs[3] + 8 * k)
                   for k in range(lix[y], lix[y + 1])])
    d["events"] = [[(s, e, r, c) for s, e, r, _, c in line] for line in ev]
    l2 = np.frombuffer(b, np.uint8, H * 3 * (P // 8), offs[4]).reshape(H, 3, P // 8)
    l2b = np.unpackbits(l2, axis=2)
    d["l2idx"] = (l2b[:, 0] | l2b[:, 1] << 1 | l2b[:, 2] << 2).astype(np.int8)
    d["l2pal"] = np.frombuffer(b, ">u2", H * 7, offs[5]).reshape(H, 7).astype(np.int32)
    return d


def l1_index(d):
    H, W = d["H"], d["W"]
    idx = np.zeros((H, W), np.int8)
    for by in range(d["rows"]):
        for bx in range(d["cols"]):
            idx[by * 16:by * 16 + 16, bx * 16:bx * 16 + 16] = d["blocks"][d["map"][by, bx]]
    return idx


def reg_colors(events, W):
    """copper ideal: color de cada registro 1..7 en cada x de la linea"""
    col = np.zeros((8, W), np.int32)
    for s, e, r, c in events:
        col[r, s:] = c                  # vale desde que empieza hasta el siguiente
    return col


def to15(c12):
    c12 = np.asarray(c12)
    e = lambda v: (v * 62 + 15) // 30   # noqa: E731
    return (e(c12 >> 8 & 15) << 10) | (e(c12 >> 4 & 15) << 5) | e(c12 & 15)


def rgb8(c12):
    c12 = np.asarray(c12)
    return (np.stack([c12 >> 8 & 15, c12 >> 4 & 15, c12 & 15], -1) * 17).astype(np.uint8)


def compose(d, idx, y, l1col, x0, x1):
    """color 0x0RGB de la linea y entre x0 y x1 del nivel; l1col[r, j] = color
    del registro r en x0 + j"""
    xs = np.arange(x0, x1)
    i1 = idx[y, x0:x1]
    out = np.full(x1 - x0, d["sky"], np.int32)
    i2 = d["l2idx"][y, xs % P]
    m2 = i2 > 0
    out[m2] = d["l2pal"][y, i2[m2] - 1]
    m1 = i1 > 0
    out[m1] = l1col[i1[m1], np.nonzero(m1)[0]]
    return out


def camera_line(events, cam_x, slot, margin):
    """(colores de cada registro en pantalla, cargas en el borrado, a mitad,
    fallidas).  Mismo reparto que dpfsplit.frame_line."""
    lo, hi = cam_x, cam_x + SCREEN_W
    vis = [ev for ev in events if ev[1] >= lo and ev[0] < hi]
    col = np.zeros((8, SCREEN_W), np.int32)
    by_reg = {}
    for ev in vis:
        by_reg.setdefault(ev[2], []).append(ev)
    loads = []
    for r, lst in by_reg.items():
        lst.sort()
        col[r, :] = lst[0][3]                       # en el borrado
        for prev, cur in zip(lst, lst[1:]):
            if prev[3] == cur[3]:
                continue
            loads.append((prev[1] + 1 - lo + margin, cur[0] - lo - margin, cur))
    used, failed = set(), 0
    for a, b, ev in sorted(loads, key=lambda t: t[1]):
        ok = None
        for sx in range(0, SCREEN_W, slot):
            if sx not in used and a <= sx <= b:
                ok = sx
                break
        if ok is None:
            failed += 1
            continue
        used.add(ok)
        col[ev[2], max(ev[0] - lo, 0):] = ev[3]
    return col, len(by_reg), len(loads), failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dat", default=os.path.join(WORK, "yi1_d.dat"))
    ap.add_argument("--step", type=int, default=4)
    ap.add_argument("--slot", type=int, default=16)
    ap.add_argument("--margin", type=int, default=8)
    ap.add_argument("--png", default=os.path.join(WORK, "yi1_d_nivel.png"))
    a = ap.parse_args()
    d = load(a.dat)
    H, W = d["H"], d["W"]
    idx = l1_index(d)
    ideal_ref = np.load(os.path.join(WORK, "yi1_d_ideal.npy"))

    # 1. nivel entero, copper ideal
    img = np.zeros((H, W), np.int32)
    lcols = []
    for y in range(H):
        lc = reg_colors(d["events"][y], W)
        lcols.append(lc)
        img[y] = compose(d, idx, y, lc, 0, W)
    diff = int((to15(img) != ideal_ref).sum())     # el cielo: to15(sky) == 0x197
    print("nivel entero con el copper ideal: %d px distintos de la imagen ideal (%dx%d)"
          % (diff, W, H))
    if a.png:
        Image.fromarray(rgb8(img)).save(a.png)
        print("-> %s" % a.png)

    # 2. encuadres de camara
    bad = total = 0
    worst = (0, 0)
    max_hbl = max_mid = 0
    for cam_x in range(0, W - SCREEN_W + 1, a.step):
        fbad = 0
        for y in range(H):
            col, hbl, mid, failed = camera_line(d["events"][y], cam_x, a.slot, a.margin)
            max_hbl, max_mid = max(max_hbl, hbl), max(max_mid, mid)
            if not failed:
                continue
            got = compose(d, idx, y, col, cam_x, cam_x + SCREEN_W)
            want = img[y, cam_x:cam_x + SCREEN_W]
            fbad += int((got != want).sum())
        bad += fbad
        total += int((idx[:, cam_x:cam_x + SCREEN_W] > 0).sum())
        if fbad > worst[0]:
            worst = (fbad, cam_x)
    print("encuadres cada %d px: %d px de capa 1 mal de %d vistos (%.3f %%), peor cam_x=%d con %d px"
          % (a.step, bad, total, 100.0 * bad / max(total, 1), worst[1], worst[0]))
    print("registros de la capa 1 cargados en el borrado: max %d por linea; "
          "cargas a mitad de linea: max %d" % (max_hbl, max_mid))


if __name__ == "__main__":
    main()
