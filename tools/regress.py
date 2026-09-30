#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
regress.py - la red de seguridad del port: compila desde el codigo ACTUAL,
corre todas las verificaciones contra el oraculo y compara cada numero con
tools/baseline.json. Ver ROADMAP.md, regla V1.

    python3 tools/regress.py                 # PC (marioverify) + 68000 (m68kverify)
    python3 tools/regress.py --quick         # solo marioverify (segundos)
    python3 tools/regress.py --level         # + conversor del nivel (render_d.py, numpy)
    python3 tools/regress.py --emu logic,scrollbench,scrollimg   # + FS-UAE (minutos)
    python3 tools/regress.py --shots DIR     # lee capturas ya hechas (p. ej. WinUAE en la PC):
                                             #   DIR/logicbench.png, DIR/scrollb.png
    python3 tools/regress.py --update        # la medida actual pasa a ser la base
    python3 tools/regress.py --accept-last   # la base toma lo medido en la ultima corrida
                                             # (work/regress_last.json), sin volver a correr

Cada metrica tiene una direccion:
    eq    tiene que dar exactamente lo mismo (un cambio = cambio de alcance)
    max   mas es mejor (frames exactos, tramo mas largo)
    min   menos es mejor (resincronizaciones, ciclos, % de frame, fallos)
    info  solo se muestra
Resultado por metrica: OK, MEJOR (no falla: actualizar la base con --update
y explicarlo en el commit), PEOR o FALTA (fallan). Sale con 1 si algo falla.
Ademas, cruces PC <-> 68000: si el binario de vbcc no da EXACTAMENTE lo mismo
que el C del PC, es un fallo del compilador o del arnes (P38), no del port.

Solo usa la biblioteca estandar (corre tambien con el Python de la PC).
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
WORK = os.path.join(ROOT, "work")
BASELINE = os.path.join(HERE, "baseline.json")
EXE = ".exe" if os.name == "nt" else ""
MV = os.path.join(WORK, "marioverify" + EXE)
ORACLE = os.path.join(WORK, "oracle_yi1.bin")
PY = sys.executable
CSRC = ["tools/marioverify.c", "player/mario.c", "player/mcoll.c", "player/manim.c",
        "player/mgfx.c", "player/mcam.c", "player/msprite.c", "player/gen/smwrom00.c"]
# el C del port como biblioteca, con las opciones del build de la Amiga (-DNOOAM),
# para el cruce de la RAM entera con el binario del 68000 (m68kverify --cross)
LIBSRC = ["player/mario.c", "player/mcoll.c", "player/manim.c", "player/mgfx.c", "player/mcam.c",
          "player/msprite.c", "player/mspr.c", "player/gen/smwrom00.c"]
LIB = os.path.join(WORK, "libport.so")
SCROLL_X = (500, 1000, 1700, 2500, 3500, 4500)

# tolerancias relativas de las medidas de tiempo (Musashi es determinista:
# cualquier subida es real; FS-UAE varia un poco entre corridas)
TOL = {"cyc": 0.002, "pct": 0.01}


class Run:
    def __init__(self):
        self.got = {}           # metrica -> (valor, direccion, tolerancia)
        self.notes = []         # (nombre, ok, texto) de los cruces y los pasos
        self.logs = {}

    def put(self, name, value, how, tol=0.0, tol_abs=0):
        self.got[name] = (value, how, (tol, tol_abs))

    def note(self, name, ok, text):
        self.notes.append((name, ok, text))


def sh(cmd, timeout=900, env=None):
    """corre un comando; devuelve (codigo, salida)"""
    try:
        p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout, env=env, shell=isinstance(cmd, str))
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT (%d s)" % timeout
    except OSError as e:
        return 127, str(e)


def num(rx, text, cast=int):
    m = re.search(rx, text)
    return tuple(cast(g) for g in m.groups()) if m else None


def vbcc_dir():
    for d in (os.environ.get("VBCC"), os.path.expanduser("~/vbcc"), "/c/Users/JC/vbcc",
              r"C:\Users\JC\vbcc"):
        if d and (os.path.exists(os.path.join(d, "bin", "vbccm68k"))
                  or os.path.exists(os.path.join(d, "bin", "vbccm68k.exe"))):
            return d
    return None


