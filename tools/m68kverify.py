#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m68kverify.py - corre el codigo 68000 REAL del port (el que compila vbcc y
arma tools/logicbench_build.sh en work/logicbench.bin) en un emulador de CPU
(Unicorn, modelo M68000) contra el oraculo, con el mismo bucle que
`marioverify full`:

  - para cada par de frames N, N+1 de Yoshi's Island 1: estado de N +
    entradas de N+1 (joypad, FrameA) -> _mario_player + _blocks_update
    -> se compara con N+1 en los mismos 24 campos;
  - el mapa y la RAM que no graba el oraculo persisten entre frames y se
    recargan al empezar cada tramo.

Sirve para dos cosas que en la PC de desarrollo no se pueden ver:
  1. que el binario de la Amiga (big-endian, int de 32 bits, vbcc) da
     EXACTAMENTE lo mismo que el C compilado en el PC;
  2. cuanto cuesta un frame del jugador: instrucciones (--count, Unicorn)
     o ciclos de un 68000 SIN esperas de DMA (--engine musashi, el nucleo
     de amitools). Es una cota inferior: en la A500 la CPU pierde ciclos
     con el DMA de pantalla, el copper y el blitter. La medida de verdad
     es la 8d en WinUAE cycle-exact.

    python tools/m68kverify.py [--max N] [--count] [--engine unicorn|musashi]
