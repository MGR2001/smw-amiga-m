;----------------------------------------------------------------------
; game.s - Etapas 6.3 y 6b: el juego. Un solo binario con la logica del
; port (el C de player/*.c que compila vbcc, level_frame) y el scroll
; (player/scroll.s como biblioteca, SCROLL_LIB).
;
; Cada frame, desde la linea $110 (despues de la ultima visible):
;   entrada -> level_frame (camara, Mario, sprites) -> scroll_frame con
;   s = Bg1HOfs ($1A-$1B), que escribe la lista del copper que se ve
;   desde el frame siguiente (un frame de latencia, como la SNES).
;
; -DREPLAY (6.3): la entrada sale de work/yi1_replay.bin (m68kverify.py
; --mode loop --sprites --replay): el joypad grabado de cada frame y las
; mismas resincronizaciones que hace el lazo cerrado del PC, asi que la
; Amiga sigue la partida grabada igual que el PC.
;   -DSTOPF=n: se para despues del frame n del replay (0 = el primero) y
;   se queda quieto (para capturar: la pantalla es la de la camara del
;   oraculo en el frame primero + n).
;
;   sh tools/game_build.sh               (-> work/game.adf)
;
; Memoria (D13): el ADF trae el binario (lo carga boot.s en chip) y
; work/yi1_s.dat. El binario se copia a la slow RAM si la hay (todo el
; codigo es relativo al PC y los datos del C a a4) y libera la chip: no
; entran en 512 KB el binario, los datos del scroll, PF1 y las dos listas.
;
; Registros: en el bucle, a3 = datos del scroll, a4 = CUSTOM, a5 = vars
; del scroll (lo que espera scroll.s). El C se llama con a4 = binstart
; (sus datos: -sd) y respeta la ABI de vbcc (d2-d7/a2-a6).
;----------------------------------------------------------------------

; una sola seccion (como logicbench.s: vasm -Fbin)
        section "CODE",code

; GETBASE An: An = binstart (desde cualquier sitio: lea binstart(pc) solo
; llega a 32 KB)
GETBASE macro
.b\@:   lea     .b\@(pc),\1
        sub.l   #.b\@-binstart,\1
        endm

binstart:
        bra.s   hdr_go                      ; el codigo queda a mas de 32 KB
        dc.b    "A5PL"
hdr_data_off:   dc.l    0
hdr_data_len:   dc.l    0
hdr_go: lea     binstart(pc),a0
        add.l   #entry-binstart,a0
        jmp     (a0)


;----------------------------------------------------------------------
; El C compilado por vbcc (work/cc/*.s, tools/logicbench_build.sh). Sus
; datos primero: tienen que quedar a menos de 32 KB de binstart (P36).
;----------------------------------------------------------------------
        cnop    0,4
        include "work/cc/smwrom00.data.s"
        even
cdata0:
        include "work/cc/mario.data.s"
        include "work/cc/mcoll.data.s"
        include "work/cc/manim.data.s"
        include "work/cc/mgfx.data.s"
        include "work/cc/mcam.data.s"
        include "work/cc/msprite.data.s"
        include "work/cc/mspr.data.s"
        even
cdata1:
        ifgt    cdata1-binstart-$7ffe
        fail    "los datos del C quedan a mas de 32 KB de binstart (P36)"
        endc
        cnop    0,4
        include "work/cc/mario.code.s"
        include "work/cc/mcoll.code.s"
        include "work/cc/manim.code.s"
        include "work/cc/mgfx.code.s"
        include "work/cc/mcam.code.s"
        include "work/cc/msprite.code.s"
        include "work/cc/mspr.code.s"
        include "work/cc/smwrom00.code.s"
        include "work/cc/smwram.i"
        include "player/logic68k.s"
        include "player/mspr68k.s"
        even

;----------------------------------------------------------------------
; El scroll (Etapa 6)
;----------------------------------------------------------------------
SCROLL_LIB  equ 1
SPRITES     equ 1                           ; punteros de sprites en la lista
        include "player/scroll.s"

MAPHALF     equ 20*$1B0                     ; 20 pantallas de Yoshi's Island 1
CIAA_SDR    equ $bfec01
CIAA_ICR    equ $bfed01
CIAA_CRA    equ $bfee01
JOY1DAT     equ $00c
POTGO       equ $034
POTINP      equ $016
MSPR_WORDS  equ 2+2*40+2                    ; mario.h: palabras por sprite
SPRBUF      equ 4*MSPR_WORDS*2              ; las 2 parejas de Mario (bytes)
SPR_KEEPN   equ 11                          ; tablas de sprites que se conservan

;----------------------------------------------------------------------
; Arranque. Desde boot.s: a0 = base (chip), a1 = IOStdReq, a6 = ExecBase
;----------------------------------------------------------------------
entry:
        move.l  4.w,a6
        move.l  a1,a2                       ; a2 = IOStdReq
        lea     CUSTOM,a4
        move.w  #$0f80,COLOR00(a4)

        ;--- el binario a la slow RAM (si la hay) ----------------------
        GETBASE a0                          ; = a0 de boot.s
        lea     old_base(pc),a1             ; (antes de copiar: la copia
        move.l  a0,(a1)                     ; lo lleva)
        move.l  #binend-binstart,d0
        move.l  #MEMF_FAST,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq.s   .stay                       ; solo 512 KB: se queda en chip
        move.l  d0,a1
        GETBASE a0
        move.l  #(binend-binstart)/4-1,d1
.cp:    move.l  (a0)+,(a1)+
        subq.l  #1,d1
        bpl.s   .cp
        move.l  d0,a0
        add.l   #.moved-binstart,a0
        jmp     (a0)                        ; seguir en la copia
.moved: lea     old_base(pc),a0             ; soltar la chip de boot.s
        move.l  (a0),a1                     ; (la longitud de mkadf.py:
        move.l  #(binend-binstart+511)&-512,d0  ; redondeada a 512)
        jsr     _LVOFreeMem(a6)
.stay:
        lea     CUSTOM,a4
        lea     vars(pc),a5

        ;--- datos del scroll a chip -----------------------------------
        GETBASE a0
        move.l  hdr_data_len-binstart(a0),d2
        beq     gfail
        add.l   #511,d2
        and.l   #$fffffe00,d2
        move.l  d2,d0
        move.l  #MEMF_CHIP,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     gfail
        move.l  d0,a3
        move.l  a2,a1
        move.w  #CMD_READ,IO_COMMAND(a1)
        move.l  d2,IO_LENGTH(a1)
        move.l  a3,IO_DATA(a1)
        GETBASE a0
        move.l  hdr_data_off-binstart(a0),IO_OFFSET(a1)
        jsr     _LVODoIO(a6)
        tst.l   d0
        bne     gfail
        move.l  a2,a1
        move.w  #TD_MOTOR,IO_COMMAND(a1)
        clr.l   IO_LENGTH(a1)
        jsr     _LVODoIO(a6)

        move.l  #BUF1,d0
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     gfail
        move.l  d0,V_BUF1(a5)
        move.l  #CL_SIZE,d0
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     gfail
        move.l  d0,V_COP(a5)
        move.l  #CL_SIZE,d0
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     gfail
        move.l  d0,V_COP2(a5)
        move.l  #2*SPRBUF+8,d0              ; Mario (una por lista) + nulo
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     gfail
        lea     g_spra(pc),a0
        move.l  d0,(a0)+                    ; g_spra
        add.l   #SPRBUF,d0
        move.l  d0,(a0)+                    ; g_sprb
        add.l   #SPRBUF,d0
        move.l  d0,(a0)                     ; g_null: 0, 0 (MEMF_CLEAR)

        ;--- el C: punteros al mapa y a los sprites del nivel -----------
        movem.l a3-a5,-(sp)
        GETBASE a4
        move.l  a4,a0
        add.l   #map16-binstart,a0
        move.l  a0,_map16_lo(a4)
        add.l   #MAPHALF,a0
        move.l  a0,_map16_hi(a4)
        move.l  a4,a0
        add.l   #spr_lv-binstart,a0
        move.l  a0,_spr_level(a4)
        move.b  #1,_level_sprites(a4)
        move.l  a4,a0
        add.l   #gfx32-binstart,a0
        move.l  a0,_gfx32(a4)
        movem.l (sp)+,a3-a5

        bsr     replay_init
        ifd     REPLAY
        bsr     game_step                   ; el primer frame (SYNC)
        else
        bsr     live_init                   ; el estado del primer frame
        endc
        bsr     cam_to_s
        bsr     scroll_init
        move.l  V_BACK(a5),-(sp)            ; Mario en las dos listas
        move.l  V_COP(a5),V_BACK(a5)
        bsr     mario_draw
        move.l  V_COP2(a5),V_BACK(a5)
        bsr     mario_draw
        move.l  (sp)+,V_BACK(a5)

        ;--- tomar el hardware (como scroll.s) ------------------------
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
        move.w  #$83e0,DMACON(a4)           ; MASTER|BPLEN|COPEN|BLTEN|SPREN
        ifnd    REPLAY
        lea     kb_int(pc),a0               ; teclado: nivel 2 (PORTS)
        move.l  a0,$68.w
        move.b  #$7f,CIAA_ICR               ; solo el SP del CIA-A
        move.b  #$88,CIAA_ICR
        tst.b   CIAA_ICR
        and.b   #$bf,CIAA_CRA               ; SPMODE: entrada
        move.w  #$ff00,POTGO(a4)            ; 2.o boton del joystick
        move.w  #$0008,INTREQ(a4)
        move.w  #$c008,INTENA(a4)           ; INTEN|PORTS
        endc

;----------------------------------------------------------------------
; Bucle por frame
;----------------------------------------------------------------------
gframe:
.w1:    move.l  VPOSR(a4),d0
        lsr.l   #8,d0
        and.w   #$1ff,d0
        cmp.w   #$110,d0
        blo.s   .w1
        bsr     game_step
        bsr     cam_to_s
        bsr     mario_draw
        bsr     scroll_frame
.w2:    move.l  VPOSR(a4),d0                ; esperar a que empiece otro frame
        lsr.l   #8,d0
        and.w   #$1ff,d0
        cmp.w   #$110,d0
        bhs.s   .w2
        bra.s   gframe

;----------------------------------------------------------------------
; --- cam_to_s --- V_S = Bg1HOfs, dentro del nivel
;----------------------------------------------------------------------
cam_to_s:
        GETBASE a0
        add.l   #_ram-binstart,a0
        moveq   #0,d0
        move.b  $1B(a0),d0
        lsl.w   #8,d0
        move.b  $1A(a0),d0
        move.w  D_W(a3),d1
        sub.w   #VIS,d1
        cmp.w   d1,d0
        bls.s   .ok
        move.w  d1,d0
.ok:    move.w  d0,V_S(a5)
        rts

;----------------------------------------------------------------------
; --- game_step --- la entrada y la logica de un frame
; registros destruidos: d0-d1/a0-a1
;----------------------------------------------------------------------
        ifd     REPLAY
; los ops de m68kverify.py (REP_*)
OP_RUN      equ 0
OP_SYNC     equ 1
OP_SKIP     equ 2
OP_RUNSYNC  equ 3

game_step:
        lea     g_left(pc),a0
        tst.w   (a0)
        beq.s   .done                       ; fin del replay: quieto
        subq.w  #1,(a0)
        move.l  g_op(pc),a1
        lea     g_op(pc),a0
        addq.l  #6,(a0)
        moveq   #0,d0
        move.b  (a1),d0                     ; op
        cmp.b   #OP_SKIP,d0
        beq.s   .done
        cmp.b   #OP_SYNC,d0
        beq.s   .sync
        move.l  d0,-(sp)
        GETBASE a0                 ; joypad -> $15-$18
        add.l   #_ram+$15-binstart,a0
        move.b  2(a1),(a0)+
        move.b  3(a1),(a0)+
        move.b  4(a1),(a0)+
        move.b  5(a1),(a0)+
        bsr     callframe
        move.l  (sp)+,d0
        cmp.b   #OP_RUNSYNC,d0
        bne.s   .done
.sync:  move.l  g_sts(pc),a0
        lea     g_sts(pc),a1
        add.l   #576,(a1)
        bra     loadstate
.done:  rts
        endc

; replay_init: punteros a los ops y a los estados; wm_SprLoadStatus. En
; vivo solo se usa el primer estado (el del principio de la partida)
replay_init:
        movem.l d2/a2,-(sp)
        GETBASE a0
        add.l   #replay-binstart,a0
        move.w  4(a0),d0                    ; frames
        ifd     STOPF
        ifd     REPLAY
        cmp.w   #STOPF+1,d0
        bls.s   .n
        move.w  #STOPF+1,d0
.n:
        endc
        endc
        lea     g_left(pc),a1
        move.w  d0,(a1)
        move.l  a0,d0
        add.l   12(a0),d0
        lea     g_op(pc),a1
        move.l  d0,(a1)
        move.l  a0,d0
        add.l   16(a0),d0
        lea     g_sts(pc),a1
        move.l  d0,(a1)
        lea     20(a0),a0                   ; 128 bytes -> $1938
        GETBASE a1
        add.l   #_ram+$1938-binstart,a1
        moveq   #128/4-1,d0
.c:     move.l  (a0)+,(a1)+
        dbf     d0,.c
        movem.l (sp)+,d2/a2
        rts

g_left: dc.w    0                           ; frames que faltan
g_op:   dc.l    0                           ; siguiente op
g_sts:  dc.l    0                           ; siguiente estado

        ifnd    REPLAY
;----------------------------------------------------------------------
; En vivo (6b.3): teclado y joystick -> $15-$18 -> level_frame. Lo que el
; port no tiene (animaciones de Mario, tuberias, meta...) congela el frame
; (mario_unsupported): despues de RESTART frames el nivel vuelve a
; empezar. El dano (MEV_HURT) se resuelve aca, sin la animacion: grande ->
; chico con el tiempo de invulnerabilidad; chico -> reinicio.
;----------------------------------------------------------------------
RESTART     equ 75                          ; 1,5 s

; live_init: guarda los datos del C (con ram[]) y el mapa como estan al
; cargar, y pone el estado del primer frame de la partida
live_init:
        movem.l d2/a2/a6,-(sp)
        move.l  4.w,a6
        move.l  #(cdata1-cdata0)+MAPHALF*2,d0
        moveq   #MEMF_PUBLIC,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     gfail
        lea     g_save(pc),a0
        move.l  d0,(a0)
        move.l  d0,a1
        GETBASE a0
        add.l   #cdata0-binstart,a0
        move.w  #(cdata1-cdata0)/2-1,d0
.c1:    move.w  (a0)+,(a1)+
        dbf     d0,.c1
        GETBASE a0
        add.l   #map16-binstart,a0
        move.w  #MAPHALF-1,d0               ; (MAPHALF*2 bytes)
.c2:    move.w  (a0)+,(a1)+
        dbf     d0,.c2
        movem.l (sp)+,d2/a2/a6
        bra.s   live_start

; live_restart: todo como al cargar, y el primer frame
live_restart:
        move.l  g_save(pc),a0
        GETBASE a1
        add.l   #cdata0-binstart,a1
        move.w  #(cdata1-cdata0)/2-1,d0
.c1:    move.w  (a0)+,(a1)+
        dbf     d0,.c1
        GETBASE a1
        add.l   #map16-binstart,a1
        move.w  #MAPHALF-1,d0
.c2:    move.w  (a0)+,(a1)+
        dbf     d0,.c2
        lea     g_dead(pc),a0
        clr.w   (a0)
        bsr     replay_init                 ; wm_SprLoadStatus y g_sts
live_start:
        move.l  g_sts(pc),a0                ; el primer estado (SYNC)
        bra     loadstate

game_step:
        movem.l d2-d5/a2,-(sp)
        bsr     read_input                  ; d0 = $15, d1 = $17
        GETBASE a2
        move.l  a2,a0
        add.l   #_ram+$15-binstart,a0
        move.b  (a0),d2                     ; $16 = recien apretado
        not.b   d2
        and.b   d0,d2
        move.b  d0,(a0)+
        move.b  d2,(a0)+
        move.b  (a0),d2                     ; $18
        not.b   d2
        and.b   d1,d2
        move.b  d1,(a0)+
        move.b  d2,(a0)
        clr.l   _mario_events(a2)
        bsr     callframe
        move.l  a2,a0
        add.l   #_ram-binstart,a0
        btst    #4,_mario_events+3(a2)      ; MEV_HURT (HurtMario)
        beq.s   .nh
        tst.b   $19(a0)                     ; wm_MarioPowerUp
        beq.s   .dead                       ; chico: muere
        clr.b   $19(a0)
        move.b  #$7f,$1497(a0)              ; wm_PlayerHurtTimer
.nh:    tst.l   _mario_unsupported(a2)
        bne.s   .dead
        tst.b   $71(a0)                     ; wm_MarioAnimation
        bne.s   .dead
        lea     g_dead(pc),a0
        tst.w   (a0)                        ; (el que murio sigue contando)
        beq.s   .x
.dead:  lea     g_dead(pc),a0
        addq.w  #1,(a0)
        cmp.w   #RESTART,(a0)
        blo.s   .x
        bsr     live_restart
.x:     movem.l (sp)+,d2-d5/a2
        rts

; read_input: teclado (keymap, con la tabla D14) OR joystick del puerto 2
; salida: d0.b = byetUDLR ($15), d1.b = axlr---- ($17)
; registros destruidos: d2-d5/a0-a1
read_input:
        moveq   #0,d0
        moveq   #0,d1
        lea     keymap(pc),a0
        lea     keytab(pc),a1
.k:     move.b  (a1)+,d2                    ; codigo raw ($FF: fin)
        bmi.s   .joy
        move.b  (a1)+,d3                    ; 0: $15, 1: $17
        move.b  (a1)+,d4                    ; bit
        moveq   #0,d5
        move.b  d2,d5
        lsr.w   #3,d5
        and.w   #7,d2
        btst    d2,(a0,d5.w)
        beq.s   .k
        tst.b   d3
        bne.s   .kb
        bset    d4,d0
        bra.s   .k
.kb:    bset    d4,d1
        bra.s   .k
.joy:   move.w  CUSTOM+JOY1DAT,d2
        btst    #1,d2
        beq.s   .j1
        bset    #0,d0                       ; R
.j1:    btst    #9,d2
        beq.s   .j2
        bset    #1,d0                       ; L
.j2:    move.w  d2,d3
        lsr.w   #1,d3
        eor.w   d2,d3                       ; bit 0: abajo, bit 8: arriba
        btst    #0,d3
        beq.s   .j3
        bset    #2,d0                       ; D
.j3:    btst    #8,d3
        beq.s   .j4
        bset    #3,d0                       ; U
.j4:    btst    #7,CIAA_PRA                 ; boton 1 (0 = apretado)
        bne.s   .j5
        btst    #8,d3                       ; arriba + boton = A (giro)
        beq.s   .jb
        bset    #7,d1
        bra.s   .j5
.jb:    bset    #7,d0                       ; B (salto)
.j5:    btst    #14-8,CUSTOM+POTINP         ; boton 2 = Y (correr)
        bne.s   .j6
        bset    #6,d0
.j6:    rts

; D14: codigo raw del teclado, registro (0 = $15 byetUDLR, 1 = $17
; axlr----), bit. Cambiar la asignacion es cambiar esta tabla.
keytab: dc.b    $4c,0,3                     ; flecha arriba    U
        dc.b    $4d,0,2                     ; flecha abajo     D
        dc.b    $4e,0,0                     ; flecha derecha   R
        dc.b    $4f,0,1                     ; flecha izquierda L
        dc.b    $31,0,7                     ; Z                B (salto)
        dc.b    $32,1,7                     ; X                A (giro)
        dc.b    $20,0,6                     ; A                Y (correr)
        dc.b    $21,1,6                     ; S                X
        dc.b    $44,0,4                     ; Return           Start
        dc.b    $61,0,5                     ; Shift derecho    Select
        dc.b    $ff
        even

; kb_int: interrupcion de nivel 2 (PORTS): un byte del teclado. Codigo raw
; = ~SDR rotado un bit a la derecha, bit 7 = soltada. Handshake: SPMODE en
; salida al menos 85 us (se esperan 2 lineas enteras, con VHPOSR).
kb_int:
        movem.l d0-d1/a0,-(sp)
        move.b  CIAA_ICR,d0                 ; (leerlo lo borra)
        btst    #3,d0                       ; SP: llego un byte
        beq.s   .x
        move.b  CIAA_SDR,d0
        or.b    #$40,CIAA_CRA               ; SPMODE: salida
        not.b   d0
        ror.b   #1,d0
        lea     keymap(pc),a0
        moveq   #0,d1
        move.b  d0,d1
        and.w   #$7f,d1
        lsr.w   #3,d1
        add.w   d1,a0
        move.b  d0,d1
        and.w   #7,d1
        tst.b   d0
        bmi.s   .up
        bset    d1,(a0)
        bra.s   .hs
.up:    bclr    d1,(a0)
.hs:    moveq   #3-1,d0                     ; 3 cambios de linea: >= 2
.l:     move.b  CUSTOM+VHPOSR,d1            ; lineas enteras (128 us)
.w:     cmp.b   CUSTOM+VHPOSR,d1
        beq.s   .w
        dbf     d0,.l
        and.b   #$bf,CIAA_CRA               ; SPMODE: entrada
.x:     move.w  #$0008,CUSTOM+INTREQ
        move.w  #$0008,CUSTOM+INTREQ
        movem.l (sp)+,d0-d1/a0
        rte

keymap: ds.b    16                          ; 128 teclas: 1 = apretada
g_dead: dc.w    0                           ; frames sin poder seguir
g_save: dc.l    0                           ; datos del C y mapa al cargar
        even
        endc

;----------------------------------------------------------------------
; --- loadstate --- a0 = estado del oraculo (576 bytes: $0000-$00FF y
; $13C0-$14FF). Como sync() de m68kverify.py: las tablas de SPR_KEEP
; quedan como estaban (los sprites son del port).
; registros destruidos: d0-d1/a0-a1
;----------------------------------------------------------------------
loadstate:
        movem.l d2/a2-a3,-(sp)
        GETBASE a2
        add.l   #_ram-binstart,a2           ; a2 = ram
        lea     spr_keep(pc),a1             ; guardar las tablas
        lea     keepbuf(pc),a3
        moveq   #SPR_KEEPN-1,d1
.k1:    move.w  (a1)+,d0
        moveq   #12-1,d2
.k1b:   move.b  (a2,d0.w),(a3)+
        addq.w  #1,d0
        dbf     d2,.k1b
        dbf     d1,.k1
        move.l  a2,a1                       ; el estado
        moveq   #256/4-1,d0
.dp:    move.l  (a0)+,(a1)+
        dbf     d0,.dp
        lea     $13C0(a2),a1
        moveq   #320/4-1,d0
.w13:   move.l  (a0)+,(a1)+
        dbf     d0,.w13
        lea     spr_keep(pc),a1             ; y las tablas de vuelta
        lea     keepbuf(pc),a3
        moveq   #SPR_KEEPN-1,d1
.k2:    move.w  (a1)+,d0
        moveq   #12-1,d2
.k2b:   move.b  (a3)+,(a2,d0.w)
        addq.w  #1,d0
        dbf     d2,.k2b
        dbf     d1,.k2
        move.b  #$07,$1931(a2)              ; wm_LvHeadTileset (no se graba)
        move.b  spr_lv(pc),d0               ; wm_SpriteMemory
        and.b   #$3f,d0
        move.b  d0,$1692(a2)
        move.b  #$ff,$1430(a2)              ; Lowest/HighestSolidSprTile
        move.b  #$ff,$1431(a2)
        movem.l (sp)+,d2/a2-a3
        rts

spr_keep:                                   ; m68kverify.py SPR_KEEP
        dc.w    $14C8,$009E,$00E4,$14E0,$00D8,$14D4,$00B6,$00AA,$00C2,$14F8,$14EC
keepbuf: ds.b   SPR_KEEPN*12
        even

;----------------------------------------------------------------------
; --- callframe --- level_frame (camara, graficos, jugador, sprites,
; bloques) con a4 = binstart. Guarda todos los registros.
;----------------------------------------------------------------------
callframe:
        movem.l d0-d7/a0-a6,-(sp)
        GETBASE a4
        move.l  a4,a0
        add.l   #_level_frame-binstart,a0
        jsr     (a0)
        movem.l (sp)+,d0-d7/a0-a6
        rts

;----------------------------------------------------------------------
; --- mario_draw --- Mario (6b.4) en la lista que se escribe este frame
; (V_BACK): mario_sprite (mspr.c) arma las dos parejas de sprites en el
; buffer de esa lista; aca van sus punteros (SPR0-3; SPR4-7 al nulo) y la
; paleta (mario_pal -> COLOR17-31) en la cabecera de la lista.
; registros destruidos: d0-d1/a0-a1
;----------------------------------------------------------------------
mario_draw:
        movem.l d2-d7/a2-a6,-(sp)
        move.l  V_BACK(a5),a2
        move.l  g_spra(pc),d2
        cmp.l   V_COP(a5),a2
        beq.s   .a
        move.l  g_sprb(pc),d2
.a:     GETBASE a4
        movem.l d2/a2,-(sp)                 ; (mspr_draw destruye d2)
        move.l  d2,a2                       ; = mario_sprite(d2, $2C, $A0)
        bsr     mspr_draw
        movem.l (sp)+,d2/a2
        GETBASE a4
        lea     CL_SPR+2(a2),a0
        moveq   #4-1,d1
.p:     swap    d2
        move.w  d2,(a0)
        swap    d2
        move.w  d2,4(a0)
        addq.l  #8,a0
        add.l   #MSPR_WORDS*2,d2
        dbf     d1,.p
        move.l  g_null(pc),d2
        moveq   #4-1,d1
.q:     swap    d2
        move.w  d2,(a0)
        swap    d2
        move.w  d2,4(a0)
        addq.l  #8,a0
        dbf     d1,.q
        moveq   #0,d0                       ; paleta
        move.b  _mario_pal(a4),d0
        and.w   #7,d0
        lsl.w   #5,d0
        move.l  a4,a1
        add.l   #mario_pals+2-binstart,a1   ; (sin COLOR16)
        add.w   d0,a1
        lea     CL_COL17+2(a2),a0
        moveq   #15-1,d1
.c:     move.w  (a1)+,(a0)
        addq.l  #4,a0
        dbf     d1,.c
        movem.l (sp)+,d2-d7/a2-a6
        rts

g_spra: dc.l    0                           ; sprites de Mario (lista A)
g_sprb: dc.l    0                           ; (lista B)
g_null: dc.l    0                           ; sprite vacio

gfail:  lea     CUSTOM,a4
.f:     move.w  #$0f00,COLOR00(a4)
        bra.s   .f

old_base:
        dc.l    0                           ; lo pone entry (a0 de boot.s)
gfxname: dc.b   "graphics.library",0
        even
vars:   ds.b    V_SIZE
        even

;----------------------------------------------------------------------
; Datos (el C los lee por puntero)
;----------------------------------------------------------------------
map16:  incbin  "work/yi1_map16.bin"
        even
spr_lv: incbin  "work/cc/spr.lv"
        even
mario_pals:
        incbin  "work/cc/mario_pal.bin"     ; tools/mkmario.py
gfx32:  incbin  "work/cc/gfx32.bin"
gfx32f: incbin  "work/cc/gfx32f.bin"        ; con los bits al reves (volteo)
        even
        cnop    0,4
replay: incbin  "work/yi1_replay.bin"       ; en vivo: solo el primer estado
        cnop    0,4
binend:
