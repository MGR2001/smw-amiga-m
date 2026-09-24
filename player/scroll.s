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

; lista del copper (dos: la que se ve y la que se escribe)
CL_BPLCON1  equ 20+2
CL_COLOR00  equ 36+2
CL_PTR      equ 44              ; BPL1PTH; BPLnPTH en CL_PTR + (n-1)*8
CL_LINES    equ 92
; un segmento por linea: 2 WAIT + 7 + 7 MOVE (borrado), hasta MIDMAX pares
; WAIT + MOVE a mitad de linea y el salto al segmento siguiente
; (COP2LCH, COP2LCL, COPJMP2). Tamano fijo, contenido de largo variable:
; los huecos no le cuestan tiempo al copper.
MIDMAX      equ 12
SEG         equ 64+MIDMAX*8+12  ; 172 (tools/mkscroll.py: SEG)
CL_SIZE     equ CL_LINES+SEG*LINES+4
HOFS        equ $40             ; posicion h (color clocks) de la x = 0 de pantalla
        ifnd    TXOFS
TXOFS       equ 5               ; carga: x = fin del tramo anterior + TXOFS
        endc

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

; variables (a5)
V_S     equ 0                   ; scroll de la capa 1 (px)
V_P     equ 2                   ; palabra del puntero, (s - 1) >> 4
V_CHG   equ 4                   ; .l siguiente cambio de color
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
V_LB    equ 46                  ; build_mid: bases de la lista que se escribe
V_SHB   equ 50
V_WKB   equ 54
V_MLXB  equ 58
V_SIZE  equ 62

CIAB_TALO   equ $bfd400
CIAB_TAHI   equ $bfd500
CIAB_ICR    equ $bfdd00
CIAB_CRA    equ $bfde00

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

        move.l  V_COP(a5),a0
        bsr     build_copper
        move.l  V_COP2(a5),a0
        bsr     build_copper
        bsr     init_lo
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
        move.l  V_COP(a5),V_BACK(a5)
        bsr     set_pointers
        bsr     build_mid
        move.l  V_COP2(a5),V_BACK(a5)
        bsr     set_pointers
        bsr     build_mid

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
        move.w  #$83c0,DMACON(a4)           ; MASTER|BPLEN|COPEN|BLTEN
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
        move.w  V_S(a5),d0
        cmp.w   #STOPX,d0
        ifd     BENCH
        bhs     show_results
        endc
        bhs.s   .same
        addq.w  #SPEED,d0
        cmp.w   #STOPX,d0
        bls.s   .ok
        move.w  #STOPX,d0
.ok:    move.w  d0,V_S(a5)
.same:
        ; columna nueva (cuando cambia la palabra del puntero), lo primero:
        ; en el borrado vertical el blitter tiene todo el bus, y la ultima
        ; copia (672 filas) corre mientras la CPU hace build_mid
        move.w  V_S(a5),d0
        subq.w  #1,d0
        asr.w   #4,d0
        cmp.w   V_P(a5),d0
        beq.s   .nocol
        move.w  d0,V_P(a5)
        add.w   #SLOTS-1,d0                 ; p + 21: la que entra despues
        cmp.w   D_COLS(a3),d0
        bhs.s   .nocol
        bsr     blit_column
        ifd     BENCH
        st      V_COLF(a5)
        endc
.nocol:
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
; aplica los cambios de color de la capa 1 con x <= s (tools/mkscroll.py)
; registros destruidos: d0-d2/a0-a1
;----------------------------------------------------------------------
apply_colors:
        move.l  a2,-(sp)
        move.l  V_CHG(a5),a0
        move.l  V_COP(a5),a1
        lea     CL_LINES(a1),a1
        move.l  V_COP2(a5),a2
        lea     CL_LINES(a2),a2
        move.w  V_S(a5),d0
.l:     cmp.w   (a0),d0
        blo.s   .done                       ; x > s ($FFFF: fin)
        move.w  2(a0),d1
        move.w  4(a0),(a1,d1.w)             ; en las dos listas
        move.w  4(a0),(a2,d1.w)
        addq.l  #6,a0
        bra.s   .l
.done:  move.l  a0,V_CHG(a5)
        move.l  (sp)+,a2
        rts

;----------------------------------------------------------------------
; --- init_lo ---
; lo_tab[L] = primera carga a mitad de linea de la linea L (MLX)
;----------------------------------------------------------------------
init_lo:                                    ; lo_tab[L] = (MLX[L], nxt = 0)
        lea     shadow_a(pc),a0             ; sombras: vu = 0, sin entradas
        move.w  #LINES*2-1,d0
.sh:    clr.w   (a0)
        move.w  #4,2(a0)
        lea     SHSZ(a0),a0
        dbf     d0,.sh
        lea     wake_a(pc),a0               ; wake = 0: todas en el 1er frame
        move.w  #LINES*2-1,d0
