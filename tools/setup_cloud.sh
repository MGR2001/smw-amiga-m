#!/bin/sh
# setup_cloud.sh - prepara un entorno Linux (Claude cloud) para compilar y
# revisar el port SIN la ROM ni WinUAE. Ver "Donde quedo el trabajo" en
# AGENTS.md: aca se escribe y compila codigo; verificar y medir es en la PC.
#
#   sh tools/setup_cloud.sh          # instala en ~/vbcc (VBCC=... para cambiarlo)
#
# Deja $VBCC/bin/vbccm68k y $VBCC/bin/vasmm68k_mot (los que usa
# tools/logicbench_build.sh) y las librerias de Python de tools/.
set -e
VBCC=${VBCC:-$HOME/vbcc}
mkdir -p "$VBCC/bin"
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$(mktemp -d)"

# vasm (68000, sintaxis Motorola)
curl -fsSL http://sun.hasenbraten.de/vasm/release/vasm.tar.gz | tar xz
make -C vasm CPU=m68k SYNTAX=mot >/dev/null
cp vasm/vasmm68k_mot "$VBCC/bin/"

# vbcc: solo el compilador (el port no usa libc ni startup). El make pregunta
# por los tipos del host; las respuestas por defecto sirven.
curl -fsSL http://phoenix.owl.de/tags/vbcc0_9hP2.tar.gz | tar xz
mkdir -p vbcc/bin
yes "" | make -C vbcc TARGET=m68k >/dev/null
cp vbcc/bin/vbccm68k "$VBCC/bin/"

# fuente de SMW (lo lee tools/smwgen.py en ../../smw-src-master)
SRC="$(cd "$HERE/../.." && pwd)/smw-src-master"
[ -d "$SRC" ] || git clone -q --depth 1 https://github.com/galaxyhaxz/smw-src "$SRC"

python3 -m pip install -q numpy pillow scipy
command -v gcc >/dev/null || echo "AVISO: falta gcc (para tools/marioverify.c)"
echo "listo. Compilar: VBCC=$VBCC sh tools/logicbench_build.sh"
echo "(sin la ROM falta player/gen/smwrom00.c: ver AGENTS.md)"
