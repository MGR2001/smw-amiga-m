# boot_yi1.orc - desde el encendido hasta el primer frame de Yoshi's Island 1
# (modo $14, translevel $29).  SRAM vacia -> fichero A nuevo, 1 jugador.
# Lo incluyen los demas guiones; no graba nada.
rec off
until $0100==07 max 600 -       # pantalla de titulo
20 -
1 START                          # -> seleccion de fichero (modo $08)
60 -
1 START                          # fichero A -> 1 jugador (modo $0A)
60 -
1 START                          # -> mensaje de la intro (modo $14, translevel 0)
until $1426!=0 max 1000 -        # la caja de mensaje se abre
until $1DF5==0 max 2000 -        # wm_IntroCtrlSeqFrame: hasta 0 no acepta botones
2 -
1 START                          # cierra el mensaje -> mapa
until $0100==0E max 1000 -       # mapa (modo $0E), Mario en la casa de Yoshi
60 -
4 LEFT                           # camino a Yoshi's Island 1
until w$1F17==0038 max 300 -     # llego al punto del nivel
30 -
1 B                              # entrar
until $0100==14 max 600 -        # primer frame del nivel
assert $13BF==29
