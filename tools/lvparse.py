#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lvparse.py - Parser de datos de nivel de Super Mario World (.lv)

FORMATO (verificado contra documentacion publica + traza del desensamblado)

  Los datos de Layer 1 empiezan con 5 bytes de cabecera, luego objetos de
  3 bytes (4 para el "screen exit"):

      byte0 : NBBYYYYY   N = flag "nueva pantalla"
                         BB = 2 bits altos del numero de objeto
                         YYYYY = Y (0..31)
      byte1 : bbbbXXXX   bbbb = 4 bits bajos del numero de objeto
                         XXXX = X dentro de la pantalla (0..15)
      byte2 : SSSSSSSS   settings (objeto estandar)
                         o numero de objeto extendido (si el nº estandar = 0)

  Numero de objeto (6 bits) = bbbb | (BB << 4)      ; 0..63
     == 0  -> OBJETO EXTENDIDO  (byte2 = nº extendido, 0..255)
     != 0  -> OBJETO ESTANDAR   (byte2 = settings; el nº es 1..63)

  $FF como primer byte = fin de los datos.

  Confirmado en el codigo:
    lv_read.s:LoadLevelData   -> wm_BlockNum = (byte1>>4) | ((byte0 & $60)>>1)
    tiles.s:CODE_0DA40F       -> dispatch de objetos estandar (por nº - 1)
    tiles.s:CODE_0DA100       -> dispatch de objetos extendidos (por byte2)
    tiles.s:_0DA95D           -> stride por pantalla = $1B0 = 27*16
                                 => el nivel tiene 27 filas de 16 columnas
    tiles.s:CODE_0DA95B       -> escribe el tile number en el buffer L
    tiles.s:BlockIsPage1/2    -> escribe bits 8-15 en el buffer H

  El buffer Map16 de cada pantalla son DOS arrays de $1B0 bytes:
    wm_Map16BlkPtrL -> tile number (10 bits) + paleta/flip/prioridad en H
    offset dentro de la pantalla = Y * 16 + X      (row-major)

Uso:
    python lvparse.py [--lv fichero] [--dump] [--json salida] [--layout png]
