#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mklvl.py - Convierte un nivel de SMW en un tilemap renderizable.

Flujo:
    1. lvparse.py decodifica los objetos del .lv
    2. se ejecutan los handlers (transcritos de tiles.s) que escriben tiles
       en un buffer de palabras Map16 de (pantallas x 27 x 16)
    3. cada tile number (10 bits) se resuelve a (fichero GFX, tile dentro del
       fichero) usando OBJECTGFXLIST del tileset
    4. se renderiza con la paleta del CGRAM reconstruida (palette.py)

MAPA DE VRAM (game.s:UploadSpriteGFX / el bucle de subida de layer)
    Los 4 primeros bytes de OBJECTGFXLIST[tileset] son ficheros GFX; cada uno
    sube 128 tiles a un bloque de $800 palabras de VRAM:

        bloque 0  VRAM $0000  tiles   0..127   <- OBJECTGFXLIST[t*4 + 0]
        bloque 1  VRAM $0800  tiles 128..255   <- OBJECTGFXLIST[t*4 + 1]
        bloque 2  VRAM $1000  tiles 256..383   <- OBJECTGFXLIST[t*4 + 2]
        bloque 3  VRAM $1800  tiles 384..511   <- OBJECTGFXLIST[t*4 + 3]

    (el orden es invertido respecto a la lista porque el bucle usa
     `LDA OBJECTGFXLIST,Y / STA m4,X` con X de 3 a 0)

    El buffer Map16 guarda el WORD del tilemap:
        bits 0-9   tile number (10 bits)
        bits 10-12 paleta
        bit  13    prioridad
        bit  14    flip X
        bit  15    flip Y
    Los handlers escriben el byte bajo con CODE_0DA95B (buffer L) y el byte
    alto con BlockIsPage1/2 (buffer H).

Uso:
    python mklvl.py [--lv fichero] [--out png] [--scale N] [--pal 0..7]
"""

import argparse
import collections
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lvparse import (parse_header, decode_stream, _DEF_SRC, LEVEL_ROWS,
                     TILES_PER_SCREEN_W)
from smw2amiga import lc_lz2_decompress, decode_snes_tileset, BPP_TABLE

# ---------------------------------------------------------------------------
# main.S:96-168 -> indice GFX -> fichero
# ---------------------------------------------------------------------------
GFX_TABLE = [
    "spr-1", "spr-2", "spr-3", "spr-4", "spr-5", "spr-6", "spr-7", "obj-1",
    "map-1", "spr-8", "boss-1", "boss-2", "bg-1", "cin-1", "spr-9", "cin-2",
    "map-2", "spr-10", "spr-11", "spr-12", "obj-2", "obj-3", "obj-4", "obj-5",
    "obj-6", "bg-2", "obj-7", "bg-3", "map-3", "map-4", "map-5", "obj-8",
    "spr-13", "boss-3", "cin-3", "spr-14", "boss-4", "boss-5", "cin-4",
    "boss-6", "gb-1", "gb-2", "gb-3", "gb-4", "cin-5", "cin-6", "cin-7",
    "gb-5", "cin-8", "spr-15",
]
GFX_CHR = "chr"
GFX_ANIM = "anim"

# game.s:4721 OBJECTGFXLIST (13 filas x 8 bytes, pero se indexa como lista
# plana con Y = tileset*4)
OBJECTGFXLIST = [
    0x14, 0x17, 0x19, 0x15, 0x14, 0x17, 0x1B, 0x18,
    0x14, 0x17, 0x1B, 0x16, 0x14, 0x17, 0x0C, 0x1A,
    0x14, 0x17, 0x1B, 0x08, 0x14, 0x17, 0x0C, 0x07,
    0x14, 0x17, 0x0C, 0x16, 0x14, 0x17, 0x1B, 0x15,
    0x14, 0x17, 0x19, 0x16, 0x14, 0x17, 0x0D, 0x1A,
    0x14, 0x17, 0x1B, 0x08, 0x14, 0x17, 0x1B, 0x18,
    0x14, 0x17, 0x19, 0x1F, 0x14, 0x17, 0x0D, 0x07,
    0x14, 0x17, 0x19, 0x1A, 0x14, 0x17, 0x14, 0x14,
    0x0E, 0x0F, 0x17, 0x17, 0x1C, 0x1D, 0x08, 0x1E,
    0x1C, 0x1D, 0x08, 0x1E, 0x1C, 0x1D, 0x08, 0x1E,
    0x1C, 0x1D, 0x08, 0x1E, 0x1C, 0x1D, 0x08, 0x1E,
    0x1C, 0x1D, 0x08, 0x1E, 0x1C, 0x1D, 0x08, 0x1E,
    0x14, 0x17, 0x19, 0x2C, 0x19, 0x17, 0x1B, 0x18,
]


def gfx_files_for_tileset(t):
    """Devuelve [fichero_bloque0, ..., fichero_bloque3] para un tileset."""
    y = t * 4
    if y + 4 > len(OBJECTGFXLIST):
        return None
    return [GFX_TABLE[OBJECTGFXLIST[y + i]] for i in range(4)]


# ---------------------------------------------------------------------------
# Tablas de tiles de los handlers (tiles.s)
# ---------------------------------------------------------------------------
DATA_0DA8B4 = [0x02, 0x21, 0x23, 0x2A, 0x2B, 0x3F, 0x03, 0x13,
               0x1E, 0x24, 0x2E, 0x2F, 0x30, 0x32, 0x65]

DATA_0DAA12 = [0x33, 0x37, 0x39, 0x00, 0x00]
DATA_0DAA17 = [0x34, 0x38, 0x3A, 0x00, 0x00]
DATA_0DAA1C = [0x00, 0x00, 0x39, 0x33, 0x37]
DATA_0DAA21 = [0x00, 0x00, 0x3A, 0x34, 0x38]

DATA_0DB039 = [0x40, 0x41, 0x06, 0x45, 0x4B, 0x48, 0x4C, 0x01,
               0x03, 0xB6, 0xB7, 0x45, 0x4B, 0x48, 0x4C]
DATA_0DB048 = [0x40, 0x41, 0x06, 0x4B, 0x4B, 0x4C, 0x4C, 0x40,
               0x41, 0x4B, 0x4C, 0x4B, 0x4B, 0x4C, 0x4C]
DATA_0DB057 = [0x40, 0x41, 0x06, 0x4B, 0x4B, 0x4C, 0x4C, 0x40,
               0x41, 0x4B, 0x4C, 0x4B, 0x4B, 0x4C, 0x4C]
DATA_0DB066 = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
               0xFF, 0xFF, 0xFF, 0xE2, 0xE2, 0xE4, 0xE4]

# Tablas de mezcla de CODE_0DB114 (tope) y CODE_0DB198 (cuerpo) del Ledge edge
DATA_0DB0F0 = [0x7D, 0x7E, 0x82, 0x83, 0x9B, 0x9C, 0xA0, 0xA1,
               0xAA, 0xAB, 0xAF, 0xB0, 0xD8, 0xDC, 0xDE, 0xE0,
               0xE2, 0xE4]
DATA_0DB102 = [0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF,
               0xC0, 0xC1, 0xC2, 0xC3, 0xD9, 0xDD, 0xDF, 0xE1,
               0xE3, 0xE5]
DATA_0DB15C = [0x6E, 0x6F, 0x73, 0x74, 0x78, 0x79, 0x7D, 0x7E,
               0x82, 0x83, 0x87, 0x88, 0x8C, 0x8D, 0x91, 0x92,
               0x96, 0x97, 0x9B, 0x9C, 0xA0, 0xA1, 0xA5, 0xA6,
               0xAA, 0xAB, 0xAF, 0xB0, 0xE2, 0xE4]
DATA_0DB17A = [0x70, 0x70, 0x75, 0x75, 0x7A, 0x7A, 0x7F, 0x7F,
               0x84, 0x84, 0x89, 0x89, 0x8E, 0x8E, 0x93, 0x93,
               0x98, 0x98, 0x9D, 0x9D, 0xA2, 0xA2, 0xA7, 0xA7,
               0xAC, 0xAC, 0xB1, 0xB1, 0xE9, 0xEA]

DATA_0DB5A8 = [0x73, 0x7A, 0x85, 0x88, 0xC3]
DATA_0DB5AD = [0x74, 0x7B, 0x86, 0x89, 0xC3]
DATA_0DB5B2 = [0x79, 0x80, 0x87, 0x8E, 0xC3]

DATA_0DB5E8 = [0x07, 0x0A, 0x0A, 0x08, 0x0A, 0x0A, 0x09,
               0x81, 0x82, 0x83, 0x81, 0x82, 0x83, 0x81,
               0x81, 0x25, 0x84, 0x81, 0x25, 0x84, 0x81,
               0x81, 0x25, 0x84, 0x81, 0x25, 0x84, 0x81]

# Tabla DATA_0DA548: objeto extendido (0x10..0x42) -> tile number
DATA_0DA548 = [
    0x1F, 0x22, 0x24, 0x42, 0x43, 0x27, 0x29, 0x25,
    0x6E, 0x6F, 0x70, 0x71, 0x72, 0x45, 0x46, 0x47,
    0x48, 0x36, 0x37, 0x11, 0x12, 0x14, 0x15, 0x16,
    0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x29, 0x1D,
    0x1F, 0x20, 0x21, 0x22, 0x23, 0x25, 0x26, 0x27,
    0x28, 0x2A, 0xDE, 0xE0, 0xE2, 0xE4, 0xEC, 0xED,
    0x2C, 0x25, 0x2D,
]


class Level:
    """Buffer Map16 del nivel: palabras de 16 bits (tile + paleta + flips)."""

    def __init__(self, ns):
        self.ns = ns
        self.W = ns * TILES_PER_SCREEN_W
        self.H = LEVEL_ROWS
        self.M = [0] * (self.W * self.H)
        self.placed = 0
        self.skipped = []

    def put(self, gx, gy, tile, page=0, pal=0, prio=0, xf=0, yf=0):
        """page=None: no se llamo a BlockIsPage1/2, asi que la celda CONSERVA
        el byte alto que ya tenia (0 si estaba vacia).  BlockIsPage1/2 no son
        un "modo": escriben el byte alto en la celda actual."""
        if gx < 0 or gx >= self.W or gy < 0 or gy >= self.H:
            return
        if page is None:
            old = self.M[gy * self.W + gx]
            page = (old >> 8) & 1
        word = (tile & 0xFF) | ((page & 1) << 8) | ((pal & 7) << 10) \
            | ((prio & 1) << 13) | ((xf & 1) << 14) | ((yf & 1) << 15)
        self.M[gy * self.W + gx] = word
        self.placed += 1

    def get(self, gx, gy):
        if gx < 0 or gx >= self.W or gy < 0 or gy >= self.H:
            return None
        return self.M[gy * self.W + gx]


# ---------------------------------------------------------------------------
# Handlers. Transcritos de tiles.s. Devuelven True si se implementaron.
# ---------------------------------------------------------------------------

def h_generic_rect(lv, o):
    """Objetos 0x01..0x0E -> CODE_0DA8C3.
    Rectangulo (w+1) x (h+1) del tile DATA_0DA8B4[num-1].
    Si idx >= 7 el tile va a la pagina 2 (tile += 256)."""
    idx = o["num"] - 1
    if not (0 <= idx < len(DATA_0DA8B4)):
        return False
    t = DATA_0DA8B4[idx]
    page = 1 if idx >= 7 else 0
    for j in range(o["h"] + 1):
        for i in range(o["w"] + 1):
            lv.put(o["gx"] + i, o["gy"] + j, t, page)
    return True


def h_vertical_pipe(lv, o):
    """Objeto 0x0F Vertical pipes -> CODE_0DAA26.  {Height},{Type}"""
    hh, ty = o["h"], o["w"]
    gx, gy = o["gx"], o["gy"]
    if ty >= len(DATA_0DAA12):
        return False

    def top():
        if ty < 3:
            lv.put(gx, gy, DATA_0DAA12[ty], 1)
            lv.put(gx + 1, gy, DATA_0DAA17[ty], 1)
        elif ty == 5:
            lv.put(gx, gy, 0x68, 1)
            lv.put(gx + 1, gy, 0x69, 1)
        else:
            lv.put(gx, gy, 0x35, 1)
            lv.put(gx + 1, gy, 0x36, 1)

    def body(y):
        if ty == 5:
            lv.put(gx, y, 0x68, 1)
            lv.put(gx + 1, y, 0x69, 1)
        else:
            lv.put(gx, y, 0x35, 1)
            lv.put(gx + 1, y, 0x36, 1)

    def bottom(y):
        lv.put(gx, y, DATA_0DAA1C[ty], 1)
        lv.put(gx + 1, y, DATA_0DAA21[ty], 1)

    top()
    m0 = hh
    y = gy
    if ty == 5 or ty < 2:
        while True:
            y += 1
            m0 -= 1
            if m0 < 0:
                break
            body(y)
    else:
        while True:
            y += 1
            m0 -= 1
            if m0 != 0:
                body(y)
            else:
                bottom(y)
                break
    return True


def _blend_0db114(lv, gx, gy, ty, t, page):
    """CODE_0DB114: ajusta el tope de un Ledge edge segun lo que ya haya.
    Solo actua para tipos 0,1 y >= $0B (no el 2).  Devuelve (tile, pagina)."""
    if (9 <= ty < 0x0B) or ty == 2:
        return t, page
    low = _low_at(lv, gx, gy)
    if low in DATA_0DB0F0:
        # el ROM busca de X=$11 hacia abajo: gana la ULTIMA coincidencia
        i = len(DATA_0DB0F0) - 1 - DATA_0DB0F0[::-1].index(low)
        return DATA_0DB102[i], 1
    if low != 0x25 and t in (0x01, 0x03, 0x45, 0x48):
        t += 1
    return t, page


def _blend_0db198(lv, gx, gy, ty, t, page):
    """CODE_0DB198: ajusta el cuerpo de un Ledge edge (tipos 0,1,7,8)."""
    if ty == 2 or (3 <= ty < 7) or ty >= 9:
        return t, page
    low = _low_at(lv, gx, gy)
    if low in DATA_0DB15C:
        i = len(DATA_0DB15C) - 1 - DATA_0DB15C[::-1].index(low)
        return DATA_0DB17A[i], 1
    return t, page


def h_ledge_edges(lv, o):
    """Objeto 0x13 Ledge edges -> CODE_0DB075.  {Height},{Type}

    Tope (DATA_0DB039 + CODE_0DB114) en la fila 0, `height` filas de cuerpo
    (DATA_0DB048 la primera, DATA_0DB057 el resto, + CODE_0DB198) y, para los
    tipos >= $0B, el remate DATA_0DB066 en la fila height+1.  Todas las
    escrituras son `STA [ptr],Y` + CODE_0DA97D: columna fija."""
    hh, ty = o["h"], o["w"]
    gx, gy = o["gx"], o["gy"]
    if ty >= len(DATA_0DB039):
        return False

    def body_page(t):
        if t >= 9:
            return 1
        if t >= 7 or t < 3:
            return 0
        return 1

    y = gy
    t, p = _blend_0db114(lv, gx, y, ty, DATA_0DB039[ty], 1 if ty >= 3 else 0)
    lv.put(gx, y, t, p)
    y += 1
    m0 = hh - 1
    tabla = DATA_0DB048
    while m0 >= 0:
        t, p = _blend_0db198(lv, gx, y, ty, tabla[ty], body_page(ty))
        lv.put(gx, y, t, p)
        y += 1
        m0 -= 1
        tabla = DATA_0DB057
    if ty >= 0x0B:
        lv.put(gx, y, DATA_0DB066[ty], 1)
    return True


def h_ground_ledge(lv, o):
    """Objeto 0x14 Ground ledge -> CODE_0DB1D4.  {Height},{Width}
    Fila 0 = Map16 $100 (page 2, tile $00), despues `height` filas de $03F
    (page 1).  Total height+1 filas: m2 arranca en height y el bucle escribe
    mientras m2 >= 0 tras el decremento, o sea height veces."""
    w, hh = o["w"], o["h"]
    gx, gy = o["gx"], o["gy"]
    for i in range(w + 1):
        lv.put(gx + i, gy, 0x00, 1)
    for j in range(1, hh + 1):
        for i in range(w + 1):
            lv.put(gx + i, gy + j, 0x3F, 0)
    return True


def h_long_ground_ledge(lv, o):
    """Objeto 0x21 Long ground ledge -> CODE_0DB1C8.  {Width}
    m2 = 2 fijo -> 1 fila de tile $100 + 2 filas de tile $3F."""
    w = o["settings"]
    gx, gy = o["gx"], o["gy"]
    for i in range(w + 1):
        lv.put(gx + i, gy, 0x00, 1)
    for j in (1, 2):
        for i in range(w + 1):
            lv.put(gx + i, gy + j, 0x3F, 0)
    return True


def h_bushes(lv, o):
    """Objeto 0x3F Bushes -> CODE_0DB5B7.  {Height=tipo},{Width}
    Inicio + (width-1) piezas de medio + final = width+1 bloques: el bucle es
    `DEC m0 / BNE`, que cuenta el inicio como una iteracion.  (Con width=0 el
    ROM da la vuelta a 255 piezas; se reproduce con el & $FF.)"""
    ty, w = o["h"], o["w"]
    if ty >= len(DATA_0DB5A8):
        return False
    cur = Cur(lv, o["gx"], o["gy"])
    cur.w(DATA_0DB5A8[ty], 0)
    for _ in range((w - 1) & 0xFF):
        cur.w(DATA_0DB5AD[ty], 0)
    cur.put(DATA_0DB5B2[ty], 0)
    return True


def h_arch_ledge(lv, o):
    """Objeto 0x3C Arch ledge -> CODE_0DB604.  {Height},{Width}"""
    w = o["w"]
    gx, gy = o["gx"], o["gy"]
    xi = 0
    m2 = w
    for _ in range(3):
        lv.put(gx, gy + _, DATA_0DB5E8[xi % len(DATA_0DB5E8)], 1)
        xi += 1
    while m2 > 0:
        lv.put(gx, gy, DATA_0DB5E8[xi % len(DATA_0DB5E8)], 1)
        xi += 1
        lv.put(gx, gy, DATA_0DB5E8[xi % len(DATA_0DB5E8)], 1)
        xi += 1
        m2 -= 1
    return True


def h_ext_block(lv, o):
    """Objetos extendidos 0x10..0x42 -> CODE_0DA57B.
    tile = DATA_0DA548[type-0x10]; page 2 si (type-0x10) >= 0x13."""
    ty = o["type"]
    idx = ty - 0x10
    if not (0 <= idx < len(DATA_0DA548)):
        return False
    page = 1 if idx >= 0x13 else 0
    lv.put(o["gx"], o["gy"], DATA_0DA548[idx], page)
    return True


def h_ext_yellow_block(lv, o):
    """Extendido 0x8E '! block, yellow' -> CODE_0DB583 -> tile $6B."""
    lv.put(o["gx"], o["gy"], 0x6B, 0)
    return True


def h_noop(lv, o):
    """Objetos sin tiles (screen exit / jump)."""
    return True


# ---------------------------------------------------------------------------
# Cursor de escritura, fiel a tiles.s
#
# El hardware no tiene un "buffer 2D": tiene un puntero (wm_Map16BlkPtrL) y un
# indice Y (wm_BlockSubScrPos = (fila&0x0F)*16 + columna).  Los handlers avanzan
# con estas cuatro primitivas, y la diferencia entre ellas es lo que da la forma
# de cada objeto.  Modelarlas bien es lo que hace que una tuberia diagonal salga
# diagonal y no una escalera al reves.
# ---------------------------------------------------------------------------
class Cur:
    """Cursor de bloques Map16 sobre un Level.

    Modela el estado REAL del ROM, que son tres cosas distintas:

        scr / saved   wm_Map16BlkPtrL (puntero vivo a la pantalla) y m4/m5
                      (la copia que guarda CODE_0DA6B1)
        row / pcol    wm_BlockSubScrPos: fila y columna BASE, persistentes
        col           el registro Y: columna donde escribe CODE_0DA95B

    `restore()` (CODE_0DA6BA) SOLO repone el puntero de pantalla; NO toca ni la
    fila ni la columna.  La fila avanza de forma permanente con down*(), que
    reescriben wm_BlockSubScrPos.  Modelar restore() como "volver al punto
    guardado" hace que todos los bucles save/restore/down reescriban la MISMA
    fila (era el bug de las pendientes huecas de las pantallas 5 y 11).

    Las columnas se cuentan DENTRO de la pantalla (0..15).  Al pasar de la
    columna 15 el hardware avanza a la pantalla siguiente y vuelve a la
    columna 0 de la fila base (tiles.s `_0DA95D`: ptr += $B0, Y = pos & $F0).
    """

    def __init__(self, lv, gx, gy):
        self.lv = lv
        self.scr = gx // TILES_PER_SCREEN_W
        self.pcol = gx % TILES_PER_SCREEN_W
        self.col = self.pcol
        self.row = gy
        self.saved = self.scr

    def gx(self):
        return self.scr * TILES_PER_SCREEN_W + self.col

    def gy(self):
        return self.row

    def save(self):
        """CODE_0DA6B1: m4/m5 = puntero de pantalla (solo eso)."""
        self.saved = self.scr

    def restore(self):
        """CODE_0DA6BA: puntero de pantalla = m4/m5.  Y y la fila no cambian."""
        self.scr = self.saved

    def put(self, idx, page=0):
        self.lv.put(self.gx(), self.row, idx & 0xFF, page)

    def adv(self):
        """CODE_0DA95B / _0DA95D: una columna a la derecha; al pasar de la 15
        vuelve a la columna 0 de la MISMA fila, en la pantalla siguiente."""
        self.col += 1
        if self.col > TILES_PER_SCREEN_W - 1:
            self.col = 0
            self.scr += 1

    def set_pos(self):
        """`STY wm_BlockSubScrPos`: la columna actual pasa a ser la base."""
        self.pcol = self.col

    def w(self, idx, page=0):
        """Escribe y avanza una columna (CODE_0DA95B)."""
        self.put(idx, page)
        self.adv()

    def down(self):
        """CODE_0DA97D: pos += $10 -> una fila abajo; Y = pos (columna base).
        No toca el puntero de pantalla."""
        self.row += 1
        self.col = self.pcol

    def down_left(self):
        """CODE_0DA992: pos += $0F -> una fila abajo y una columna a la
        IZQUIERDA; Y = pos.  Si la columna base era 0, va a la columna 15 de la
        PANTALLA ANTERIOR, y CODE_0DA9D6 mueve TAMBIEN la copia guardada (m4/m5)
        (verificado contra la referencia: la tuberia diagonal de la pantalla 8
        aparece en la columna 15 de la pantalla 7)."""
        self.row += 1
        self.pcol -= 1
        if self.pcol < 0:
            self.pcol = TILES_PER_SCREEN_W - 1
            self.scr -= 1
            self.saved -= 1
        self.col = self.pcol

    def down_right(self):
        """CODE_0DA9B4: pos += $11 -> una fila abajo y una columna a la
        DERECHA; al pasar de la 15 sigue en la columna 0 de la pantalla
        siguiente, y CODE_0DA9EF mueve tambien la copia guardada."""
        self.row += 1
        self.pcol += 1
        if self.pcol > TILES_PER_SCREEN_W - 1:
            self.pcol = 0
            self.scr += 1
            self.saved += 1
        self.col = self.pcol


def _low_at(lv, gx, gy):
    """Byte bajo del bloque que ya hay en (gx, gy), como lo lee el ROM.

    Una celda vacia vale $25 en el ROM (el bloque en blanco con el que se
    inicializa el buffer), no 0: las mezclas comparan con `CMP #$25`.  En
    nuestro Level el vacio es la palabra 0, asi que hay que traducirlo."""
    w = lv.get(gx, gy)
    return (w & 0xFF) if w else 0x25


def _low(lv, cur):
    return _low_at(lv, cur.gx(), cur.gy())


def _abfd(lv, cur, base, page=1):
    """CODE_0DABFD: escribe `base` ajustado segun lo que ya haya en la celda.
    Comprueba en el orden $03, $01, $3F y suma $04, $03, $01."""
    low = _low(lv, cur)
    if low == 0x03:
        base += 0x04
    elif low == 0x01:
        base += 0x03
    elif low == 0x3F:
        base += 0x01
    cur.w(base, page)


def _84e(lv, cur, base, page):
    """CODE_0DB84E: idem pero con $25 y $3F (suma 0, 1 o 2)."""
    low = _low(lv, cur)
    if low == 0x25:
        pass
    elif low == 0x3F:
        base += 1
    else:
        base += 2
    cur.w(base, page)


# --- tablas de tiles.s -----------------------------------------------------

# DATA_0DA7E3 - cartel de flecha (2x2)
DATA_0DA7E3 = [0x66, 0x67, 0x68, 0x69]

# DATA_0DB3BB - Rope/Clouds: el indice sale de settings>>4
DATA_0DB3BB = [0x05, 0x06]

# DATA_0DB72F - tuberia diagonal (16 entradas, se escriben con pagina 2, o sea
# indices Map16 $1C4..$1C7 / $1EC..$1EE y $159..$15C).
DATA_0DB72F = [0xC4, 0xC5, 0xC7, 0xEC, 0xED, 0xC6, 0xC7, 0xEE,
               0x59, 0x5A, 0xEF, 0xC7, 0xEE, 0x59, 0x5B, 0x5C]

# DATA_0DB212/215/218 (tipo 0) y DATA_0DB21B/21E/221 (tipo != 0):
# fila superior, filas del medio, fila inferior del poste.
DATA_0DB_POLE = [
    ([0x2F, 0x25, 0x32], [0x30, 0x25, 0x33], [0x31, 0x25, 0x34]),
    ([0x39, 0x25, 0x3C], [0x3A, 0x25, 0x3D], [0x3B, 0x25, 0x3E]),
]


# ---------------------------------------------------------------------------
# Handlers nuevos (transcritos de tiles.s)
# ---------------------------------------------------------------------------

def h_yoshi_coin(lv, o):
    """Extendido 0x41 Yoshi Coin -> CODE_0DB2CA.
    Map16 $02D arriba y $02E una fila abajo, misma columna.
    OJO: el ROM hace `STA [ptr],Y` (sin avanzar columna) y despues
    `CODE_0DA97D`; hay que usar put()+down(), no w()."""
    cur = Cur(lv, o["gx"], o["gy"])
    cur.put(0x2D, 0)
    cur.down()
    cur.put(0x2E, 0)
    return True


def h_midway_point(lv, o):
    """Objeto 0x15 Midway/Goal point -> CODE_0DB224.  {Height},{Type}
    Tres columnas de (height+1) filas: la del medio es el poste ($25).
    El ROM escribe con `STA [ptr],Y` + `CODE_0DA97D`, o sea columna fija."""
    ty = o["w"] & 0x01
    top, mid, bot = DATA_0DB_POLE[ty]
    # El ROM baja con TYA/ADC #$10/TAY sobre el registro Y, sin tocar
    # wm_BlockSubScrPos: coordenadas directas, sin Cur.
    gx, gy = o["gx"], o["gy"]
    for c in range(3):
        y = gy
        lv.put(gx + c, y, top[c], 0)
        for _ in range(o["h"] - 1):
            y += 1
            lv.put(gx + c, y, mid[c], 0)
        lv.put(gx + c, y + 1, bot[c], 0)
    return True


def h_rope_clouds(lv, o):
    """Objeto 0x17 Rope/Clouds -> CODE_0DB3BD.  {Type},{Width}
    (settings&0x0F)+1 bloques en fila; el tipo (settings>>4) elige $05 o $06.
    Ambos van a la pagina 2 -> Map16 $105 / $106."""
    ty = o["h"]
    if ty >= len(DATA_0DB3BB):
        return False
    cur = Cur(lv, o["gx"], o["gy"])
    for _ in range((o["w"] & 0x0F) + 1):
        cur.w(DATA_0DB3BB[ty], 1)
    return True


def h_midway_rope(lv, o):
    """Extendido 0x46 Midway point rope -> CODE_0DA68E.
    $35 una columna a la izquierda, $38 en la posicion (ambos pagina 1)."""
    cur = Cur(lv, o["gx"], o["gy"])
    cur.col -= 1
    if cur.col < 0:
        cur.col = TILES_PER_SCREEN_W - 1
        cur.scr -= 1
    cur.w(0x35, 0)
    cur.put(0x38, 0)
    return True


def h_arrow_sign(lv, o):
    """Extendido 0x86 Arrow sign -> CODE_0DA7E7.
    Bloque 2x2 de Map16 $066..$069 (pagina 1)."""
    cur = Cur(lv, o["gx"], o["gy"])
    cur.save()
    x = 0
    while True:
        cur.w(DATA_0DA7E3[x], 0)
        x += 1
        if x & 1:
            continue
        cur.restore()
        cur.down()
        if x >= 4:
            break
    return True


def h_vert_pipe_bone_log(lv, o):
    """Objeto 0x1F Vert. Pipe/Bone/Log -> CODE_0DB51F.  {Height},{Unused}
    Columna vertical: $53, (height-1) x $54, $55.  Todo pagina 2.
    Igual que el poste: `STA [ptr],Y` + `CODE_0DA97D` -> put()+down()."""
    cur = Cur(lv, o["gx"], o["gy"])
    cur.put(0x53, 1)
    for _ in range(o["h"] - 1):
        cur.down()
        cur.put(0x54, 1)
    cur.down()
    cur.put(0x55, 1)
    return True


def h_diag_pipe_right(lv, o):
    """Objeto 0x39 Right facing diagonal pipe -> CODE_0DB73F.  {Height},{Unused}

    Escribe DATA_0DB72F con pagina 2 (indices Map16 $1C4/$1C5/$1C7/$1EC/$1ED/
    $1C6/$1EE y $159/$15A/$15B/$15C).  Cada fila empieza una columna mas a la
    izquierda que la anterior (CODE_0DA992) y tiene 2 bloques mas que la previa.
    Verificado contra la referencia: fila 20 -> $159 en la col 8, $15A en la 9;
    fila 21 -> $159 en la 7, $15B en la 8; fila 22 -> $159 en la 6, $15B en la 7.
    """
    cur = Cur(lv, o["gx"], o["gy"])
    m0 = o["h"]
    m1 = 1
    x = 0

    def fila(n):
        nonlocal x
        for _ in range(n):
            cur.w(DATA_0DB72F[x], 1)
            x += 1

    cur.save()
    # bucle A
    while True:
        fila(m1 + 1)
        cur.restore()
        cur.down_left()
        m1 += 2
        m0 -= 1
        if m0 < 0:
            break
        if x == 6:
            break
    if m0 >= 0:
        # bucle B
        m1 -= 1
        while True:
            fila(m1 + 1)
            cur.restore()
            cur.down_left()
            if x == 0x10:
                x -= 5
            m0 -= 1
            if m0 < 0:
                break
    cur.adv()
    cur.w(0xEB, 1)
    return True


def h_diag_ledge_left(lv, o):
    """Objeto 0x3A Left facing diagonal ledge -> CODE_0DB7AA.  {Height},{Type}

    Escalera que baja en diagonal hacia la derecha: una cara de $AA/$E2/$F7 y
    relleno de $3F, con los bordes $A1/$A6/$A3.  Nota: la rutina original tiene
    un bug en Nintendo (`LDA.W BlockIsPage1` en vez de `JSR`).  BlockIsPage1/2
    escriben el byte alto EN LA CELDA ACTUAL, asi que sin la llamada el $A1
    conserva la pagina que ya tenia esa celda (vacia -> 0 -> Map16 $0A1).
    Verificado contra la referencia: la cima de las colinas es $0A1, no $1A1.
    """
    cur = Cur(lv, o["gx"], o["gy"])
    m2 = o["w"]
    m3 = o["h"]
    m1 = 1
    x = 1
    cur.save()

    _abfd(lv, cur, 0xAA, 1)
    _84e(lv, cur, 0xA1, None)       # sin BlockIsPage: bug de Nintendo

    while True:
        # _0DB7FD
        cur.restore()
        cur.down_left()
        m1 += 2
        x = m1
        m2 -= 1
        if m2 < 0:
            break
        # CODE_0DB7D6
        _abfd(lv, cur, 0xAA, 1)
        x -= 1
        cur.w(0xE2, 1)
        # _0DB7F2
        while True:
            x -= 1
            if x == 0:
                break
            cur.w(0x3F, 0)
        _84e(lv, cur, 0xA6, 0)

    # JSR _0DA95D / STY wm_BlockSubScrPos / JSR CODE_0DA6B1
    cur.adv()
    cur.set_pos()
    cur.save()
    x -= 1
    m1 = x
    _abfd(lv, cur, 0xF7, 1)
    x = m1
    while True:
        # _0DB836
        while True:
            x -= 1
            if x == 0:
                break
            cur.w(0x3F, 0)
        _84e(lv, cur, 0xA6, 0)
        cur.restore()
        cur.down_right()
        x = m1
        m3 -= 1
        if m3 < 0:
            break
        # CODE_0DB823
        _84e(lv, cur, 0xA3, 0)
    return True


def h_slopes(lv, o):
    """Objeto 0x12 Slopes -> CODE_0DAB3E.  {Height},{Type}
    El tipo es (settings & 0x0F) mod 10 y elige una de las 10 rutinas de
    PtrsLong0DAB50.  Yoshi's Island 1 solo usa el tipo 4 (CODE_0DADA3):
    una escalera de pendiente que crece un bloque por fila.

    OJO con los bucles: `BPL -` de CODE_0DADA3 apunta a `CPX #$01`, no al
    principio de la rutina, asi que el bucle de relleno es
    "mientras X != 1" y no "hasta que X == 1 desde el inicio".
    """
    ty = o["w"] & 0x0F
    while ty >= 10:
        ty -= 10

    if ty == 4:
        # CODE_0DADA3: $AF (pagina 2) en la diagonal, relleno $3F (pagina 1)
        # y remate $E4 (pagina 2).  La fila k lleva k bloques de relleno.
        cur = Cur(lv, o["gx"], o["gy"])
        m0 = o["h"] + 1
        m2 = 0
        cur.save()
        while True:
            if m0 == 0:
                return True
            _abfd(lv, cur, 0xAF, 1)
            cur.restore()
            cur.down()
            m2 += 1
            x = m2
            m0 -= 1
            if m0 < 0:
                return True
            while x != 1:
                cur.w(0x3F, 0)
                x -= 1
            cur.w(0xE4, 1)

    if ty == 5:
        # CODE_0DADEB: cara de 4 columnas ($82/$87/$8C/$91, pagina 2),
        # relleno $3F y remate $E6/$E6/$DB/$DC; el relleno crece 4 por fila.
        cur = Cur(lv, o["gx"], o["gy"])
        m0 = o["h"] + 1
        m2 = 3
        cur.save()
        while True:
            for base in (0x82, 0x87, 0x8C, 0x91):
                _abfd(lv, cur, base, 1)
            cur.restore()
            cur.down()
            m2 += 4
            x = m2
            m0 -= 1
            if m0 < 0:
                return True
            while x != 7:
                cur.w(0x3F, 0)
                x -= 1
            for base in (0xE6, 0xE6, 0xDB, 0xDC):
                cur.w(base, 1)
            if m0 == 0:
                return True

    return False


# ---------------------------------------------------------------------------
# Handlers. Transcritos de tiles.s. Devuelven True si se implementaron.
# ---------------------------------------------------------------------------


HANDLERS = {
    # objetos estandar
    0x01: h_generic_rect, 0x02: h_generic_rect, 0x03: h_generic_rect,
    0x04: h_generic_rect, 0x05: h_generic_rect, 0x06: h_generic_rect,
    0x07: h_generic_rect, 0x08: h_generic_rect, 0x09: h_generic_rect,
    0x0A: h_generic_rect, 0x0B: h_generic_rect, 0x0C: h_generic_rect,
    0x0D: h_generic_rect, 0x0E: h_generic_rect,
    0x0F: h_vertical_pipe,
    0x12: h_slopes,
    0x13: h_ledge_edges,
    0x14: h_ground_ledge,
    0x15: h_midway_point,
    0x17: h_rope_clouds,
    0x1F: h_vert_pipe_bone_log,
    0x21: h_long_ground_ledge,
    0x39: h_diag_pipe_right,
    0x3A: h_diag_ledge_left,
    0x3C: h_arch_ledge,
    0x3F: h_bushes,
}

EXT_HANDLERS = {
    0x00: h_noop, 0x01: h_noop,
    0x41: h_yoshi_coin,
    0x46: h_midway_rope,
    0x86: h_arrow_sign,
    0x8E: h_ext_yellow_block,
}

# Extendidos 0x10..0x40 son todos "escribir un bloque" (CODE_0DA57B), salvo
# 0x17 (Green star block -> CODE_0DA64D) que va aparte.
for _t in range(0x10, 0x41):
    if _t != 0x17:
        EXT_HANDLERS.setdefault(_t, h_ext_block)


def build(lv_path, verbose=True):
    data = open(lv_path, "rb").read()
    h = parse_header(data)
    objs, ok, endp = decode_stream(data)

    if not ok:
        print("AVISO: no se encontro el terminador $FF")
    if verbose:
        print("cabecera   : %s" % " ".join("%02X" % b for b in h["raw"]))
        print("pantallas  : %d   tileset: %d" % (h["num_screens"], h["tileset"]))
        print("terminador : offset %d de %d" % (endp, len(data)))

    lv = Level(h["num_screens"])
    for o in objs:
        gx = o["screen"] * TILES_PER_SCREEN_W + o["x"]
        gy = o["y"]
        o["gx"], o["gy"] = gx, gy
        fn = HANDLERS.get(o["num"]) if o["kind"] == "std" \
            else EXT_HANDLERS.get(o["type"])
        if fn is None:
            o["handled"] = False
            lv.skipped.append(o)
            continue
        o["handled"] = fn(lv, o)

    if verbose:
        print("tiles escritos : %d" % lv.placed)
        print("objetos manejados: %d de %d"
              % (sum(1 for o in objs if o.get("handled")), len(objs)))
        if lv.skipped:
            c = collections.Counter(o["name"] for o in lv.skipped)
            print("NO implementados:")
            for n, k in c.most_common():
                print("   %-42s x%d" % (n, k))
    return h, objs, lv


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def load_gfx(src_dir, files):
    """Devuelve {nombre: [tiles decodificados]}"""
    out = {}
    for f in files:
        if f in out:
            continue
        raw = open(os.path.join(src_dir, f + ".lz2"), "rb").read()
        dec = lc_lz2_decompress(raw)
        bpp = BPP_TABLE.get(f, 3)
        out[f] = decode_snes_tileset(dec, bpp)
    return out


# Los 8 pasos de la animacion de color de la moneda de Yoshi.
# Viven en `palette.py` (COIN_ANIM) porque el override va dentro de
# `build_cgram`, asi lo heredan TODAS las herramientas de comparacion.
from palette import COIN_ANIM, COIN_ANIM_REF


def render(h, lv, out_png, scale=1, pal_index=None, use_ramp=False,
           coin_frame=COIN_ANIM_REF):
    """Renderiza el nivel. Si pal_index es None se usa la paleta Map16 de cada
    cuadrante (lo correcto); si se pasa un entero se fuerza esa paleta para
    todos los tiles (util para diagnosticar)."""
    from PIL import Image
    import palette as palmod
    from map16 import Map16, TILESET_SET

    src = os.path.join(_DEF_SRC, "graphics")
    ts = h["tileset"]
    files = gfx_files_for_tileset(ts)
    if files is None:
        raise SystemExit("tileset %d fuera de OBJECTGFXLIST" % ts)
    print("tileset %d -> bloques GFX: %s" % (ts, files))
    gfx = load_gfx(src, files)

    setidx = TILESET_SET.get(ts, 0)
    m16 = Map16(set_index=setidx, tileset=ts)
    print("tablas Map16: set_%d (%d entradas)" % (setidx, len(m16.entries)))

    # paleta: 8 paletas de BG en CGRAM 0..127
    bank, labels = palmod.load_palette_bank(
        os.path.join(_DEF_SRC, "palettes", "palettes.a"))
    cgram, bgc = palmod.build_cgram(
        bank, labels, h["fg_palette"], h["bg_palette"],
        h["spr_palette"], h["bg_color"], coin_frame)
    if use_ramp:
        from smw2amiga import RAMP
        pals = [list(RAMP) for _ in range(8)]
    else:
        pals = [[palmod.snes_to_rgb8(c) for c in cgram[p * 16:p * 16 + 16]]
                for p in range(8)]
    # El color de fondo NO es cgram[0]: LoadPalette lo devuelve aparte en
    # `bg_color` (palette.py:138, bank[PALETTE_Sky + bgcol]).  cgram[0] queda
    # a 0 (negro) porque el CGRAM no se inicializa ahi.
    bg = palmod.snes_to_rgb8(bgc) if not use_ramp else (0, 0, 0)
    if pal_index is not None:
        print("paleta forzada a %d" % pal_index)

    # Cada bloque Map16 mide 16x16 (cuatro tiles de 8x8).  OJO: hasta el
    # 2026-09-22 esto usaba un paso de 8 px por bloque; con --scale 2 salia
    # 5120 px de ancho (parecia alineado con la referencia) pero cada bloque
    # pisaba la mitad derecha/inferior del anterior: solo se veia el cuadrante
    # superior izquierdo ampliado 2x.  Las pendientes salian "en escalera".
    BW, BH = lv.W * 16, lv.H * 16
    W, H = BW * scale, BH * scale
    img = Image.new("RGB", (W, H), bg)
    px = img.load()

    missing_idx = collections.Counter()
    missing_tile = collections.Counter()
    used_pals = collections.Counter()

    # Los 4 cuadrantes de la entrada Map16.
    #
    # ORDEN CORREGIDO (2026-09-22): la tabla Map16 NO guarda las 4 palabras en
    # orden raster TL,TR,BL,BR sino en orden COLUMN-MAJOR: TL,BL,TR,BR.
    # Es decir word0=TL, word1=BL, word2=TR, word3=BR.
    # Verificado empiricamente: renderizando la tabla completa (tools/m16sheet.py
    # --order row|col) con column-major aparecen objetos coherentes (tuberias,
    # cerros redondeados, bloques '?', monedas, bloques ON/OFF) y con row-major
    # salen todos despedazados.  Ademas cuadra con el expansor Map16->tilemap de
    # lv_read.s:1161, donde word0 y word2 van a la MISMA columna (TopLeft y
    # TopLeft+2) y word1 y word3 a la otra (BottomLeft y BottomLeft+2).
    QUAD = [(0, 0), (8, 0), (0, 8), (8, 8)]
    ORDER = [0, 2, 1, 3]

    for gy in range(lv.H):
        for gx in range(lv.W):
            idx = lv.get(gx, gy)
            if idx is None or idx == 0:
                continue
            scr = gx // TILES_PER_SCREEN_W
            e = m16.get(idx, scr)
            if e is None:
                missing_idx[idx] += 1
                continue
            eq = [e[i] for i in ORDER]
            rq = [m16.get_raw(idx, scr)[i] for i in ORDER]
            for (qdx, qdy), (tile10, pal, prio, xf, yf), rw in zip(QUAD, eq, rq):
                # el cuadrante vacio es la palabra $0000 COMPLETA.
                # Ojo: NO sirve `tile10 == 0` (el tile 0 es valido, p.ej. la
                # boquilla de tuberia = tile 0 a paleta 5, palabra $1400).
                if rw == 0:
                    continue
                block = tile10 // 128
                within = tile10 % 128
                if block >= len(files) or within >= len(gfx[files[block]]):
                    missing_tile[tile10] += 1
                    continue
                p = pal_index if pal_index is not None else pal
                used_pals[p] += 1
                colors = pals[p]
                t = gfx[files[block]][within]
                for y in range(8):
                    row = t[7 - y] if yf else t[y]
                    for x in range(8):
                        v = row[7 - x] if xf else row[x]
                        if v == 0:
                            continue
                        c = colors[v & 0x0F]
                        ox = gx * 16 + qdx + x
                        oy = gy * 16 + qdy + y
                        if ox >= BW or oy >= BH:
                            continue
                        for sy in range(scale):
                            for sx in range(scale):
                                px[ox * scale + sx, oy * scale + sy] = c
    img.save(out_png)
    print("render -> %s  (%dx%d px)" % (out_png, W, H))
    print("paletas usadas: %s"
          % ", ".join("%d:%d" % (p, c) for p, c in sorted(used_pals.items())))
    if missing_idx:
        print("indices Map16 sin tabla (%d): %s"
              % (len(missing_idx), ["$%03X" % i for i in sorted(missing_idx)][:12]))
    if missing_tile:
        print("tiles fuera de rango (%d): %s"
              % (len(missing_tile), sorted(missing_tile)[:12]))
    return img


def main():
    ap = argparse.ArgumentParser(description="Convierte un nivel de SMW a PNG")
    ap.add_argument("--lv", default=os.path.join(
        _DEF_SRC, "levels", "data", "world_1", "1", "obj.lv"))
    ap.add_argument("--out", default=os.path.join(_HERE, "..", "work", "level.png"))
    # --scale 1 = 5120x432, alineado 1:1 con SuperMarioWorldMap02.png
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--pal", type=int, default=None)
    ap.add_argument("--ramp", action="store_true")
    ap.add_argument("--coin-frame", type=int, default=COIN_ANIM_REF,
                    choices=list(range(len(COIN_ANIM))),
                    help="paso de la animacion de color de la moneda de Yoshi "
                         "(0..7); el paso 1 = $27FF es el de la referencia")
    a = ap.parse_args()

    h, objs, lv = build(a.lv)
    render(h, lv, a.out, a.scale, a.pal, a.ramp, a.coin_frame)


if __name__ == "__main__":
    main()
