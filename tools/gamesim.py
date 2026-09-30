#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gamesim.py - el binario del juego (player/game.s, work/live/game.bin o
work/game.bin) en Unicorn, para llamar a sus rutinas una por una: lo usan
tools/inputtest.py (la entrada) y tools/diag_read.py (el modo diagnostico
y la reproduccion de una partida desde el historial del joypad).

Hace lo que hace `entry` antes de tomar la maquina (punteros del C al mapa
y a los sprites). Con hw=True mapea tambien las paginas del CIA-A y de los
registros custom, para llamar a read_input con el joystick "apretado".
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import m68kverify as V                          # noqa: E402

WORK = V.WORK
LIVE_BIN = os.path.join(WORK, "live", "game.bin")
LIVE_LST = os.path.join(WORK, "live", "game.lst")
CIAA_PAGE, CUSTOM_PAGE = 0xBFE000, 0xDFF000
SCRATCH = 0xA0000               # memoria libre del emulador (el binario acaba antes)


def build_sign(code, syms):
    """la firma de build_sign (game.s): rol 1 + eor por palabra, cdata0..build_end"""
    s = 0
    for i in range(syms["cdata0"], syms["build_end"], 2):
        s = ((s << 1) | (s >> 15)) & 0xFFFF
        s ^= code[i] << 8 | code[i + 1]
    return s


class GameSim:
    def __init__(self, binp=LIVE_BIN, lst=LIVE_LST, hw=False):
        from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN
        from unicorn import m68k_const as K
        self.K = K
        self.code = open(binp, "rb").read()
        self.syms = V.symbols(lst)
        self.B = V.BASE
        self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        self.uc.ctl_set_cpu_model(K.UC_CPU_M68K_M68000)
        self.uc.mem_map(0, 0x100000)
        self.uc.mem_write(V.RET, b"\x4e\x71")
        if hw:
            self.uc.mem_map(CIAA_PAGE, 0x1000)
            self.uc.mem_map(CUSTOM_PAGE, 0x1000)
            self.set_joy()
        self.uc.mem_write(self.B, self.code)
        s, B = self.syms, self.B
        if "build_sign" in s:
            self.call("build_sign")             # como entry (g_build), antes de tocar nada
        self.w32("_map16_lo", B + s["map16"])
        self.w32("_map16_hi", B + s["map16"] + 20 * 0x1B0)
        self.w32("_spr_level", B + s["spr_lv"])
        self.write(self.a("_level_sprites"), b"\x01")
        self.w32("_gfx32", B + s["gfx32"])

    # ---- memoria y simbolos ----
    def a(self, name):
        return self.B + self.syms[name]

    def has(self, name):
        return name in self.syms

    def read(self, adr, n):
        return bytes(self.uc.mem_read(adr, n))

    def write(self, adr, data):
        self.uc.mem_write(adr, bytes(data))

    def w32(self, name, v):
        self.write(self.a(name), struct.pack(">I", v & 0xFFFFFFFF))

    def r32(self, name):
        return struct.unpack(">I", self.read(self.a(name), 4))[0]

    def r16(self, name, off=0):
        return struct.unpack(">H", self.read(self.a(name) + off, 2))[0]

    def ram(self):
        return self.read(self.a("_ram"), 0x2000)

    def sign(self):
        return build_sign(self.code, self.syms)

    # ---- llamadas ----
    def call(self, name, **regs):
        """llama a la rutina con los registros dados (d0=..., a2=...); devuelve
        {d0..d7, a0..a6} al volver"""
        K = self.K
        names = ["d%d" % i for i in range(8)] + ["a%d" % i for i in range(7)]
        ids = [getattr(K, "UC_M68K_REG_%s" % n.upper()) for n in names]
        for n, i in zip(names, ids):
            self.uc.reg_write(i, regs.get(n, self.B if n == "a4" else 0) & 0xFFFFFFFF)
        self.uc.reg_write(K.UC_M68K_REG_A7, V.STACK - 4)
        self.write(V.STACK - 4, struct.pack(">I", V.RET))
        self.uc.emu_start(self.a(name), V.RET)
        return {n: self.uc.reg_read(i) for n, i in zip(names, ids)}

    # ---- hardware (hw=True) ----
    def set_joy(self, joy1dat=0, fire=False, fire2=False):
        self.write(CUSTOM_PAGE + 0x00C, struct.pack(">H", joy1dat))
        self.write(CUSTOM_PAGE + 0x016, struct.pack(">H", 0 if fire2 else 0xFFFF))
        self.write(CIAA_PAGE + 0x001, bytes([0x7F if fire else 0xFF]))

    # ---- en vivo ----
    def start(self, pada=0, padb=0):
        """el principio del nivel, como live_init/live_restart (sin AllocMem):
        replay_init (historial) + live_start (el primer estado). pada/padb:
        las copias de pad_convert al empezar (DI_PAD0)"""
        self.write(self.a("g_pada"), bytes([pada, padb]))
        self.call("replay_init")
        self.call("live_start")

    def step(self, h, l):
        """un frame en vivo (live_logic): h = byetUDLR, l = axlr----;
        devuelve el motivo (0 = sigue)"""
        return self.call("live_logic", d0=h, d1=l)["d0"] & 0xFF

    def frame(self):
        return self.r32("g_frame")


def replay_pads(path=os.path.join(WORK, "yi1_replay.bin")):
    """[(op, $15, $16, $17, $18)] por frame del replay (m68kverify --replay)"""
    d = open(path, "rb").read()
    n = struct.unpack(">H", d[4:6])[0]
    o = struct.unpack(">I", d[12:16])[0]
    return [tuple(d[o + 6 * k:o + 6 * k + 6][i] for i in (0, 2, 3, 4, 5)) for k in range(n)]
