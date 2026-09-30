; WIP 6.4 (SIN ENSAMBLAR NI VERIFICAR): build_mid incremental para
; player/scroll.s. Reemplaza el bloque build_mid; necesita el MLD de 20
; bytes de mkscroll_6_4.diff (flag "tarde" en M_F, lonext, PL, SR) y LT = 144
; (LNS guarda linea * LT). Pendiente antes de probarlo:
;   - htab con x - s0 desde TMIN = -16 (asr al construirla) y mdir/mjump;
;   - linetab_a/b de 2 x 144 x 224 bytes: pedirlas con AllocMem en
;     scroll_init (V_LTAB) en vez de ds.b: en game.s, 64 KB en medio del
;     binario rompen los bsr/lea (pc) (P52); linetab_b = linetab_a + LT*LINES;
;   - scratch_seg (144 bytes) para mid_rebase, con lea (pc), no move.l #;
;   - init_lines: mulu #MLDR, los campos nuevos, alllines con N*LT.
; Verificar con scrollsim --ret (9282 px, ida = vuelta) y scrollprof.
;----------------------------------------------------------------------
; --- build_mid ---
; entrada:  V_BACK = lista que se escribe, V_S = scroll
; salida:   en el segmento de cada linea que puede tener cargas en
;           pantalla (LNS) y cuyo contenido ya no vale, las cargas del plan
;           y el salto al segmento siguiente
; registros destruidos: d0-d1/a0-a1 (guarda el resto)
;
; El plan (tools/mkscroll.py) esta en coordenadas del nivel: para cada
; carga, la x en que cae y si va con WAIT, detras de la anterior o con 1-2
; MOVE de relleno. Se escribe con una BASE s0 por linea: la h de cada WAIT
; sale de htab[x - s0] y la primera carga escrita va siempre con WAIT; con
; la misma base para todas, los huecos del plan se conservan.
;
; Lo escrito queda FIJO en pantalla: el MOVE de una carga cae entre x - s0
; y x - s0 + 7 (rejilla de 8 px, P42; los de detras, a 16 px del anterior)
; y vale (el color cambia despues del fin del tramo anterior y antes del
; principio del nuevo) mientras s0 + a <= s < s0 + b. Las escritas son las
; de x en [s, s + LASTX] sin las muertas del principio (una carga muerta,
; s >= lo = x + a, ya tiene su color en el borrado: CHG) y no mas de
; MIDMAX. Una muerta escrita no molesta mientras la siguiente del mismo
; registro no se aplique en el borrado (s < lonext).
;
; Cargas "tarde" (a > 0 o b <= 0, flag de MLD): con la base s no caen en
; su ventana. Si hay una viva escrita la linea es CANONICA, s0 = s, como
; antes: esas cargas caen donde caerian escritas en s, y eso no cambia
; mientras x - s siga en la misma celda de 8 px (P42): la imagen depende
; solo de s (ida = vuelta, P50) y es la de antes. Si no hay tardes vivas,
; todas valen con cualquier base de (-minb, -maxa], que contiene 0: se
; elige segun hacia donde va la camara (6.4) para que valgan mas tiempo:
; a la derecha la mayor (caen mas a la izquierda), a la izquierda la menor.
; Las cargas validas pintan bien con cualquier base.
;
; La linea se mira cuando s sale de [vl, vu):
;   vl = max(PL(klo), s0 + maxa, lo de las tardes muertas (reviven al
;        volver), principio de la celda de las tardes vivas)
;   vu = min(SR(khi) - LASTX, s0 + minb, lonext de las escritas, fin de la
;        celda de las tardes vivas, x(klo) + 1 si no entraron todas)
; PL/SR (mkscroll.py): una carga no escrita de la izquierda o de la
; derecha hace falta (su ventana entera en pantalla) y se puede escribir.
; Entonces, en orden:
;   - salto de camara, s < PL(klo) o s >= lonext de una escrita:
;     mid_full (se reescribe todo);
;   - si no, mid_rebase: agrega por la derecha las que entraron, saca las
;     que salieron por la derecha, y mid_base elige la base y reescribe
;     SOLO el byte h de cada WAIT si la base cambio. Si no se puede
;     (pantalla, MIDMAX), mid_full.
;----------------------------------------------------------------------
MLDR    equ 20                  ; bytes por carga en MLD (tools/mkscroll.py)
M_CLS   equ 0
M_X     equ 2
M_MOVE  equ 4
M_A     equ 8
M_B     equ 10
M_F     equ 12                  ; bit 0: tarde
M_LON   equ 14
M_PL    equ 16
M_SR    equ 18
; linetab: LT bytes por linea (mkscroll.py: LNS guarda linea * LT)
LT      equ 144
LT_SEG  equ 0                   ; .l donde empiezan las cargas en el segmento
LT_KLO  equ 4                   ; .l primera carga escrita (MLD)
LT_KHI  equ 8                   ; .l una despues de la ultima
LT_VL   equ 12                  ; lo escrito vale mientras vl <= s < vu
LT_VU   equ 14
LT_VW   equ 16                  ; palabra alta del WAIT (v << 8)
LT_JMP  equ 18                  ; salto al segmento siguiente (12 bytes)
LT_S0   equ 30                  ; base de lo escrito
LT_WEND equ 32                  ; donde esta el salto (desde LT_SEG)
LT_MAXA equ 34                  ; max a / min b de las no tardes escritas
LT_MINB equ 36
LT_MINL equ 38                  ; min lonext de las escritas
LT_NW   equ 40                  ; WAIT en LT_WL
LT_NT   equ 42                  ; tardes en LT_TL
LT_TL   equ 46                  ; tardes: MIDMAX x (x, lo)
LT_WL   equ LT_TL+MIDMAX*4      ; WAIT: MIDMAX x (desplazamiento del byte h, x)
        ifgt    LT_WL+MIDMAX*4-LT
        fail    "linetab: LT chico"
        endc
