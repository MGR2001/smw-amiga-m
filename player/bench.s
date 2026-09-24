;----------------------------------------------------------------------
; bench.s - Etapa 4: banco de pruebas de rendimiento (codigo desechable).
;
; Mide en la propia Amiga cuanto tardan las cargas de blitter que decide
; D1/D8/D9 (AGENTS.md §9), con 5 planos entrelazados EN PANTALLA para que
; la contencion de DMA sea la real:
;
;   W0  nada (coste de la propia medida)
;   W1  columna nueva al hacer scroll de 16 px: 14 bloques 16x16 x
;       (copia del fondo + bloque con mascara)
;   W2  recomposicion completa con paralaje: copia del fondo 336x224 con
;       desplazamiento + 160 bloques con mascara (peor ventana del nivel)
;   W3  bobs: Banzai Bill 64x64 + 4 Rex 16x32, restaurar + dibujar
;
; El contenido de los buffers es basura: el coste del blitter depende
; solo de los tamanos, no de los pixeles.
;
; Reloj: CIA-B timer A en modo continuo, 709379 Hz (1 tick = 1.41 us).
; Cada carga se repite ITER veces sincronizada a la misma linea.
;
; Resultado: se dibuja en pantalla (1 plano) como filas de 16 celdas
; blancas/negras, una palabra por fila, MSB a la izquierda.
; tools/bench_read.py lo decodifica de la captura de WinUAE.
;
;   fila 0      $A55A (sincronia)
;   fila 1      ticks por frame
;   filas 2-9   W0..W3 (max, media) con BLTPRI apagado (la CPU compite)
;   filas 10-17 W0..W3 (max, media) con BLTPRI encendido ("blitter nasty")
;   fila 18     $5AA5 (fin)
;
; Entrada (desde boot.s): A6 = ExecBase, A1 = IOStdReq.
; Registros con dueno: a4 = CUSTOM, a5 = variables.
;----------------------------------------------------------------------

        include "exec.i"

; --- video ---
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

; --- blitter (los que no estan en exec.i) ---
BLTCPT      equ $048
BLTBPT      equ $04c
BLTCMOD     equ $060
BLTBMOD     equ $062
BLTALWM     equ $046

; --- CIA-B timer A ---
CIAB_TALO   equ $bfd400
CIAB_TAHI   equ $bfd500
CIAB_ICR    equ $bfdd00
CIAB_CRA    equ $bfde00

; --- geometria: pantalla entrelazada de 5 planos ---
PLANES      equ 5
ROWB        equ 44                  ; bytes por linea de UN plano (352 px)
LINEB       equ ROWB*PLANES         ; 220: bytes por linea de pantalla
SCR_LINES   equ 272
SCR_BYTES   equ LINEB*SCR_LINES     ; 59840
SRC_BYTES   equ 16384
COP_BYTES   equ 512

ITER        equ 32                  ; repeticiones por carga (media = suma/32)
SYNC_LINE   equ $20

; --- tamanos de blit: BLTSIZE = (filas << 6) | palabras ---
; Con pantalla entrelazada un blit de h lineas y 5 planos son h*5 filas.
BS_BLOCK    equ ((16*PLANES)<<6)|1    ; bloque 16x16
BS_L2HALF   equ ((112*PLANES)<<6)|21  ; media pantalla de fondo, 336 px
BS_BANZAI   equ ((64*PLANES)<<6)|5    ; 64 px + 1 palabra de desplazamiento
BS_REX      equ ((32*PLANES)<<6)|2    ; 16 px + 1 palabra de desplazamiento
BS_CLEAR    equ (544<<6)|55           ; 544*55*2 = 59840 bytes

; --- variables (offsets desde a5) ---
V_BUFA      equ 0                   ; pantalla / destino
V_BUFB      equ 4                   ; fondo (capa 2) / fuente de restauracion
V_SRC       equ 8                   ; graficos y mascaras (basura)
V_COP       equ 12
V_COP2      equ 16
V_RES       equ 20                  ; 19 palabras de resultados
NRES        equ 19
V_SIZE      equ 64

COL_NOMEM   equ $0f00

