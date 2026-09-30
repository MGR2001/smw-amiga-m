#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_read.py - lee el modo diagnostico de player/game.s (P58) de una
captura y, con la pagina del historial, reproduce la partida en el PC.

Pagina 1 (la de entrada): la imagen del juego congelada y, debajo, una
franja de 32 lineas con barras blancas arriba y abajo y 3 filas de texto
(motivo, frame, X/Y de Mario, $71, el Map16 bajo los pies). Se lee
reconociendo las letras de tools/diagfont.py.

Pagina 2 (ESPACIO): 320 x 256 con barras arriba (lineas 0-3) y abajo
(252-255) y una rejilla de celdas de 2x2 px (160 por fila, lineas
32-251): la cabecera dg_info (18 palabras: motivo, frame, X, Y..., firma
del binario, suma de control) y el historial del joypad desde el principio
del nivel (una entrada por bit que cambia).

Las barras dan el origen y la escala. Sin --auto la escala es 2 (WinUAE,
tools/shot.ps1; P57: se muestrea el centro de cada pixel); con --auto se
mide (FS-UAE en cloud: x2,125).

    python3 tools/diag_read.py --shot shot.png           # WinUAE x2
    python3 tools/diag_read.py --shot shot.png --auto    # FS-UAE
    python3 tools/diag_read.py --shot hist.png --repro   # reproducir con work/live/game.bin
    python3 tools/diag_read.py --shot hist.png --replay  # binario -DREPLAY -DDIAGTEST
    python3 tools/diag_read.py --sim                     # prueba sin emulador (Unicorn)

--repro corre live_logic (el mismo codigo 68000 que la Amiga, en Unicorn)
desde el primer estado del nivel con el joypad del historial y dice en que
frame y con que motivo el port no puede seguir; tiene que ser el mismo
binario que corria en la Amiga (se comprueba con la firma DI_BUILD).

