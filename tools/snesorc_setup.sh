#!/bin/sh
# snesorc_setup.sh - prepara el generador de oraculos sin usuario (Etapa 8.1).
#
# Clona snesrev/smw FUERA del repo (~/.cache/snesrev-smw, o $SNESREV_DIR),
# en un commit fijo, saca sus assets de la ROM, compila sus objetos y enlaza
# nuestro driver tools/snesorc/orc.c en work/snesorc.  Nada de snesrev ni
# de la ROM entra en el repo (R9): solo este script y el driver.
#
#   sh tools/snesorc_setup.sh            # ~1 min la primera vez, ~2 s despues
#   work/snesorc --script tools/snesorc/yi1_normal.orc --out work/oracle_normal.txt
#
# Necesita work/smw.sfc (ROM (U), SHA-1 6b47bb75..., la misma que CRC32
# B19ED489; setup_cloud.sh la ensambla desde el fuente), git, gcc, python3
# y libsdl2-dev (solo para compilar los objetos de snesrev; no abre ventana).
set -e
HERE=$(cd "$(dirname "$0")/.." && pwd)
SRC=${SNESREV_DIR:-$HOME/.cache/snesrev-smw}
COMMIT=eae20c65c58930c8b62c76188d259579ad4130f1
ROM=$HERE/work/smw.sfc
SHA1=6b47bb75d16514b6a476aa0c73a683a2a4c18765

[ -f "$ROM" ] || { echo "falta $ROM (sh tools/setup_cloud.sh la ensambla)"; exit 1; }
[ "$(sha1sum "$ROM" | cut -d' ' -f1)" = "$SHA1" ] || { echo "$ROM no es la ROM (U) que espera snesrev"; exit 1; }

if ! command -v sdl2-config >/dev/null 2>&1; then
    echo "instalando libsdl2-dev..."
    (apt-get install -y libsdl2-dev >/dev/null 2>&1) || (apt-get update >/dev/null 2>&1 && apt-get install -y libsdl2-dev >/dev/null 2>&1)
fi

if [ ! -d "$SRC/.git" ]; then
    mkdir -p "$(dirname "$SRC")"
    git clone -q https://github.com/snesrev/smw "$SRC"
fi
cd "$SRC"
if [ "$(git rev-parse HEAD)" != "$COMMIT" ]; then
    git fetch -q origin 2>/dev/null || true
    git checkout -q "$COMMIT"
fi

if [ ! -f smw_assets.dat ]; then
    cp "$ROM" smw.sfc
    python3 assets/restool.py
    rm -f smw.sfc
fi

# todos los objetos de snesrev (su Makefile); main.o/opengl.o no se usan
CFLAGS="-O2 -fno-strict-aliasing" make -j"$(nproc)" smw >/dev/null
OBJS=$(ls smb1/*.o smbll/*.o src/*.o src/snes/*.o | grep -v -e 'src/main.o' -e 'src/opengl.o' -e 'src/glsl_shader.o')

cd "$HERE"
gcc -O2 -fno-strict-aliasing -Wall -Wno-unused-function -Wno-unknown-pragmas $(sdl2-config --cflags) -I"$SRC" \
    -o work/snesorc tools/snesorc/orc.c $(for o in $OBJS; do printf '%s ' "$SRC/$o"; done) \
    $(sdl2-config --libs) -lm
echo "work/snesorc listo (snesrev $COMMIT en $SRC)"
