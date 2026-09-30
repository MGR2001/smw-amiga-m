;----------------------------------------------------------------------
; scroll.s - Etapa 6: el nivel real en la Amiga, en el formato de D8 (d),
; con la camara en las dos direcciones (6.2).
;
;   PF1 (planos impares) = capa 1: buffer circular de 22 columnas de
;       bloques escrito dos veces (704 px), 3 planos entrelazados. Tiene
;       las columnas p - 2 .. p + 19 (p = palabra del puntero); cuando p
;       cambia se dibuja UNA columna nueva, fuera de la pantalla, por el
;       lado hacia el que va la camara.
;   PF2 (planos pares)   = capa 2: mapa de bits de 848 px (periodo de 512
;       + 336) a media velocidad: paralaje por hardware (BPLCON1 bits 4-7).
;   Colores: lista del copper por linea: 2 WAIT + 7 MOVE de la capa 1 + los
;       de la capa 2 en el borrado (los de la capa 1 los mantiene
;       apply_colors con la lista CHG, hacia adelante y hacia atras), y las
;       cargas a mitad de linea que caen en pantalla (build_mid, que las
;       copia del plan de tools/mkscroll.py).
;
; Datos: work/yi1_s.dat (tools/mkscroll.py). Ventana vertical fija: lineas
; 192..415 del nivel (la camara de Yoshi's Island 1 no se mueve en Y).
;
; Scroll: la columna de pantalla 0 muestra la x = s del nivel. Con el
; fetch adelantado una palabra: puntero = palabra (s - 1) >> 4 y retardo
; (-s) & 15.
;
;   vasmm68k_mot -Fbin -m68000 -I player -o work/scroll.bin player/scroll.s
;   python3 tools/mkadf.py --boot work/boot.bin --stage2 work/scroll.bin \
;       --data work/yi1_s.dat --out work/scroll.adf
;   -DSTOPX=n: para en s = n (por defecto recorre el nivel entero)
;   -DRETURN=r: va hasta r y vuelve hasta STOPX (6.2: ida y vuelta)
;   -DS0=n: empieza en s = n
;
; Para el juego (6b): scroll_init y scroll_frame, con a3 = datos, a4 =
; CUSTOM, a5 = vars y la s en V_S.
;
; Registros vivos en el bucle: a3 = datos  a4 = CUSTOM  a5 = variables
;----------------------------------------------------------------------

        include "exec.i"

        ifnd    VIS
VIS     equ     256             ; ancho de pantalla (D10: 256 como la SNES;
        endc                    ; -DVIS=320 arma la pantalla vieja)
        ifnd    STOPX
STOPX   equ     5120-VIS        ; el final del nivel
        endc
        ifnd    SPEED
SPEED   equ     2               ; px por frame
        endc
        ifnd    S0
S0      equ     0
        endc

LINES   equ     224
SLOTS   equ     22              ; columnas del buffer circular (x2)
ROWB1   equ     SLOTS*2*2       ; bytes de una fila de un plano de PF1 (88)
LINEB1  equ     ROWB1*3         ; 264
ROWB2   equ     106             ; 848 px
LINEB2  equ     ROWB2*3         ; 318
BUF1    equ     LINEB1*LINES    ; 59136

; lista del copper (dos: la que se ve y la que se escribe)
CL_BPLCON1  equ 20+2
CL_COLOR00  equ 36+2
CL_PTR      equ 44              ; BPL1PTH; BPLnPTH en CL_PTR + (n-1)*8
        ifd     SPRITES
; -DSPRITES (el juego, 6b.4): la cabecera lleva ademas los 8 punteros de
; sprites (SPR0PTH..SPR7PTL) y COLOR17-31, que escribe el juego en la
; lista de cada frame (Mario se ve junto con el fondo de su frame)
CL_SPR      equ 92              ; SPR0PTH; SPRnPTH en CL_SPR + n*8
CL_COL17    equ CL_SPR+64       ; COLOR17; COLORk en CL_COL17 + (k-17)*4
CL_LINES    equ CL_COL17+60
        else
CL_LINES    equ 92
        endc
; un segmento por linea: 2 WAIT + 7 + 7 MOVE (borrado), hasta MIDMAX
; cargas a mitad de linea y el salto al segmento siguiente (COP2LCH,
; COP2LCL, COPJMP2). Tamano fijo, contenido de largo variable: los huecos
; no le cuestan tiempo al copper.
MIDMAX      equ 12
SEG         equ 64+MIDMAX*12+12 ; 220 (tools/mkscroll.py: SEG). Una carga
                                ; ocupa hasta 12 bytes: 2 rellenos + MOVE
CL_SIZE     equ CL_LINES+SEG*LINES+4
; WAIT + MOVE: en que x de pantalla cambia el color (P42, medido en WinUAE
; con copcal.s -DPATTERN y COPCAL_FINE=1, h de a 2):
;   h <= $D0: x = 8 * ((h - $38) >> 2) - 1   (rejilla de 8 px: con 6 planos
;             el copper tiene una ranura cada 4 cc; h = $40 y $42 dan
;             x = 15, $44 y $46 dan 23). BPLCON1 no lo mueve.
;   h >= $D0: x = 303 + (h - $D0)            ($D4 -> 307, $DC -> 315)
; Para cambiar en x >= objetivo (nunca antes), lo mas pronto posible:
;   objetivo <= 303: q = (objetivo + 8) >> 3, h = $38 + 4q, x = 8q - 1
;   objetivo >  303: h = (objetivo - 94) & $FE, x = h + 95
; Pantalla de 256 px (DIW $2CA1, fetch $40-$C0; medido igual, copcal.s
; -DW256, COPCAL_W256=1..3): la misma rejilla con h - $48, hasta h = $C0
; (x = 239); despues $C4 -> 243, $C8 -> 247, $CC -> 251, $CE -> 255 (TAILH)
        ifeq    VIS-256
HOFS        equ $48
LASTX       equ 255             ; ninguna carga despues de esta x
XKNEE       equ 239             ; x de h = HKNEE; despues, TAILH
HKNEE       equ $c0
FETCHW      equ 17              ; palabras por linea y plano
DIWS        equ $2ca1
DIWE        equ $0ca1
DDFS        equ $0040
DDFE        equ $00c0
        else
HOFS        equ $38
LASTX       equ 316             ; ninguna carga despues de esta x
XKNEE       equ 303             ; x de h = HKNEE; despues, 1 px por unidad de h
HKNEE       equ $d0
FETCHW      equ 21
DIWS        equ $2c81
DIWE        equ $0cc1
DDFS        equ $0030
DDFE        equ $00d0
        endc

; h para x > XKNEE (en el registro \1)
TAILH   macro
        ifeq    VIS-256
        sub.w   #XKNEE+1,\1                 ; 0.. desde x = 240
        cmp.w   #12,\1
        blo.s   .t1\@
        move.w  #$ce,\1                     ; 252..: $CE (x = 255)
        bra.s   .t2\@
.t1\@:  and.w   #$fffc,\1
        add.w   #$c4,\1                     ; $C4 + 4k: x = 243 + 4k
.t2\@:
        else
        sub.w   #XKNEE-HKNEE-1,\1           ; x > 303: h = x - 94, par
        endc
        endm
        ifnd    BLITS
BLITS       equ 4               ; pasos de blit_steps por frame
        endc
BLANKH      equ $e2             ; el borrado empieza en esta h de la linea
                                ; ANTERIOR: 7 + k MOVE terminan antes de x = 0

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
D_MLX   equ 40
D_MLD   equ 44
D_LNS   equ 48

; variables (a5)
V_S     equ 0                   ; scroll de la capa 1 (px)
V_P     equ 2                   ; palabra del puntero, (s - 1) >> 4
V_CHG   equ 4                   ; .l siguiente cambio de color (x > s)
V_BUF1  equ 8                   ; .l buffer de PF1
V_COP   equ 12                  ; .l lista del copper A
V_COP2  equ 16                  ; .l lista del copper B
V_BACK  equ 20                  ; .l la que se escribe este frame
; BENCH: medidas con el timer A de CIA-B (ticks de 1,41 us)
V_T0    equ 24                  ; cuenta al empezar el trabajo del frame
V_COLF  equ 26                  ; este frame dibujo una columna
V_TPF   equ 28                  ; ticks por frame (calibracion)
V_MAXC  equ 30                  ; max / suma / n, frames con columna
V_SUMC  equ 32
V_NC    equ 36
V_MAXN  equ 38                  ; ... y sin columna
V_SUMN  equ 40
V_NN    equ 44
V_DIR   equ 46                  ; -DRETURN: 0 = a la derecha, 1 = volviendo
V_DONE  equ 48                  ; el recorrido termino
V_DATA  equ 62                  ; .l datos (build_copper usa a3)
V_LSA   equ 66                  ; s con la que se escribio cada lista
V_LSB   equ 68                  ; ($8000: nunca)
V_CCOL  equ 76                  ; columna que se esta dibujando (-1: ninguna)
V_CBLK  equ 78                  ; su siguiente paso (0..13 bloques, 14 copia)
V_BSKIP equ 80                  ; BENCH: frames que todavia no se cuentan
V_MSC   equ V_MAXC+52           ; BENCH: s del peor frame con columna (82)
V_MSN   equ V_MAXN+52           ; ... y sin columna (90)
V_SIZE  equ 92

CIAB_TALO   equ $bfd400
CIAB_TAHI   equ $bfd500
CIAB_ICR    equ $bfdd00
CIAB_CRA    equ $bfde00

        ifnd    SCROLL_LIB
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
        move.l  #CL_SIZE,d0
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     fail
        move.l  d0,V_COP2(a5)

        move.w  #S0,V_S(a5)
        bsr     scroll_init

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
        ifd     SPRTEST
        bsr     spr_init
        move.w  #$83e0,DMACON(a4)           ; + SPREN
        else
        move.w  #$83c0,DMACON(a4)           ; MASTER|BPLEN|COPEN|BLTEN
        endc
        ifd     BENCH
        bsr     bench_init
        endc

;----------------------------------------------------------------------
; Bucle por frame: todo despues de la ultima linea visible ($10C).
;----------------------------------------------------------------------
frame:
.w1:    move.l  VPOSR(a4),d0
        lsr.l   #8,d0
        and.w   #$1ff,d0
        cmp.w   #$110,d0
        blo.s   .w1
        ifd     BENCH
        bsr     readtimer
        move.w  d0,V_T0(a5)
        clr.w   V_COLF(a5)
        endc
        ifd     SPRTEST
        bsr     spr_ptrs
        endc
        bsr     camera
        ifd     BENCH
        tst.w   V_DONE(a5)
        bne     show_results
        endc
        bsr     scroll_frame
.w2:
        ifd     BENCH
        bsr     bench_frame
        endc
.w2l:    move.l  VPOSR(a4),d0                ; esperar a que empiece otro frame
        lsr.l   #8,d0
        and.w   #$1ff,d0
        cmp.w   #$110,d0
        bhs.s   .w2l
        bra     frame

;----------------------------------------------------------------------
; --- camera ---
; la s del frame (programa de prueba): de S0 a STOPX a SPEED px por
; frame; con -DRETURN=r, de S0 a r y despues de vuelta hasta STOPX.
; V_DONE = 1 cuando llega (y la s ya no cambia).
;----------------------------------------------------------------------
camera:
        move.w  V_S(a5),d0
        ifd     RETURN
        tst.w   V_DIR(a5)
        bne.s   .back
        cmp.w   #RETURN,d0
        bhs.s   .turn
        addq.w  #SPEED,d0
        cmp.w   #RETURN,d0
        bls.s   .ok
        move.w  #RETURN,d0
        bra.s   .ok
.turn:  move.w  #1,V_DIR(a5)
.back:  cmp.w   #STOPX,d0
        bls.s   .stop
        subq.w  #SPEED,d0
        cmp.w   #STOPX,d0
        bge.s   .ok
        move.w  #STOPX,d0
        else
        cmp.w   #STOPX,d0
        bhs.s   .stop
        addq.w  #SPEED,d0
        cmp.w   #STOPX,d0
        bls.s   .ok
        move.w  #STOPX,d0
        endc
.ok:    move.w  d0,V_S(a5)
        rts
.stop:  move.w  #1,V_DONE(a5)
        rts
        endc                                ; SCROLL_LIB

;----------------------------------------------------------------------
; --- scroll_init ---
; entrada:  a3 = datos, a5 = vars, V_S, V_BUF1, V_COP, V_COP2 (listas de
;           CL_SIZE y buffer de BUF1 bytes, en chip)
; salida:   las dos listas del copper listas para V_S, las columnas de la
;           ventana dibujadas (con la CPU), V_BACK = la lista B
; registros destruidos: d0-d7/a0-a2
;----------------------------------------------------------------------
scroll_init:
        move.l  V_COP(a5),a0
        bsr     build_copper
        move.l  V_COP2(a5),a0
        bsr     build_copper
        bsr     init_lines
        move.w  #-1,V_CCOL(a5)
        move.l  a3,a0
        add.l   D_CHG(a3),a0
        addq.l  #8,a0                       ; despues del centinela (x = 0)
        move.l  a0,V_CHG(a5)
        bsr     apply_colors
        move.w  V_S(a5),d0
        subq.w  #1,d0
        asr.w   #4,d0
        move.w  d0,V_P(a5)
        bsr     draw_window
        move.l  V_COP(a5),V_BACK(a5)
        bsr     set_pointers
        bsr     build_mid
        move.l  V_COP2(a5),V_BACK(a5)
        bsr     set_pointers
        bsr     build_mid
        rts

;----------------------------------------------------------------------
; --- scroll_frame ---
; entrada:  V_S = la s de este frame (cualquier direccion)
; salida:   la columna nueva empezada, los colores del borrado al dia, la
;           lista V_BACK escrita y puesta en COP1LC (se ve desde el frame
;           siguiente), V_BACK = la otra
; registros destruidos: d0-d7/a0-a2
;----------------------------------------------------------------------
scroll_frame:
        ; columna nueva (cuando cambia la palabra del puntero), lo primero:
        ; en el borrado vertical el blitter tiene todo el bus, y la ultima
        ; copia (672 filas) corre mientras la CPU hace build_mid
        bsr     columns
        bsr     apply_colors
        bsr     set_pointers
        ifnd    NOMID
        bsr     build_mid
        endc
        move.l  V_BACK(a5),COP1LC(a4)       ; se usa desde el proximo frame
        move.l  V_COP(a5),d0                ; la otra, para el frame siguiente
        cmp.l   V_BACK(a5),d0
        bne.s   .sw
        move.l  V_COP2(a5),d0
.sw:    move.l  d0,V_BACK(a5)
        rts

;----------------------------------------------------------------------
; --- columns ---
; El buffer tiene las columnas p - 2 .. p + 19. Si p sube, entra p + 19
; (en el hueco de p - 3); si baja, entra p - 2 (en el hueco de p + 20). Se
; dibuja en varios frames (blit_steps): la columna nueva no se ve hasta
; que la camara recorre 32 px (a la izquierda) o 48 (a la derecha). Si la
; camara salta mas de una columna, se redibuja la ventana entera.
; registros destruidos: d0-d3/d7/a0-a2
;----------------------------------------------------------------------
columns:
        move.w  V_S(a5),d0
        subq.w  #1,d0
        asr.w   #4,d0                       ; p
        move.w  V_P(a5),d1
        cmp.w   d1,d0
        beq.s   .steps
        move.w  d0,V_P(a5)
        sub.w   d0,d1                       ; p viejo - p nuevo
        cmp.w   #-1,d1
        beq.s   .fw
        cmp.w   #1,d1
        beq.s   .bw
        bsr     draw_window                 ; un salto
        bra.s   .steps
.fw:    add.w   #19,d0
        bra.s   .new
.bw:    subq.w  #2,d0
.new:   tst.w   d0
        bmi.s   .steps
        cmp.w   D_COLS(a3),d0
        bhs.s   .steps
        move.w  V_CCOL(a5),d1               ; una columna a medias:
        bmi.s   .nc
        sub.w   d0,d1
        cmp.w   #SLOTS,d1                   ; en el mismo hueco (la camara dio
        beq.s   .nc                         ; la vuelta): ya no hace falta
        cmp.w   #-SLOTS,d1
        beq.s   .nc
        move.w  d0,-(sp)                    ; si no, terminarla
        moveq   #99,d7
        bsr     blit_steps
        move.w  (sp)+,d0