;----------------------------------------------------------------------
; Cabecera: mkadf.py busca "A5PL" (este programa no usa blob de datos).
;----------------------------------------------------------------------
        bra.w   entry
        dc.b    "A5PL"
hdr_data_off:   dc.l    0
hdr_data_len:   dc.l    0

entry:
        move.l  4.w,a6
        lea     CUSTOM,a4
        lea     vars(pc),a5

        ;--- memoria (todo lo que ve el chipset va en Chip) ---------------
        move.l  #SCR_BYTES,d0
        bsr     alloc_chip
        move.l  d0,V_BUFA(a5)
        move.l  #SCR_BYTES,d0
        bsr     alloc_chip
        move.l  d0,V_BUFB(a5)
        move.l  #SRC_BYTES,d0
        bsr     alloc_chip
        move.l  d0,V_SRC(a5)
        move.l  #COP_BYTES,d0
        bsr     alloc_chip
        move.l  d0,V_COP(a5)
        move.l  #COP_BYTES,d0
        bsr     alloc_chip
        move.l  d0,V_COP2(a5)

        bsr     build_copper_test
        bsr     build_copper_result

        ;--- tomar la maquina (igual que demo.s) ----------------------------
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
        move.w  #$83c0,DMACON(a4)           ; SET|DMAEN|BPLEN|COPEN|BLTEN

        ;--- CIA-B timer A: continuo desde $FFFF ----------------------------
        move.b  #$7f,CIAB_ICR               ; sin interrupciones de CIA-B
        move.b  #0,CIAB_CRA                 ; parado
        move.b  #$ff,CIAB_TALO
        move.b  #$ff,CIAB_TAHI
        move.b  #$11,CIAB_CRA               ; START | LOAD, continuo

        ;--- calibracion: ticks en un frame ---------------------------------
        move.w  #$40,d0
        bsr     waitline
        move.w  #$41,d0
        bsr     waitline
        move.w  #$40,d0
        bsr     waitline
        bsr     readtimer
        move.w  d0,d7
        move.w  #$41,d0
        bsr     waitline
        move.w  #$40,d0
        bsr     waitline
        bsr     readtimer
        sub.w   d0,d7                       ; cuenta hacia abajo
        move.w  #$a55a,V_RES+0(a5)
        move.w  d7,V_RES+2(a5)

        ;--- cargas: primero con BLTPRI apagado, despues encendido ----------
        lea     V_RES+4(a5),a2
        bsr     suite
        move.w  #$8400,DMACON(a4)           ; SET|BLTPRI: el blitter no cede
        lea     V_RES+20(a5),a2
        bsr     suite
        move.w  #$0400,DMACON(a4)
        move.w  #$5aa5,V_RES+36(a5)

        bsr     show_results
.forever:
        bra.s   .forever

;----------------------------------------------------------------------
; suite - mide W0..W3 y guarda (max, media) en (a2)+.
;----------------------------------------------------------------------
suite:
        lea     work0(pc),a3
        bsr.s   .one
        lea     work1(pc),a3
        bsr.s   .one
        lea     work2(pc),a3
        bsr.s   .one
        lea     work3(pc),a3
.one:   move.l  a2,-(sp)
        bsr     measure
        move.l  (sp)+,a2
        move.w  d4,(a2)+                    ; max
        move.w  d5,(a2)+                    ; media
        rts

;----------------------------------------------------------------------
; alloc_chip - d0 = bytes -> d0 = direccion.  Sin memoria: rojo fijo.
;----------------------------------------------------------------------
alloc_chip:
        move.l  #MEMF_CHIP,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq.s   .fail
        rts
.fail:  move.w  #COL_NOMEM,COLOR00(a4)
        bra.s   .fail

;----------------------------------------------------------------------
; waitline - espera a que el haz este en la linea d0.w (0..311).
; destruye d1
;----------------------------------------------------------------------
waitline:
.w:     move.l  VPOSR(a4),d1                ; VPOSR:VHPOSR
        lsr.l   #8,d1
        and.w   #$1ff,d1
        cmp.w   d0,d1
        bne.s   .w
        rts

;----------------------------------------------------------------------
; readtimer - d0.l = cuenta actual del timer A de CIA-B (0..$FFFF).
; Lee alto/bajo/alto y reintenta si el alto cambio en medio.
; destruye d1, d2
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

