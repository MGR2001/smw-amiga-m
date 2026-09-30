#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inputtest.py - 6b.3 (ROADMAP 8.2): la entrada de player/game.s en vivo,
corrida en Unicorn sobre el binario de verdad (work/live/game.bin):

  1. pad_convert: joypad -> $15-$18 como el ControllerUpdate de SMW
     (game.s:708): "recien apretado" contra una copia propia del frame
     anterior, A suma a B y X a Y en $15, X suma a Y en $16. Incluye el
     caso de P55: el juego borra $15-$18 (no_buttons) con la tecla
     apretada y el frame siguiente NO tiene que ver un salto nuevo.
  2. read_input: teclado (tabla D14 sobre keymap) y joystick del puerto 2
     (JOY1DAT, boton 1 en CIA-A, boton 2 en POTINP), con el boton 1 fijo en
     A o B mientras no se suelta.

    GDEFS=" " OUT=work/live sh tools/game_build.sh
    python3 tools/inputtest.py              # sale con 1 si falla un caso
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamesim as G                             # noqa: E402

B_, Y_, SEL, STA, U, D, L, R = 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01
A_, X_, LS, RS = 0x80, 0x40, 0x20, 0x10

# (nombre, JOY1H, JOY1L, borrar $15-$18 antes, esperado ($15, $16, $17, $18))
PAD_CASES = [
    ("nada", 0, 0, False, (0, 0, 0, 0)),
    ("aprieta B", B_, 0, False, (B_, B_, 0, 0)),
    ("mantiene B", B_, 0, False, (B_, 0, 0, 0)),
    ("P55: el juego borra $15-$18, B sigue", B_, 0, True, (B_, 0, 0, 0)),
    ("P55: y el frame siguiente", B_, 0, True, (B_, 0, 0, 0)),
    ("suelta B", 0, 0, False, (0, 0, 0, 0)),
    ("vuelve a apretar B", B_, 0, False, (B_, B_, 0, 0)),
    ("B -> A: A cuenta como B en $15, no en $16", 0, A_, False, (B_, 0, A_, A_)),
    ("A -> X: X cuenta como Y en $15 y $16", 0, X_, False, (Y_, Y_, X_, X_)),
    ("X + Y: Y nuevo", Y_, X_, False, (Y_, Y_, X_, 0)),
    ("L + R", 0, LS | RS, False, (0, 0, LS | RS, LS | RS)),
    ("derecha + correr", R | Y_, 0, False, (R | Y_, R | Y_, 0, 0)),
    ("+ salto", R | Y_ | B_, 0, False, (R | Y_ | B_, B_, 0, 0)),
    ("borrado con todo apretado", R | Y_ | B_, 0, True, (R | Y_ | B_, 0, 0, 0)),
    ("Start", STA, 0, False, (STA, STA, 0, 0)),
    ("Select + arriba", SEL | U, 0, False, (SEL | U, SEL | U, 0, 0)),
    ("abajo (suelta Select, mantiene arriba)", U | D, 0, False, (U | D, D, 0, 0)),
]

# teclado: codigos raw de la tabla D14 (game.s keytab)
KEYS = {"up": 0x4C, "down": 0x4D, "right": 0x4E, "left": 0x4F, "z": 0x31, "x": 0x32,
        "a": 0x20, "s": 0x21, "return": 0x44, "rshift": 0x61, "space": 0x40}
# (nombre, teclas, JOY1DAT, boton 1, boton 2, esperado (JOY1H, JOY1L))
JOY_R, JOY_L = 0x0003, 0x0300                   # JOY1DAT: bit 1 (y 0) / bit 9 (y 8)
JOY_DOWN, JOY_UP = 0x0001, 0x0100               # bit 0 ^ bit 1, bit 8 ^ bit 9
IN_CASES = [
    ("nada", [], 0, False, False, (0, 0)),
    ("flechas", ["up", "right"], 0, False, False, (U | R, 0)),
    ("Z = B, X = A", ["z", "x"], 0, False, False, (B_, A_)),
    ("A = Y, S = X", ["a", "s"], 0, False, False, (Y_, X_)),
    ("Return = Start, Shift der. = Select", ["return", "rshift"], 0, False, False, (STA | SEL, 0)),
    ("ESPACIO no es del juego", ["space"], 0, False, False, (0, 0)),
    ("joystick derecha", [], JOY_R, False, False, (R, 0)),
    ("joystick izquierda", [], JOY_L, False, False, (L, 0)),
    ("joystick abajo", [], JOY_DOWN, False, False, (D, 0)),
    ("joystick arriba", [], JOY_UP, False, False, (U, 0)),
    ("boton 2 = Y", [], 0, False, True, (Y_, 0)),
    ("boton 1 = B", [], 0, True, False, (B_, 0)),
    ("boton 1 mantenido + arriba: sigue siendo B", [], JOY_UP, True, False, (U | B_, 0)),
    ("suelta", [], 0, False, False, (0, 0)),
    ("arriba + boton 1 = A", [], JOY_UP, True, False, (U, A_)),
    ("suelta arriba, boton mantenido: sigue siendo A", [], 0, True, False, (0, A_)),
    ("suelta el boton", [], 0, False, False, (0, 0)),
    ("teclado OR joystick", ["z"], JOY_R, False, True, (B_ | R | Y_, 0)),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=G.LIVE_BIN)
    ap.add_argument("--lst", default=G.LIVE_LST)
    ap.add_argument("-v", action="store_true", help="mostrar todos los casos")
    a = ap.parse_args()
    s = G.GameSim(a.bin, a.lst, hw=True)
    for need in ("pad_convert", "read_input", "keymap", "g_pada"):
        if not s.has(need):
            sys.exit("falta %s en %s: armar en vivo (GDEFS=\" \" OUT=work/live)" % (need, a.lst))
    RAM = s.a("_ram")
    bad = 0
    s.write(s.a("g_pada"), b"\0\0")
    for name, h, l, clear, want in PAD_CASES:
        if clear:
            s.write(RAM + 0x15, b"\0\0\0\0")
        s.call("pad_convert", d0=h, d1=l)
        got = tuple(s.read(RAM + 0x15, 4))
        ok = got == want
        bad += not ok
        if a.v or not ok:
            print("%-5s pad_convert %-44s $15-$18 = %s  esperado %s" % (
                "ok" if ok else "FALLO", name, " ".join("%02X" % v for v in got),
                " ".join("%02X" % v for v in want)))
    for name, keys, joy, f1, f2, want in IN_CASES:
        km = bytearray(16)
        for k in keys:
            km[KEYS[k] >> 3] |= 1 << (KEYS[k] & 7)
        s.write(s.a("keymap"), km)
        s.set_joy(joy, f1, f2)
        r = s.call("read_input")
        got = (r["d0"] & 0xFF, r["d1"] & 0xFF)
        ok = got == want
        bad += not ok
        if a.v or not ok:
            print("%-5s read_input  %-44s %02X %02X  esperado %02X %02X" % (
                "ok" if ok else "FALLO", name, got[0], got[1], want[0], want[1]))
    n = len(PAD_CASES) + len(IN_CASES)
    print("inputtest: %d de %d casos bien (pad_convert %d, read_input %d)"
          % (n - bad, n, len(PAD_CASES), len(IN_CASES)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
