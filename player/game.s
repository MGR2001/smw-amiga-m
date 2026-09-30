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
; En vivo (sin -DREPLAY): teclado + joystick -> $15-$18 como el
; ControllerUpdate de SMW (P55) -> level_frame. Cuando el port no puede
; seguir (mario_unsupported, la muerte, el dano con Mario chico) la
; pantalla se congela en MODO DIAGNOSTICO (P58): debajo del juego, una
; franja con el motivo, la X/Y de Mario, el frame...; ESPACIO cambia a la
; pagina del historial (el joypad desde el principio del nivel, en bits:
; tools/diag_read.py lo lee de una captura y reproduce la partida en el
; PC); RETURN (Start), Z o el boton del joystick vuelven a empezar el nivel.
;   -DDIAGSECS=n: tambien vuelve a empezar solo a los n segundos
;   -DDIAGPAGE=2: entra directamente en la pagina del historial
;   -DPADTEST:    en vivo, pero el joypad es el grabado del replay (para
;                 probar el modo diagnostico sin teclado)
;   -DREPLAY -DDIAGTEST=n: el replay entra en el modo diagnostico en su
;                 frame n (0: en el primero en que el port no puede seguir)
;
;   sh tools/game_build.sh                           (-> work/game.adf)
;   GDEFS=" " OUT=work/live sh tools/game_build.sh   (-> en vivo)
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
build_end:                                  ; fin de lo que firma g_build

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

;--- modo diagnostico (P58) ---------------------------------------------
        ifnd    REPLAY
DIAG        equ 1                           ; en vivo, siempre
        else
        ifd     DIAGTEST
DIAG        equ 1                           ; replay: solo para probarlo
        endc
        endc
        ifnd    DIAGSECS
DIAGSECS    equ 0                           ; 0: solo con una tecla
        endc
        ifnd    DIAGPAGE
DIAGPAGE    equ 1                           ; 1 = juego + franja, 2 = historial
        endc
; motivos (el byte alto de DI_MOT): 1..10 = mario_unsupported (MARIO_UNSUP_*)
MOT_DANO    equ $10                         ; dano con Mario chico (MEV_HURT)
MOT_MUERTE  equ $11                         ; kill_mario (MEV_DEATH: foso, aplastado)
MOT_ANIM    equ $12                         ; wm_MarioAnimation ($71) sin portar
MOT_PRUEBA  equ $ff                         ; -DDIAGTEST=n en un frame sin motivo
; cola de la lista del juego en el modo diagnostico: la franja de 32 lineas
; debajo de las 224 del juego (ver diag_enter)
CL_TAIL     equ 64                          ; bytes de mas en cada lista
CL_END      equ CL_SIZE-4                   ; donde estaba el $FFFFFFFE
DIWE_DIAG   equ $2ca1                       ; DIWSTOP: hasta la linea $12C
; memoria de chip del diagnostico (una sola reserva)
DG_PAGEB    equ 40                          ; pagina 2: 320 x 256, 1 plano
DG_STRIPB   equ FETCHW*2                    ; franja: 17 palabras por linea
DG_PAGE     equ 0
DG_STRIP    equ DG_PAGEB*256                ; 32 lineas
DG_ONES     equ DG_STRIP+DG_STRIPB*32       ; una linea de $FF (plano 2)
DG_COP      equ DG_ONES+40                  ; lista del copper de la pagina 2
DG_SIZE     equ DG_COP+160
; rejilla de la pagina 2: celdas de 2x2 px, 160 por fila, lineas 32..251
DG_GLINE    equ 32
DG_GROWS    equ 110
DG_GWORDS   equ DG_GROWS*10                 ; palabras de 16 bits en la rejilla
DG_HDR      equ 18                          ; palabras de la cabecera (dg_info)
HISTMAX     equ DG_GWORDS-DG_HDR            ; entradas del historial que caben
; cabecera (dg_info; tools/diag_read.py): palabras de 16 bits
DI_MAGIC    equ 0                           ; $D1A6
DI_VER      equ 2                           ; version << 8 | flags
DI_FRAME    equ 4                           ; frame (bajo; 1 = el primero)
DI_MOT      equ 6                           ; motivo << 8 | mario_unsupported
DI_EV       equ 8                           ; mario_events (bajo)
DI_X        equ 10                          ; $94-$95
DI_Y        equ 12                          ; $96-$97
DI_A71      equ 14                          ; $71 << 8 | $19
DI_SPD      equ 16                          ; $7B << 8 | $7D
DI_BODY     equ 18                          ; Map16 en (X+8, Y+$18)
DI_FOOT     equ 20                          ; Map16 en (X+8, Y+$20)
DI_PAD0     equ 22                          ; copias del joypad al empezar
DI_CAM      equ 24                          ; $1A-$1B
DI_T        equ 26                          ; $72 << 8 | $1693 (ultimo bloque)
DI_N        equ 28                          ; entradas del historial
DI_BUILD    equ 30                          ; firma del binario (g_build)
DI_FRAMEH   equ 32                          ; frame (alto)
DI_SUM      equ 34                          ; suma de control
DF_OVER     equ 0                           ; flags: el historial se lleno
DF_REPLAY   equ 1                           ;        binario -DREPLAY

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
        bsr     build_sign                  ; antes de que corra nada
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
        move.l  #CL_SIZE+CL_TAIL,d0         ; (+ la cola del diagnostico)
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     gfail
        move.l  d0,V_COP(a5)
        move.l  #CL_SIZE+CL_TAIL,d0
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
        ifd     DIAG
        move.l  #DG_SIZE,d0                 ; las pantallas del diagnostico
        move.l  #MEMF_CHIP|MEMF_CLEAR,d1
        jsr     _LVOAllocMem(a6)
        tst.l   d0
        beq     gfail
        lea     g_dmem(pc),a0
        move.l  d0,(a0)
        endc

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
        ifd     DIAG
        move.w  g_diag(pc),d0
        bne.s   .dg                         ; congelado: solo el diagnostico
        endc
        bsr     game_step
        bsr     cam_to_s
        bsr     mario_draw
        bsr     scroll_frame
        ifd     DIAG
        move.w  g_diag(pc),d0               ; game_step no pudo seguir: la
        beq.s   .w2                         ; imagen de ese frame queda
        bsr     diag_enter                  ; congelada, con la franja
        endc