.nc:    move.w  d0,V_CCOL(a5)
        clr.w   V_CBLK(a5)
.steps: moveq   #BLITS-1,d7
        bra     blit_steps

; --- draw_window --- las columnas p - 2 .. p + 19 (V_P) con la CPU
draw_window:
        bsr     bwait
        move.w  #-1,V_CCOL(a5)
        move.w  V_P(a5),d7
        subq.w  #2,d7
        moveq   #SLOTS-1,d6
.c:     tst.w   d7
        bmi.s   .n
        cmp.w   D_COLS(a3),d7
        bhs.s   .n
        move.w  d7,d0
        bsr     draw_column
.n:     addq.w  #1,d7
        dbf     d6,.c
        rts

;----------------------------------------------------------------------
; --- set_pointers ---
; entrada:  V_S
; salida:   BPLCON1 y los 6 punteros de plano en la lista del copper
; registros destruidos: d0-d3/a0-a1
;----------------------------------------------------------------------
set_pointers:
        move.l  V_BACK(a5),a1
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
; los colores de la capa 1 en el borrado: aplica los cambios con x <= s
; (color nuevo) y deshace los que tienen x > s (color viejo), en las dos
; listas. CHG empieza con un centinela x = 0 y termina en x = $FFFF.
; registros destruidos: d0-d1/a0-a1
;----------------------------------------------------------------------
apply_colors:
        move.l  a2,-(sp)
        move.l  V_CHG(a5),a0
        move.l  V_COP(a5),a1
        lea     CL_LINES(a1),a1
        move.l  V_COP2(a5),a2
        lea     CL_LINES(a2),a2
        move.w  V_S(a5),d0
