;----------------------------------------------------------------------
; scroll.s - Etapa 6, primer prototipo: el nivel real en la Amiga, en el
; formato de D8 (d), desplazandose solo hacia la derecha.
;
;   PF1 (planos impares) = capa 1: buffer circular de 22 columnas de
;       bloques escrito dos veces (704 px), 3 planos entrelazados. Cada 16
;       px de scroll se dibuja UNA columna nueva (fuera de la pantalla).
;   PF2 (planos pares)   = capa 2: mapa de bits de 848 px (periodo de 512
;       + 336) a media velocidad: paralaje por hardware (BPLCON1 bits 4-7).
;   Colores: lista del copper por linea (2 WAIT + 7 MOVE de la capa 1 + 7
;       de la capa 2). PROTOTIPO: la capa 1 solo recibe las cargas del
;       borrado (tools/mkscroll.py), NO las de mitad de linea.
;
; Datos: work/yi1_s.dat (tools/mkscroll.py). Ventana vertical fija: lineas
; 192..415 del nivel (la camara de Yoshi's Island 1 no se mueve en Y).
;
; Scroll: la columna de pantalla 0 muestra la x = s del nivel. Con el
; fetch adelantado una palabra (DDFSTRT $30): puntero = palabra
; (s - 1) >> 4 y retardo (-s) & 15.
;
;   vasmm68k_mot -Fbin -m68000 -I player -o work/scroll.bin player/scroll.s
;   python3 tools/mkadf.py --boot work/boot.bin --stage2 work/scroll.bin \
;       --data work/yi1_s.dat --out work/scroll.adf
;   (-DSTOPX=n: para en s = n; por defecto recorre el nivel entero)
;
; Registros vivos en el bucle: a3 = datos  a4 = CUSTOM  a5 = variables
;----------------------------------------------------------------------

        include "exec.i"

        ifnd    STOPX
STOPX   equ     4800            ; 5120 - 320: el final del nivel
        endc
        ifnd    SPEED
SPEED   equ     2               ; px por frame
        endc

LINES   equ     224
SLOTS   equ     22              ; columnas del buffer circular (x2)
ROWB1   equ     SLOTS*2*2       ; bytes de una fila de un plano de PF1 (88)
LINEB1  equ     ROWB1*3         ; 264
ROWB2   equ     106             ; 848 px
LINEB2  equ     ROWB2*3         ; 318
BUF1    equ     LINEB1*LINES    ; 59136

; lista del copper
CL_BPLCON1  equ 20+2
CL_COLOR00  equ 36+2
CL_PTR      equ 44              ; BPL1PTH; BPLnPTH en CL_PTR + (n-1)*8
CL_LINES    equ 92
CL_LINE     equ 64
CL_SIZE     equ CL_LINES+CL_LINE*LINES+4

; cabecera de yi1_s.dat
D_W     equ 4
D_COLS  equ 6
D_SKY   equ 10
D_BLK   equ 16
D_MAP   equ 20
D_INI   equ 24
D_CHG   equ 28
D_L2B   equ 32
D_L2P   equ 36

; variables (a5)
V_S     equ 0                   ; scroll de la capa 1 (px)
V_P     equ 2                   ; palabra del puntero, (s - 1) >> 4
V_CHG   equ 4                   ; .l siguiente cambio de color
V_BUF1  equ 8                   ; .l buffer de PF1
V_COP   equ 12                  ; .l lista del copper
V_SIZE  equ 16

        bra.w   entry
        dc.b    "A5PL"
hdr_data_off:   dc.l    0
hdr_data_len:   dc.l    0

entry:
        move.l  4.w,a6
        move.l  a1,a2                       ; a2 = IOStdReq
        lea     CUSTOM,a4
        move.w  #$0f80,COLOR00(a4)
        lea     vars(pc),a5

        ;--- datos a Chip RAM ----------------------------------------
        move.l  hdr_data_len(pc),d2
        beq     fail
        add.l   #511,d2
        and.l   #$fffffe00,d2
        move.l  d2,d0
        move.l  #MEMF_CHIP,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     fail
        move.l  d0,a3
        move.l  a2,a1
        move.w  #CMD_READ,IO_COMMAND(a1)
        move.l  d2,IO_LENGTH(a1)
        move.l  a3,IO_DATA(a1)
        move.l  hdr_data_off(pc),IO_OFFSET(a1)
        jsr     _LVODoIO(a6)
        tst.l   d0
        bne     fail
        move.l  a2,a1
        move.w  #TD_MOTOR,IO_COMMAND(a1)
        clr.l   IO_LENGTH(a1)
        jsr     _LVODoIO(a6)

        move.l  #BUF1,d0
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     fail
        move.l  d0,V_BUF1(a5)
        move.l  #CL_SIZE,d0
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     fail
        move.l  d0,V_COP(a5)

        bsr     build_copper
        clr.w   V_S(a5)
        move.w  #-1,V_P(a5)
        move.l  a3,a0
        add.l   D_CHG(a3),a0
        move.l  a0,V_CHG(a5)
        moveq   #0,d7                       ; columnas 0..21
.init:  move.w  d7,d0
        bsr     draw_column
        addq.w  #1,d7
        cmp.w   #SLOTS,d7
        blo.s   .init
        bsr     set_pointers

        ;--- tomar el hardware (como demo.s) -------------------------
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
.nogfx:
        move.l  4.w,a6
        lea     CUSTOM,a4
        move.w  #$7fff,INTENA(a4)
        move.w  #$7fff,INTREQ(a4)
        move.w  #$7fff,DMACON(a4)
        move.l  V_COP(a5),COP1LC(a4)
        move.w  #0,COPJMP1(a4)
        move.w  #$8380,DMACON(a4)           ; MASTER|BPLEN|COPEN

;----------------------------------------------------------------------
; Bucle por frame: todo despues de la ultima linea visible ($10C).
;----------------------------------------------------------------------
frame:
.w1:    move.l  VPOSR(a4),d0
        lsr.l   #8,d0
        and.w   #$1ff,d0
        cmp.w   #$110,d0
        blo.s   .w1
        move.w  V_S(a5),d0
        cmp.w   #STOPX,d0
        bhs.s   .same
        addq.w  #SPEED,d0
        cmp.w   #STOPX,d0
        bls.s   .ok
        move.w  #STOPX,d0
.ok:    move.w  d0,V_S(a5)
.same:
        bsr     set_pointers
        bsr     apply_colors
        ; columna nueva: cuando cambia la palabra del puntero
        move.w  V_S(a5),d0
        subq.w  #1,d0
        asr.w   #4,d0
        cmp.w   V_P(a5),d0
        beq.s   .w2
        move.w  d0,V_P(a5)
        add.w   #SLOTS-1,d0                 ; p + 21: la que entra despues
        cmp.w   D_COLS(a3),d0
        bhs.s   .w2
        bsr     draw_column
.w2:    move.l  VPOSR(a4),d0                ; esperar a que empiece otro frame
        lsr.l   #8,d0
        and.w   #$1ff,d0
        cmp.w   #$110,d0
        bhs.s   .w2
        bra.s   frame

;----------------------------------------------------------------------
; --- set_pointers ---
; entrada:  V_S
; salida:   BPLCON1 y los 6 punteros de plano en la lista del copper
; registros destruidos: d0-d3/a0-a1
;----------------------------------------------------------------------
set_pointers:
        move.l  V_COP(a5),a1
        move.w  V_S(a5),d0
        ; PF1: palabra (s - 1) >> 4, en el buffer circular (p + 22) mod 22
        move.w  d0,d1
        subq.w  #1,d1
        asr.w   #4,d1
        add.w   #SLOTS,d1
        ext.l   d1
        divu    #SLOTS,d1
        swap    d1                          ; resto
        add.w   d1,d1
        moveq   #0,d2
        move.w  d1,d2
        add.l   V_BUF1(a5),d2
        lea     CL_PTR+2(a1),a0             ; BPL1PTH
        moveq   #3-1,d3
.p1:    swap    d2
        move.w  d2,(a0)
        swap    d2
        move.w  d2,4(a0)
        add.l   #ROWB1,d2
        lea     16(a0),a0                   ; BPL1 -> BPL3 -> BPL5
        dbf     d3,.p1
        ; PF2: t = (s >> 1) mod 512, +512 si t < 16; palabra (t - 1) >> 4
        move.w  d0,d1
        lsr.w   #1,d1
        and.w   #511,d1
        cmp.w   #16,d1
        bhs.s   .t
        add.w   #512,d1
.t:     move.w  d1,d3                       ; d3 = t (para el retardo)
        subq.w  #1,d1
        lsr.w   #4,d1
        add.w   d1,d1
        moveq   #0,d2
        move.w  d1,d2
        add.l   a3,d2
        add.l   D_L2B(a3),d2
        lea     CL_PTR+8+2(a1),a0           ; BPL2PTH
        swap    d3
        move.w  #3-1,d3
.p2:    swap    d2
        move.w  d2,(a0)
        swap    d2
        move.w  d2,4(a0)
        add.l   #ROWB2,d2
        lea     16(a0),a0
        dbf     d3,.p2
        swap    d3                          ; t
        neg.w   d3
        and.w   #15,d3
        lsl.w   #4,d3                       ; retardo PF2
        neg.w   d0
        and.w   #15,d0                      ; retardo PF1
        or.w    d3,d0
        move.w  d0,CL_BPLCON1(a1)
        rts

;----------------------------------------------------------------------
; --- apply_colors ---
; aplica los cambios de color de la capa 1 con x <= s (tools/mkscroll.py)
; registros destruidos: d0-d2/a0-a1
;----------------------------------------------------------------------
apply_colors:
        move.l  V_CHG(a5),a0
        move.l  V_COP(a5),a1
        lea     CL_LINES(a1),a1
        move.w  V_S(a5),d0
.l:     cmp.w   (a0),d0
        blo.s   .done                       ; x > s ($FFFF: fin)
        move.w  2(a0),d1
        move.w  4(a0),(a1,d1.w)
        addq.l  #6,a0
        bra.s   .l
.done:  move.l  a0,V_CHG(a5)
        rts

;----------------------------------------------------------------------
; --- draw_column ---
; entrada:  d0.w = columna de bloques del nivel
; salida:   la columna, en sus dos copias del buffer circular de PF1
; registros destruidos: d0-d3/a0-a2
; ciclos:   ~24 000 (CPU; 224 lineas x 3 planos x 2 copias)
; PROTOTIPO: con la CPU. El definitivo va por blitter (§12).
;----------------------------------------------------------------------
draw_column:
        move.w  d0,d1
        mulu    #15,d1
        move.l  a3,a1
        add.l   D_MAP(a3),a1
        add.l   d1,a1                       ; a1 = MAP[c * 15]
        moveq   #0,d1
        move.w  d0,d1
        divu    #SLOTS,d1
        swap    d1
        add.w   d1,d1
        move.l  V_BUF1(a5),a2
        add.w   d1,a2                       ; a2 = columna en el buffer
        moveq   #LINES/16-1,d3
.blk:   moveq   #0,d0
        move.b  (a1)+,d0
        mulu    #96,d0
        move.l  a3,a0
        add.l   D_BLK(a3),a0
        add.l   d0,a0                       ; a0 = bloque
        moveq   #16-1,d2
.row:   move.w  (a0)+,d0
        move.w  d0,(a2)
        move.w  d0,SLOTS*2(a2)
        move.w  (a0)+,d0
        move.w  d0,ROWB1(a2)
        move.w  d0,ROWB1+SLOTS*2(a2)
        move.w  (a0)+,d0
        move.w  d0,ROWB1*2(a2)
        move.w  d0,ROWB1*2+SLOTS*2(a2)
        lea     LINEB1(a2),a2
        dbf     d2,.row
        dbf     d3,.blk
        rts

;----------------------------------------------------------------------
; --- build_copper ---
; la lista fija; los colores iniciales de las dos capas por linea
; registros destruidos: d0-d4/a0-a2
;----------------------------------------------------------------------
build_copper:
        move.l  V_COP(a5),a0
        move.l  #$008e2c81,(a0)+            ; DIWSTRT
        move.l  #$00900cc1,(a0)+            ; DIWSTOP: 224 lineas
        move.l  #$00920030,(a0)+            ; DDFSTRT: una palabra antes
        move.l  #$009400d0,(a0)+            ; DDFSTOP
        move.l  #$01006600,(a0)+            ; BPLCON0: 6 planos, DBLPF, COLOR
        move.l  #$01020000,(a0)+            ; BPLCON1 (set_pointers)
        move.l  #$01040000,(a0)+            ; BPLCON2: PF1 delante
        move.w  #$0108,(a0)+
        move.w  #LINEB1-42,(a0)+            ; BPL1MOD
        move.w  #$010a,(a0)+
        move.w  #LINEB2-42,(a0)+            ; BPL2MOD
        move.w  #COLOR00,(a0)+
        move.w  D_SKY(a3),(a0)+
        move.l  #$01900000,(a0)+            ; COLOR08 (transparente en PF2)
        move.w  #$00e0,d0                   ; BPL1PTH..BPL6PTL
        moveq   #12-1,d1
.ptr:   move.w  d0,(a0)+
        clr.w   (a0)+
        addq.w  #2,d0
        dbf     d1,.ptr
        ; lineas
        move.l  a3,a1
        add.l   D_INI(a3),a1
        move.l  a3,a2
        add.l   D_L2P(a3),a2
        moveq   #0,d2                       ; d2 = linea
.line:  move.w  d2,d0
        add.w   #$2c,d0                     ; posicion vertical
        move.w  d0,d3
        lsl.w   #8,d3
        or.w    #$0007,d3
        cmp.w   #$100,d0
        bne.s   .nowrap
        move.l  #$ffdffffe,(a0)+            ; cruzar la linea 255
        bra.s   .w
.nowrap:
        move.w  d3,(a0)+
        move.w  #$fffe,(a0)+
.w:     move.w  d3,(a0)+
        move.w  #$fffe,(a0)+
        move.w  #$0182,d0                   ; COLOR01..07: capa 1
        moveq   #7-1,d1
.c1:    move.w  d0,(a0)+
        move.w  (a1)+,(a0)+
        addq.w  #2,d0
        dbf     d1,.c1
        move.w  #$0192,d0                   ; COLOR09..15: capa 2
        moveq   #7-1,d1
.c2:    move.w  d0,(a0)+
        move.w  (a2)+,(a0)+
        addq.w  #2,d0
        dbf     d1,.c2
        addq.w  #1,d2
        cmp.w   #LINES,d2
        blo.s   .line
        move.l  #$fffffffe,(a0)+
        rts

fail:   lea     CUSTOM,a4
.l:     move.w  #$0f00,COLOR00(a4)
        bra.s   .l

        even
vars:   ds.b    V_SIZE
gfxname: dc.b   "graphics.library",0
        even
