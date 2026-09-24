#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m68kprof.py - perfil en CICLOS de 68000 del frame del jugador, por funcion
del C, sobre el binario de perfil (PROF=1 sh tools/logicbench_build.sh:
sin inline y sin "static", para que cada funcion tenga su simbolo).

Ejecuta instruccion a instruccion en Musashi (el nucleo de amitools) los
mismos frames del oraculo que tools/m68kverify.py y reparte los ciclos
entre las funciones (ciclos PROPIOS, sin las llamadas). Sin esperas de
DMA: sirve para saber DONDE se va el tiempo, no cuanto cuesta en la A500.

    PROF=1 sh tools/logicbench_build.sh
    python tools/m68kprof.py [--every 10]
"""
import argparse
import bisect
import collections
import os
import struct

import m68kverify as V

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=os.path.join(WORK, "prof", "logicbench.bin"))
    ap.add_argument("--lst", default=os.path.join(WORK, "prof", "logicbench.lst"))
    ap.add_argument("--every", type=int, default=10, help="perfilar 1 de cada N frames")
    a = ap.parse_args()

    syms = V.symbols(a.lst)
    data = {"_ram", "_rom00", "_map16_lo", "_map16_hi", "_mario_events", "_mario_unsupported"}
    funcs = sorted((V.BASE + v, k) for k, v in syms.items() if k.startswith("_") and k not in data)
    starts = [f[0] for f in funcs]
    code = open(a.bin, "rb").read()
    map0 = open(os.path.join(WORK, "yi1_map16.bin"), "rb").read()
    db = open(os.path.join(WORK, "oracle_yi1.bin"), "rb").read()
    RAM, MAP = V.BASE + syms["_ram"], V.BASE + syms["map16"]

    cpu = V.MusashiCPU()
    M = cpu.M
    cpu.write(V.BASE, code)
    cpu.write(V.BASE + syms["_map16_lo"], struct.pack(">I", MAP))
    cpu.write(V.BASE + syms["_map16_hi"], struct.pack(">I", MAP + len(map0) // 2))
    cpu.write(MAP, map0)

    prof = collections.Counter()
    calls = collections.Counter()

    def run(sym):
        c = cpu.cpu
        c.w_reg(M.Register.A4, V.BASE)
        c.w_reg(M.Register.A7, V.STACK - 4)
        cpu.mem.w32(V.STACK - 4, V.RET)
        c.w_pc(V.BASE + syms[sym])
        total = 0
        while True:
            pc = c.r_pc()
            if pc == V.RET:
                break
            i = bisect.bisect_right(starts, pc) - 1
            name = funcs[i][1] if i >= 0 else "?"
            if i >= 0 and pc == funcs[i][0]:
                calls[name] += 1
            r = cpu.m.execute(1)
            prof[name] += r.cycles
            total += r.cycles
        return total

    n = len(db) // V.REC
    frames = 0
    prev = None
    for i in range(n - 1):
        o, p = i * V.REC, (i + 1) * V.REC
        fi, ti = struct.unpack_from("<IB", db, o)
        fj, tj = struct.unpack_from("<IB", db, p)
        if prev is None or fi != prev[0] + 1 or prev[1] != 0x29:
            cpu.write(MAP, map0)
            cpu.write(RAM, bytes(0x2000))
        prev = (fi, ti)
        if fj != fi + 1 or ti != 0x29 or tj != 0x29:
            continue
        ri, rj = db[o + 8:o + V.REC], db[p + 8:p + V.REC]
        if ri[0x71] or rj[0x71] or ri[0x9D] or rj[0x9D]:
            continue
        cpu.write(RAM, ri[:256])
        cpu.write(RAM + 0x13C0, ri[256:])
        cpu.write(RAM + 0x13, rj[0x13:0x14])
        cpu.write(RAM + 0x15, rj[0x15:0x19])
        cpu.write(RAM + 0x1931, b"\x07")
        if i % a.every:
            cpu.call(V.BASE + syms["_mario_player"], V.BASE)     # sin perfilar
            cpu.call(V.BASE + syms["_blocks_update"], V.BASE)
            continue
        run("_mario_player")
        run("_blocks_update")
        frames += 1

    tot = sum(prof.values())
    print("perfil de %d frames (1 de cada %d), %s" % (frames, a.every, a.bin))
    print("media: %.0f ciclos por frame (sin DMA; sin inline es algo mas caro que el build real)"
          % (tot / frames))
    print("%-22s %9s %7s %9s" % ("funcion", "ciclos/fr", "%", "llamadas/fr"))
    for name, cyc in prof.most_common(25):
        print("%-22s %9.0f %6.1f%% %9.1f" % (name, cyc / frames, 100.0 * cyc / tot, calls[name] / frames))


if __name__ == "__main__":
    main()