"""

import argparse
import collections
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEF_SRC = os.path.normpath(os.path.join(_HERE, "..", "..", "smw-src-master", "project", "mw_e10"))

TILES_PER_SCREEN_W = 16
LEVEL_ROWS = 27

# ---------------------------------------------------------------------------
# Objetos ESTANDAR (numero 1..0x3F). El indice de la tabla del handler es
# (numero - 1). Fuente: tiles.s:CODE_0DA44B + doc publica.
# ---------------------------------------------------------------------------
STD_OBJ_NAMES = [
    "Water (Blue)",               # 01
    "Invisible coin blocks",      # 02
    "Invisible note blocks",      # 03
    "Invisible POW coins",        # 04
    "Coins",                      # 05
    "Walk-through dirt",          # 06
    "Water (Other color)",        # 07
    "Note blocks",                # 08
    "Turn blocks",                # 09
    "Coin ? blocks",              # 0A
    "Throw blocks",               # 0B
    "Black piranha plants",       # 0C
    "Cement blocks",              # 0D
    "Brown blocks",               # 0E
    "Vertical pipes",             # 0F
    "Horizontal pipes",           # 10
    "Bullet shooter",             # 11
    "Slopes",                     # 12
    "Ledge edges",                # 13
    "Ground ledge",               # 14
    "Midway/Goal point",          # 15
    "Blue coins",                 # 16
    "Rope/Clouds",                # 17
    "Water surface (ani)",        # 18
    "Water surface (not ani)",    # 19
    "Lava surface (ani)",         # 1A
    "Net top edge",               # 1B
    "Donut bridge",               # 1C
    "Net bottom edge",            # 1D
    "Net vertical edge",          # 1E
    "Vert. Pipe/Bone/Log",        # 1F
    "Horiz. Pipe/Bone/Log",       # 20
    "Long ground ledge",          # 21
    "Special (LM)",               # 22
    "Special (LM)",               # 23
    "Special (LM)",               # 24
    "Special (LM)",               # 25
    "Special (LM)",               # 26
    "Special (LM)",               # 27
    "Special (LM)",               # 28
    "Special (Reserved)",         # 29
    "Special (Reserved)",         # 2A
    "Special (Reserved)",         # 2B
    "Special (Reserved)",         # 2C
    "Special (LM)",               # 2D
    "Tileset Specific 1",         # 2E
    "Tileset Specific 2",         # 2F
    "Tileset Specific 3",         # 30
    "Tileset Specific 4",         # 31
    "Tileset Specific 5",         # 32
    "Tileset Specific 6",         # 33
    "Tileset Specific 7",         # 34
    "Tileset Specific 8",         # 35
    "Tileset Specific 9",         # 36
    "Tileset Specific 10",        # 37
    "Tileset Specific 11",        # 38
    "Tileset Specific 12",        # 39
    "Tileset Specific 13",        # 3A
    "Tileset Specific 14",        # 3B
    "Tileset Specific 15",        # 3C
    "Tileset Specific 16",        # 3D
    "Tileset Specific 17",        # 3E
    "Tileset Specific 18",        # 3F
]

# Nombres "de verdad" de los Tileset Specific (numeros 0x2E..0x3F = 18 entradas).
# El codigo los tiene en tiles.s:CODE_0DA44B a partir del indice 45
# (= numero 0x2E). La asignacion de abajo esta cruzada contra la tabla de
# handlers: p.ej. el numero 0x3F apunta a CODE_0DB5B7 = "Bushes 1 through 5",
# que es justo el objeto que aparece 13 veces en Yoshi's Island 1.
TILESET7_SPECIFIC = {
    0x2E: "Tileset Specific 1 (unused)",
    0x2F: "Tileset Specific 2 (unused)",
    0x30: "Ice blue vertical pipe",
    0x31: "Ice blue turn tiles",
    0x32: "Blue switch blocks",
    0x33: "Forest tree top",
    0x34: "Solid left/right and top edge (forest)",
    0x35: "Ledge (forest)",
    0x36: "Large tree trunk (forest)",
    0x37: "Small tree trunk (forest)",
    0x38: "Red switch blocks",
    0x39: "Right facing diagonal pipe",
    0x3A: "Left facing diagonal ledge",
    0x3B: "Right facing diagonal ledge",
    0x3C: "Arch ledge",
    0x3D: "Top cloud fringe",
    0x3E: "Left/right cloud fringe",
    0x3F: "Bushes 1 through 5",
}

# ---------------------------------------------------------------------------
# Objetos EXTENDIDOS (numero 0..0xFF). Fuente: doc SnesLab + tiles.s:CODE_0DA106
# ---------------------------------------------------------------------------
EXT_OBJ_NAMES = {
    0x00: "Screen Exit", 0x01: "Screen Jump",
    0x10: "Small door", 0x11: "Invisible ? block (1-UP)",
    0x12: "Invisible note block", 0x13: "Top left corner edge tile 1",
    0x14: "Top right corner edge tile 1", 0x15: "Small POW door",
    0x16: "Invisible POW ? block", 0x17: "Green star block",
    0x18: "3-UP moon", 0x19: "Invisible 1-UP #1",
    0x1A: "Invisible 1-UP #2", 0x1B: "Invisible 1-UP #3",
    0x1C: "Invisible 1-UP #4", 0x1D: "Red berry", 0x1E: "Pink berry",
    0x1F: "Green berry", 0x20: "Always turning block",
    0x21: "Bottom right of midway point (unused)",
    0x22: "Bottom right of midway point (unused)",
    0x23: "Note block (flower/feather/star)", 0x24: "ON/OFF block",
    0x25: "Direction coins ? block", 0x26: "Note block",
    0x27: "Note block, bounce on all sides", 0x28: "Turn block (Flower)",
    0x29: "Turn block (Feather)", 0x2A: "Turn block (Star)",
    0x2B: "Turn block (Star 2/1-UP/Vine)", 0x2C: "Turn block (Multiple coins)",
    0x2D: "Turn block (Coin)", 0x2E: "Turn block (Nothing)",
    0x2F: "Turn block (POW)", 0x30: "? block (Flower)",
    0x31: "? block (Feather)", 0x32: "? block (Star)", 0x33: "? block (Star 2)",
    0x34: "? block (Multiple coins)", 0x35: "? block (Key/Wings/Balloon/Shell)",
    0x36: "? block (Yoshi)", 0x37: "? block (Shell)", 0x38: "? block (Shell)",
    0x39: "Turn block, unbreakable (Feather)",
    0x3A: "Top left corner edge tile 2", 0x3B: "Top right corner edge tile 2",
    0x3C: "Top left corner edge tile 3", 0x3D: "Top right corner edge tile 3",
    0x3E: "Top left corner edge tile 4", 0x3F: "Top right corner edge tile 4",
    0x40: "Transculent block", 0x41: "Yoshi Coin",
    0x42: "Top left slope", 0x43: "Top right slope",
    0x44: "Purple triangle, left", 0x45: "Purple triangle, right",
    0x46: "Midway point rope", 0x47: "Door", 0x48: "Invisible POW door",
    0x49: "Ghost house exit", 0x4A: "Climbing net door",
    0x4B: "Conveyor end tile 1", 0x4C: "Conveyor end tile 2",
    0x7F: "Torpedo launcher", 0x80: "Ghost house entrance",
    0x81: "Water weed", 0x82: "Big bush 1", 0x83: "Big bush 2",
    0x84: "Castle entrance", 0x85: "Yoshi's house", 0x86: "Arrow sign",
    0x87: "! block, green", 0x88: "Tree branch, left",
    0x89: "Tree branch, right", 0x8A: "Switch, green", 0x8B: "Switch, yellow",
    0x8C: "Switch, blue", 0x8D: "Switch, red", 0x8E: "! block, yellow",
    0x8F: "Ghost house window", 0x90: "Boss door",
    0x91: "Steep left slope (vert. lev.)", 0x92: "Steep right slope (vert. lev.)",
    0x93: "Normal left slope (vert. lev.)", 0x94: "Normal right slope (vert. lev.)",
    0x95: "Very steep left slope (vert. lev.)",
    0x96: "Very steep right slope (vert. lev.)",
    0x97: "Switch palace right and bottom edge tile",
}

# Tabla DATA_0DA548: tipo extendido (0x10..0x42) -> tile number.
DATA_0DA548 = [
    0x1F, 0x22, 0x24, 0x42, 0x43, 0x27, 0x29, 0x25,
    0x6E, 0x6F, 0x70, 0x71, 0x72, 0x45, 0x46, 0x47,
    0x48, 0x36, 0x37, 0x11, 0x12, 0x14, 0x15, 0x16,
    0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x29, 0x1D,
    0x1F, 0x20, 0x21, 0x22, 0x23, 0x25, 0x26, 0x27,
    0x28, 0x2A, 0xDE, 0xE0, 0xE2, 0xE4, 0xEC, 0xED,
    0x2C, 0x25, 0x2D,
]

# Semantica del byte de settings por objeto estandar (doc SnesLab).
# "HW" = {Height},{Width};  "HT" = {Height},{Type};  etc.
STD_SETTINGS = {
    0x01: "HW", 0x02: "HW", 0x03: "HW", 0x04: "HW", 0x05: "HW",
    0x06: "HW", 0x07: "HW", 0x08: "HW", 0x09: "HW", 0x0A: "HW",
    0x0B: "HW", 0x0C: "HW", 0x0D: "HW", 0x0E: "HW",
    0x0F: "HT", 0x10: "TW", 0x11: "HU", 0x12: "HT", 0x13: "HT",
    0x14: "HW", 0x15: "HT", 0x16: "HW", 0x17: "TW", 0x18: "HW",
    0x19: "HW", 0x1A: "HW", 0x1B: "HW", 0x1C: "UW", 0x1D: "HW",
    0x1E: "HT", 0x1F: "HU", 0x20: "UW", 0x21: "W",
}


def parse_header(data):
    b0, b1, b2, b3, b4 = data[0:5]
    return {
        "raw": [b0, b1, b2, b3, b4],
        "num_screens": (b0 & 0x1F) + 1,
        "bg_palette": (b0 >> 5) & 0x07,
        "bg_color": (b1 >> 5) & 0x07,
        "level_mode": b1 & 0x1F,
        "spr_gfx": b2 & 0x0F,
        "music": (b2 >> 4) & 0x07,
        "layer3_prio": b2 >> 7,
        "timer": (b3 >> 6) & 0x03,
        "spr_palette": (b3 >> 3) & 0x07,
        "fg_palette": b3 & 0x07,
        # byte 4 = IIVVZZZZ, como lv_read.s (CODE_0584xx): tileset & $0F,
        # item memory = bits 6-7, wm_VertScrollHead = bits 4-5 (3 -> 0 y
        # sin scroll horizontal). Antes: 5 bits de tileset y el bit 7 como
        # scroll vertical (P77).
        "tileset": b4 & 0x0F,
        "item_memory": b4 >> 6,
        "vertical_scroll": (b4 >> 4) & 0x03,
    }


def decode_stream(data, base=5):
    """Recorre el flujo de objetos. Devuelve (objetos, ok, offset_fin)."""
    p = base
    screen = 0
    objs = []
    while p < len(data):
        if data[p] == 0xFF:
            return objs, True, p
        if p + 3 > len(data):
            return objs, False, p
        b0, b1, b2 = data[p], data[p + 1], data[p + 2]
        pos = p
        p += 3

        if b0 & 0x80:                     # N = "nueva pantalla"
            screen += 1

        num = (b1 >> 4) | ((b0 & 0x60) >> 1)     # numero de objeto, 0..63
        y = b0 & 0x1F                            # 0..31 (5 bits)
        x = b1 & 0x0F                            # 0..15
        # offset dentro del bloque Map16 (row-major, 16 columnas)
        sub = (y & 0x0F) * 16 + x

        o = {"pos": pos, "screen": screen, "x": x, "y": y, "sub": sub,
             "b0": b0, "b1": b1, "b2": b2, "num": num}

        if num == 0:
            o["kind"] = "ext"
            o["type"] = b2
            o["name"] = EXT_OBJ_NAMES.get(b2, "ext 0x%02X" % b2)
            o["tile"] = DATA_0DA548[b2 - 0x10] if 0x10 <= b2 <= 0x42 else None
            o["settings"] = None
        else:
            o["kind"] = "std"
            o["type"] = num
            nm = STD_OBJ_NAMES[num - 1] if 1 <= num <= len(STD_OBJ_NAMES) else "?"
            if nm.startswith("Tileset Specific"):
                nm = TILESET7_SPECIFIC.get(num, nm)
            o["name"] = nm
            o["tile"] = None
            o["settings"] = b2
            o["h"] = (b2 >> 4) & 0x0F
            o["w"] = b2 & 0x0F
            o["sem"] = STD_SETTINGS.get(num, "?")

        objs.append(o)

        # --- bytes extra ---
        if num == 0 and b2 == 0x00:            # Screen Exit: 4 bytes en total
            if p < len(data):
                o["dest"] = data[p]
                o["dest_flags"] = b1
                p += 1
        elif num == 0 and b2 == 0x01:          # Screen Jump: fija la pantalla
            screen = b0 & 0x1F
            o["jump_to"] = screen
    return objs, False, p


def main():
    ap = argparse.ArgumentParser(description="Parser de niveles de SMW (.lv)")
    ap.add_argument("--lv", default=None)
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--json", default=None)
    ap.add_argument("--layout", default=None,
                    help="render esquematico del nivel a PNG")
    a = ap.parse_args()

    lv = a.lv or os.path.join(_DEF_SRC, "levels", "data", "world_1", "1", "obj.lv")
    data = open(lv, "rb").read()
    print("fichero : %s" % lv)
    print("tamano  : %d bytes" % len(data))

    h = parse_header(data)
    print("\n=== CABECERA PRIMARIA ===")
    print("  bytes           : %s" % " ".join("%02X" % b for b in h["raw"]))
    print("  pantallas       : %d" % h["num_screens"])
    print("  modo de nivel   : %d" % h["level_mode"])
    print("  pal BG / color  : %d / %d" % (h["bg_palette"], h["bg_color"]))
    print("  gfx sprites     : %d" % h["spr_gfx"])
    print("  musica          : %d" % h["music"])
    print("  pal FG / SPR    : %d / %d" % (h["fg_palette"], h["spr_palette"]))
    print("  tiempo          : %d" % h["timer"])
    print("  tileset         : %d" % h["tileset"])
    print("  layer3 prio     : %d" % h["layer3_prio"])
    print("  item memory     : %d" % h["item_memory"])
    vs = h["vertical_scroll"]
    print("  scroll vertical : %d (%s)" % (vs, ("no hay (f7f4 vuelve enseguida)", "sigue a Mario",
          "solo en algunos casos (CODE_00F82A)", "ni vertical ni horizontal")[vs]))

    objs, ok, endp = decode_stream(data)
    print("\n=== FLUJO DE OBJETOS ===")
    print("  objetos leidos  : %d" % len(objs))
    print("  terminador $FF  : %s (offset %d de %d)"
          % ("OK" if ok else "NO ENCONTRADO", endp, len(data)))
    if ok and endp != len(data) - 1:
        print("  AVISO: %d bytes tras el terminador" % (len(data) - 1 - endp))

    std = collections.Counter()
    ext = collections.Counter()
    for o in objs:
        (std if o["kind"] == "std" else ext)[o["name"]] += 1

    print("\n=== OBJETOS ESTANDAR (%d) ===" % sum(std.values()))
    for n, c in std.most_common():
        print("  %-42s x%d" % (n, c))
    print("\n=== OBJETOS EXTENDIDOS (%d) ===" % sum(ext.values()))
    for n, c in ext.most_common():
        print("  %-42s x%d" % (n, c))

    # rango de Y de los objetos "de suelo" -> confirma la orientacion del eje Y
    ys = [o["y"] for o in objs if o["kind"] == "std" and o["num"] in (0x14, 0x21)]
    if ys:
        print("\n  Y de los objetos de suelo: min=%d max=%d (nivel de %d filas)"
              % (min(ys), max(ys), LEVEL_ROWS))

    if a.dump:
        print("\n=== DETALLE ===")
        print("  %-5s %-5s %-3s %-3s %-4s %-10s %s"
              % ("offs", "pant", "X", "Y", "num", "tipo", "nombre"))
        for o in objs:
            extra = ""
            if o["kind"] == "std":
                extra = "  h=%d w=%d" % (o["h"], o["w"])
            elif o.get("tile") is not None:
                extra = "  tile=$%02X" % o["tile"]
            if o.get("dest") is not None:
                extra += "  dest=$%02X" % o["dest"]
            print("  %-5d %-5d %-3d %-3d $%02X  %-10s %s%s"
                  % (o["pos"], o["screen"], o["x"], o["y"], o["num"],
                     o["kind"], o["name"], extra))

    if a.layout:
        render_layout(h, objs, a.layout)

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"header": h, "objects": objs}, f, indent=1)
        print("\nJSON -> %s" % a.json)


# ---------------------------------------------------------------------------
# Render esquematico: dibuja cada objeto como un rectangulo en su posicion.
# Sirve para VERIFICAR el parser (la silueta de Yoshi's Island 1 es conocida).
# ---------------------------------------------------------------------------
def render_layout(h, objs, path, scale=6):
    from PIL import Image, ImageDraw

    ns = h["num_screens"]
    W = ns * TILES_PER_SCREEN_W
    H = LEVEL_ROWS
    img = Image.new("RGB", (W * scale, H * scale), (108, 190, 240))  # cielo
    d = ImageDraw.Draw(img)

    # rejilla de pantallas
    for s in range(ns + 1):
        x = s * TILES_PER_SCREEN_W * scale
        d.line([(x, 0), (x, H * scale)], fill=(150, 210, 245))

    palette = {}
    colors = [(70, 130, 60), (140, 90, 40), (200, 60, 60), (60, 60, 200),
              (230, 200, 60), (30, 140, 140), (150, 60, 160), (90, 90, 90)]

    def col(name):
        if name not in palette:
            palette[name] = colors[len(palette) % len(colors)]
        return palette[name]

    for o in objs:
        sx = o["screen"] * TILES_PER_SCREEN_W + o["x"]
        sy = o["y"]
        if o["kind"] == "std":
            # los objetos crecen hacia abajo (Y+1) y hacia la derecha (X+1)
            w = max(1, o["w"])
            hh = max(1, o["h"])
            if o["sem"] == "W":
                w = o["settings"] + 1
                hh = 3
            elif o["sem"] == "HT":
                hh = max(1, o["h"]) + 1
                w = 1
            elif o["sem"] == "TW":
                w = max(1, o["w"]) + 1
                hh = 1
            elif o["sem"] == "HU":
                hh = max(1, o["h"]) + 1
                w = 1
            elif o["sem"] == "UW":
                w = max(1, o["w"]) + 1
                hh = 1
            c = col(o["name"])
        else:
            w = hh = 1
            c = (240, 240, 240)

        x0 = sx * scale
        y0 = sy * scale
        x1 = min(W, sx + w) * scale - 1
        y1 = min(H, sy + hh) * scale - 1
        d.rectangle([x0, y0, x1, y1], fill=c,
                    outline=(0, 0, 0) if o["kind"] == "ext" else None)

    img.save(path)
    print("\nlayout -> %s  (%dx%d px, %d pantallas x %d filas)"
          % (path, img.width, img.height, ns, H))
    print("  leyenda:")
    for n, c in sorted(palette.items()):
        print("    rgb%-16s %s" % (str(c), n))


if __name__ == "__main__":
    main()