.w2:    move.l  VPOSR(a4),d0                ; esperar a que empiece otro frame
        lsr.l   #8,d0
        and.w   #$1ff,d0
        cmp.w   #$110,d0
        bhs.s   .w2
        bra.s   gframe
        ifd     DIAG
.dg:    bsr     diag_frame
        bra.s   .w2
        endc

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
        ifd     DIAG
        lea     g_frame(pc),a0              ; frame del replay (0 = el primero)
        addq.l  #1,(a0)
        endc
        lea     g_left(pc),a0
        tst.w   (a0)
        beq     .done                       ; fin del replay: quieto
        subq.w  #1,(a0)
        move.l  g_op(pc),a1
        lea     g_op(pc),a0
        addq.l  #6,(a0)
        ifd     DIAG
        movem.l d2-d4/a1,-(sp)              ; el historial: el joypad del op
        move.b  2(a1),d0
        move.b  4(a1),d1
        and.b   #$f0,d1
        bsr     hist_record
        movem.l (sp)+,d2-d4/a1
        endc
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
        ifd     DIAGTEST
        bsr     diag_test                   ; (no toca d0 de la pila)
        move.w  g_diag(pc),d0
        beq.s   .nt
        addq.l  #4,sp                       ; congelado: sin resincronizar
        bra.s   .done
.nt:
        endc
        move.l  (sp)+,d0
        cmp.b   #OP_RUNSYNC,d0
        bne.s   .done
.sync:  move.l  g_sts(pc),a0
        lea     g_sts(pc),a1
        add.l   #576,(a1)
        bra     loadstate
.done:  rts

        ifd     DIAGTEST
; diag_test: -DDIAGTEST=n: el modo diagnostico en el frame n del replay
; (0: en el primero en que el port no puede seguir; ver diag_cause)
diag_test:
        movem.l d2-d3/a2,-(sp)
        bsr     diag_cause
        ifne    DIAGTEST
        move.l  g_frame(pc),d1
        cmp.l   #DIAGTEST,d1
        bne.s   .no
        tst.b   d0
        bne.s   .t
        moveq   #-1,d0                      ; MOT_PRUEBA
        else
        tst.b   d0
        beq.s   .no
        endc
.t:     bsr     diag_trigger
.no:    movem.l (sp)+,d2-d3/a2
        rts
        endc
        endc                                ; REPLAY

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
        ifd     DIAG
        bsr     hist_reset                  ; el historial empieza aca
        endc
        movem.l (sp)+,d2/a2
        rts

g_left: dc.w    0                           ; frames que faltan
g_op:   dc.l    0                           ; siguiente op
g_sts:  dc.l    0                           ; siguiente estado

        ifnd    REPLAY
;----------------------------------------------------------------------
; En vivo (6b.3): teclado y joystick -> $15-$18 -> level_frame. Lo que el
; port no tiene (animaciones de Mario, tuberias, meta...) congela el frame
; en el modo diagnostico (P58). El dano (MEV_HURT) se resuelve aca, sin la
; animacion: grande -> chico con el tiempo de invulnerabilidad; chico ->
; diagnostico (MOT_DANO).
;----------------------------------------------------------------------

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
        bsr     replay_init                 ; wm_SprLoadStatus, g_sts, historial
; live_start: el estado del primer frame de la partida (lo llama tambien
; tools/diag_read.py --repro, despues de replay_init)
live_start:
        move.l  g_sts(pc),a0                ; el primer estado (SYNC)
        bra     loadstate

game_step:
        movem.l d2-d5/a2,-(sp)
        bsr     read_input                  ; d0 = JOY1H, d1 = JOY1L
        ifd     PADTEST
        bsr     pad_synth
        endc
        bsr     live_logic
        tst.b   d0
        beq.s   .x
        bsr     diag_trigger                ; congelar (diag_enter, en el bucle)
.x:     movem.l (sp)+,d2-d5/a2
        rts

;----------------------------------------------------------------------
; --- live_logic --- un frame de juego en vivo, sin tocar el hardware (lo
; llama tambien tools/diag_read.py --repro, con el historial)
; entrada:  d0.b = byetUDLR, d1.b = axlr---- (lo que da read_input)
; salida:   d0.l = motivo para congelar (0 = sigue; ver diag_cause)
; registros destruidos: d0-d1/a0-a1
;----------------------------------------------------------------------
live_logic:
        movem.l d2-d4/a2,-(sp)
        lea     g_frame(pc),a0
        addq.l  #1,(a0)                     ; 1 = el primer frame jugado
        and.b   #$f0,d1
        bsr     hist_record
        bsr     pad_convert
        GETBASE a2
        clr.l   _mario_events(a2)
        bsr     callframe
        bsr     diag_cause                  ; d0 = motivo
        btst    #4,_mario_events+3(a2)      ; MEV_HURT (HurtMario) con Mario
        beq.s   .x                          ; grande: chico, sin la animacion
        move.l  a2,a0
        add.l   #_ram-binstart,a0
        tst.b   $19(a0)                     ; wm_MarioPowerUp
        beq.s   .x
        clr.b   $19(a0)
        move.b  #$7f,$1497(a0)              ; wm_PlayerHurtTimer
