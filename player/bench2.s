;----------------------------------------------------------------------
; bench2.s - D8 opcion (d): costes en la pantalla REAL de dual playfield
; (6 planos: capa 1 = PF1, 3 planos entrelazados; capa 2 = PF2, 3 planos).
; Derivado de bench.s (mismo reloj, misma salida; tools/bench2_read.py).
;
;   W0  nada (coste de la propia medida)
;   W1  columna nueva al hacer scroll de 16 px: 14 bloques 16x16 de 3
;       planos, copia directa (en DPF no hay que componer el fondo)
;   W2  CPU: generar la lista del copper del PEOR frame de la partida
;       grabada (tools/copsim.py): 224 WAIT + 633 MOVE copiadas de una
;       tabla precalculada, con una comparacion de puntero por linea
;   W3  bobs en PF1: Banzai Bill 64x64 + 4 Rex 16x32, restaurar + dibujar
;
; Salida: igual que bench.s (19 palabras, sincronias $A55A / $5AA5).
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

; --- geometria: capa 1 = 3 planos entrelazados (PF1) ---
PLANES      equ 3
ROWB        equ 44                  ; bytes por linea de UN plano (352 px)
LINEB       equ ROWB*PLANES         ; 132: bytes por linea de la capa 1
SCR_LINES   equ 272
SCR_BYTES   equ LINEB*SCR_LINES     ; 35904
SRC_BYTES   equ 16384
COP_BYTES   equ 4096                ; la lista generada: 857*4+4 bytes
TAB_BYTES   equ 4096
NGEN_MOVE   equ 633                 ; MOVE del peor frame (copsim.py)
NGEN_LINE3  equ NGEN_MOVE-2*224     ; lineas con 3 MOVE (el resto, 2)

ITER        equ 32                  ; repeticiones por carga (media = suma/32)
SYNC_LINE   equ $20

; --- tamanos de blit: BLTSIZE = (filas << 6) | palabras ---
; Con pantalla entrelazada un blit de h lineas y 5 planos son h*5 filas.
BS_BLOCK    equ ((16*PLANES)<<6)|1    ; bloque 16x16
BS_L2HALF   equ ((112*PLANES)<<6)|21  ; media pantalla de fondo, 336 px
BS_BANZAI   equ ((64*PLANES)<<6)|5    ; 64 px + 1 palabra de desplazamiento
BS_REX      equ ((32*PLANES)<<6)|2    ; 16 px + 1 palabra de desplazamiento
BS_CLEAR    equ (408<<6)|44           ; 408*44*2 = 35904 bytes

; --- variables (offsets desde a5) ---
V_BUFA      equ 0                   ; pantalla / destino
V_BUFB      equ 4                   ; fondo (capa 2) / fuente de restauracion
V_SRC       equ 8                   ; graficos y mascaras (basura)
V_COP       equ 12
V_COP2      equ 16
V_RES       equ 24                  ; 19 palabras de resultados
V_TAB       equ 20                  ; tabla de la lista del copper
V_GEN       equ 64                  ; destino de la lista generada (W2)
NRES        equ 19
V_SIZE      equ 72

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

        move.l  #TAB_BYTES,d0
        move.l  #MEMF_ANY,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     tab_fail
        move.l  d0,V_TAB(a5)
        move.l  #COP_BYTES,d0
        bsr     alloc_chip
        move.l  d0,V_GEN(a5)
        bsr     build_tab

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
tab_fail:
        move.w  #COL_NOMEM,COLOR00(a4)
        bra.s   tab_fail

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
.blk:   ; bloque de la capa 1: copia directa (el 0 es transparente a PF2)
        move.l  V_SRC(a5),a0
        move.l  a2,a1
        moveq   #0,d0
        move.w  #BS_BLOCK,d1
        moveq   #0,d2
        moveq   #ROWB-2,d3
        bsr     bcopy
        add.w   #16*LINEB,a2
        add.w   #16*LINEB,a3
        dbf     d7,.blk
        rts

; W2: generar la lista del copper del peor frame en V_GEN (ni la lista
; activa ni la de resultados).  Por linea: WAIT, avance del puntero de la capa 1 (una
; comparacion), y las MOVE de la tabla.
work2:
        move.l  V_TAB(a5),a0
        move.l  V_GEN(a5),a1
        move.l  #$2c01fffe,d2
        moveq   #0,d3
        move.w  #224-1,d7
.line:  move.l  d2,(a1)+
        add.l   #$01000000,d2
        move.w  (a0)+,d4
        cmp.w   d4,d3
        bls.s   .noadv
        addq.w  #1,d3
.noadv: move.w  (a0)+,d1
        subq.w  #1,d1
        bmi.s   .next
.mv:    move.l  (a0)+,(a1)+
        dbf     d1,.mv
.next:  dbf     d7,.line
        move.l  #$fffffffe,(a1)+
        rts

; build_tab: por linea (cmp.w, n, n MOVE); NGEN_LINE3 lineas con 3, el resto 2.
build_tab:
        move.l  V_TAB(a5),a0
        moveq   #0,d6
        move.w  #224-1,d7
.l:     move.w  #0,(a0)+
        moveq   #2,d1
        cmp.w   #NGEN_LINE3,d6
        bhs.s   .c
        moveq   #3,d1
.c:     move.w  d1,(a0)+
        subq.w  #1,d1
.e:     move.l  #$01820000,(a0)+
        dbf     d1,.e
        addq.w  #1,d6
        dbf     d7,.l
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
        move.l  #$01006600,(a0)+            ; BPLCON0: 6 planos, DBLPF, COLOR
        move.l  #$01020000,(a0)+
        move.l  #$01040000,(a0)+
        move.w  #BPL1MOD,(a0)+
        move.w  #LINEB-42,(a0)+             ; PF1 entrelazado
        move.w  #BPL2MOD,(a0)+
        move.w  #LINEB-42,(a0)+             ; PF2 igual
        ; impares (1,3,5) = capa 1 en BUFA; pares (2,4,6) = capa 2 en BUFB
        move.w  #BPL1PTH,d1
        moveq   #3-1,d2
        moveq   #0,d3
.bp:    move.l  V_BUFA(a5),d0
        add.l   d3,d0
        bsr     .ptr
        move.l  V_BUFB(a5),d0
        add.l   d3,d0
        bsr     .ptr
        add.l   #ROWB,d3
        dbf     d2,.bp
        move.l  #$01800000,(a0)+            ; COLOR00 negro
        move.l  #$fffffffe,(a0)+
        rts
.ptr:   swap    d0
        move.w  d1,(a0)+
        move.w  d0,(a0)+
        addq.w  #2,d1
        swap    d0
        move.w  d1,(a0)+
        move.w  d0,(a0)+
        addq.w  #2,d1
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
