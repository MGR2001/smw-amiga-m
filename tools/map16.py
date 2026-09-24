#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
map16.py - Tablas Map16 de Super Mario World.

El buffer `wm_Map16BlkPtrL/H` NO guarda tile numbers: guarda **indices Map16**
(por eso se llama "Map16 block"). Cada indice se resuelve a 4 palabras
(cuadrantes 8x8, en orden TL, TR, BL, BR) con el formato del tilemap:

    bits 0-9   tile number de VRAM (0..1023)
    bits 10-12 paleta (0..7)
    bit  13    prioridad
    bit  14    flip X
    bit  15    flip Y

Estructura de las tablas (project/mw_e10/tilemaps/):

  Comunes a todos los tilesets:
      000-072.bin  0x000..0x072  (115 entradas)
      100-106.bin  0x100..0x106  (  7)
      111-152.bin  0x111..0x152  ( 66)
      16E-1C3.bin  0x16E..0x1C3  ( 86)
      1C4-1C7.bin  0x1C4..0x1C7  (  4)
      1C8-1EB.bin  0x1C8..0x1EB  ( 36)
      1EC-1EF.bin  0x1EC..0x1EF  (  4)
      1F0-1FF.bin  0x1F0..0x1FF  ( 16)

  Especificas del estilo (set_0..set_4):
      set_N/073-0FF.bin  0x073..0x0FF (141)
      set_N/107-110.bin  0x107..0x110 ( 10)
      set_N/153-16D.bin  0x153..0x16D ( 27)

  Sustituciones que hace el ROM al cargar el nivel (lv_read.s):

    * Tilesets 0 y 7 (lv_read.s:283): $1C4-$1C7 y $1EC-$1EF se reapuntan a
      DATA_0D8A70 = 1C4-1C7_2.bin + 1EC-1EF_2.bin (bocas de tuberia diagonal;
      las tablas "normales" son pendientes de tierra).
    * Tuberias $133-$13A (MAP16AppTable, lv_read.s:805): al subir la columna
      c se elige la variante (c >> 4) & 3 = PANTALLA & 3.  Cada variante es
      la misma tuberia con otra paleta:
          pantalla&3 = 0 -> pipes/1.bin      paleta 3
                       1 -> 111-152.bin      paleta 5 (verde)
                       2 -> pipes/2.bin      paleta 6
                       3 -> pipes/3.bin      paleta 7 (lavanda)
      Por eso en Yoshi's Island 1 las tuberias de la pantalla 7 son lavanda
      (esto cierra la decision D7).  Usar get(idx, screen).

  Los indices >= 0x200 son los especificos del tileset y viven en el banco
  que da TilesetMAP16Loc (lv_read.s). No se usan en Yoshi's Island 1.