;----------------------------------------------------------------------
; waitblit - espera a que el blitter termine.
; El primer TST es por el fallo de Agnus antiguo (BBUSY tarda en subir).
;----------------------------------------------------------------------
waitblit:
        tst.w   DMACONR(a4)
.w:     btst    #14-8,DMACONR(a4)
        bne.s   .w
        rts

;----------------------------------------------------------------------
; measure - ejecuta (a3) ITER veces, cada vez sincronizada a SYNC_LINE.
; salida: d4.w = maximo, d5.w = media (ticks).  destruye d0-d7/a0-a2
;----------------------------------------------------------------------
measure:
        moveq   #0,d4                       ; max
        moveq   #0,d5                       ; suma
        moveq   #ITER-1,d7
.loop:  move.w  #SYNC_LINE,d0
        bsr     waitline
        bsr     readtimer
        move.w  d0,d6                       ; inicio
        movem.l d4-d7/a3,-(sp)
        jsr     (a3)
        bsr     waitblit
        movem.l (sp)+,d4-d7/a3
        bsr     readtimer
        sub.w   d0,d6                       ; transcurrido (modulo 65536)
        moveq   #0,d0
        move.w  d6,d0
        add.l   d0,d5
        cmp.w   d4,d6
        bls.s   .nomax
        move.w  d6,d4
.nomax: dbf     d7,.loop
        lsr.l   #5,d5                       ; / ITER (32)
        rts

;----------------------------------------------------------------------
; Primitivas de blit.  Todas esperan al blitter antes de tocarlo.
;
; bcopy   A->D.  a0 = fuente, a1 = destino, d0 = desplazamiento (0..15),
;         d1 = BLTSIZE, d2 = mod A, d3 = mod D
; bcookie cookie-cut ABCD (D = A*B + ~A*C).  a0 = mascara, a1 = grafico,
;         a2 = destino (C = D), d0 = desplazamiento, d1 = BLTSIZE,
;         d2 = mod A/B, d3 = mod C/D
;----------------------------------------------------------------------
bcopy:
        bsr     waitblit
        ror.w   #4,d0                       ; desplazamiento -> bits 12-15
        or.w    #$09f0,d0                   ; USEA|USED, D = A
        move.w  d0,BLTCON0(a4)
        move.w  #0,BLTCON1(a4)
        move.l  #$ffffffff,BLTAFWM(a4)
        move.l  a0,BLTAPT(a4)
        move.l  a1,BLTDPT(a4)
        move.w  d2,BLTAMOD(a4)
        move.w  d3,BLTDMOD(a4)
        move.w  d1,BLTSIZE(a4)
        rts

bcookie:
        bsr     waitblit
        ; sin desplazamiento no hay palabra extra: la ultima palabra es
        ; grafico y su mascara tiene que ser $FFFF
        move.l  #$ffffffff,BLTAFWM(a4)
        tst.w   d0
        beq.s   .noshift
        move.w  #$0000,BLTALWM(a4)          ; la palabra extra de A no cuenta
.noshift:
        ror.w   #4,d0
        move.w  d0,BLTCON1(a4)              ; desplazamiento de B
        or.w    #$0fca,d0                   ; USEA|B|C|D, D = AB + ~AC
        move.w  d0,BLTCON0(a4)
        move.l  a0,BLTAPT(a4)
        move.l  a1,BLTBPT(a4)
        move.l  a2,BLTCPT(a4)
        move.l  a2,BLTDPT(a4)
        move.w  d2,BLTAMOD(a4)
        move.w  d2,BLTBMOD(a4)
        move.w  d3,BLTCMOD(a4)
        move.w  d3,BLTDMOD(a4)
        move.w  d1,BLTSIZE(a4)
        rts

;----------------------------------------------------------------------
; Cargas.  Pueden destruir d0-d7/a0-a3 (measure los guarda).
;----------------------------------------------------------------------
work0:
        rts

; W1: columna de 14 bloques en la columna 20 de la pantalla.
work1:
        move.l  V_BUFA(a5),a2
        add.w   #40,a2                      ; columna 20
        move.l  V_BUFB(a5),a3
        add.w   #40,a3
        moveq   #14-1,d7
