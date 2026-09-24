;----------------------------------------------------------------------
; logicbench.s - etapa 8d: cuanto cuesta en la Amiga la fisica de Mario
; portada (player/mario.c, etapa 8a) con la pantalla REAL de la opcion (d)
; en pantalla (DPF 6 planos). Derivado de bench2.s; salida igual
; (tools/logicbench_read.py).
;
;   W0  nada (coste de la propia medida)
;   W1  copiar a ram[] el estado de un frame (576 bytes): se descuenta
;   W2  copiar el estado "corriendo en el suelo" (frame 5410) + el frame
;       entero del jugador: mario_player (colision 8b, fisica 8a,
;       animacion CEB1) + blocks_update (bloques que rebotan)
;   W3  lo mismo con el estado "empieza un salto" (frame 10983)
;
; El C (mario.c, smwrom00.c) lo compila vbcc con -sc -sd -const-in-data:
; codigo relativo al PC y datos relativos a a4. Aca a4 = binstart, asi que
; el desplazamiento de cada dato es su posicion en este binario (< 32 KB).
; Los estados salen de tools/marioverify.c (dump), ya preparados.
;----------------------------------------------------------------------

; Una sola seccion, la misma que usan los .s de vbcc (logicbench_build.sh
; las renombra a "CODE"): con -Fbin, vasm 2.0 pone cada seccion en 0 y da
; "sections must not overlap" si el arnes queda en la seccion por defecto.
        section "CODE",code

binstart:
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

; W1: solo copiar el estado (se descuenta de W2/W3)
work1:
        lea     state_run(pc),a0
        bra     copystate

; W2: estado "corriendo" + el frame entero del jugador
work2:
        lea     state_run(pc),a0
        bsr     copystate
        bra     callframe

; W3: estado "empieza un salto" + el frame entero del jugador
work3:
        lea     state_jump(pc),a0
        bsr     copystate
        bra     callframe

; build_tab: lo llama el arranque heredado de bench2.s; aca no hace falta.
build_tab:
        rts

; copystate: a0 = 576 bytes -> _ram[$0000-$00FF] y _ram[$13C0-$14FF]
copystate:
        move.l  a4,-(sp)
        lea     binstart(pc),a4
        lea     _ram(a4),a1
        moveq   #64-1,d0
.dp:    move.l  (a0)+,(a1)+
        dbf     d0,.dp
        lea     _ram+$13C0(a4),a1
        moveq   #80-1,d0
.w13:   move.l  (a0)+,(a1)+
        dbf     d0,.w13
        move.b  #$07,_ram+$1931(a4)         ; wm_LvHeadTileset (no se graba)
        move.l  (sp)+,a4
        rts

; callframe: un frame del jugador como en el juego: CODE_00C500 (con
; colision, 8a y animacion) y despues la fase de sprites de los bloques.
; El C respeta la ABI de vbcc (d2-d7/a2-a6 preservados); a4 = base de
; datos pequenos. El mapa del nivel (lo / hi) se lee por puntero.
callframe:
        movem.l d2-d7/a2-a6,-(sp)
        lea     binstart(pc),a4
        ; el codigo del C y el mapa quedan a mas de 32 KB: direccion =
        ; binstart + desplazamiento (el binario se carga en cualquier sitio)
        move.l  a4,a0
        add.l   #map16-binstart,a0
        move.l  a0,_map16_lo(a4)
        add.l   #MAPHALF,a0
        move.l  a0,_map16_hi(a4)
        move.l  a4,a0
        add.l   #_mario_player-binstart,a0
        jsr     (a0)
        move.l  a4,a0
        add.l   #_blocks_update-binstart,a0
        jsr     (a0)
        movem.l (sp)+,d2-d7/a2-a6
        rts

        even
state_run:
        incbin  "work/cc/state_run.bin"
state_jump:
        incbin  "work/cc/state_jump.bin"
        even

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

;----------------------------------------------------------------------
; El C compilado por vbcc (work/cc/*.s, lo genera tools/logicbench_build.sh)
;----------------------------------------------------------------------
; datos del C primero (tienen que quedar a menos de 32 KB de binstart),
; despues el codigo y el mapa
        cnop    0,4
        include "work/cc/smwrom00.data.s"
        include "work/cc/mario.data.s"
        include "work/cc/mcoll.data.s"
        include "work/cc/manim.data.s"
        cnop    0,4
        include "work/cc/mario.code.s"
        include "work/cc/mcoll.code.s"
        include "work/cc/manim.code.s"
        include "work/cc/smwrom00.code.s"
        even
MAPHALF     equ 20*$1B0                     ; 20 pantallas de Yoshi's Island 1
map16:
        incbin  "work/yi1_map16.bin"
