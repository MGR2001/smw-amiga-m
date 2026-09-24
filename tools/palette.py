#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
palette.py - Reconstruye el CGRAM real de SMW emulando LoadPalette.

El layout de paletas de SMW NO es un array plano 8x16.  La rutina
`LoadPalette` (game.s:5039) escribe sub-paletas de 6 colores en huecos
concretos del CGRAM usando tres parametros:

    m0 = puntero al blob fuente (avanza CONTIGUAMENTE entre pasadas)
    m4 = offset en BYTES dentro del shadow de CGRAM (avanza +$20 por pasada,
         o sea una fila de 16 colores)
    m6 = n_colores - 1
    m8 = n_pasadas - 1

    LoadColors:
        X = m4
        Y = m6
        bucle:  A = (m0); wm_Palette[X] = A;  m0 += 2; X += 2;  Y--; BPL
                m4 += $20
                m8--; BPL LoadColors

    LoadCol8Pal(value, X): escribe `value` en X, X+$20, ..., X+$E0 (8 filas)

Resultado (layout de SMW en CGRAM):

    color 0 de cada paleta  = transparente / color de fondo
    color 1 de cada paleta  = $7FDD (BG) / $7FFF (sprites)  -> "blanco"
    BG pal 0,1  col 2..7    <- PALETTE_Background[bgpal]   (fondo de nivel)
    BG pal 0,1  col 8..15   <- PALETTE_Layer3              (Layer 3)
    BG pal 2,3  col 2..7    <- PALETTE_Foreground[fgpal]   (terreno)
    BG pal 4..7 col 2..7    <- PALETTE_Objects[0..3]       (objetos comunes)
    spr pal 0..5 col 2..7   <- PALETTE_Objects[4..9]
    spr pal 6,7 col 2..7    <- PALETTE_Sprites[sprpal]     (Mario, enemigos)
    pal 2,3,4 col 9         <- PALETTE_YoshiBerry          (color de baya)
    pal 9,10,11 col 9       <- PALETTE_YoshiBerry

Uso:
    python palette.py --dump                       # tabla de las 16 paletas
    python palette.py --swatch                     # PNG con las 256 entradas
    python palette.py --tiles chr --pal 4          # render de chr.lz2
