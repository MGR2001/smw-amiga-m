#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smw2amiga.py - Etapa 1 del port-demo SMW (SNES) -> Commodore Amiga OCS/ECS

Convierte los recursos del decompilado a formatos que una Amiga 500 (1 MB)
pueda consumir con el blitter y el copper:

    1. Descompresor LC_LZ2      (formato de compresion de graficos de SMW)
    2. Decodificador de tiles SNES  (planar entrelazado, 2/3/4 bpp)
    3. Codificador planar Amiga (bitplane-major, listo para el blitter)
    4. Paletas: BGR555 (SNES, 15 bits) -> 0x0RGB (Amiga, 12 bits)
    5. Previews PNG para verificar visualmente
    6. Auto-test de ida y vuelta del codificador planar

Uso:
    python smw2amiga.py --all
    python smw2amiga.py --gfx chr spr-1 obj-3 --planes 4
"""

import argparse
import os
import sys

# Rutas por defecto resueltas desde la ubicacion de ESTE script, no desde el
# directorio de trabajo: asi funciona se invoque como se invoque.
_HERE = os.path.dirname(os.path.abspath(__file__))
_DEF_SRC = os.path.normpath(os.path.join(_HERE, "..", "..", "smw-src-master",
                                         "project", "mw_e10"))
_DEF_OUT = os.path.normpath(os.path.join(_HERE, "..", "assets-out"))

# ---------------------------------------------------------------------------
# Profundidad de color de cada fichero de graficos.
# Fuente: document/graphics.txt (IDs en hexadecimal) + verificacion empirica
# renderizando cada fichero a 4, 3 y 2 bpp (work/bpp_matrix.png).
#
# Resumen de la verificacion visual:
#   spr-1  3bpp -> "Nintendo Presents"      (4bpp/2bpp = basura)
#   spr-2  3bpp -> Koopa, goomba, piranha
#   obj-1  3bpp -> ghost house, plataforma de hueso, pinchos
#   obj-3  3bpp -> suelo de hierba, arbusto, tuberia fina
#   bg-1   3bpp -> tiles de barco hundido
#   gb-1   2bpp -> set de caracteres "0123...UVW"
#   chr    4bpp -> cara de Mario + huevo de Yoshi
#
# Todos los ficheros de 0xC00 (3072) B descomprimidos son 3bpp = 128 tiles,
# salvo chr (0x5D00 = 23808 B, 4bpp = 744 tiles) y gb-* (2048 B, 2bpp).
# ---------------------------------------------------------------------------
BPP_TABLE = {
    "chr": 4, "anim": 3,
    "spr-1": 3, "spr-2": 3, "spr-3": 3, "spr-4": 3, "spr-5": 3,
    "spr-6": 3, "spr-7": 3, "spr-8": 3, "spr-9": 3, "spr-10": 3,
    "spr-11": 3, "spr-12": 3, "spr-13": 3, "spr-14": 3, "spr-15": 3,
    "obj-1": 3, "obj-2": 3, "obj-3": 3, "obj-4": 3,
    "obj-5": 3, "obj-6": 3, "obj-7": 3, "obj-8": 3,
    "bg-1": 3, "bg-2": 3, "bg-3": 3,
    "map-1": 3, "map-2": 3, "map-3": 3, "map-4": 3, "map-5": 3,
    "boss-1": 3, "boss-2": 3, "boss-3": 3, "boss-4": 3, "boss-5": 3,
    "boss-6": 4,
    "cin-1": 3, "cin-2": 3, "cin-3": 3, "cin-4": 3,
    "cin-5": 3, "cin-6": 3, "cin-7": 3, "cin-8": 3,
    "gb-1": 2, "gb-2": 2, "gb-3": 2, "gb-4": 2, "gb-5": 2,
}

# Contenido segun document/graphics.txt (util para el informe)
GFX_NOTES = {
    # chr = GFX 32 (4BPP) "Player tiles, yoshi berry" -> 744 tiles, el fichero
    # mas grande.  Verificado renderizando: se ve la cara de Mario y el huevo
    # de Yoshi.  OJO: NO son "objetos comunes" (eso esta repartido entre
    # obj-*.lz2 y spr-*.lz2).
    "chr": "tiles del jugador (Mario/Luigi), huevo de Yoshi (4bpp)",
    "anim": "animaciones de tiles",
    "spr-1": "logo Nintendo, power-ups",
    "spr-2": "Koopa, goomba, piranha",
    "spr-3": "Spiny, wiggler, bob-omb, p-balloon",
    "spr-4": "Thwomp, magikoopa, bony fish",
    "spr-5": "Buzzy beetle, blargg, skull raft",
    "spr-6": "Diggin' chuck, plataformas, sierra",
    "spr-7": "Torpedo ted, erizo, delfin, pez globo",
    "spr-8": "Monty mole, pokey, volcano lotus",
    "spr-9": "Puntin' chuck, disco ball, ninji",
    "spr-10": "Big boo, boo block, eerie",
    "spr-11": "Bony koopa, sparky, grinder",
    "spr-12": "Huevo de Yoshi, hammer bro, chuck",
    "spr-13": "Banzai bill, mega mole, rex",
    "spr-14": "Dino torch, dino rhino",
    "spr-15": "sprites finales",
    "obj-1": "tiles de ghost house, plataforma hueso, pinchos",
    "obj-2": "tuberia, moneda Yoshi, bloque cemento, nubes",
    "obj-3": "suelo de hierba, arbusto, tuberia fina",
    "obj-4": "cuerda, tronco, columna vegetal",
    "obj-5": "arbusto grande, luna 3-up, puerta, bloque estrella",
    "obj-6": "tiles de castillo, pinchos grandes, puerta de castillo",
    "obj-7": "tiles subterraneos, plataforma de hueso",
    "obj-8": "tiles de bosque/nube, tronco",
    "bg-1": "tiles de barco hundido",
    "bg-2": "bosque/nube/montana, plataforma tronco",
    "bg-3": "tiles de montana, plataforma seta",
    "map-1": "casa de Yoshi, switch palace, castillo de Bowser",
    "map-2": "tiles de sprites del overworld",
    "map-3": "tiles de hierba del overworld, agua",
    "map-4": "objetos del overworld",
    "map-5": "niveles/carteles del overworld",
    "boss-1": "Wendy, Lemmy", "boss-2": "Morton, Ludwig, Roy",
    "boss-3": "Bowser", "boss-4": "Mechakoopa, caja de power-up",
    "boss-5": "Iggy, Larry, Reznor",
    "boss-6": "plataforma Iggy/Larry, rueda de Reznor (4bpp)",
    "cin-1": "Peach, p-switch pulsado, texto, tiles submarinos",
    "cin-2": "cartel no-yoshi, graficos de final, texto",
    "cin-3": "Peach en la pelea de Bowser",
    "cin-4": "Yoshi/Peach del final",
    "cin-5": "cinematica 5", "cin-6": "cinematica 6", "cin-7": "cinematica 7",
    "cin-8": "cinematica 8",
    "gb-1": "set de caracteres 1, tiles de layer 3, titulo (2bpp)",
    "gb-2": "numeros grandes, titulo (2bpp)",
    "gb-3": "set de caracteres 2 (2bpp)",
    "gb-4": "set de caracteres 3 (2bpp)",
    "gb-5": "set de caracteres 4 (2bpp)",
}


# ===========================================================================
# 1. LC_LZ2
# ===========================================================================
# Cabecera de chunk: CCCLLLLL   (CCC = comando, LLLLL = longitud-1)
# Cabecera $FF = fin de datos.
#   000 Direct Copy     : (L+1) bytes literales
#   001 Byte Fill       : 1 byte repetido (L+1) veces
#   010 Word Fill       : 2 bytes alternados hasta (L+1) bytes
#   011 Increasing Fill : byte inicial, +1 por escritura, (L+1) bytes
#   100 Repeat          : 2 bytes big-endian = offset ABSOLUTO en la salida
#   101/110             : sin usar
#   111 Long Length     : cabecera de 2 bytes: 111CCCLL LLLLLLLL
#
# NOTA: los back-references de "Repeat" apuntan a un offset absoluto en el
# buffer de salida y pueden solaparse consigo mismos -> copiar byte a byte.

CMD_DIRECT, CMD_BYTE_FILL, CMD_WORD_FILL = 0, 1, 2
CMD_INC_FILL, CMD_REPEAT, CMD_LONG = 3, 4, 7


class LZ2Error(Exception):
    pass


def lc_lz2_decompress(data, max_out=1 << 22):
    out = bytearray()
    pos = 0
    n = len(data)

    def need(k):
        if pos + k > n:
            raise LZ2Error("fin de datos inesperado en offset %d" % pos)

    while pos < n:
        header = data[pos]
        pos += 1
        if header == 0xFF:
            break

        cmd = header >> 5
        length = header & 0x1F

        if cmd == CMD_LONG:
            need(1)
            lo = data[pos]
            pos += 1
            cmd = (header >> 2) & 0x07
            length = ((header & 0x03) << 8) | lo
            if cmd == CMD_LONG:
                raise LZ2Error("comando largo anidado en offset %d" % (pos - 2))

        count = length + 1

        if cmd == CMD_DIRECT:
            need(count)
            out += data[pos:pos + count]
            pos += count
        elif cmd == CMD_BYTE_FILL:
            need(1)
            out += bytes([data[pos]]) * count
            pos += 1
        elif cmd == CMD_WORD_FILL:
            need(2)
            pair = data[pos:pos + 2]
            pos += 2
            out += (pair * ((count // 2) + 1))[:count]
        elif cmd == CMD_INC_FILL:
            need(1)
            b = data[pos]
            pos += 1
            out += bytes(((b + i) & 0xFF) for i in range(count))
        elif cmd == CMD_REPEAT:
            need(2)
            offset = (data[pos] << 8) | data[pos + 1]
            pos += 2
            if offset >= len(out):
                raise LZ2Error("back-reference fuera de rango (%d >= %d)"
                               % (offset, len(out)))
            for i in range(count):
                out.append(out[offset + i])
        else:
            raise LZ2Error("comando reservado %d en offset %d" % (cmd, pos - 1))

        if len(out) > max_out:
            raise LZ2Error("salida excede el limite")

    return bytes(out)


# ===========================================================================
# 2. Tiles SNES -> indices de paleta
# ===========================================================================
#   4 bpp (32 B): [f0:BP0 BP1]..[f7:BP0 BP1] [f0:BP2 BP3]..[f7:BP2 BP3]
#   3 bpp (24 B): [f0:BP0 BP1]..[f7:BP0 BP1] [f0..f7:BP2]
#   2 bpp (16 B): [f0:BP0 BP1]..[f7:BP0 BP1]
#   pixel = BP0 | BP1<<1 | BP2<<2 | BP3<<3   (bit 7 = pixel mas a la izq.)

def snes_tile_size(bpp):
    return {2: 16, 3: 24, 4: 32}[bpp]


def decode_snes_tile(tile, bpp):
    rows = []
    for y in range(8):
        if bpp == 4:
            bp = (tile[y * 2], tile[y * 2 + 1], tile[16 + y * 2], tile[16 + y * 2 + 1])
        elif bpp == 3:
            bp = (tile[y * 2], tile[y * 2 + 1], tile[16 + y])
        else:
            bp = (tile[y * 2], tile[y * 2 + 1])

        row = []
        for x in range(8):
            bit = 7 - x
            v = 0
            for p in range(bpp):
                v |= ((bp[p] >> bit) & 1) << p
            row.append(v)
        rows.append(row)
    return rows


def decode_snes_tileset(data, bpp):
    size = snes_tile_size(bpp)
    count = len(data) // size
    return [decode_snes_tile(data[i * size:(i + 1) * size], bpp)
            for i in range(count)]


# ===========================================================================
# 3. Codificador / decodificador planar Amiga
# ===========================================================================
# Bitmap planar: un bloque contiguo por bitplane.
# Tileset de `cols` columnas y `rows` filas de tiles:
#   ancho en bytes = cols          alto en lineas = rows*8
#   tamano de un plano = rows*8*cols
#   pixel (x,y) plano p -> buf[p*H*W + y*W + x//8], bit (7 - x%8)

def encode_amiga_tileset(tiles, cols, planes=4):
    rows = (len(tiles) + cols - 1) // cols
    w = cols
    h = rows * 8
    plane_size = h * w
    buf = bytearray(plane_size * planes)

    for idx, tile in enumerate(tiles):
        tx = (idx % cols) * 8
        ty = (idx // cols) * 8
        for y in range(8):
            for x in range(8):
                v = tile[y][x] & ((1 << planes) - 1)
                for p in range(planes):
                    if (v >> p) & 1:
                        off = p * plane_size + (ty + y) * w + (tx + x) // 8
                        buf[off] |= 0x80 >> ((tx + x) % 8)
    return bytes(buf), cols, rows


def decode_amiga_tileset(blob, cols, rows, planes=4):
    """Inverso de encode_amiga_tileset. Solo para el auto-test."""
    w = cols
    h = rows * 8
    plane_size = h * w
    tiles = []
    for idx in range(rows * cols):
        tx = (idx % cols) * 8
        ty = (idx // cols) * 8
        tile = []
        for y in range(8):
            row = []
            for x in range(8):
                v = 0
                for p in range(planes):
                    off = p * plane_size + (ty + y) * w + (tx + x) // 8
                    if (blob[off] >> (7 - (tx + x) % 8)) & 1:
                        v |= 1 << p
                row.append(v)
            tile.append(row)
        tiles.append(tile)
    return tiles


# ===========================================================================
# 4. Paletas
# ===========================================================================
# SNES: 15 bits BGR555 -> 0bbbbbgg gggrrrrr
# Amiga: registro de 12 bits 0x0RGB

def snes_word_to_rgb8(word):
    r5, g5, b5 = word & 0x1F, (word >> 5) & 0x1F, (word >> 10) & 0x1F
    return (r5 << 3 | r5 >> 2, g5 << 3 | g5 >> 2, b5 << 3 | b5 >> 2)


def snes_word_to_amiga12(word):
    r5, g5, b5 = word & 0x1F, (word >> 5) & 0x1F, (word >> 10) & 0x1F
    return ((r5 >> 1) << 8) | ((g5 >> 1) << 4) | (b5 >> 1)


def parse_palette_file(path):
    palettes, label = {}, None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.split(";")[0].strip()
            if not line:
                continue
            if ":" in line and ".DW" not in line.upper():
                label = line.split(":")[0].strip()
                palettes.setdefault(label, [])
            elif ".DW" in line.upper() and label:
                for tok in line.upper().split(".DW", 1)[1].replace("\t", " ").split(","):
                    tok = tok.strip()
                    if tok.startswith("$"):
                        try:
                            palettes[label].append(int(tok[1:], 16))
                        except ValueError:
                            pass
    return palettes


def write_amiga_palette(words, path, planes=4, title=""):
    limit = 1 << planes
    out = ["; Paleta Amiga generada desde SNES BGR555",
           "; %s" % title,
           "; Formato: move.w #$0RGB,$dff180+2*n   (%d colores)" % limit,
           ""]
    for i, w in enumerate(words[:limit]):
        r, g, b = snes_word_to_rgb8(w)
        out.append("        dc.w    $%03X        ; %2d   SNES $%04X  rgb(%3d,%3d,%3d)"
                   % (snes_word_to_amiga12(w), i, w, r, g, b))
    open(path, "w", encoding="ascii").write("\n".join(out) + "\n")
    return min(len(words), limit)


# ===========================================================================
# 5. Previews
# ===========================================================================
# Paleta "ramp": colores muy distintos por indice. Demuestra que la
# decodificacion es correcta independientemente de la paleta real de SMW.

RAMP = [(0, 0, 0), (255, 255, 255), (210, 60, 60), (60, 200, 60),
        (60, 60, 210), (225, 225, 70), (60, 215, 215), (215, 60, 215),
        (125, 125, 125), (185, 185, 185), (255, 165, 60), (165, 255, 60),
        (60, 165, 255), (255, 60, 165), (110, 70, 25), (205, 205, 165)]


def render_png(tiles, cols, palette_rgb8, path, scale=3, bg=(20, 20, 28)):
    from PIL import Image
    rows = (len(tiles) + cols - 1) // cols
    img = Image.new("RGB", (cols * 8, rows * 8), bg)
    px = img.load()
    for idx, tile in enumerate(tiles):
        tx, ty = (idx % cols) * 8, (idx // cols) * 8
        for y in range(8):
            for x in range(8):
                v = tile[y][x]
                if v < len(palette_rgb8):
                    px[tx + x, ty + y] = palette_rgb8[v]
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(path)
    return img.size


# ===========================================================================
# main
# ===========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_DEF_SRC)
    ap.add_argument("--out", default=_DEF_OUT)
    ap.add_argument("--gfx", nargs="+", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--cols", type=int, default=16)
    ap.add_argument("--planes", type=int, default=4, choices=[3, 4, 5])
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    names = sorted(BPP_TABLE) if (args.all or not args.gfx) else args.gfx

    # --- paletas -----------------------------------------------------------
    pals = parse_palette_file(os.path.join(src, "palettes", "palettes.a"))
    bg_pal = pals.get("PALETTE_Background", [])[:16]
    spr_pal = pals.get("PALETTE_Sprites", [])[:16]
    write_amiga_palette(bg_pal, os.path.join(out, "palette_bg.asm"),
                        args.planes, "PALETTE_Background[0..%d]" % (args.planes ** 2 - 1))
    write_amiga_palette(spr_pal, os.path.join(out, "palette_sprites.asm"),
                        args.planes, "PALETTE_Sprites[0..%d]" % (args.planes ** 2 - 1))

    gfx_dir = os.path.join(src, "graphics")
    report, total_planar = [], 0

    for name in names:
        path = os.path.join(gfx_dir, name + ".lz2")
        if not os.path.exists(path):
            print("  [skip] %s.lz2 no existe" % name)
            continue

        raw = open(path, "rb").read()
        try:
            dec = lc_lz2_decompress(raw)
        except LZ2Error as exc:
            print("  [ERROR] %s: %s" % (name, exc))
            continue

        bpp = BPP_TABLE[name]
        tiles = decode_snes_tileset(dec, bpp)

        # descartar el resto de un tile incompleto (no deberia ocurrir)
        leftover = len(dec) % snes_tile_size(bpp)

        blob, cols, rows = encode_amiga_tileset(tiles, args.cols, args.planes)
        open(os.path.join(out, "%s_%dpl.bin" % (name, args.planes)), "wb").write(blob)

        ok = ""
        if args.selftest:
            back = decode_amiga_tileset(blob, cols, rows, args.planes)
            mask = (1 << args.planes) - 1
            same = all(back[i][y][x] == (tiles[i][y][x] & mask)
                       for i in range(len(tiles))
                       for y in range(8) for x in range(8))
            ok = "OK" if same else "FALLO"
            if not same:
                print("  !! round-trip FALLO en %s" % name)

        render_png(tiles, args.cols, RAMP, os.path.join(out, "%s.png" % name))

        total_planar += len(blob)
        report.append(dict(name=name, bpp=bpp, lz2=len(raw), raw=len(dec),
                           tiles=len(tiles), planar=len(blob),
                           leftover=leftover, roundtrip=ok))

    # --- informe -----------------------------------------------------------
    L = []
    L.append("ETAPA 1 - conversion de assets SMW (SNES) -> Amiga OCS/ECS")
    L.append("=" * 74)
    L.append("")
    L.append("%-8s %4s %8s %8s %7s %10s  %s" %
             ("gfx", "bpp", "lz2 B", "raw B", "tiles", "planar B", "round-trip"))
    L.append("-" * 74)
    for r in report:
        L.append("%-8s %4d %8d %8d %7d %10d  %s" %
                 (r["name"], r["bpp"], r["lz2"], r["raw"], r["tiles"],
                  r["planar"], r["roundtrip"] or "-"))
    L.append("-" * 74)
    L.append("TOTAL planar: %d bytes (%.1f KB)  |  %d planos = %d colores"
             % (total_planar, total_planar / 1024.0, args.planes, 1 << args.planes))
    L.append("")
    L.append("Ficheros procesados: %d de %d" % (len(report), len(names)))
    bad = [r["name"] for r in report if r["roundtrip"] == "FALLO"]
    if args.selftest:
        L.append("Auto-test planar: %s" % ("TODO OK" if not bad
                                           else "FALLOS: %s" % ", ".join(bad)))
    L.append("")
    L.append("Contenido de cada fichero:")
    for r in report:
        L.append("  %-8s %s" % (r["name"], GFX_NOTES.get(r["name"], "")))
    L.append("")
    L.append("Los .bin son tilesets plane-major listos para el blitter.")
    L.append("Los .png usan una paleta 'ramp' para mostrar los indices de color.")

    txt = "\n".join(L) + "\n"
    open(os.path.join(out, "REPORT.txt"), "w", encoding="utf-8").write(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
