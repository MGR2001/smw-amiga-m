;----------------------------------------------------------------------
; copcal.s - calibracion del copper para el scroll (etapa 6, P39).
;
; Pantalla = la de scroll.s: DPF de 6 planos, DDFSTRT $30 / DDFSTOP $D0,
; DIW $2C81-$2CC1, sin DMA de sprites. Todos los pixeles = indice 1 de PF1
; (plano 1 a unos, el resto a ceros; modulo negativo: un solo renglon).
; Las lineas de prueba (work/copcal_lines.i) las genera tools/copcal.py,
; que tambien lee la captura: en que x cambia COLOR01 en cada prueba.
;
; Entrada (desde boot.s): A6 = ExecBase.  a4 = CUSTOM, a5 = variables.
;----------------------------------------------------------------------

        include "exec.i"

BPL1MOD     equ $108
BPL2MOD     equ $10a
BPL1PTH     equ $0e0
FETCHB      equ 42                  ; 21 palabras por linea y plano

V_ONES      equ 0
V_ZERO      equ 4
V_COP       equ 8
V_PAT       equ 12
V_SIZE      equ 16

        bra.w   entry
        dc.b    "A5PL"
hdr_data_off:   dc.l    0
hdr_data_len:   dc.l    0

entry:
        move.l  4.w,a6
        lea     CUSTOM,a4
        lea     vars(pc),a5
        moveq   #64,d0
        bsr     alloc_chip
        move.l  d0,V_ONES(a5)
        move.l  d0,a0
        moveq   #16-1,d1
.ones:  move.l  #$ffffffff,(a0)+
        dbf     d1,.ones
        moveq   #64,d0
        bsr     alloc_chip
        move.l  d0,V_ZERO(a5)
        ; -DPATTERN: PF1 plano 1 = $7FFF (el primer pixel de cada palabra a
        ; 0: una raya vertical de 1 px cada 16 px, que se corre con el
        ; retardo de BPLCON1) y PF2 plano 1 = unos (COLOR09 detras de las
        ; rayas; el borde fuera de la DIW queda en COLOR00)
        moveq   #64,d0
        bsr     alloc_chip
        move.l  d0,V_PAT(a5)
        move.l  d0,a0
        moveq   #32-1,d1
.pat:   move.w  #$7fff,(a0)+
        dbf     d1,.pat
        move.l  #COPEND-COPLIST,d0
        bsr     alloc_chip
        move.l  d0,V_COP(a5)
        ; copiar la lista y poner los punteros de plano
        lea     COPLIST(pc),a0
        move.l  V_COP(a5),a1
        move.w  #(COPEND-COPLIST)/2-1,d0
.cp:    move.w  (a0)+,(a1)+
        dbf     d0,.cp
        move.l  V_COP(a5),a1
        lea     PTRS-COPLIST+2(a1),a1       ; valor de BPL1PTH
        ifd     PATTERN
        move.l  V_PAT(a5),d0                ; BPL1 = PF1 plano 1
        bsr     .setp
        move.l  V_ONES(a5),d0               ; BPL2 = PF2 plano 1
        bsr     .setp
        moveq   #4-1,d2
        else
        move.l  V_ONES(a5),d0
        bsr     .setp
        moveq   #5-1,d2
        endc
.bp:    move.l  V_ZERO(a5),d0
        bsr     .setp
        dbf     d2,.bp

        jsr     _LVOForbid(a6)
        lea     gfxname(pc),a1
        moveq   #0,d0
        jsr     _LVOOpenLibrary(a6)
        tst.l   d0
        beq.s   .nogfx
        move.l  d0,a6
        sub.l   a1,a1
        jsr     _LVOLoadView(a6)
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOWaitTOF(a6)
.nogfx: move.l  4.w,a6
        move.w  #$7fff,INTENA(a4)
        move.w  #$7fff,INTREQ(a4)
        move.w  #$7fff,DMACON(a4)
        move.l  V_COP(a5),COP1LC(a4)
        move.w  #0,COPJMP1(a4)
        move.w  #$83c0,DMACON(a4)           ; como scroll.s: sin sprites
.forever:
        bra.s   .forever

.setp:  swap    d0                          ; a1 = valor de BPLxPTH
        move.w  d0,(a1)
        swap    d0
        move.w  d0,4(a1)
        addq.l  #8,a1
        rts

alloc_chip:
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq.s   .fail
        rts
.fail:  move.w  #$0f00,COLOR00(a4)
        bra.s   .fail

        even
COPLIST:
        dc.w    $008e,$2c81,$0090,$2cc1     ; DIW
        dc.w    $0092,$0030,$0094,$00d0     ; DDF: como el scroll
        dc.w    $0100,$6600,$0102,$0000,$0104,$0000
        dc.w    BPL1MOD,-FETCHB,BPL2MOD,-FETCHB
PTRS:   dc.w    $00e0,0,$00e2,0,$00e4,0,$00e6,0,$00e8,0,$00ea,0
        dc.w    $00ec,0,$00ee,0,$00f0,0,$00f2,0,$00f4,0,$00f6,0
        dc.w    $0180,$0000,$0182,$0fff
        dc.w    $0192,$0444                 ; COLOR09: PF2 (solo con PATTERN)
        include "copcal_lines.i"
        dc.w    $ffff,$fffe
COPEND:

gfxname: dc.b    "graphics.library",0
        even
vars:   ds.b    V_SIZE
        even