.x:     movem.l (sp)+,d2-d4/a2
        rts

;----------------------------------------------------------------------
; --- pad_convert --- $15-$18 como ControllerUpdate (game.s:708 de SMW)
; entrada:  d0.b = byetUDLR (JOY1H), d1.b = axlr0000 (JOY1L & $F0)
;   $15 = (JOY1L & $C0) | JOY1H     (A cuenta como B, X como Y)
;   $16 = recien apretado de JOY1H | (el de JOY1L & $40)
;   $17 = JOY1L                      $18 = recien apretado de JOY1L
; "Recien apretado" es contra una copia PROPIA del frame anterior
; (g_pada/g_padb = wm_JoyDisP1L/H), no contra $15/$17, que el juego
; borra a veces (P55: no_buttons() con la tecla apretada daba otro salto).
; registros destruidos: d2-d4/a0-a1 (d0/d1 quedan)
;----------------------------------------------------------------------
pad_convert:
        lea     g_pada(pc),a1
        move.b  (a1),d2                     ; JOY1H del frame anterior
        not.b   d2
        and.b   d0,d2                       ; d2 = recien apretado (JOY1H)
        move.b  d0,(a1)+
        move.b  (a1),d3                     ; JOY1L del frame anterior
        not.b   d3
        and.b   d1,d3                       ; d3 = recien apretado (JOY1L)
        move.b  d1,(a1)
        GETBASE a0
        add.l   #_ram+$15-binstart,a0
        move.b  d1,d4
        and.b   #$c0,d4
        or.b    d0,d4
        move.b  d4,(a0)+                    ; $15
        move.b  d3,d4
        and.b   #$40,d4
        or.b    d2,d4
        move.b  d4,(a0)+                    ; $16
        move.b  d1,(a0)+                    ; $17
        move.b  d3,(a0)                     ; $18
        rts

        ifd     PADTEST
; pad_synth: -DPADTEST: el joypad del frame que viene (g_frame + 1) es el
; del op de ese frame en el replay ($15 y $17 grabados), 0 despues
pad_synth:
        move.l  g_frame(pc),d2
        addq.l  #1,d2
        GETBASE a0
        add.l   #replay-binstart,a0
        moveq   #0,d0
        moveq   #0,d1
        cmp.w   4(a0),d2                    ; frames del replay
        bhs.s   .x
        move.l  a0,a1
        add.l   12(a0),a1                   ; ops
        mulu    #6,d2
        add.l   d2,a1
        move.b  2(a1),d0
        move.b  4(a1),d1
.x:     rts
        endc

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
        btst    d2,(a0,d5.w)                ; P40 ok (0..15)
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
.j4:    lea     g_fire(pc),a0               ; boton 1 (0 = apretado): al
        btst    #7,CIAA_PRA                 ; apretarlo, con arriba = A (giro),
        beq.s   .f1                         ; si no B (salto); y sigue siendo
        clr.b   (a0)                        ; lo mismo mientras no se suelte
        bra.s   .j5                         ; (si no, soltar arriba con el boton
.f1:    move.b  (a0),d4                     ; apretado era un B nuevo: otro
        bne.s   .f2                         ; salto)
        moveq   #1,d4                       ; 1 = B
        btst    #8,d3
        beq.s   .f3
        moveq   #2,d4                       ; 2 = A
.f3:    move.b  d4,(a0)
.f2:    cmp.b   #2,d4
        bne.s   .jb
        bset    #7,d1                       ; A (giro)
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
KEY_SPACE   equ $40                         ; diagnostico: cambiar de pagina

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
g_fire: dc.b    0                           ; boton 1 del joystick: 0, 1 = B, 2 = A
        even
g_save: dc.l    0                           ; datos del C y mapa al cargar
        even
        endc                                ; ifnd REPLAY

g_pada: dc.b    0                           ; JOY1H del frame anterior (wm_JoyDisP1L)
g_padb: dc.b    0                           ; JOY1L del frame anterior (wm_JoyDisP1H)
        even

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
.k1b:   move.b  (a2,d0.w),(a3)+             ; P40 ok (< $1500)
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
.k2b:   move.b  (a3)+,(a2,d0.w)             ; P40 ok (< $1500)
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

;----------------------------------------------------------------------
; --- build_sign --- g_build = firma de 16 bits del binario (datos del C
; y codigo del C y de las bibliotecas, cdata0..build_end, como estan en
; game.bin): tools/diag_read.py --repro comprueba con ella que reproduce
; con el mismo binario. Se calcula al arrancar, antes de que cambie nada.
; registros destruidos: d0-d1/a0
;----------------------------------------------------------------------
build_sign:
        move.l  d2,-(sp)
        GETBASE a0
        add.l   #cdata0-binstart,a0
        move.l  #(build_end-cdata0)/2-1,d1
        moveq   #0,d0
.l:     rol.w   #1,d0
        move.w  (a0)+,d2
        eor.w   d2,d0
        subq.l  #1,d1
        bpl.s   .l
        lea     g_build(pc),a0
        move.w  d0,(a0)
        move.l  (sp)+,d2
        rts

g_build: dc.w   0

        ifd     DIAG
