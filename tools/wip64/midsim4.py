#!/usr/bin/env python3
"""modelo 4 (CIP-delta): base por linea s0 = s + delta (conservadora con a, b
como hoy), canonica (delta = 0 + celda) si hay una carga imposible; cargas
muertas sin cota superior salvo lonext; entradas por 'necesaria'.
Operaciones: FULL (reescribir todo), REBASE (solo las h de los WAIT +
validez) con APPEND por la derecha y TRUNC por la derecha."""
import sys, collections
from midsim import load, LINES, LASTX, PAL
from midsim2 import prep, frames_ret, INF

MIDB = 144
SIZE = {0: 8, 1: 4, 2: 8, 3: 12}
TMIN = 0                       # blanco minimo en pantalla de una carga escrita


def prep4(lines):
    L2 = prep(lines)
    for ln in L2:
        n = ln.n
        ln.a = [ln.lo[k] - ln.x[k] for k in range(n)]
        ln.b = [ln.hi[k] - ln.x[k] - 6 for k in range(n)]
        need = [ln.hi[k] - LASTX < ln.lo[k] for k in range(n)]
        ln.PL = [-INF] * (n + 1)
        for k in range(n):
            ln.PL[k + 1] = max(ln.PL[k], ln.lo[k] if need[k] else -INF)
        ln.SR = [INF] * (n + 1)
        for k in range(n - 1, -1, -1):
            ln.SR[k] = min(ln.SR[k + 1], ln.hi[k] - LASTX if need[k] else INF)
        ln.klo = ln.khi = 0
        ln.s0 = 0
        ln.canon = False
        ln.vl, ln.vu = 1, 0
    return L2


def nbytes(ln, klo, khi):
    return sum(8 if k == klo else SIZE[ln.cls[k]] for k in range(klo, khi))


def nwaits(ln, klo, khi):
    return sum(1 for k in range(klo, khi) if k == klo or ln.cls[k] == 0)


def place(ln, s, d, klo, khi, st):
    """elige s0 y calcula la validez; devuelve False si no se puede"""
    dlo, dhi = -INF, INF
    for k in range(klo, khi):
        if ln.lo[k] > s:
            dlo = max(dlo, -ln.b[k] + 1)
            dhi = min(dhi, -ln.a[k])
    if khi > klo:
        slo = ln.x[khi - 1] - s - LASTX        # la ultima en pantalla
        shi = ln.x[klo] - s - TMIN             # la primera en pantalla
    else:
        slo, shi = -INF, INF
    canon = False
    lo_, hi_ = max(dlo, slo), min(dhi, shi)
    if lo_ <= hi_:
        delta = (hi_ if d >= 0 else lo_)
        if delta == -INF or delta == INF:
            delta = 0
    else:
        if slo > 0 or shi < 0:
            return False
        delta, canon = 0, True
    s0 = s + delta
    vl, vu = ln.PL[klo], ln.SR[khi]
    for k in range(klo, khi):
        a, b, lo = ln.a[k], ln.b[k], ln.lo[k]
        if ln.lo[k] > s:
            if canon and not (s0 + a <= s < s0 + b):
                y = ln.x[k] - s
                c0 = ln.x[k] - 8 * ((y + 8) >> 3)
                vl, vu = max(vl, c0 + 1), min(vu, c0 + 9)
                continue
            vl = max(vl, s0 + a)
            if lo > s0 + b:
                vu = min(vu, s0 + b)          # caduca antes de morir
        else:
            vl = max(vl, s0 + a if lo <= s0 + b else lo)
        vu = min(vu, ln.lonext[k])
    if not (vl <= s < vu):
        st["forced"] += 1
        vl, vu = s, s + 1
    ln.s0, ln.canon, ln.vl, ln.vu = s0, canon, vl, vu
    return True


def full(ln, s, d, st):
    klo = 0
    n = ln.n
    while klo < n and (ln.lo[klo] <= s or ln.x[klo] < s):
        klo += 1
    khi = klo
    while khi < n and ln.x[khi] <= s + LASTX and nbytes(ln, klo, khi + 1) <= MIDB:
        khi += 1
    ln.klo, ln.khi = klo, khi
    if not place(ln, s, d, klo, khi, st):
        st["fullfail"] += 1
        ln.vl, ln.vu = s, s + 1
    return 520 + 124 * (khi - klo)


def check(ln, s, d, st):
    """devuelve (coste, tipo)"""
    klo, khi = ln.klo, ln.khi
    if ln.PL[klo] > s:
        return full(ln, s, d, st), "full:entL"
    for k in range(klo, khi):
        if ln.lonext[k] <= s:
            return full(ln, s, d, st), "full:lonext"
    # la primera escrita todavia en pantalla (blanco >= TMIN) con la base nueva
    # se decide en place(); truncar por la derecha las que salen (vuelta)
    cost = 150
    kind = "rebase"
    nkhi = khi
    while nkhi > klo and ln.x[nkhi - 1] > s + LASTX and ln.hi[nkhi - 1] > s + LASTX:
        nkhi -= 1
    if nkhi != khi:
        kind = "rebase+trunc"
    # por la derecha: las que entraron
    app = 0
    while nkhi < ln.n and ln.x[nkhi] <= s + LASTX:
        if nbytes(ln, klo, nkhi + 1) > MIDB:
            return full(ln, s, d, st), "full:cap"
        nkhi += 1
        app += 1
    if app:
        kind = "rebase+app"
    if not place(ln, s, d, klo, nkhi, st):
        return full(ln, s, d, st), "full:place"
    ln.khi = nkhi
    return cost + 50 * nwaits(ln, klo, nkhi) + 25 * (nkhi - klo) + 124 * app, kind


def run(lines, lns, frames):
    L2 = [prep4(lines), prep4(lines)]
    last = [0x8000, 0x8000]
    out = []
    prevs = None
    st = collections.Counter()
    for li, s in frames:
        d = 0 if prevs is None else (1 if s > prevs else (-1 if s < prevs else 0))
        prevs = s
        if last[li] == s:
            out.append((s, 0, 0))
            continue
        dd = abs(last[li] - s)
        last[li] = s
        chk = range(LINES) if dd > 16 else lns[s >> 4]
        cost = 72 * len(chk)
        nl = 0
        for y in chk:
            ln = L2[li][y]
            if ln.vl <= s < ln.vu:
                continue
            if dd > 16:
                c, kind = full(ln, s, d, st), "full:jump"
            else:
                c, kind = check(ln, s, d, st)
            st[("<" if d < 0 else ">") + kind] += 1
            cost += c
            nl += 1
        out.append((s, cost, nl))
    return out, st


if __name__ == "__main__":
    speed = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    lines, lns = load()
    fr, nf = frames_ret(speed)
    res, st = run(lines, lns, fr)
    print(dict(sorted(st.items())))
    fw, bw = res[2 + 8:2 + nf], res[2 + nf:]
    for name, part in (("ida", fw), ("vuelta", bw)):
        cs = [c for _, c, _ in part]
        m = max(range(len(cs)), key=lambda i: cs[i])
        print("%s: media %.1f%%  max %.1f%% (s=%d, %d lineas)  >25%%: %d  >20%%: %d"
              % (name, 100 * sum(cs) / len(cs) / PAL, 100 * cs[m] / PAL, part[m][0], part[m][2],
                 sum(1 for c in cs if c > 0.25 * PAL), sum(1 for c in cs if c > 0.20 * PAL)))
        for s, c, nl in sorted(part, key=lambda r: -r[1])[:5]:
            print("   s=%d %.1f%% lineas %d" % (s, 100 * c / PAL, nl))
