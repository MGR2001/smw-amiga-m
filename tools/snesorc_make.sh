#!/bin/sh
# snesorc_make.sh - regenera los oraculos guionizados (tools/snesorc/*.orc)
# con work/snesorc, los pasa a binario y corre marioverify sobre cada uno.
# Con --replay, ademas valida el generador reproduciendo los dos tramos de
# Yoshi's Island 1 de work/oracle_yi1.txt (grabados en smwrecomp): tienen
# que salir identicos linea a linea.
#
#   sh tools/snesorc_setup.sh        # una vez por contenedor
#   sh tools/snesorc_make.sh         # todos los guiones
#   sh tools/snesorc_make.sh hills   # uno
#   sh tools/snesorc_make.sh --replay
#
# Los .txt que salen son deterministas: si difieren de los de git, cambio
# el guion, el driver o la version de snesrev (git diff --stat work/).
set -e
HERE=$(cd "$(dirname "$0")/.." && pwd)
cd "$HERE"
[ -x work/snesorc ] || { echo "falta work/snesorc: sh tools/snesorc_setup.sh"; exit 1; }
[ -x work/marioverify ] || { echo "falta work/marioverify (sh tools/setup_cloud.sh)"; exit 1; }

if [ "$1" = "--replay" ]; then
    for seg in 1 2; do
        work/snesorc --script tools/snesorc/boot_yi1.orc --replay work/oracle_yi1.txt \
            --replay-seg $seg --out work/replay_yi1_$seg.txt 2>/dev/null
    done
    python3 - <<'EOF'
ref = {}
for ln in open('work/oracle_yi1.txt'):
    p = ln.rstrip('\n').split(' ')
    ref[p[0]] = ln
n = same = 0
for s in (1, 2):
    for ln in open('work/replay_yi1_%d.txt' % s):
        n += 1
        same += ref.get(ln.split(' ')[0]) == ln
print('[replay] lineas de oracle_yi1 (translevel $29) reproducidas: %d identicas de %d' % (same, n))
EOF
    exit 0
fi

NAMES=$*
[ -n "$NAMES" ] || NAMES=$(ls tools/snesorc/*.orc | xargs -n1 basename | sed 's/\.orc$//' | grep -v '^boot_')
for n in $NAMES; do
    work/snesorc --script tools/snesorc/$n.orc --out work/oracle_$n.txt 2>&1 | tail -1
    python3 tools/oracle2bin.py --inp work/oracle_$n.txt --out work/oracle_$n.bin >/dev/null
    echo "== $n"
    work/marioverify work/oracle_$n.bin full | grep -e 'TODOS' -e '^frames con'
    work/marioverify work/oracle_$n.bin gfx work/oracle_${n}_oam.bin | tail -1
    work/marioverify work/oracle_$n.bin loop | tail -3
    work/marioverify work/oracle_$n.bin game | tail -3
done
