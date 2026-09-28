#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
game_check.py - Etapa 6b.5: una captura del juego en modo replay (WinUAE,
game.s -DREPLAY -DSTOPF=F-5145) contra lo que tiene que verse en el frame F:
el fondo del PC para la camara de ese frame (como scroll_check.py --mid) con
Mario encima, dibujado como la SNES desde la OAM que calcula el port
(mario_oam), los tiles de GFX32 que apuntan los punteros de DMA (wm_0D85) y
su paleta (mario_pal, work/cc/mario_pal.bin). El estado sale de correr el
replay en un emulador de 68000 hasta F (como gamecheck.py).

    python3 tools/game_check.py --shot work/g6b/6000.png --frame 6000
"""
import argparse
import os
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import m68kverify as V                          # noqa: E402
import render_d                                 # noqa: E402
import scroll_check as SC                       # noqa: E402

W, LINES = 256, 224


def run_to(frame, binp, lst):
    """el replay de game.bin hasta el frame (del oraculo) dado: (ram, oam, osz, pal)"""
    code = open(binp, "rb").read()
    syms = V.symbols(lst)
    B = V.BASE
    cpu = V.UnicornCPU(False)
    cpu.write(B, code)
    cpu.write(B + syms["_map16_lo"], struct.pack(">I", B + syms["map16"]))
    cpu.write(B + syms["_map16_hi"], struct.pack(">I", B + syms["map16"] + 20 * 0x1B0))
    cpu.write(B + syms["_spr_level"], struct.pack(">I", B + syms["spr_lv"]))
    cpu.write(B + syms["_level_sprites"], b"\x01")
    cpu.call(B + syms["replay_init"], B)
    first = struct.unpack(">H", cpu.read(B + syms["replay"] + 6, 2))[0]
    for _ in range(frame - first + 1):
        cpu.call(B + syms["game_step"], B)
    return (cpu.read(B + syms["_ram"], 0x2000), cpu.read(B + syms["_mario_oam"], 16),
            cpu.read(B + syms["_mario_osz"], 4), cpu.read(B + syms["_mario_pal"], 1)[0])


def mario_pixels(ram, oam, osz, g32):
    """{(x, y) de pantalla SNES: indice de color 1..15}, como la SNES"""
    vram = {}
    for r in range(2):
        for i in range(5):
            o = 0x0D85 + 10 * r + 2 * i
            p = (ram[o] | ram[o + 1] << 8) - 0x2000
            if 0 <= p <= len(g32) - 64:
                vram[16 * r + 2 * i] = g32[p:p + 32]
                vram[16 * r + 2 * i + 1] = g32[p + 32:p + 64]
    p = (ram[0x0D99] | ram[0x0D9A] << 8) - 0x2000
    if 0 <= p <= len(g32) - 32:
        vram[0x7F] = g32[p:p + 32]
    px = {}
    for e in range(3, -1, -1):
        o = oam[4 * e:4 * e + 4]
        if o[1] == 0xF0:
            continue
        sz = 16 if osz[e] & 2 else 8
        ex = o[0] | ((osz[e] & 1) << 8)
        ex = ex - 512 if ex >= 256 else ex
        ey = o[1] - 256 if o[1] >= 0xF0 else o[1]
        for v in range(sz):
            for u in range(sz):
                uu = sz - 1 - u if o[3] & 0x40 else u
                vv = sz - 1 - v if o[3] & 0x80 else v
                t = o[2] + (uu >> 3) + 16 * (vv >> 3)
                if t not in vram:
                    continue
                tl, x, y = vram[t], uu & 7, vv & 7
                c = (((tl[2 * y] >> (7 - x)) & 1) | (((tl[2 * y + 1] >> (7 - x)) & 1) << 1)
                     | (((tl[16 + 2 * y] >> (7 - x)) & 1) << 2) | (((tl[17 + 2 * y] >> (7 - x)) & 1) << 3))
                if c:
                    px[(ex + u, ey + v + 1)] = c        # +1: la SNES, una linea mas abajo
    return px


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", required=True)
    ap.add_argument("--frame", type=int, required=True)
    ap.add_argument("--bin", default=os.path.join(V.WORK, "game.bin"))
    ap.add_argument("--lst", default=os.path.join(V.WORK, "game.lst"))
    ap.add_argument("--origin", default="130,69", help="x0,y0 de la pantalla en la captura (WinUAE)")
    ap.add_argument("--png", default=None)
    a = ap.parse_args()

    ram, oam, osz, pal = run_to(a.frame, a.bin, a.lst)
    cam = ram[0x1A] | ram[0x1B] << 8
    d = render_d.load(os.path.join(V.WORK, "yi1_d.dat"))
    SC.W = W
    e = SC.expect(d, render_d.l1_index(d), cam, True)
    g32 = open(os.path.join(V.WORK, "cc", "gfx32.bin"), "rb").read()
    pals = struct.unpack(">128H", open(os.path.join(V.WORK, "cc", "mario_pal.bin"), "rb").read())
    mp = np.zeros((LINES, W), bool)
    for (x, y), c in mario_pixels(ram, oam, osz, g32).items():
        if 0 <= x < W and 0 <= y < LINES:
            w = pals[16 * (pal & 7) + c]
            e[y, x] = [((w >> 8) & 15) * 17, ((w >> 4) & 15) * 17, (w & 15) * 17]
            mp[y, x] = True
    cap = np.asarray(Image.open(a.shot).convert("RGB")).astype(int)
    x0, y0 = (int(v) for v in a.origin.split(","))
    got = cap[y0 + 1:y0 + 2 * LINES:2, x0 + 1:x0 + 2 * W:2]   # centro de cada pixel x2
    bad = np.abs(got - e).max(axis=2) > 8
    print("frame %d: camara %d, Mario %d px (paleta %d); fallos: fondo %d, Mario %d"
          % (a.frame, cam, mp.sum(), pal, (bad & ~mp).sum(), (bad & mp).sum()))
    if a.png:
        img = np.vstack([e, got, np.where(bad[..., None], [255, 0, 255], got // 2 + 64)])
        Image.fromarray(img.astype(np.uint8)).resize((W * 3, LINES * 9), 0).save(a.png)
        print("-> %s (esperado / captura / fallos en magenta)" % a.png)
    return 1 if bad.any() else 0


if __name__ == "__main__":
    sys.exit(main())