.wk:    clr.w   (a0)+
        dbf     d0,.wk
        move.l  a3,a0
        add.l   D_MLX(a3),a0
        lea     lo_tab(pc),a1
        move.w  #LINES-1,d0
.l:     move.w  (a0)+,(a1)+
        clr.w   (a1)+
        dbf     d0,.l
        rts

;----------------------------------------------------------------------
; --- build_mid ---
; entrada:  V_BACK = lista que se escribe, V_S = scroll
; salida:   en cada segmento de linea, las cargas a mitad de linea que se
;           ven con esta camara (WAIT + MOVE; solo MOVE si cae a menos de
;           16 px de la anterior) y el salto al segmento siguiente.
; registros destruidos: d0-d1/a0-a1 (guarda el resto)
;
; Incremental. Por lista y por linea hay una SOMBRA (SHSZ bytes):
;   +0 vu: la estructura de la linea (que cargas, con o sin WAIT) vale
;      mientras s < vu. Cambia cuando la carga mas vieja sale por la
;      izquierda, una entra por la derecha o una saltada empieza a verse.
;   +2 fin de las entradas (4 = ninguna)
;   +4 por cada WAIT escrito: desplazamiento en el segmento, x objetivo
; Con s < vu solo se recalculan las h de los WAIT (camino rapido).
; wake[L] (por lista) = la s desde la que hay que mirar la linea: 0 si
; tiene cargas escritas, vu si no. Un bucle minimo recorre wake y solo
; entra en las lineas que hacen falta (de media ~35 de 224).
; PROTOTIPO: la camara solo avanza (lo_tab y vu suponen s creciente).
;----------------------------------------------------------------------
SHSZ        equ 4+MIDMAX*4

build_mid:
        movem.l d2-d7/a2-a6,-(sp)
        move.l  V_BACK(a5),a0
        lea     shadow_a(pc),a6
        lea     wake_a(pc),a4
        cmp.l   V_COP(a5),a0
        beq.s   .ln
        lea     shadow_b(pc),a6
        lea     wake_b(pc),a4
.ln:    lea     CL_LINES(a0),a0
        move.l  a0,V_LB(a5)                 ; bases, para cada linea visitada
        move.l  a6,V_SHB(a5)
        move.l  a4,V_WKB(a5)
        move.l  a3,a1
        add.l   D_MLD(a3),a1                ; a1 = cargas
        move.l  a3,a2
        add.l   D_MLX(a3),a2
        move.l  a2,V_MLXB(a5)
        move.w  V_S(a5),d6                  ; d6 = s
        move.w  d6,d5
        add.w   #320,d5                     ; d5 = s + 320
        move.w  #LINES-1,d3
.scan:  cmp.w   (a4)+,d6                    ; s >= wake: hay que mirarla
        bhs.s   .visit
        dbf     d3,.scan
        movem.l (sp)+,d2-d7/a2-a6
        rts
.visit: movem.l d3/a4,-(sp)
        move.l  a4,d0
        sub.l   V_WKB(a5),d0
        lsr.w   #1,d0
        subq.w  #1,d0                       ; d0 = linea
        move.w  d0,d1
        mulu    #SEG,d1
        move.l  V_LB(a5),a0
        add.l   d1,a0                       ; a0 = segmento
        move.w  d0,d1
        mulu    #SHSZ,d1
        move.l  V_SHB(a5),a6
        add.l   d1,a6                       ; a6 = sombra
        lea     lo_tab(pc),a4
        move.w  d0,d1
        lsl.w   #2,d1
        add.w   d1,a4                       ; a4 = (lo, nxt)
        move.l  V_MLXB(a5),a2
        move.w  d0,d1
        add.w   d1,d1
        lea     2(a2,d1.w),a2               ; a2 = MLX[L+1]
        move.w  d0,d7
        add.w   #$2c,d7
        lsl.w   #8,d7
        or.w    #1,d7                       ; d7 = WAIT (v << 8) | 1
        bsr     .do_line
        moveq   #0,d0                       ; wake: 0 si hay cargas escritas
        cmp.w   #4,2(a6)                    ; (sus h cambian cada frame);
        bne.s   .wk                         ; si no, vu
        move.w  (a6),d0
.wk:    movem.l (sp)+,d3/a4
        move.w  d0,-2(a4)
        dbf     d3,.scan
        movem.l (sp)+,d2-d7/a2-a6
        rts

; una linea: a0 segmento, a2 = MLX[L+1], a4 = lo_tab[L], a6 = sombra, d7
.do_line:
        cmp.w   (a6),d6
        bhs     .full
        ;--- camino rapido: la misma estructura, otras h ---------------
        move.w  2(a6),d4
        subq.w  #4,d4
        beq     .next
        lsr.w   #2,d4                       ; d4 = WAITs
        lea     4(a6),a3
        moveq   #0,d1                       ; ultima h
