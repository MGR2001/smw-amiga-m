#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m68kprof.py - perfil en CICLOS de 68000 del frame del jugador, por funcion
del C, sobre el binario de perfil (PROF=1 sh tools/logicbench_build.sh:
sin inline y sin "static", para que cada funcion tenga su simbolo).

Ejecuta instruccion a instruccion en Musashi (el nucleo de amitools) los
mismos frames del oraculo que tools/m68kverify.py (un _level_frame desde
el estado grabado de cada frame) y reparte los ciclos
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
    ap.add_argument("--worst", type=int, default=0,
                    help="ademas: los N frames mas caros, con el perfil por funcion del peor")
    ap.add_argument("--at", type=int, action="append", default=[],
                    help="con --worst: tambien el perfil de este frame")
    ap.add_argument("--hot", type=int, default=0,
                    help="ademas: las N lineas del listado con mas ciclos y el resumen por instruccion")
    ap.add_argument("--sprites", action="store_true",
                    help="_level_sprites = 1: el frame corre tambien los sprites (etapa 9)")
    a = ap.parse_args()

    syms = V.symbols(a.lst)
    data = {"_ram", "_rom00", "_map16_lo", "_map16_hi", "_mario_events", "_mario_unsupported",
            "_spr_level", "_spr_spawned", "_level_sprites"}
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
    if a.sprites:
        spr = open(os.path.join(HERE, "..", "..", "smw-src-master", "project", "mw_e10", "levels",
                                "data", "world_1", "1", "spr.lv"), "rb").read()
        SPR = V.BASE + ((len(code) + 0x103) & ~3)
        cpu.write(SPR, spr)
        cpu.write(V.BASE + syms["_spr_level"], struct.pack(">I", SPR))
        cpu.write(V.BASE + syms["_level_sprites"], b"\x01")

    prof = collections.Counter()
    perpc = collections.Counter()
    per_frame = []
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
            if a.hot:
                perpc[pc] += r.cycles
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
        cpu.write(RAM, ri[:256])                  # estado de N + joypad de N+1
        cpu.write(RAM + 0x13C0, ri[256:])
        cpu.write(RAM + 0x15, rj[0x15:0x19])
        cpu.write(RAM + 0x1931, b"\x07")
        if a.sprites:
            cpu.write(RAM + 0x1692, bytes([spr[0] & 0x3F]))   # wm_SpriteMemory
            cpu.write(RAM + 0x1430, b"\xff\xff")
        cpu.write(RAM + 0x13, bytes([(ri[0x13] + 0) & 255]))   # level_frame lo sube a N+1
        if i % a.every:
            cpu.call(V.BASE + syms["_level_frame"], V.BASE)      # sin perfilar
            continue
        before = collections.Counter(prof)
        t = run("_level_frame")
        frames += 1
        if a.worst:
            per_frame.append((t, fi, collections.Counter({k: prof[k] - before[k] for k in prof})))

    tot = sum(prof.values())
    print("perfil de %d frames (1 de cada %d), %s" % (frames, a.every, a.bin))
    print("media: %.0f ciclos por frame (sin DMA; sin inline es algo mas caro que el build real)"
          % (tot / frames))
    print("%-22s %9s %7s %9s" % ("funcion", "ciclos/fr", "%", "llamadas/fr"))
    for name, cyc in prof.most_common(25):
        print("%-22s %9.0f %6.1f%% %9.1f" % (name, cyc / frames, 100.0 * cyc / tot, calls[name] / frames))

    if a.hot:
        hot_report(a, perpc, frames, tot)
    if a.worst:
        per_frame.sort(key=lambda r: -r[0])
        print()
        print("los %d frames mas caros (estado del oraculo + joypad; sin inline):" % a.worst)
        for t, fi, _ in per_frame[:a.worst]:
            print("  frame %5d  %6d ciclos" % (fi, t))
        for t, fi, pf in [per_frame[0]] + [r for r in per_frame if r[1] in a.at]:
            print("perfil del frame %d (%d ciclos):" % (fi, t))
            for name, cyc in pf.most_common(20):
                print("  %-22s %6d %5.1f%%" % (name, cyc, 100.0 * cyc / t))


def hot_report(a, perpc, frames, tot):
    """lineas del listado de vasm con mas ciclos, y ciclos por mnemonico"""
    import re
    src = {}
    for ln in open(a.lst, encoding="latin-1"):
        m = re.match(r"^\d\d:([0-9A-F]{8}) \S*\s+\d+: (.*)$", ln.rstrip())
        if m:
            src[V.BASE + int(m.group(1), 16)] = m.group(2).strip()
    print()
    print("las %d instrucciones con mas ciclos por frame:" % a.hot)
    for pc, cyc in perpc.most_common(a.hot):
        print("  %6.0f %5.1f%%  %06X  %s" % (cyc / frames, 100.0 * cyc / tot, pc - V.BASE, src.get(pc, "?")[:70]))
    kind = collections.Counter()
    for pc, cyc in perpc.items():
        t = src.get(pc, "?").split()
        op = t[0] if t and not t[0].endswith(":") else (t[1] if len(t) > 1 else "?")
        arg = " ".join(t[1:]) if t and not t[0].endswith(":") else " ".join(t[2:])
        mem = "ram" if "_ram" in arg else ("rom" if "_rom00" in arg else "")
        kind[(op.split(".")[0], mem)] += cyc
    print("ciclos por mnemonico (y si toca _ram / _rom00 por nombre):")
    for (op, mem), cyc in kind.most_common(20):
        print("  %-8s %-4s %7.0f %5.1f%%" % (op, mem, cyc / frames, 100.0 * cyc / tot))


if __name__ == "__main__":
    main()
