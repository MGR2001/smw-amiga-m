#!/bin/sh
# logicbench_build.sh - arma work/logicbench.adf (etapa 8d: coste de la
# fisica de Mario en la Amiga). Ver player/logicbench.s.
#
#   sh tools/logicbench_build.sh
#
# 1. vbcc compila el C con codigo relativo al PC (-sc), datos relativos a a4
#    (-sd) y las tablas const como datos (-const-in-data).
# 2. Las secciones de vbcc (CODE, __MERGED data/bss) se juntan en "CODE".
# 3. vasm arma un binario plano con el arnes (derivado de bench2.s) + el C,
#    y mkadf.py lo pone detras del bootblock.
set -e
cd "$(dirname "$0")/.."
VBCC=/c/Users/JC/vbcc
mkdir -p work/cc
for f in mario gen/smwrom00; do
    b=$(basename $f)
    "$VBCC/bin/vbccm68k.exe" -quiet -c99 -cpu=68000 -O=991 -sc -sd -const-in-data \
        -Iplayer -o=work/cc/$b.s player/$f.c
    # todo (codigo, datos, bss) a UNA seccion: con -Fbin cada seccion
    # empezaria en 0 y se pisarian; y con a4 = inicio del binario, el
    # desplazamiento de cada dato es su posicion en el fichero.
    sed -i -E 's/^\tsection\t"[^"]*",(code|data|bss)/\tsection\t"CODE",code/' work/cc/$b.s
done
"$VBCC/bin/vasmm68k_mot.exe" -Fbin -m68000 -I player -I . -L work/logicbench.lst \
    -o work/logicbench.bin player/logicbench.s
python tools/mkadf.py --boot work/boot.bin --stage2 work/logicbench.bin --out work/logicbench.adf
