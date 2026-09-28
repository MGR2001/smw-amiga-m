#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gamecheck.py - Etapa 6.3: corre la parte de CPU de player/game.s -DREPLAY
(work/game.bin, tools/game_build.sh) en un emulador de 68000, frame a
frame, y comprueba que sigue la partida grabada como el lazo cerrado del
PC (m68kverify.py --mode loop --sprites): despues de cada frame RUN, los
campos de Mario y de la camara tienen que ser los del oraculo.

Hace lo que hace `entry` antes de tomar la maquina (punteros del C al mapa
y a los sprites) y despues llama a replay_init y a game_step por frame. No
corre el scroll (eso lo miran scrollprof.py / scrollsim.py y las
capturas): solo la entrada, la logica y las resincronizaciones.

    python3 tools/gamecheck.py                  # Unicorn (rapido)
    python3 tools/gamecheck.py --engine musashi # + ciclos por frame (sin DMA)
    python3 tools/gamecheck.py --cams 5400,6500 # la camara en esos frames
    python3 tools/gamecheck.py --spr            # + mario_sprite (mspr.c, 6b.4)
                                                #   contra un render de referencia
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import m68kverify as V                          # noqa: E402

PAL_FRAME = V.PAL_FRAME


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=os.path.join(V.WORK, "game.bin"))
    ap.add_argument("--lst", default=os.path.join(V.WORK, "game.lst"))
    ap.add_argument("--oracle", default=os.path.join(V.WORK, "oracle_yi1.bin"))
    ap.add_argument("--engine", choices=("unicorn", "musashi"), default="unicorn")
    ap.add_argument("--cams", default="", help="frames (del oraculo) de los que dar la camara")
    ap.add_argument("--spr", action="store_true",
                    help="despues de cada frame, _mario_sprite (vbcc) contra la referencia")
    a = ap.parse_args()

    code = open(a.bin, "rb").read()
    syms = V.symbols(a.lst)
    for s in ("replay_init", "game_step", "replay", "_ram", "map16", "spr_lv",
              "_map16_lo", "_map16_hi", "_spr_level", "_level_sprites", "g_left"):
        if s not in syms:
            sys.exit("falta el simbolo %s en %s (armar con -DREPLAY)" % (s, a.lst))
    B = V.BASE
    cpu = V.MusashiCPU() if a.engine == "musashi" else V.UnicornCPU(False)
    cpu.write(B, code)
    # lo que hace entry con a4 = binstart
    cpu.write(B + syms["_map16_lo"], struct.pack(">I", B + syms["map16"]))
    cpu.write(B + syms["_map16_hi"], struct.pack(">I", B + syms["map16"] + 20 * 0x1B0))
    cpu.write(B + syms["_spr_level"], struct.pack(">I", B + syms["spr_lv"]))
    cpu.write(B + syms["_level_sprites"], b"\x01")
    cpu.call(B + syms["replay_init"], B)
    if a.spr:
        cpu.write(B + syms["_gfx32"], struct.pack(">I", B + syms["gfx32"]))
        g32 = cpu.read(B + syms["gfx32"], 0x5D00)
    sprbad = sprn = asmbad = 0

    rp = B + syms["replay"]
    nframes, first, nst = struct.unpack(">HHH", cpu.read(rp + 4, 6))
    o_ops = struct.unpack(">I", cpu.read(rp + 12, 4))[0]
    ops = cpu.read(rp + o_ops, 6 * nframes)[0::6]

    db = open(a.oracle, "rb").read()
    n = len(db) // V.REC
    orc = {}
    for i in range(n):
        f, tl = struct.unpack_from("<IB", db, i * V.REC)
        if first <= f < first + nframes:
            o = i * V.REC + 8
            orc[f] = (db[o:o + 256], db[o + 256:o + 576])

    def want(f, adr):
        dp, w13 = orc[f]
        return dp[adr] if adr < 0x100 else w13[adr - 0x13C0]

    RAM = B + syms["_ram"]
    fields = V.FIELDS + V.LOOP_FIELDS
    bad, runs, costs, cams = [], 0, [], {}
    wantcam = {int(x) for x in a.cams.split(",") if x}
    for k in range(nframes):
        f = first + k
        c = cpu.call(B + syms["game_step"], B)
        ram = cpu.read(RAM, 0x2000)
        if f in wantcam:
            cams[f] = (ram[0x1A] | ram[0x1B] << 8, want(f, 0x1A) | want(f, 0x1B) << 8)
        if a.spr and ops[k] != V.REP_SKIP:
            sprn += 1
            if not spr_ok(cpu, B, syms, g32, False):
                sprbad += 1
            if not spr_ok(cpu, B, syms, g32, True):
                asmbad += 1
        if ops[k] == V.REP_SKIP:
            continue
        if ops[k] == V.REP_RUN:
            runs += 1
            costs.append((c, f))
        miss = [nm for nm, adr, w in fields
                if any(ram[adr + t] != want(f, adr + t) for t in range(w))]
        if miss:
            bad.append((f, ops[k], miss))
    left = struct.unpack(">H", cpu.read(B + syms["g_left"], 2))[0]
    print("game.bin (%s): replay de %d frames desde %d (%d RUN), quedan %d; frames que no "
          "coinciden con el oraculo: %d" % (a.engine, nframes, first, runs, left, len(bad)))
    for f, op, miss in bad[:10]:
        print("  frame %d (op %d): %s" % (f, op, ", ".join(miss)))
    if a.spr:
        slow = struct.unpack(">H", cpu.read(B + syms["mspr_slow"], 2))[0]
        print("mario_sprite (vbcc) = referencia en %d de %d frames; mspr_draw (asm): %d "
              "(fue al C en %d)" % (sprn - sprbad, sprn, sprn - asmbad, slow))
    for f in sorted(cams):
        print("  camara en el frame %d: %d (oraculo %d)" % (f, cams[f][0], cams[f][1]))
    if a.engine == "musashi" and costs:
        c = sorted(x[0] for x in costs)
        w = max(costs)
        print("ciclos por game_step RUN (sin DMA): media %.0f (%.1f %%), max %d (%.1f %%, frame %d)"
              % (sum(c) / len(c), 100 * sum(c) / len(c) / PAL_FRAME, w[0], 100 * w[0] / PAL_FRAME, w[1]))
    return 1 if bad or (a.spr and (sprbad or asmbad)) else 0