# --------------------------------------------------------------------------
# compilar SIEMPRE desde el codigo actual: un binario viejo da un OK falso
# --------------------------------------------------------------------------
def build(r, want_68k):
    if not os.path.exists(os.path.join(ROOT, "player", "gen", "smwrom00.c")):
        r.note("build", False, "falta player/gen/smwrom00.c: correr tools/smwgen.py (o setup_cloud.sh)")
        return False, False
    cc = shutil.which("gcc") or shutil.which("cc")
    if not cc:
        r.note("build", False, "no hay gcc")
        return False, False
    code, out = sh([cc, "-O2", "-Iplayer", "-o", MV] + CSRC)
    if code:
        r.note("build PC", False, out[-800:])
        return False, False
    r.note("build PC", True, "work/marioverify desde el codigo actual")
    if not want_68k:
        return True, False
    if os.name != "nt":
        code, out = sh([cc, "-shared", "-fPIC", "-O2", "-DNOOAM", "-Iplayer", "-o", LIB] + LIBSRC)
        if code:
            r.note("build PC (biblioteca)", False, out[-800:])
    v = vbcc_dir()
    if not v:
        r.note("build 68000", False, "no encuentro vbcc (VBCC=...): se saltan las pruebas del 68000")
        return True, False
    env = dict(os.environ, VBCC=v)
    code, out = sh(["sh", "tools/logicbench_build.sh"], env=env)
    r.logs["logicbench_build"] = out
    if code:
        # logicbench_build.sh se para, entre otras cosas, si vbcc emitio una
        # referencia absoluta (P36): eso es un fallo, no un "saltado"
        r.note("build 68000", False, out[-800:])
        return True, False
    r.note("build 68000", True, "work/logicbench.bin (vbcc -O=991 -sc -sd)")
    return True, True


# --------------------------------------------------------------------------
# PC: tools/marioverify.c
# --------------------------------------------------------------------------
def todos(r, key, out):
    t = num(r"TODOS los campos\s+(\d+)/(\d+)\s+(\d+)/(\d+)", out)
    if not t:
        return None
    r.put(key + ".aire.ok", t[0], "max")
    r.put(key + ".aire.tot", t[1], "eq")
    r.put(key + ".suelo.ok", t[2], "max")
    r.put(key + ".suelo.tot", t[3], "eq")
    return t


def pc_checks(r):
    res = {}
    for mode in ("", "full", "gfx", "loop", "sprload", "sprloop", "game"):
        args = [MV, ORACLE] + ([mode] if mode else [])
        code, out = sh(args, timeout=300)
        r.logs["marioverify " + (mode or "8a")] = out
        if code:
            r.note("marioverify " + (mode or "8a"), False, "codigo %d: %s" % (code, out[-300:]))
            continue
        if mode == "":
            todos(r, "pc.8a", out)
        elif mode == "full":
            res["full"] = todos(r, "pc.full", out)
        elif mode == "gfx":
            t = num(r"\[gfx\] frames: (\d+).*?\n\s*OAM de Mario exacta: (\d+)\s+MarioScrPosX/Y exacta: (\d+)",
                    out.replace("\r", ""))
            if t:
                r.put("pc.gfx.frames", t[0], "eq")
                r.put("pc.gfx.oam_ok", t[1], "max")
                r.put("pc.gfx.scr_ok", t[2], "max")
        elif mode == "loop":
            t = num(r"resincronizaciones: (\d+)\s*\n\s*tramo mas largo sin diferencias: (\d+)", out)
            if t:
                r.put("pc.loop.resync", t[0], "min")
                r.put("pc.loop.tramo", t[1], "max")
                res["loop"] = t[0]
        elif mode == "sprload":
            t = num(r"oraculo: (\d+)\s+del port: (\d+)\s+exactos: (\d+)\s+distintos: (\d+)", out)
            if t:
                r.put("pc.sprload.oraculo", t[0], "eq")
                r.put("pc.sprload.exactos", t[2], "max")
                r.put("pc.sprload.distintos", t[3], "min")
        elif mode == "sprloop":
            t = num(r"Rex-frames seguidos: (\d+)\s+exactos: (\d+)\s+con diferencia: (\d+)", out)
            if t:
                r.put("pc.sprloop.seguidos", t[0], "info")
                r.put("pc.sprloop.exactos", t[1], "max")
                r.put("pc.sprloop.diferencia", t[2], "min")
            t = num(r"port (\d+), oraculo (\d+), coinciden (\d+)", out)
            if t:
                r.put("pc.sprloop.rebotes_ok", t[2], "max")
        elif mode == "game":
            t = num(r"resincronizaciones de Mario: (\d+)\s+tramo mas largo: (\d+)", out)
            if t:
                r.put("pc.game.resync", t[0], "min")
                r.put("pc.game.tramo", t[1], "max")
            t = num(r"Rex seguidos: (\d+) Rex-frames, exactos (\d+)", out)
            if t:
                r.put("pc.game.rex_seguidos", t[0], "info")
                r.put("pc.game.rex_exactos", t[1], "max")
            game_sprite_checks(r, out)
    return res


