#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mkscroll.py - etapa 6 (primer prototipo): del blob de la etapa 5
(work/yi1_d.dat) a lo que lee player/scroll.s, ya en el orden de la Amiga.
Salida: work/yi1_s.dat (derivado del ROM: no se versiona, R9).

Ventana vertical fija: la camara de Yoshi's Island 1 no se mueve en
vertical en toda la partida grabada (Bg1VOfs = Bg2VOfs = 192): se ven las
lineas 192..415 del nivel.

Colores de la capa 1. En el borrado de cada linea, el registro r vale el
color del primer evento de r que todavia no termino a la izquierda de la
pantalla (render_d.camera_line). Eso cambia solo cuando cam_x pasa el
final de un evento: se guarda una lista de cambios ordenada por x (con el
color viejo, para deshacerlos cuando la camara vuelve), y la Amiga la
aplica a la lista del copper segun se mueve la camara. Las cargas a mitad
de linea (MLD) se planifican aca, en coordenadas del nivel (plan()): la
Amiga solo escribe, para cada linea, las que caen en pantalla (Etapa 6.2).

Formato (big-endian):
  +0   "SMWS"  u16 ancho del nivel  u16 columnas de bloques  u16 bloques
       u16 color del cielo (0x0RGB)  u16 nº de cambios
  +16  u32 x 10: BLK, MAP, INI, CHG, L2B, L2P, MLX, MLD, LNS, 0
  BLK  bloques de 96 bytes (16 filas x 3 planos x palabra)
  MAP  por columna de bloques (columnas x 14 filas visibles + 1): nº de
       bloque (byte). Las 224 lineas empiezan en la fila 12 (192 = 12*16)
  INI  224 lineas x 7 colores: la capa 1 con cam_x = 0
  CHG  cambios: u16 x, u16 desplazamiento del valor en la lista del copper
       por lineas (linea*SEG + 8 + (registro-1)*4 + 2: cada segmento de
       linea empieza con 2 WAIT + 7 MOVE de la capa 1),
       u16 color nuevo, u16 color viejo; ordenados por x; empieza con un
       centinela x = 0 (sin efecto) y termina en x = $FFFF
  L2B  capa 2, 224 lineas x 3 planos x 106 bytes (848 px: el periodo de
       512 mas 336, para que el puntero no tenga que dar la vuelta)
  L2P  224 lineas x 7 colores (registros 9..15)
  MLX  225 x u16: primera carga de cada linea en MLD
  MLD  cargas a mitad de linea de la capa 1, en coordenadas del nivel, 12
       bytes: u16 clase (0 = WAIT en x; 1 = MOVE detras de la anterior; 2,
       3 = 1 o 2 MOVE de relleno y el MOVE), u16 x planificada (plan():
       modelo medido del copper; creciente dentro de la linea), u16 registro
       ($182..$18E), u16 color, s16 a = fin del tramo anterior + 1 - x,
       s16 b = principio del nuevo - x - 6. Por linea, en el orden del plan,
       entre dos centinelas: antes, x = $FFFF (-1 con signo) y despues,
       x = $7FFF. La Amiga escribe las de x en [s0, s0 + LASTX]
       (la primera, siempre con WAIT) y esa escritura, fija en pantalla,
       sigue bien mientras s0 + a <= s < s0 + b (el MOVE cae entre x y
       x + 7: ver scroll.s, build_mid). MLX apunta a la primera carga
  LNS  lineas que build_mid tiene que mirar: u16 x (W/16 + 1) desplazamientos
       (desde LNS) de listas de u16 (linea * 32, $FFFF al final), una por
       cada 16 px de s (k = s >> 4): las lineas con alguna carga en pantalla
       para alguna s en [16k - 16, 16k + 32). Asi tambien se limpian las
       que se quedan sin cargas (la camara no se mueve mas de 16 px entre
       dos escrituras de la misma lista)

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
Y0, LINES = 192, 224
LASTXMAX = 316              # LASTX de scroll.s a 320 px (a 256: 255); MSK con el mayor
SEG = 220                   # bytes por linea en la lista del copper (scroll.s: SEG)