SPRW = 2 + 2 * 40 + 2           # mario.h: MSPR_WORDS
SPRBUF = 0xE0000                # buffer de los sprites en la memoria del emulador


def spr_ok(cpu, B, syms, g32, asm):
    """_mario_sprite(SPRBUF, $2C, $A0) (o mspr_draw con a2 = SPRBUF, asm)
    decodificado = render de la OAM de Mario (mario_oam) con la VRAM armada
    como el DMA del NMI (ver marioverify mspr)"""
    st = V.STACK - 4
    cpu.write(st + 4, struct.pack(">III", SPRBUF, 0x2C, 0xA0))
    cpu.write(SPRBUF, bytes([0x55]) * (8 * SPRW))
    call_args(cpu, B + syms["mspr_draw" if asm else "_mario_sprite"], B, SPRBUF)
    ram = cpu.read(B + syms["_ram"], 0x2000)
    oam = cpu.read(B + syms["_mario_oam"], 16)
    osz = cpu.read(B + syms["_mario_osz"], 4)
    sp = struct.unpack(">%dH" % (4 * SPRW), cpu.read(SPRBUF, 8 * SPRW))
    got = {}
    for col in range(2):
        a, b = sp[2 * col * SPRW:(2 * col + 1) * SPRW], sp[(2 * col + 1) * SPRW:(2 * col + 2) * SPRW]
        if a[0] == 0 and a[1] == 0:
            continue
        if not b[1] & 0x80:
            return False
        vs = (a[0] >> 8) | ((a[1] >> 2) & 1) << 8
        ve = (a[1] >> 8) | ((a[1] >> 1) & 1) << 8
        hs = ((a[0] & 0xFF) << 1) | (a[1] & 1)
        for l in range(ve - vs):
            for x in range(16):
                c = (((a[2 + 2 * l] >> (15 - x)) & 1) | (((a[3 + 2 * l] >> (15 - x)) & 1) << 1)
                     | (((b[2 + 2 * l] >> (15 - x)) & 1) << 2) | (((b[3 + 2 * l] >> (15 - x)) & 1) << 3))
                if c:
                    got[(hs - 0xA0 + x, vs - 0x2C - 1 + l)] = c
    vram = {}
    for r in range(2):
        for i in range(5):
            o = 0x0D85 + 10 * r + 2 * i
            p = (ram[o] | ram[o + 1] << 8) - 0x2000
            if 0 <= p <= len(g32) - 64:
                vram[16 * r + 2 * i] = g32[p:p + 32]
                vram[16 * r + 2 * i + 1] = g32[p + 32:p + 64]
    p = (ram[0x0D99] | ram[0x0D9A] << 8) - 0x2000
    if 0 <= p <= len(g32) - 32:
        vram[0x7F] = g32[p:p + 32]
    want = {}
    for e in range(3, -1, -1):              # la primera tapa a las demas
        o = oam[4 * e:4 * e + 4]
        if o[1] == 0xF0:
            continue
        sz = 16 if osz[e] & 2 else 8
        ex = o[0] | ((osz[e] & 1) << 8)
        ex = ex - 512 if ex >= 256 else ex
        ey = o[1] - 256 if o[1] >= 0xF0 else o[1]
        for v in range(sz):
            for u in range(sz):
                uu = sz - 1 - u if o[3] & 0x40 else u
                vv = sz - 1 - v if o[3] & 0x80 else v
                t = o[2] + (uu >> 3) + 16 * (vv >> 3)
                if t not in vram:
                    continue
                tl, x, y = vram[t], uu & 7, vv & 7
                c = (((tl[2 * y] >> (7 - x)) & 1) | (((tl[2 * y + 1] >> (7 - x)) & 1) << 1)
                     | (((tl[16 + 2 * y] >> (7 - x)) & 1) << 2) | (((tl[17 + 2 * y] >> (7 - x)) & 1) << 3))
                if c:
                    want[(ex + u, ey + v)] = c
    want = {k: v for k, v in want.items() if 0 <= k[0] < 256 and 0 <= k[1] < 240}
    got = {k: v for k, v in got.items() if 0 <= k[0] < 256 and 0 <= k[1] < 240}
    return got == want


def call_args(cpu, adr, a4, a2=0):
    """como cpu.call, sin tocar los argumentos ya escritos en la pila"""
    if isinstance(cpu, V.MusashiCPU):
        M = cpu.M
        cpu.cpu.w_reg(M.Register.A2, a2)
        cpu.cpu.w_reg(M.Register.A4, a4)
        cpu.cpu.w_reg(M.Register.A7, V.STACK - 4)
        cpu.mem.w32(V.STACK - 4, V.RET)
        cpu.cpu.w_pc(adr)
        cpu.m.execute(10_000_000)
    else:
        from unicorn.m68k_const import UC_M68K_REG_A2
        cpu.uc.reg_write(UC_M68K_REG_A2, a2)
        cpu.uc.reg_write(cpu.A4, a4)
        cpu.uc.reg_write(cpu.A7, V.STACK - 4)
        cpu.uc.mem_write(V.STACK - 4, struct.pack(">I", V.RET))
        cpu.uc.emu_start(adr, V.RET)


if __name__ == "__main__":
    sys.exit(main())
