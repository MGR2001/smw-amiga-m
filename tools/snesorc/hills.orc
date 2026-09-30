# hills.orc - la 8c: las colinas de Yoshi's Island 1 (Etapa 8.1).
#   -> work/oracle_hills.txt
#
# Las "colinas" del nivel son cornisas con pendiente de 45 grados que no
# llegan al suelo: se sube por la izquierda (bloques $1AA/$1E2), la cima
# ($0A1) y el lado derecho ($0A6) no son solidos y por dentro se pasa.
#   colina 1: bloques $0B-$0D, pendiente de x = $0B0 (y $140) a $0DF (y $120)
#   colinas 2-4: bloques $4B-$56, tres pendientes seguidas; la de cada una
#     empieza dentro de la anterior ($1AB/$1F8)
# (La colina grande de $AE0, con pendiente hacia el otro lado y cinco Rex
# encima, queda sin grabar.)
#
# Graba desde el primer frame del nivel.  De paso: el Koopa sin caparazon
# ($02, sale del $BD que baja deslizandose) pisado.
include boot_yi1.orc
rec on

# --- colina 1 ---
until w$0094>=0058 max 200 RIGHT+Y
20 RIGHT+Y+B                     # salta al Koopa que baja y aterriza en la pendiente
until $0072==00 max 100 RIGHT
until w$0094>=00C4 max 200 RIGHT # sube andando
until $0072!=00 max 200 -        # quieto: resbala y cae por abajo
until $0072==00 max 100 -
until w$0094<=0070 max 300 LEFT
until $14E7==FF max 400 -        # el Koopa $02 (ranura 7) llega al borde y vuelve
until $00EB==28 max 400 -
8 LEFT+B                         # y se lo pisa
until $0072==00 max 100 -
30 -
assert $0071==00
until w$0094>=0080 max 300 RIGHT
14 RIGHT+B                       # del suelo a la pendiente, andando
until $0072==00 max 100 RIGHT
30 DOWN                          # agachado: se desliza y cae
until $0072==00 max 100 DOWN
until w$0094<=0050 max 300 LEFT
10 -
until w$0094>=0078 max 300 RIGHT+Y
6 RIGHT+Y+B                      # del suelo a la pendiente, corriendo
until $0072==00 max 100 RIGHT+Y
until $0072!=00 max 100 RIGHT+Y  # cruza corriendo y cae por la derecha
until $0072==00 max 100 RIGHT+Y
20 LEFT
until w$0094<=0060 max 300 LEFT  # vuelve por dentro de la colina
until w$0094>=0080 max 300 RIGHT
14 RIGHT+B
until $0072==00 max 100 RIGHT
until w$0094>=00C4 max 200 RIGHT
until $0072!=00 max 200 LEFT     # baja andando hacia la izquierda
until $0072==00 max 100 -
until w$0094<=0060 max 300 LEFT
until w$0094>=0080 max 300 RIGHT
14 RIGHT+B
until $0072==00 max 100 RIGHT
until w$0094>=00C0 max 200 RIGHT
until $0072!=00 max 200 LEFT+Y   # baja corriendo hacia la izquierda
until $0072==00 max 100 LEFT+Y
until w$0094<=0060 max 300 LEFT
until w$0094>=0080 max 300 RIGHT
14 RIGHT+B
until $0072==00 max 100 RIGHT
until w$0094>=00B8 max 200 RIGHT
10 B                             # salto en la pendiente
until $0072==00 max 100 -
until w$0094>=00B8 max 200 RIGHT
12 A                             # salto con giro
until $0072==00 max 100 -
20 -
until $0072==00 max 100 -
assert $0071==00

# --- camino hasta las colinas 2-4 (x de los saltos: busqueda) ---
until w$0094>=0140 max 600 RIGHT+Y
assert $0071==00
until w$0094>=0149 max 600 RIGHT+Y
32 RIGHT+Y+B                     # Rex de $210; el Banzai Bill pasa por arriba
until w$0094>=0200 max 600 RIGHT+Y
assert $0071==00
until w$0094>=0280 max 600 RIGHT+Y
assert $0071==00
until w$0094>=0289 max 600 RIGHT+Y
4 RIGHT+Y+B
until w$0094>=0300 max 600 RIGHT+Y
assert $0071==00
until w$0094>=0318 max 600 RIGHT+Y
assert $0071==00
until w$0094>=0318 max 600 RIGHT
8 RIGHT+B                        # el Rex del tubo diagonal 1
until w$0094>=03C0 max 400 RIGHT
assert $0071==00
until w$0094>=03C4 max 600 RIGHT+Y
4 RIGHT+Y+B
until $0072==00 max 120 RIGHT+Y
8 RIGHT+Y+B                      # los Rex de la meseta
until w$0094>=0440 max 600 RIGHT+Y
16 RIGHT+Y+B                     # a la pendiente de la colina 2
until $13EE!=00 max 120 RIGHT+Y
assert $0071==00

# --- colinas 2-4 ---
until $0072!=00 max 100 RIGHT+Y  # sube corriendo y salta a la siguiente
until $13EE!=00 max 100 RIGHT
until w$0094>=0510 max 100 RIGHT
12 B                             # salto en la pendiente: cae en la colina 4
until $0072==00 max 100 -
until w$0094>=0548 max 200 RIGHT
20 -                             # quieto: resbala
until $0072!=00 max 100 LEFT+Y   # baja corriendo hacia la izquierda y cae
until $0072==00 max 100 LEFT
10 -
assert $0071==00