;----------------------------------------------------------------------
; Modo diagnostico (P58)
;
; Pantalla 1 (la de entrada): la imagen del juego del frame en que el port
; no pudo seguir, congelada, y debajo (lineas $10C-$12B, que el juego no
; usa) una franja de 32 lineas con el texto. La franja la pone una cola en
; la lista del copper que se esta viendo: DIWSTOP hasta $12C y, al final de
; la ultima linea del juego, 2 planos (el 1 = texto, el 2 = una linea de
; $FF repetida con BPL2MOD negativo), BPLCON2 = 0 (el campo de juego tapa
; a los sprites: todos sus pixeles son de color 2 o 3). No toca el buffer
; circular de PF1 ni los colores de Mario (los sprites 4-7 compartirian
; COLOR25-31 con las parejas adosadas de Mario, P32), y se lee en blanco
; sobre negro.
;
; Pantalla 2 (ESPACIO): 320 x 256, 1 plano, otra lista del copper (sin
; sprites). Barras blancas arriba (lineas 0-3) y abajo (252-255) para
; encontrar la escala en la captura, 3 filas de texto (8-31) y la rejilla:
; celdas de 2x2 px, 160 por fila, filas en las lineas 32-251; bit 15
; primero. Contiene dg_info (DG_HDR palabras) y el historial del joypad.
;
; Historial: una entrada de 16 bits por cada bit que cambia (b << 12 | d):
; b = 0..11 (bits 11-4 = byetUDLR, 3-0 = axlr), d = frames desde la
; entrada anterior (0..4095); b = 15: solo pasa el tiempo (d = 4095). El
; estado de partida (frame 0) es 0.
;----------------------------------------------------------------------

; --- hist_reset --- el historial y el frame empiezan (principio del nivel)
; registros destruidos: d0/a0
hist_reset:
        lea     g_frame(pc),a0
        ifd     REPLAY
        move.l  #-1,(a0)                    ; el primer game_step (SYNC) = 0
        else
        clr.l   (a0)
        endc
        lea     h_last(pc),a0
        clr.w   (a0)+                       ; h_last
        clr.l   (a0)+                       ; h_t
        clr.w   (a0)+                       ; h_n
        clr.w   (a0)+                       ; h_flags
        move.b  g_pada(pc),(a0)+            ; h_pa0, h_pb0: las copias de
        move.b  g_padb(pc),(a0)             ; pad_convert al empezar
        rts

; --- hist_record --- el joypad del frame g_frame (>= 1) al historial
; entrada:  d0.b = byetUDLR, d1.b = axlr0000
; registros destruidos: d2-d4/a0 (d0/d1 quedan)
hist_record:
        move.l  g_frame(pc),d4
        ble.s   .x                          ; frame 0: el estado de partida
        moveq   #0,d2
        move.b  d0,d2
        lsl.w   #4,d2
        moveq   #0,d3
        move.b  d1,d3
        lsr.b   #4,d3
        or.w    d3,d2                       ; d2 = estado (12 bits)
        lea     h_last(pc),a0
        move.w  (a0),d3
        eor.w   d2,d3                       ; bits que cambian
        beq.s   .x
        move.w  d2,(a0)
        movem.l d0-d1/d5,-(sp)
.long:  move.l  d4,d0                       ; mas de 4095 frames sin cambios:
        sub.l   h_t(pc),d0                  ; marcas de tiempo
        cmp.l   #$fff,d0
        bls.s   .bits
        move.w  #$ffff,d0
        bsr.s   .emit
        lea     h_t(pc),a0
        add.l   #$fff,(a0)
        bra.s   .long
.bits:  moveq   #0,d5                       ; b
.b:     btst    d5,d3
        beq.s   .nb
        move.l  d4,d0
        sub.l   h_t(pc),d0
        move.w  d5,d1
        ror.w   #4,d1                       ; b << 12
        or.w    d1,d0
        bsr.s   .emit
        lea     h_t(pc),a0
        move.l  d4,(a0)
.nb:    addq.w  #1,d5
        cmp.w   #12,d5
        blo.s   .b
        movem.l (sp)+,d0-d1/d5
.x:     rts
.emit:  lea     h_n(pc),a0                  ; d0.w = entrada
        move.w  (a0),d1
        cmp.w   #HISTMAX,d1
        bhs.s   .full
        addq.w  #1,(a0)
        add.w   d1,d1
        lea     hist(pc),a0
        move.w  d0,(a0,d1.w)                ; P40 ok (< 2*HISTMAX)
        rts
.full:  lea     h_flags(pc),a0
        bset    #DF_OVER,1(a0)
        rts

; --- diag_cause --- por que el port no puede seguir despues de este
; level_frame (solo mira: el dano con Mario grande lo resuelve live_logic)
; salida:   d0.l = 0 (sigue), MOT_DANO (MEV_HURT con Mario chico), 1..10
;           (mario_unsupported), MOT_MUERTE (MEV_DEATH) o MOT_ANIM ($71)
; registros destruidos: d0/a0-a1
diag_cause:
        GETBASE a1
        move.l  a1,a0
        add.l   #_ram-binstart,a0
        btst    #4,_mario_events+3(a1)      ; MEV_HURT
        beq.s   .nh
        tst.b   $19(a0)                     ; chico: se muere
        bne.s   .nh
        moveq   #MOT_DANO,d0
        rts
.nh:    move.l  _mario_unsupported(a1),d0
        bne.s   .x
        btst    #3,_mario_events+3(a1)      ; MEV_DEATH
        beq.s   .na
        moveq   #MOT_MUERTE,d0
        rts
.na:    tst.b   $71(a0)                     ; wm_MarioAnimation
        beq.s   .x
        moveq   #MOT_ANIM,d0
.x:     rts