TMIN    equ -16                 ; la x - s0 mas chica de una carga escrita
                                ; (muertas del principio: htab llega a -16;
                                ; caen en x = -9 o -1, antes de la pantalla)

build_mid:
        move.l  V_BACK(a5),a0
        lea     V_LSA(a5),a1
        cmp.l   V_COP(a5),a0
        beq.s   .la
        lea     V_LSB(a5),a1
.la:    move.w  V_S(a5),d0
        move.w  (a1),d1
        cmp.w   d1,d0                       ; la camara no se movio desde la
        bne.s   .go                         ; ultima vez que se escribio esta
        rts                                 ; lista: ya esta bien
.go:    move.w  d0,(a1)
        movem.l d2-d7/a2-a6,-(sp)
        move.w  d0,d6                       ; d6 = s
        lea     mdir(pc),a1                 ; mdir: 1 = a la izquierda
        cmp.w   d1,d0                       ; (s vieja > s; $8000 = nunca:
        slt     (a1)+                       ; a la derecha)
        sf      (a1)                        ; mjump
        sub.w   d0,d1                       ; |s vieja - s| > 16 (o nunca
        bpl.s   .ab                         ; escrita): todas las lineas,
        neg.w   d1                          ; enteras
.ab:    lea     alllines(pc),a6
        cmp.w   #16,d1
        bhi.s   .all
        move.w  d6,d0
        lsr.w   #4,d0
        add.w   d0,d0
        move.l  a3,a6
        add.l   D_LNS(a3),a6
        moveq   #0,d1
        move.w  (a6,d0.w),d1                ; sin signo: LNS pasa de 32 KB
        add.l   d1,a6                       ; LNS[s >> 4]
        bra.s   .al2
.all:   st      (a1)
.al2:   lea     linetab_b(pc),a4
        cmp.l   V_COP(a5),a0
        bne.s   .ta
        lea     linetab_a(pc),a4
.ta:    move.l  a4,a5                       ; OJO: a5 prestado (vars)
        move.w  d6,d5
        add.w   #LASTX,d5                   ; d5 = s + LASTX
.line:  move.w  (a6)+,d0                    ; linea * LT
        bmi.s   .done
        lea     (a5,d0.w),a4                ; a4 = linetab[L]
        cmp.w   LT_VL(a4),d6
        blt.s   .rw                         ; s < vl
        cmp.w   LT_VU(a4),d6
        blt.s   .line                       ; s < vu: lo escrito vale