def game_sprite_checks(r, out):
    """etapa 9.1: marioverify game, frames exactos por numero de sprite (los que
    corre el port: seguidos = frames comparados, exactos = los 11 campos grabados)"""
    for n, seg, ok in re.findall(r"sprite ([0-9A-F]{2}): seguidos (\d+) exactos (\d+)", out):
        r.put("pc.game.spr_%s.seguidos" % n, int(seg), "info")
        r.put("pc.game.spr_%s.exactos" % n, int(ok), "max")
        r.put("pc.game.spr_%s.distintos" % n, int(seg) - int(ok), "min")


# oraculos guionizados de snesorc (tools/snesorc/*.orc -> work/oracle_X.txt,
# en git): el .bin se regenera si falta o si el .txt es mas nuevo
SNESORC = ("normal", "diagpipe", "hills", "banzai")


def orc_checks(r):
    for n in SNESORC:
        txt = os.path.join(WORK, "oracle_%s.txt" % n)
        binf = os.path.join(WORK, "oracle_%s.bin" % n)
        if not os.path.exists(txt):
            continue
        if not os.path.exists(binf) or os.path.getmtime(txt) > os.path.getmtime(binf):
            code, out = sh([PY, "tools/oracle2bin.py", "--inp", txt, "--out", binf])
            if code:
                r.note("oracle2bin " + n, False, out[-300:])
                continue
        k = "orc.%s." % n
        for mode in ("full", "gfx", "loop", "game", "sprload"):
            code, out = sh([MV, binf, mode], timeout=300)
            r.logs["marioverify %s %s" % (n, mode)] = out
            if code:
                r.note("marioverify %s %s" % (n, mode), False, "codigo %d: %s" % (code, out[-300:]))
                continue
            if mode == "full":
                t = num(r"TODOS los campos\s+(\d+)/(\d+)\s+(\d+)/(\d+)", out)
                if t:
                    r.put(k + "full.ok", t[0] + t[2], "max")
                    r.put(k + "full.tot", t[1] + t[3], "eq")
            elif mode == "gfx":
                t = num(r"OAM de Mario exacta: (\d+)\s+MarioScrPosX/Y exacta: (\d+)", out)
                if t:
                    r.put(k + "gfx.oam_ok", t[0], "max")
                    r.put(k + "gfx.scr_ok", t[1], "max")
            elif mode == "loop":
                t = num(r"resincronizaciones: (\d+)\s*\n\s*tramo mas largo sin diferencias: (\d+)", out)
                if t:
                    r.put(k + "loop.resync", t[0], "min")
                    r.put(k + "loop.tramo", t[1], "max")
            elif mode == "game":
                t = num(r"resincronizaciones de Mario: (\d+)\s+tramo mas largo: (\d+)", out)
                if t:
                    r.put(k + "game.resync", t[0], "min")
                    r.put(k + "game.tramo", t[1], "max")
                bad = sum(int(a) - int(b) for a, b in
                          re.findall(r"sprite [0-9A-F]{2}: seguidos (\d+) exactos (\d+)", out))
                r.put(k + "game.spr_distintos", bad, "min")
            elif mode == "sprload":
                t = num(r"oraculo: (\d+)\s+del port: (\d+)\s+exactos: (\d+)\s+distintos: (\d+)", out)
                if t:
                    r.put(k + "sprload.exactos", t[2], "max")
                    r.put(k + "sprload.distintos", t[3], "min")