.f:     cmp.w   (a0),d0
        blo.s   .b                          ; x > s
        moveq   #0,d1                       ; desplazamiento SIN signo: pasa
        move.w  2(a0),d1                    ; de 32 767 desde la linea 149
        move.w  4(a0),(a1,d1.l)
        move.w  4(a0),(a2,d1.l)
        addq.l  #8,a0
        bra.s   .f
.b:     cmp.w   -8(a0),d0                   ; el anterior tiene x > s: la
        bhs.s   .done                       ; camara volvio, deshacerlo
        subq.l  #8,a0
        moveq   #0,d1
        move.w  2(a0),d1
        move.w  6(a0),(a1,d1.l)
        move.w  6(a0),(a2,d1.l)
        bra.s   .b
.done:  move.l  a0,V_CHG(a5)
        move.l  (sp)+,a2
        rts

;----------------------------------------------------------------------
; --- init_lines ---
; Una tabla por lista (linetab_a, linetab_b), 32 bytes por linea:
;   +0  .l donde empiezan las cargas en el segmento (absoluta)
;   +4  .l lo, +8 .l hi: cargas escritas, [lo, hi) en MLD (absolutas)
;   +12 vl, +14 vu: lo escrito vale mientras vl <= s < vu
;   +16 la palabra alta del WAIT (v << 8)
;   +18 el salto al segmento siguiente (COP2LCH, COP2LCL, COPJMP2)
; htab[x] = byte bajo del WAIT (h | 1) para que el MOVE caiga en x >= x.
; entrada:  a3 = datos, V_COP, V_COP2 (build_copper ya dejo ldoff)
;----------------------------------------------------------------------
init_lines:
        lea     linetab_a(pc),a0
        move.l  V_COP(a5),d4
        bsr.s   .tab
        lea     linetab_b(pc),a0
        move.l  V_COP2(a5),d4
        bsr.s   .tab
        move.w  #$8000,V_LSA(a5)
        move.w  #$8000,V_LSB(a5)
        lea     htab(pc),a0                 ; h para cambiar en x >= objetivo
        moveq   #0,d1                       ; (P42, cabecera)
