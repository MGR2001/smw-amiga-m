#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
copcal.py - calibracion del copper para el scroll (etapa 6, P39).

Genera las lineas de prueba de player/copcal.s (work/copcal_lines.i) y
lee la captura: en que x de pantalla cambia COLOR01 en cada prueba.
Pantalla = la de scroll.s: DPF de 6 planos, DDFSTRT $30 / DDFSTOP $D0,
DIW $2C81-$2CC1 (320 px), todo PF1 = indice 1, sin DMA de sprites.

Cada prueba ocupa 4 lineas; cada linea empieza con WAIT (v, $07) y
COLOR01 = blanco, y despues la secuencia de la prueba (colores distintos
para poder separar cada escritura en la captura).

    python3 tools/copcal.py gen
    vasmm68k_mot -Fbin -m68000 -I player -I work -o work/copcal.bin player/copcal.s
    python3 tools/mkadf.py --boot work/boot.bin --stage2 work/copcal.bin --out work/copcal.adf
    sh tools/fsuae_shot.sh work/copcal.adf work/copcal.png 40
    python3 tools/copcal.py read --shot work/copcal.png
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")
COLORS = [0xF00, 0x0F0, 0x00F, 0xFF0, 0x0FF, 0xF0F, 0x800, 0x080, 0x008]
V0, STEP, REP = 0x30, 10, 4

# prueba: lista de ("W", h) o ("M", k) (MOVE COLOR01 = COLORS[k]) o
# ("P", n) (n MOVE de relleno a COLOR02..07/09..15, como el borrado)
TESTS = [("wait h=$%02X" % h, [("W", h), ("M", 0)])
         for h in (0x38, 0x40, 0x48, 0x50, 0x60, 0x80, 0xA0, 0xC0, 0xD8)]
TESTS_RIGHT = [("wait h=$%02X (borde derecho)" % h, [("W", h), ("M", 0)])
               for h in (0xC8, 0xCC, 0xD0, 0xD4, 0xDC, 0xE0, 0xE2)]
TESTS += [
    ("cadena de 6 MOVE tras WAIT $50", [("W", 0x50)] + [("M", k) for k in range(6)]),
    ("WAIT $50 repetido entre MOVE", [("W", 0x50), ("M", 0), ("W", 0x50), ("M", 1), ("W", 0x50), ("M", 2)]),
    ("WAIT cada 8 cc (16 px)", [("W", 0x50), ("M", 0), ("W", 0x58), ("M", 1), ("W", 0x60), ("M", 2), ("W", 0x68), ("M", 3)]),
    ("WAIT cada 12 cc (24 px)", [("W", 0x50), ("M", 0), ("W", 0x5C), ("M", 1), ("W", 0x68), ("M", 2), ("W", 0x74), ("M", 3)]),
    ("borrado (2 W + 14 MOVE) + WAIT $40", [("P", 14), ("W", 0x40), ("M", 0), ("W", 0x48), ("M", 1)]),
    ("borrado + WAIT $60", [("P", 14), ("W", 0x60), ("M", 0)]),
    ("borrado (v,$07) 14 MOVE, sin WAIT: fin", [("P", 14), ("M", 0)]),
    ("borrado (v-1,$E2) 14 MOVE: fin", [("B", 0), ("P", 14), ("M", 0)]),
    ("borrado (v-1,$E2) 7 MOVE: fin", [("B", 0), ("P", 7), ("M", 0)]),
    ("borrado (v-1,$E2) 14 + WAIT $40", [("B", 0), ("P", 14), ("W", 0x40), ("M", 0)]),
    ("borrado (v-1,$D8) 14 MOVE: fin", [("B", 1), ("P", 14), ("M", 0)]),
]
# COPCAL_FINE=1: la h de a 2 (no solo multiplos de 8: con 6 planos el
# copper tiene una ranura cada 8 cc) y retardos de BPLCON1 ("D", d); para
# leer con tools/copcal_fine.py y el binario armado con -DPATTERN
TESTS_FINE = ([("wait h=$%02X" % h, [("W", h), ("M", 0)]) for h in range(0x40, 0x60, 2)]
              + [("wait h=$%02X" % h, [("W", h), ("M", 0)]) for h in range(0x88, 0x92, 2)]
              + [("d=%d wait h=$80" % d, [("D", d), ("W", 0x80), ("M", 0)]) for d in (0, 4, 8, 12, 15)]
              + [("d=%d wait h=$8E" % d, [("D", d), ("W", 0x8E), ("M", 0)]) for d in (0, 12)])
if os.environ.get("COPCAL_RIGHT"):
    TESTS = TESTS_RIGHT
