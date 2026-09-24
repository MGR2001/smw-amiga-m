;----------------------------------------------------------------------
; copbench.s - D8 opcion (d): cuantas MOVE del copper entran por linea
; con dual playfield de 6 planos en lowres (codigo desechable).
;
; tools/dpfsplit.py supone 1 MOVE cada 16 px en pantalla con 6 planos
; (los planos 5 y 6 ocupan 2 de los 4 ciclos pares de cada bloque de 8,
; y el copper solo usa ciclos pares). Esto lo mide.
;
; Pantalla: todos los pixeles = indice 1 (plano 1 a unos, el resto a
; ceros; modulo negativo, asi que un solo renglon de 42 bytes).  En cada
; linea de prueba el copper espera a (v, h) y encadena NMOVE MOVE a
; COLOR01 con el valor k = 1..NMOVE (R=0, G=k>>4, B=k&15), y al final
; COLOR01 = $F00.  En la captura, el ancho de cada franja k es la
; separacion entre MOVE, y la primera k visible dice cuantas se hicieron
; antes de que empiece la pantalla.  tools/copbench_read.py lo decodifica.
;
;   banda 0  v $40,$42..$4E  4 planos      WAIT h=$3C   (calibracion: 8 px)
;   banda 1  v $58,$5A..$66  5 planos      WAIT h=$3C
;   banda 2  v $70,$72..$7E  DPF 6 planos  WAIT h=$3C
;   banda 3  v $88,$8A..$96  DPF 6 planos  WAIT h=$D8 de la linea anterior
;                                       (cuantas entran en el borrado)
;   banda 4  v $A8..      DPF 6 planos  una rafaga de 100 MOVE (MOVE por linea)
;
; DMA de sprites encendido (punteros a un sprite vacio), fetch de 336 px
; (DDFSTRT $30) como el scroll fino real.
;
; Entrada (desde boot.s): A6 = ExecBase.  a4 = CUSTOM, a5 = variables.
;----------------------------------------------------------------------

        include "exec.i"

DIWSTRT     equ $08e
DIWSTOP     equ $090
DDFSTRT     equ $092
DDFSTOP     equ $094
BPLCON0     equ $100
BPLCON1     equ $102
BPLCON2     equ $104
BPL1MOD     equ $108
BPL2MOD     equ $10a
BPL1PTH     equ $0e0
SPR0PTH     equ $120
COLOR01     equ $182

FETCHB      equ 42                  ; 21 palabras por linea y plano
NMOVE       equ 36
COP_BYTES   equ 16384

V_ONES      equ 0
V_ZERO      equ 4
V_COP       equ 8
V_SIZE      equ 16

COL_NOMEM   equ $0f00

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
        bsr     alloc_chip                  ; MEMF_CLEAR: ceros (bitplanes y sprite)
        move.l  d0,V_ZERO(a5)
        move.l  #COP_BYTES,d0
        bsr     alloc_chip
        move.l  d0,V_COP(a5)

        bsr     build_copper

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
        move.w  #$83e0,DMACON(a4)           ; SET|DMAEN|BPLEN|COPEN|BLTEN|SPREN
.forever:
        bra.s   .forever

alloc_chip:
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq.s   .fail
        rts
.fail:  move.w  #COL_NOMEM,COLOR00(a4)
        bra.s   .fail

;----------------------------------------------------------------------
; build_copper
;----------------------------------------------------------------------
build_copper:
        move.l  V_COP(a5),a0
        move.l  #$008e2c81,(a0)+            ; DIWSTRT
        move.l  #$00902cc1,(a0)+            ; DIWSTOP
        move.l  #$00920030,(a0)+            ; DDFSTRT (una palabra antes)
        move.l  #$009400d0,(a0)+            ; DDFSTOP
        move.l  #$01004200,(a0)+            ; BPLCON0: arranca en 4 planos
        move.l  #$01020000,(a0)+
        move.l  #$01040024,(a0)+
        move.w  #BPL1MOD,(a0)+
        move.w  #-FETCHB,(a0)+              ; repetir el mismo renglon
        move.w  #BPL2MOD,(a0)+
        move.w  #-FETCHB,(a0)+
        ; bitplanes: 1 = unos, 2..6 = ceros
        move.w  #BPL1PTH,d1
        move.l  V_ONES(a5),d0
        bsr     .ptr
        moveq   #5-1,d2
