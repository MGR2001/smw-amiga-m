#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mkmario.py - Etapa 6b.4: los datos de Mario para player/game.s (derivados
del ROM y de los fuentes: van a work/cc/, no a git, R9).

  work/cc/gfx32.bin     GFX32 (graphics/chr.lz2) descomprimido: lo que la
                        SNES tiene en $7E:2000 y de donde copia los tiles de
                        Mario por DMA (player/mspr.c)
  work/cc/gfx32f.bin    lo mismo con los bits de cada byte al reves: los tiles
                        volteados en horizontal (player/mspr68k.s)
  work/cc/mario_pal.bin 8 paletas x 16 colores OCS (0x0RGB), una por indice
                        de DATA_00E2A2 (mgfx.c: mario_pal). El color k es el
                        de la paleta 0 de sprites de la SNES (CGRAM 128 + k)
                        con la del jugador copiada desde el 135 (P10); en la
                        Amiga va a COLOR16 + k (sprites adosados)

    python3 tools/mkmario.py
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from smw2amiga import lc_lz2_decompress, _DEF_SRC              # noqa: E402
from palette import load_palette_bank, build_cgram, snes_to_amiga12   # noqa: E402

WORK = os.path.join(HERE, "..", "work")
ROM = os.path.join(HERE, "..", "..", "smwre", "smw.sfc")
LEVEL = "3340088027"            # header de Yoshi's Island 1 (obj.lv)
DATA_00E2A2 = 0xE2A2            # 8 punteros (banco 0) a paletas de 10 colores
PLAYER_CGRAM_BASE = 135


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_DEF_SRC)
    ap.add_argument("--rom", default=ROM)
    ap.add_argument("--level", default=LEVEL)
    a = ap.parse_args()
    out = os.path.join(WORK, "cc")
    os.makedirs(out, exist_ok=True)

    g = lc_lz2_decompress(open(os.path.join(a.src, "graphics", "chr.lz2"), "rb").read())
    open(os.path.join(out, "gfx32.bin"), "wb").write(g)
    rev = bytes(int("{:08b}".format(i)[::-1], 2) for i in range(256))
    open(os.path.join(out, "gfx32f.bin"), "wb").write(bytes(rev[b] for b in g))

    rom = open(a.rom, "rb").read()
    hdr = len(rom) % 1024                       # copiador: 512 bytes delante

    def r16(adr):                               # banco 0 (LoROM)
        o = hdr + (adr & 0x7FFF)
        return rom[o] | rom[o + 1] << 8

    h = bytes.fromhex(a.level)
    bank, labels = load_palette_bank(os.path.join(a.src, "palettes", "palettes.a"))
    cgram, _ = build_cgram(bank, labels, h[3] & 0x07, h[0] >> 5, (h[3] >> 3) & 0x07, h[1] >> 5)
    pals = b""
    for i in range(8):
        p = r16(DATA_00E2A2 + 2 * i)
        cg = list(cgram)
        for k in range(10):
            cg[PLAYER_CGRAM_BASE + k] = r16(p + 2 * k)
        pals += struct.pack(">16H", *[snes_to_amiga12(w) for w in cg[128:144]])
    open(os.path.join(out, "mario_pal.bin"), "wb").write(pals)
    print("gfx32.bin: %d bytes; mario_pal.bin: 8 paletas" % len(g))


if __name__ == "__main__":
    main()