# COPCAL_FINE=2: borde derecho de a 2 y WAIT despues de un MOVE
TESTS_FINE2 = ([("wait h=$%02X" % h, [("W", h), ("M", 0)]) for h in range(0xC8, 0xE4, 2)]
               + [("W$50 M W$%02X M" % h, [("W", 0x50), ("M", 1), ("W", h), ("M", 0)])
                  for h in range(0x5C, 0x6A, 2)])
# COPCAL_W256=1/2 (armar copcal.s con -DW256 -DPATTERN): la pantalla de
# 256 px (D10), h de a 2 en toda la linea, en dos tandas
TESTS_W256 = {
    "1": [("wait h=$%02X" % h, [("W", h), ("M", 0)]) for h in range(0x3C, 0x80, 2)],
    "2": [("wait h=$%02X" % h, [("W", h), ("M", 0)]) for h in range(0x80, 0xC4, 2)],
    "3": ([("wait h=$%02X" % h, [("W", h), ("M", 0)]) for h in range(0xC4, 0xE4, 2)]
          + [("W$60 M M M", [("W", 0x60), ("M", 0), ("M", 1), ("M", 2)]),
             ("W$60 M W$60 M", [("W", 0x60), ("M", 0), ("W", 0x60), ("M", 1)]),
             ("borrado (v-1,$E2) 7 MOVE: fin", [("B", 0), ("P", 7), ("M", 0)])]),
}
if os.environ.get("COPCAL_W256"):
    TESTS, STEP = TESTS_W256[os.environ["COPCAL_W256"]], 5
elif os.environ.get("COPCAL_FINE") == "2":
    TESTS, STEP = TESTS_FINE2, 7
elif os.environ.get("COPCAL_FINE"):
    TESTS, STEP = TESTS_FINE, 7


def gen():
    out = ["; generado por tools/copcal.py: NO editar"]
    for i, (name, seq) in enumerate(TESTS):
        out.append("; prueba %d: %s" % (i, name))
        for r in range(REP):
            v = V0 + i * STEP + r
            b = [a for op, a in seq if op == "B"]
            if b:                                   # borrado en la linea anterior
                out.append("        dc.w    $%04X,$FFFE,$0182,$0FFF"
                           % (((v - 1) << 8) | (0xE3 if b[0] == 0 else 0xD9)))
            else:
                out.append("        dc.w    $%04X,$FFFE,$0182,$0FFF" % ((v << 8) | 0x07))
            if any(op == "P" for op, _ in seq) and not b:
                out.append("        dc.w    $%04X,$FFFE" % ((v << 8) | 0x07))
            for op, a in seq:
                if op == "W":
                    out.append("        dc.w    $%04X,$FFFE" % ((v << 8) | (a & 0xFE) | 1))
                elif op == "M":
                    out.append("        dc.w    $0182,$%04X" % COLORS[a])
                elif op == "B":
                    pass
                elif op == "D":                     # BPLCON1 = retardo d en PF1 y PF2
                    out.append("        dc.w    $0102,$%04X" % (a * 0x11))
                else:
                    regs = [0x184 + 2 * k for k in range(6)] + [0x192 + 2 * k for k in range(7)]
                    for k in range(a):
                        out.append("        dc.w    $%04X,$0000" % regs[k % len(regs)])
    open(os.path.join(WORK, "copcal_lines.i"), "w").write("\n".join(out) + "\n")
    print("%d pruebas -> work/copcal_lines.i" % len(TESTS))


def c12(p):
    return (int(p[0]) // 17) << 8 | (int(p[1]) // 17) << 4 | int(p[2]) // 17


def read(shot, x0, y0, sc):
    from PIL import Image
    img = np.asarray(Image.open(shot).convert("RGB")).astype(int)
    for i, (name, seq) in enumerate(TESTS):
        v = V0 + i * STEP + 1                       # la segunda de las 4 lineas
        cy = int(y0 + (v - 0x2C + 0.5) * sc)
        row = img[cy]
        marks = []
        prev = None
        for x in range(-16, 336):
            cx = int(x0 + (x + 0.5) * sc)
            if cx < 0 or cx >= img.shape[1]:
                continue
            c = c12(row[cx])
            if c != prev:
                if c in COLORS:
                    marks.append("x=%d:%03X" % (x, c))
                prev = c
        print("%2d %-38s %s" % (i, name, " ".join(marks)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("gen", "read"))
    ap.add_argument("--shot", default=os.path.join(WORK, "copcal.png"))
    ap.add_argument("--x0", type=float, default=171.375)   # origen de la x = 0 (scroll_check)
    ap.add_argument("--y0", type=float, default=112.0)
    ap.add_argument("--sc", type=float, default=2.125)
    a = ap.parse_args()
    if a.cmd == "gen":
        gen()
    else:
        read(a.shot, a.x0, a.y0, a.sc)


if __name__ == "__main__":
    main()