.h:     move.w  d1,d2
        cmp.w   #XKNEE,d2
        bhi.s   .hk
        addq.w  #8,d2
        lsr.w   #3,d2                       ; q = (x + 8) >> 3
        lsl.w   #2,d2
        add.w   #HOFS,d2                    ; h = HOFS + 4q
        bra.s   .hk2
.hk:    TAILH   d2
.hk2:   and.w   #$fe,d2
        cmp.w   #BLANKH,d2
        bls.s   .hk3
        move.w  #BLANKH,d2
.hk3:   or.w    #1,d2
        move.b  d2,(a0)+
        addq.w  #1,d1
        cmp.w   #LASTX,d1
        bls.s   .h
        rts
; una tabla: a0 = tabla, d4 = lista
.tab:   add.l   #CL_LINES,d4                ; d4 = segmento
        move.l  a3,a1
        add.l   D_MLX(a3),a1
        move.l  a3,d2
        add.l   D_MLD(a3),d2                ; d2 = MLD
        lea     ldoff(pc),a2
        move.w  #$2c<<8,d3
        move.w  #LINES-1,d1
.l:     moveq   #0,d0
        move.w  (a2)+,d0
        add.l   d4,d0
        move.l  d0,(a0)                     ; donde van las cargas
        moveq   #0,d0
        move.w  (a1)+,d0
        mulu    #12,d0
        add.l   d2,d0
        move.l  d0,4(a0)                    ; lo = hi = la primera carga
        move.l  d0,8(a0)
        move.w  #1,12(a0)                   ; vl = 1, vu = 0: nunca vale
        clr.w   14(a0)
        move.w  d3,16(a0)
        add.l   #SEG,d4
        move.w  #$0084,18(a0)               ; salto al segmento siguiente
        move.l  d4,d0
        swap    d0
        move.w  d0,20(a0)
        move.w  #$0086,22(a0)
        move.w  d4,24(a0)
        move.l  #$008a0000,26(a0)
        add.w   #$100,d3
        lea     32(a0),a0
        dbf     d1,.l
        rts

;----------------------------------------------------------------------
; --- build_mid ---
; entrada:  V_BACK = lista que se escribe, V_S = scroll
; salida:   en el segmento de cada linea que puede tener cargas en
;           pantalla (LNS) y cuyo contenido ya no vale, las cargas del plan
;           con x en [s, s + LASTX] (hasta MIDMAX) y el salto al segmento
;           siguiente
; registros destruidos: d0-d1/a0-a1 (guarda el resto)
;
; El plan (tools/mkscroll.py) esta en coordenadas del nivel: para cada
; carga, la x en que cae y si va con WAIT, detras de la anterior o con 1-2
; MOVE de relleno. Aca se copia: la h del WAIT sale de htab[x - s] y la
; primera carga de la linea va siempre con WAIT (la anterior del plan
; quedo fuera por la izquierda).
;
; Lo escrito queda FIJO en pantalla: el MOVE de una carga cae entre x - s0
; y x - s0 + 7 (rejilla de 8 px, P42; los de detras, a 16 px del
; anterior). Sigue bien mientras caiga despues del fin del tramo anterior
; y antes del principio del nuevo: s0 + a <= s < s0 + b (a, b en MLD). La
; linea se reescribe cuando alguna deja de valer, cuando entra una carga
; por la derecha (s >= x[hi] - LASTX), cuando la camara vuelve y una
; vuelve a entrar por la izquierda (s <= x[lo - 1]) o la ultima sale por
; la derecha (s < x[hi - 1] - LASTX). Las que salen por la izquierda NO:
; escriben el color que el borrado ya puso. No depende de la direccion.
;----------------------------------------------------------------------
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
        sub.w   d0,d1                       ; |s vieja - s| > 16 (o nunca
        bpl.s   .ab                         ; escrita): todas las lineas
        neg.w   d1
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
.all:   lea     linetab_b(pc),a4
        cmp.l   V_COP(a5),a0
        bne.s   .ta
        lea     linetab_a(pc),a4