.blk:   ; fondo de la capa 2 bajo el bloque
        move.l  a3,a0
        move.l  a2,a1
        moveq   #0,d0
        move.w  #BS_BLOCK,d1
        moveq   #ROWB-2,d2
        moveq   #ROWB-2,d3
        bsr     bcopy
        ; bloque de la capa 1 con mascara
        move.l  V_SRC(a5),a0                ; mascara
        lea     160(a0),a1                  ; grafico
        moveq   #0,d0
        move.w  #BS_BLOCK,d1
        moveq   #0,d2
        moveq   #ROWB-2,d3
        bsr     bcookie
        add.w   #16*LINEB,a2
        add.w   #16*LINEB,a3
        dbf     d7,.blk
        rts

; W2: recomposicion completa con paralaje.
work2:
        ; fondo: dos blits de 112 lineas x 336 px, con desplazamiento
        moveq   #1,d6
        move.l  V_BUFB(a5),a0
        move.l  V_BUFA(a5),a1
.half:  moveq   #7,d0
        move.w  #BS_L2HALF,d1
        moveq   #ROWB-42,d2
        moveq   #ROWB-42,d3
        movem.l a0-a1,-(sp)
        bsr     bcopy
        movem.l (sp)+,a0-a1
        add.l   #112*LINEB,a0
        add.l   #112*LINEB,a1
        dbf     d6,.half
        ; 160 bloques con mascara, en una rejilla de 21 x 14
        move.l  V_BUFA(a5),a3               ; esquina de la fila actual
        moveq   #0,d6                       ; columna
        move.w  #160-1,d7
.blk:   move.l  a3,a2
        move.w  d6,d0
        add.w   d0,d0
        add.w   d0,a2
        move.l  V_SRC(a5),a0
        lea     160(a0),a1
        moveq   #0,d0
        move.w  #BS_BLOCK,d1
        moveq   #0,d2
        moveq   #ROWB-2,d3
        bsr     bcookie
        addq.w  #1,d6
        cmp.w   #21,d6
        bne.s   .next
        moveq   #0,d6
        add.l   #16*LINEB,a3
.next:  dbf     d7,.blk
        rts

; W3: bobs.  Restaurar el fondo (A->D) y dibujar (ABCD con desplazamiento).
work3:
        ; Banzai Bill 64x64 en (x=64+5, y=40)
        move.l  V_BUFB(a5),a0
        add.l   #40*LINEB+8,a0
        move.l  V_BUFA(a5),a1
        add.l   #40*LINEB+8,a1
        moveq   #0,d0
        move.w  #BS_BANZAI,d1
        moveq   #ROWB-10,d2
        moveq   #ROWB-10,d3
        bsr     bcopy
        move.l  V_SRC(a5),a0
        lea     512(a0),a0                  ; mascara 3200 B
        lea     3200(a0),a1                 ; grafico 3200 B
        move.l  V_BUFA(a5),a2
        add.l   #40*LINEB+8,a2
        moveq   #5,d0
        move.w  #BS_BANZAI,d1
        moveq   #0,d2
        moveq   #ROWB-10,d3
        bsr     bcookie
        ; 4 Rex 16x32
        move.l  V_BUFA(a5),a3
        add.l   #150*LINEB+20,a3
        moveq   #4-1,d7
.rex:   move.l  a3,a1
        sub.l   V_BUFA(a5),a1
        add.l   V_BUFB(a5),a1
        move.l  a1,a0                       ; fuente = mismo sitio en BUFB
        move.l  a3,a1
        moveq   #0,d0
        move.w  #BS_REX,d1
        moveq   #ROWB-4,d2
        moveq   #ROWB-4,d3
        bsr     bcopy
        move.l  V_SRC(a5),a0
        add.w   #6912,a0                    ; mascara 640 B
        lea     640(a0),a1                  ; grafico 640 B
        move.l  a3,a2
        moveq   #3,d0
        move.w  #BS_REX,d1
        moveq   #0,d2
        moveq   #ROWB-4,d3
        bsr     bcookie
        addq.w  #6,a3
        dbf     d7,.rex
        rts

