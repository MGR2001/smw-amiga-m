#!/usr/bin/env python3
"""modelo 2: build_mid con validez exacta (rejilla), cargas 'necesarias'
(ventana [lo, hi] entera en pantalla), cargas muertas inofensivas hasta que
el CHG de la siguiente del mismo registro se aplica, y colocacion segun la
direccion. Solo reescrituras completas (coste modelado)."""
import sys, collections
from midsim import load, frames_speed, LINES, LASTX, PAL

INF = 1 << 20


def G(y):
    """x de pantalla donde cae el MOVE despues del WAIT con htab[y]"""
    if y <= 239:
        return 8 * ((y + 8) >> 3) - 1
    t = y - 240
    return 255 if t >= 12 else 243 + (t & ~3)


def gmin(t):
    """menor y >= 0 con G(y) >= t (None si no hay)"""
    for y in range(max(0, t - 8), LASTX + 1):
        if G(y) >= t:
            return y
    return None


def gmax(t):
    """mayor y con G(y) <= t (None si no hay)"""
    for y in range(min(LASTX, t), -1, -1):
        if G(y) <= t:
            return y
    return None


class L:
    pass


def prep(lines):
    out = []
    for recs in lines:
        r = recs[1:-1]
        ln = L()
        ln.x = [q[1] for q in r]
        ln.cls = [q[0] for q in r]
        ln.reg = [q[2] for q in r]
        ln.lo = [q[1] + q[4] for q in r]
        ln.hi = [q[1] + q[5] + 6 for q in r]
        n = len(r)
        nxt = [INF] * n
        last = {}
        for k in range(n - 1, -1, -1):
            nxt[k] = last.get(ln.reg[k], INF)
            last[ln.reg[k]] = ln.lo[k]
        ln.lonext = nxt
        ln.n = n
        out.append(ln)
    return out


def place(ln, s, d, W):
    """coloca las cargas W (indices crecientes) en s, direccion d. Devuelve
    dict k -> G (pantalla) y cuantas quedaron 'tarde' (necesarias invalidas)."""
    # cadenas: corridas de W consecutivas en el plan con clase != 0
    chains = []
    for k in W:
        if chains and chains[-1][-1] == k - 1 and ln.cls[k] != 0:
            chains[-1].append(k)
        else:
            chains.append([k])
    pos, late = {}, 0
    if d >= 0:
        prev_end = -INF
        for c in chains:
            h = c[0]
            Lc = -INF
            for k in c:
                if ln.lo[k] > s:
                    Lc = max(Lc, ln.lo[k] - (ln.x[k] - ln.x[h]) - s)
            t = max(Lc, prev_end + 48, 0)
            y = gmin(t)
            D = ln.x[c[-1]] - ln.x[h]
            if y is None or y + D > LASTX:
                y = min(LASTX - D, LASTX) if y is None else y
                y = max(0, min(y, LASTX - D))
            g = G(y)
            for k in c:
                pos[k] = g + ln.x[k] - ln.x[h]
            prev_end = g + D
    else:
        nxt_head = INF
        for c in reversed(chains):
            h = c[0]
            D = ln.x[c[-1]] - ln.x[h]
            Hc = INF
            for k in c:
                if ln.lo[k] > s:
                    Hc = min(Hc, ln.hi[k] - (ln.x[k] - ln.x[h]) - s)
            t = min(Hc, nxt_head - 48 - D, LASTX - D)
            y = gmax(t) if t >= 0 else 0
            if y is None:
                y = 0
            g = G(y)
            for k in c:
                pos[k] = g + ln.x[k] - ln.x[h]
            nxt_head = g
    for k in W:
        if ln.lo[k] > s and ln.hi[k] <= s + LASTX:
            l = pos[k] + s
            if not (ln.lo[k] <= l <= ln.hi[k]):
                late += 1
    return pos, late


