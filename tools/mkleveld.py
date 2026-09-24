#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mkleveld.py - etapa 5: convierte el nivel al formato de D8 opcion (d)
(dual playfield + el copper recargando colores a mitad de linea).

Entradas: work/fg15.npy y work/bg512.npy (tools/mkd8in.py, datos del ROM).
Salida:   work/yi1_d.dat (derivado del ROM: no se versiona, R9).

Colores. El OCS tiene paleta de 12 bits: cada color de la SNES (5 bits por
canal) se cuantiza al de 4 bits mas cercano, round(c * 15 / 31), ANTES de
repartir registros (dos colores que quedan iguales ya no piden recarga). El
cielo (SKY = 0x197 en fg15/bg512) va aparte, como COLOR00.

Capa 1 (PF1, 3 planos, indices 1..7). La asignacion de dpfsplit.py
(allocate: intervalos de color por linea, GAP px, 7 registros, derrame al
mas cercano) sobre los colores cuantizados. El mapa de indices se parte en
bloques de 16x16 y se guardan solo los distintos.

Capa 2 (PF2, 3 planos). Mapa de bits de 512 x 432 (el fondo se repite cada
512 px) con <= 7 colores por linea; los registros se mantienen entre
lineas para que el copper recargue lo menos posible.

Formato (big-endian, para el 68000):
  +0   "SMWD"  u16 version (1)
  +6   u16 ancho del nivel (px)   u16 lineas   u16 bloques   u16 columnas
       u16 filas de bloques      u16 color del cielo (0x0RGB)
  +20  u32 x 6: desplazamientos de las secciones, desde el principio:
       BLK  bloques: 96 bytes cada uno, 16 filas x (plano0, plano1, plano2),
            palabras de 16 px (el orden de un playfield entrelazado)
       MAP  filas x columnas bytes: numero de bloque de cada celda
       LIX  (lineas + 1) x u16: primer evento de cada linea en EVT
       EVT  eventos de la capa 1: u16 x_ini, u16 x_fin, u8 registro (1..7),
            u8 0, u16 color (0x0RGB); por linea, ordenados por x_ini. En
            pantalla, el registro tiene que valer ese color de x_ini a
            x_fin (si esta a la vista): es lo que el copper carga en el
            borrado o a mitad de linea (etapa 6)
       L2B  capa 2: 432 lineas x (plano0, plano1, plano2) x 64 bytes
       L2P  capa 2: 432 lineas x 7 colores (registros 9..15 del DPF)

    python tools/mkleveld.py [--gap 48]
