#!/bin/sh
# setup_cloud.sh - prepara un entorno Linux (Claude cloud) para compilar el
# port y VERIFICARLO contra el oraculo, sin la ROM del usuario ni WinUAE.
# Ver "Donde quedo el trabajo" en AGENTS.md.
#
#   sh tools/setup_cloud.sh          # herramientas en ~/vbcc (VBCC=... para cambiarlo)
#
# Deja:
#   $VBCC/bin/vbccm68k, $VBCC/bin/vasmm68k_mot   (tools/logicbench_build.sh)
#   ../../smw-src-master                          (fuente de SMW, tools/smwgen.py)
#   work/smw.sfc      la ROM (U), ENSAMBLADA desde el fuente (CRC32 B19ED489)
#   player/gen/*      tools/smwgen.py
#   work/oracle_yi1.bin, work/marioverify, work/cc/state_*.bin
#
# La red del entorno cloud no deja bajar de sun.hasenbraten.de ni de
# phoenix.owl.de: vasm y vbcc salen de espejos en GitHub. La ROM y todo lo
# que sale de ella quedan fuera de git (.gitignore, regla R9).
set -e
VBCC=${VBCC:-$HOME/vbcc}
HERE=$(cd "$(dirname "$0")" && pwd)
PORT=$(cd "$HERE/.." && pwd)
SRC="$(cd "$PORT/.." && pwd)/smw-src-master"
B=${BUILD:-$HOME/.cache/smw-cloud}
mkdir -p "$VBCC/bin" "$B"

command -v gcc >/dev/null || { echo "falta gcc"; exit 1; }
command -v cmake >/dev/null || apt-get install -y -q cmake >/dev/null

# --- vasm (68000, sintaxis Motorola) --------------------------------------
if [ ! -x "$VBCC/bin/vasmm68k_mot" ]; then
    [ -d "$B/vasm" ] || git clone -q --depth 1 https://github.com/mbitsnbites/vasm-mirror "$B/vasm"
    make -C "$B/vasm" CPU=m68k SYNTAX=mot >/dev/null 2>&1
    cp "$B/vasm/vasmm68k_mot" "$VBCC/bin/"
fi

# --- vbcc: solo el compilador (el port no usa libc ni startup) ------------
# El make pregunta por los tipos del host; las respuestas por defecto sirven.
if [ ! -x "$VBCC/bin/vbccm68k" ]; then
    [ -d "$B/vbcc" ] || git clone -q --depth 1 https://github.com/AmigaPorts/vbcc "$B/vbcc"
    mkdir -p "$B/vbcc/bin"
    yes "" | make -C "$B/vbcc" TARGET=m68k >/dev/null 2>&1
    cp "$B/vbcc/bin/vbccm68k" "$VBCC/bin/"
fi

# --- fuente de SMW ---------------------------------------------------------
[ -d "$SRC" ] || git clone -q --depth 1 https://github.com/galaxyhaxz/smw-src "$SRC"

python3 -m pip install -q numpy pillow scipy unicorn machine68k 2>/dev/null

# --- WLA-DX del 2016-07-29 (misma fecha que bin/wla-65816.exe de smw-src) --
# con un parche: DL (3 bytes) dentro de .ENUM, como la WLA modificada.
WLA="$B/wla-dx/build/binaries"
if [ ! -x "$WLA/wla-65816" ]; then
    [ -d "$B/wla-dx" ] || git clone -q https://github.com/vhelin/wla-dx "$B/wla-dx"
    git -C "$B/wla-dx" checkout -q -f 3e58d1dd9127b62341c7f6cba5e8efca9f13b4a9
    python3 - "$B/wla-dx/pass_1.c" <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read()
if '"DL") == 0 || strcaselesscmp(tmp, "LONG")' not in s:
    for old, add in (
        ('      else if (strcaselesscmp(tmp, "DW") == 0 || strcaselesscmp(tmp, "WORD") == 0)\n        o += 2*ord;\n',
         '      else if (strcaselesscmp(tmp, "DL") == 0 || strcaselesscmp(tmp, "LONG") == 0)\n        o += 3*ord;\n'),
        ('      else if (strcaselesscmp(tmp, "DW") == 0 || strcaselesscmp(tmp, "WORD") == 0)\n        si->size = 2;\n',
         '      else if (strcaselesscmp(tmp, "DL") == 0 || strcaselesscmp(tmp, "LONG") == 0)\n        si->size = 3;\n')):
        assert s.count(old) == 1, old
        s = s.replace(old, old + add)
    open(p, 'w').write(s)
EOF
    mkdir -p "$B/wla-dx/build"
    (cd "$B/wla-dx/build" && cmake .. >/dev/null && make -j4 wla-65816 wla-spc700 wlalink >/dev/null 2>&1)
fi

# --- la ROM, ensamblada desde una copia adaptada del fuente ----------------
mkdir -p "$PORT/work"
if [ ! -f "$PORT/work/smw.sfc" ]; then
    rm -rf "$B/smwsrc"
    cp -r "$SRC" "$B/smwsrc"
    python3 "$HERE/smwsrc_wla.py" "$B/smwsrc/project/mw_e10"
    (cd "$B/smwsrc/project/mw_e10" && PATH="$WLA:$PATH" make >/dev/null 2>&1)
    cp "$B/smwsrc/project/mw_e10/mw_e10.sfc" "$PORT/work/smw.sfc"
fi
python3 - "$PORT/work/smw.sfc" <<'EOF'
import sys, zlib
c = zlib.crc32(open(sys.argv[1], 'rb').read())
if c != 0xB19ED489:
    sys.exit("ROM ensamblada con CRC32 %08X, esperaba B19ED489 (SMW U)" % c)
print("ROM ensamblada: CRC32 B19ED489 = Super Mario World (U)")
EOF

# --- lo que sale de la ROM y del oraculo -----------------------------------
cd "$PORT"
python3 tools/smwgen.py --rom work/smw.sfc
python3 tools/oracle2bin.py
python3 tools/mkmapbin.py
SRCS="tools/marioverify.c player/mario.c player/mcoll.c player/manim.c player/mgfx.c player/gen/smwrom00.c"
gcc -O2 -Iplayer -o work/marioverify $SRCS
gcc -O2 -DMCOLL_TRACE -Iplayer -o work/mvtrace $SRCS
mkdir -p work/cc
work/marioverify work/oracle_yi1.bin fulldump 5410 work/cc/state_run.bin >/dev/null || true
work/marioverify work/oracle_yi1.bin fulldump 10983 work/cc/state_jump.bin >/dev/null || true
"$VBCC/bin/vasmm68k_mot" -quiet -Fbin -m68000 -no-opt -I player -o work/boot.bin player/boot.s

echo "listo."
echo "  verificar la 8a:  work/marioverify work/oracle_yi1.bin"
echo "  verificar 8a+8b:  work/marioverify work/oracle_yi1.bin full"
echo "  ADF de la 8d:     VBCC=$VBCC sh tools/logicbench_build.sh   (se corre en la PC, WinUAE)"