.ta:    move.l  a4,a5                       ; OJO: a5 prestado (vars)
        lea     htab(pc),a2
        sub.w   d6,a2                       ; a2 = htab - s
        move.w  d6,d5
        add.w   #LASTX,d5                   ; d5 = s + LASTX
        move.w  #$fffe,d2
.line:  move.w  (a6)+,d0                    ; linea * 32
        bmi     .done
        lea     (a5,d0.w),a4                ; a4 = linetab[L]
        cmp.w   12(a4),d6
        blt.s   .rw                         ; s < vl
        cmp.w   14(a4),d6
        blt.s   .line                       ; s < vu: lo escrito vale
.rw:    move.l  4(a4),a1                    ; a1 = lo (registros de 12 bytes:
.lof:   cmp.w   2(a1),d6                    ; clase, x, MOVE, a, b)
        ble.s   .lob                        ; x < s: salio por la izquierda
        lea     12(a1),a1
        bra.s   .lof
.lob:   cmp.w   -10(a1),d6                  ; la anterior tiene x >= s: la
        bgt.s   .lod                        ; camara volvio (centinelas: -1
        lea     -12(a1),a1                  ; antes, $7FFF despues)
        bra.s   .lob
.lod:   move.l  a1,4(a4)
        move.l  8(a4),a0                    ; a0 = hi
.hif:   cmp.w   2(a0),d5                    ; x <= s + LASTX: entro por la
        blt.s   .hib                        ; derecha
        lea     12(a0),a0
        bra.s   .hif
.hib:   cmp.w   -10(a0),d5                  ; la anterior tiene x > s + LASTX
        bge.s   .hid
        lea     -12(a0),a0
        bra.s   .hib
.hid:   move.w  -10(a1),d3
        addq.w  #1,d3                       ; d3 = vl: la anterior vuelve
        move.w  2(a0),d4
        sub.w   #LASTX,d4                   ; d4 = vu: la siguiente entra
        move.l  (a4),a3                     ; a3 = donde van las cargas
        move.l  a0,d1
        sub.l   a1,d1                       ; 12 * cargas
        bne.s   .some
        move.l  a0,8(a4)
        bra.s   .jump
.some:  cmp.w   #MIDMAX*12,d1
        bls.s   .n
        lea     MIDMAX*12(a1),a0            ; no entran todas: se rehace
        move.w  2(a1),d4                    ; cuando la primera sale
        addq.w  #1,d4
.n:     move.l  a0,8(a4)
        move.w  -10(a0),d0                  ; la ultima sale por la derecha
        sub.w   #LASTX,d0                   ; si s < x - LASTX
        cmp.w   d0,d3
        bge.s   .n2
        move.w  d0,d3
.n2:    sub.w   d6,d3                       ; vl y vu relativas a s: se
        sub.w   d6,d4                       ; comparan con a y b
        move.w  16(a4),d7                   ; WAIT: v << 8
        addq.l  #2,a1                       ; la primera, siempre con WAIT
        bra.s   .w
.ld:    move.w  (a1)+,d1                    ; clase
        bne.s   .ch
.w:     move.w  (a1)+,d0                    ; x
        move.b  (a2,d0.w),d7                ; h | 1 para x - s
        move.w  d7,(a3)+
        move.w  d2,(a3)+                    ; $FFFE
.mv:    move.l  (a1)+,(a3)+                 ; MOVE registro, color
        cmp.w   (a1)+,d3                    ; vl = max(vl, a)
        bge.s   .k1
        move.w  -2(a1),d3
.k1:    cmp.w   (a1)+,d4                    ; vu = min(vu, b)
        ble.s   .k2
        move.w  -2(a1),d4
.k2:    cmp.l   a0,a1
        bne.s   .ld
        add.w   d6,d3
        add.w   d6,d4
        bra.s   .jump
.ch:    addq.l  #2,a1                       ; (x: no hace falta)
        subq.w  #2,d1                       ; 1: MOVE detras del anterior
        bmi.s   .mv
        beq.s   .f1                         ; 2: un relleno; 3: dos
        move.l  #$01fe0000,(a3)+
.f1:    move.l  #$01fe0000,(a3)+
        bra.s   .mv
.jump:  move.l  18(a4),(a3)+                ; el salto al segmento siguiente
        move.l  22(a4),(a3)+
        move.l  26(a4),(a3)+
        cmp.w   d6,d3                       ; si no vale ni en s (una carga
        bgt.s   .late                       ; que ya llega tarde o temprano),
        cmp.w   d6,d4                       ; vl = s y vu = s + 1: se
        bgt.s   .j2                         ; reescribe en cada frame, vaya
.late:  move.w  d6,d3                       ; hacia donde vaya la camara (si
        move.w  d6,d4                       ; solo se corrigiera vu, al
        addq.w  #1,d4                       ; volver valdria lo escrito antes
.j2:    move.w  d3,12(a4)                   ; y la ida y la vuelta darian
        move.w  d4,14(a4)                   ; imagenes distintas: P50)
        bra     .line
.done:  movem.l (sp)+,d2-d7/a2-a6
        rts

