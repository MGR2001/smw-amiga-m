"""
d8objs.py - D8 opcion (d): donde pueden ir los objetos (Mario y enemigos).

Los objetos salen de la referencia (SuperMarioWorldMap02.png) restando el
render limpio de las capas (work/d8_b_nivel.png): posicion inicial, mascara
y colores de cada uno.

Por cada objeto mide dos vias:

 (A) bob en PF1: para cada linea que ocupa, en cada posicion de su recorrido,
     cuantos de sus colores tienen registro: o el terreno ya tiene ese color
     vivo en todo el tramo del objeto, o hay un registro de PF1 libre en
     [x - GAP, x + ancho + GAP] (la asignacion de la capa 1 es la de
     dpfsplit.py). Colores sin registro -> color mas cercano (error).
 (B) sprite de hardware: columnas de 16 px por linea (el copper corre la
     columna entre lineas con SPRxPOS), y colores contra los 15 de los
     sprites adosados (17-31) junto con los de Mario.

Recorridos: Rex/Chuck/caparazon +-128 px, Banzai Bill 512 px hacia la
izquierda, el resto quieto.

    python tools/d8objs.py
"""
import os
import numpy as np
from PIL import Image
from scipy import ndimage
import dpfsplit as d

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")
REF = os.path.join(HERE, "..", "..", "..", "SuperMarioWorldMap02.png")
GAP = 48
MARIO = {0x0, 0x7f58, 0x7d0e, 0x2800, 0x7416, 0x7dcd, 0x7fe0, 0x2213, 0x4379,
         0x58ac, 0x10d1}


def c15(a):
    a = a.astype(np.int64)
    return (a[..., 0] >> 3) << 10 | (a[..., 1] >> 3) << 5 | (a[..., 2] >> 3)


def main():
    ref = c15(np.array(Image.open(REF).convert("RGB").crop((0, 0, 5120, 432))))
    clean = c15(np.array(Image.open(os.path.join(WORK, "d8_b_nivel.png")).convert("RGB")))
    fg = np.load(os.path.join(WORK, "fg15.npy"))
    H, W = fg.shape
    diff = ref != clean
    lab, _ = ndimage.label(ndimage.binary_closing(diff, np.ones((5, 5))))
    ivs = [d.allocate(fg[y], GAP)[2] for y in range(H)]

    objs = []
    for i, sl in enumerate(ndimage.find_objects(lab)):
        m = (lab[sl] == i + 1) & diff[sl]
        if m.sum() < 30:
            continue
        cols, cnt = np.unique(ref[sl][m], return_counts=True)
        cset = {int(c) for c, k in zip(cols, cnt) if k >= 6}
        x0, y0 = sl[1].start, sl[0].start
        w, h = m.shape[1], m.shape[0]
        spans = [(np.nonzero(r)[0].min(), np.nonzero(r)[0].max()) for r in m if r.any()]
        ncol = max((b - a) // 16 + 1 for a, b in spans)
        if w >= 60:
            kind, path = "Banzai", range(-512, 1, 8)
        elif w in (19, 20) and h >= 30:
            kind, path = "Rex", range(-128, 129, 8)
        elif w == 28:
            kind, path = "Chuck", range(-128, 129, 8)
        else:
            kind, path = "otro", range(0, 1)
        objs.append(dict(x=x0, y=y0, w=w, h=h, cols=cset, ncol=ncol, kind=kind,
                         path=path, rows=[(y0 + j, a, b) for j, (a, b) in
                                          enumerate(spans)]))

    print("%-7s %5s %4s %6s %5s %4s | %-26s | %s" % (
        "tipo", "x", "y", "tam", "cols", "col16", "A: bob en PF1 (lineas-pos ok)",
        "B: sprite, colores con Mario"))
    for o in sorted(objs, key=lambda o: o["x"]):
        ok = tot = 0
        miss_max = 0
        for dx in o["path"]:
            for (y, a, b) in o["rows"]:
                if not (0 <= y < H):
                    continue
                xa, xb = o["x"] + a + dx, o["x"] + b + dx
                live = [iv for iv in ivs[y] if iv[4] is not None and
                        iv[0] <= xb + GAP and iv[1] + GAP >= xa]
                covered = {iv[2] for iv in live if iv[0] <= xa and iv[1] >= xb}
                used = {iv[4] for iv in live}
                need = len(o["cols"] - covered)
                free = 7 - len(used)
                tot += 1
                if need <= free:
                    ok += 1
                else:
                    miss_max = max(miss_max, need - free)
        union = len(o["cols"] | MARIO)
        print("%-7s %5d %4d %3dx%-2d %5d %4d | %5.1f %% (falta max %d)       | %d %s" % (
            o["kind"], o["x"], o["y"], o["w"], o["h"], len(o["cols"]), o["ncol"],
            100.0 * ok / max(tot, 1), miss_max, union,
            "ok" if union <= 15 else "+%d" % (union - 15)))

    # demanda de columnas de sprite por linea, objetos quietos + Mario
    worst = 0
    where = None
    for cam in range(0, W - 256, 8):
        need = np.ones(H, int)                     # Mario, en cualquier linea
        for o in objs:
            if o["kind"] == "Banzai":
                continue
            if o["x"] + o["w"] < cam or o["x"] >= cam + 256:
                continue
            for (y, a, b) in o["rows"]:
                need[y] += (b - a) // 16 + 1
        if need.max() > worst:
            worst, where = int(need.max()), cam
    print("\ncolumnas de sprite por linea (objetos en su sitio, sin Banzai, + Mario): "
          "max %d (cam_x=%d); hay 4 columnas adosadas / 8 de 3 colores" % (worst, where))


if __name__ == "__main__":
    main()
