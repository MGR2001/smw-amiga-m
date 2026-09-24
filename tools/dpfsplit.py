"""
dpfsplit.py - Simula D8 opcion (d): dual playfield + el copper recargando
colores A MITAD DE LINEA para que la capa 1 (PF1, 7 colores) sea 1:1.

Modelo (ver AGENTS.md, D8 punto 7):
  * La asignacion color -> indice (1..7) es FIJA por posicion del nivel: los
    pixeles quedan grabados en el bitmap. Es coloreo de intervalos: cada
    color "vive" en una linea entre su primer y su ultimo uso; dos usos del
    mismo color separados por >= GAP px son intervalos distintos. Si hay mas
    de 7 vivos, el intervalo con menos pixeles se "derrama" al color mas
    cercano de los que estan vivos (error permanente).
  * Por frame (camara cam_x) y por linea: el color inicial de cada indice se
    carga en el borrado horizontal (limite HBL_MOVES). Cada intervalo que
    empieza en pantalla sobre un indice que ya mostro otro color en esa linea
    necesita una MOVE a mitad de linea. Las ranuras del copper estan cada
    SLOT px de pantalla (6 planos lowres: 1 MOVE / 16 px), y la MOVE hace
    efecto en slot_x + fase; con +-MARGIN px de incertidumbre. Se reparten con
    "el plazo mas cercano primero". Si una carga no entra, ese intervalo se ve
    con el color anterior del indice (error).
  * Capa 2 (PF2): fondo limpio de periodo 512, <= 7 colores por linea (una
    sola linea tiene 8: se derrama). Se carga en el borrado horizontal.

Uso:
    python dpfsplit.py [--gap 32] [--margin 4] [--slot 16] [--step 4]
Salidas en work/: d8d_nivel.png (paleta ideal = todas las cargas entran),
d8d_err.png (mapa de error), d8d_worst.png (peor encuadre), y un informe.
"""
import argparse, os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")
SKY = 0x197
SCREEN_W = 256
P = 512


def rgb(c):
    c = np.asarray(c)
    return np.stack([(c >> 10 & 31) << 3, (c >> 5 & 31) << 3, (c & 31) << 3], -1)


def dist2(a, b):
    return ((rgb(a).astype(np.int64) - rgb(b).astype(np.int64)) ** 2).sum(-1)


# --------------------------------------------------------------------------
# asignacion estatica de una linea de la capa 1
# --------------------------------------------------------------------------
def intervals(row, gap):
    """[(start, end, color, npix)] con end inclusivo."""
    out = []
    for c in np.unique(row):
        if c == SKY:
            continue
        xs = np.nonzero(row == c)[0]
        br = np.nonzero(np.diff(xs) >= gap)[0]
        st = np.r_[xs[0], xs[br + 1]]
        en = np.r_[xs[br], xs[-1]]
        for s, e in zip(st, en):
            out.append([int(s), int(e), int(c), int(((xs >= s) & (xs <= e)).sum())])
    out.sort()
    return out


def allocate(row, gap, nreg=7):
    """Devuelve (idx_row, shown_row, ivs): indice por pixel, color mostrado si
    todas las cargas entran (derrames aplicados), e intervalos con 'reg'."""
    ivs = intervals(row, gap)
    reg_free_at = [-10**9] * nreg        # x a partir del cual el registro esta libre
    reg_color = [None] * nreg
    active = []                           # intervalos con registro
    spilled = []
    for iv in ivs:
        s, e, c, n = iv
        active = [a for a in active if a[1] + gap > s]
        free = [r for r in range(nreg) if reg_free_at[r] <= s]
        if not free:
            # derramar el de menos pixeles entre los activos y el nuevo
            victim = min(active + [iv], key=lambda a: a[3])
            if victim is iv:
                spilled.append(iv)
                continue
            active.remove(victim)
            spilled.append(victim)
            r = victim[4]
            victim[4] = None
            free = [r]
        # preferir un registro que ya tenga este color (no hace falta recargar)
        same = [r for r in free if reg_color[r] == c]
        r = same[0] if same else free[0]
        iv.append(r) if len(iv) == 4 else iv.__setitem__(4, r)
        reg_free_at[r] = e + gap
        reg_color[r] = c
        active.append(iv)
    for iv in spilled:
        if len(iv) == 4:
            iv.append(None)
        else:
            iv[4] = None
    idx = np.zeros(len(row), np.int8)
    shown = row.copy()
    good = [iv for iv in ivs if iv[4] is not None]
    for s, e, c, n, r in good:
        seg = row[s:e + 1] == c
        idx[s:e + 1][seg] = r + 1
    for s, e, c, n, r in [iv for iv in ivs if iv[4] is None]:
        # color mas cercano entre los que estan vivos en ese tramo
        live = [g for g in good if g[0] <= e and g[1] >= s]
        xs = np.nonzero(row[s:e + 1] == c)[0] + s
        for x in xs:
            cand = [g for g in live if g[0] <= x <= g[1]] or live or good
            best = min(cand, key=lambda g: int(dist2(g[2], c)))
            shown[x] = best[2]
            idx[x] = best[4] + 1
    return idx, shown, ivs