;----------------------------------------------------------------------
; Copper de la prueba: 320x256, 5 planos entrelazados, fetch de 336 px
; (DDFSTRT $30, como el scroll fino real).
;----------------------------------------------------------------------
build_copper_test:
        move.l  V_COP(a5),a0
        move.l  #$008e2c81,(a0)+            ; DIWSTRT
        move.l  #$00902cc1,(a0)+            ; DIWSTOP
        move.l  #$00920030,(a0)+            ; DDFSTRT (una palabra antes)
        move.l  #$009400d0,(a0)+            ; DDFSTOP
        move.l  #$01005200,(a0)+            ; BPLCON0: 5 planos + COLOR
        move.l  #$01020000,(a0)+
        move.l  #$01040000,(a0)+
        move.w  #BPL1MOD,(a0)+
        move.w  #LINEB-42,(a0)+             ; entrelazado: saltar los otros planos
        move.w  #BPL2MOD,(a0)+
        move.w  #LINEB-42,(a0)+
        move.l  V_BUFA(a5),d0
        move.w  #BPL1PTH,d1
        moveq   #PLANES-1,d2
.bp:    swap    d0
        move.w  d1,(a0)+
        move.w  d0,(a0)+
        addq.w  #2,d1
        swap    d0
        move.w  d1,(a0)+
        move.w  d0,(a0)+
        addq.w  #2,d1
        add.l   #ROWB,d0
        dbf     d2,.bp
        move.l  #$01800000,(a0)+            ; COLOR00 negro
        move.l  #$fffffffe,(a0)+
        rts

;----------------------------------------------------------------------
; Copper del resultado: 1 plano, blanco sobre negro, 320 px.
;----------------------------------------------------------------------
build_copper_result:
        move.l  V_COP2(a5),a0
        move.l  #$008e2c81,(a0)+
        move.l  #$00902cc1,(a0)+
        move.l  #$00920038,(a0)+
        move.l  #$009400d0,(a0)+
        move.l  #$01001200,(a0)+            ; 1 plano
        move.l  #$01020000,(a0)+
        move.l  #$01040000,(a0)+
        move.w  #BPL1MOD,(a0)+
        move.w  #LINEB-40,(a0)+
        move.l  V_BUFA(a5),d0
        swap    d0
        move.w  #BPL1PTH,(a0)+
        move.w  d0,(a0)+
        swap    d0
        move.w  #BPL1PTH+2,(a0)+
        move.w  d0,(a0)+
        move.l  #$01800000,(a0)+            ; COLOR00 negro
        move.l  #$01820fff,(a0)+            ; COLOR01 blanco
        move.l  #$fffffffe,(a0)+
        rts

;----------------------------------------------------------------------
; show_results - borra BUFA y dibuja las NRES palabras de V_RES.
; Fila i: lineas 8+12*i .. +7; bit 15 en la palabra 2 de la linea.
;----------------------------------------------------------------------
show_results:
        bsr     waitblit
        move.w  #$0100,BLTCON0(a4)          ; solo D, D = 0
        move.w  #0,BLTCON1(a4)
        move.l  V_BUFA(a5),BLTDPT(a4)
        move.w  #0,BLTDMOD(a4)
        move.w  #BS_CLEAR,BLTSIZE(a4)
        bsr     waitblit

        lea     V_RES(a5),a2
        move.l  V_BUFA(a5),a3
        add.l   #8*LINEB+4,a3               ; fila 0, palabra 2
        moveq   #NRES-1,d7
.row:   move.w  (a2)+,d0
        move.l  a3,a0
        moveq   #16-1,d6
.bit:   add.w   d0,d0                       ; MSB -> carry
        bcc.s   .zero
        move.l  a0,a1
        moveq   #8-1,d5
.fill:  move.w  #$ffff,(a1)
        add.w   #LINEB,a1
        dbf     d5,.fill
.zero:  addq.w  #2,a0
        dbf     d6,.bit
        add.l   #12*LINEB,a3
        dbf     d7,.row

        move.l  V_COP2(a5),COP1LC(a4)
        move.w  #0,COPJMP1(a4)
        rts

;----------------------------------------------------------------------
        even
gfxname: dc.b    "graphics.library",0
        even
vars:   ds.b    V_SIZE
        even
