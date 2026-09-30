# banzai.orc - sprites para la Etapa 9: el Koopa sin caparazon ($02, sale
# del Koopa deslizante $BD) pisado, y el Banzai Bill ($9F) cruzando la
# pantalla entero por encima de Mario, el segundo pisado.
#   -> work/oracle_banzai.txt
include boot_yi1.orc
rec on
until w$0094>=0058 max 200 RIGHT+Y
20 RIGHT+Y+B                     # sobre el Koopa $BD, que baja deslizandose
until $0072==00 max 100 RIGHT
until w$0094>=00C4 max 200 RIGHT
until $0072!=00 max 200 -
until $0072==00 max 100 -
until w$0094<=0070 max 300 LEFT
until $14E7==FF max 400 -        # el Koopa, ya $02 (ranura 7), llega al borde y vuelve
until $00EB==28 max 400 -
8 LEFT+B                         # pisado
until $0072==00 max 100 -
30 -
assert $0071==00
until w$0094>=0130 max 400 RIGHT # quieto bajo el camino del Banzai Bill
until $009E==9F max 400 -        # aparece en la ranura 0 (x = $1F0)
until $14E0==00 max 400 -        # pasa por encima de Mario...
until $14E0==01 max 400 -        # ...sale por la izquierda y aparece otro
until $00E4<=70 max 400 -
24 B                             # y se lo pisa
until $0072==00 max 200 -
60 -
assert $0071==00
