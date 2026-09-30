#!/usr/bin/env python3
"""
scrollsim.py - simulador del copper del scroll (Etapa 0.3/0.4, 6.x).

Corre player/scroll.s en Musashi (tools/scrollprof.py) y, en CADA frame del
recorrido, lee la lista del copper que se va a mostrar, la ejecuta con el
modelo MEDIDO del copper (P39, P42) y compara los colores de la capa 1 con
el render del PC (render_d). Asi se ven los errores de color EN MOVIMIENTO,
que las capturas con el scroll parado (scroll_check) no ven.

Modelo (medido en WinUAE / FS-UAE, pantalla del scroll):
  - el borrado (2 WAIT + MOVE de color en (v-1, $E2)) deja los registros
    listos y el copper LIBRE ~60 px antes de x = 0 (T0); un MOVE sin WAIT
    despues del borrado cae ahi, no en x = 0 (P42). Con mas de 9 MOVE en el
    borrado se aproxima 16 px por MOVE de mas;
  - MOVE: escribe en x = T, T += 16;
  - WAIT (v, h): T = max(T + 32, x(h)), x(h) de P42;
  - un color vale desde la x en que se escribe.
Solo mira la capa 1 (registros $182-$18E) en los pixeles donde se ve.

  python3 tools/scrollsim.py                    # todo el nivel, SPEED=4
  python3 tools/scrollsim.py --from 1780 --to 1840 --png work/sim.png
"""
import argparse, hashlib, os, struct, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_d                                 # noqa: E402
import scrollprof as P                          # noqa: E402

Y0, LINES, W = 192, 224, 320
CL_LINES, SEG = 92, 220
T0 = -56                # x en que termina el borrado de 7 MOVE (antes de 0; P42)


def xh(h):
    """x de pantalla donde cae el MOVE despues de WAIT h (P42; 256 px: copcal -DW256)"""
    if W == 256:
        if h <= 0xC0:
            return 8 * ((h - 0x48) >> 2) - 1
        return {0xC4: 243, 0xC6: 243, 0xC8: 247, 0xCA: 247, 0xCC: 251}.get(h, 255 if h <= 0xCE else 999)
    return 8 * ((h - 0x38) >> 2) - 1 if h <= 0xD0 else 303 + (h - 0xD0)