# --------------------------------------------------------------------------
# un frame: que cargas hacen falta y cuales entran en las ranuras
# --------------------------------------------------------------------------
def frame_line(ivs, cam_x, slot, margin, phase):
    """Devuelve (n_cargas_hbl, n_cargas_mid, px_mal, [intervalos fallidos])."""
    lo, hi = cam_x, cam_x + SCREEN_W
    vis = [iv for iv in ivs if iv[4] is not None and iv[1] >= lo and iv[0] < hi]
    by_reg = {}
    for iv in vis:
        by_reg.setdefault(iv[4], []).append(iv)
    hbl = 0
    loads = []   # (ventana_ini, ventana_fin en pantalla, iv)
    for r, lst in by_reg.items():
        lst.sort()
        hbl += 1
        for prev, cur in zip(lst, lst[1:]):
            if prev[2] == cur[2]:
                continue          # mismo color: no hace falta recargar
            a = prev[1] + 1 - lo + margin     # la nueva carga no puede pisar prev
            b = cur[0] - lo - margin          # ... y tiene que llegar antes de cur
            loads.append((a, b, cur))
    # ranuras en pantalla: x = phase + k*slot
    slots = list(range(phase, SCREEN_W, slot))
    used = set()
    bad_px = 0
    failed = []
    for a, b, iv in sorted(loads, key=lambda t: t[1]):
        ok = None
        for sx in slots:
            if sx in used:
                continue
            if a <= sx <= b:
                ok = sx
                break
        if ok is None:
            s = max(iv[0], lo)
            e = min(iv[1], hi - 1)
            bad_px += iv[3] if (iv[0] >= lo and iv[1] < hi) else max(0, e - s + 1)
            failed.append(iv)
        else:
            used.add(ok)
    return hbl, len(loads), bad_px, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=int, default=32)
    ap.add_argument("--margin", type=int, default=4)
    ap.add_argument("--slot", type=int, default=16)
    ap.add_argument("--step", type=int, default=4)
    ap.add_argument("--tag", default="d8d")
    # MOVE que entran entre el borde derecho de una linea y el izquierdo de
    # la siguiente, medido con player/copbench.s (DPF 6 planos, 320 px): 15,
    # menos el WAIT de la linea = 14.
    ap.add_argument("--hbl", type=int, default=14)
    args = ap.parse_args()

    fg = np.load(os.path.join(WORK, "fg15.npy"))
    bg = np.load(os.path.join(WORK, "bg512.npy"))
    H, W = fg.shape

    # ---- capa 1: asignacion estatica
    idx = np.zeros_like(fg, dtype=np.int8)
    shown = fg.copy()
    all_ivs = []
    for y in range(H):
        i, s, ivs = allocate(fg[y], args.gap)
        idx[y], shown[y] = i, s
        all_ivs.append(ivs)
    spill_px = int((shown != fg).sum())

    # ---- capa 2: <= 7 colores por linea, derrame al mas cercano
    bgs = bg.copy()
    for y in range(H):
        u, c = np.unique(bg[y][bg[y] != SKY], return_counts=True)
        if len(u) > 7:
            keep = u[np.argsort(c)[::-1][:7]]
            for col in set(u.tolist()) - set(keep.tolist()):
                bgs[y][bg[y] == col] = keep[np.argmin(dist2(keep, col))]
    bg_spill = int((bgs != bg).sum())

    # indices de la capa 2 estables entre lineas: cargas en el borrado
    bg_loads = np.zeros(H, np.int32)
    prev = {}
    for y in range(H):
        cols = set(bgs[y][bgs[y] != SKY].tolist())
        keep = {r: c for r, c in prev.items() if c in cols}
        free = [r for r in range(7) if r not in keep]
        for c in sorted(cols - set(keep.values())):
            keep[free.pop(0)] = c
            bg_loads[y] += 1
        prev = keep

    # ---- recorrido de camara
    err_map = np.zeros((H, W), np.int32)
    visits = np.zeros(W, np.int32)
    tot_bad = 0
    tot_px = 0
    max_mid = 0
    max_hbl = 0
    hbl_hist = np.zeros(21, np.int64)
    hbl_over = 0
    worst = (0, 0)
    cams = range(0, W - SCREEN_W + 1, args.step)
    for cam_x in cams:
        phase = (0 if args.slot == 0 else 0)
        visits[cam_x:cam_x + SCREEN_W] += 1
        frame_bad = 0
        state = {}
        for y in range(H):
            lo, hi = cam_x, cam_x + SCREEN_W
            first, last = {}, {}
            for iv in all_ivs[y]:
                if iv[4] is None or iv[1] < lo or iv[0] >= hi:
                    continue
                first.setdefault(iv[4], iv[2])
                last[iv[4]] = iv[2]
            need = sum(1 for r, c in first.items() if state.get(r) != c)
            state.update(last)
            tot_need = need + int(bg_loads[y])
            hbl_hist[min(tot_need, 20)] += 1
            if tot_need > args.hbl:
                hbl_over += 1
            hbl, mid, bad, failed = frame_line(all_ivs[y], cam_x, args.slot,
                                               args.margin, phase)
            max_mid = max(max_mid, mid)
            max_hbl = max(max_hbl, hbl)
            frame_bad += bad
            for iv in failed:
                s = max(iv[0], cam_x)
                e = min(iv[1], cam_x + SCREEN_W - 1)
                seg = fg[y, s:e + 1] == iv[2]
                err_map[y, s:e + 1] += seg
        tot_bad += frame_bad
        tot_px += int((fg[:, cam_x:cam_x + SCREEN_W] != SKY).sum())
        if frame_bad > worst[0]:
            worst = (frame_bad, cam_x)

    # ---- informe
    fgpx = int((fg != SKY).sum())
    print(f"gap={args.gap} margin={args.margin} slot={args.slot} step={args.step}")
    print(f"capa 1: pixeles derramados (error fijo) {spill_px} de {fgpx} "
          f"({100 * spill_px / fgpx:.3f} %)")
    print(f"capa 2: pixeles derramados {bg_spill}")
    print(f"cargas a mitad de linea: max {max_mid} (hay ~20 ranuras en 320 px)")
    nz = np.nonzero(hbl_hist)[0]
    print(f"cargas en el borrado (capa 1 + capa 2, solo lo que cambia): max {nz.max()}, "
          f"lineas-frame por encima de {args.hbl}: {hbl_over} de {int(hbl_hist.sum())}")
    print("   histograma:", {int(k): int(hbl_hist[k]) for k in nz})
    print(f"cargas que no entran: {tot_bad} px mal de {tot_px} px de capa 1 vistos "
          f"({100 * tot_bad / max(tot_px, 1):.3f} %), peor encuadre cam_x={worst[1]} "
          f"con {worst[0]} px")

    # variantes de bloque que exige la asignacion
    pats = set()
    for by in range(0, H - 15, 16):
        for bx in range(0, W - 15, 16):
            blk = idx[by:by + 16, bx:bx + 16]
            if blk.any():
                pats.add(blk.tobytes())
    print(f"bloques distintos en indices (16x16x3 planos): {len(pats)} "
          f"-> {len(pats) * 96 // 1024} KB + mascara")

    # ---- imagenes
    comp = np.where(fg != SKY, shown, np.tile(bgs, (1, W // P)))
    Image.fromarray(rgb(comp).astype(np.uint8)).save(
        os.path.join(WORK, f"{args.tag}_nivel.png"))
    frac = err_map / np.maximum(visits, 1)[None, :]
    hl = (rgb(comp) * 0.35).astype(np.uint8)
    hl[shown != fg] = (255, 255, 0)                      # derrame: siempre mal
    m = frac > 0
    hl[m] = np.stack([np.full(m.sum(), 255),
                      (1 - np.clip(frac[m] * 4, 0, 1)) * 160,
                      np.full(m.sum(), 255)], -1).astype(np.uint8)
    Image.fromarray(hl).save(os.path.join(WORK, f"{args.tag}_err.png"))
    # peor encuadre renderizado
    cx = worst[1]
    view = comp[:, cx:cx + SCREEN_W].copy()
    for y in range(H):
        _, _, _, failed = frame_line(all_ivs[y], cx, args.slot, args.margin, 0)
        for iv in failed:
            # se ve con el color que el indice tenia antes en esa linea
            prev = [p for p in all_ivs[y] if p[4] == iv[4] and p[1] < iv[0]
                    and p[1] >= cx]
            col = prev[-1][2] if prev else iv[2]
            s = max(iv[0], cx)
            e = min(iv[1], cx + SCREEN_W - 1)
            seg = fg[y, s:e + 1] == iv[2]
            view[y, s - cx:e - cx + 1][seg] = col
    Image.fromarray(rgb(view).astype(np.uint8)).resize(
        (SCREEN_W * 2, H * 2), Image.NEAREST).save(
        os.path.join(WORK, f"{args.tag}_worst.png"))


if __name__ == "__main__":
    main()