; --- diag_trigger --- congelar: g_diag y la foto del estado (dg_info)
; entrada:  d0.b = motivo
; registros destruidos: d0-d1/a0-a1
diag_trigger:
        movem.l d2/a2-a3,-(sp)
        lea     g_diag(pc),a0
        move.w  #DIAGPAGE,(a0)
        lea     dg_info(pc),a3
        GETBASE a2                          ; a2 = binstart, a1 = ram
        move.l  a2,a1
        add.l   #_ram-binstart,a1
        lsl.w   #8,d0
        move.b  _mario_unsupported+3(a2),d0
        move.w  d0,DI_MOT(a3)
        move.w  #$d1a6,DI_MAGIC(a3)
        move.w  h_flags(pc),d0
        ifd     REPLAY
        bset    #DF_REPLAY,d0
        endc
        or.w    #$0100,d0                   ; version 1
        move.w  d0,DI_VER(a3)
        move.w  g_frame+2(pc),DI_FRAME(a3)
        move.w  g_frame(pc),DI_FRAMEH(a3)
        move.w  _mario_events+2(a2),DI_EV(a3)
        move.b  $95(a1),d0                  ; X, Y (little-endian en ram[])
        lsl.w   #8,d0
        move.b  $94(a1),d0
        move.w  d0,DI_X(a3)
        move.b  $97(a1),d1
        lsl.w   #8,d1
        move.b  $96(a1),d1
        move.w  d1,DI_Y(a3)
        movem.w d0-d1,-(sp)
        addq.w  #8,d0                       ; Map16 bajo Mario
        add.w   #$18,d1
        bsr     m16_at
        move.w  d2,DI_BODY(a3)
        movem.w (sp)+,d0-d1
        addq.w  #8,d0
        add.w   #$20,d1
        bsr     m16_at
        move.w  d2,DI_FOOT(a3)
        move.b  $71(a1),d0
        lsl.w   #8,d0
        move.b  $19(a1),d0
        move.w  d0,DI_A71(a3)
        move.b  $7B(a1),d0
        lsl.w   #8,d0
        move.b  $7D(a1),d0
        move.w  d0,DI_SPD(a3)
        move.b  $1B(a1),d0
        lsl.w   #8,d0
        move.b  $1A(a1),d0
        move.w  d0,DI_CAM(a3)
        move.b  $72(a1),d0
        lsl.w   #8,d0
        move.b  $1693(a1),d0                ; wm_Map16NumLo
        move.w  d0,DI_T(a3)
        move.b  h_pa0(pc),d0
        lsl.w   #8,d0
        move.b  h_pb0(pc),d0
        move.w  d0,DI_PAD0(a3)
        move.w  h_n(pc),DI_N(a3)
        move.w  g_build(pc),DI_BUILD(a3)
        movem.l (sp)+,d2/a2-a3
        rts

; --- m16_at --- el indice Map16 (9 bits) de la capa 1 en (x, y) del nivel
; entrada:  d0.w = x, d1.w = y (fuera del nivel: $FFFF)
; salida:   d2.w = indice
; registros destruidos: d0-d2/a0
m16_at:
        moveq   #-1,d2
        cmp.w   #$1b0,d1                    ; 27 filas (sin signo: y < 0 fuera)
        bhs.s   .x
        cmp.w   #20*256,d0
        bhs.s   .x
        moveq   #0,d2
        move.w  d0,d2
        lsr.w   #8,d2
        mulu    #$1b0,d2                    ; pantalla
        and.w   #$1f0,d1
        add.w   d1,d2                       ; fila * 16
        lsr.w   #4,d0
        and.w   #15,d0
        add.w   d0,d2                       ; columna
        GETBASE a0
        add.l   #map16-binstart,a0
        add.l   d2,a0
        moveq   #0,d2
        move.b  MAPHALF(a0),d2
        lsl.w   #8,d2
        move.b  (a0),d2
.x:     rts

; --- diag_enter --- (bucle, despues de scroll_frame del frame congelado)
; la franja en la lista que se ve y las dos pantallas dibujadas
diag_enter:
        movem.l d2-d7/a2-a6,-(sp)
        move.l  V_COP(a5),d0                ; la lista que se ve desde el
        cmp.l   V_BACK(a5),d0               ; frame siguiente: la que no es
        bne.s   .l                          ; V_BACK
        move.l  V_COP2(a5),d0
.l:     lea     g_dlist(pc),a0
        move.l  d0,(a0)
        bsr     diag_render
        move.l  g_dlist(pc),a0
        move.w  #DIWE_DIAG,6(a0)            ; DIWSTOP (build_copper: 2.a palabra)
        add.l   #CL_END,a0
        lea     diag_tail(pc),a1
        move.l  g_dmem(pc),d0
        add.l   #DG_STRIP,d0
        move.l  d0,d1
        add.l   #DG_ONES-DG_STRIP,d1
.t:     move.l  (a1)+,d2                    ; la cola, con los punteros
        cmp.l   #$00e00000,d2
        bne.s   .t1
        swap    d0
        move.w  d0,d2
        swap    d0
.t1:    cmp.l   #$00e20000,d2
        bne.s   .t2
        move.w  d0,d2
.t2:    cmp.l   #$00e40000,d2
        bne.s   .t3
        swap    d1
        move.w  d1,d2
        swap    d1
.t3:    cmp.l   #$00e60000,d2
        bne.s   .t4
        move.w  d1,d2
.t4:    move.l  d2,(a0)+
        cmp.l   #$fffffffe,d2
        bne.s   .t
        lea     g_dtime(pc),a0
        clr.w   (a0)+                       ; g_dtime
        move.b  #$ff,(a0)                   ; g_dprev: todo "apretado"
        ifeq    DIAGPAGE-2
        move.l  g_dmem(pc),d0
        add.l   #DG_COP,d0
        move.l  d0,COP1LC(a4)
        endc
        movem.l (sp)+,d2-d7/a2-a6
        rts

