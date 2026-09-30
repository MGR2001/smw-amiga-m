#!/bin/sh
# fsuae_shot.sh - corre un ADF en FS-UAE (A500 PAL, 512 KB chip + 512 KB
# slow, cycle-exact: los valores por defecto de amiga_model=A500) SIN
# pantalla (Xvfb) y guarda una captura PNG. Es el equivalente en Claude
# cloud de tools/shot.ps1 -Exact. Sin Kickstart propio, FS-UAE usa el AROS
# que trae dentro: sirve para lo que toma la maquina tras el bootblock
# (bancos de pruebas, demo), no para probar el arranque en KS 1.2.
#
#   sh tools/fsuae_shot.sh work/logicbench.adf work/logicbench.png [segundos]
#   python3 tools/logicbench_read.py --shot work/logicbench.png --auto
#
# Varias corridas a la vez: FSUAE_BASE=/tmp/fsuae-X y FSUAE_DISPLAY=:9N
# distintos en cada una (si no, comparten el directorio y la pantalla).
#
# Instala (una vez): apt-get install -y fs-uae xvfb x11-apps netpbm
set -e
ADF=$(realpath "$1"); OUT=$2; SECS=${3:-30}
BASE=${FSUAE_BASE:-/tmp/fsuae}
mkdir -p "$BASE"
DISP=${FSUAE_DISPLAY:-:$((90 + $$ % 9))}
Xvfb $DISP -screen 0 1024x768x24 >/dev/null 2>&1 &
XPID=$!
sleep 2
DISPLAY=$DISP timeout $((SECS + 15)) fs-uae --amiga_model=A500 --floppy_drive_0="$ADF" \
    --fullscreen=0 --window_width=752 --window_height=572 --base_dir="$BASE" \
    --sound=0 --audio_driver=dummy >"$BASE/run.log" 2>&1 &
UPID=$!
sleep "$SECS"
xwd -root -display $DISP -out "$BASE/shot.xwd"
kill $UPID 2>/dev/null || true
kill $XPID 2>/dev/null || true
xwdtopnm "$BASE/shot.xwd" 2>/dev/null | pnmtopng > "$OUT"
grep -q "cpu_cycle_exact\" to \"true" "$BASE"/Cache/Logs/fs-uae.log.txt \
    && echo "cycle-exact: si" || echo "AVISO: no encuentro cpu_cycle_exact en el log"
echo "-> $OUT"