# --------------------------------------------------------------------------
# 68000: tools/m68kverify.py sobre el binario que arma vbcc (Musashi)
# --------------------------------------------------------------------------
def m68k_checks(r, pc):
    try:
        import machine68k  # noqa: F401
    except ImportError:
        r.note("68000", False, "falta machine68k (pip install machine68k): no se verifico el binario")
        return
    cross = ["--cross", LIB] if os.path.exists(LIB) else []
    runs = (("full", ["--mode", "full"]), ("loop", ["--mode", "loop"] + cross),
            ("spr", ["--mode", "loop", "--sprites"] + cross))
    for key, extra in runs:
        code, out = sh([PY, "tools/m68kverify.py", "--engine", "musashi"] + extra, timeout=1800)
        r.logs["m68kverify " + key] = out
        if code:
            r.note("m68kverify " + key, False, "codigo %d: %s" % (code, out[-400:]))
            continue
        if key == "full":
            t = num(r"pares: (\d+)\s+sin portar: (\d+)\s+todos los campos: (\d+)", out)
            if t:
                r.put("m68k.full.ok", t[2], "max")
                if pc.get("full"):
                    want = pc["full"][0] + pc["full"][2]
                    r.note("cruce full PC=68000", t[2] == want,
                           "68000 %d, PC %d (aire + suelo)" % (t[2], want))
            t = num(r"por frame \(mario_E2BD.*?media (\d+), mediana \d+, p99 \d+, max (\d+)", out)
            if t:
                r.put("m68k.full.ciclos_media", t[0], "min", TOL["cyc"])
                r.put("m68k.full.ciclos_max", t[1], "min", TOL["cyc"])
            continue
        t = num(r"(\d+) frames, (\d+) resincronizaciones, tramo mas largo (\d+)", out)
        if t:
            r.put("m68k.%s.resync" % key, t[1], "min")
            r.put("m68k.%s.tramo" % key, t[2], "max")
            if key == "loop" and pc.get("loop") is not None:
                r.note("cruce loop PC=68000", t[1] == pc["loop"],
                       "resincronizaciones: 68000 %d, PC %d" % (t[1], pc["loop"]))
        t = num(r"cruce con el C del PC \(RAM entera tras cada llamada\): (\d+) llamadas, (\d+) distintas", out)
        if t:
            r.note("cruce RAM %s PC=68000" % key, t[1] == 0,
                   "%d llamadas a level_frame/level_start_sprites, %d con la RAM distinta" % t)
        elif cross:
            r.note("cruce RAM %s PC=68000" % key, False, "m68kverify --cross no dio el resultado")
        t = num(r"_level_frame: media (\d+), p99 (\d+), max (\d+)", out)
        if t:
            r.put("m68k.%s.ciclos_media" % key, t[0], "min", TOL["cyc"])
            r.put("m68k.%s.ciclos_p99" % key, t[1], "min", TOL["cyc"])
            r.put("m68k.%s.ciclos_max" % key, t[2], "min", TOL["cyc"])


# --------------------------------------------------------------------------
# nivel: la cadena de la etapa 5 (necesita numpy/scipy y el fuente de SMW)
# --------------------------------------------------------------------------
def level_checks(r):
    for step in ("mkbg.py", "mkd8in.py", "mkleveld.py", "mkscroll.py"):
        code, out = sh([PY, "tools/" + step], timeout=1800)
        r.logs[step] = out
        if code:
            r.note(step, False, out[-400:])
            return
    code, out = sh([PY, "tools/render_d.py"], timeout=3600)
    r.logs["render_d"] = out
    if code:
        r.note("render_d.py", False, out[-400:])
        return
    t = num(r"copper ideal: (\d+) px distintos", out)
    if t:
        r.put("nivel.render_vs_ideal_px", t[0], "min")
    t = num(r"encuadres cada \d+ px: (\d+) px de capa 1 mal", out)
    if t:
        r.put("nivel.encuadres_px_mal", t[0], "min")