Cada entrada son 8 bytes = 4 palabras little-endian.
"""

import os
import struct

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEF_SRC = os.path.normpath(os.path.join(_HERE, "..", "..", "smw-src-master", "project", "mw_e10"))

COMMON_RANGES = [
    ("000-072.bin", 0x000),
    ("100-106.bin", 0x100),
    ("111-152.bin", 0x111),
    ("16E-1C3.bin", 0x16E),
    ("1C4-1C7.bin", 0x1C4),
    ("1C8-1EB.bin", 0x1C8),
    ("1EC-1EF.bin", 0x1EC),
    ("1F0-1FF.bin", 0x1F0),
]

SET_RANGES = [
    ("073-0FF.bin", 0x073),
    ("107-110.bin", 0x107),
    ("153-16D.bin", 0x153),
]

# Tileset -> set de tablas Map16.
# Fuente: TilesetMAP16Loc (lv_read.s) agrupado por estilo. Los 5 sets de
# tilemaps/set_N corresponden a los 5 estilos de nivel.
# Tilesets que reapuntan $1C4-$1C7/$1EC-$1EF a las tablas _2 (lv_read.s:283)
ALT_1C4_TILESETS = (0, 7)
ALT_1C4_FILES = [("1C4-1C7_2.bin", 0x1C4), ("1EC-1EF_2.bin", 0x1EC)]

# MAP16AppTable: variante de tuberia por (pantalla & 3).  None = la comun.
PIPE_FIRST, PIPE_COUNT = 0x133, 8
PIPE_VARIANTS = ["pipes/1.bin", None, "pipes/2.bin", "pipes/3.bin"]

TILESET_SET = {
    0: 0,   # Normal 1
    1: 1,   # Castle 1
    2: 2,   # Rope 1
    3: 3,   # Underground 1
    4: 4,   # Switch Palace 1
    5: 4,   # Ghost House 1
    6: 2,   # Rope 2
    7: 0,   # Normal 2   <-- Yoshi's Island
    8: 2,   # Rope 3
    9: 3,   # Underground 2
    10: 3,  # Switch Palace 2
    11: 3,  # Castle 2
    12: 0,  # Cloud/Forest
    13: 4,  # Ghost House 2
    14: 3,  # Underground 3
}


def decode_word(w):
    """Palabra del tilemap -> (tile, paleta, prioridad, xflip, yflip)."""
    return (w & 0x3FF, (w >> 10) & 0x07, (w >> 13) & 0x01,
            (w >> 14) & 0x01, (w >> 15) & 0x01)


class Map16:
    def __init__(self, src=None, set_index=0, tileset=None):
        """`tileset` activa las sustituciones que hace el ROM para ese
        tileset (ver cabecera).  Sin tileset quedan las tablas crudas."""
        src = src or os.path.join(_DEF_SRC, "tilemaps")
        self.entries = {}
        self.raw = {}
        self.ranges = []
        for name, base in COMMON_RANGES:
            self._load(os.path.join(src, name), base)
        for name, base in SET_RANGES:
            self._load(os.path.join(src, "set_%d" % set_index, name), base)
        if tileset in ALT_1C4_TILESETS:
            for name, base in ALT_1C4_FILES:
                self._load(os.path.join(src, name), base)
        # variantes de tuberia: [(entries, raw)] indexado por pantalla & 3
        self.pipes = []
        for name in PIPE_VARIANTS:
            if name is None:
                ids = range(PIPE_FIRST, PIPE_FIRST + PIPE_COUNT)
                self.pipes.append(({i: self.entries[i] for i in ids},
                                   {i: self.raw[i] for i in ids}))
                continue
            raw = open(os.path.join(src, name), "rb").read()
            ent, rw = {}, {}
            for i in range(PIPE_COUNT):
                q = struct.unpack_from("<4H", raw, i * 8)
                ent[PIPE_FIRST + i] = [decode_word(w) for w in q]
                rw[PIPE_FIRST + i] = list(q)
            self.pipes.append((ent, rw))

    def _load(self, path, base):
        if not os.path.exists(path):
            return
        raw = open(path, "rb").read()
        n = len(raw) // 8
        for i in range(n):
            q = struct.unpack_from("<4H", raw, i * 8)
            self.entries[base + i] = [decode_word(w) for w in q]
            self.raw[base + i] = list(q)
        self.ranges.append((os.path.basename(path), base, n))

    def get(self, idx, screen=None):
        """Indice Map16 -> lista de 4 (tile, pal, prio, xf, yf). None si falta.
        Con `screen`, las tuberias $133-$13A usan la variante de esa pantalla
        (MAP16AppTable).  Sin `screen` se devuelve la comun (verde)."""
        if screen is not None and idx in self.pipes[screen & 3][0]:
            return self.pipes[screen & 3][0][idx]
        return self.entries.get(idx)

    def get_raw(self, idx, screen=None):
        """Indice Map16 -> las 4 palabras crudas.

        OJO: un cuadrante vacio se codifica con la palabra $0000.  NO se puede
        usar `tile == 0` para detectar el vacio, porque el tile number 0 es un
        tile valido (p.ej. la boquilla de tuberia usa el tile 0 a paleta 5,
        palabra $1400).  Hay que mirar la palabra entera.
        """
        if screen is not None and idx in self.pipes[screen & 3][1]:
            return self.pipes[screen & 3][1][idx]
        return self.raw.get(idx)

    def summary(self):
        return " ".join("%s:$%03X+%d" % (n, b, c) for n, b, c in self.ranges)


if __name__ == "__main__":
    import sys
    for s in range(5):
        m = Map16(set_index=s)
        print("set_%d: %d entradas" % (s, len(m.entries)))
    m = Map16(set_index=TILESET_SET[7])
    print()
    print("tileset 7 -> set_%d" % TILESET_SET[7])
    for idx in (0x02, 0x03, 0x13, 0x1E, 0x21, 0x23, 0x2A, 0x2B, 0x3F,
                0x65, 0x6B, 0x73, 0x74, 0x79):
        e = m.get(idx)
        if e is None:
            print("  $%03X: (no existe)" % idx)
            continue
        print("  $%03X: %s" % (idx, " | ".join(
            "t=%3d p=%d %s%s%s" % (t, p, 'X' if xf else '.', 'Y' if yf else '.',
                                   'P' if pr else '.')
            for t, p, pr, xf, yf in e)))
