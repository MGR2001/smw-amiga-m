#!/usr/bin/env python3
"""
oracle2bin.py - pasa el oraculo grabado por oamrec.py (texto) a un binario
que lee tools/marioverify.c.

Registro (584 bytes): u32 frame (little-endian), u8 translevel, u8 modo,
u16 relleno, WRAM $0000-$00FF (256), WRAM $13C0-$14FF (320).

Ademas, <out sin .bin>_oam.bin, un registro por cada uno del anterior
(645 bytes): u32 frame, u8 n, y n entradas VISIBLES de la OAM (y != $F0)
en orden de slot, 5 bytes cada una: x, y, tile, atributos, tamaño
(wm_ExOamSize/wm_OamSize: bit 0 = bit 8 de la X, bit 1 = 16x16); el resto
a cero hasta 128 entradas.

    python tools/oracle2bin.py [--inp work/oracle_yi1.txt] [--out work/oracle_yi1.bin]
"""
import argparse
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", default=os.path.join(WORK, "oracle_yi1.txt"))
    ap.add_argument("--out", default=os.path.join(WORK, "oracle_yi1.bin"))
    a = ap.parse_args()
    n = 0
    oam_path = a.out[:-4] + "_oam.bin" if a.out.endswith(".bin") else a.out + "_oam"
    with open(a.out, "wb") as f, open(oam_path, "wb") as fo:
        for ln in open(a.inp):
            p = ln.rstrip("\n").split(" ")
            if len(p) < 14 or len(p[12]) != 512 or len(p[13]) != 640:
                continue
            f.write(struct.pack("<IBBH", int(p[0]), int(p[2], 16), int(p[1], 16), 0))
            f.write(bytes.fromhex(p[12]))
            f.write(bytes.fromhex(p[13]))
            oam = bytes.fromhex(p[10]) if len(p[10]) % 10 == 0 else b""
            fo.write(struct.pack("<IB", int(p[0]), len(oam) // 5))
            fo.write(oam.ljust(640, b"\0"))
            n += 1
    print(f"{n} registros -> {a.out}")


if __name__ == "__main__":
    main()