# --------------------------------------------------------------------------
# emulador: FS-UAE (cloud) o capturas ya hechas (PC)
# --------------------------------------------------------------------------
def read_logic(r, shot):
    code, out = sh([PY, "tools/logicbench_read.py", "--shot", shot, "--auto"])
    r.logs["logicbench_read"] = out
    t = [float(x) for x in re.findall(r"=\s*([\d.]+) % de un frame", out)]
    if code or len(t) != 2:
        r.note("logicbench (captura)", False, out[-300:])
        return
    r.put("emu.logic.corriendo_pct", t[0], "min", TOL["pct"])
    r.put("emu.logic.salto_pct", t[1], "min", TOL["pct"])


def read_scrollbench(r, shot):
    code, out = sh([PY, "tools/scroll_read.py", "--shot", shot, "--auto"])
    r.logs["scroll_read"] = out
    rows = re.findall(r"(con columna nueva|sin columna)\s+\d+ frames\s+media\s+\d+ ticks =\s*([\d.]+) %"
                      r"\s+max\s+\d+ =\s*([\d.]+) %.*?en s=(\d+)", out)
    if code or len(rows) != 2:
        r.note("scroll bench (captura)", False, out[-300:])
        return
    for name, av, mx, sx in rows:
        r.put("emu.scroll.%s_max_s" % ("con_col" if name.startswith("con") else "sin_col"),
              int(sx), "info")
        k = "con_col" if name.startswith("con") else "sin_col"
        r.put("emu.scroll.%s_media_pct" % k, float(av), "min", TOL["pct"])
        # Ojo: con blit_steps casi todos los frames cuentan como "con columna"
        r.put("emu.scroll.%s_max_pct" % k, float(mx), "min", TOL["pct"])


def vasm():
    v = vbcc_dir()
    return os.path.join(v, "bin", "vasmm68k_mot" + (".exe" if os.path.exists(
        os.path.join(v, "bin", "vasmm68k_mot.exe")) else "")) if v else None


def fsuae(r, adf, png, secs):
    code, out = sh(["sh", "tools/fsuae_shot.sh", adf, png, str(secs)], timeout=secs + 120)
    r.logs["fsuae " + png] = out
    if code or not os.path.exists(os.path.join(ROOT, png)):
        r.note("FS-UAE " + png, False, out[-300:])
        return False
    if "cycle-exact: si" not in out:
        r.note("FS-UAE " + png, False, "el log no confirma cpu_cycle_exact: la medida no vale (V2)")
        return False
    return True