def run_list(mem, base):
    """por linea: [(x, registro, color)] de la capa 1 (borrado en x = -1)"""
    out = []
    for L in range(LINES):
        a = base + CL_LINES + L * SEG
        ev, T, nb, stage = [], 0, 0, 0
        v = L + 0x2C
        for _ in range(SEG // 4):
            w1, w2 = mem.r16(a), mem.r16(a + 2)
            a += 4
            if w1 & 1:                                   # WAIT
                if (w1 >> 8) == (v - 1) & 0xFF:          # los del borrado (v de 8 bits)
                    continue
                if stage == 0:
                    stage = 1
                    T = T0 + max(0, 16 * (nb - 9))
                T = max(T + 32, xh(w1 & 0xFE))
                continue
            if w1 == 0x8A:                               # COPJMP2: fin
                break
            if w1 in (0x84, 0x86):
                continue
            if stage == 0 and not (w1 == 0x1FE):
                nb += 1
                if 0x182 <= w1 <= 0x18E:
                    ev.append((-1, (w1 - 0x180) >> 1, w2))
                continue
            if stage == 0:
                stage = 1
                T = T0 + max(0, 16 * (nb - 9))
            if 0x182 <= w1 <= 0x18E:
                ev.append((T, (w1 - 0x180) >> 1, w2))
            T += 16
        out.append(ev)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "..", "player", "scroll.s"))
    ap.add_argument("--speed", type=int, default=4)
    ap.add_argument("--vis", type=int, default=256, help="ancho de pantalla de scroll.s (-DVIS)")
    ap.add_argument("--from", dest="x0", type=int, default=0)
    ap.add_argument("--to", dest="x1", type=int, default=5120)
    ap.add_argument("-D", action="append", default=[])
    ap.add_argument("--png", help="imagen (esperado / simulado / fallos) del peor frame")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--data", default=os.path.join(P.WORK, "yi1_s.dat"))
    ap.add_argument("--ret", action="store_true",
                    help="ida (--from -> --to) y vuelta (-> --from): la imagen simulada de la "
                         "capa 1 tiene que ser IDENTICA en cada s (6.2, P50)")
    a = ap.parse_args()
    global W, T0
    W = a.vis
    T0 = -56 - (320 - W)            # el borrado termina a la misma h: antes de x = 0
    a.x1 = min(a.x1, 5120 - W)

    d = render_d.load(os.path.join(P.WORK, "yi1_d.dat"))
    idx = render_d.l1_index(d)
    ideal = [render_d.reg_colors(d["events"][Y0 + L], d["W"]) for L in range(LINES)]
    defs = ["SPEED=%d" % a.speed, "STOPX=%d" % a.x1, "VIS=%d" % W]
    if a.ret:
        defs = ["SPEED=%d" % a.speed, "S0=%d" % a.x0, "RETURN=%d" % a.x1, "STOPX=%d" % a.x0,
                "VIS=%d" % W]
    code, lst = P.assemble(a.src, defs + a.D)
    syms, local = P.listing(lst)
    V = {n: v for n, v in syms.items() if n.startswith("V_")}
    sc = P.Scroll(code, syms, local, open(a.data, "rb").read(), V)
    sc.init()
    res, prev, worst = [], None, None
    back, fwd_img, same, diff, back_tot = False, {}, 0, [], 0
    while True:
        s, _ = sc.frame()
        if s == prev:
            break
        if prev is not None and s < prev:
            back = True
        prev = s
        if s < a.x0:
            continue
        img = hashlib.sha1()
        lst_adr = sc.mem.r32(P.FAKE + 0x80)             # COP1LC: lo que se ve despues
        lines = run_list(sc.mem, lst_adr)
        bad = np.zeros((LINES, W), bool)
        late = early = 0
        for L, ev in enumerate(lines):
            i1 = idx[Y0 + L, s:s + W]
            if not i1.any():
                continue
            reg = np.zeros((8, W), np.int32)
            for x, r, c in sorted(ev, key=lambda e: e[0]):
                reg[r, max(x, 0):] = c
            want = ideal[L][:, s:s + W]
            cols = np.arange(W)
            got_c = reg[i1, cols]
            want_c = want[i1, cols]
            m = (i1 > 0) & (got_c != want_c)
            bad[L] = m
            img.update(struct.pack(">H", L) + (got_c * (i1 > 0)).astype(np.int32).tobytes())
        n = int(bad.sum())
        if back:
            if s in fwd_img:
                if fwd_img[s] == img.digest():
                    same += 1
                else:
                    diff.append(s)
            back_tot += n
            continue
        fwd_img[s] = img.digest()
        res.append((s, n))
        if worst is None or n > worst[1]:
            worst = (s, n, bad.copy())
    tot = sum(n for _, n in res)
    print("scroll.s simulado (%s): %d frames, s = %d..%d" % (" ".join(a.D) or "base", len(res),
                                                              res[0][0], res[-1][0]))
    print("px de la capa 1 con el color mal: total %d, media %.1f por frame, frames con fallos %d"
          % (tot, tot / len(res), sum(1 for _, n in res if n)))
    for s, n in sorted(res, key=lambda r: -r[1])[:a.top]:
        print("  s = %4d  %5d px" % (s, n))
    if a.ret:
        print("vuelta: px mal %d; imagen igual a la ida en %d de %d frames%s"
              % (back_tot, same, same + len(diff),
                 "" if not diff else "; DISTINTA en s = %s" % " ".join(map(str, diff[:20]))))
    if a.png and worst:
        from PIL import Image
        s, n, bad = worst
        img = np.full((LINES, W, 3), 40, np.uint8)
        img[idx[Y0:Y0 + LINES, s:s + W] > 0] = (120, 120, 120)
        img[bad] = (255, 0, 255)
        Image.fromarray(img).resize((W * 2, LINES * 2), 0).save(a.png)
        print("-> %s (s = %d: capa 1 en gris, fallos en magenta)" % (a.png, s))


if __name__ == "__main__":
    main()
