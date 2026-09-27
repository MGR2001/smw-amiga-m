#!/usr/bin/env python3
"""
scrollprof.py - perfil de player/scroll.s en Musashi (Etapa 0.3 / 6.4).

Corre el cuerpo REAL del bucle `frame` de scroll.s, frame a frame, en
Musashi (machine68k), con los datos de work/yi1_s.dat. Lo que no es CPU se
simula lo minimo:
  - la inicializacion de `entry` (AllocMem, DoIO, tomar la maquina) se
    reproduce desde Python llamando a las mismas rutinas del binario
    (build_copper, init_lo, draw_column, set_pointers, build_mid);
  - CUSTOM (a4) apunta a RAM: DMACONR = 0 (el blitter "ya termino") y
    VPOSR = linea $110, asi que la espera del principio de `frame` pasa;
  - una trampa de linea A en `.w2l` devuelve el control a Python al final
    del trabajo del frame.

Da, por frame, los ciclos de CPU (SIN esperas de DMA ni de blitter: es una
COTA INFERIOR, V2) y la s. Con --at S perfila ese frame por rutina (cuenta
instrucciones y ciclos aproximados por rutina con un hook).

  python3 tools/scrollprof.py                       # SPEED=4, todo el nivel
  python3 tools/scrollprof.py --top 10              # los 10 frames mas caros
  python3 tools/scrollprof.py --at 4504             # detalle del frame s = 4504
  python3 tools/scrollprof.py --src work/scroll_base.s   # otra version (A/B)
"""
import argparse, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
WORK = os.path.join(ROOT, "work")
PAL = 141_876                   # ciclos de CPU por frame PAL

BASE = 0x1000                   # binario
DATA = 0x20000                  # yi1_s.dat
BUF1 = 0x60000                  # PF1
COPA = 0x70000                  # listas del copper
COPB = 0x80000
FAKE = 0xE0000                  # "CUSTOM" en RAM
STACK = 0xF0000
RET = 0xFFFF0


def vasm():
    for d in (os.environ.get("VBCC"), os.path.expanduser("~/vbcc"), "/c/Users/JC/vbcc",
              r"C:\Users\JC\vbcc"):
        if d:
            for x in ("vasmm68k_mot.exe", "vasmm68k_mot"):
                p = os.path.join(d, "bin", x)
                if os.path.exists(p):
                    return p
    sys.exit("no encuentro vasm (VBCC=...)")


def assemble(src, defs):
    out = os.path.join(WORK, "scrollprof.bin")
    lst = os.path.join(WORK, "scrollprof.lst")
    cmd = [vasm(), "-quiet", "-Fbin", "-m68000", "-I", os.path.join(ROOT, "player"),
           "-L", lst, "-o", out] + ["-D" + d for d in defs] + [src]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    return open(out, "rb").read(), lst


def listing(lst):
    """simbolos globales (del final) y direcciones de etiquetas locales"""
    syms, local, lines = {}, {}, []
    glob = None
    for ln in open(lst, encoding="latin-1"):
        m = re.match(r"^([0-9A-F]{8}) ([A-Za-z_]\w*)$", ln.rstrip())
        if m:
            syms[m.group(2)] = int(m.group(1), 16)
            continue
        # "00:000001F0 202C0004   296: .w2l:  move.l ..." o, sin codigo en
        # la linea, "              236: frame:"
        m = re.match(r"^(?:\d\d:([0-9A-F]{8}) \S*)?\s+\d+: ([A-Za-z_.]\w*):", ln)
        if m:
            lab = m.group(2)
            if not lab.startswith("."):
                glob = lab
            elif m.group(1):
                local[(glob, lab)] = int(m.group(1), 16)
    return syms, local


class Scroll:
    def __init__(self, code, syms, local, data, V):
        import machine68k as M
        self.M, self.V, self.syms = M, V, syms
        self.m = M.Machine(M.CPUType.M68000, 1024)
        self.cpu, self.mem = self.m.cpu, self.m.mem
        tid = self.m.traps.alloc(lambda op, pc: self.m.abort_execute())
        self.trap = 0xA000 | tid
        self.mem.w16(RET, self.trap)
        self.mem.w_block(BASE, code)
        self.mem.w_block(DATA, data)
        self.mem.w32(FAKE + 4, 0x110 << 8)          # VPOSR: linea $110
        self.w2l = BASE + local[("frame", ".w2l")]
        self.mem.w16(self.w2l, self.trap)           # fin del trabajo del frame
        self.vars = BASE + syms["vars"]

    def regs(self, a0=None, d0=None):
        M = self.M
        self.cpu.w_reg(M.Register.A3, DATA)
        self.cpu.w_reg(M.Register.A4, FAKE)
        self.cpu.w_reg(M.Register.A5, self.vars)
        if a0 is not None:
            self.cpu.w_reg(M.Register.A0, a0)
        if d0 is not None:
            self.cpu.w_reg(M.Register.D0, d0)

    def run(self, pc):
        self.cpu.w_reg(self.M.Register.A7, STACK - 4)
        self.mem.w32(STACK - 4, RET)
        self.cpu.w_pc(pc)
        r = self.m.execute(200_000_000)
        return r.cycles - 34

    def call(self, name, a0=None, d0=None):
        self.regs(a0, d0)
        return self.run(BASE + self.syms[name])

    def v16(self, off):
        return self.mem.r16(self.vars + off)

    def init(self):
        """lo que hace `entry` entre build_copper y tomar la maquina"""
        V, w16, w32 = self.V, self.mem.w16, self.mem.w32
        w32(self.vars + V["V_BUF1"], BUF1)
        w32(self.vars + V["V_COP"], COPA)
        w32(self.vars + V["V_COP2"], COPB)
        self.call("build_copper", a0=COPA)
        self.call("build_copper", a0=COPB)
        self.call("init_lo")
        w16(self.vars + V["V_CCOL"], 0xFFFF)
        w16(self.vars + V["V_S"], 0)
        w16(self.vars + V["V_P"], 0xFFFF)
        w32(self.vars + V["V_CHG"], DATA + self.mem.r32(DATA + 28))
        for c in range(22):
            self.call("draw_column", d0=c)
        w32(self.vars + V["V_BACK"], COPA)
        self.call("set_pointers")
        self.call("build_mid")
        w32(self.vars + V["V_BACK"], COPB)
        self.call("set_pointers")
        self.call("build_mid")

    def frame(self):
        """un frame: desde `frame` hasta `.w2l`. Devuelve (s, ciclos)"""
        self.regs()
        c = self.run(BASE + self.syms["frame"])
        return self.v16(self.V["V_S"]), c


