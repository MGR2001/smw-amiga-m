#!/usr/bin/env python3
"""
oamrec.py - carga tools/oambot.lua en SuperMarioWorldSNESRecomp (puerto Lua
TCP 4380) y vacia lo que graba en work/oam_yi1.txt hasta que se sale del
nivel (o --seconds).

    $env:SNESRECOMP_LUA_PORT='4380'
    ..\\smwrecomp\\SuperMarioWorldSNESRecomp.exe --rom ..\\smwre\\smw.sfc
    python tools/oamrec.py              # graba mientras alguien juega
    python tools/oamrec.py --test 10    # prueba: graba 10 s en cualquier modo

Protocolo (medido): cada valor de la respuesta se corta a 1024 caracteres y
van como maximo 16 valores; oambot.lua entrega trozos de 1000 y aca se
vuelven a pegar. Solo una conexion a la vez: no consultar el juego desde
otra terminal mientras esto corre.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "smwrecomp", "lua"))
from lua_tcp import LuaClient  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "work", "oam_yi1.txt"))
    ap.add_argument("--test", type=float, default=0,
                    help="segundos de prueba grabando en cualquier modo")
    ap.add_argument("--seconds", type=float, default=1800)
    a = ap.parse_args()
    src = open(os.path.join(HERE, "oambot.lua"), encoding="utf-8").read()
    src = ("REC_ALL = true\n" if a.test else "REC_ALL = false\n") + src
    limit = a.test or a.seconds
    with LuaClient() as c, open(a.out, "w") as f:
        print(c.eval(src)["values"], flush=True)
        c.command("resume")
        t0 = time.time()
        total = 0
        last_print = 0
        stopping = False
        while True:
            v = c.eval("return BOT_drain()")["values"]
            pending, done = int(v[0]), v[1] == "true"
            text = "".join(v[2:])
            if text:
                f.write(text)
                total += text.count("\n")
            now = time.time() - t0
            if now - last_print >= 5:
                last_print = now
                print(f"{now:5.0f} s  frames grabados {total}  en cola {pending}", flush=True)
            if now > limit and not stopping:
                c.eval("BOT.done = true")      # deja de grabar; se vacia lo que queda
                stopping = True
            if (done or stopping) and pending == 0 and not text:
                break
            if not text:
                time.sleep(0.05)
    print(f"{total} frames -> {a.out}", flush=True)


if __name__ == "__main__":
    main()
