# diagpipe.orc - Mario pequeno sobre los DOS tubos diagonales de Yoshi's
# Island 1 (Etapa 8.1).  -> work/oracle_diagpipe.txt
#
#   tubo 1: pantalla 3, bloques $33-$3A, sube de x = $330 (suelo) a la boca
#           ($380-$39F, y = $100) y desemboca en la meseta de x >= $3B0
#   tubo 2: pantallas 7-8, bloques $7C-$85, de x = $7C0 a la boca ($810-$82F);
#           a la derecha, el sprite $8E (bloques invisibles) hace de suelo
#
# Graba desde el primer frame del nivel: el camino hasta los tubos (correr,
# saltar, pisar Rex, pasar bajo el Banzai Bill) tambien sirve.  Las x de los
# saltos del camino las encontro una busqueda (ver snesorc_setup.sh); los
# 'assert' hacen fallar el guion si algo cambia la partida.
include boot_yi1.orc
rec on

# --- camino hasta el tubo 1 ---
until w$0094>=0058 max 200 RIGHT+Y
20 RIGHT+Y+B                     # sobre el Koopa que baja deslizandose por la colina
until w$0094>=0155 max 600 RIGHT+Y
24 RIGHT+Y+B                     # sobre el Rex de $210 (el Banzai Bill pasa por arriba)
until w$0094>=0288 max 600 RIGHT+Y
4 RIGHT+Y+B                      # sobre el Rex de $2F0
until w$0094>=0300 max 600 RIGHT+Y

# --- tubo 1 ---
until w$0094>=0318 max 600 RIGHT
assert $0071==00
until w$0094>=0320 max 600 RIGHT
12 RIGHT+B                       # pisa al Rex que baja por el tubo
until w$0094>=0368 max 600 RIGHT
assert $0071==00
until w$0094>=0390 max 600 RIGHT # sube andando hasta la boca
assert $0071==00
until w$0094>=03C0 max 600 RIGHT # baja a la meseta
until w$0094<=0358 max 400 LEFT  # vuelve a subir la boca por la derecha y baja andando
18 -                             # quieto en la pendiente: resbala
until w$0094>=03A0 max 400 RIGHT+Y   # sube corriendo
until w$0094<=0360 max 400 LEFT+Y    # baja corriendo (pisa a otro Rex)
10 RIGHT
12 RIGHT+B                       # salto en la pendiente
until $0072==00 max 100 RIGHT
20 DOWN                          # agachado: se desliza
until w$0094>=03C8 max 400 RIGHT

# --- camino hasta el tubo 2 ---
until w$0094>=03CC max 600 RIGHT+Y
4 RIGHT+Y+B
until $0072==00 max 120 RIGHT+Y
8 RIGHT+Y+B                      # dos Rex en la meseta
until w$0094>=04A0 max 400 RIGHT+Y
assert $0071==00
until w$0094>=04B5 max 600 RIGHT+Y
4 RIGHT+Y+B
until w$0094>=0500 max 600 RIGHT+Y
assert $0071==00
until w$0094>=0580 max 600 RIGHT+Y
assert $0071==00
until w$0094>=0600 max 600 RIGHT+Y
assert $0071==00
until w$0094>=0680 max 600 RIGHT+Y
assert $0071==00
until w$0094>=06C0 max 600 RIGHT+Y
assert $0071==00
until w$0094>=06C8 max 600 RIGHT+Y
4 RIGHT+Y+B                      # la tuberia de la piranha
until w$0094>=0740 max 600 RIGHT+Y
assert $0071==00
until w$0094>=074F max 600 RIGHT+Y
10 RIGHT+Y+B                     # la caja de bloques de cemento
until w$0094>=07B0 max 600 RIGHT+Y
assert $0071==00

# --- tubo 2 ---
until $0072==00 max 100 -        # aterriza en el tubo corriendo
60 -                             # quieto: resbala hasta abajo
until w$0094>=07F0 max 200 RIGHT # sube andando
30 -                             # quieto en la pendiente
until w$0094>=0800 max 200 RIGHT
until w$0094<=07C0 max 200 LEFT  # baja andando
20 -
until w$0094>=0810 max 200 RIGHT+Y   # sube corriendo hasta la boca
until w$0094<=07B8 max 200 LEFT+Y    # baja corriendo
10 -
12 RIGHT+B                       # desde el suelo a la pendiente
until $0072==00 max 100 RIGHT
until w$0094>=07E8 max 200 RIGHT
12 RIGHT+B                       # salto en la pendiente
until $0072==00 max 100 RIGHT
40 DOWN                          # agachado: se desliza
30 -
until w$0094>=07F0 max 200 RIGHT
12 RIGHT+A                       # salto con giro en la pendiente
until $0072==00 max 100 RIGHT
30 -
until w$0094>=0818 max 200 RIGHT # por encima de la boca, al sprite $8E
60 -
until w$0094<=07C0 max 300 LEFT  # vuelve por la boca y baja andando
until w$0094>=0824 max 300 RIGHT+Y   # sube corriendo y pasa la boca
16 LEFT                          # frena
until w$0094<=07D0 max 300 LEFT+Y    # baja corriendo
until w$0094>=07F0 max 300 RIGHT
10 B                             # salto en el sitio en la pendiente
until $0072==00 max 100 -
30 -
8 LEFT+B
until $0072==00 max 100 -
60 -
assert $0071==00