def routines(syms):
    """rangos [inicio, fin) de las rutinas globales de codigo"""
    code = sorted((a, n) for n, a in syms.items()
                  if n in ("frame", "set_pointers", "apply_colors", "init_lo", "build_mid",
                           "draw_column", "blit_column", "blit_steps", "bwait",
                           "build_copper", "readtimer", "waitline", "bench_init",
                           "bench_frame", "show_results", "fail"))
    return [(a, code[i + 1][0] if i + 1 < len(code) else 1 << 30, n)
            for i, (a, n) in enumerate(code)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "player", "scroll.s"))
    ap.add_argument("--data", default=os.path.join(WORK, "yi1_s.dat"))
    ap.add_argument("--speed", type=int, default=4)
    ap.add_argument("--vis", type=int, default=256, help="ancho de pantalla (-DVIS)")
    ap.add_argument("--stopx", type=int, help="por defecto 5120 - vis")
    ap.add_argument("-D", action="append", default=[], help="define extra para vasm")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--at", type=int, help="perfil por rutina del frame con esta s")
    ap.add_argument("--csv", help="escribir s,ciclos de cada frame")
    a = ap.parse_args()

    if a.stopx is None:
        a.stopx = 5120 - a.vis
    defs = ["SPEED=%d" % a.speed, "STOPX=%d" % a.stopx, "VIS=%d" % a.vis] + a.D
    code, lst = assemble(a.src, defs)
    syms, local = listing(lst)
    V = {n: v for n, v in syms.items() if n.startswith("V_")}
    sc = Scroll(code, syms, local, open(a.data, "rb").read(), V)
    sc.init()

    rows, prev = [], None
    while True:
        if a.at is not None and sc.v16(V["V_S"]) + a.speed >= a.at:
            s_next = min(sc.v16(V["V_S"]) + a.speed, a.stopx)
            if s_next == a.at:
                profile(sc, syms)
                return
        s, c = sc.frame()
        if s == prev:
            break                                    # llego a STOPX
        rows.append((s, c))
        prev = s
    if a.csv:
        with open(a.csv, "w") as f:
            f.write("s,ciclos\n")
            for s, c in rows:
                f.write("%d,%d\n" % (s, c))
    body = rows[8:]                                  # BSKIP, como el banco
    cs = [c for _, c in body]
    print("scroll.s en Musashi (%s), SPEED=%d: %d frames (sin los 8 primeros)"
          % (" ".join(defs), a.speed, len(body)))
    print("ciclos de CPU por frame, SIN DMA ni blitter (cota inferior):")
    print("  media %d = %.1f %%   max %d = %.1f %% (s = %d)"
          % (sum(cs) / len(cs), 100 * sum(cs) / len(cs) / PAL, max(cs),
             100 * max(cs) / PAL, body[cs.index(max(cs))][0]))
    for s, c in sorted(body, key=lambda r: -r[1])[:a.top]:
        print("  s = %4d  %7d ciclos  %6.1f %%" % (s, c, 100 * c / PAL))


def profile(sc, syms):
    rng = routines(syms)
    count, stack = {}, []
    names = {a: n for a, _, n in rng}

    def where(pc):
        off = pc - BASE
        for lo, hi, n in rng:
            if lo <= off < hi:
                return n
        return "?"

    def hook(pc):
        n = where(pc)
        count[n] = count.get(n, 0) + 1

    sc.cpu.set_instr_hook_callback(hook)
    s, c = sc.frame()
    sc.cpu.set_instr_hook_callback(None)
    tot = sum(count.values())
    print("frame s = %d: %d ciclos (%.1f %%), %d instrucciones" % (s, c, 100 * c / PAL, tot))
    print("  instrucciones por rutina (el ciclo medio es ~%d por instruccion):" % (c // max(tot, 1)))
    for n, k in sorted(count.items(), key=lambda r: -r[1]):
        print("    %-14s %7d  %5.1f %%" % (n, k, 100 * k / tot))


if __name__ == "__main__":
    main()