"""
import argparse
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dpfsplit                                 # noqa: E402

WORK = os.path.join(HERE, "..", "work")
SKY = dpfsplit.SKY
P = 512


def q4(c5):
    """5 bits -> 4 bits, el mas cercano"""
    return (c5 * 30 + 31) // 62


def to12(c15):
    """RGB555 (r<<10|g<<5|b) -> 0x0RGB del OCS"""
    c15 = np.asarray(c15)
    return (q4(c15 >> 10 & 31) << 8) | (q4(c15 >> 5 & 31) << 4) | q4(c15 & 31)


def back15(c12):
    """0x0RGB -> RGB555 representativo (para las distancias de dpfsplit)"""
    c12 = np.asarray(c12)
    e = lambda v: (v * 62 + 15) // 30         # noqa: E731  (4 -> 5 bits)
    return (e(c12 >> 8 & 15) << 10) | (e(c12 >> 4 & 15) << 5) | e(c12 & 15)


def quantize(img):
    """fg/bg en RGB555 -> mismo formato pero con los colores ya del OCS;
    el cielo queda en SKY (y ningun color del nivel puede caer en SKY)"""
    out = back15(to12(img)).astype(img.dtype)
    sky = img == SKY
    clash = (~sky) & (out == SKY)
    if clash.any():
        raise SystemExit("un color del nivel cuantiza igual que el cielo: %d px" % clash.sum())
    out[sky] = SKY
    return out


def planar_rows(idx_rows, width):
    """indices (h x width, 0..7) -> bytes: por fila, 3 planos de width/8 bytes"""
    out = bytearray()
    for row in idx_rows:
        for p in range(3):
            bits = ((row >> p) & 1).astype(np.uint8)
            out += np.packbits(bits).tobytes()
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=int, default=48)
    ap.add_argument("--out", default=os.path.join(WORK, "yi1_d.dat"))
    a = ap.parse_args()

    fg0 = np.load(os.path.join(WORK, "fg15.npy"))
    bg0 = np.load(os.path.join(WORK, "bg512.npy"))
    fg, bg = quantize(fg0), quantize(bg0)
    H, W = fg.shape
    sky12 = int(to12(SKY))
    print("colores de la capa 1: %d en la SNES, %d en el OCS"
          % (len(np.unique(fg0[fg0 != SKY])), len(np.unique(fg[fg != SKY]))))

    # ---- capa 1
    idx = np.zeros((H, W), np.int8)
    shown = fg.copy()
    events = []
    for y in range(H):
        i, s, ivs = dpfsplit.allocate(fg[y], a.gap)
        ev = sorted((iv[0], iv[1], iv[4] + 1, int(to12(iv[2]))) for iv in ivs if iv[4] is not None)
        # derrames: dpfsplit elige el tramo vivo mas cercano en color, pero
        # puede no cubrir el pixel, y ahi el registro vale OTRO color. Se
        # rehace con lo que vale de verdad cada registro en esa x (el ultimo
        # evento que empezo antes) y el color mas cercano entre esos.
        spilled = [x for iv in ivs if iv[4] is None
                   for x in range(iv[0], iv[1] + 1) if fg[y, x] == iv[2]]
        if len(spilled):
            val = np.full((8, W), -1, np.int64)
            for es, ee, r, c in ev:
                val[r, es:] = back15(c)
            for x in spilled:
                regs = [r for r in range(1, 8) if val[r, x] >= 0]
                if not regs:
                    raise SystemExit("linea %d x %d: ningun registro con valor" % (y, x))
                r = min(regs, key=lambda r: int(dpfsplit.dist2(int(val[r, x]), int(fg[y, x]))))
                i[x] = r
                s[x] = val[r, x]
        idx[y], shown[y] = i, s
        events.append(ev)
    spill = int((shown != fg).sum())

    blocks, bmap = [], np.zeros((H // 16, W // 16), np.uint8)
    seen = {}
    empty = np.zeros((16, 16), np.int8)
    seen[empty.tobytes()] = 0
    blocks.append(empty)
    for by in range(H // 16):
        for bx in range(W // 16):
            blk = idx[by * 16:by * 16 + 16, bx * 16:bx * 16 + 16]
            k = blk.tobytes()
            if k not in seen:
                if len(blocks) == 256:
                    raise SystemExit("mas de 256 bloques distintos")
                seen[k] = len(blocks)
                blocks.append(blk.copy())
            bmap[by, bx] = seen[k]

    # ---- capa 2: <= 7 colores por linea, registros estables entre lineas
    l2idx = np.zeros((H, P), np.int8)
    l2pal = np.zeros((H, 7), np.int32)
    prev = {}
    for y in range(H):
        row = bg[y]
        cols, cnt = np.unique(row[row != SKY], return_counts=True)
        if len(cols) > 7:
            raise SystemExit("la capa 2 tiene %d colores en la linea %d" % (len(cols), y))
        keep = {r: c for r, c in prev.items() if c in set(cols.tolist())}
        free = [r for r in range(7) if r not in keep]
        for c in cols.tolist():
            if c not in keep.values():
                keep[free.pop(0)] = c
        for r, c in keep.items():
            l2idx[y][row == c] = r + 1
            l2pal[y, r] = int(to12(c))
        for r in range(7):                  # registros sin uso: se quedan como estaban
            if r not in keep and y:
                l2pal[y, r] = l2pal[y - 1, r]
        prev = keep

    # ---- blob
    blk_bytes = b"".join(planar_rows(b.astype(np.int64), 16) for b in blocks)
    map_bytes = bmap.tobytes()
    lix, evt = [], bytearray()
    n = 0
    for ev in events:
        lix.append(n)
        for s, e, r, c in ev:
            evt += struct.pack(">HHBBH", s, e, r, 0, c)
            n += 1
    lix.append(n)
    if n >= 65536:
        raise SystemExit("demasiados eventos para u16")
    lix_bytes = struct.pack(">%dH" % len(lix), *lix)
    l2b = planar_rows(l2idx.astype(np.int64), P)
    l2p = struct.pack(">%dH" % (H * 7), *[int(v) for v in l2pal.flatten()])
    sections = [blk_bytes, map_bytes, lix_bytes, bytes(evt), l2b, l2p]
    head = b"SMWD" + struct.pack(">HHHHHHH", 1, W, H, len(blocks), W // 16, H // 16, sky12)
    off = len(head) + 4 * len(sections)
    offs = []
    for s in sections:
        off = (off + 3) & ~3
        offs.append(off)
        off += len(s)
    blob = bytearray(head + struct.pack(">6I", *offs))
    for o, s in zip(offs, sections):
        blob += bytes(o - len(blob))
        blob += s
    open(a.out, "wb").write(blob)

    print("capa 1: %d bloques distintos (%d bytes), mapa %dx%d, %d eventos (%d bytes), "
          "derrame %d px"
          % (len(blocks), len(blk_bytes), W // 16, H // 16, n, len(evt), spill))
    print("capa 2: %d bytes de mapa de bits + %d de paleta por linea" % (len(l2b), len(l2p)))
    print("-> %s (%d bytes)" % (a.out, len(blob)))
    np.save(os.path.join(WORK, "yi1_d_ideal.npy"), np.where(fg != SKY, shown, np.tile(bg, (1, W // P))))


if __name__ == "__main__":
    main()