Sale con 1 si no puede leer la captura o si algo no coincide.
"""
import argparse
import math
import os
import re
import sys

from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import diagfont                                 # noqa: E402

# game.s (DI_*): palabra -> nombre
HDR = ["magic", "ver", "frame", "mot", "ev", "x", "y", "a71", "spd", "body", "foot",
       "pad0", "cam", "t", "n", "build", "frameh", "sum"]
NHDR = len(HDR)
MAGIC = 0xD1A6
GROWS, GCOLS = 110, 160                         # rejilla: filas y celdas por fila
GLINE = 32
MOTIVOS = {1: "CAPE", 2: "FIRE", 3: "YOSHI", 4: "LAYER", 5: "TILE", 6: "HURT", 7: "PIPE",
           8: "WATER", 9: "CLIMB", 10: "WALL", 0x10: "DANO (Mario chico)",
           0x11: "MUERTE (kill_mario)", 0x12: "ANIM ($71 sin portar)", 0xFF: "PRUEBA"}
EVENTS = ["TILE", "COIN", "BOUNCE", "DEATH", "HURT", "PIPE", "MIDWAY", "1UP", "POUND",
          "SWITCH", "SPRITE"]
BUTTONS = "BYsSUDLRaxlr"                         # bits 11..0 del estado del historial
GLYPH = {tuple(v): k for k, v in diagfont.table().items()}


# --------------------------------------------------------------------------
# la captura
# --------------------------------------------------------------------------
class Shot:
    """la captura en gris, con el origen y la escala de la pagina que tiene"""

    def __init__(self, img, auto):
        # "blanco": el canal mas bajo, solo donde los tres son parecidos (el
        # marron claro del suelo o el cielo no cuentan)
        r, g, b = img.convert("RGB").split()
        mn = ImageChops.darker(ImageChops.darker(r, g), b)
        mx = ImageChops.lighter(ImageChops.lighter(r, g), b)
        gray = ImageChops.subtract(mx, mn).point(lambda v: 255 if v < 48 else 0)
        self.g = ImageChops.multiply(mn, gray)
        self.w, self.h = self.g.size
        self.data = self.g.tobytes()
        self.find_bars(auto)

    def find_bars(self, auto):
        runs = []
        for y in range(self.h):
            row = self.data[y * self.w:(y + 1) * self.w]
            best = (0, 0)
            for m in re.finditer(rb"[\x81-\xff]+", row):
                if m.end() - m.start() > best[0]:
                    best = (m.end() - m.start(), m.start())
            runs.append(best)
        wmax = max(r[0] for r in runs)
        if wmax < 100:
            raise SystemExit("no encuentro las barras blancas del diagnostico")
        rows = [y for y in range(self.h) if runs[y][0] >= 0.9 * wmax]
        bands, cur = [], [rows[0]]
        for y in rows[1:]:
            if y == cur[-1] + 1:
                cur.append(y)
            else:
                bands.append(cur)
                cur = [y]
        bands.append(cur)
        if len(bands) < 2:
            raise SystemExit("encuentro %d barra(s) blanca(s), hacen falta 2" % len(bands))
        top, bot = bands[0], bands[-1]
        c0 = (top[0] + top[-1] + 1) / 2.0
        c1 = (bot[0] + bot[-1] + 1) / 2.0
        x0 = sum(runs[y][1] for y in top + bot) / float(len(top + bot))
        x1 = sum(runs[y][1] + runs[y][0] for y in top + bot) / float(len(top + bot))
        if (c1 - c0) / (x1 - x0) < 0.3:
            self.page, self.width, self.cbot, self.ctop = 1, 256, 31.0, 1.0
        else:
            self.page, self.width, self.cbot, self.ctop = 2, 320, 254.0, 2.0
        sx, sy = (x1 - x0) / self.width, (c1 - c0) / (self.cbot - self.ctop)
        if self.page == 1 and abs(sy / sx - 1) < 0.05:
            sy = sx                             # 30 lineas miden peor que 256 px
        if auto:
            self.sx, self.sy = sx, sy
        else:
            if abs(sx - 2) > 0.1 or abs(sy - 2) > 0.1:
                print("AVISO: la escala medida es %.3f x %.3f, no 2 (WinUAE): probar --auto"
                      % (sx, sy))
            self.sx = self.sy = 2.0
        self.x0 = x0 if auto else (x0 + x1 - self.width * self.sx) / 2.0
        self.y0 = (c0 - self.ctop * self.sy + c1 - self.cbot * self.sy) / 2.0

    def bit(self, xc, yc):
        """el pixel en el punto (xc, yc) de la pagina (coordenadas de la Amiga,
        con decimales: el centro del pixel x es x + 0,5)"""
        x = int(self.x0 + xc * self.sx)
        y = int(self.y0 + yc * self.sy)
        if not (0 <= x < self.w and 0 <= y < self.h):
            return 0
        return 1 if self.data[y * self.w + x] > 128 else 0

    def text(self, line, ncols):
        """una fila de texto (letras de 8x8 desde la linea dada): (texto, error)"""
        out, worst = [], 0
        for c in range(ncols):
            cell = []
            for r in range(8):
                b = 0
                for i in range(8):
                    b = b << 1 | self.bit(8 * c + i + 0.5, line + r + 0.5)
                cell.append(b)
            cell = tuple(cell)
            if cell in GLYPH:
                out.append(GLYPH[cell])
                continue
            best = min(GLYPH, key=lambda g: sum(bin(g[k] ^ cell[k]).count("1") for k in range(8)))
            worst = max(worst, sum(bin(best[k] ^ cell[k]).count("1") for k in range(8)))
            out.append(GLYPH[best])
        return "".join(out), worst

    def grid(self):
        """las palabras de la rejilla de la pagina 2"""
        words = []
        for r in range(GROWS):
            yc = GLINE + 2 * r + 1.0
            for w in range(GCOLS // 16):
                v = 0
                for k in range(16):
                    v = v << 1 | self.bit(2 * (16 * w + k) + 1.0, yc)
                words.append(v)
        return words


# --------------------------------------------------------------------------
# la cabecera y el historial
# --------------------------------------------------------------------------
def checksum(words):
    s = 0
    for w in words:
        s = ((s << 1) | (s >> 15)) & 0xFFFF
        s ^= w
    return s


def decode(words):
    """(cabecera {nombre: valor}, entradas del historial, errores [])"""
    h = dict(zip(HDR, words[:NHDR]))
    err = []
    if h["magic"] != MAGIC:
        err.append("marca %04X (esperaba %04X)" % (h["magic"], MAGIC))
        return h, [], err
    n = h["n"]
    if n > len(words) - NHDR:
        err.append("n = %d entradas no entra en la rejilla" % n)
        n = len(words) - NHDR
    ent = words[NHDR:NHDR + n]
    s = checksum(words[:NHDR - 1] + ent)
    if s != h["sum"]:
        err.append("suma de control %04X (en la cabecera %04X)" % (s, h["sum"]))
    return h, ent, err


def frame_of(h):
    return h["frameh"] << 16 | h["frame"]


def states(ent, nframes):
    """el estado del joypad (12 bits: byetUDLR << 4 | axlr) de cada frame
    0..nframes (el 0 es el de partida, siempre 0) y el ultimo frame cubierto"""
    ch, t, st = [], 0, 0
    for e in ent:
        b, d = e >> 12, e & 0xFFF
        t += d
        if b == 15:
            continue
        if b > 11:
            raise ValueError("entrada %04X: bit %d" % (e, b))
        st ^= 1 << b
        ch.append((t, st))
    out, cur, i = [0] * (nframes + 1), 0, 0
    for f in range(1, nframes + 1):
        while i < len(ch) and ch[i][0] <= f:
            cur = ch[i][1]
            i += 1
        out[f] = cur
    return out, t


def pad_str(st):
    return "".join(BUTTONS[11 - b] if st >> b & 1 else "." for b in range(11, -1, -1))


def show_header(h):
    mot = h["mot"] >> 8
    print("  motivo           : %02X %s   (mario_unsupported = %d)"
          % (mot, MOTIVOS.get(mot, "?"), h["mot"] & 0xFF))
    print("  frame            : %d (desde el principio del nivel; 1 = el primero jugado)"
          % frame_of(h))
    print("  Mario            : X %04X  Y %04X  vel %02X/%02X  $71 %02X  $19 %02X  $72 %02X"
          % (h["x"], h["y"], h["spd"] >> 8, h["spd"] & 0xFF, h["a71"] >> 8, h["a71"] & 0xFF,
             h["t"] >> 8))
    print("  Map16            : pies %04X  cuerpo %04X  ultimo bloque ($1693) %02X"
          % (h["foot"], h["body"], h["t"] & 0xFF))
    ev = [EVENTS[i] for i in range(len(EVENTS)) if h["ev"] >> i & 1]
    print("  mario_events     : %04X %s" % (h["ev"], " ".join(ev)))
    print("  camara           : %04X" % h["cam"])
    print("  historial        : %d entradas%s; binario %04X%s"
          % (h["n"], " (LLENO: incompleto)" if h["ver"] & 1 else "", h["build"],
             " (-DREPLAY)" if h["ver"] & 2 else ""))


# --------------------------------------------------------------------------
# reproducir en el PC (Unicorn, el binario 68000)
# --------------------------------------------------------------------------
def repro(h, st, last, binp, lst, verbose=True):
    """corre live_logic con el historial desde el primer estado; devuelve
    (frame, motivo, sim) del primer frame en que el port no puede seguir"""
    import gamesim as G
    s = G.GameSim(binp, lst)
    ok = True
    if s.sign() != h["build"]:
        print("AVISO: la firma de %s es %04X y la de la captura %04X: no es el mismo binario, "
              "la reproduccion puede no coincidir" % (os.path.relpath(binp), s.sign(), h["build"]))
        ok = False
    s.start(h["pad0"] >> 8, h["pad0"] & 0xFF)
    nf = frame_of(h)
    top = nf if not h["ver"] & 1 else min(nf, last)
    for f in range(1, top + 1):
        m = s.step(st[f] >> 4, (st[f] & 15) << 4)
        if m:
            return f, m, s, ok
    return None, 0, s, ok


def check_repro(h, st, last, binp, lst):
    f, m, s, ok = repro(h, st, last, binp, lst)
    nf, mot = frame_of(h), h["mot"] >> 8
    if f is None:
        print("reproduccion: el port sigue sin problemas hasta el frame %d; la Amiga paro en el %d"
              " (motivo %02X)" % (min(nf, last) if h["ver"] & 1 else nf, nf, mot))
        return 1
    r = s.ram()
    got = {"x": r[0x94] | r[0x95] << 8, "y": r[0x96] | r[0x97] << 8,
           "a71": r[0x71] << 8 | r[0x19], "cam": r[0x1A] | r[0x1B] << 8}
    same = f == nf and m == mot and all(got[k] == h[k] for k in got)
    print("reproduccion (%s): motivo %02X %s en el frame %d; X %04X Y %04X  -> %s"
          % (os.path.relpath(binp), m, MOTIVOS.get(m, "?"), f, got["x"], got["y"],
             "IGUAL que la Amiga" if same else "DISTINTO de la Amiga (frame %d, motivo %02X, "
             "X %04X Y %04X)" % (nf, mot, h["x"], h["y"])))
    return 0 if same else 1


def check_replay(h, st, path):
    """-DREPLAY -DDIAGTEST: el historial = el joypad de los ops del replay"""
    import gamesim as G
    pads = G.replay_pads(path)
    nf = frame_of(h)
    bad = [f for f in range(1, nf + 1) if st[f] != (pads[f][1] << 4 | pads[f][3] >> 4)]
    print("historial contra %s: %d de %d frames iguales%s"
          % (os.path.relpath(path), nf - len(bad), nf,
             "" if not bad else " (primero distinto: %d)" % bad[0]))
    return 1 if bad else 0


# --------------------------------------------------------------------------
def read_shot(path, auto, save=None):
    """lee la captura; devuelve (pagina, cabecera o campos, entradas, errores)"""
    sh = Shot(Image.open(path), auto)
    print("%s: pagina %d, origen (%.1f, %.1f), escala %.3f x %.3f"
          % (path, sh.page, sh.x0, sh.y0, sh.sx, sh.sy))
    if sh.page == 1:
        rows = [sh.text(line, 32) for line in (3, 11, 19)]
        for t, e in rows:
            print("  | %s |%s" % (t, "" if not e else "  (%d px dudosos)" % e))
        f = parse_page1([t for t, _ in rows])
        return 1, f, [], ([] if f else ["no entiendo el texto de la franja"])
    for line in (8, 16, 24):
        t, e = sh.text(line, 40)
        print("  | %s |%s" % (t, "" if not e else "  (%d px dudosos)" % e))
    h, ent, err = decode(sh.grid())
    return 2, h, ent, err


def parse_page1(rows):
    m1 = re.match(r"MOTIVO ([0-9A-F]{2}) (\S+)\s+FRAME ([0-9A-F]{4})", rows[0])
    m2 = re.match(r"X ([0-9A-F]{4}) Y ([0-9A-F]{4}) A71 ([0-9A-F]{2}) PIE ([0-9A-F]{4})", rows[1])
    if not (m1 and m2):
        return None
    return {"mot": int(m1.group(1), 16), "nombre": m1.group(2), "frame": int(m1.group(3), 16),
            "x": int(m2.group(1), 16), "y": int(m2.group(2), 16), "a71": int(m2.group(3), 16),
            "foot": int(m2.group(4), 16)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", help="captura del modo diagnostico (pagina 1 o 2)")
    ap.add_argument("--auto", action="store_true", help="medir la escala (FS-UAE x2,125)")
    ap.add_argument("--repro", action="store_true", help="reproducir el historial en el PC")
    ap.add_argument("--replay", action="store_true",
                    help="(binario -DREPLAY -DDIAGTEST) comparar el historial con el replay")
    ap.add_argument("--bin", default=os.path.join(HERE, "..", "work", "live", "game.bin"))
    ap.add_argument("--lst", default=None, help="(por defecto, el .lst junto a --bin)")
    ap.add_argument("--replay-bin", default=os.path.join(HERE, "..", "work", "yi1_replay.bin"))
    ap.add_argument("--save", help="guardar el joypad de cada frame (texto: frame, estado)")
    ap.add_argument("--expect", default="",
                    help="frame,motivo esperados (p. ej. de --sim): sale con 1 si no coinciden")
    ap.add_argument("--sim", action="store_true", help="prueba completa en Unicorn, sin emulador")
    a = ap.parse_args()
    lst = a.lst or os.path.splitext(a.bin)[0] + ".lst"
    if a.sim:
        return selftest(a.bin, lst)
    if not a.shot:
        ap.error("falta --shot (o --sim)")
    page, h, ent, err = read_shot(a.shot, a.auto)
    rc = 0
    for e in err:
        print("FALLO: %s" % e)
        rc = 1
    if page == 1:
        if h:
            print("  motivo %02X %s, frame %d, X %04X Y %04X, $71 %02X, Map16 bajo los pies %04X"
                  % (h["mot"], MOTIVOS.get(h["mot"], "?"), h["frame"], h["x"], h["y"], h["a71"],
                     h["foot"]))
            got = (h["frame"], h["mot"])
        if a.repro or a.replay or a.save:
            print("(--repro/--replay/--save necesitan la pagina 2: ESPACIO en el diagnostico)")
    else:
        show_header(h)
        got = (frame_of(h) & 0xFFFF, h["mot"] >> 8)
        if not err:
            st, last = states(ent, frame_of(h))
            if a.save:
                with open(a.save, "w") as f:
                    f.write("# frame estado(hex, byetUDLR<<4|axlr) botones\n")
                    for fr in range(1, len(st)):
                        f.write("%d %03X %s\n" % (fr, st[fr], pad_str(st[fr])))
                print("-> %s (%d frames)" % (a.save, len(st) - 1))
            if a.replay:
                rc |= check_replay(h, st, a.replay_bin)
            if a.repro:
                rc |= check_repro(h, st, last, a.bin, lst)
    if a.expect and not rc:
        ef, em = (int(v, 0) for v in a.expect.split(","))
        if got != (ef & 0xFFFF, em):
            print("FALLO: esperaba frame %d y motivo %02X" % (ef, em))
            rc = 1
        else:
            print("frame y motivo = los esperados (%d, %02X)" % (ef, em))
    return rc


# --------------------------------------------------------------------------
# --sim: toda la cadena en Unicorn (sin emulador ni captura real)
# --------------------------------------------------------------------------
def page_image(bm, stride, first, width, lines, scale, pad=(37, 23)):
    """un mapa de bits de 1 plano como una captura: pixeles de scale x scale
    (vecino mas cercano, con escala no entera tambien), blanco sobre negro"""
    W, H = int(width * scale) + 2 * pad[0], int(lines * scale) + 2 * pad[1]
    img = Image.new("L", (W, H), 0)
    px = img.load()
    for Y in range(H):
        y = math.floor((Y - pad[1]) / scale)
        if not 0 <= y < lines:
            continue
        for X in range(W):
            x = math.floor((X - pad[0]) / scale)
            if 0 <= x < width and bm[y * stride + first + (x >> 3)] & (0x80 >> (x & 7)):
                px[X, Y] = 255
    return img


def selftest(binp, lst):
    import gamesim as G
    s = G.GameSim(binp, lst)
    pads = G.replay_pads()
    s.start()
    for f in range(1, len(pads)):
        m = s.step(pads[f][1], pads[f][3] & 0xF0)
        if m:
            break
    else:
        print("--sim: el joypad del replay no para al port")
        return 1
    r = s.ram()
    want = {"frame": f, "mot": m, "x": r[0x94] | r[0x95] << 8, "y": r[0x96] | r[0x97] << 8}
    print("--sim: live_logic con el joypad del replay: motivo %02X %s en el frame %d, X %04X Y %04X"
          % (m, MOTIVOS.get(m, "?"), f, want["x"], want["y"]))
    dmem = G.SCRATCH
    s.write(dmem, bytes(s.syms["DG_SIZE"] + 16))
    s.w32("g_dmem", dmem)
    s.w32("g_null", dmem + s.syms["DG_SIZE"])
    s.call("diag_trigger", d0=m)
    s.call("diag_render")
    page = s.read(dmem, 40 * 256)
    strip = s.read(dmem + s.syms["DG_STRIP"], s.syms["DG_STRIPB"] * 32)
    rc = 0
    tmp = os.path.join(HERE, "..", "work", "diag_sim")
    os.makedirs(tmp, exist_ok=True)
    for scale, auto in ((2.0, False), (2.125, True)):
        p1 = os.path.join(tmp, "p1_%g.png" % scale)
        p2 = os.path.join(tmp, "p2_%g.png" % scale)
        page_image(strip, s.syms["DG_STRIPB"], 2, 256, 32, scale).save(p1)
        page_image(page, 40, 0, 320, 256, scale).save(p2)
        pg, f1, _, e1 = read_shot(p1, auto)
        ok1 = (not e1 and f1 and f1["frame"] == f and f1["mot"] == m and f1["x"] == want["x"]
               and f1["y"] == want["y"])
        pg, h, ent, e2 = read_shot(p2, auto)
        ok2 = not e2 and frame_of(h) == f and h["mot"] >> 8 == m
        if ok2:
            st, last = states(ent, f)
            okh = all(st[k] == (pads[k][1] << 4 | pads[k][3] >> 4) for k in range(1, f + 1))
            print("  historial decodificado = joypad del replay en los %d frames: %s"
                  % (f, "si" if okh else "NO"))
            ok2 = okh and check_repro(h, st, last, binp, lst) == 0
        print("--sim escala %g: pagina 1 %s, pagina 2 + reproduccion %s"
              % (scale, "OK" if ok1 else "FALLO", "OK" if ok2 else "FALLO"))
        rc |= not (ok1 and ok2)
    print("--sim: %s" % ("TODO OK" if not rc else "FALLO"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
