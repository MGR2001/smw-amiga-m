#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mkdemo.py - genera el blob de datos para el demo en la Amiga.

Formato del blob (big-endian, lo lee el 68000 tal cual):

    +0     16 palabras = 32 B   paleta Amiga 12-bit (COLOR00..COLOR15)
    +32    N bytes              tileset planar, 4 planos, plane-major

El tileset se coloca en una rejilla de COLS columnas x ROWS filas de tiles
de 8x8. El ancho en bytes por linea es COLS y el alto en lineas es ROWS*8,
que es exactamente lo que espera el copper list (BPL1MOD = 0).

FUENTES DE PALETA
-----------------
Las paletas de SMW no son arrays planos: `LoadPalette` (game.s:5039) las
reparte por el CGRAM con offsets y strides.  Por eso este script NO lee
`palettes.a` directamente, sino que emula `LoadPalette` con `palette.py` y
elige la paleta ya reconstruida:

    --pal cgram:N   paleta N (0-15) del CGRAM reconstruido
    --pal mario     paleta de sprites 0 con los colores de Mario en $87
    --pal luigi     idem con Luigi
    --pal raw:NAME  blob plano de palettes.a (modo legado/debug)

Uso:
    python mkdemo.py --gfx chr --pal mario --out ../work/demo.dat
    python mkdemo.py --gfx obj-3 --pal cgram:5
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smw2amiga import (lc_lz2_decompress, decode_snes_tileset,
                       snes_word_to_amiga12, parse_palette_file, BPP_TABLE,
                       _DEF_SRC)
from palette import (load_palette_bank, build_cgram, cgram_palette,
                     snes_to_rgb8)

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEF_OUT = os.path.normpath(os.path.join(_HERE, "..", "work", "demo.dat"))

# Paletas del jugador (palettes.a:70-73)
PLAYER_PALS = {
    "mario":     [0x635F, 0x581D, 0x000A, 0x391F, 0x44C4,
                  0x4E08, 0x6770, 0x30B6, 0x35DF, 0x03FF],
    "luigi":     [0x4F3F, 0x581D, 0x1140, 0x3FE0, 0x3C07,
                  0x7CAE, 0x7DB3, 0x2F00, 0x165F, 0x03FF],
    "mariofire": [0x635F, 0x581D, 0x2529, 0x7FFF, 0x0008,
                  0x0017, 0x001F, 0x577B, 0x0DDF, 0x03FF],
    "luigifire": [0x3B1F, 0x581D, 0x2529, 0x7FFF, 0x1140,
                  0x01E0, 0x02E0, 0x577B, 0x0DDF, 0x03FF],
}
# CODE_00B03E (game.s:5527) copia la paleta del jugador a wm_PaletteCopy
# desde el color 135 (= CGRAM $87).  El sprite usa la paleta de sprites 0
# (colores 128-143), asi que la vista de 16 colores es la 8 con el jugador
# superpuesto en 135.
PLAYER_CGRAM_BASE = 135


def build_player_palette(cgram, which):
    """16 colores tal como los ve el sprite del jugador."""
    cg = list(cgram)
    for i, w in enumerate(PLAYER_PALS[which]):
        cg[PLAYER_CGRAM_BASE + i] = w
    return cg[128:144]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_DEF_SRC)
    ap.add_argument("--gfx", default="chr")
    ap.add_argument("--pal", default="mario",
                    help="cgram:N | mario | luigi | mariofire | luigifire | raw:NAME")
    ap.add_argument("--level", default="3340088027",
                    help="header de nivel en hex (define fg/bg/spr pal y bgcol)")
    ap.add_argument("--cols", type=int, default=40)
    ap.add_argument("--rows", type=int, default=32)
    ap.add_argument("--planes", type=int, default=4)
    ap.add_argument("--out", default=_DEF_OUT)
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    out = os.path.abspath(args.out)

    if args.gfx not in BPP_TABLE:
        sys.exit("gfx desconocido: %s" % args.gfx)
    bpp = BPP_TABLE[args.gfx]
    raw = open(os.path.join(src, "graphics", args.gfx + ".lz2"), "rb").read()
    dec = lc_lz2_decompress(raw)
    tiles = decode_snes_tileset(dec, bpp)
    print("%s: %d tiles de %d bpp  (lz2 %d B -> raw %d B)"
          % (args.gfx, len(tiles), bpp, len(raw), len(dec)))

    cols, rows, planes = args.cols, args.rows, args.planes
    w = cols                      # bytes por linea (8 px por byte)
    h = rows * 8                  # lineas
    plane_size = h * w
    buf = bytearray(plane_size * planes)

    mask = (1 << planes) - 1
    placed = 0
    for idx, tile in enumerate(tiles):
        if idx >= cols * rows:
            break
        tx = (idx % cols) * 8
        ty = (idx // cols) * 8
        for y in range(8):
            for x in range(8):
                v = tile[y][x] & mask
                for p in range(planes):
                    if (v >> p) & 1:
                        off = p * plane_size + (ty + y) * w + (tx + x) // 8
                        buf[off] |= 0x80 >> ((tx + x) % 8)
        placed += 1

    # --- paleta ------------------------------------------------------------
    hdr = bytes.fromhex(args.level)
    fgpal, bgpal = hdr[3] & 0x07, hdr[0] >> 5
    sprpal, bgcol = (hdr[3] >> 3) & 0x07, hdr[1] >> 5

    pal_desc = args.pal
    if args.pal.startswith("raw:"):
        pals = parse_palette_file(os.path.join(src, "palettes", "palettes.a"))
        words = pals.get(args.pal[4:], [])[:1 << planes]
        if len(words) < (1 << planes):
            sys.exit("la paleta %s tiene solo %d colores" % (args.pal[4:], len(words)))
        pal_desc = "raw %s" % args.pal[4:]
    else:
        bank, labels = load_palette_bank(
            os.path.join(src, "palettes", "palettes.a"))
        cgram, bg_color = build_cgram(bank, labels, fgpal, bgpal, sprpal, bgcol)
        print("CGRAM: FgPal=%d BgPal=%d SprPal=%d BgCol=%d  fondo=$%04X rgb%s"
              % (fgpal, bgpal, sprpal, bgcol, bg_color, snes_to_rgb8(bg_color)))
        if args.pal.startswith("cgram:"):
            n = int(args.pal[6:])
            words = cgram_palette(cgram, n)
            pal_desc = "CGRAM paleta %d" % n
        elif args.pal in PLAYER_PALS:
            words = build_player_palette(cgram, args.pal)
            pal_desc = "jugador %s (CGRAM $%02X)" % (args.pal, PLAYER_CGRAM_BASE)
        else:
            sys.exit("--pal invalido: %s" % args.pal)

    words = words[:1 << planes]
    if len(words) < (1 << planes):
        words = words + [0] * ((1 << planes) - len(words))
    pal = b"".join(struct.pack(">H", snes_word_to_amiga12(x)) for x in words)

    blob = pal + bytes(buf)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "wb").write(blob)

    print("pantalla    : %d x %d px, %d planos (%d colores)"
          % (cols * 8, h, planes, 1 << planes))
    print("tiles       : %d de %d colocados" % (placed, cols * rows))
    print("plano       : %d B, total %d B" % (plane_size, len(buf)))
    print("paleta      : %s" % pal_desc)
    print("colores     : " + " ".join("%03X" % snes_word_to_amiga12(x)
                                      for x in words))
    print("blob        : %s  (%d bytes)" % (out, len(blob)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