; la cola de la lista del juego en el modo diagnostico ($00E0-$00E6: los
; punteros, que pone diag_enter)
diag_tail:
        dc.w    ($10b&$ff)<<8|BLANKH|1,$fffe    ; fin de la ultima linea
        dc.w    $0100,$2200                 ; BPLCON0: 2 planos, sin DBLPF
        dc.w    $00e0,0,$00e2,0             ; BPL1PT = franja
        dc.w    $00e4,0,$00e6,0             ; BPL2PT = linea de $FF
        dc.w    $0108,0                     ; BPL1MOD
        dc.w    $010a,-DG_STRIPB            ; BPL2MOD: la misma linea
        dc.w    $0102,0                     ; BPLCON1
        dc.w    $0104,0                     ; BPLCON2: el campo tapa a los sprites
        dc.w    $0180,$000                  ; COLOR00 (borde)
        dc.w    $0184,$000                  ; COLOR02: fondo
        dc.w    $0186,$fff                  ; COLOR03: texto
        dc.w    $ffff,$fffe
DIAG_TAILSZ equ *-diag_tail
        ifgt    DIAG_TAILSZ+4-CL_TAIL
        fail    "la cola del diagnostico no entra en CL_TAIL"
        endc

; --- diag_exit --- (en vivo) la lista como estaba y el nivel otra vez
        ifnd    REPLAY
diag_exit:
        move.l  g_dlist(pc),a0
        move.w  #DIWE,6(a0)
        move.l  a0,COP1LC(a4)
        add.l   #CL_END,a0                  ; (> 32 KB)
        move.l  #$fffffffe,(a0)
        lea     g_diag(pc),a0
        clr.w   (a0)
        bra     live_restart
        endc

; --- diag_frame --- un frame congelado: teclas y tiempo
diag_frame:
        ifnd    REPLAY
        movem.l d2-d5/a2,-(sp)
        bsr     read_input                  ; d0 = byetUDLR, d1 = axlr----
        and.b   #$f0,d1
        lea     g_pada(pc),a0               ; las copias de pad_convert
        move.b  d0,(a0)+                    ; siguen al joypad (al volver, lo
        move.b  d1,(a0)                     ; apretado no es "nuevo")
        move.b  d0,d2                       ; teclas para el diagnostico:
        and.b   #$90,d2                     ; bit 7 = B o A, 4 = Start,
        move.b  d1,d3                       ; 0 = ESPACIO
        and.b   #$80,d3
        or.b    d3,d2
        lea     keymap+KEY_SPACE/8(pc),a0
        btst    #KEY_SPACE&7,(a0)
        beq.s   .ns
        bset    #0,d2
.ns:    lea     g_dprev(pc),a0
        move.b  (a0),d3
        move.b  d2,(a0)
        not.b   d3
        and.b   d2,d3                       ; d3 = recien apretadas
        lea     g_dtime(pc),a0
        addq.w  #1,(a0)
        btst    #0,d3                       ; ESPACIO: la otra pagina
        beq.s   .np
        lea     g_diag(pc),a0
        move.l  g_dlist(pc),d0
        eor.w   #3,(a0)                     ; 1 <-> 2
        cmp.w   #2,(a0)
        bne.s   .p1
        move.l  g_dmem(pc),d0
        add.l   #DG_COP,d0
.p1:    move.l  d0,COP1LC(a4)
.np:    move.w  g_dtime(pc),d0
        cmp.w   #50,d0                      ; 1 s antes de aceptar la salida
        blo.s   .x
        and.b   #$90,d3                     ; B/A o Start: otra vez
        bne.s   .go
        ifne    DIAGSECS
        cmp.w   #DIAGSECS*50,d0
        bhs.s   .go
        endc
.x:     movem.l (sp)+,d2-d5/a2
        rts
.go:    bsr     diag_exit
        bra.s   .x
        else
        rts                                 ; replay: se queda asi
        endc

; --- diag_render --- las dos pantallas desde dg_info y el historial
; registros destruidos: d0-d7/a0-a3
diag_render:
        lea     dg_info(pc),a3              ; la suma de control
        moveq   #0,d0
        moveq   #DI_SUM/2-1,d1
.s1:    rol.w   #1,d0
        move.w  (a3)+,d2
        eor.w   d2,d0
        dbf     d1,.s1
        lea     hist(pc),a0
        move.w  h_n(pc),d1
        bra.s   .s3
.s2:    rol.w   #1,d0
        move.w  (a0)+,d2
        eor.w   d2,d0
.s3:    dbf     d1,.s2
        lea     dg_info(pc),a3
        move.w  d0,DI_SUM(a3)

        ;--- pagina 2: barras, texto, rejilla --------------------------
        move.l  g_dmem(pc),a0
        move.w  #DG_PAGEB*4/4-1,d0
.b1:    move.l  #-1,(a0)+                   ; lineas 0-3
        dbf     d0,.b1
        move.l  g_dmem(pc),a0
        add.l   #DG_PAGEB*252,a0
        move.w  #DG_PAGEB*4/4-1,d0
.b2:    move.l  #-1,(a0)+                   ; lineas 252-255
        dbf     d0,.b2
        moveq   #DG_PAGEB,d2
        move.l  g_dmem(pc),a1
        add.l   #DG_PAGEB*8,a1
        lea     fmt_p2a(pc),a0
        lea     dg_info(pc),a3
        bsr     diag_args
        bsr     txt_fmt
        move.l  g_dmem(pc),a1
        add.l   #DG_PAGEB*16,a1
        lea     fmt_p2b(pc),a0
        bsr     txt_fmt
        move.l  g_dmem(pc),a1
        add.l   #DG_PAGEB*24,a1
        lea     fmt_p2c(pc),a0
        bsr     txt_fmt
        ; rejilla: dg_info y luego hist[0..h_n-1], el resto 0
        move.l  g_dmem(pc),a1
        add.l   #DG_PAGEB*DG_GLINE,a1
        lea     dg_info(pc),a0
        moveq   #0,d6                       ; palabras escritas
        move.w  h_n(pc),d7
        add.w   #DG_HDR,d7                  ; palabras con datos
