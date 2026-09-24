;----------------------------------------------------------------------
; demo.s - Etapa 3 del port-demo: mostrar un tileset de SMW convertido.
;
; Carga el blob de datos (paleta + tileset planar) a Chip RAM y lo pone
; en pantalla con un copper list. Es la prueba de que la cadena completa
; funciona: pipeline de assets -> formato planar -> ADF -> Amiga.
;
; Entrada (desde boot.s): A6 = ExecBase, A1 = IOStdReq, A0 = base propia.
; Codigo independiente de posicion.
;
; Registros vivos:
;   a2 = copper list    a3 = datos    a4 = CUSTOM    a5 = IOStdReq
;
; Colores de borde:
;   naranja = cargando        rojo   = sin memoria
;   magenta = fallo de disco  amarillo = cabecera mala
;----------------------------------------------------------------------

        include "exec.i"

; --- registros de video (no estan en exec.i) ---
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
BPL1PTL     equ $0e2
COLOR       equ $180

; --- geometria de la pantalla ---
COLS        equ 40              ; columnas de tiles (8 px cada una)
ROWS        equ 32              ; filas de tiles (8 lineas cada una)
PLANES      equ 4               ; 4 planos = 16 colores
PAL_WORDS   equ 1<<PLANES       ; palabras de paleta al principio del blob
PLANE_BYTES equ COLS*ROWS*8     ; bytes de un plano (10240)
COPPER_MAX  equ 1024

COL_LOAD    equ $0f80           ; naranja
COL_NOMEM   equ $0f00           ; rojo
COL_DISK    equ $0f0f           ; magenta
COL_BADHDR  equ $0ff0           ; amarillo

;----------------------------------------------------------------------
; Cabecera. mkadf.py busca "A5PL" y escribe data_off/data_len.
;----------------------------------------------------------------------
        bra.w   entry
        dc.b    "A5PL"
hdr_data_off:   dc.l    0
hdr_data_len:   dc.l    0

entry:
        move.l  4.w,a6
        move.l  a1,a5
        lea     CUSTOM,a4
        move.w  #COL_LOAD,COLOR00(a4)

        ;--- cargar el blob de datos a Chip RAM ----------------------
        move.l  hdr_data_len(pc),d2
        beq     badhdr
        add.l   #511,d2
        and.l   #$fffffe00,d2
        move.l  d2,d0
        move.l  #MEMF_CHIP,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     nomem
        move.l  d0,a3                       ; a3 = datos

        move.l  a5,a1
        move.w  #CMD_READ,IO_COMMAND(a1)
        move.l  d2,IO_LENGTH(a1)
        move.l  a3,IO_DATA(a1)
        move.l  hdr_data_off(pc),IO_OFFSET(a1)
        jsr     _LVODoIO(a6)
        tst.l   d0
        bne     diskerr

        ;--- apagar el motor -----------------------------------------
        ; El CMD_READ lo volvio a encender. Con las interrupciones
        ; cortadas mas abajo, el temporizador de trackdisk ya no lo
        ; apagaria nunca: en una A500 real el LED quedaria encendido.
        move.l  a5,a1
        move.w  #TD_MOTOR,IO_COMMAND(a1)
        clr.l   IO_LENGTH(a1)
        jsr     _LVODoIO(a6)

        ;--- copper list, en Chip RAM --------------------------------
        move.l  #COPPER_MAX,d0
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     nomem
        move.l  d0,a2
        bsr     build_copper

        ;--- tomar el hardware ---------------------------------------
        ; Sin LoadView(NULL) el servidor de VBL de graphics reinstala su
        ; copper list y nos pisa la pantalla.
        ; OJO: d0/d1/a0/a1 son registros de trabajo en TODA llamada a una
        ; libreria. GfxBase no puede vivir en a0 a traves de LoadView o
        ; WaitTOF: se usa a6 directamente y ExecBase se recarga de $4.
        jsr     _LVOForbid(a6)
        lea     gfxname(pc),a1
        moveq   #0,d0
        jsr     _LVOOpenLibrary(a6)
        tst.l   d0
        beq.s   .nogfx
        move.l  d0,a6                       ; a6 = GfxBase
        sub.l   a1,a1
        jsr     _LVOLoadView(a6)
        jsr     _LVOWaitTOF(a6)
        jsr     _LVOWaitTOF(a6)
.nogfx:
        move.l  4.w,a6                      ; a6 = ExecBase otra vez
        lea     CUSTOM,a4
        move.w  #$7fff,INTENA(a4)
        move.w  #$7fff,INTREQ(a4)
        move.w  #$7fff,DMACON(a4)
        move.l  a2,COP1LC(a4)
        move.w  #0,COPJMP1(a4)              ; strobe
        move.w  #$8380,DMACON(a4)           ; MASTER|BPLEN|COPEN

.forever:
        bra.s   .forever

;----------------------------------------------------------------------
; build_copper - arma el copper list en a2.
; Usa a0/a1/d0-d2. Preserva a2, a3, a4, a5.
;----------------------------------------------------------------------
build_copper:
        movem.l d0-d2/a0-a1,-(sp)
        move.l  a2,a0

        move.l  #$008e2c81,(a0)+            ; DIWSTRT  (V=$2C, H=$81)
        move.l  #$00902cc1,(a0)+            ; DIWSTOP  (256 lineas)
        move.l  #$00920038,(a0)+            ; DDFSTRT
        move.l  #$009400d0,(a0)+            ; DDFSTOP  (320 px)
        move.l  #$01004200,(a0)+            ; BPLCON0: 4 planos + COLOR
        move.l  #$01020000,(a0)+            ; BPLCON1
        move.l  #$01040000,(a0)+            ; BPLCON2
        move.l  #$01080000,(a0)+            ; BPL1MOD = 0
        move.l  #$010a0000,(a0)+            ; BPL2MOD = 0

        ;--- punteros de bitplane ------------------------------------
        move.l  a3,d0                       ; d0 = base de los datos
        add.l   #PAL_WORDS*2,d0             ; saltar la paleta
        move.w  #BPL1PTH,d1
        move.w  #PLANES-1,d2
.bp:    swap    d0
        move.w  d1,(a0)+
        move.w  d0,(a0)+
        addq.w  #2,d1
        swap    d0
        move.w  d1,(a0)+
        move.w  d0,(a0)+
        addq.w  #2,d1
        add.l   #PLANE_BYTES,d0
        dbf     d2,.bp

        ;--- paleta --------------------------------------------------
        move.l  a3,a1
        move.w  #COLOR,d1
        move.w  #PAL_WORDS-1,d2
.col:   move.w  d1,(a0)+
        move.w  (a1)+,(a0)+
        addq.w  #2,d1
        dbf     d2,.col

        move.l  #$fffffffe,(a0)+            ; fin del copper list
        movem.l (sp)+,d0-d2/a0-a1
        rts

;----------------------------------------------------------------------
; Errores: el color se reescribe en un lazo para que el copper list del
; sistema, que pone COLOR00 una vez por frame, no lo tape.
;----------------------------------------------------------------------
nomem:  move.w  #COL_NOMEM,d0
        bra.s   stop
diskerr:
        move.w  #COL_DISK,d0
        bra.s   stop
badhdr: move.w  #COL_BADHDR,d0
stop:   lea     CUSTOM,a4
.loop:  move.w  d0,COLOR00(a4)
        bra.s   .loop

;----------------------------------------------------------------------
        even
gfxname: dc.b    "graphics.library",0
        even