def plan(loads):
    """Planifica las cargas de una linea con el modelo MEDIDO del copper en
    DPF (tools/copcal.py, P39): tiempo T en px de pantalla; un MOVE escribe
    en T y T += 16; un WAIT cuesta 32 px (T = max(T + 32, x)); hasta 32 px
    de espera salen mejor con 1-2 MOVE de relleno. Orden: por plazo (EDF)
    entre las liberadas. Carga = (fin anterior, principio nuevo, reg,
    color): se libera en fin + 1 y vence en principio.
    Devuelve [(x en que se escribe, clase, carga)] y cuantas llegan tarde.
    Clase: 0 = WAIT; 1 = MOVE detras del anterior; 2, 3 = con 1 o 2
    rellenos."""
    pend = sorted(loads)
    out, ready, i, late = [], [], 0, 0
    T = -10 ** 6
    while i < len(pend) or ready:
        if not ready and pend[i][0] + 1 > T:
            nxt = pend[i][0] + 1
            while i < len(pend) and pend[i][0] + 1 <= nxt:
                ready.append(pend[i])
                i += 1
        while i < len(pend) and pend[i][0] + 1 <= T:
            ready.append(pend[i])
            i += 1
        ready.sort(key=lambda e: e[1])
        e = ready.pop(0)
        r = e[0] + 1
        g = r - T
        if g <= 0:
            land, k = T, 1
        elif g <= 32:
            k = (g + 15) // 16
            land, k = T + 16 * k, 1 + k
        else:
            land, k = max(T + 32, r), 0
        if land > e[1]:
            late += 1
        out.append((land, k, e))
        T = land + 16
    return out, late
L2W = 848


def main():
    d = render_d.load(os.path.join(WORK, "yi1_d.dat"))
    W, cols = d["W"], d["cols"]
    ini = np.zeros((LINES, 7), np.int32)
    chg = []
    mld = [[] for _ in range(LINES)]
    idx = render_d.l1_index(d)
    for L in range(LINES):
        by_reg = {}
        for ev in d["events"][Y0 + L]:
            by_reg.setdefault(ev[2], []).append(ev)
        row = idx[Y0 + L]
        for r, lst in by_reg.items():
            lst.sort()
            # visible a cam_x: el primer evento con fin >= cam_x
            ini[L, r - 1] = lst[0][3]
            for prev, cur in zip(lst, lst[1:]):
                if cur[3] != prev[3]:
                    # fin REAL del tramo anterior: mkleveld.py reparte los
                    # "derrames" (pixeles fuera de todo tramo) al registro
                    # que conserva el color, asi que despues de prev[1]
                    # puede haber pixeles de r que todavia necesitan el
                    # color viejo. La carga no puede caer antes del ultimo.
                    use = np.nonzero(row[prev[1] + 1:cur[0]] == r)[0]
                    fin = prev[1] + 1 + int(use[-1]) if len(use) else prev[1]
                    chg.append((fin + 1, L * SEG + 8 + (r - 1) * 4 + 2, cur[3], prev[3]))
                    mld[L].append((fin, cur[0], 0x180 + 2 * r, cur[3]))
    chg.sort()
    mlx, mldb = [], bytearray()
    pxs = [[] for _ in range(LINES)]
    late = 0
    for L in range(LINES):
        mldb += struct.pack(">HHHHHH", 0, 0xFFFF, 0, 0, 0, 0)
        mlx.append(len(mldb) // 12)
        out, lt = plan(mld[L])
        late += lt
        for tx, k, (pe, cs, r, c) in out:
            mldb += struct.pack(">HHHHhh", k, tx, r, c, pe + 1 - tx, cs - tx - 6)
            pxs[L].append(tx)
        mldb += struct.pack(">HHHHHH", 0, 0x7FFF, 0, 0, 0, 0)
    mlx.append(len(mldb) // 12)
    print("cargas a mitad de linea que llegan tarde en el plan (modelo medido): %d de %d"
          % (late, len(mldb) // 12 - 2 * LINES))
    nk = W // 16 + 1
    lns_o, lns_d = [], bytearray()
    for k in range(nk):
        lo, hi = 16 * k - 16, 16 * k + 31 + LASTXMAX
        lns_o.append(2 * nk + len(lns_d))
        ls = [32 * L for L in range(LINES) if any(lo <= x <= hi for x in pxs[L])]
        lns_d += struct.pack(">%dH" % (len(ls) + 1), *ls, 0xFFFF)
    lns = struct.pack(">%dH" % nk, *lns_o) + bytes(lns_d)
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
    chgb = (struct.pack(">HHHH", 0, 0, 0, 0)
            + b"".join(struct.pack(">HHHH", *c) for c in chg) + struct.pack(">HHHH", 0xFFFF, 0, 0, 0))
    secs = [bytes(blk), bytes(mp), inib, chgb, bytes(l2), l2p,
            struct.pack(">%dH" % len(mlx), *mlx), bytes(mldb), lns]
    head = b"SMWS" + struct.pack(">HHHHH", W, cols, d["nblk"], d["sky"], len(chg))
    off = len(head) + 2 + 4 * 10
    offs = []
    for s in secs:
        off = (off + 7) & ~7
        offs.append(off)
        off += len(s)
    out = bytearray(head + b"\0\0" + struct.pack(">10I", *offs, 0))
    for o, s in zip(offs, secs):
        out += bytes(o - len(out)) + s
    open(os.path.join(WORK, "yi1_s.dat"), "wb").write(out)
    print("yi1_s.dat: %d bytes, %d bloques, %d cambios de color (capa 1, borrado)"
          % (len(out), d["nblk"], len(chg)))


if __name__ == "__main__":
    main()