.fast:  move.w  (a3)+,d0                    ; desplazamiento del WAIT
        move.w  (a3)+,d2                    ; x objetivo
        sub.w   d6,d2
        bpl.s   .fp
        moveq   #0,d2
.fp:    lsr.w   #1,d2
        add.w   #HOFS,d2
        and.w   #$fe,d2
        cmp.w   d1,d2
        bhs.s   .fh
        move.w  d1,d2
.fh:    cmp.w   #$e2,d2
        bls.s   .fh2
        move.w  #$e2,d2
.fh2:   move.w  d2,d1
        or.w    d7,d2
        move.w  d2,(a0,d0.w)
        subq.w  #1,d4
        bne.s   .fast
        bra     .next
        ;--- camino completo ---------------------------------------------
.full:  move.w  2(a6),-(sp)                 ; habia cargas escritas?
        move.w  #4,2(a6)
        move.w  (a4),d2                     ; d2 = primera carga viva
        move.w  (a2),d3                     ; d3 = fin de la linea
.adv:   cmp.w   d3,d2
        bhs.s   .adv_done
        move.w  d2,d0
        lsl.w   #3,d0
        cmp.w   (a1,d0.w),d6                ; fin del tramo anterior < s?
        bls.s   .adv_done
        addq.w  #1,d2
        bra.s   .adv
.adv_done:
        move.w  d2,(a4)
        move.w  #$ffff,d0                   ; nxt = fin de la carga d2 - 319
        move.w  #$ffff,(a6)                 ; vu = fin de la carga d2 + 1
        cmp.w   d3,d2
        bhs.s   .nx
        move.w  d2,d0
        lsl.w   #3,d0
        move.w  (a1,d0.w),d0
        move.w  d0,(a6)
        addq.w  #1,(a6)
        sub.w   #319,d0
        bcc.s   .nx
        moveq   #0,d0
.nx:    move.w  d0,2(a4)
        lea     64(a0),a3                   ; a3 = donde van las cargas
        moveq   #0,d4                       ; d4 = cargas escritas
        moveq   #0,d1                       ; d1 = ultima h
.ld:    cmp.w   d3,d2
        bhs     .ld_done
        move.w  d2,d0
        lsl.w   #3,d0
        lea     (a1,d0.w),a5                ; OJO: a5 prestado (vars)
        cmp.w   (a5),d5                     ; fin anterior >= s + 320: ya no
        bhi.s   .in
        move.w  (a5),d0                     ; entra cuando s > fin - 320
        sub.w   #319,d0
        bcc.s   .vu1
        moveq   #0,d0
.vu1:   cmp.w   (a6),d0
        bhs     .ld_done
        move.w  d0,(a6)
        bra     .ld_done
.in:    move.w  2(a5),d0                    ; principio del nuevo
        cmp.w   d0,d5
        bhi.s   .vis
        sub.w   #319,d0                     ; empieza fuera: se vera cuando
        cmp.w   (a6),d0                     ; s > principio - 320
        bhs     .next_ld
        move.w  d0,(a6)
        bra     .next_ld
.vis:   move.w  (a5),d0                     ; al principio de la ventana: si
        addq.w  #TXOFS,d0                   ; cambian varios registros juntos,
                                            ; cada MOVE llega 16 px despues del
                                            ; anterior (ventanas >= 48 px)
        move.w  d0,-(sp)                    ; x objetivo
        sub.w   d6,d0
        bpl.s   .pos
        moveq   #0,d0
.pos:   lsr.w   #1,d0
        add.w   #HOFS,d0
        and.w   #$fe,d0
        cmp.w   d1,d0
        bhs.s   .h
        move.w  d1,d0
.h:     cmp.w   #$e2,d0
        bls.s   .h2
        move.w  #$e2,d0
