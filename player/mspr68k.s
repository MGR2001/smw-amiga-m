;----------------------------------------------------------------------
; mspr68k.s - Etapa 6b.4: Mario en sprites de hardware, a mano. Hace lo
; mismo que mario_sprite() de player/mspr.c (que queda como referencia y
; para los casos raros) en el caso de siempre: las entradas de OAM que se
; ven son de 16x16, estan en la misma X, sin volteo vertical y no se
; tapan entre si (Mario: arriba y abajo). Entonces cada linea de 16 px de
; una pareja de sprites sale de dos filas de tiles de la SNES sin
; convertir nada: en un tile de 4 bpp la fila r tiene los planos 0-1 en
; la palabra 2r y los 2-3 en la 16 + 2r, y MOVEP.W escribe los bytes de
; una palabra en direcciones alternas: el tile izquierdo en los bytes
; altos de DATA/DATB, el derecho en los bajos. Volteo horizontal: los
; tiles de gfx32f (los bytes con los bits al reves, tools/mkmario.py) y
; el izquierdo y el derecho cambiados.
;
; Lo incluye player/game.s (a4 = binstart: datos del C por (a4)).
;----------------------------------------------------------------------

; --- mspr_draw ---
; entrada:  a2 = buffer de 4 sprites de MSPR_WORDS palabras, a4 = binstart
; salida:   como mario_sprite(a2, $2C, $A0)
; registros destruidos: d0-d7/a0-a3/a5-a6 (guarda a2 y a4)
mspr_draw:
        lea     _mario_oam(a4),a0
        lea     _mario_osz(a4),a1
        lea     mspr_ent(pc),a3             ; entradas que se ven: y, tile, prop
        moveq   #0,d7                       ; cuantas
        move.w  #$7fff,d5                   ; by: la y mas chica
        move.w  #-$7fff,d6                  ; y1: la mas grande + 16
        moveq   #3,d4                       ; entrada
.e:     move.b  1(a0),d1                    ; y
        cmp.b   #$f0,d1
        beq.s   .next
        btst    #1,(a1)                     ; 16x16
        beq     .slow
        btst    #7,3(a0)                    ; sin volteo vertical
        bne     .slow
        moveq   #0,d0                       ; x: 9 bits con signo
        move.b  (a0),d0
        btst    #0,(a1)
        beq.s   .x8
        sub.w   #256,d0
.x8:    ext.w   d1                          ; y: $F1-$FF = -15..-1 (d1.b)
        cmp.w   #-16,d1                     ; (la y va a d1.w)
        blt.s   .ypos
        bra.s   .yok
.ypos:  and.w   #$ff,d1
.yok:   tst.w   d7
        bne.s   .same
        move.w  d0,d3                       ; d3 = la x de todas
        bra.s   .add
.same:  cmp.w   d0,d3
        bne     .slow
.add:   move.w  d1,(a3)+                    ; y
        move.b  2(a0),(a3)+                 ; tile
        move.b  3(a0),(a3)+                 ; prop
        cmp.w   d5,d1
        bge.s   .b1
        move.w  d1,d5
.b1:    add.w   #16,d1
        cmp.w   d6,d1
        ble.s   .b2
        move.w  d1,d6
.b2:    addq.w  #1,d7
.next:  addq.l  #4,a0
        addq.l  #1,a1
        dbf     d4,.e

        lea     mspr_n(pc),a0
        move.w  d7,(a0)
        beq     .none
        move.w  d6,d0                       ; alto
        sub.w   d5,d0
        cmp.w   #MSPR_H,d0
        bhi     .slow
        ; que no se tapen: |y_i - y_j| >= 16 para cada par
        lea     mspr_ent(pc),a0
        move.w  d7,d1
        subq.w  #2,d1
        bmi.s   .ov2
.ov:    move.w  (a0),d2
        lea     4(a0),a1
        move.w  d1,d4
.ov1:   move.w  (a1),d0
        sub.w   d2,d0
        bpl.s   .abs
        neg.w   d0
.abs:   cmp.w   #16,d0
        blo     .slow
        addq.l  #4,a1
        dbf     d4,.ov1
        addq.l  #4,a0
        dbf     d1,.ov
.ov2:
        ; --- cabeceras: SPR0/SPR1 (pareja), SPR2/SPR3 vacios -----------
        move.w  d6,d4
        sub.w   d5,d4                       ; d4 = n lineas
        move.w  d5,d0
        add.w   #$2c+1,d0                   ; vs (+1: la SNES dibuja una
        move.w  d0,d1                       ; linea mas abajo)
        add.w   d4,d1                       ; ve
        move.w  d3,d2
        add.w   #$a0,d2                     ; hs
        moveq   #0,d6                       ; POS
        move.b  d0,d6
        lsl.w   #8,d6
        move.w  d2,d7
        lsr.w   #1,d7
        move.b  d7,d6
        moveq   #0,d7                       ; CTL
        move.b  d1,d7
        lsl.w   #8,d7
        btst    #8,d0
        beq.s   .c1
        addq.w  #4,d7
.c1:    btst    #8,d1
        beq.s   .c2
        addq.w  #2,d7
.c2:    btst    #0,d2
        beq.s   .c3
        addq.w  #1,d7