def emu_checks(r, what, xs=SCROLL_X):
    if not shutil.which("fs-uae"):
        r.note("FS-UAE", False, "no esta instalado (apt-get install fs-uae xvfb x11-apps netpbm)")
        return
    va = vasm()
    if "logic" in what:
        if os.path.exists(os.path.join(WORK, "logicbench.adf")) and fsuae(
                r, "work/logicbench.adf", "work/rg_logicbench.png", 30):
            read_logic(r, "work/rg_logicbench.png")
    need_dat = os.path.exists(os.path.join(WORK, "yi1_s.dat"))
    if ("scrollbench" in what or "scrollimg" in what) and not need_dat:
        r.note("scroll", False, "falta work/yi1_s.dat: correr con --level (o mkscroll.py)")
        return
    if "scrollbench" in what:
        code, out = sh([va, "-quiet", "-Fbin", "-m68000", "-I", "player", "-DBENCH", "-DSPEED=4",
                        "-o", "work/rg_scrollb.bin", "player/scroll.s"])
        code2, out2 = sh([PY, "tools/mkadf.py", "--boot", "work/boot.bin", "--stage2",
                          "work/rg_scrollb.bin", "--data", "work/yi1_s.dat", "--out", "work/rg_scrollb.adf"])
        if code or code2:
            r.note("scroll.s -DBENCH", False, (out + out2)[-400:])
        elif fsuae(r, "work/rg_scrollb.adf", "work/rg_scrollb.png", 70):
            read_scrollbench(r, "work/rg_scrollb.png")
    if "scrollimg" in what:
        for x in xs:
            b, adf, png = "work/rg_scroll%d.bin" % x, "work/rg_scroll%d.adf" % x, "work/rg_scroll%d.png" % x
            code, out = sh([va, "-quiet", "-Fbin", "-m68000", "-I", "player", "-DSTOPX=%d" % x,
                            "-o", b, "player/scroll.s"])
            code2, out2 = sh([PY, "tools/mkadf.py", "--boot", "work/boot.bin", "--stage2", b,
                              "--data", "work/yi1_s.dat", "--out", adf])
            if code or code2:
                r.note("scroll.s STOPX=%d" % x, False, (out + out2)[-400:])
                continue
            # AROS tarda ~35 s en arrancar y el scroll va a 2 px por frame
            # (x / 100 s): con 60 s fijos, x = 3500 y 4500 se capturaban antes
            # de llegar
            if not fsuae(r, adf, png, 50 + x // 100):
                continue
            code, out = sh([PY, "tools/scroll_check.py", "--shot", png, "--s", str(x), "--mid",
                            "--png", "work/rg_scroll%d_cmp.png" % x], timeout=600)
            r.logs["scroll_check %d" % x] = out
            t = num(r"fallos que no se explican por un vecino: (\d+)", out)
            if code or not t:
                r.note("scroll_check %d" % x, False, out[-300:])
                continue
            pct = num(r"px distintos de \d+ \(([\d.]+) %\)", out, float)
            if pct and pct[0] > 20:
                r.note("scroll_check %d" % x, False, "%.0f %% distinto: la captura no esta en x = %d "
                       "(espera corta o el scroll no llego); mirar work/rg_scroll%d_cmp.png"
                       % (pct[0], x, x))
            # +-5 px: la misma x da 91 o 94 segun el build (ver ROADMAP, Etapa 0.4)
            r.put("emu.scrollimg.x%d_fallos" % x, t[0], "min", 0.0, 5)


# --------------------------------------------------------------------------
def compare(r, base, ignore=()):
    rows, bad, better = [], 0, 0
    for name in sorted(r.got):
        val, how, (tol, tol_abs) = r.got[name]
        ref = base.get(name, {}).get("value") if isinstance(base.get(name), dict) else None
        if ref is None:
            st = "NUEVA"
        elif how == "info":
            st = "info"
        elif how == "eq":
            st = "OK" if val == ref else "PEOR"
        else:
            lim = max(abs(ref) * tol, tol_abs)
            worse = val > ref + lim if how == "min" else val < ref - lim
            best = val < ref - lim if how == "min" else val > ref + lim
            st = "PEOR" if worse else ("MEJOR" if best else "OK")
        bad += st == "PEOR"
        better += st == "MEJOR"
        rows.append((st, name, val, ref, how))
    # una metrica de la base que no aparecio, en un grupo que si corrio
    # (p. ej. "pc.gfx"), es un fallo: la herramienta cambio de salida o murio
    ran = {".".join(k.split(".")[:2]) for k in r.got}
    missing = [n for n in base if not n.startswith("_") and n not in r.got
               and ".".join(n.split(".")[:2]) in ran and n not in ignore]
    return rows, bad, better, missing


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--quick", action="store_true", help="solo marioverify")
    ap.add_argument("--no-build", action="store_true", help="no recompilar (NO recomendado)")
    ap.add_argument("--level", action="store_true", help="tambien la cadena del nivel (etapa 5)")
    ap.add_argument("--emu", default="", help="logic,scrollbench,scrollimg (FS-UAE, minutos)")
    ap.add_argument("--scroll-x", default=",".join(str(x) for x in SCROLL_X),
                    help="x de las capturas de scrollimg")
    ap.add_argument("--shots", default="", help="directorio con logicbench.png / scrollb.png")
    ap.add_argument("--update", action="store_true", help="guardar lo medido como base")
    ap.add_argument("--force", action="store_true", help="--update aunque haya fallos")
    ap.add_argument("--accept-last", action="store_true",
                    help="pasar a la base lo medido en la ultima corrida, sin correr nada")
    ap.add_argument("--baseline", default=BASELINE)
    ap.add_argument("--log", default=os.path.join(WORK, "regress.log"))
    a = ap.parse_args()

    last = os.path.join(WORK, "regress_last.json")
    if a.accept_last:
        got = json.load(open(last, encoding="utf-8"))
        base = json.load(open(a.baseline, encoding="utf-8")) if os.path.exists(a.baseline) else {}
        base.update(got)
        json.dump(base, open(a.baseline, "w", encoding="utf-8"), indent=1, sort_keys=True)
        print("base actualizada desde %s (%d entradas)" % (os.path.relpath(last, ROOT), len(got)))
        return 0

    r = Run()
    ok_pc, ok_68k = (os.path.exists(MV), not a.quick) if a.no_build else build(r, not a.quick)
    pc = pc_checks(r) if ok_pc else {}
    if ok_pc:
        orc_checks(r)
    if ok_68k:
        m68k_checks(r, pc)
    if a.level:
        level_checks(r)
    if a.emu:
        emu_checks(r, set(a.emu.split(",")), [int(x) for x in a.scroll_x.split(",")])
    if a.shots:
        for f, fn in (("logicbench.png", read_logic), ("scrollb.png", read_scrollbench)):
            p = os.path.join(a.shots, f)
            if os.path.exists(p):
                fn(r, p)

    base = json.load(open(a.baseline, encoding="utf-8")) if os.path.exists(a.baseline) else {}
    xs = {int(x) for x in a.scroll_x.split(",")}
    ignore = {n for n in base if re.match(r"emu\.scrollimg\.x(\d+)_", n)
              and int(re.match(r"emu\.scrollimg\.x(\d+)_", n).group(1)) not in xs}
    rows, bad, better, missing = compare(r, base, ignore)
    print("%-6s %-34s %12s %12s  %s" % ("", "metrica", "ahora", "base", ""))
    for st, name, val, ref, how in rows:
        print("%-6s %-34s %12s %12s  (%s)" % (st, name, val, "-" if ref is None else ref, how))
    for name in missing:
        print("%-6s %-34s %12s %12s" % ("FALTA", name, "-", base[name]["value"]))
    print()
    for name, ok, text in r.notes:
        print("%-6s %-34s %s" % ("ok" if ok else "FALLO", name, text.strip().splitlines()[-1][:200]
                                 if text.strip() else ""))
    fails = bad + len(missing) + sum(1 for _, ok, _ in r.notes if not ok)

    with open(a.log, "w", encoding="utf-8") as f:
        for k, v in r.logs.items():
            f.write("===== %s\n%s\n" % (k, v))
    print("\nsalida completa de cada herramienta: %s" % os.path.relpath(a.log, ROOT))

    head = sh(["git", "rev-parse", "--short", "HEAD"])[1].strip()
    dirty = sh(["git", "status", "--porcelain", "--untracked-files=no"])[1].strip()
    now = {"_meta": {"fecha": datetime.date.today().isoformat(),
                     "commit": head + ("+cambios" if dirty else ""),
                     "nota": "tools/regress.py; las medidas emu.* dependen del emulador"}}
    for name, (val, how, tol) in r.got.items():
        now[name] = {"value": val, "how": how}
    json.dump(now, open(last, "w", encoding="utf-8"), indent=1, sort_keys=True)
    if a.update and fails and not a.force:
        print("NO se actualiza la base: hay %d fallos (PEOR/FALTA/FALLO). Una base peor esconde "
              "regresiones; si es a proposito (cambio de alcance), --update --force y explicarlo." % fails)
        return 1
    if a.update:
        base.update(now)
        json.dump(base, open(a.baseline, "w", encoding="utf-8"), indent=1, sort_keys=True)
        print("base actualizada: %s (%d metricas)" % (os.path.relpath(a.baseline, ROOT), len(r.got)))
        return 0
    if better:
        print("%d metricas MEJORAN: si el cambio es intencional, --update y explicarlo en el commit" % better)
    print("RESULTADO: %s" % ("FALLA (%d)" % fails if fails else "OK"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