"""
import argparse
import os
import re
import struct
import sys

PAL_CPU_HZ = 7093790
PAL_FRAME = PAL_CPU_HZ / 50.0           # ciclos de CPU por frame a 50 Hz


class UnicornCPU:
    def __init__(self, count):
        from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
        from unicorn.m68k_const import UC_CPU_M68K_M68000, UC_M68K_REG_A4, UC_M68K_REG_A7
        self.A4, self.A7 = UC_M68K_REG_A4, UC_M68K_REG_A7
        self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        self.uc.ctl_set_cpu_model(UC_CPU_M68K_M68000)
        self.uc.mem_map(0, 0x100000)
        self.uc.mem_write(RET, b"\x4e\x71")
        self.n = 0
        if count:
            self.uc.hook_add(UC_HOOK_CODE, self._hook)

    def _hook(self, u, addr, size, ud):
        self.n += 1

    def write(self, adr, data):
        self.uc.mem_write(adr, bytes(data))

    def read(self, adr, n):
        return bytes(self.uc.mem_read(adr, n))

    def call(self, adr, a4):
        """devuelve instrucciones ejecutadas (0 sin --count)"""
        self.n = 0
        self.uc.reg_write(self.A4, a4)
        self.uc.reg_write(self.A7, STACK - 4)
        self.uc.mem_write(STACK - 4, struct.pack(">I", RET))
        self.uc.emu_start(adr, RET)
        return self.n


class MusashiCPU:
    def __init__(self):
        import machine68k as M
        self.M = M
        self.m = M.Machine(M.CPUType.M68000, 1024)
        self.cpu, self.mem = self.m.cpu, self.m.mem
        tid = self.m.traps.alloc(lambda op, pc: self.m.abort_execute())
        self.mem.w16(RET, 0xA000 | tid)     # linea A: vuelve a Python

    def write(self, adr, data):
        self.mem.w_block(adr, bytes(data))

    def read(self, adr, n):
        return bytes(self.mem.r_block(adr, n))

    def call(self, adr, a4):
        """devuelve ciclos de 68000 (sin esperas de DMA)"""
        M = self.M
        self.cpu.w_reg(M.Register.A4, a4)
        self.cpu.w_reg(M.Register.A7, STACK - 4)
        self.mem.w32(STACK - 4, RET)
        self.cpu.w_pc(adr)
        r = self.m.execute(10_000_000)
        return r.cycles - 34                # la excepcion de linea A del final

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")
REC = 584
BASE = 0x10000              # donde se carga el binario
STACK = 0xF0000
RET = 0xFFFF0               # direccion de vuelta "magica"

# (nombre, direccion SNES, bytes) -- los mismos que tools/marioverify.c
FIELDS = [
    ("XPos $94-95", 0x94, 2), ("YPos $96-97", 0x96, 2), ("SpeedX $7B", 0x7B, 1),
    ("SpeedY $7D", 0x7D, 1), ("SubX $13DA", 0x13DA, 1), ("SubY $13DC", 0x13DC, 1),
    ("AccSpeedX $7A", 0x7A, 1), ("ObjStatus $77", 0x77, 1), ("OnGround $13EF", 0x13EF, 1),
    ("IsFlying $72", 0x72, 1), ("SlopeA $13EE", 0x13EE, 1), ("SlopeB $13E1", 0x13E1, 1),
    ("SlopePose $13ED", 0x13ED, 1), ("Direction $76", 0x76, 1), ("IsDucking $73", 0x73, 1),
    ("DashTimer $13E4", 0x13E4, 1), ("IsSpinJump $140D", 0x140D, 1), ("FrameB $14", 0x14, 1),
    ("MarioFrame $13E0", 0x13E0, 1), ("WalkPose $13DB", 0x13DB, 1),
    ("AnimTimer $1496", 0x1496, 1), ("CapeImage $13DF", 0x13DF, 1),
    ("CapeWave $14A2", 0x14A2, 1), ("FrameIndex $13E5", 0x13E5, 1),
]
ANIM, LOCKED, ONGROUND_SPR = 0x71, 0x9D, 0x1471


def symbols(lst):
    """offsets de los simbolos globales, del final del listado de vasm"""
    syms = {}
    for ln in open(lst, encoding="latin-1"):
        m = re.match(r"^([0-9A-F]{8}) ([A-Za-z_]\w*)$", ln.rstrip())
        if m:
            syms[m.group(2)] = int(m.group(1), 16)
    return syms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=os.path.join(WORK, "logicbench.bin"))
    ap.add_argument("--lst", default=os.path.join(WORK, "logicbench.lst"))
    ap.add_argument("--oracle", default=os.path.join(WORK, "oracle_yi1.bin"))
    ap.add_argument("--map", default=os.path.join(WORK, "yi1_map16.bin"))
    ap.add_argument("--max", type=int, default=0, help="parar despues de N pares")
    ap.add_argument("--count", action="store_true", help="contar instrucciones (Unicorn)")
    ap.add_argument("--engine", choices=("unicorn", "musashi"), default="unicorn")
    a = ap.parse_args()

    code = open(a.bin, "rb").read()
    syms = symbols(a.lst)
    for s in ("_ram", "_map16_lo", "_map16_hi", "_mario_player", "_blocks_update",
              "_mario_unsupported", "map16"):
        if s not in syms:
            sys.exit("falta el simbolo %s en %s" % (s, a.lst))
    RAM = BASE + syms["_ram"]
    MAP = BASE + syms["map16"]
    map0 = open(a.map, "rb").read()
    db = open(a.oracle, "rb").read()
    n = len(db) // REC

    cpu = MusashiCPU() if a.engine == "musashi" else UnicornCPU(a.count)
    measure = a.engine == "musashi" or a.count
    unit = "ciclos 68000 (sin DMA)" if a.engine == "musashi" else "instrucciones 68000"
    cpu.write(BASE, code)
    cpu.write(BASE + syms["_map16_lo"], struct.pack(">I", MAP))
    cpu.write(BASE + syms["_map16_hi"], struct.pack(">I", MAP + len(map0) // 2))

    def call(sym):
        return cpu.call(BASE + syms[sym], BASE)

    def rec(i):
        o = i * REC
        f, tl = struct.unpack_from("<IB", db, o)
        return f, tl, db[o + 8:o + 8 + 256], db[o + 8 + 256:o + REC]

    def orc(r, adr):
        if adr < 0x100:
            return r[2][adr]
        return r[3][adr - 0x13C0]

    pairs = allok = unsup = 0
    bad = [0] * len(FIELDS)
    fails = []
    counts = []
    prev = None
    for i in range(n - 1):
        ri, rj = rec(i), rec(i + 1)
        if prev is None or ri[0] != prev[0] + 1 or prev[1] != 0x29:
            cpu.write(MAP, map0)
            cpu.write(RAM, bytes(0x2000))
        prev = ri
        if rj[0] != ri[0] + 1 or ri[1] != 0x29 or rj[1] != 0x29:
            continue
        if orc(ri, ANIM) or orc(rj, ANIM) or orc(ri, LOCKED) or orc(rj, LOCKED):
            continue
        pairs += 1
        cpu.write(RAM, ri[2])
        cpu.write(RAM + 0x13C0, ri[3])
        cpu.write(RAM + 0x13, bytes([rj[2][0x13]]))
        cpu.write(RAM + 0x15, rj[2][0x15:0x19])
        cpu.write(RAM + 0x1931, b"\x07")
        cost = call("_mario_player")
        if struct.unpack(">i", cpu.read(BASE + syms["_mario_unsupported"], 4))[0] == 0:
            cost += call("_blocks_update")
        if struct.unpack(">i", cpu.read(BASE + syms["_mario_unsupported"], 4))[0]:
            unsup += 1
            continue
        counts.append((cost, rj[0]))
        ram = cpu.read(RAM, 0x2000)
        ok = True
        for k, (name, adr, w) in enumerate(FIELDS):
            want = bytes(orc(rj, adr + t) for t in range(w))
            if bytes(ram[adr:adr + w]) != want:
                bad[k] += 1
                ok = False
        if ok:
            allok += 1
        else:
            fails.append(rj[0])
        if a.max and pairs >= a.max:
            break

    print("binario 68000: %s (%d bytes), CPU M68000 (%s)" % (a.bin, len(code), a.engine))
    print("pares: %d  sin portar: %d  todos los campos: %d  con fallos: %d"
          % (pairs, unsup, allok, len(fails)))
    for k, (name, _, _) in enumerate(FIELDS):
        if bad[k]:
            print("  %-18s %d fallos" % (name, bad[k]))
    if fails:
        print("frames con fallos:", " ".join(str(f) for f in fails[:40]),
              "..." if len(fails) > 40 else "")
    if measure and counts:
        c = sorted(x[0] for x in counts)
        mean = sum(c) / len(c)
        worst = max(counts)
        print("%s por frame (mario_player + blocks_update): media %.0f, mediana %d, "
              "p99 %d, max %d (frame %d)"
              % (unit, mean, c[len(c) // 2], c[int(len(c) * 0.99)], worst[0], worst[1]))
        if a.engine == "musashi":
            print("  = media %.1f %%, max %.1f %% de un frame PAL (%.0f ciclos), sin contar el DMA"
                  % (100 * mean / PAL_FRAME, 100 * worst[0] / PAL_FRAME, PAL_FRAME))


if __name__ == "__main__":
    main()