.rw:    move.b  mjump(pc),d0
        bne.s   .fu
        move.l  LT_KLO(a4),a1
        cmp.w   M_PL(a1),d6                 ; s < PL(klo): hace falta una de
        blt.s   .fu                         ; la izquierda
        cmp.w   LT_MINL(a4),d6              ; s >= lonext de una escrita
        bge.s   .fu
        bsr     mid_rebase
        tst.w   d0
        beq.s   .line
.fu:    bsr     mid_full
        bra.s   .line
.done:  movem.l (sp)+,d2-d7/a2-a6
        rts

;----------------------------------------------------------------------
; --- mid_full --- la linea entera (build_mid)
; entrada:  a4 = linetab[L], d6 = s, d5 = s + LASTX
; salida:   las cargas escritas, el salto, el estado de la linea
; registros destruidos: d0-d4/d7/a0-a3
;----------------------------------------------------------------------
mid_full:
        move.l  LT_KLO(a4),a1               ; klo: la primera con x >= s
.lof:   cmp.w   M_X(a1),d6                  ; (registros de MLDR bytes;
        ble.s   .lob                        ; centinelas: x = -1 antes,
        lea     MLDR(a1),a1                 ; $7FFF despues)
        bra.s   .lof
.lob:   cmp.w   M_X-MLDR(a1),d6             ; la anterior tiene x >= s: la
        bgt.s   .dea                        ; camara volvio
        lea     -MLDR(a1),a1
        bra.s   .lob
.dea:   move.w  M_X(a1),d0                  ; sin las muertas del principio
        add.w   M_A(a1),d0                  ; (lo = x + a <= s)
        cmp.w   d6,d0
        bgt.s   .kl
        lea     MLDR(a1),a1
        bra.s   .dea
.kl:    move.l  a1,LT_KLO(a4)
        move.l  LT_KHI(a4),a0               ; khi: la primera con x > s + LASTX
        cmp.l   a1,a0
        bhs.s   .hif
        move.l  a1,a0
.hif:   cmp.w   M_X(a0),d5
        blt.s   .hib
        lea     MLDR(a0),a0
        bra.s   .hif
.hib:   cmp.l   a1,a0
        beq.s   .hid
        cmp.w   M_X-MLDR(a0),d5
        bge.s   .hid
        lea     -MLDR(a0),a0
        bra.s   .hib
.hid:   move.l  a0,d0
        sub.l   a1,d0
        cmp.w   #MIDMAX*MLDR,d0
        bls.s   .nc
        lea     MIDMAX*MLDR(a1),a0          ; no entran todas
.nc:    move.l  a0,LT_KHI(a4)
        move.l  LT_SEG(a4),a3
        clr.w   LT_NW(a4)
        clr.w   LT_NT(a4)
        move.w  #-16000,LT_MAXA(a4)
        move.w  #16000,LT_MINB(a4)
        move.w  #$7fff,LT_MINL(a4)
        move.w  #$8000,LT_S0(a4)            ; mid_base escribe todas las h
        moveq   #1,d1                       ; la primera, con WAIT
        bsr     mid_put
        move.l  a3,d0
        sub.l   LT_SEG(a4),d0
        move.w  d0,LT_WEND(a4)
        move.l  LT_JMP(a4),(a3)+            ; el salto al segmento siguiente
        move.l  LT_JMP+4(a4),(a3)+
        move.l  LT_JMP+8(a4),(a3)+
        bsr     mid_base                    ; con x en [s, s + LASTX] siempre
        rts                                 ; hay base

;----------------------------------------------------------------------
; --- mid_put --- escribe las cargas [a1, a0) en a3 y las agrega al estado
; (listas de WAIT y de tardes, maxa, minb, minl). Los WAIT quedan sin h
; (la escribe mid_base).
; entrada:  a1, a0 (MLD), a3 = donde, a4 = linetab[L], d1 = 1 si la
;           primera va con WAIT aunque sea de otra clase
; salida:   a3 = despues de la ultima
; registros destruidos: d0-d4/a1-a2
;----------------------------------------------------------------------
mid_put:
        cmp.l   a0,a1
        beq     .ret
        move.l  a5,-(sp)
        move.w  LT_NW(a4),d0                ; a2 = siguiente WAIT de la lista
        add.w   d0,d0
        add.w   d0,d0
        lea     LT_WL(a4,d0.w),a2
        move.w  LT_NT(a4),d0                ; a5 = siguiente tarde
        add.w   d0,d0
        add.w   d0,d0
        lea     LT_TL(a4,d0.w),a5
        move.w  LT_MAXA(a4),d2
        move.w  LT_MINB(a4),d3
        move.w  LT_MINL(a4),d4
        tst.w   d1
        bne.s   .w