def validity(ln, s, W, pos):
    vl, vu = -INF, INF
    Ws = set(W)
    for k in W:
        g = pos[k]
        lo, hi = ln.lo[k], ln.hi[k]
        gap = hi - g + 1 < lo
        alive = lo > s
        if alive:
            l = g + s
            if not (lo <= l and (l <= hi or hi > s + LASTX)):
                return s, s + 1              # tarde: cada frame (P50)
            vl = max(vl, lo - g)
            if gap:
                vu = min(vu, hi - g + 1)
        else:
            vl = max(vl, lo if gap else lo - g)
        vu = min(vu, ln.lonext[k])          # la siguiente del registro se aplica
    for k in range(ln.n):
        if k in Ws:
            continue
        lo, hi = ln.lo[k], ln.hi[k]
        if hi - LASTX >= lo:
            continue                         # ventana mas ancha que la pantalla
        # necesaria en [hi - LASTX, lo)
        if hi - LASTX > s:
            vu = min(vu, hi - LASTX)
        elif lo <= s:
            vl = max(vl, lo)
        else:
            return s, s + 1                  # necesaria y no escrita (no deberia)
    return vl, vu


def rewrite(ln, s, d, look):
    W = []
    for k in range(ln.n):
        lo, hi = ln.lo[k], ln.hi[k]
        if lo > s and hi <= s + LASTX:
            W.append(k)                      # necesaria
        elif d >= 0 and lo > s and s + LASTX < hi <= s + LASTX + look and ln.x[k] <= s + LASTX:
            W.append(k)                      # la siguiente por la derecha
        elif d < 0 and hi <= s + LASTX and s - look < lo <= s and ln.x[k] >= s:
            W.append(k)                      # la siguiente por la izquierda
    pos, late = place(ln, s, d, W)
    vl, vu = validity(ln, s, W, pos)
    return W, vl, vu, late


def run(lines, lns, frames, look=0):
    L2 = prep(lines)
    st = [[[-INF + 1, -INF] for _ in range(LINES)] for _ in range(2)]
    last = [0x8000, 0x8000]
    out = []
    prevs = None
    for li, s in frames:
        d = 0 if prevs is None else (1 if s > prevs else (-1 if s < prevs else 0))
        prevs = s
        if last[li] == s:
            out.append((s, 0, 0, 0, 0))
            continue
        dd = abs(last[li] - s)
        last[li] = s
        chk = range(LINES) if dd > 16 else lns[s >> 4]
        nl = nd = lt = 0
        for y in chk:
            vl, vu = st[li][y]
            if vl <= s < vu:
                continue
            W, vl, vu, late = rewrite(L2[y], s, d, look)
            st[li][y] = [vl, vu]
            nl += 1
            nd += len(W)
            lt += late
        out.append((s, len(chk), nl, nd, lt))
    return out


def frames_ret(speed, stop=4864):
    fr = [(0, 0), (1, 0)]
    s, li = 0, 1
    seq = list(range(speed, stop + 1, speed))
    if seq[-1] != stop:
        seq.append(stop)
    back = list(range(stop - speed, -1, -speed))
    for s in seq + back:
        fr.append((li, s))
        li ^= 1
    return fr, len(seq)


if __name__ == "__main__":
    speed = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    look = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    cl, cd = 600, 150
    lines, lns = load()
    fr, nf = frames_ret(speed)
    res = run(lines, lns, fr, look)
    fw, bw = res[2 + 8:2 + nf], res[2 + nf:]
    for name, part in (("ida", fw), ("vuelta", bw)):
        cost = [(s, 72 * c + cl * nl + cd * nd, nl, nd, lt) for s, c, nl, nd, lt in part]
        cs = [c for _, c, *_ in cost]
        m = max(range(len(cs)), key=lambda i: cs[i])
        print("%s: media %.1f%%  max %.1f%% (s=%d, %d lineas, %d cargas)  >25%%: %d  tarde: %d"
              % (name, 100 * sum(cs) / len(cs) / PAL, 100 * cs[m] / PAL, cost[m][0], cost[m][2],
                 cost[m][3], sum(1 for c in cs if c > 0.25 * PAL), sum(r[4] for r in part)))
        for s, c, nl, nd, lt in sorted(cost, key=lambda r: -r[1])[:5]:
            print("   s=%d %.1f%% lineas %d cargas %d tarde %d" % (s, 100 * c / PAL, nl, nd, lt))