;----------------------------------------------------------------------
; --- draw_column ---
; entrada:  d0.w = columna de bloques del nivel
; salida:   la columna, en sus dos copias del buffer circular de PF1
; registros destruidos: d0-d3/a0-a2
; ciclos:   ~24 000 (CPU; 224 lineas x 3 planos x 2 copias)
; Para el arranque y los saltos de camara; en el scroll va por blitter.
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
; --- blit_steps ---
; La columna nueva, repartida entre frames: hasta d7+1 pasos por llamada.
; Paso 0..13 = un bloque (1 palabra x 48 filas: 16 lineas x 3 planos, que
; en el buffer entrelazado estan a ROWB1 bytes); paso 14 = la segunda
; copia de toda la columna (1 x 672 filas, sin esperar a que termine).
; entrada:  V_CCOL (-1: nada), V_CBLK, d7 = pasos - 1
; registros destruidos: d0-d3/d7/a0-a2
;----------------------------------------------------------------------
BLTCON0R    equ $040
BLTCON1R    equ $042
BLTAFWMR    equ $044
BLTALWMR    equ $046
BLTAPTR     equ $050
BLTDPTR     equ $054
BLTSIZER    equ $058
BLTAMODR    equ $064
BLTDMODR    equ $066

blit_steps:
        tst.w   V_CCOL(a5)
        bmi.s   .done
        ifd     BENCH
        st      V_COLF(a5)
        endc
        move.w  V_CCOL(a5),d0
        moveq   #0,d1
        move.w  d0,d1
        divu    #SLOTS,d1
        swap    d1
        add.w   d1,d1
        move.l  V_BUF1(a5),a2
        add.w   d1,a2                       ; a2 = columna en el buffer
        mulu    #15,d0
        move.l  a3,a1
        add.l   D_MAP(a3),a1
        add.l   d0,a1                       ; a1 = MAP[c * 15]
.step:  move.w  V_CBLK(a5),d1
        cmp.w   #LINES/16,d1
        beq.s   .copy
        moveq   #0,d0
        move.b  (a1,d1.w),d0
        mulu    #96,d0
        add.l   a3,d0
        add.l   D_BLK(a3),d0                ; d0 = bloque
        mulu    #16*LINEB1,d1
        lea     (a2,d1.l),a0                ; destino
        bsr     bwait
        move.l  #$09f00000,BLTCON0R(a4)     ; A -> D, BLTCON1 = 0
        move.l  #$ffffffff,BLTAFWMR(a4)
        move.w  #0,BLTAMODR(a4)
        move.w  #ROWB1-2,BLTDMODR(a4)
        move.l  d0,BLTAPTR(a4)
        move.l  a0,BLTDPTR(a4)
        move.w  #(48<<6)|1,BLTSIZER(a4)
        addq.w  #1,V_CBLK(a5)
        dbf     d7,.step
.done:  rts
.copy:  bsr.s   bwait                       ; segunda copia, 44 bytes despues
        move.w  #ROWB1-2,BLTAMODR(a4)
        move.w  #ROWB1-2,BLTDMODR(a4)
        move.l  a2,BLTAPTR(a4)
        lea     SLOTS*2(a2),a2
        move.l  a2,BLTDPTR(a4)
        move.w  #((LINES*3)<<6)|1,BLTSIZER(a4)
        move.w  #-1,V_CCOL(a5)
        rts

bwait:  btst    #6,DMACONR(a4)              ; dos veces: bug del Agnus viejo
.w:     btst    #6,DMACONR(a4)
        bne.s   .w
        rts

;----------------------------------------------------------------------
; --- build_copper ---
; la lista fija; los colores iniciales de las dos capas por linea (la capa
; 1 con cam_x = 0: apply_colors la lleva a V_S)
; registros destruidos: d0-d5/a0-a2
;----------------------------------------------------------------------
build_copper:                               ; a0 = lista
        movem.l a2/a6,-(sp)
        move.l  a0,d4                       ; d4 = principio de la lista
        move.l  #$008e0000|DIWS,(a0)+       ; DIWSTRT
        move.l  #$00900000|DIWE,(a0)+       ; DIWSTOP: 224 lineas
        move.l  #$00920000|DDFS,(a0)+       ; DDFSTRT: una palabra antes
        move.l  #$00940000|DDFE,(a0)+       ; DDFSTOP
        move.l  #$01006600,(a0)+            ; BPLCON0: 6 planos, DBLPF, COLOR
        move.l  #$01020000,(a0)+            ; BPLCON1 (set_pointers)
        ifd     SPRTEST
        move.l  #$01040024,(a0)+            ; BPLCON2: sprites delante
        else
        ifd     SPRITES
        move.l  #$01040024,(a0)+            ; BPLCON2: sprites delante
        else
        ifd     BPLCON2V
        move.l  #$01040000|BPLCON2V,(a0)+
        else
        move.l  #$01040000,(a0)+            ; BPLCON2: PF1 delante
        endc
        endc
        endc
        move.w  #$0108,(a0)+
        move.w  #LINEB1-FETCHW*2,(a0)+      ; BPL1MOD
        move.w  #$010a,(a0)+
        move.w  #LINEB2-FETCHW*2,(a0)+      ; BPL2MOD
        move.w  #COLOR00,(a0)+
        move.w  D_SKY(a3),(a0)+
        move.l  #$01900000,(a0)+            ; COLOR08 (transparente en PF2)
        move.w  #$00e0,d0                   ; BPL1PTH..BPL6PTL
        moveq   #12-1,d1
.ptr:   move.w  d0,(a0)+
        clr.w   (a0)+
        addq.w  #2,d0
        dbf     d1,.ptr
        ifd     SPRITES
        move.w  #$0120,d0                   ; SPR0PTH..SPR7PTL
        moveq   #16-1,d1
.spt:   move.w  d0,(a0)+
        clr.w   (a0)+
        addq.w  #2,d0
        dbf     d1,.spt
        move.w  #$01a2,d0                   ; COLOR17..COLOR31
        moveq   #15-1,d1
