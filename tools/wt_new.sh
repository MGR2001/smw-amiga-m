#!/bin/sh
# wt_new.sh - un worktree listo para que un subagente trabaje en paralelo
# (SUBAGENTES.md). Compilar escribe en work/ (marioverify, logicbench.bin,
# game.bin...): dos agentes en el mismo arbol se pisan. Cada tarea va en su
# worktree, al lado del repo (asi ../smw-src-master sigue en su sitio), con
# work/ y player/gen/ copiados (lo que no esta en git, R9).
#
#   sh tools/wt_new.sh <nombre>        # ../wt-<nombre>, rama wt/<nombre> desde HEAD
#   sh tools/wt_new.sh --rm <nombre>   # lo borra (con la rama, si ya esta integrada)
#
# Imprime lo que el subagente tiene que exportar (FSUAE_BASE y FSUAE_DISPLAY
# propios: P76).
set -e
cd "$(dirname "$0")/.."
ROOT=$(pwd)
if [ "$1" = "--rm" ]; then
    N=$2; W="$ROOT/../wt-$N"
    [ -n "$N" ] || { echo "falta el nombre"; exit 1; }
    git worktree remove --force "$W"
    if git merge-base --is-ancestor "wt/$N" HEAD; then
        git branch -q -D "wt/$N" && echo "wt/$N borrada (estaba integrada)"
    else
        echo "AVISO: wt/$N NO esta integrada en HEAD: la rama queda"
    fi
    exit 0
fi
N=$1
[ -n "$N" ] || { echo "uso: sh tools/wt_new.sh <nombre>"; exit 1; }
W="$ROOT/../wt-$N"
[ -e "$W" ] && { echo "ya existe $W"; exit 1; }
[ -f work/smw.sfc ] || { echo "falta work/smw.sfc: sh tools/setup_cloud.sh primero"; exit 1; }
git worktree add -q "$W" -b "wt/$N" HEAD
mkdir -p "$W/work" "$W/player/gen"
# work/ entero menos las capturas y los directorios de corridas viejas
tar -C work --exclude='./caps' --exclude='./g[0-9]*' --exclude='./dt*' --exclude='./prof' \
    -cf - . | tar -C "$W/work" -xf -
cp -a player/gen/. "$W/player/gen/"
D=$(( 70 + $(printf '%s' "$N" | cksum | cut -d' ' -f1) % 20 ))
W=$(cd "$W" && pwd)
echo "worktree: $W (rama wt/$N)"
echo "  cd $W && export VBCC=\$HOME/vbcc PY=python3 FSUAE_BASE=/tmp/fsuae-$N FSUAE_DISPLAY=:$D"
echo "  python3 tools/lint_port.py && python3 tools/regress.py   # tiene que dar OK antes de empezar"