.h2:    tst.w   d4                          ; a menos de 16 px de la anterior:
        beq.s   .wait                       ; sin WAIT (el copper en DPF tiene
        sub.w   d1,d0                       ; una ranura cada 16 px y un WAIT
        cmp.w   #8,d0                       ; gasta ranuras como un MOVE)
        bhi.s   .w0
        addq.l  #2,sp                       ; sin WAIT: sin sombra
        bra.s   .mv
.w0:    add.w   d1,d0
.wait:  move.w  d0,d1
        or.w    d7,d0
        move.w  d0,(a3)                     ; WAIT
        move.w  #$fffe,2(a3)
        move.l  a3,d0
        sub.l   a0,d0
        move.w  d0,-(sp)                    ; desplazamiento del WAIT
        move.w  2(a6),d0
        move.w  (sp)+,(a6,d0.w)
        move.w  (sp)+,2(a6,d0.w)
        addq.w  #4,2(a6)
        addq.l  #4,a3
.mv:    move.w  4(a5),(a3)+                 ; MOVE registro, color
        move.w  6(a5),(a3)+
        addq.w  #1,d4
        cmp.w   #MIDMAX,d4
        beq.s   .ld_done
.next_ld:
        addq.w  #1,d2
        bra     .ld
.ld_done:
        lea     vars(pc),a5
        move.w  (sp)+,d0                    ; lo que habia escrito antes
        tst.w   d4
        bne.s   .jump
        cmp.w   #4,d0
        beq.s   .next                       ; sin cargas, igual que antes
.jump:  lea     SEG(a0),a5                  ; el siguiente segmento
        move.l  a5,d0
        lea     vars(pc),a5
        move.w  #$0084,(a3)+                ; COP2LCH
        swap    d0
        move.w  d0,(a3)+
        move.w  #$0086,(a3)+                ; COP2LCL
        swap    d0
        move.w  d0,(a3)+
        move.l  #$008a0000,(a3)+            ; COPJMP2
.next:  rts

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
; --- blit_column ---
; entrada:  d0.w = columna de bloques del nivel
; salida:   la columna en sus dos copias del buffer circular de PF1, con el
;           blitter: un blit por bloque (1 palabra x 48 filas: 16 lineas x
;           3 planos, que en el buffer entrelazado estan a ROWB1 bytes) y
;           la segunda copia de una vez (1 palabra x 672 filas). No espera
;           al ultimo blit.
; registros destruidos: d0-d3/a0-a2
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

blit_column:
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
        move.l  a2,-(sp)
        move.l  a3,d2
        add.l   D_BLK(a3),d2                ; d2 = bloques
        bsr.s   bwait
        move.l  #$09f00000,BLTCON0R(a4)     ; A -> D, BLTCON1 = 0
        move.l  #$ffffffff,BLTAFWMR(a4)
        move.w  #0,BLTAMODR(a4)
        move.w  #ROWB1-2,BLTDMODR(a4)
        moveq   #LINES/16-1,d3
.blk:   moveq   #0,d0
        move.b  (a1)+,d0
        mulu    #96,d0
        add.l   d2,d0
        bsr.s   bwait
        move.l  d0,BLTAPTR(a4)
        move.l  a2,BLTDPTR(a4)
        move.w  #(48<<6)|1,BLTSIZER(a4)
        lea     16*LINEB1(a2),a2
        dbf     d3,.blk
        move.l  (sp)+,a2                    ; segunda copia, 44 bytes despues
        bsr.s   bwait
        move.w  #ROWB1-2,BLTAMODR(a4)
        move.l  a2,BLTAPTR(a4)
        lea     SLOTS*2(a2),a2
        move.l  a2,BLTDPTR(a4)
        move.w  #((LINES*3)<<6)|1,BLTSIZER(a4)
        rts

bwait:  btst    #6,DMACONR(a4)              ; dos veces: bug del Agnus viejo
.w:     btst    #6,DMACONR(a4)
        bne.s   .w
        rts

;----------------------------------------------------------------------
; --- build_copper ---
; la lista fija; los colores iniciales de las dos capas por linea
; registros destruidos: d0-d4/a0-a2
;----------------------------------------------------------------------
build_copper:                               ; a0 = lista
        movem.l a2,-(sp)
        move.l  a0,d4                       ; d4 = principio de la lista
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
.line:  move.l  a0,d5                       ; d5 = principio del segmento
        move.w  d2,d0
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
        movem.l (sp)+,a2
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

; el trabajo del frame termina cuando termina el blitter
bench_frame:
        bsr     bwait
        bsr     readtimer
        move.w  V_T0(a5),d1
        sub.w   d0,d1                       ; cuenta hacia abajo
        lea     V_MAXC(a5),a0
        tst.b   V_COLF(a5)
        bne.s   .c
        lea     V_MAXN(a5),a0
.c:     cmp.w   (a0),d1
        bls.s   .m
        move.w  d1,(a0)
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

fail:   lea     CUSTOM,a4
.l:     move.w  #$0f00,COLOR00(a4)
        bra.s   .l

        even
vars:   ds.b    V_SIZE
lo_tab: ds.w    LINES*2                     ; build_mid: (primera carga viva, nxt)
        even
shadow_a: ds.b  SHSZ*LINES                  ; build_mid: sombra de cada lista
shadow_b: ds.b  SHSZ*LINES
wake_a: ds.w    LINES                       ; build_mid: s desde la que hay que
wake_b: ds.w    LINES                       ; mirar cada linea (0: siempre)
gfxname: dc.b   "graphics.library",0
        even