.g:     cmp.w   #DG_HDR,d6
        bne.s   .g1
        lea     hist(pc),a0
.g1:    moveq   #0,d0
        cmp.w   d7,d6
        bhs.s   .g2
        move.w  (a0)+,d0
.g2:    moveq   #16-1,d4                    ; cada bit, 2 px
        moveq   #0,d3
.g3:    add.l   d3,d3
        add.l   d3,d3
        add.w   d0,d0
        bcc.s   .g4
        addq.l  #3,d3
.g4:    dbf     d4,.g3
        move.l  d3,(a1)
        move.l  d3,DG_PAGEB(a1)             ; la linea de abajo de la celda
        addq.l  #4,a1
        addq.w  #1,d6
        moveq   #0,d0
        move.w  d6,d0
        divu    #10,d0
        swap    d0
        tst.w   d0
        bne.s   .g5
        add.w   #DG_PAGEB,a1                ; fila siguiente (2 lineas)
.g5:    cmp.w   #DG_GWORDS,d6
        blo.s   .g

        ;--- la franja (pantalla 1) ------------------------------------
        move.l  g_dmem(pc),a0
        add.l   #DG_STRIP,a0
        lea     2(a0),a1                    ; la palabra 0 no se ve
        moveq   #DG_STRIPB-2-1,d0
.f1:    move.b  #$ff,DG_STRIPB*30(a1)       ; lineas 30-31
        move.b  #$ff,DG_STRIPB*31(a1)
        move.b  #$ff,DG_STRIPB(a1)          ; lineas 0-1
        move.b  #$ff,(a1)+
        dbf     d0,.f1
        move.l  g_dmem(pc),a1
        add.l   #DG_ONES,a1
        moveq   #DG_STRIPB-1,d0
.f2:    move.b  #$ff,(a1)+
        dbf     d0,.f2
        moveq   #DG_STRIPB,d2
        move.l  g_dmem(pc),a1
        add.l   #DG_STRIP+DG_STRIPB*3+2,a1
        lea     fmt_p1a(pc),a0
        lea     dg_info(pc),a3
        bsr     diag_args
        bsr     txt_fmt
        move.l  g_dmem(pc),a1
        add.l   #DG_STRIP+DG_STRIPB*11+2,a1
        lea     fmt_p1b(pc),a0
        bsr     txt_fmt
        move.l  g_dmem(pc),a1
        add.l   #DG_STRIP+DG_STRIPB*19+2,a1
        lea     fmt_p1c(pc),a0
        bsr     txt_fmt

        ;--- lista del copper de la pagina 2 ---------------------------
        move.l  g_dmem(pc),a0
        move.l  a0,d0                       ; DG_PAGE = 0
        add.l   #DG_COP,a0
        lea     dg_coph(pc),a1
.c1:    move.l  (a1)+,d1
        beq.s   .c2
        move.l  d1,(a0)+
        bra.s   .c1
.c2:    move.w  #$00e0,(a0)+
        swap    d0
        move.w  d0,(a0)+
        move.w  #$00e2,(a0)+
        swap    d0
        move.w  d0,(a0)+
        move.l  g_null(pc),d0
        move.w  #$0120,d1                   ; SPR0PTH..SPR7PTL: nulo
        moveq   #8-1,d2
.c3:    move.w  d1,(a0)+
        swap    d0
        move.w  d0,(a0)+
        swap    d0
        addq.w  #2,d1
        move.w  d1,(a0)+
        move.w  d0,(a0)+
        addq.w  #2,d1
        dbf     d2,.c3
        move.l  #$fffffffe,(a0)
        rts

dg_coph:                                    ; pagina 2: 320 x 256, 1 plano
        dc.w    $008e,$2c81,$0090,$2cc1     ; DIWSTRT, DIWSTOP
        dc.w    $0092,$0038,$0094,$00d0     ; DDFSTRT, DDFSTOP
        dc.w    $0100,$1200,$0102,0         ; BPLCON0, BPLCON1
        dc.w    $0104,0,$0108,0             ; BPLCON2, BPL1MOD
        dc.w    $0180,$000,$0182,$fff       ; negro, blanco
        dc.l    0

; --- diag_args --- los argumentos de los formatos (dg_args) desde dg_info
; entrada:  a3 = dg_info
; salida:   a2 = dg_args
; registros destruidos: d0/a2
diag_args:
        lea     dg_args(pc),a2
        move.w  DI_MOT(a3),d0
        lsr.w   #8,d0
        move.w  d0,(a2)+                    ; 0 motivo
        move.w  d0,(a2)+                    ; 1 motivo (nombre)
        move.w  DI_FRAME(a3),(a2)+          ; 2
        move.w  DI_N(a3),(a2)+              ; 3
        move.w  DI_X(a3),(a2)+              ; 4
        move.w  DI_Y(a3),(a2)+              ; 5
        move.w  DI_SPD(a3),d0
        lsr.w   #8,d0
        move.w  d0,(a2)+                    ; 6 $7B
        move.w  DI_SPD(a3),(a2)+            ; 7 $7D
        move.w  DI_A71(a3),d0
        lsr.w   #8,d0
        move.w  d0,(a2)+                    ; 8 $71
        move.w  DI_A71(a3),(a2)+            ; 9 $19
        move.w  DI_FOOT(a3),(a2)+           ; 10
        move.w  DI_BODY(a3),(a2)+           ; 11
        move.w  DI_T(a3),(a2)+              ; 12 $1693
        move.w  DI_EV(a3),(a2)+             ; 13
        move.w  DI_CAM(a3),(a2)+            ; 14
        lea     dg_args(pc),a2
        rts