.c17:   move.w  d0,(a0)+
        clr.w   (a0)+
        addq.w  #2,d0
        dbf     d1,.c17
        endc
        ; lineas
        move.l  a3,a1
        add.l   D_INI(a3),a1
        move.l  a3,a2
        add.l   D_L2P(a3),a2
        lea     ldoff(pc),a6                ; inicio de las cargas
        moveq   #0,d2                       ; d2 = linea
.line:  move.l  a0,d5                       ; d5 = principio del segmento
        move.w  d2,d0
        add.w   #$2c-1,d0                   ; el borrado, en el borde derecho
        cmp.w   #$ff,d0                     ; de la linea anterior (medido: con
        beq.s   .w255                       ; 7-9 MOVE termina antes de x = 0)
        move.w  d0,d3
        lsl.w   #8,d3
        or.w    #BLANKH|1,d3
        move.w  d3,(a0)+
        move.w  #$fffe,(a0)+
        move.w  d3,(a0)+
        move.w  #$fffe,(a0)+
        bra.s   .wd
.w255:  move.l  #$ffdffffe,(a0)+            ; en la 255: WAIT ($FF,$DE) y uno
        move.l  #$01fe0000,(a0)+            ; solo (+ un MOVE nulo). El copper
                                            ; ve ($FF,$E2) con V ya en $00
                                            ; (256): no llegaba nunca y las
                                            ; lineas 212-223 se quedaban sin
                                            ; segmento; un 2.o WAIT ($FF,$DE)
                                            ; tambien cae despues (P59)
.wd:    move.w  #$0182,d0                   ; COLOR01..07: capa 1
        moveq   #7-1,d1
.c1:    move.w  d0,(a0)+
        move.w  (a1)+,(a0)+
        addq.w  #2,d0
        dbf     d1,.c1
        move.w  #$0192,d0                   ; COLOR09..15: capa 2, solo los que
        moveq   #7-1,d1                     ; cambian respecto de la linea
.c2:    tst.w   d2                          ; anterior (casi nunca)
        beq.s   .c2w
        move.w  -14(a2),d4
        cmp.w   (a2),d4
        beq.s   .c2n
.c2w:   move.w  d0,(a0)+
        move.w  (a2),(a0)+
.c2n:   addq.l  #2,a2
        addq.w  #2,d0
        dbf     d1,.c2
        move.l  a0,d0                       ; inicio de las cargas de la linea
        sub.l   d5,d0
        move.w  d0,(a6)+
        move.l  d5,d0                       ; salto al segmento siguiente
        add.l   #SEG,d0
        move.w  #$0084,(a0)+
        swap    d0
        move.w  d0,(a0)+
        move.w  #$0086,(a0)+
        swap    d0
        move.w  d0,(a0)+
        move.l  #$008a0000,(a0)+
        move.l  d5,a0
        lea     SEG(a0),a0
        addq.w  #1,d2
        cmp.w   #LINES,d2
        blo     .line
        move.l  #$fffffffe,(a0)+
        movem.l (sp)+,a2/a6
        rts

        ifd     BENCH
;----------------------------------------------------------------------
; Medida (-DBENCH). Mismo formato de salida que bench2.s: palabras como
; bits en un plano, filas cada 12 lineas desde la 8, palabra 2 en
; adelante. tools/scroll_read.py las lee.
;   w0 $A55A  w1 ticks/frame  w2-w4 con columna: max, media, n
;   w5-w7 sin columna: max, media, n   w8-w17 $8001   w18 $5AA5
;----------------------------------------------------------------------
readtimer:
.r:     moveq   #0,d0
        move.b  CIAB_TAHI,d0
        move.b  CIAB_TALO,d1
        move.b  CIAB_TAHI,d2
        cmp.b   d0,d2
        bne.s   .r
        lsl.w   #8,d0
        move.b  d1,d0
        rts

waitline:                                   ; d0 = linea (< 256)
        move.w  d0,d3
.w:     move.l  VPOSR(a4),d1
        lsr.l   #8,d1
        and.w   #$1ff,d1
        cmp.w   d3,d1
        bne.s   .w
        rts

bench_init:
        move.b  #$7f,CIAB_ICR
        move.b  #0,CIAB_CRA
        move.b  #$ff,CIAB_TALO
        move.b  #$ff,CIAB_TAHI
        move.b  #$11,CIAB_CRA               ; START | LOAD, continuo
        move.w  #$40,d0
        bsr     waitline
        move.w  #$41,d0
        bsr     waitline
        move.w  #$40,d0
        bsr     waitline
        bsr     readtimer
        move.w  d0,d4
        move.w  #$41,d0
        bsr     waitline
        move.w  #$40,d0
        bsr     waitline
        bsr     readtimer
        sub.w   d0,d4
        move.w  d4,V_TPF(a5)
        rts

; el trabajo del frame termina cuando termina el blitter. Los primeros
; BSKIP frames (arranque) no se cuentan, y cada maximo guarda la s donde
; ocurrio.
BSKIP   equ 8
bench_frame:
        bsr     bwait
        cmp.w   #BSKIP,V_BSKIP(a5)
        bhs.s   .go
        addq.w  #1,V_BSKIP(a5)
        rts
.go:    bsr     readtimer
        move.w  V_T0(a5),d1
        sub.w   d0,d1                       ; cuenta hacia abajo
        lea     V_MAXC(a5),a0
        tst.b   V_COLF(a5)
        bne.s   .c
        lea     V_MAXN(a5),a0
.c:     cmp.w   (a0),d1
        bls.s   .m
        move.w  d1,(a0)
        move.w  V_S(a5),52(a0)              ; V_MSC / V_MSN: donde fue
.m:     moveq   #0,d0
        move.w  d1,d0
        add.l   d0,2(a0)
        addq.w  #1,6(a0)
        rts

show_results:
        bsr     bwait
        move.l  V_BUF1(a5),a0               ; pantalla de 1 plano, 40 bytes/linea
        move.w  #BUF1/4-1,d0
