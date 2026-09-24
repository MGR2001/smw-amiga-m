#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mkbg.py - la capa 2 (el fondo) de un nivel, sacada de los datos del ROM (via
el fuente), sin la imagen de referencia.

Como la carga el juego (lv_read.s:CODE_05801E / CODE_058126):
  - Layer2Ptrs[nivel] con banco $FF = fondo "de tiles" (los niveles
    normales). Los datos estan en Layer2BGBank ($0C) a la misma direccion:
    levels/data/bg/<nombre>.bg (levels/bg.a).
  - RLE: byte b; si b & $80, (b & $7F) + 1 copias del byte siguiente; si
    no, b + 1 bytes literales. Termina en $FF $FF. Sale 2 pantallas de
    27 x 16 bloques ($1B0 bytes cada una): el fondo se repite cada 512 px.
  - La pagina (byte alto) es 0 para los fondos anteriores a Layer2Cave en
    el ROM y 1 para el resto. Yoshi's Island 1 = Layer2Mountains, pagina 0.
  - Cada bloque se resuelve con la tabla Map16 de FONDOS, DATA_0D9100 =
    tilemaps/background.bin (512 entradas de 8 bytes, 4 palabras en orden
    de columnas como las del nivel, P12), con los mismos GFX y CGRAM que la
    capa 1 (paletas de BG 0-1 = PALETTE_Background + BgPal, §8b).

    python tools/mkbg.py [--bg mountains] [--out work/bg.png] [--level work/level_l1l2.png]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mklvl                                    # noqa: E402
from lvparse import _DEF_SRC                    # noqa: E402

SCR = 0x1B0
QUAD = [(0, 0), (8, 0), (0, 8), (8, 8)]         # TL, TR, BL, BR
ORDER = [0, 2, 1, 3]                            # palabras en orden de columnas (P12)

# orden de los .bg en el ROM (levels/bg.a): los anteriores a Layer2Cave van
# en la pagina 0, el resto en la 1 (CODE_05801E: CPX #Layer2Cave)
BG_ORDER = ["mountains", "water", "cloudy_hills", "clouds", "small_hills", "rocky-2",
            "castle-2", "large_hills", "bonus", "stars", "rocky-1", "black", "cave",
            "forest", "ghost_house", "ghost_ship", "castle-1"]


def decode_bg(data):
    """RLE de CODE_058126 -> bytes (indices Map16, byte bajo)"""
    out = bytearray()
    i = 0
    while not (data[i] == 0xFF and data[i + 1] == 0xFF):
        b = data[i]
        i += 1
        if b & 0x80:
            out += bytes([data[i]]) * ((b & 0x7F) + 1)
            i += 1
        else:
            out += data[i:i + b + 1]
            i += b + 1
    return bytes(out)


def bg_map16(src):
    """background.bin -> lista de 512 entradas de 4 palabras"""
    d = open(os.path.join(src, "tilemaps", "background.bin"), "rb").read()
    return [[d[k * 8 + 2 * q] | d[k * 8 + 2 * q + 1] << 8 for q in range(4)]
            for k in range(len(d) // 8)]


def render_bg(name, h, out_png=None):
    """devuelve (img RGBA de 512 x 432, transparente donde no hay tile, color de cielo)"""
    from PIL import Image
    import palette as palmod
    src = _DEF_SRC
    data = open(os.path.join(src, "levels", "data", "bg", name + ".bg"), "rb").read()
    cells = decode_bg(data)
    page = 0 if BG_ORDER.index(name) < BG_ORDER.index("cave") else 1
    m16 = bg_map16(src)
    files = mklvl.gfx_files_for_tileset(h["tileset"])
    gfx = mklvl.load_gfx(os.path.join(src, "graphics"), files)
    bank, labels = palmod.load_palette_bank(os.path.join(src, "palettes", "palettes.a"))
    cgram, bgc = palmod.build_cgram(bank, labels, h["fg_palette"], h["bg_palette"],
                                    h["spr_palette"], h["bg_color"], mklvl.COIN_ANIM_REF)
    pals = [[palmod.snes_to_rgb8(c) for c in cgram[p * 16:p * 16 + 16]] for p in range(8)]
    screens = len(cells) // SCR
    W, H = screens * 256, 27 * 16
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load()
    for s in range(screens):
        for r in range(27):
            for c in range(16):
                idx = cells[s * SCR + r * 16 + c] | (page << 8)
                words = m16[idx]
                for (qx, qy), w in zip(QUAD, [words[i] for i in ORDER]):
                    if w == 0:
                        continue
                    tile10, pal = w & 0x3FF, (w >> 10) & 7
                    xf, yf = (w >> 14) & 1, (w >> 15) & 1
                    blk, within = tile10 // 128, tile10 % 128
                    if blk >= len(files):
                        continue
                    t = gfx[files[blk]][within]
                    for y in range(8):
                        row = t[7 - y] if yf else t[y]
                        for x in range(8):
                            v = row[7 - x] if xf else row[x]
                            if v:
                                px[s * 256 + c * 16 + qx + x, r * 16 + qy + y] = \
                                    pals[pal][v & 0x0F] + (255,)
    if out_png:
        full = Image.new("RGB", (W, H), palmod.snes_to_rgb8(bgc))
        full.paste(img, (0, 0), img)
        full.save(out_png)
    return img, palmod.snes_to_rgb8(bgc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lv", default=os.path.join(_DEF_SRC, "levels", "data", "world_1", "1", "obj.lv"))
    ap.add_argument("--bg", default="mountains")
    ap.add_argument("--out", default=os.path.join(HERE, "..", "work", "bg_mountains.png"))
    ap.add_argument("--level", default=os.path.join(HERE, "..", "work", "level_l1l2.png"),
                    help="compuesto capa 2 (repetida cada 512 px) + capa 1")
    a = ap.parse_args()
    from PIL import Image
    h, objs, lv = mklvl.build(a.lv, verbose=False)
    bg, sky = render_bg(a.bg, h, a.out)
    print("fondo %s -> %s (%dx%d)" % (a.bg, a.out, bg.size[0], bg.size[1]))
    if a.level:
        l1 = os.path.join(HERE, "..", "work", "level_final.png")
        if not os.path.exists(l1):
            mklvl.render(h, lv, l1)
        fg = Image.open(l1).convert("RGB")
        W, H = fg.size
        comp = Image.new("RGB", (W, H), sky)
        for x in range(0, W, bg.size[0]):
            comp.paste(bg, (x, 0), bg)
        # la capa 1: todo lo que no es el color de cielo del render
        mask = Image.eval(fg.convert("RGB"), lambda v: v)
        fgp, cp = fg.load(), comp.load()
        for y in range(H):
            for x in range(W):
                if fgp[x, y] != sky:
                    cp[x, y] = fgp[x, y]
        comp.save(a.level)
        print("capa 2 + capa 1 -> %s (%dx%d)" % (a.level, W, H))


if __name__ == "__main__":
    main()