"""

import argparse
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEF_SRC = os.path.normpath(os.path.join(_HERE, "..", "..", "smw-src-master",
                                         "project", "mw_e10"))

# ---------------------------------------------------------------------------
# Parser del banco de paletas
# ---------------------------------------------------------------------------
# palettes.a es un unico blob continuo con etiquetas intercaladas.  Hay que
# leerlo EN ORDEN: PALETTE_Objects, por ejemplo, solo declara 36 palabras
# (6 grupos) pero la rutina lee 60 -> las otras 24 viven tras las etiquetas
# DATA_B298 / DATA_B2A4 / DATA_B2BC que hay en medio.

_LABEL_RE = re.compile(r"^\s*([A-Za-z_@][A-Za-z0-9_@]*)\s*:")
_WORD_RE = re.compile(r"\$([0-9A-Fa-f]{1,4})")


def load_palette_bank(path):
    """Devuelve (words, labels): el banco plano y etiqueta -> indice de palabra."""
    words, labels = [], {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.split(";")[0]
            if not line.strip():
                continue
            m = _LABEL_RE.match(line)
            if m:
                labels[m.group(1)] = len(words)
                line = line[m.end():]
            if ".DW" not in line.upper():
                continue
            for tok in line.upper().split(".DW", 1)[1].replace("\t", " ").split(","):
                tok = tok.strip()
                if tok.startswith("$"):
                    try:
                        words.append(int(tok[1:], 16) & 0xFFFF)
                    except ValueError:
                        pass
    return words, labels


# ---------------------------------------------------------------------------
# Emulacion exacta de las rutinas 65816
# ---------------------------------------------------------------------------

def load_colors(cgram, bank, m0, m4, m6, m8):
    """game.s:5157 LoadColors.  m0 indice de PALABRA, m4 offset en BYTES."""
    s, base = m0, m4
    for _ in range(m8 + 1):
        d = base
        for _ in range(m6 + 1):
            cgram[(d >> 1) & 0xFF] = bank[s] & 0xFFFF
            s += 1
            d += 2
        base = (base + 0x20) & 0xFFFF
    return s


def load_col8pal(cgram, value, x):
    """game.s:5145 LoadCol8Pal: mismo valor en 8 filas consecutivas."""
    for i in range(8):
        cgram[((x + i * 0x20) >> 1) & 0xFF] = value & 0xFFFF


# DATA_00ABD3 (game.s:5026): offset en BYTES al sub-paleta dentro del blob.
# Los 8 primeros son de 12 palabras; los 4 ultimos de 10 palabras.
DATA_00ABD3 = [0x00, 0x18, 0x30, 0x48, 0x60, 0x78, 0x90, 0xA8,
               0x00, 0x14, 0x28, 0x3C]

# ---------------------------------------------------------------------------
# Animacion de la MONEDA DE YOSHI
# ---------------------------------------------------------------------------
# `CODE_00A418` (game.s:4148) corre TODOS los frames y hace:
#     LDA #$64 / STA CGADD          ; $64 = indice de palabra $32 = pal 6 color 4
#     LDA wm_FrameB / AND #$1C / LSR
#     TAY / LDA PALETTE_Flashing,Y / STA CGDATAW
# O sea: el color 4 de la paleta 6 **no** es el $7C3F que carga
# `PALETTE_Objects` (palettes.a:58, un magenta), sino un valor animado que
# sale de `PALETTE_Flashing` (palettes.a:157, fila "Yellow").
# Con Y = 0,2,4,...,14 los 8 pasos son:
COIN_ANIM = [0x02DF, 0x27FF, 0x73FF, 0x27FF,
             0x01BF, 0x001B, 0x0018, 0x001F]
# Paso que capturo la referencia de SNES (`SuperMarioWorldMap02.png`):
# sus monedas tienen $27FF, o sea el paso 1 (o el 3, que es igual).
COIN_ANIM_REF = 1


def build_cgram(bank, labels, fgpal=0, bgpal=0, sprpal=0, bgcol=0,
                coin_frame=COIN_ANIM_REF):
    """Reproduce LoadPalette.  Devuelve (cgram[256], color_de_fondo)."""
    cgram = [0] * 256

    def sub(label):
        if label not in labels:
            raise KeyError("etiqueta %r no encontrada en palettes.a" % label)
        return labels[label]

    # 1. color 1 de todas las paletas (el "blanco" universal)
    load_col8pal(cgram, 0x7FDD, 0x0002)     # BG  paletas 0-7
    load_col8pal(cgram, 0x7FFF, 0x0102)     # spr paletas 0-7

    # 2. Layer 3 -> color 8..15 de las paletas 0 y 1
    load_colors(cgram, bank, sub("PALETTE_Layer3"), 0x0010, 7, 1)

    # 3. Objetos comunes: 10 grupos de 6 -> BG pal 4-7 + spr pal 0-5
    load_colors(cgram, bank, sub("PALETTE_Objects"), 0x0084, 5, 9)

    # 4. color de fondo (escalar, no va al CGRAM)
    bg_color = bank[sub("PALETTE_Sky") + (bgcol & 0x0F)]

    # 5. Terreno: 2 grupos -> BG pal 2 y 3
    off = DATA_00ABD3[fgpal & 0x0F]
    load_colors(cgram, bank, sub("PALETTE_Foreground") + (off >> 1), 0x0044, 5, 1)

    # 6. Sprites: 2 grupos -> spr pal 6 y 7
    off = DATA_00ABD3[sprpal & 0x0F]
    load_colors(cgram, bank, sub("PALETTE_Sprites") + (off >> 1), 0x01C4, 5, 1)

    # 7. Fondo del nivel: 2 grupos -> BG pal 0 y 1
    off = DATA_00ABD3[bgpal & 0x0F]
    load_colors(cgram, bank, sub("PALETTE_Background") + (off >> 1), 0x0004, 5, 1)

    # 8. Bayas de Yoshi (3 grupos) en BG pal 2-4 y spr pal 1-3, color 9
    load_colors(cgram, bank, sub("PALETTE_YoshiBerry"), 0x0052, 5, 2)
    load_colors(cgram, bank, sub("PALETTE_YoshiBerry"), 0x0132, 5, 2)

    # 9. Animacion de la moneda de Yoshi: pisa el color 4 de la paleta 6.
    cgram[6 * 16 + 4] = COIN_ANIM[coin_frame % len(COIN_ANIM)]

    return cgram, bg_color


# ---------------------------------------------------------------------------
# Conversion de color
# ---------------------------------------------------------------------------

def snes_to_rgb8(word):
    """BGR555 -> (r,g,b) 0..255."""
    r, g, b = word & 0x1F, (word >> 5) & 0x1F, (word >> 10) & 0x1F
    return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2)


def snes_to_amiga12(word):
    """BGR555 -> registro Amiga 0x0RGB (4 bits por canal)."""
    r, g, b = word & 0x1F, (word >> 5) & 0x1F, (word >> 10) & 0x1F
    return ((r >> 1) << 8) | ((g >> 1) << 4) | (b >> 1)


def cgram_palette(cgram, index):
    """Los 16 colores de la paleta `index` (0-15) del CGRAM."""
    return cgram[index * 16:(index + 1) * 16]


# ---------------------------------------------------------------------------
# Salidas
# ---------------------------------------------------------------------------

def dump_table(cgram, bg_color):
    L = []
    L.append("CGRAM reconstruido (emulando LoadPalette)")
    L.append("=" * 78)
    L.append("Color de fondo (wm_LvBgColor) = $%04X  rgb%s"
             % (bg_color, snes_to_rgb8(bg_color)))
    L.append("")
    for p in range(16):
        cols = cgram_palette(cgram, p)
        kind = "BG " if p < 8 else "SPR"
        L.append("paleta %2d (%s %d):" % (p, kind, p if p < 8 else p - 8))
        L.append("   " + " ".join("$%04X" % c for c in cols))
        L.append("   " + " ".join("%02X%02X%02X" % snes_to_rgb8(c) for c in cols))
    return "\n".join(L)


def make_swatch(cgram, path, cell=26, label_w=34, head_h=20):
    """PNG con las 256 entradas del CGRAM (16 filas x 16 columnas).

    Cada fila es una paleta; cada columna un indice dentro de ella.  Los
    indices se numeran 0-F arriba y las paletas 0-15 a la izquierda.
    """
    from PIL import Image, ImageDraw
    W = label_w + 16 * cell + 4
    H = head_h + 16 * cell + 4
    img = Image.new("RGB", (W, H), (26, 26, 32))
    d = ImageDraw.Draw(img)
    for i in range(16):
        d.text((label_w + i * cell + cell // 2 - 3, 5), "%X" % i, fill=(200, 200, 210))
    for p in range(16):
        y0 = head_h + p * cell
        kind = "BG " if p < 8 else "SPR"
        d.text((2, y0 + cell // 2 - 5), "%2d %s%d" % (p, kind, p if p < 8 else p - 8),
               fill=(200, 200, 210))
        for i in range(16):
            r, g, b = snes_to_rgb8(cgram[p * 16 + i])
            x0 = label_w + i * cell
            d.rectangle([x0, y0, x0 + cell - 3, y0 + cell - 3], fill=(r, g, b))
    img.save(path)
    return img.size


def write_amiga_asm(cgram, path, level_desc="", planes=4):
    """Vuelca las 16 paletas del CGRAM como `dc.w $0RGB` listo para el copper."""
    L = ["; Paletas de SMW reconstruidas emulando LoadPalette (game.s:5039)",
         "; %s" % level_desc,
         ";",
         "; Uso en el copper list:",
         ";   dc.w  $0180,$0000   ; COLOR00 = transparente",
         ";   ...",
         ";",
         "; Formato Amiga: $0RGB (4 bits por canal, 4096 colores)"]
    for p in range(16):
        cols = cgram_palette(cgram, p)
        kind = "BG " if p < 8 else "SPR"
        L.append("")
        L.append("; --- paleta %d (%s%d) ---" % (p, kind, p if p < 8 else p - 8))
        for i, w in enumerate(cols):
            r, g, b = snes_to_rgb8(w)
            L.append("        dc.w    $%03X        ; %2d  SNES $%04X  rgb(%3d,%3d,%3d)"
                     % (snes_to_amiga12(w), i, w, r, g, b))
    open(path, "w", encoding="ascii").write("\n".join(L) + "\n")
    return path


def render_tiles(tiles, cols, palette_rgb8, path, scale=3, bg=(30, 30, 36)):
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


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_DEF_SRC)
    ap.add_argument("--out", default=os.path.join(_HERE, "..", "work"))
    ap.add_argument("--fgpal", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--bgpal", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--sprpal", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--bgcol", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--level", default=None,
                    help="header de 5 bytes en hex, p.ej. 3340088027")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--swatch", action="store_true")
    ap.add_argument("--asm", action="store_true",
                    help="vuelca las 16 paletas como dc.w $0RGB para el copper")
    ap.add_argument("--tiles", default=None, help="nombre de gfx, p.ej. chr")
    ap.add_argument("--pal", type=int, default=None,
                    help="paleta 0-15 para el render de tiles")
    ap.add_argument("--allpals", action="store_true",
                    help="montaje de los tiles con las 16 paletas")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    bank_path = os.path.join(os.path.abspath(args.src), "palettes", "palettes.a")
    bank, labels = load_palette_bank(bank_path)

    fg, bg, sp, bc = args.fgpal, args.bgpal, args.sprpal, args.bgcol
    if args.level:
        h = bytes.fromhex(args.level)
        bg = h[0] >> 5
        bc = h[1] >> 5
        fg = h[3] & 0x07
        sp = (h[3] >> 3) & 0x07

    cgram, bg_color = build_cgram(bank, labels, fg, bg, sp, bc)
    print("banco de paletas: %d palabras, %d etiquetas" % (len(bank), len(labels)))
    print("header: FgPal=%d BgPal=%d SprPal=%d BgCol=%d" % (fg, bg, sp, bc))

    if args.dump or not (args.swatch or args.tiles):
        txt = dump_table(cgram, bg_color)
        print(txt)
        open(os.path.join(out, "cgram.txt"), "w", encoding="utf-8").write(txt + "\n")

    if args.swatch:
        p = os.path.join(out, "cgram_swatch.png")
        print("swatch ->", p, make_swatch(cgram, p))

    if args.asm:
        p = os.path.join(out, "palette_cgram.asm")
        desc = ("nivel con FgPal=%d BgPal=%d SprPal=%d BgCol=%d"
                % (fg, bg, sp, bc))
        if args.level:
            desc = "header %s (%s)" % (args.level, desc)
        print("asm ->", write_amiga_asm(cgram, p, desc))

    if args.tiles:
        sys.path.insert(0, _HERE)
        from smw2amiga import (lc_lz2_decompress, decode_snes_tileset, BPP_TABLE)
        gfx = os.path.join(os.path.abspath(args.src), "graphics",
                           args.tiles + ".lz2")
        dec = lc_lz2_decompress(open(gfx, "rb").read())
        tiles = decode_snes_tileset(dec, BPP_TABLE[args.tiles])
        print("%s: %d tiles @ %d bpp" % (args.tiles, len(tiles), BPP_TABLE[args.tiles]))

        if args.allpals:
            from PIL import Image
            mont = Image.new("RGB", (16 * 8 * 8 * 2, 1), (30, 30, 36))
            paths = []
            for p in range(16):
                rgb = [snes_to_rgb8(c) for c in cgram_palette(cgram, p)]
                f = os.path.join(out, "tiles_%s_pal%02d.png" % (args.tiles, p))
                render_tiles(tiles[:64], 8, rgb, f, scale=2)
                paths.append(f)
            # montaje vertical de los 16 renders
            imgs = [Image.open(p) for p in paths]
            w = max(i.width for i in imgs)
            h = sum(i.height for i in imgs)
            sheet = Image.new("RGB", (w, h), (30, 30, 36))
            y = 0
            for i in imgs:
                sheet.paste(i, (0, y))
                y += i.height
            sp_path = os.path.join(out, "tiles_%s_allpals.png" % args.tiles)
            sheet.save(sp_path)
            print("montaje 16 paletas ->", sp_path, sheet.size)
        else:
            p = args.pal if args.pal is not None else 4
            rgb = [snes_to_rgb8(c) for c in cgram_palette(cgram, p)]
            f = os.path.join(out, "tiles_%s_pal%02d.png" % (args.tiles, p))
            print("tiles ->", f, render_tiles(tiles, 16, rgb, f, scale=3))

    return 0


if __name__ == "__main__":
    sys.exit(main())