.c3:    move.l  a2,a0                       ; SPR0
        lea     MSPR_WORDS*2(a2),a1         ; SPR1 (adosado)
        move.w  d6,(a0)+
        move.w  d7,(a0)+
        move.w  d6,(a1)+
        or.w    #$80,d7
        move.w  d7,(a1)+
        move.w  d4,d0                       ; lineas en 0, y el final
        subq.w  #1,d0
.clr:   clr.l   (a0)+
        clr.l   (a1)+
        dbf     d0,.clr
        clr.l   (a0)
        clr.l   (a1)
        clr.l   MSPR_WORDS*4(a2)            ; SPR2, SPR3: nada
        clr.l   MSPR_WORDS*6(a2)

        ; --- cada entrada: 16 lineas desde y - by -----------------------
        lea     mspr_ent(pc),a6
        moveq   #0,d7                       ; entrada
.ent:   cmp.w   mspr_n(pc),d7
        bhs     .ok
        move.w  (a6)+,d0                    ; y
        sub.w   d5,d0
        lsl.w   #2,d0
        lea     4(a2,d0.w),a0               ; a0 = linea en SPR0
        lea     MSPR_WORDS*2(a0),a1         ; a1 = en SPR1
        moveq   #0,d6
        move.b  (a6)+,d6                    ; tile
        move.b  (a6)+,d2                    ; prop
        movem.l d5/d7/a6,-(sp)
        moveq   #0,d4                       ; fila de tiles (0: arriba, 16)
.half:  move.w  d6,d0                       ; izquierdo: t + 16 fila
        add.w   d4,d0
        move.w  d0,d1
        addq.w  #1,d1                       ; derecho: + 1
        btst    #6,d2
        beq.s   .nf
        exg     d0,d1                       ; volteado: al reves
.nf:    bsr     mspr_tile
        beq     .slowp                      ; (no es de Mario)
        move.l  a3,a5                       ; a5 = izquierdo
        move.w  d1,d0
        bsr     mspr_tile
        beq     .slowp
        moveq   #8-1,d0                     ; a3 = derecho
.row:   move.w  (a5)+,d1                    ; planos 0-1
        movep.w d1,0(a0)
        move.w  (a3)+,d1
        movep.w d1,1(a0)
        move.w  14(a5),d1                   ; planos 2-3
        movep.w d1,0(a1)
        move.w  14(a3),d1
        movep.w d1,1(a1)
        addq.l  #4,a0
        addq.l  #4,a1
        dbf     d0,.row
        add.w   #16,d4
        cmp.w   #32,d4
        blo.s   .half
        movem.l (sp)+,d5/d7/a6
        addq.w  #1,d7
        bra     .ent
.ok:    rts

.none:  clr.l   (a2)                        ; Mario no se ve
        clr.l   MSPR_WORDS*2(a2)
        clr.l   MSPR_WORDS*4(a2)
        clr.l   MSPR_WORDS*6(a2)
        rts

.slowp: movem.l (sp)+,d5/d7/a6
.slow:  lea     mspr_slow(pc),a0            ; el caso raro: el C
        addq.w  #1,(a0)
        pea     $a0.w                       ; hx0
        pea     $2c.w                       ; vy0
        move.l  a2,-(sp)
        move.l  a4,a0
        add.l   #_mario_sprite-binstart,a0
        jsr     (a0)
        lea     12(sp),sp
        rts

; mspr_tile: d0.w = tile de la VRAM de sprites -> a3 = sus 32 bytes en
; gfx32 (o gfx32f si d2 bit 6: volteado); Z = 1 si no es de Mario.
; Como vram_tile() de mspr.c. Destruye d0, a3 (guarda d1).
mspr_tile:
        move.l  d1,-(sp)
        cmp.w   #$7f,d0
        bne.s   .t1
        lea     _ram+$0D99(a4),a3           ; wm_Tile7FPtr
        moveq   #0,d1
        bra.s   .ptr
.t1:    cmp.w   #$20,d0
        bhs.s   .no
        move.w  d0,d1
        and.w   #15,d1
        cmp.w   #10,d1
        bhs.s   .no
        lsr.w   #1,d1
        add.w   d1,d1                       ; 2 * puntero
        btst    #4,d0
        beq.s   .r0
        add.w   #10,d1                      ; fila 1: wm_0D85 + 10
.r0:    lea     _ram+$0D85(a4),a3
        add.w   d1,a3
        moveq   #0,d1
        btst    #0,d0
        beq.s   .ptr
        moveq   #32,d1                      ; la segunda mitad
.ptr:   moveq   #0,d0                       ; R16 (la SNES: bajo primero)
        move.b  1(a3),d0
        lsl.w   #8,d0
        move.b  (a3),d0
        add.w   d1,d0
        sub.w   #$2000,d0                   ; GFX32 en $7E:2000
        bcs.s   .no
        cmp.w   #$5d00-32,d0
        bhi.s   .no
        move.l  a4,a3
        btst    #6,d2
        bne.s   .fl
        add.l   #gfx32-binstart,a3
        bra.s   .ad
.fl:    add.l   #gfx32f-binstart,a3
.ad:    add.w   d0,a3
        move.l  (sp)+,d1
        moveq   #1,d0                       ; Z = 0
        rts
.no:    move.l  (sp)+,d1
        moveq   #0,d0                       ; Z = 1
        rts

MSPR_H      equ 40                          ; mario.h: MSPR_LINES
mspr_ent:   ds.w    4*2                     ; y, tile + prop (4 entradas)
mspr_n:     dc.w    0
mspr_slow:  dc.w    0                       ; veces que fue al C
        even