.ld:    move.w  M_CLS(a1),d1                ; clase
        bne.s   .ch
.w:     move.l  a3,d0                       ; WAIT: a la lista
        sub.l   LT_SEG(a4),d0
        addq.w  #1,d0
        move.w  d0,(a2)+                    ; desplazamiento del byte h
        move.w  M_X(a1),(a2)+
        move.w  LT_VW(a4),(a3)+
        move.w  #$fffe,(a3)+
.mv:    move.l  M_MOVE(a1),(a3)+            ; MOVE registro, color
        btst    #0,M_F+1(a1)
        bne.s   .tl
        move.w  M_A(a1),d0
        cmp.w   d0,d2
        bge.s   .a1
        move.w  d0,d2
.a1:    move.w  M_B(a1),d0
        cmp.w   d0,d3
        ble.s   .lon
        move.w  d0,d3
        bra.s   .lon
.tl:    move.w  M_X(a1),d0                  ; tarde: (x, lo)
        move.w  d0,(a5)+
        add.w   M_A(a1),d0
        move.w  d0,(a5)+
.lon:   move.w  M_LON(a1),d0
        cmp.w   d0,d4
        ble.s   .nx
        move.w  d0,d4
.nx:    lea     MLDR(a1),a1
        cmp.l   a0,a1
        bne.s   .ld
        move.w  d2,LT_MAXA(a4)
        move.w  d3,LT_MINB(a4)
        move.w  d4,LT_MINL(a4)
        lea     LT_WL(a4),a1
        move.l  a2,d0
        sub.l   a1,d0
        lsr.w   #2,d0
        move.w  d0,LT_NW(a4)
        lea     LT_TL(a4),a1
        move.l  a5,d0
        sub.l   a1,d0
        lsr.w   #2,d0
        move.w  d0,LT_NT(a4)
        move.l  (sp)+,a5
.ret:   rts
.ch:    subq.w  #2,d1                       ; 1: MOVE detras del anterior
        bmi.s   .mv
        beq.s   .f1                         ; 2: un relleno; 3: dos
        move.l  #$01fe0000,(a3)+
.f1:    move.l  #$01fe0000,(a3)+
        bra.s   .mv

;----------------------------------------------------------------------
; --- mid_rebase --- la linea ya escrita, sin reescribirla (build_mid)
; entrada:  a4 = linetab[L], d6 = s, d5 = s + LASTX
; salida:   d0 = 0 hecho; d0 != 0: no se puede (mid_full)
; registros destruidos: d0-d4/d7/a0-a3
;----------------------------------------------------------------------
mid_rebase:
        move.l  LT_KLO(a4),a1
        move.l  LT_KHI(a4),a0               ; khi nuevo: la primera con
        move.l  a0,a2                       ; x > s + LASTX (a2 = el viejo)
.hif:   cmp.w   M_X(a0),d5
        blt.s   .hib
        lea     MLDR(a0),a0
        bra.s   .hif
.hib:   cmp.l   a1,a0
        beq.s   .hid
        cmp.w   M_X-MLDR(a0),d5
        bge.s   .hid
        lea     -MLDR(a0),a0
        bra.s   .hib
.hid:   cmp.l   a2,a0
        beq.s   .base                       ; igual
        bhi.s   .app
        ;--- salieron por la derecha: cortar en a0 (el viejo a2)
        move.l  a0,LT_KHI(a4)
        move.l  LT_SEG(a4),a3               ; donde cae a0 en el segmento
        cmp.l   a1,a0
        beq.s   .tcut
        addq.l  #8,a3                       ; la primera: WAIT + MOVE
        lea     MLDR(a1),a2
.tw:    cmp.l   a0,a2
        beq.s   .tcut
        move.w  M_CLS(a2),d0                ; 0: 8, 1: 4, 2: 8, 3: 12
        add.w   d0,d0
        move.w  .tsz(pc,d0.w),d0
        add.w   d0,a3
        lea     MLDR(a2),a2
        bra.s   .tw
