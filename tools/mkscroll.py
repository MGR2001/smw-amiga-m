#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mkscroll.py - etapa 6 (primer prototipo): del blob de la etapa 5
(work/yi1_d.dat) a lo que lee player/scroll.s, ya en el orden de la Amiga.
Salida: work/yi1_s.dat (derivado del ROM: no se versiona, R9).

Ventana vertical fija: la camara de Yoshi's Island 1 no se mueve en
vertical en toda la partida grabada (Bg1VOfs = Bg2VOfs = 192): se ven las
lineas 192..415 del nivel.

Colores de la capa 1 (prototipo: SOLO las cargas en el borrado, sin las
de mitad de linea). En el borrado de cada linea, el registro r vale el
color del primer evento de r que todavia no termino a la izquierda de la
pantalla (render_d.camera_line). Eso cambia solo cuando cam_x pasa el
final de un evento: se guarda una lista de cambios ordenada por x, y la
Amiga la aplica a la lista del copper segun avanza la camara.

Formato (big-endian):
  +0   "SMWS"  u16 ancho del nivel  u16 columnas de bloques  u16 bloques
       u16 color del cielo (0x0RGB)  u16 nº de cambios
  +16  u32 x 8: BLK, MAP, INI, CHG, L2B, L2P, MLX, MLD
  BLK  bloques de 96 bytes (16 filas x 3 planos x palabra)
  MAP  por columna de bloques (columnas x 14 filas visibles + 1): nº de
       bloque (byte). Las 224 lineas empiezan en la fila 12 (192 = 12*16)
  INI  224 lineas x 7 colores: la capa 1 con cam_x = 0
  CHG  cambios: u16 x, u16 desplazamiento del valor en la lista del copper
       por lineas (linea*SEG + 8 + (registro-1)*4 + 2: cada segmento de
       linea empieza con 2 WAIT + 7 MOVE de la capa 1 + 7 de la capa 2),
       u16 color; ordenados por x; termina en x = $FFFF
  L2B  capa 2, 224 lineas x 3 planos x 106 bytes (848 px: el periodo de
       512 mas 336, para que el puntero no tenga que dar la vuelta)
  L2P  224 lineas x 7 colores (registros 9..15)
  MLX  225 x u16: primera carga de cada linea en MLD
  MLD  cargas a mitad de linea de la capa 1, en coordenadas del nivel:
       u16 fin del tramo anterior del registro, u16 principio del nuevo,
       u16 registro ($182..$18E), u16 color; por linea, ordenadas por el
       fin del tramo anterior. Hacen falta cuando el tramo anterior todavia
       se ve (fin >= cam_x) y el nuevo empieza en pantalla

    python3 tools/mkscroll.py
"""
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_d                                 # noqa: E402

WORK = os.path.join(HERE, "..", "work")
Y0, LINES, VIS = 192, 224, 320
SEG = 172                   # bytes por linea en la lista del copper (scroll.s: SEG)
L2W = 848


def main():
    d = render_d.load(os.path.join(WORK, "yi1_d.dat"))
    W, cols = d["W"], d["cols"]
    ini = np.zeros((LINES, 7), np.int32)
    chg = []
    mld = [[] for _ in range(LINES)]
    for L in range(LINES):
        by_reg = {}
        for ev in d["events"][Y0 + L]:
            by_reg.setdefault(ev[2], []).append(ev)
        for r, lst in by_reg.items():
            lst.sort()
            # visible a cam_x: el primer evento con fin >= cam_x
            ini[L, r - 1] = lst[0][3]
            for prev, cur in zip(lst, lst[1:]):
                if cur[3] != prev[3]:
                    chg.append((prev[1] + 1, L * SEG + 8 + (r - 1) * 4 + 2, cur[3]))
                    mld[L].append((prev[1], cur[0], 0x180 + 2 * r, cur[3]))
    chg.sort()
    mlx, mldb = [], bytearray()
    for L in range(LINES):
        mlx.append(len(mldb) // 8)
        for e in sorted(mld[L]):
            mldb += struct.pack(">HHHH", *e)
    mlx.append(len(mldb) // 8)
    rows0 = Y0 // 16
    mp = bytearray()
    for c in range(cols):
        for r in range(rows0, rows0 + 15):
            mp.append(int(d["map"][r, c]) if r < d["rows"] else 0)
    blk = bytearray()
    for b in d["blocks"]:
        for y in range(16):
            for p in range(3):
                bits = ((b[y] >> p) & 1).astype(np.uint8)
                blk += np.packbits(bits).tobytes()
    l2 = bytearray()
    for L in range(LINES):
        row = d["l2idx"][Y0 + L]
        row = np.concatenate([row, row[:L2W - 512]])
        for p in range(3):
            l2 += np.packbits(((row >> p) & 1).astype(np.uint8)).tobytes()
    l2p = struct.pack(">%dH" % (LINES * 7), *[int(v) for v in d["l2pal"][Y0:Y0 + LINES].flatten()])
    inib = struct.pack(">%dH" % (LINES * 7), *[int(v) for v in ini.flatten()])
    chgb = b"".join(struct.pack(">HHH", x, o, c) for x, o, c in chg) + struct.pack(">HHH", 0xFFFF, 0, 0)
    secs = [bytes(blk), bytes(mp), inib, chgb, bytes(l2), l2p,
            struct.pack(">%dH" % len(mlx), *mlx), bytes(mldb)]
    head = b"SMWS" + struct.pack(">HHHHH", W, cols, d["nblk"], d["sky"], len(chg))
    off = len(head) + 2 + 4 * 8
    offs = []
    for s in secs:
        off = (off + 7) & ~7
        offs.append(off)
        off += len(s)
    out = bytearray(head + b"\0\0" + struct.pack(">8I", *offs))
    for o, s in zip(offs, secs):
        out += bytes(o - len(out)) + s
    open(os.path.join(WORK, "yi1_s.dat"), "wb").write(out)
    print("yi1_s.dat: %d bytes, %d bloques, %d cambios de color (capa 1, borrado)"
          % (len(out), d["nblk"], len(chg)))


if __name__ == "__main__":
    main()
