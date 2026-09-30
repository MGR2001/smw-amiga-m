#!/usr/bin/env python3
"""modelo en Python de build_mid (scroll.s, 6.2) sobre work/yi1_s.dat:
por frame, lineas reescritas y por que, cargas copiadas; coste estimado."""
import struct, sys, os, collections

WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "work")
LINES, LASTX, MIDMAX = 224, 255, 12
PAL = 141876


def s16(v):
    return v - 65536 if v >= 32768 else v


def load():
    b = open(os.path.join(WORK, "yi1_s.dat"), "rb").read()
    offs = struct.unpack_from(">10I", b, 16)
    MLX, MLD, LNS = offs[6], offs[7], offs[8]
    mlx = struct.unpack_from(">225H", b, MLX)
    n = mlx[224] + 1
    recs = [struct.unpack_from(">HHHHhh", b, MLD + 12 * i) for i in range(n + 1)]
    lines = []
    for L in range(LINES):
        i0 = mlx[L]
        # desde el centinela anterior hasta el posterior
        j = i0
        while recs[j][1] != 0x7FFF:
            j += 1
        lines.append([(r[0], s16(r[1]), r[2], r[3], r[4], r[5]) for r in recs[i0 - 1:j + 1]])
    W = struct.unpack_from(">H", b, 4)[0]
    nk = W // 16 + 1
    lns = []
    for k in range(nk):
        o = struct.unpack_from(">H", b, LNS + 2 * k)[0]
        ls = []
        while True:
            v = struct.unpack_from(">H", b, LNS + o)[0]
            o += 2
            if v == 0xFFFF:
                break
            ls.append(v // 32)
        lns.append(ls)
    return lines, lns


class Line:
    def __init__(self, recs):
        self.r = recs           # recs[0] y recs[-1] centinelas
        self.lo = self.hi = 1
        self.vl, self.vu = 1, 0
        self.why = None


def rewrite(ln, s):
    r = ln.r
    lo = ln.lo
    while r[lo][1] < s:
        lo += 1
    while r[lo - 1][1] >= s:
        lo -= 1
    hi = ln.hi
    while r[hi][1] <= s + LASTX:
        hi += 1
    while r[hi - 1][1] > s + LASTX:
        hi -= 1
    vl = r[lo - 1][1] + 1
    vu = r[hi][1] - LASTX
    why = {"vl": "prev", "vu": "enter"}
    n = hi - lo
    ln.lo = lo
    if n == 0:
        ln.hi = hi
    else:
        if n > MIDMAX:
            hi = lo + MIDMAX
            vu = r[lo][1] + 1
            why["vu"] = "cap"
            n = MIDMAX
        ln.hi = hi
        t = r[hi - 1][1] - LASTX
        if t > vl:
            vl, why["vl"] = t, "lastright"
        for k in range(lo, hi):
            a, b = r[k][4], r[k][5]
            if s + a > vl:
                vl, why["vl"] = s + a, "a"
            if s + b < vu:
                vu, why["vu"] = s + b, "b"
    if vl > s or vu <= s:
        vl, vu = s, s + 1
        why = {"vl": "late", "vu": "late"}
    ln.vl, ln.vu, ln.why = vl, vu, why
    return n


def run(lines, lns, frames, cost_line=520, cost_load=124, cost_scan=72):
    lists = [[Line(l) for l in lines] for _ in range(2)]
    last = [0x8000, 0x8000]
    out = []
    for li, s in frames:
        L = lists[li]
        if last[li] == s:
            out.append((s, 0, 0, 0, collections.Counter()))
            continue
        d = abs(last[li] - s)
        last[li] = s
        chk = range(LINES) if d > 16 else lns[s >> 4]
        nl = nd = 0
        why = collections.Counter()
        for y in chk:
            ln = L[y]
            if ln.vl <= s < ln.vu:
                continue
            reason = ("vl:" + ln.why["vl"]) if (ln.why and s < ln.vl) else (
                ("vu:" + ln.why["vu"]) if ln.why else "init")
            why[reason] += 1
            nd += rewrite(ln, s)
            nl += 1
        out.append((s, len(chk), nl, nd, why))
    return out


def frames_speed(speed, stop=4864, s0=0, ret=None):
    """(lista, s) como scroll.s: init escribe A y B con s0; despues B, A, B..."""
    fr = [(0, s0), (1, s0)]
    s, li = s0, 1
    seq = []
    while s < stop:
        s = min(s + speed, stop)
        seq.append(s)
    if ret is not None:
        pass
    for s in seq:
        fr.append((li, s))
        li ^= 1
    return fr


if __name__ == "__main__":
    speed = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    lines, lns = load()
    fr = frames_speed(speed)
    res = run(lines, lns, fr)
    body = res[2 + 8:]
    cost = [(s, 72 * c + 520 * nl + 124 * nd, nl, nd, w) for s, c, nl, nd, w in body]
    cost.sort(key=lambda r: -r[1])
    for s, c, nl, nd, w in cost[:12]:
        print(s, c, "%.1f%%" % (100 * c / PAL), nl, nd, dict(w))
    tot = collections.Counter()
    for r in body:
        tot.update(r[4])
    print("total razones:", dict(tot))