.tsz:   dc.w    8,4,8,12
.tcut:  move.l  a3,d0
        sub.l   LT_SEG(a4),d0
        move.w  d0,LT_WEND(a4)
        move.l  LT_JMP(a4),(a3)+
        move.l  LT_JMP+4(a4),(a3)+
        move.l  LT_JMP+8(a4),(a3)+
        clr.w   LT_NW(a4)                   ; el estado, de nuevo (sin
        clr.w   LT_NT(a4)                   ; escribir: a3 a un lado)
        move.w  #-16000,LT_MAXA(a4)
        move.w  #16000,LT_MINB(a4)
        move.w  #$7fff,LT_MINL(a4)
        move.l  #scratch_seg,a3
        move.l  LT_SEG(a4),-(sp)
        move.l  a3,LT_SEG(a4)               ; los desplazamientos de los
        moveq   #1,d1                       ; WAIT salen relativos: iguales
        bsr     mid_put
        move.l  (sp)+,LT_SEG(a4)
        move.w  #$8000,LT_S0(a4)            ; (el WAIT nuevo no esta; ninguno
        bra.s   .base                       ; cambia, pero se reescriben)
        ;--- entraron por la derecha: agregarlas
.app:   move.l  a0,d0
        sub.l   a1,d0
        cmp.w   #MIDMAX*MLDR,d0
        bhi.s   .no                         ; no entran: mid_full
        move.l  a0,LT_KHI(a4)
        move.l  LT_SEG(a4),a3
        add.w   LT_WEND(a4),a3
        moveq   #0,d1
        cmp.l   a1,a2                       ; no habia ninguna: la primera
        seq     d1                          ; con WAIT
        and.w   #1,d1
        move.l  a2,a1
        bsr     mid_put
        move.l  a3,d0
        sub.l   LT_SEG(a4),d0
        move.w  d0,LT_WEND(a4)
        move.l  LT_JMP(a4),(a3)+
        move.l  LT_JMP+4(a4),(a3)+
        move.l  LT_JMP+8(a4),(a3)+
        move.w  #$8000,LT_S0(a4)            ; los WAIT nuevos, sin h
.base:  bra     mid_base
.no:    moveq   #1,d0
        rts

;----------------------------------------------------------------------
; --- mid_base --- elige la base de la linea, reescribe el byte h de cada
; WAIT si cambio y calcula [vl, vu) (build_mid)
; entrada:  a4 = linetab[L] (con klo, khi, listas y agregados), d6 = s,
;           d5 = s + LASTX
; salida:   d0 = 0 hecho; d0 != 0: con estas cargas no hay base
; registros destruidos: d0-d4/d7/a0-a3
;----------------------------------------------------------------------
mid_base:
        move.l  LT_KLO(a4),a1
        move.l  LT_KHI(a4),a0
        move.w  M_PL(a1),d3                 ; vl = PL(klo)
        move.w  M_SR(a0),d4                 ; vu = SR(khi) - LASTX
        sub.w   #LASTX,d4
        cmp.l   a1,a0
        beq     .val                        ; nada escrito
        cmp.w   M_X(a0),d5                  ; khi en pantalla: no entraron
        blt.s   .nc                         ; todas (MIDMAX); se rehace
        move.w  M_X(a1),d4                  ; cuando la primera sale
        addq.w  #1,d4
.nc:    ;--- canonica si hay una tarde viva
        move.w  LT_NT(a4),d7
        beq.s   .free
        lea     LT_TL(a4),a2
        subq.w  #1,d7
.tv:    cmp.w   2(a2),d6                    ; lo > s: viva
        blt.s   .can
        addq.l  #4,a2
        dbf     d7,.tv
        ;--- delta en (-minb, -maxa] y pantalla: x(klo) - s0 >= TMIN,
        ; x(khi - 1) - s0 <= LASTX
.free:  move.w  LT_MAXA(a4),d1
        neg.w   d1                          ; d1 = -maxa (el mayor)
        move.w  LT_MINB(a4),d2
        neg.w   d2
        addq.w  #1,d2                       ; d2 = 1 - minb (el menor)
        move.w  M_X(a1),d0
        sub.w   d6,d0
        sub.w   #TMIN,d0
        cmp.w   d0,d1
        ble.s   .h2
        move.w  d0,d1
