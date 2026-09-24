#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scroll_check.py - compara una captura de player/scroll.s (FS-UAE, x2,125)
con el frame esperado calculado en el PC desde work/yi1_d.dat, con el
mismo modelo que la Amiga: capa 2 a media velocidad (paralaje) y los
colores de la capa 1 cargados solo en el borrado (--mid: con las cargas
a mitad de linea, lo que tiene que dar el scroll definitivo).

    python3 tools/scroll_check.py --shot work/scroll.png --s 1000 [--mid]

El origen de la captura (x0, y0) se busca por ajuste. Los bordes de 1 px
y los puntos de la tierra salen distintos por el reescalado x2,125 de la
captura, no por la Amiga: el % no llega a 0 aunque este todo bien.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_d                                 # noqa: E402

Y0, LINES, W, SC = 192, 224, 320, 2.125


def expect(d, idx, s, mid):
    out = np.zeros((LINES, W), np.int32)
    for L in range(LINES):
        y = Y0 + L
        if mid:
            col = render_d.reg_colors(d["events"][y], d["W"])[:, s:s + W]
        else:
            col = np.zeros((8, W), np.int32)
            by = {}
            for ev in d["events"][y]:
                if ev[1] >= s and ev[0] < s + W:
                    by.setdefault(ev[2], []).append(ev)
            for r, lst in by.items():
                lst.sort()
                col[r, :] = lst[0][3]
        i1 = idx[y, s:s + W]
        o = np.full(W, d["sky"], np.int32)
        i2 = d["l2idx"][y, (s // 2 + np.arange(W)) % 512]
        m2 = i2 > 0
        o[m2] = d["l2pal"][y, i2[m2] - 1]
        m1 = i1 > 0
        o[m1] = col[i1[m1], np.nonzero(m1)[0]]
        out[L] = o
    return render_d.rgb8(out).astype(int)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=os.path.join(HERE, "..", "work", "scroll.png"))
    ap.add_argument("--s", type=int, default=1000)
    ap.add_argument("--mid", action="store_true")
    ap.add_argument("--png", default=os.path.join(HERE, "..", "work", "scroll_cmp.png"))
    a = ap.parse_args()
    d = render_d.load(os.path.join(HERE, "..", "work", "yi1_d.dat"))
    e = expect(d, render_d.l1_index(d), a.s, a.mid)
    cap = np.asarray(Image.open(a.shot).convert("RGB")).astype(int)
    best = None
    for x0 in np.arange(150, 200, 0.5):
        for y0 in np.arange(90, 125, 0.5):
            xs = (x0 + (np.arange(0, W, 4) + 0.5) * SC).astype(int)
            ys = (y0 + (np.arange(0, LINES, 4) + 0.5) * SC).astype(int)
            if xs[-1] >= cap.shape[1] or ys[-1] >= cap.shape[0]:
                continue
            ok = (np.abs(cap[ys][:, xs] - e[::4, ::4]).max(axis=2) <= 8).mean()
            if best is None or ok > best[0]:
                best = (ok, x0, y0)
    _, x0, y0 = best
    xs = (x0 + (np.arange(W) + 0.5) * SC).astype(int)
    ys = (y0 + (np.arange(LINES) + 0.5) * SC).astype(int)
    got = cap[ys][:, xs]
    bad = np.abs(got - e).max(axis=2) > 8
    print("origen de la captura (%.1f, %.1f); %d px distintos de %d (%.2f %%)"
          % (x0, y0, bad.sum(), bad.size, 100 * bad.mean()))
    img = np.vstack([e, got, np.where(bad[..., None], [255, 0, 255], got // 2 + 64)])
    Image.fromarray(img.astype(np.uint8)).resize((960, 2016), 0).save(a.png)
    print("-> %s (esperado / captura / fallos en magenta)" % a.png)


if __name__ == "__main__":
    main()
