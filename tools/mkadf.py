#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mkadf.py - construye un ADF booteable para el port-demo de SMW.

Estructura del disco (sectores de 512 bytes):

    offset 0        bootblock (1024 B = sectores 0-1)
                      "DOS\0" | checksum | longitud_stage2 | codigo
    offset 1024     stage2 (el programa), redondeado a sector
    offset X        datos (tilesets, paletas...), redondeado a sector

El stage2 lleva una cabecera que este script rellena:

    +0   bra.w entry
    +2   "A5PL"          <- magic, aqui se busca
    +6   .l  data_off    <- offset en bytes desde el inicio del disco
    +10  .l  data_len    <- longitud en bytes

Uso:
    python mkadf.py --boot work/boot.bin --stage2 work/demo.bin \
                    --data work/demo.dat --out work/smw.adf
"""

import argparse
import os
import struct
import sys

SECTOR = 512
ADF_SIZE = 80 * 2 * 11 * SECTOR      # 901120 bytes: DD, 80 cilindros
BOOTBLOCK_SIZE = 1024
STAGE2_OFFSET = 1024
MAGIC = b"A5PL"


def align(n, a=SECTOR):
    return (n + a - 1) // a * a


def bootblock_checksum(bb):
    """Suma de 256 longwords big-endian con acarreo circular, complementada.
    El campo del checksum (longword 1) cuenta como cero."""
    total = 0
    for i in range(256):
        if i == 1:
            continue
        v = struct.unpack_from(">I", bb, i * 4)[0]
        old = total
        total = (total + v) & 0xFFFFFFFF
        if total < old:
            total = (total + 1) & 0xFFFFFFFF
    return (~total) & 0xFFFFFFFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", required=True, help="bootblock ensamblado (flat)")
    ap.add_argument("--stage2", required=True, help="programa principal (flat)")
    ap.add_argument("--data", default=None, help="blob de datos (opcional)")
    ap.add_argument("--out", required=True, help="ADF de salida")
    args = ap.parse_args()

    boot = open(args.boot, "rb").read()
    stage2 = open(args.stage2, "rb").read()
    data = open(args.data, "rb").read() if args.data else b""

    if len(boot) > BOOTBLOCK_SIZE:
        sys.exit("el bootblock ocupa %d bytes, el limite es %d"
                 % (len(boot), BOOTBLOCK_SIZE))

    # --- offsets -----------------------------------------------------------
    stage2_len = align(len(stage2))
    data_off = STAGE2_OFFSET + stage2_len
    data_len = align(len(data)) if data else 0

    # --- cabecera del stage2 ----------------------------------------------
    idx = stage2.find(MAGIC)
    if idx < 0:
        sys.exit("no encuentro el magic '%s' en el stage2" % MAGIC.decode())
    stage2 = bytearray(stage2)
    struct.pack_into(">I", stage2, idx + 4, data_off)
    struct.pack_into(">I", stage2, idx + 8, data_len)
    stage2 = bytes(stage2)

    # --- bootblock ---------------------------------------------------------
    bb = bytearray(BOOTBLOCK_SIZE)
    bb[0:len(boot)] = boot
    struct.pack_into(">I", bb, 8, stage2_len)          # longitud a leer
    struct.pack_into(">I", bb, 4, 0)                   # checksum a cero
    struct.pack_into(">I", bb, 4, bootblock_checksum(bb))

    # --- imagen ------------------------------------------------------------
    img = bytearray(ADF_SIZE)
    img[0:BOOTBLOCK_SIZE] = bb
    img[STAGE2_OFFSET:STAGE2_OFFSET + len(stage2)] = stage2
    if data:
        img[data_off:data_off + len(data)] = data

    if data_off + data_len > ADF_SIZE:
        sys.exit("no cabe: los datos acaban en %d, el disco tiene %d"
                 % (data_off + data_len, ADF_SIZE))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    open(args.out, "wb").write(img)

    used = data_off + data_len
    print("ADF      : %s" % args.out)
    print("  bootblock   %5d B  (checksum $%08X)"
          % (BOOTBLOCK_SIZE, struct.unpack_from(">I", bb, 4)[0]))
    print("  stage2      %5d B  @ %d" % (len(stage2), STAGE2_OFFSET))
    print("  datos       %5d B  @ %d" % (len(data), data_off))
    print("  ocupado     %5d B de %d  (%.1f%%)"
          % (used, ADF_SIZE, 100.0 * used / ADF_SIZE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
