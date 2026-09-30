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
    ap.add_argument("--mode", choices=("full", "loop"), default="full",
                    help="full: estado de N + entradas de N+1 (como marioverify full); "
                         "loop: lazo cerrado con _level_frame, solo el joypad")
    ap.add_argument("--dump", type=int, default=None,
                    help="loop: guardar ram[] y el mapa justo antes del level_frame de este frame "
                         "(work/cc/worst_ram.bin, worst_map.bin: para logicbench -DWORST)")
    ap.add_argument("--sprites", action="store_true",
                    help="loop con _level_sprites = 1: los sprites del nivel los corre el "
                         "binario (como marioverify game, pero TODOS: los sin portar no hacen nada)")
    ap.add_argument("--replay", default=None,
                    help="loop: escribir el replay del tramo mas largo para player/game.s "
                         "(-DREPLAY, etapa 6.3): el joypad de cada frame y las resincronizaciones")
    ap.add_argument("--cross", default=None, metavar="LIB",
                    help="loop: el C del PC (gcc -shared -DNOOAM, p. ej. work/libport.so) en "
                         "paralelo: antes de cada llamada se le copia la RAM y el mapa del 68000 y "
                         "despues se comparan enteros (P38: un fallo de vbcc o de logic68k.s)")
    ap.add_argument("--show", default="",
                    help="loop: imprimir los ciclos de cada frame en este rango (F0-F1)")
    ap.add_argument("--spr", default=os.path.join(HERE, "..", "..", "smw-src-master", "project",
                                                  "mw_e10", "levels", "data", "world_1", "1", "spr.lv"))
    a = ap.parse_args()

    code = open(a.bin, "rb").read()
    syms = symbols(a.lst)
    for s in ("_ram", "_map16_lo", "_map16_hi", "_mario_player", "_blocks_update", "_mario_E2BD",
              "_level_frame",
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

    pc = PCPort(a.cross, len(map0), a.spr if a.sprites else None) if a.cross else None

    def call(sym):
        if pc is None or sym not in ("_level_frame", "_level_start_sprites"):
            return cpu.call(BASE + syms[sym], BASE)
        pc.before(cpu.read(RAM, 0x2000), cpu.read(MAP, len(map0)))
        cyc = cpu.call(BASE + syms[sym], BASE)
        pc.after(sym[1:], cpu.read(RAM, 0x2000), cpu.read(MAP, len(map0)),
                 struct.unpack(">i", cpu.read(BASE + syms["_mario_unsupported"], 4))[0])
        return cyc

    def rec(i):
        o = i * REC
        f, tl = struct.unpack_from("<IB", db, o)
        return f, tl, db[o + 8:o + 8 + 256], db[o + 8 + 256:o + REC]

    def orc(r, adr):
        if adr < 0x100:
            return r[2][adr]
        return r[3][adr - 0x13C0]

    if a.mode == "loop":
        ret = run_loop(a, cpu, call, rec, orc, n, RAM, MAP, map0, syms)
        if pc is not None:
            pc.report()
        return ret

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
        cpu.write(RAM + 0x1A, rj[2][0x1A:0x1E])     # camara de N+1 (etapa 6)
        cpu.write(RAM + 0x1931, b"\x07")
        cpu.write(RAM + 0x0200, bytes([0, 0xF0, 0, 0]) * 128)   # wm_ClearOam (x/tile/prop sin importar)
        cost = call("_mario_E2BD")
        cost += call("_mario_player")
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
        print("%s por frame (mario_E2BD + mario_player + blocks_update): media %.0f, mediana %d, "
              "p99 %d, max %d (frame %d)"
              % (unit, mean, c[len(c) // 2], c[int(len(c) * 0.99)], worst[0], worst[1]))
        if a.engine == "musashi":
            print("  = media %.1f %%, max %.1f %% de un frame PAL (%.0f ciclos), sin contar el DMA"
                  % (100 * mean / PAL_FRAME, 100 * worst[0] / PAL_FRAME, PAL_FRAME))


class PCPort:
    """--cross: el mismo C compilado para el PC (ctypes) llamado con la RAM y el
    mapa que tiene el 68000 justo antes de cada llamada; despues se comparan
    ram[], el mapa y mario_unsupported. Asi cada diferencia es de UNA llamada
    (no se arrastra) y no depende del oraculo: vbcc (P38) o logic68k.s."""

    def __init__(self, path, maplen, sprpath):
        import ctypes
        self.C = ctypes
        self.lib = ctypes.CDLL(os.path.abspath(path))
        self.ram = (ctypes.c_ubyte * 0x2000).in_dll(self.lib, "ram")
        self.map = (ctypes.c_ubyte * maplen)()
        ctypes.c_void_p.in_dll(self.lib, "map16_lo").value = ctypes.addressof(self.map)
        ctypes.c_void_p.in_dll(self.lib, "map16_hi").value = ctypes.addressof(self.map) + maplen // 2
        self.unsup = ctypes.c_int.in_dll(self.lib, "mario_unsupported")
        if sprpath:
            data = open(sprpath, "rb").read()
            self.spr = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
            ctypes.c_void_p.in_dll(self.lib, "spr_level").value = ctypes.addressof(self.spr)
            ctypes.c_ubyte.in_dll(self.lib, "level_sprites").value = 1
        self.calls = self.bad = 0
        self.shown = []

    def before(self, ram, mp):
        self.C.memmove(self.ram, ram, 0x2000)
        self.C.memmove(self.map, mp, len(mp))
        self.unsup.value = 0

    def after(self, fn, ram, mp, unsup):
        getattr(self.lib, fn)()
        self.calls += 1
        pr, pm = bytes(self.ram), bytes(self.map)
        if pr == ram and pm == mp and self.unsup.value == unsup:
            return
        self.bad += 1
        if len(self.shown) < 10:
            d = ["$%04X=%02X/%02X" % (k, ram[k], pr[k]) for k in range(0x2000) if ram[k] != pr[k]][:8]
            d += ["mapa+%d" % k for k in range(len(mp)) if mp[k] != pm[k]][:2]
            if self.unsup.value != unsup:
                d.append("unsup %d/%d" % (unsup, self.unsup.value))
            self.shown.append("%s: %s" % (fn, " ".join(d)))

    def report(self):
        print("cruce con el C del PC (RAM entera tras cada llamada): %d llamadas, %d distintas"
              % (self.calls, self.bad))
        for t in self.shown:
            print("  (68000/PC) " + t)


# tablas de sprite que el port conserva al resincronizar a Mario (--sprites)
SPR_KEEP = [0x14C8, 0x9E, 0xE4, 0x14E0, 0xD8, 0x14D4, 0xB6, 0xAA, 0xC2, 0x14F8, 0x14EC]


def run_loop(a, cpu, call, rec, orc, n, RAM, MAP, map0, syms):
    """lazo cerrado: como `marioverify ... loop`, con el binario 68000"""
    frames = resync = longest = cur = 0
    spr = None
    if a.sprites:
        spr = open(a.spr, "rb").read()
        SPR = BASE + ((len(open(a.bin, "rb").read()) + 0x103) & ~3)
        cpu.write(SPR, spr)
        cpu.write(BASE + syms["_spr_level"], struct.pack(">I", SPR))
        cpu.write(BASE + syms["_level_sprites"], b"\x01")

    def sync(r, keep):
        cpu.write(RAM, r[2])
        cpu.write(RAM + 0x13C0, r[3])
        cpu.write(RAM + 0x1931, b"\x07")
        if spr is None:
            return
        for t in SPR_KEEP:                  # los sprites son del port
            cpu.write(RAM + t, keep[t:t + 12])
        cpu.write(RAM + 0x1692, bytes([spr[0] & 0x3F]))    # wm_SpriteMemory
        cpu.write(RAM + 0x1430, b"\xff\xff")               # Lowest/HighestSolidSprTile

    def level_start(r):
        """como marioverify game: si el tramo empieza al principio del nivel, los
        sprites iniciales los crea el port (_level_start_sprites con el estado
        del primer frame) y tienen que dar los grabados. Deja la RAM lista para
        el sync() normal (que conserva las tablas de SPR_KEEP)"""
        if "_level_start_sprites" not in syms:  # binario viejo (abcheck con una base anterior)
            return False
        sync(r, bytes(0x2000))
        call("_level_start_sprites")
        ram = cpu.read(RAM, 0x2000)
        for k in range(12):
            if not ram[0x14C8 + k] and not orc(r, 0x14C8 + k):
                continue
            for t in SPR_KEEP:
                if t + k < 0x1500 and ram[t + k] != orc(r, t + k):   # XAcc 8-11: sin grabar
                    return False
        return True

    def newseg_sprites(r):
        """como marioverify game: los sprites ya a la vista cuentan como cargados
        (el oraculo no los tiene: nacieron antes de empezar a grabar)"""
        cam = orc(r, 0x1A) | orc(r, 0x1B) << 8
        y = idx = 0
        y = 1
        while spr[y] != 0xFF:
            sx = ((((spr[y] << 3) & 0x10) | (spr[y + 1] & 0x0F)) << 8) | (spr[y + 1] & 0xF0)
            if sx + 0x30 >= cam and sx < cam + 0x120:
                cpu.write(RAM + 0x1938 + idx, b"\x01")    # wm_SprLoadStatus
            y += 3
            idx += 1
    synced = False
    costs = []
    prev = None
    lstarts = 0
    seglvl = False
    # --replay: el tramo mas largo de la grabacion, frame a frame (ver replay_write)
    seg = longest_segment(rec, n) if a.replay else None
    ops, states, sprinit = [], [], None
    for i in range(n):
        r = rec(i)
        newseg = prev is None or r[0] != prev[0] + 1 or prev[1] != 0x29
        prev = r
        inseg = seg is not None and seg[0] <= r[0] <= seg[1]
        if r[1] != 0x29:
            synced = False
            continue
        if newseg:
            cpu.write(MAP, map0)
            cpu.write(RAM, bytes(0x2000))
            lvl = False
            if spr is not None:
                lvl = not (orc(r, ANIM) or orc(r, LOCKED)) and level_start(r)
                if lvl:
                    lstarts += 1
                else:
                    cpu.write(MAP, map0)
                    cpu.write(RAM, bytes(0x2000))
                    newseg_sprites(r)
            if inseg:
                sprinit = cpu.read(RAM + 0x1938, 128)
                seglvl = lvl
            synced = False
        if orc(r, ANIM) or orc(r, LOCKED):
            synced = False
            if inseg:
                ops.append((REP_SKIP, r[2][0x15:0x19]))
            continue
        if not synced:
            sync(r, cpu.read(RAM, 0x2000))
            synced = True
            longest = max(longest, cur)
            cur = 0
            if inseg:
                # el primer frame de un tramo que empieza al principio del
                # nivel: SYNC + _level_start_sprites + SYNC (ver level_start)
                ops.append((REP_LEVEL if seglvl and not ops else REP_SYNC, r[2][0x15:0x19]))
                states.append(r[2] + r[3])
            continue
        cpu.write(RAM + 0x15, r[2][0x15:0x19])
        if a.dump is not None and r[0] == a.dump:
            open(os.path.join(WORK, "cc", "worst_ram.bin"), "wb").write(cpu.read(RAM, 0x2000))
            open(os.path.join(WORK, "cc", "worst_map.bin"), "wb").write(cpu.read(MAP, len(map0)))
            c0, c1 = BASE + syms["cdata0"], BASE + syms["cdata1"]
            open(os.path.join(WORK, "cc", "worst_cdata.bin"), "wb").write(cpu.read(c0, c1 - c0))
        costs.append((call("_level_frame"), r[0]))
        if a.dump is not None and r[0] == a.dump:
            c0, c1 = BASE + syms["cdata0"], BASE + syms["cdata1"]
            open(os.path.join(WORK, "cc", "worst_after.bin"), "wb").write(cpu.read(c0, c1 - c0))
            print("estado del frame %d guardado (work/cc/worst_*.bin); level_frame: %d ciclos"
                  % (r[0], costs[-1][0]))
        frames += 1
        ram = cpu.read(RAM, 0x2000)
        ok = all(bytes(ram[adr:adr + w]) == bytes(orc(r, adr + t) for t in range(w))
                 for _, adr, w in FIELDS + LOOP_FIELDS)
        if ok:
            cur += 1
            if inseg:
                ops.append((REP_RUN, r[2][0x15:0x19]))
            continue
        resync += 1
        if resync <= 20:
            bad = [nm for nm, adr, w in FIELDS + LOOP_FIELDS
                   if bytes(ram[adr:adr + w]) != bytes(orc(r, adr + t) for t in range(w))]
            print("  frame %d: tras %d frames, difiere %s" % (r[0], cur, ", ".join(bad)))
        longest = max(longest, cur)
        cur = 0
        sync(r, ram)
        if inseg:
            ops.append((REP_RUNSYNC, r[2][0x15:0x19]))
            states.append(r[2] + r[3])
    longest = max(longest, cur)
    if a.replay:
        replay_write(a.replay, seg[0], ops, states, sprinit, spr)
    print("binario 68000 en lazo cerrado (%s%s): %d frames, %d resincronizaciones, "
          "tramo mas largo %d frames" % (a.engine, ", con sprites" if spr else "", frames, resync,
                                         longest))
    if spr is not None:
        print("tramos que empiezan al principio del nivel (sprites iniciales del port = oraculo): %d"
              % lstarts)
    if a.show and costs:
        f0, f1 = (int(x) for x in a.show.split("-"))
        for cy, f in costs:
            if f0 <= f <= f1:
                print("  frame %d: %d ciclos" % (f, cy))
    if a.engine == "musashi" and costs:
        c = sorted(x[0] for x in costs)
        mean = sum(c) / len(c)
        worst = max(costs)
        print("ciclos 68000 (sin DMA) por _level_frame: media %.0f, p99 %d, max %d (frame %d)"
              " = media %.1f %%, max %.1f %% de un frame PAL"
              % (mean, c[int(len(c) * 0.99)], worst[0], worst[1],
                 100 * mean / PAL_FRAME, 100 * worst[0] / PAL_FRAME))


# replay (--replay) para player/game.s -DREPLAY. Lo que hace el lazo cerrado
# de arriba en cada frame del tramo, para que la Amiga haga exactamente lo
# mismo (y siga la grabacion igual que aca):
REP_RUN, REP_SYNC, REP_SKIP, REP_RUNSYNC, REP_LEVEL = 0, 1, 2, 3, 4
#   RUN      joypad ($15-$18) + level_frame
#   SYNC     cargar el estado grabado (sync()), sin level_frame
#   SKIP     nada (Mario en una animacion o sprites congelados: no portado)
#   RUNSYNC  joypad + level_frame, y despues cargar el estado (resincronizar)
#   LEVEL    (solo el primer op, si el tramo empieza al principio del nivel)
#            cargar el estado con las tablas de sprites a 0, _level_start_sprites
#            (los sprites iniciales) y cargar otra vez el mismo estado
# Formato (big-endian):
#   +0  "SMWR"  u16 frames  u16 primer frame  u16 estados  u16 0
#   +12 u32 desplazamiento de OPS, u32 de STS
#   +20 128 bytes: wm_SprLoadStatus ($1938) al empezar el tramo
#   OPS frames x 6 bytes: u8 op, u8 0, joypad ($15-$18)
#   STS estados x 576 bytes: $0000-$00FF y $13C0-$14FF (como el oraculo),
#       en el orden en que los piden SYNC y RUNSYNC
# Al cargar un estado, game.s conserva las tablas de SPR_KEEP (los sprites
# son del port) y pone $1931 = 7, $1692 = spr.lv[0] & $3F y $1430 = $FFFF.


def longest_segment(rec, n):
    """(primer frame, ultimo frame) del tramo continuo de juego mas largo"""
    best, start, prev = None, None, None
    for i in range(n + 1):
        r = rec(i) if i < n else None
        cont = r is not None and prev is not None and r[0] == prev[0] + 1 and r[1] == 0x29
        if not cont:
            if start is not None and (best is None or prev[0] - start > best[1] - best[0]):
                best = (start, prev[0])
            start = r[0] if r is not None and r[1] == 0x29 else None
        prev = r
    return best


def replay_write(path, first, ops, states, sprinit, spr):
    if spr is None:
        sys.exit("--replay necesita --sprites (el juego corre los sprites)")
    head = b"SMWR" + struct.pack(">HHHH", len(ops), first, len(states), 0)
    o_ops = 20 + 128
    o_sts = o_ops + 6 * len(ops)
    out = head + struct.pack(">II", o_ops, o_sts) + bytes(sprinit)
    out += b"".join(bytes([op, 0]) + bytes(j) for op, j in ops)
    out += b"".join(bytes(st) for st in states)
    open(path, "wb").write(out)
    k = [sum(1 for op, _ in ops if op == t) for t in range(5)]
    print("replay: %s, frames %d-%d (%d): RUN %d, SYNC %d, SKIP %d, RUNSYNC %d, LEVEL %d; %d bytes"
          % (path, first, first + len(ops) - 1, len(ops), k[0], k[1], k[2], k[3], k[4], len(out)))


LOOP_FIELDS = [("Bg1HOfs $1A", 0x1A, 2), ("Bg1VOfs $1C", 0x1C, 2), ("Bg2HOfs $1E", 0x1E, 2),
               ("Bg2VOfs $20", 0x20, 2), ("ScrPosX $7E", 0x7E, 2), ("ScrPosY $80", 0x80, 2)]


if __name__ == "__main__":
    main()
