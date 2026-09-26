#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_port.py - comprobaciones estaticas de las reglas de AGENTS.md que un
compilador no ve. Segundos; correrlo antes de cada commit.

    python3 tools/lint_port.py            # errores y resumen de avisos
    python3 tools/lint_port.py --all      # ademas, cada aviso con su linea

ERRORES (salen con 1):
  R9   un fichero versionado que deriva de la ROM (ROM, ADF, work/ salvo las
       grabaciones, player/gen/smwrom00.c, smwtabx.h, assets-out/) o un
       fichero versionado de mas de 2 MB que no es una grabacion
  C1   float / double en player/*.c (no hay FPU, AGENTS.md §7)
  C2   malloc / free en player/*.c
  C3   #include <...> de la libc en player/*.c fuera de un #if (trazas)
  P38  un puntero "p = ram + ..." indexado con una direccion absoluta
       p[wm_X]: vbcc -O=991 suma dos veces la base. Usar p[wm_X - wm_BASE]
AVISOS (no fallan; revisar):
  P40  (An,Dn.w) en player/*.s: el indice es de 16 bits CON signo. Si el
       desplazamiento puede pasar de 32767 hay que usar (An,Dn.l) con el
       registro extendido. Una linea revisada se marca con "; P40 ok".
  C4   'int' a secas en player/*.c (en vbcc 68000 es de 32 bits: cada
       operacion .l cuesta mas; preferir u8/u16/s16 salvo donde haga falta)
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

R9_BAD = [
    (re.compile(r"\.(sfc|smc|rom|adf)$", re.I), "ROM / Kickstart / disco"),
    (re.compile(r"^work/(?!oracle_[^/]*\.txt$|oam_[^/]*\.txt$)"), "work/ (solo se versionan las grabaciones)"),
    (re.compile(r"^player/gen/smwrom00\.c$"), "bytes de la ROM volcados a C"),
    (re.compile(r"^player/gen/smwtabx\.h$"), "tablas sacadas de la ROM"),
    (re.compile(r"^assets-out/"), "graficos convertidos"),
]
BIG = 2 * 1024 * 1024


def git_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, stdout=subprocess.PIPE).stdout
    return [f for f in out.decode("utf-8", "replace").split("\0") if f]


def strip_c_comments(src):
    src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="mostrar cada aviso")
    a = ap.parse_args()
    errors, warns = [], []

    # --- R9 ---------------------------------------------------------------
    for f in git_files():
        for rx, why in R9_BAD:
            if rx.search(f):
                errors.append(("R9", f, 0, why))
        p = os.path.join(ROOT, f)
        if os.path.isfile(p) and os.path.getsize(p) > BIG and not re.match(r"work/(oracle|oam)_", f):
            errors.append(("R9", f, 0, "fichero versionado de %d KB" % (os.path.getsize(p) // 1024)))

    # --- C ----------------------------------------------------------------
    pdir = os.path.join(ROOT, "player")
    for fn in sorted(os.listdir(pdir)):
        if not fn.endswith((".c", ".h")):
            continue
        rel = "player/" + fn
        src = strip_c_comments(open(os.path.join(pdir, fn), encoding="latin-1").read())
        lines = src.split("\n")
        depth = 0
        ptrs = set(re.findall(r"\b(\w+)\s*=\s*ram\s*\+", src))
        for i, ln in enumerate(lines, 1):
            s = ln.strip()
            if s.startswith("#if"):
                depth += 1
            elif s.startswith("#endif"):
                depth = max(0, depth - 1)
            if re.search(r"\b(float|double)\b", ln):
                errors.append(("C1", rel, i, s))
            if re.search(r"\b(malloc|calloc|realloc|free)\s*\(", ln):
                errors.append(("C2", rel, i, s))
            if s.startswith("#include <") and depth == 0:
                errors.append(("C3", rel, i, s))
            for p in ptrs:
                m = re.search(r"\b%s\s*\[\s*(wm_\w+)\s*\]" % re.escape(p), ln)
                if m:
                    errors.append(("P38", rel, i, "%s[%s]: usar %s[%s - <base>]" % (p, m.group(1), p, m.group(1))))
            if re.search(r"(^|[^\w])int\b", ln) and not re.search(r"unsigned\s+int|\bint\s+main\b", ln):
                warns.append(("C4", rel, i, s))

    # --- asm --------------------------------------------------------------
    for fn in sorted(os.listdir(pdir)):
        if not fn.endswith((".s", ".i")):
            continue
        rel = "player/" + fn
        for i, ln in enumerate(open(os.path.join(pdir, fn), encoding="latin-1"), 1):
            code = ln.split(";")[0]
            if re.search(r"\(\s*(a[0-7]|sp|pc)\s*,\s*(d[0-7]|a[0-7])\.w\s*\)", code, re.I) \
                    and "P40 ok" not in ln:
                warns.append(("P40", rel, i, ln.strip()))

    for code, f, i, text in errors:
        print("ERROR %-4s %s%s  %s" % (code, f, ":%d" % i if i else "", text))
    by = {}
    for code, f, i, text in warns:
        by.setdefault(code, []).append((f, i, text))
    for code, lst in sorted(by.items()):
        files = sorted({f for f, _, _ in lst})
        print("aviso %-4s %d casos en %s%s" % (code, len(lst), ", ".join(files),
                                               "" if a.all else "  (--all para verlos)"))
        if a.all:
            for f, i, text in lst:
                print("      %s:%d  %s" % (f, i, text))
    print("RESULTADO: %s" % ("FALLA (%d errores)" % len(errors) if errors else "OK"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