.clr:   clr.l   (a0)+
        dbf     d0,.clr
        lea     res(pc),a2
        move.w  #$a55a,(a2)
        move.w  V_TPF(a5),2(a2)
        lea     V_MAXC(a5),a0
        lea     4(a2),a1
        bsr     .stat
        lea     V_MAXN(a5),a0
        lea     10(a2),a1
        bsr     .stat
        lea     16(a2),a0                   ; w8..w17: relleno para que
        moveq   #10-1,d0                    ; scroll_read (autodetect) vea
.fil:   move.w  #$8001,(a0)+                ; las 19 filas
        dbf     d0,.fil
        move.w  V_MSC(a5),d0                ; w8, w9: s de los dos maximos,
        add.w   d0,d0                       ; en los bits 1-14 (el 15 y el 0
        or.w    #$8001,d0                   ; siguen a 1 para autodetect)
        move.w  d0,16(a2)
        move.w  V_MSN(a5),d0
        add.w   d0,d0
        or.w    #$8001,d0
        move.w  d0,18(a2)
        move.w  #$5aa5,36(a2)
        move.l  V_BUF1(a5),a3
        add.l   #8*40+4,a3
        moveq   #19-1,d7
.row:   move.w  (a2)+,d0
        move.l  a3,a0
        moveq   #16-1,d6
.bit:   add.w   d0,d0
        bcc.s   .zero
        move.l  a0,a1
        moveq   #8-1,d5
.fill:  move.w  #$ffff,(a1)
        lea     40(a1),a1
        dbf     d5,.fill
.zero:  addq.w  #2,a0
        dbf     d6,.bit
        lea     12*40(a3),a3
        dbf     d7,.row
        move.l  V_COP(a5),a0                ; lista del resultado
        move.l  #$008e2c81,(a0)+
        move.l  #$00902cc1,(a0)+
        move.l  #$00920038,(a0)+
        move.l  #$009400d0,(a0)+
        move.l  #$01001200,(a0)+
        move.l  #$01020000,(a0)+
        move.l  #$01040000,(a0)+
        move.l  #$01080000,(a0)+
        move.l  V_BUF1(a5),d0
        move.w  #$00e0,(a0)+
        swap    d0
        move.w  d0,(a0)+
        move.w  #$00e2,(a0)+
        swap    d0
        move.w  d0,(a0)+
        move.l  #$01800000,(a0)+
        move.l  #$01820fff,(a0)+
        move.l  #$fffffffe,(a0)+
        move.l  V_COP(a5),COP1LC(a4)
        move.w  #0,COPJMP1(a4)
.forever:
        bra.s   .forever
.stat:  move.w  (a0),(a1)+                  ; max
        move.l  2(a0),d0
        move.w  6(a0),d1
        beq.s   .z
        divu    d1,d0
.z:     move.w  d0,(a1)+                    ; media
        move.w  6(a0),(a1)+                 ; n
        rts

res:    ds.w    19
        endc

        ifnd    SCROLL_LIB
fail:   lea     CUSTOM,a4
.l:     move.w  #$0f00,COLOR00(a4)
        bra.s   .l

        even
vars:   ds.b    V_SIZE
        endc
        even
linetab_a: ds.b 32*LINES                    ; ver init_lines
linetab_b: ds.b 32*LINES
ldoff:  ds.w    LINES                       ; build_copper: inicio de las cargas
htab:   ds.b    LASTX+1                     ; byte bajo del WAIT por x
        even
alllines:                                   ; build_mid despues de un salto
N       set     0
        rept    LINES
        dc.w    N*32
N       set     N+1
        endr
        dc.w    -1
        even
        ifd     SPRTEST
;----------------------------------------------------------------------
; -DSPRTEST (Etapa 6.1): los 8 sprites, cada uno un bloque de 16 x 16 con
; su numero de columnas (sprite n: n + 1 rayas), en x = 8 + 30 n de la
; pantalla, lineas $50-$5F. Dice que sprites tienen DMA con este fetch.
;----------------------------------------------------------------------
SPRY    equ     $50
spr_init:
        lea     sprdata(pc),a0
        moveq   #0,d2                       ; n
.s:     move.w  d2,d0
        mulu    #30,d0
        add.w   #8+DIWS&$ff-1,d0            ; HSTART = DIW + x - 1
        move.w  d0,d1
        lsr.w   #1,d1
        or.w    #SPRY<<8,d1
        move.w  d1,(a0)+                    ; SPRxPOS
        and.w   #1,d0
        or.w    #(SPRY+16)<<8,d0
        move.w  d0,(a0)+                    ; SPRxCTL
        moveq   #16-1,d3
.l:     move.w  #$aaaa,d0                   ; rayas: n + 1 a la izquierda
        move.w  d2,d1
        addq.w  #1,d1
        moveq   #-1,d4
        lsl.w   d1,d4
        not.w   d4                          ; n + 1 bits bajos... al reves
        ror.w   d1,d4                       ; ...arriba
        cmp.w   #3,d3
        bhi.s   .d
        moveq   #-1,d4                      ; 4 lineas macizas abajo
.d:     move.w  d4,(a0)+
        clr.w   (a0)+
        dbf     d3,.l
        clr.l   (a0)+
        addq.w  #1,d2
        cmp.w   #8,d2
        blo.s   .s
        move.w  #$0ff0,$1a2(a4)             ; COLOR17/21/25/29
        move.w  #$0f0f,$1aa(a4)
        move.w  #$00ff,$1b2(a4)
        move.w  #$0fff,$1ba(a4)
        rts
spr_ptrs:
        lea     sprdata(pc),a0
        move.l  a0,d0
        lea     $120(a4),a1                 ; SPR0PTH
        moveq   #8-1,d1
.p:     move.l  d0,(a1)+
        add.l   #4+16*4+4,d0
        dbf     d1,.p
        rts
        even
sprdata: ds.b   8*(4+16*4+4)
        endc

        ifnd    SCROLL_LIB
gfxname: dc.b   "graphics.library",0
        even
        endc
