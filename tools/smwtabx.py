#!/usr/bin/env python3
"""
smwtabx.py - tablas .DB de otros bancos (no el 00) que usa el C del port,
sacadas del fuente por su etiqueta, a player/gen/smwtabx.h (generado, no
se versiona: son bytes de la ROM, R9).

    python tools/smwtabx.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from smwgen import SRC, OUT, parse_tables  # noqa: E402

# (fichero, etiqueta, nombre en C)
WANT = [
    ("sprite_2-clus.s", "SpriteSlotMax", "tx_SpriteSlotMax"),
    ("sprite_2-clus.s", "SpriteSlotMax1", "tx_SpriteSlotMax1"),
    ("sprite_2-clus.s", "SpriteSlotMax2", "tx_SpriteSlotMax2"),
    ("sprite_2-clus.s", "SpriteSlotStart", "tx_SpriteSlotStart"),
    ("sprite_2-clus.s", "SpriteSlotStart1", "tx_SpriteSlotStart1"),
    ("sprite_2-clus.s", "ReservedSprite1", "tx_ReservedSprite1"),
    ("sprite_2-clus.s", "ReservedSprite2", "tx_ReservedSprite2"),
    ("sprite_2-clus.s", "DATA_02A7F6", "tx_02A7F6"),
    ("sprite_2-clus.s", "DATA_02A7F9", "tx_02A7F9"),
    ("sprite_1-main.s", "DATA_019030", "tx_019030"),
    ("sprite_1-main.s", "DATA_01902E", "tx_01902E"),
    ("sprite_1-main.s", "SpriteObjClippingX", "tx_SprObjClipX"),
    ("sprite_1-main.s", "SpriteObjClippingY", "tx_SprObjClipY"),
    ("sprite_1-main.s", "DATA_019134", "tx_019134"),
    ("sprite_1-main.s", "DATA_0192C5", "tx_0192C5"),
    ("sprite_1-main.s", "DATA_0192C7", "tx_0192C7"),
    ("sprite_1-main.s", "DATA_019284", "tx_019284"),
    ("sprite_1-main.s", "DATA_019285", "tx_019285"),
    ("sprite_3-1.s", "RexSpeed", "tx_RexSpeed"),
    ("sprite_3-1.s", "DATA_03B83F", "tx_03B83F"),
    ("sprite_3-1.s", "DATA_03B847", "tx_03B847"),
    ("sprite_3-1.s", "DATA_03B75C", "tx_03B75C"),
    ("sprite_3-1.s", "DATA_03B75E", "tx_03B75E"),
    ("sprite_3-2.s", "DATA_03C1C6", "tx_03C1C6"),
    ("sprite_3-2.s", "DATA_03C1C8", "tx_03C1C8"),
    ("sprite_tables.s", "Sprite1656Vals", "tx_1656"),
    ("sprite_tables.s", "Sprite1662Vals", "tx_1662"),
    ("sprite_tables.s", "Sprite166EVals", "tx_166E"),
    ("sprite_tables.s", "Sprite167AVals", "tx_167A"),
    ("sprite_tables.s", "Sprite1686Vals", "tx_1686"),
    ("sprite_tables.s", "Sprite190FVals", "tx_190F"),
]


def main():
    cache = {}
    with open(os.path.join(OUT, "smwtabx.h"), "w") as f:
        f.write("/* GENERADO por tools/smwtabx.py desde el fuente: no editar ni versionar */\n")
        f.write("#ifndef SMWTABX_H\n#define SMWTABX_H\n")
        for fn, lab, name in WANT:
            if fn not in cache:
                cache[fn] = parse_tables(os.path.join(SRC, fn))
            d = cache[fn].get(lab)
            if not d:
                sys.exit("no encuentro %s en %s" % (lab, fn))
            f.write("static const unsigned char %s[%d] = {%s};\n"
                    % (name, len(d), ",".join(str(b) for b in d)))
        f.write("#endif\n")
    print("smwtabx.h: %d tablas" % len(WANT))


if __name__ == "__main__":
    main()
