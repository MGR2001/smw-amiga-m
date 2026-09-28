#!/bin/sh
# game_build.sh - arma work/game.adf: el juego (player/game.s = el C de la
# logica + player/scroll.s), Etapas 6.3 y 6b.
#
#   sh tools/game_build.sh                       # replay entero (-DREPLAY)
#   GDEFS="-DREPLAY -DSTOPF=1200" OUT=work/g1200 sh tools/game_build.sh
#
# 1. El C: lo compila tools/logicbench_build.sh (work/cc/*.s; arma tambien
#    logicbench, que no molesta).
# 2. Lo que se deriva del ROM y no esta en git (R9): work/yi1_s.dat
#    (mkscroll.py), work/yi1_replay.bin (m68kverify.py --replay, con el
#    binario de logicbench: el mismo C) y work/cc/spr.lv.
# 3. vasm (-Fbin) y mkadf.py con yi1_s.dat detras.
set -e
cd "$(dirname "$0")/.."
VBCC=${VBCC:-/c/Users/JC/vbcc}
X=; [ -f "$VBCC/bin/vasmm68k_mot.exe" ] && X=.exe
PY=${PY:-python}
GDEFS=${GDEFS--DREPLAY}
OUT=${OUT:-work}
mkdir -p "$OUT"
[ -n "$NOCC" ] || sh tools/logicbench_build.sh
[ -f work/cc/spr.lv ] || cp ../smw-src-master/project/mw_e10/levels/data/world_1/1/spr.lv work/cc/spr.lv
[ -f work/yi1_s.dat ] || $PY tools/mkscroll.py
[ -f work/cc/gfx32f.bin ] && [ -f work/cc/mario_pal.bin ] || $PY tools/mkmario.py
if [ ! -f work/yi1_replay.bin ] || [ work/logicbench.bin -nt work/yi1_replay.bin ]; then
    $PY tools/m68kverify.py --mode loop --sprites --replay work/yi1_replay.bin
fi
"$VBCC/bin/vasmm68k_mot$X" -quiet -Fbin -m68000 $GDEFS -I player -I . -L "$OUT/game.lst" \
    -o "$OUT/game.bin" player/game.s
$PY tools/mkadf.py --boot work/boot.bin --stage2 "$OUT/game.bin" --data work/yi1_s.dat \
    --out "$OUT/game.adf"
