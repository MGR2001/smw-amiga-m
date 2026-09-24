#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mkd8in.py - las entradas de dpfsplit.py / copsim.py / d8objs.py, sacadas de
los datos del ROM (antes salian de la imagen de referencia de SNESMaps):

  work/fg15.npy   capa 1 del nivel, 432 x 5120, color RGB555 por pixel
                  (r << 10 | g << 5 | b, 5 bits) y SKY = 0x197 donde no hay
                  tile (el cielo $5D80 en ese mismo formato)
  work/bg512.npy  capa 2 (el fondo), 432 x 512, mismo formato

    python tools/mkd8in.py      (usa work/level_final.png y work/bg_mountains.png;
                                 los genera con mklvl / mkbg si no estan)
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "..", "work")


def rgb555(path):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int32) >> 3
    return (a[..., 0] << 10 | a[..., 1] << 5 | a[..., 2]).astype(np.int32)


def main():
    l1 = os.path.join(WORK, "level_final.png")
    bg = os.path.join(WORK, "bg_mountains.png")
    if not (os.path.exists(l1) and os.path.exists(bg)):
        subprocess.check_call([sys.executable, os.path.join(HERE, "mkbg.py")])
    fg = rgb555(l1)
    b = rgb555(bg)
    sky = 0x197
    print("capa 1 %s, cielo %d px; capa 2 %s, cielo %d px"
          % (fg.shape, (fg == sky).sum(), b.shape, (b == sky).sum()))
    np.save(os.path.join(WORK, "fg15.npy"), fg)
    np.save(os.path.join(WORK, "bg512.npy"), b)
    print("-> work/fg15.npy, work/bg512.npy")


if __name__ == "__main__":
    main()
