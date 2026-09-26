#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
abcheck.py - A/B de una optimizacion del C: compila el commit BASE (en un
git worktree aparte) y el arbol ACTUAL, corre los dos binarios 68000 en
Musashi contra el oraculo y dice (1) si dan exactamente lo mismo y (2)
cuantos ciclos se ganaron, en total y por funcion.

    python3 tools/abcheck.py bb66d2c            # base contra el arbol actual
    python3 tools/abcheck.py HEAD~1 --prof      # + perfil por funcion (mas lento)
    python3 tools/abcheck.py main --sprites     # lazo cerrado con sprites

Una optimizacion es buena si: mismas resincronizaciones y mismo tramo mas
largo (misma semantica), ciclos de media Y de maximo iguales o menores.
Los ciclos de Musashi no tienen esperas de DMA: sirven para comparar A
contra B; el coste real se mide despues en FS-UAE / WinUAE (regress.py
--emu logic).

Necesita lo que deja setup_cloud.sh (vbcc, player/gen/smwrom00.c,
work/oracle_yi1.bin, work/yi1_map16.bin, work/boot.bin) y machine68k.
Los ficheros generados que no estan en git se copian al worktree: si la
base es muy vieja y el generador cambio, el build de la base puede fallar.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from regress import vbcc_dir  # noqa: E402

GEN = ["player/gen/smwrom00.c", "player/gen/smwtabx.h"]
WORKF = ["work/boot.bin", "work/yi1_map16.bin", "work/oracle_yi1.bin",
         "work/cc/state_run.bin", "work/cc/state_jump.bin"]     # logicbench.s los incluye


def run(cmd, cwd, env=None, timeout=3600):
    p = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace")


def build(tree, env, prof):
    e = dict(env)
    if prof:
        e["PROF"] = "1"
    code, out = run(["sh", "tools/logicbench_build.sh"], tree, e)
    if code:
        sys.exit("fallo el build en %s:\n%s" % (tree, out[-1500:]))
    sub = os.path.join(tree, "work", "prof" if prof else "")
    return os.path.join(sub, "logicbench.bin"), os.path.join(sub, "logicbench.lst")


def verify(bin_, lst, sprites):
    cmd = [sys.executable, os.path.join(HERE, "m68kverify.py"), "--engine", "musashi", "--mode",
           "loop", "--bin", bin_, "--lst", lst] + (["--sprites"] if sprites else [])
    code, out = run(cmd, ROOT)
    t = re.search(r"(\d+) frames, (\d+) resincronizaciones, tramo mas largo (\d+)", out)
    c = re.search(r"media (\d+), p99 (\d+), max (\d+)", out)
    if code or not t or not c:
        sys.exit("m68kverify fallo con %s:\n%s" % (bin_, out[-1500:]))
    return {"frames": int(t.group(1)), "resync": int(t.group(2)), "tramo": int(t.group(3)),
            "media": int(c.group(1)), "p99": int(c.group(2)), "max": int(c.group(3))}


def profile(bin_, lst, sprites):
    cmd = [sys.executable, os.path.join(HERE, "m68kprof.py"), "--bin", bin_, "--lst", lst,
           "--every", "10"] + (["--sprites"] if sprites else [])
    code, out = run(cmd, ROOT, timeout=7200)
    if code:
        sys.exit("m68kprof fallo:\n" + out[-1500:])
    prof = {}
    t = re.search(r"media: (\d+) ciclos por frame", out)
    prof["TOTAL"] = (float(t.group(1)) if t else 0.0, 0.0)
    for m in re.finditer(r"^(\S+)\s+([\d.]+)\s+[\d.]+%\s+([\d.]+)\s*$", out, re.M):
        prof[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return prof


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base", help="commit, rama o tag de referencia")
    ap.add_argument("--sprites", action="store_true", help="lazo cerrado con los sprites del nivel")
    ap.add_argument("--prof", action="store_true", help="tambien el perfil por funcion")
    ap.add_argument("--keep", action="store_true", help="no borrar el worktree")
    a = ap.parse_args()
    v = vbcc_dir()
    if not v:
        sys.exit("no encuentro vbcc (VBCC=...)")
    env = dict(os.environ, VBCC=v)
    for f in GEN + WORKF:
        if not os.path.exists(os.path.join(ROOT, f)):
            sys.exit("falta %s: correr tools/setup_cloud.sh" % f)

    tmp = tempfile.mkdtemp(prefix="abcheck-")
    wt = os.path.join(tmp, "base")
    code, out = run(["git", "worktree", "add", "--detach", wt, a.base], ROOT)
    if code:
        sys.exit(out)
    try:
        for f in GEN + WORKF:
            os.makedirs(os.path.dirname(os.path.join(wt, f)), exist_ok=True)
            shutil.copy(os.path.join(ROOT, f), os.path.join(wt, f))
        # el arbol actual se compila en otra copia para no pisar work/ de
        # quien este trabajando (regress.py, capturas)
        cur = os.path.join(tmp, "actual")
        shutil.copytree(ROOT, cur, ignore=shutil.ignore_patterns(".git", "work", "__pycache__"))
        for f in WORKF:
            os.makedirs(os.path.dirname(os.path.join(cur, f)), exist_ok=True)
            shutil.copy(os.path.join(ROOT, f), os.path.join(cur, f))

        res = {}
        for name, tree in (("base", wt), ("actual", cur)):
            b, l = build(tree, env, False)
            res[name] = verify(b, l, a.sprites)
            res[name]["bytes"] = os.path.getsize(b)
        A, B = res["base"], res["actual"]
        print("%-26s %12s %12s %9s" % ("lazo cerrado%s" % (" + sprites" if a.sprites else ""),
                                       "base", "actual", "cambio"))
        for k in ("frames", "resync", "tramo", "media", "p99", "max", "bytes"):
            ch = "" if not A[k] else "%+.1f %%" % (100.0 * (B[k] - A[k]) / A[k])
            print("%-26s %12d %12d %9s" % (k, A[k], B[k], ch))
        same = all(A[k] == B[k] for k in ("frames", "resync", "tramo"))
        faster = B["media"] <= A["media"] and B["max"] <= A["max"]
        print("\nsemantica: %s" % ("IGUAL" if same else "DISTINTA (la optimizacion cambio el resultado)"))
        print("ciclos:    %s" % ("iguales o menos (media y maximo)" if faster
                                 else "SUBEN en la media o en el peor frame"))

        if a.prof:
            P = {}
            for name, tree in (("base", wt), ("actual", cur)):
                b, l = build(tree, env, True)
                P[name] = profile(b, l, a.sprites)
            names = sorted(set(P["base"]) | set(P["actual"]),
                           key=lambda n: -max(P["base"].get(n, (0, 0))[0], P["actual"].get(n, (0, 0))[0]))
            print("\nperfil (ciclos propios por frame, sin inline, 1 de cada 10 frames).\n"
                  "Si una funcion baja a 0 y otra sube, se fusionaron (refactor o macro): mirar TOTAL.")
            print("%-24s %10s %10s %10s" % ("funcion", "base", "actual", "cambio"))
            for n in names[:30]:
                x, y = P["base"].get(n, (0, 0))[0], P["actual"].get(n, (0, 0))[0]
                print("%-24s %10.0f %10.0f %+10.0f" % (n, x, y, y - x))
        return 0 if same and faster else 1
    finally:
        if not a.keep:
            run(["git", "worktree", "remove", "--force", wt], ROOT)
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print("worktree: %s" % tmp)


if __name__ == "__main__":
    sys.exit(main())