; formatos: $01 = byte en 2 hex, $02 = palabra en 4 hex, $03 = nombre del
; motivo en 6, $04 = saltar un argumento; toman el argumento siguiente de
; dg_args (en el orden de diag_args). La pantalla 1 tiene 32 columnas, la
; 2 tiene 40 (tools/diag_read.py lee estas mismas filas).
fmt_p1a: dc.b   "MOTIVO ",1," ",3,"  FRAME ",2,0               ; args 0-2
fmt_p1b: dc.b   4,"X ",2," Y ",2,4,4," A71 ",1,4," PIE ",2,0   ; 3-10
fmt_p1c: dc.b   "RETURN SEGUIR  ESPACIO HISTORIAL",0
fmt_p2a: dc.b   "MOTIVO ",1," ",3,"  FRAME ",2,"  HIST ",2,0   ; 0-3
fmt_p2b: dc.b   "X ",2," Y ",2," VX ",1," VY ",1," A71 ",1," P19 ",1,0   ; 4-9
fmt_p2c: dc.b   "PIE ",2," CUERPO ",2," T ",1," EV ",2," C ",2,0  ; 10-14
        even

; nombres de los motivos (6 caracteres)
mot_names:
        dc.b    1,"CAPE  ",2,"FIRE  ",3,"YOSHI ",4,"LAYER ",5,"TILE  "
        dc.b    6,"HURT  ",7,"PIPE  ",8,"WATER ",9,"CLIMB ",10,"WALL  "
        dc.b    MOT_DANO,"DANO  ",MOT_MUERTE,"MUERTE",MOT_ANIM,"ANIM  "
        dc.b    MOT_PRUEBA,"PRUEBA",0,"?     "
        even
hexdig: dc.b    "0123456789ABCDEF"

; --- txt_fmt --- una fila de texto (diagfont.i) en un mapa de bits
; entrada:  a0 = formato, a1 = primer byte de la fila, a2 = argumentos,
;           d2.w = bytes por linea
; salida:   a2 = despues del ultimo argumento usado
; registros destruidos: d0-d1/d3-d4/a0-a1/a3
txt_fmt:
.n:     moveq   #0,d0
        move.b  (a0)+,d0
        beq.s   .x
        cmp.b   #4,d0
        bhi.s   .c
        beq.s   .skip
        move.w  (a2)+,d3                    ; el argumento
        cmp.b   #3,d0
        beq.s   .nm
        moveq   #4-1,d4                     ; 4 cifras
        cmp.b   #1,d0
        bne.s   .h
        lsl.w   #8,d3
        moveq   #2-1,d4                     ; 2 cifras
.h:     rol.w   #4,d3
        move.w  d3,d0
        and.w   #15,d0
        lea     hexdig(pc),a3
        move.b  (a3,d0.w),d0                ; P40 ok (0..15)
        bsr.s   txt_ch
        dbf     d4,.h
        bra.s   .n
.skip:  addq.l  #2,a2
        bra.s   .n
.nm:    lea     mot_names(pc),a3            ; motivo -> nombre
.m:     move.b  (a3)+,d0
        beq.s   .m1                         ; (el "?" del final)
        cmp.b   d3,d0
        beq.s   .m1
        addq.l  #6,a3
        bra.s   .m
.m1:    moveq   #6-1,d4
.m2:    move.b  (a3)+,d0
        move.l  a3,-(sp)
        bsr.s   txt_ch
        move.l  (sp)+,a3
        dbf     d4,.m2
        bra.s   .n
.c:     bsr.s   txt_ch
        bra.s   .n
.x:     rts

; --- txt_ch --- un caracter: d0.b = codigo, a1 = byte (avanza), d2 = paso
; registros destruidos: d0-d1/a3
txt_ch:
        and.w   #$ff,d0
        sub.w   #DFONT_FIRST,d0
        bcs.s   .sp
        cmp.w   #DFONT_LAST-DFONT_FIRST,d0
        bls.s   .ok
.sp:    moveq   #0,d0                       ; fuera de la tabla: espacio
.ok:    lsl.w   #3,d0
        lea     diagfont(pc),a3
        add.w   d0,a3
        move.l  a1,-(sp)
        moveq   #8-1,d1
.l:     move.b  (a3)+,(a1)
        add.w   d2,a1
        dbf     d1,.l
        move.l  (sp)+,a1
        addq.l  #1,a1
        rts

        include "player/diagfont.i"
        even

g_diag:  dc.w   0                           ; 0 = jugando, 1/2 = pagina
g_dmem:  dc.l   0                           ; chip: DG_SIZE bytes
g_dlist: dc.l   0                           ; la lista del juego congelada
g_dtime: dc.w   0                           ; frames en el diagnostico
g_dprev: dc.b   0                           ; teclas del diagnostico (frame anterior)
        even
g_frame: dc.l   0                           ; frame desde el principio del nivel
h_last:  dc.w   0                           ; historial: ultimo estado
h_t:     dc.l   0                           ;   frame de la ultima entrada
h_n:     dc.w   0                           ;   entradas
h_flags: dc.w   0                           ;   DF_OVER
h_pa0:   dc.b   0                           ;   g_pada / g_padb al empezar
h_pb0:   dc.b   0
dg_info: ds.w   DG_HDR                      ; la cabecera (DI_*)
dg_args: ds.w   16
hist:    ds.w   HISTMAX                     ; en el binario: en la slow RAM
        endc                                ; DIAG

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