.h2:    move.w  M_X-MLDR(a0),d0
        sub.w   d5,d0
        cmp.w   d0,d2
        bge.s   .l2
        move.w  d0,d2
.l2:    cmp.w   d1,d2
        bgt.s   .no                         ; no hay
        move.b  mdir(pc),d0
        beq.s   .rt
        move.w  d2,d1                       ; a la izquierda, la menor
.rt:    add.w   d6,d1                       ; d1 = s0
        move.w  d1,d0
        add.w   LT_MAXA(a4),d0              ; vl: s0 + maxa
        cmp.w   d0,d3
        bge.s   .f1
        move.w  d0,d3
.f1:    move.w  d1,d0
        add.w   LT_MINB(a4),d0              ; vu: s0 + minb
        cmp.w   d0,d4
        ble.s   .f2
        move.w  d0,d4
.f2:    move.w  LT_NT(a4),d7                ; las tardes (muertas) reviven
        beq.s   .put                        ; al volver: vl = lo
        lea     LT_TL(a4),a2
        subq.w  #1,d7
.fd:    move.w  2(a2),d0
        cmp.w   d0,d3
        bge.s   .fd1
        move.w  d0,d3
.fd1:   addq.l  #4,a2
        dbf     d7,.fd
        bra.s   .put
.no:    moveq   #1,d0
        rts
        ;--- canonica: s0 = s; la celda de cada tarde viva
.can:   move.w  M_X(a1),d0                  ; pantalla
        sub.w   d6,d0
        cmp.w   #TMIN,d0
        blt.s   .no
        move.w  d6,d1                       ; s0 = s
        move.w  d1,d0
        add.w   LT_MAXA(a4),d0              ; las no tardes: [s + maxa,
        cmp.w   d0,d3                       ; s + minb)
        bge.s   .c1
        move.w  d0,d3
.c1:    move.w  d1,d0
        add.w   LT_MINB(a4),d0
        cmp.w   d0,d4
        ble.s   .c2
        move.w  d0,d4
.c2:    move.w  LT_NT(a4),d7
        lea     LT_TL(a4),a2
        subq.w  #1,d7
.cl:    cmp.w   2(a2),d6                    ; muerta: nada
        bge.s   .cn
        move.w  (a2),d0                     ; s en (c0, c0 + 8],
        sub.w   d6,d0                       ; c0 = x - ((x - s + 8) & ~7)
        addq.w  #8,d0
        and.w   #$fff8,d0
        neg.w   d0
        add.w   (a2),d0
        addq.w  #1,d0
        cmp.w   d0,d3
        bge.s   .c3
        move.w  d0,d3
.c3:    addq.w  #8,d0
        cmp.w   d0,d4
        ble.s   .cn
        move.w  d0,d4
.cn:    addq.l  #4,a2
        dbf     d7,.cl
        ;--- las h, si la base cambio
.put:   cmp.w   LT_S0(a4),d1
        beq.s   .lon
        move.w  d1,LT_S0(a4)
        lea     htab(pc),a2
        sub.w   d1,a2                       ; a2 = htab - s0
        move.l  LT_SEG(a4),a3
        lea     LT_WL(a4),a1
        move.w  LT_NW(a4),d7
        subq.w  #1,d7
        moveq   #0,d0
.hp:    move.w  (a1)+,d0                    ; desplazamiento del byte h
        move.w  (a1)+,d2                    ; x
        move.b  (a2,d2.w),(a3,d0.l)         ; P40 ok: d0 < 256
        dbf     d7,.hp
.lon:   move.w  LT_MINL(a4),d0              ; lonext de las escritas
        cmp.w   d0,d4
        ble.s   .val
        move.w  d0,d4
.val:   cmp.w   d6,d3                       ; si no vale ni en s (no deberia),
        bgt.s   .late                       ; vl = s y vu = s + 1: se
        cmp.w   d6,d4                       ; reescribe en cada frame (P50)
        bgt.s   .ok
.late:  move.w  d6,d3
        move.w  d6,d4
        addq.w  #1,d4
.ok:    move.w  d3,LT_VL(a4)
        move.w  d4,LT_VU(a4)
        moveq   #0,d0
        rts