.bp:    move.l  V_ZERO(a5),d0
        bsr     .ptr
        dbf     d2,.bp
        ; 8 sprites al sprite vacio
        move.w  #SPR0PTH,d1
        moveq   #8-1,d2
.sp:    move.l  V_ZERO(a5),d0
        bsr     .ptr
        dbf     d2,.sp
        move.l  #$01800000,(a0)+            ; COLOR00 negro
        move.l  #$01820fff,(a0)+            ; COLOR01 blanco

        ; banda 0: 4 planos
        move.w  #$4200,d3
        move.w  #$40,d4
        move.w  #$3c,d5
        moveq   #0,d6
        bsr     .band
        ; banda 1: 5 planos
        move.w  #$5200,d3
        move.w  #$58,d4
        bsr     .band
        ; banda 2: DPF 6 planos
        move.w  #$6600,d3
        move.w  #$70,d4
        bsr     .band
        ; banda 3: DPF 6 planos, arrancando en el borrado de la linea anterior
        move.w  #$88,d4
        move.w  #$d8,d5
        moveq   #1,d6
        bsr     .band
        ; banda 4: DPF 6 planos, UNA rafaga de 100 MOVE desde (v $A8, h $3C).
        ; La k del borde izquierdo de cada linea da las MOVE por linea entera.
        move.l  #$a83dfffe,(a0)+
        moveq   #1,d0
.long:  move.w  #COLOR01,(a0)+
        move.w  d0,(a0)+
        addq.w  #1,d0
        cmp.w   #100,d0
        bls.s   .long
        move.l  #$01820f00,(a0)+

        move.l  #$fffffffe,(a0)+
        rts

; .ptr: d1 = registro PTH, d0 = direccion -> dos MOVE; d1 += 4
.ptr:   swap    d0
        move.w  d1,(a0)+
        move.w  d0,(a0)+
        addq.w  #2,d1
        swap    d0
        move.w  d1,(a0)+
        move.w  d0,(a0)+
        addq.w  #2,d1
        rts

; .band: d3 = BPLCON0, d4 = primera linea, d5 = h del WAIT,
;        d6 = 1 si el WAIT es en la linea anterior
.band:  ; poner el modo dos lineas antes
        move.w  d4,d0
        subq.w  #2,d0
        lsl.w   #8,d0
        or.w    #$000f,d0                   ; WAIT (v-2, $0E): solo el byte bajo
        move.w  d0,(a0)+
        move.w  #$fffe,(a0)+
        move.w  #BPLCON0,(a0)+
        move.w  d3,(a0)+
        moveq   #8-1,d7
        move.w  d4,d2                       ; linea actual
.line:  move.w  d2,d0
        sub.w   d6,d0                       ; linea del WAIT
        lsl.w   #8,d0
        move.b  d5,d0
        or.w    #1,d0
        move.w  d0,(a0)+
        move.w  #$fffe,(a0)+
        moveq   #1,d0                       ; k
.mv:    move.w  #COLOR01,(a0)+
        move.w  d0,(a0)+
        addq.w  #1,d0
        cmp.w   #NMOVE,d0
        bls.s   .mv
        move.w  #COLOR01,(a0)+
        move.w  #$0f00,(a0)+                ; fin de la rafaga: rojo
        addq.w  #2,d2                       ; una linea si, otra no (sin solapes)
        dbf     d7,.line
        rts

        even
gfxname: dc.b    "graphics.library",0
        even
vars:   ds.b    V_SIZE
        even
