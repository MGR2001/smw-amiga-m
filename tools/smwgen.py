#!/usr/bin/env python3
"""
smwgen.py - genera lo que el port en C de la logica de SMW necesita, sacado
MECANICAMENTE del codigo fuente y de la ROM (nada copiado a mano):

  player/gen/smwram.h    #define de cada variable de RAM (m0-m15, wm_*) con
                         su direccion, de equates/memory.i
  player/gen/smwtab.h    #define de cada tabla de player.s con su direccion
                         en la ROM: DATA_bbaaaa por el nombre; las tablas
                         con nombre propio (MarioAccel...) buscando sus bytes
                         en el banco 00 (tiene que haber UNA coincidencia)
  player/gen/smwrom00.c  la mitad alta del banco 00 de la ROM
                         ($00:C000-$00:FFFF, ROM00_BASE en smwtab.h): ahi
                         estan las tablas de fisica de Mario. Solo 16 KB para
                         que, con ram[], quepa en el direccionamiento de
                         16 bits relativo a a4 del modelo small-data de vbcc

El fuente (smw-src-master) ensambla una ROM identica a la (U), la misma que
corre smwrecomp, asi que las direcciones de las etiquetas son las reales.

    python tools/smwgen.py [--rom ../smwre/smw.sfc]
"""
import argparse
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "smw-src-master", "project", "mw_e10")
OUT = os.path.join(HERE, "..", "player", "gen")


def parse_ram():
    out = []
    for ln in open(os.path.join(SRC, "equates", "memory.i"), encoding="latin-1"):
        m = re.match(r"^(m\d+|wm_\w+)\s+(?:DB|DW|DL|DS\b[^;]*|INSTANCEOF\b[^;]*)\s*;\s*\$([0-9A-Fa-f]+)", ln)
        if m:
            out.append((m.group(1), int(m.group(2), 16)))
    return out


def num(tok):
    tok = tok.strip()
    if tok.startswith("$"):
        return int(tok[1:], 16)
    if tok.startswith("%"):
        return int(tok[1:], 2)
    return int(tok)


def parse_tables(path):
    """{etiqueta: bytes} de las tablas .DB/.DW que siguen a cada etiqueta."""
    tabs = {}
    cur = None
    for ln in open(path, encoding="latin-1"):
        code = ln.split(";")[0]
        m = re.match(r"^([A-Za-z_]\w*):(.*)$", code)
        if m:
            cur = m.group(1)
            code = m.group(2)
            tabs.setdefault(cur, bytearray())
        if cur is None:
            continue
        d = re.match(r"^\s*\.(DB|DW)\s+(.*)$", code)
        if d:
            try:
                vals = [num(t) for t in d.group(2).split(",") if t.strip()]
            except ValueError:
                tabs[cur] = None           # expresiones / etiquetas: no se usa
                cur = None
                continue
            if tabs[cur] is None:
                continue
            for v in vals:
                if d.group(1) == "DB":
                    tabs[cur].append(v & 0xFF)
                else:
                    tabs[cur] += bytes([v & 0xFF, (v >> 8) & 0xFF])
        elif code.strip():
            if tabs.get(cur) is not None and len(tabs[cur]) == 0:
                del tabs[cur]
            cur = None
    return {k: bytes(v) for k, v in tabs.items() if v}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(HERE, "..", "..", "smwre", "smw.sfc"))
    a = ap.parse_args()
    rom = open(a.rom, "rb").read()
    rom = rom[len(rom) % 1024:]
    bank0 = rom[0:0x8000]
    os.makedirs(OUT, exist_ok=True)

    ram = parse_ram()
    with open(os.path.join(OUT, "smwram.h"), "w") as f:
        f.write("/* GENERADO por tools/smwgen.py desde equates/memory.i: no editar */\n")
        f.write("#ifndef SMWRAM_H\n#define SMWRAM_H\n")
        for n, adr in ram:
            f.write("#define %-28s 0x%04X\n" % (n, adr))
        f.write("#endif\n")

    tabs = parse_tables(os.path.join(SRC, "player.s"))
    defs = []
    ambiguous = []
    for n, data in sorted(tabs.items()):
        m = re.match(r"^(?:DATA|ADDR)_([0-9A-F]{6})$", n)
        if m:
            adr = int(m.group(1), 16)
            if adr >> 16 == 0 and adr >= 0xC000 and bank0[adr - 0x8000:adr - 0x8000 + len(data)] == data:
                defs.append((n, adr))
            else:
                ambiguous.append((n, "no coincide con la ROM"))
            continue
        hits = [i for i in range(len(bank0) - len(data) + 1)
                if bank0[i:i + len(data)] == data] if len(data) >= 3 else []
        if len(hits) == 1:
            if 0x8000 + hits[0] >= 0xC000:
                defs.append((n, 0x8000 + hits[0]))
            else:
                ambiguous.append((n, "fuera de $C000-$FFFF"))
        else:
            ambiguous.append((n, "%d coincidencias" % len(hits)))
    with open(os.path.join(OUT, "smwtab.h"), "w") as f:
        f.write("/* GENERADO por tools/smwgen.py: direcciones SNES ($00:xxxx) de las\n"
                "   tablas de player.s, verificadas contra la ROM. No editar. */\n")
        f.write("#ifndef SMWTAB_H\n#define SMWTAB_H\n")
        f.write("#define ROM00_BASE 0xC000   /* rom00[] empieza en $00:C000 */\n")
        for n, adr in defs:
            f.write("#define %-28s 0x%04X\n" % (n, adr))
        f.write("#endif\n")
    with open(os.path.join(OUT, "smwrom00.c"), "w") as f:
        f.write("/* GENERADO por tools/smwgen.py: banco 00 de la ROM de SMW (U).\n"
                "   Sale de la ROM del usuario; no se distribuye. */\n")
        f.write("const unsigned char rom00[0x4000] = {\n")
        for i in range(0x4000, 0x8000, 16):
            f.write("  " + ",".join("%d" % b for b in bank0[i:i + 16]) + ",\n")
        f.write("};\n")
    print("smwram.h : %d variables" % len(ram))
    print("smwtab.h : %d tablas con direccion verificada" % len(defs))
    if ambiguous:
        print("sin direccion (no usar sin revisar):", ", ".join("%s (%s)" % x for x in ambiguous[:12]),
              "..." if len(ambiguous) > 12 else "")


if __name__ == "__main__":
    main()
