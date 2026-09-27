#!/bin/sh
# logicbench_build.sh - arma work/logicbench.adf (etapa 8d: coste del frame
# del jugador en la Amiga: colision 8b + fisica 8a + animacion). Ver
# player/logicbench.s.
#
#   sh tools/logicbench_build.sh
#
# 1. vbcc compila el C con codigo relativo al PC (-sc), datos relativos a a4
#    (-sd) y las tablas const como datos (-const-in-data).
# 2. Cada .s de vbcc se parte en DATOS (data/bss) y CODIGO. Con -sd, cada
#    dato se direcciona como simbolo(a4) con un desplazamiento de 16 bits, y
#    a4 = inicio del binario: los datos tienen que quedar en los primeros
#    32 KB. Por eso el arnes incluye primero todos los datos y despues todo
#    el codigo (y el mapa del nivel, que el C lee por puntero).
# 3. vasm arma un binario plano (una sola seccion) y mkadf.py lo pone detras
#    del bootblock.
#
#   PROF=1 sh tools/logicbench_build.sh    variante para tools/m68kprof.py:
#       sin inline y sin "static" (cada funcion con su simbolo), en
#       work/prof/logicbench.{bin,lst}. NO sirve para medir la 8d.
set -e
cd "$(dirname "$0")/.."
VBCC=${VBCC:-/c/Users/JC/vbcc}
X=; [ -f "$VBCC/bin/vbccm68k.exe" ] && X=.exe
OUT=work; CC=work/cc; EXTRA=
if [ -n "$PROF" ]; then
    OUT=work/prof; CC=work/prof/cc; EXTRA=-inline-size=0
fi
mkdir -p $CC
for f in mario mcoll manim mgfx mcam msprite gen/smwrom00; do
    b=$(basename $f)
    src=player/$f.c
    if [ -n "$PROF" ]; then
        sed -E 's/^static ((const )?(void|u8|int|unsigned|u16) \*?[a-z_0-9]+\()/\1/' player/$f.c > $CC/$b.c
        src=$CC/$b.c
    fi
    "$VBCC/bin/vbccm68k$X" -quiet -c99 -cpu=68000 -O=991 $EXTRA -sc -sd -const-in-data \
        -Iplayer -o=$CC/$b.s $src
    # las etiquetas locales de vbcc (l12...) se repiten entre ficheros
    sed -i -E "s/\bl([0-9]+)\b/${b}_l\1/g" $CC/$b.s
    rm -f $CC/$b.data.s $CC/$b.code.s
    awk -v D=$CC/$b.data.s -v C=$CC/$b.code.s '
        /^\tsection\t/ { mode = ($0 ~ /,code$/) ? "c" : "d"; next }
        { if (mode == "d") print > D; else print > C }
    ' $CC/$b.s
    touch $CC/$b.data.s $CC/$b.code.s
done
# El binario se carga en cualquier direccion: el codigo del C solo puede
# llegar a sus datos por (a4) y a su codigo por (pc)/bsr. vbcc puede emitir
# una referencia ABSOLUTA sin avisar (paso con rom00 - $C000 en smwmac.h:
# "lea 108592+_rom00,a0"), y vasm -Fbin la acepta: aca se para.
if grep -nE '(^|[^(])\b[0-9]*\+?_[A-Za-z_][A-Za-z0-9_]*(\+[0-9]+)?,' $CC/*.code.s \
        | grep -vE '\((a4|pc)\)|_[A-Za-z0-9_]*\(a4\)|,(d[0-7]|a[0-7])\)' \
        | grep -E '\b(lea|move|pea|add|sub|cmp|and|or|tst|clr)' ; then
    echo "ERROR: referencia absoluta a un simbolo en el codigo del C (ver arriba)"; exit 1
fi
# lo mismo con las etiquetas locales de vbcc renombradas (msprite_l34): el
# patron de arriba no las ve ("move.l #msprite_l34,d3" salio al desenrollar
# init_sprite_tables con el vbcc de 2022)
if grep -nE "$(printf '\t')(move|add|sub|cmp|lea|pea)(\.[bwl])?$(printf '\t')#[a-z0-9]+_l[0-9]+" $CC/*.code.s; then
    echo "ERROR: referencia absoluta a una etiqueta local del C (ver arriba)"; exit 1
fi
[ -f work/yi1_map16.bin ] || python tools/mkmapbin.py
# el arnes incluye work/cc/*.s: en PROF, una copia que apunta a work/prof/cc
HARNESS=player/logicbench.s
if [ -n "$PROF" ]; then
    sed 's#"work/cc/\([a-z0-9]*\)\.\(data\|code\)\.s"#"work/prof/cc/\1.\2.s"#' player/logicbench.s > work/prof/logicbench.s
    HARNESS=work/prof/logicbench.s
fi
"$VBCC/bin/vasmm68k_mot$X" -quiet -Fbin -m68000 $LBDEFS -I player -I . -L $OUT/logicbench.lst \
    -o $OUT/logicbench.bin $HARNESS
[ -n "$PROF" ] || python tools/mkadf.py --boot work/boot.bin --stage2 work/logicbench.bin --out work/logicbench.adf
