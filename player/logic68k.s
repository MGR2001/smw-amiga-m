;----------------------------------------------------------------------
; logic68k.s - rutinas de la logica en ensamblador a mano (Etapa 8.2).
;
; Cada rutina reemplaza, SOLO en el build de la Amiga (vbcc, sin NOASM), a
; una funcion de player/*.c que sigue siendo la referencia: el PC
; (marioverify) corre el C, y m68kverify/abcheck comparan el binario del
; 68000 contra el. Los casos raros no se escriben aca: la rutina salta a la
; version en C con los mismos argumentos (antes de cambiar nada que el C
; no vuelva a escribir igual).
;
; ABI de vbcc: argumentos en la pila en ranuras de 32 bits (un u8 en el
; byte +3), resultado en d0, se conservan d2-d7/a2-a6; a4 = datos pequenos
; (_ram(a4), _map16_lo(a4)...). Las direcciones de ram[] salen de
; work/cc/smwram.i (lo genera logicbench_build.sh desde gen/smwram.h).
;----------------------------------------------------------------------

;----------------------------------------------------------------------
; u8 spr_tile_asm(u8 x, u8 y) = spr_tile de msprite.c (CODE_019441 /
; _01944D / CODE_0194BF): el bloque bajo el punto de choque y del sprite x.
; Deja m0, m1, m10-m13, m15 y Map16NumLo como el C.
;----------------------------------------------------------------------
        public  _spr_tile_asm
_spr_tile_asm:                              ; guarda solo d2-d3; ram por a4
        movem.l d2-d3,-(sp)
        moveq   #0,d1
        move.b  8+7(sp),d1                  ; x
        moveq   #0,d2
        move.b  8+11(sp),d2                 ; y
        lea     _ram(a4),a1
        add.w   d1,a1                       ; a1 = ram + x ((d8,An,Dn) no llega)
        move.b  d2,_ram+m15(a4)
        move.b  wm_Tweaker1656(a1),d0
        and.b   #$0f,d0
        lsl.b   #2,d0
        add.b   d0,d2                       ; y = punto de choque
        move.b  _ram+wm_TempTileGen(a4),d0
        addq.b  #1,d0
        and.b   _ram+wm_IsVerticalLvl(a4),d0
        bne     .inc                        ; generador / nivel vertical: el C
        ; py = Y del sprite + SprObjClipY[y]
        moveq   #0,d3
        move.b  wm_SpriteYHi(a1),d3
        lsl.w   #8,d3
        move.b  wm_SpriteYLo(a1),d3
        move.l  _spr_clip_y(a4),a0
        moveq   #0,d0
        move.b  (a0,d2.w),d0
        add.w   d0,d3
        move.b  d3,_ram+m12(a4)
        move.w  d3,-(sp)                    ; byte alto, sin desplazar
        move.b  (sp)+,_ram+m13(a4)
        moveq   #-16,d0                     ; $F0
        and.b   d3,d0
        move.b  d0,_ram+m0(a4)
        cmp.w   #$1b0,d3
        bhs     .out
        ; px = X del sprite + SprObjClipX[y]  (d1: x ya no hace falta)
        move.b  wm_SpriteXHi(a1),d1
        lsl.w   #8,d1
        move.b  wm_SpriteXLo(a1),d1
        move.l  _spr_clip_x(a4),a0
        moveq   #0,d0
        move.b  (a0,d2.w),d0
        add.w   d0,d1
        move.b  d1,_ram+m10(a4)
        move.b  d1,_ram+m1(a4)
        move.w  d1,d0
        lsr.w   #8,d0
        move.b  d0,_ram+m11(a4)
        tst.w   d1
        bmi     .out
        cmp.b   _ram+wm_ScreensInLvl(a4),d0
        bhs     .out
        ; o = scr_ofs[pantalla] + (py & $1F0) + (px & $FF) >> 4  (< $3600)
        and.w   #$1f,d0
        add.w   d0,d0
        lea     _scr_ofs(a4),a0
        move.w  (a0,d0.w),d0
        and.w   #$1f0,d3
        add.w   d3,d0
        moveq   #0,d3
        move.b  d1,d3
        lsr.b   #4,d3
        add.w   d3,d0
        move.l  _map16_lo(a4),a0
        move.b  (a0,d0.w),d2                ; lo
        move.l  _map16_hi(a4),a0
        moveq   #0,d3
        move.b  (a0,d0.w),d3                ; pagina
        move.b  d2,_ram+wm_Map16NumLo(a4)
        tst.b   d3
        beq.s   .p0
        cmp.b   #$32,d2
        beq.s   .uns
        cmp.b   #$2f,d2
        beq.s   .uns
        bra.s   .ret
.p0:    cmp.b   #$29,d2
        beq.s   .uns
        cmp.b   #$2b,d2
        beq.s   .uns
        sub.b   #$ec,d2
        cmp.b   #$10,d2
        bhs.s   .ret
.uns:   tst.l   _mario_unsupported(a4)      ; interruptores P: sin portar
        bne.s   .ret
        moveq   #MARIO_UNSUP_TILE,d0
        move.l  d0,_mario_unsupported(a4)
.ret:   move.l  d3,d0
        movem.l (sp)+,d2-d3
        rts
.out:   clr.b   _ram+wm_Map16NumLo(a4)      ; CODE_0194B4
        clr.b   _ram+wm_SprMoveDownPixels(a4)
        moveq   #0,d0
        movem.l (sp)+,d2-d3
        rts
.inc:   movem.l (sp)+,d2-d3                 ; los argumentos siguen en la pila
        jmp     _spr_tile_c

;----------------------------------------------------------------------
; u8 f44d_asm(void) = f44d de mcoll.c (CODE_00F44D): la sonda siguiente
; (rX += 2) respecto de la posicion de Mario (probe_mx/my), el bloque que
; toca y su pagina. Deja BlockYPos/XPos, Map16NumLo y rY como el C. Con
; wm_8E (capa 2) salta al C; con un bloque de los interruptores P llama a
; f44d_tail (f545 en C).
;----------------------------------------------------------------------
        public  _f44d_asm
_f44d_asm:                                  ; solo d2 se guarda: base en a1
        tst.b   _ram+wm_8E(a4)
        bne     .c
        move.l  d2,-(sp)
        lea     _ram(a4),a1
        move.b  _rX(a4),d0
        addq.b  #2,d0
        move.b  d0,_rX(a4)
        moveq   #$7e,d1
        and.b   d0,d1                       ; k = 2 * ((rX >> 1) & 63)
        lea     _probe_dx(a4),a0
        move.w  (a0,d1.w),d2
        add.w   _probe_mx(a4),d2            ; d2 = x
        lea     _probe_dy(a4),a0
        move.w  (a0,d1.w),d1
        add.w   _probe_my(a4),d1            ; d1 = y
        move.b  d2,wm_BlockYPos(a1)         ; (el ROM pone x en BlockYPos)
        move.w  d2,d0
        lsr.w   #8,d0                       ; d0 = xs = pantalla
        move.b  d0,wm_BlockYPos+1(a1)
        move.b  d1,wm_BlockXPos(a1)
        move.w  d1,-(sp)                    ; byte alto de y, sin desplazar
        move.b  (sp)+,wm_BlockXPos+1(a1)
        clr.b   wm_WhichSwitchPressed(a1)
        cmp.w   #$1b0,d1
        bhs.s   .off
        cmp.b   wm_ScreensInLvl(a1),d0
        bhs.s   .off
        and.w   #$1f,d0
        add.w   d0,d0
        lea     _scr_ofs(a4),a0
        move.w  (a0,d0.w),d0
        and.w   #$1f0,d1
        add.w   d1,d0
        moveq   #0,d1
        move.b  d2,d1
        lsr.b   #4,d1
        add.w   d1,d0                       ; o (< $3600)
        move.l  _map16_lo(a4),a0
        move.b  (a0,d0.w),d1                ; lo
        move.l  _map16_hi(a4),a0
        moveq   #0,d2
        move.b  (a0,d0.w),d2                ; pagina
        move.b  d1,wm_Map16NumLo(a1)
        move.b  d1,_rY(a4)
        tst.b   d2
        beq.s   .p0
        cmp.b   #$32,d1
        beq.s   .sw
        cmp.b   #$2f,d1
        beq.s   .sw
        bra.s   .ret
.p0:    cmp.b   #$29,d1
        beq.s   .sw
        cmp.b   #$2b,d1
        beq.s   .sw
        sub.b   #$ec,d1
        cmp.b   #$10,d1
        bhs.s   .ret
.sw:    move.l  d2,-(sp)                    ; interruptores P: f545 en C
        jsr     _f44d_tail
        addq.l  #4,sp
        moveq   #0,d2
        move.b  d0,d2
.ret:   move.l  d2,d0
        move.l  (sp)+,d2
        rts
.off:   move.b  #$25,_rY(a4)                ; CODE_00F4A0: fuera del nivel
        moveq   #0,d0
        move.l  (sp)+,d2
        rts
.c:     jmp     _f44d_c

;----------------------------------------------------------------------
; void spr_pos_axis_asm(u8 x, u8 o) = spr_pos_axis de msprite.c
; (SubSprYPosNoGrvty; o = $0C: SubSprXPosNoGrvty). Velocidad 4.4 a la
; posicion: YAcc += v << 4, YLo:YHi += (v asr 4) + acarreo, con addx
; (la cadena de acarreo del 65816, sin rearmar 16 bits).
;----------------------------------------------------------------------
        public  _spr_pos_axis_asm
_spr_pos_axis_asm:
        movem.l d2-d3,-(sp)
        moveq   #0,d1
        move.b  8+7(sp),d1                  ; x
        moveq   #0,d0
        move.b  8+11(sp),d0                 ; o
        add.w   d0,d1
        lea     _ram(a4),a1
        add.w   d1,a1                       ; a1 = ram + x + o
        move.b  wm_SpriteSpeedY(a1),d0      ; v
        beq.s   .zero
        move.b  d0,d1
        asr.b   #4,d1                       ; d = v >> 4 con signo
        smi     d2                          ; hi = $FF si d < 0
        lsl.b   #4,d0                       ; v << 4
        move.b  wm_SpriteYAcc(a1),d3
        add.b   d0,d3                       ; X = acarreo c
        move.b  d3,wm_SpriteYAcc(a1)        ; (move no toca X)
        scs     d0                          ; d0 = -c
        move.b  wm_SpriteYLo(a1),d3
        addx.b  d1,d3                       ; YLo + d + c
        move.b  d3,wm_SpriteYLo(a1)
        move.b  wm_SpriteYHi(a1),d3
        addx.b  d2,d3                       ; YHi + hi + acarreo
        move.b  d3,wm_SpriteYHi(a1)
        sub.b   d0,d1                       ; d + c
        move.b  d1,_ram+wm_SprPixelMove(a4)
        movem.l (sp)+,d2-d3
        rts
.zero:  clr.b   _ram+wm_SprPixelMove(a4)
        movem.l (sp)+,d2-d3
        rts

;----------------------------------------------------------------------
; int get_draw_info_asm(u8 x) = get_draw_info de msprite.c
; (GetDrawInfoBnk3, solo los flags de fuera de pantalla). Devuelve 0 si
; el sprite esta lejos.
;----------------------------------------------------------------------
        public  _get_draw_info_asm
_get_draw_info_asm:
        movem.l d2-d4,-(sp)
        moveq   #0,d1
        move.b  12+7(sp),d1                 ; x
        lea     _ram(a4),a1
        add.w   d1,a1                       ; a1 = ram + x
        lea     _ram(a4),a0
        clr.b   wm_OffscreenVert(a1)
        move.b  wm_SpriteXHi(a1),d2
        lsl.w   #8,d2
        move.b  wm_SpriteXLo(a1),d2         ; sx
        move.b  wm_Bg1HOfs+1(a0),d0
        lsl.w   #8,d0
        move.b  wm_Bg1HOfs(a0),d0           ; camara X
        sub.w   d0,d2                       ; sx - cam
        move.w  d2,d0
        lsr.w   #8,d0
        sne     d0
        neg.b   d0
        move.b  d0,wm_OffscreenHorz(a1)     ; alto != 0
        add.w   #$40,d2
        cmp.w   #$180,d2
        shs     d0
        neg.b   d0
        move.b  d0,wm_SpriteOffTbl(a1)
        bne.s   .far
        move.b  wm_Bg1VOfs+1(a0),d3
        lsl.w   #8,d3
        move.b  wm_Bg1VOfs(a0),d3           ; camara Y
        move.b  wm_SpriteYHi(a1),d2
        lsl.w   #8,d2
        move.b  wm_SpriteYLo(a1),d2
        sub.w   d3,d2                       ; sy - camY (+ tabla abajo)
        moveq   #0,d4
        btst    #5,wm_Tweaker1662(a1)
        beq.s   .y0
        moveq   #1,d4                       ; y = 1: dos puntos
.lp:    move.l  _gdi_ofs(a4),a0
        moveq   #0,d0
        move.b  (a0,d4.w),d0
        add.w   d2,d0
        lsr.w   #8,d0
        beq.s   .nx
        move.l  _gdi_bit(a4),a0
        move.b  (a0,d4.w),d0
        or.b    d0,wm_OffscreenVert(a1)
.nx:    subq.w  #1,d4
        bpl.s   .lp
        bra.s   .on
.y0:    move.l  _gdi_ofs(a4),a0
        moveq   #0,d0
        move.b  (a0),d0
        add.w   d2,d0
        lsr.w   #8,d0
        beq.s   .on
        move.l  _gdi_bit(a4),a0
        move.b  (a0),d0
        or.b    d0,wm_OffscreenVert(a1)
.on:    moveq   #1,d0
        movem.l (sp)+,d2-d4
        rts
.far:   moveq   #0,d0
        movem.l (sp)+,d2-d4
        rts

;----------------------------------------------------------------------
; void camera_F6DB(void) = camera_F6DB_c de mcam.c (CODE_00F6DB, nivel
; horizontal): Bg1/Bg2 a partir de L1/L2NextPos y de Mario respecto de la
; zona muerta. f7f4 (scroll vertical) y f8ab (L/R) siguen en C. Nivel
; vertical: el C (lo marca sin portar).
; d3 = pts  d4 = bg1h  d5 = bg1v  d6 = bg2h  d7 = bg2v  a2 = ram
;----------------------------------------------------------------------
RD16    macro                               ; \2.w = ram[\1] (little endian)
        move.b  \1+1(a2),\2
        lsl.w   #8,\2
        move.b  \1(a2),\2
        endm
WR16    macro                               ; ram[\1] = \2.w (destruye d0)
        move.b  \2,\1(a2)
        move.w  \2,d0
        lsr.w   #8,d0
        move.b  d0,\1+1(a2)
        endm

        public  _camera_F6DB
_camera_F6DB:
        btst    #0,_ram+wm_IsVerticalLvl(a4)
        bne     .vert
        movem.l d2-d7/a2,-(sp)
        lea     _ram(a4),a2
        RD16    wm_PosToScrollScreen,d3
        move.w  d3,d1
        sub.w   #$000c,d1
        WR16    wm_CanScrollScreen,d1
        add.w   #$0018,d1
        WR16    wm_CanScrollScreen+2,d1
        RD16    wm_L1NextPosX,d4
        RD16    wm_L1NextPosY,d5
        RD16    wm_L2NextPosX,d6
        RD16    wm_L2NextPosY,d7
        WR16    wm_Bg1HOfs,d4
        moveq   #0,d0                       ; bg1v = f7f4($00C0, bg1v)
        move.w  d5,d0
        move.l  d0,-(sp)
        move.l  #$00c0,-(sp)
        jsr     _f7f4
        addq.l  #8,sp
        move.w  d0,d5
        tst.b   wm_HorzScrollHead(a2)
        beq     .l2
        RD16    wm_MarioXPos,d1
        sub.w   d4,d1                       ; v0 = MarioXPos - bg1h
        WR16    m0,d1
        moveq   #2,d2                       ; y
        move.w  d1,d0
        sub.w   d3,d0
        bpl.s   .y2
        moveq   #0,d2
.y2:    move.b  d2,wm_Layer1ScrollDir(a2)
        move.b  d2,wm_Layer2ScrollDir(a2)
        move.w  d3,d0                       ; a = v0 - (pts - $0C [+ $18])
        sub.w   #$000c,d0
        tst.b   d2
        beq.s   .y0
        add.w   #$0018,d0
.y0:    sub.w   d0,d1                       ; d1 = a
        beq     .l2
        lea     _rom00+(DATA_00F6A3-ROM00_BASE)(a4),a0
        move.w  d1,d0                       ; (a ^ T16X(DATA_00F6A3, y)) & $8000:
        lsr.w   #8,d0                       ; solo cuenta el bit 15, o sea el
        move.b  1(a0,d2.w),d2               ; bit 7 de los bytes altos
        eor.b   d2,d0
        bpl     .l2
        WR16    m2,d1
        jsr     _f8ab
        RD16    m2,d1                       ; v2
        add.w   d4,d1                       ; a = v2 + bg1h
        bpl.s   .pos
        moveq   #0,d1
.pos:   move.w  d1,d4
        moveq   #0,d0
        move.b  wm_LastScreenHorz(a2),d0
        subq.b  #1,d0
        lsl.w   #8,d0                       ; ((LastScreenHorz - 1) & $FF) << 8
        bpl.s   .lim
        move.w  #$0080,d0
.lim:   cmp.w   d4,d0                       ; a - bg1h < 0 (con signo)?
        bge.s   .l2
        move.w  d0,d4
.l2:    moveq   #0,d0                       ; _00F79D: la capa 2
        move.b  wm_HorzScrollLyr2(a2),d0
        beq.s   .v2
        move.w  d4,d6
        cmp.b   #1,d0
        beq.s   .v2
        lsr.w   #1,d6
.v2:    move.b  wm_VertScrollLyr2(a2),d0
        beq.s   .wr
        move.w  d5,d1
        cmp.b   #1,d0
        beq.s   .v1
        cmp.b   #2,d0
        bne.s   .v5
        lsr.w   #1,d1
        bra.s   .v1
.v5:    lsr.w   #5,d1
.v1:    RD16    wm_VertL2ScrollLength,d7
        add.w   d1,d7
.wr:    WR16    wm_Bg1HOfs,d4
        WR16    wm_Bg1VOfs,d5
        WR16    wm_Bg2HOfs,d6
        WR16    wm_Bg2VOfs,d7
        move.b  d4,d0                       ; cuanto se movio cada capa
        sub.b   wm_L1NextPosX(a2),d0
        move.b  d0,wm_L1CurXChange(a2)
        move.b  d5,d0
        sub.b   wm_L1NextPosY(a2),d0
        move.b  d0,wm_L1CurYChange(a2)
        move.b  d6,d0
        sub.b   wm_L2NextPosX(a2),d0
        move.b  d0,wm_L2CurXChange(a2)
        move.b  d7,d0
        sub.b   wm_L2NextPosY(a2),d0
        move.b  d0,wm_L2CurYChange(a2)
        WR16    wm_L1NextPosX,d4
        WR16    wm_L1NextPosY,d5
        WR16    wm_L2NextPosX,d6
        WR16    wm_L2NextPosY,d7
        movem.l (sp)+,d2-d7/a2
        rts
.vert:  jmp     _camera_F6DB_c

;----------------------------------------------------------------------
; int spr_mario_contact_asm(u8 x) = spr_mario_contact de msprite.c: cajas
; de Mario y del sprite x; 1 si se tocan. Primero Y, despues X, como el C.
; Tablas por puntero (logic68k_init): _mcl (MarioClipDispY, MarioClipH) y
; _cl (ClipDispX, ClipDispY, ClipWidth, ClipHeight).
;----------------------------------------------------------------------
CONTACT macro                               ; \1 = a  \2 = b  \3 = wa  \4 = wb
        move.w  \1,d0                       ; (u16)(a - b + $80) >= $100: no
        sub.w   \2,d0
        add.w   #$80,d0
        cmp.w   #$100,d0
        bhs     .no
        move.b  \3,d0                       ; (u8)(wa + wb) <
        add.b   \4,d0
        move.b  \2,d1                       ;   (u8)((u8)b - (u8)a + wb): no
        sub.b   \1,d1
        add.b   \4,d1
        cmp.b   d1,d0
        blo     .no
        endm

        public  _spr_mario_contact_asm
_spr_mario_contact_asm:
        movem.l d2-d7/a2,-(sp)
        moveq   #0,d1
        move.b  28+7(sp),d1                 ; x
        lea     _ram(a4),a2
        lea     (a2,d1.w),a1                ; a1 = ram + x
        moveq   #1,d2                       ; k
        tst.b   wm_IsDucking(a2)
        bne.s   .k
        tst.b   wm_MarioPowerUp(a2)
        beq.s   .k
        moveq   #0,d2
.k:     tst.b   wm_OnYoshi(a2)
        beq.s   .k2
        addq.w  #2,d2
.k2:    RD16    wm_MarioYPos,d3
        move.l  _mcl_dy(a4),a0
        moveq   #0,d0
        move.b  (a0,d2.w),d0
        add.w   d0,d3                       ; my
        move.l  _mcl_h(a4),a0
        move.b  (a0,d2.w),d4                ; mh
        moveq   #$3f,d7
        and.b   wm_Tweaker1662(a1),d7       ; c
        move.b  wm_SpriteYHi(a1),d5
        lsl.w   #8,d5
        move.b  wm_SpriteYLo(a1),d5
        move.l  _cl_dy(a4),a0
        move.b  (a0,d7.w),d0
        ext.w   d0
        add.w   d0,d5                       ; sy
        move.l  _cl_h(a4),a0
        move.b  (a0,d7.w),d6                ; sh
        CONTACT d3,d5,d4,d6
        RD16    wm_MarioXPos,d3
        addq.w  #2,d3                       ; mx
        moveq   #$0c,d4                     ; mw
        move.b  wm_SpriteXHi(a1),d5
        lsl.w   #8,d5
        move.b  wm_SpriteXLo(a1),d5
        move.l  _cl_dx(a4),a0
        move.b  (a0,d7.w),d0
        ext.w   d0
        add.w   d0,d5                       ; sx
        move.l  _cl_w(a4),a0
        move.b  (a0,d7.w),d6                ; sw
        CONTACT d3,d5,d4,d6
        moveq   #1,d0
        movem.l (sp)+,d2-d7/a2
        rts
.no:    moveq   #0,d0
        movem.l (sp)+,d2-d7/a2
        rts

;----------------------------------------------------------------------
; void rex_main_asm(u8 x) = rex_main de msprite.c (el Rex, sprite $AB):
; pose, temporizadores, velocidad, movimiento e interacciones. Las rutinas
; de sprite siguen en C (o en este fichero) y el contacto con Mario, que
; es raro, es rex_contact (C). a3 = ram + x: SPR(t, x) = t(a3).
;----------------------------------------------------------------------
CALLX   macro                               ; \1(x), x en d2
        move.l  d2,-(sp)
        jsr     \1
        addq.l  #4,sp
        endm

        public  _rex_main_asm
_rex_main_asm:
        movem.l d2/a2-a3,-(sp)
        moveq   #0,d2
        move.b  12+7(sp),d2                 ; x
        lea     _ram(a4),a2
        lea     (a2,d2.w),a3
        tst.b   wm_SpriteDecTbl3(a3)        ; RexGfxRt
        beq.s   .g1
        move.b  #5,wm_SpriteGfxTbl(a3)
.g1:    tst.b   wm_DisSprCapeContact(a3)
        beq.s   .g2
        move.b  #2,wm_SpriteGfxTbl(a3)
.g2:    CALLX   _get_draw_info_asm
        cmp.b   #$08,wm_SpriteStatus(a3)
        bne     .ret
        tst.b   wm_SpritesLocked(a2)
        bne     .ret
        move.b  wm_SpriteDecTbl3(a3),d0
        beq.s   .alive
        move.b  d0,wm_SpriteEatenTbl(a3)
        cmp.b   #1,d0
        bne     .ret
        clr.b   wm_SpriteStatus(a3)
        bra     .ret
.alive: CALLX   _sub_offscreen3
        addq.b  #1,wm_SpriteMiscTbl6(a3)
        move.b  wm_SpriteMiscTbl6(a3),d0
        lsr.b   #2,d0
        tst.b   wm_SpriteState(a3)
        beq.s   .s0
        and.b   #1,d0
        addq.b  #3,d0
        bra.s   .s1
.s0:    lsr.b   #1,d0
        and.b   #1,d0
.s1:    move.b  d0,wm_SpriteGfxTbl(a3)
        btst    #2,wm_SprObjStatus(a3)
        beq.s   .n2
        move.b  #$10,wm_SpriteSpeedY(a3)
        moveq   #0,d0
        move.b  wm_SpriteDir(a3),d0
        tst.b   wm_SpriteState(a3)
        beq.s   .d
        addq.b  #2,d0
.d:     move.l  _rex_speed(a4),a0
        move.b  (a0,d0.w),wm_SpriteSpeedX(a3)
.n2:    tst.b   wm_DisSprCapeContact(a3)
        bne.s   .n3
        CALLX   _spr_update_pos_asm
.n3:    moveq   #3,d0
        and.b   wm_SprObjStatus(a3),d0
        beq.s   .n4
        eor.b   #1,wm_SpriteDir(a3)
.n4:    CALLX   _spr_spr_interact
        CALLX   _mario_spr_interact
        tst.l   d0
        beq.s   .ret
        CALLX   _rex_contact
.ret:   movem.l (sp)+,d2/a2-a3
        rts

;----------------------------------------------------------------------
; void spr_update_pos_asm(u8 x) = spr_update_pos de msprite.c
; (SubUpdateSprPos): Y con gravedad, X, y la interaccion con los bloques
; (spr_obj_interact, C). Las dos constantes de la ROM, por puntero.
;----------------------------------------------------------------------
        public  _spr_update_pos_asm
_spr_update_pos_asm:
        movem.l d2-d3/a3,-(sp)
        moveq   #0,d2
        move.b  12+7(sp),d2                 ; x
        lea     _ram(a4),a3
        add.w   d2,a3                       ; a3 = ram + x
        clr.l   -(sp)                       ; spr_pos_axis(x, 0)
        move.l  d2,-(sp)
        bsr     _spr_pos_axis_asm
        addq.l  #8,sp
        tst.b   wm_SprInWaterTbl(a3)
        bne.s   .unsup
        move.l  _upd_grav(a4),a0
        move.b  wm_SpriteSpeedY(a3),d0
        add.b   (a0),d0                     ; v = SpeedY + gravedad
        bmi.s   .v
        move.l  _upd_max(a4),a0
        cmp.b   (a0),d0
        blo.s   .v
        move.b  (a0),d0                     ; tope de caida
.v:     move.b  d0,wm_SpriteSpeedY(a3)
        move.b  wm_SpriteSpeedX(a3),d3      ; keep
        pea     $0c.w                       ; spr_pos_axis(x, $0C)
        move.l  d2,-(sp)
        bsr     _spr_pos_axis_asm
        addq.l  #8,sp
        move.b  d3,wm_SpriteSpeedX(a3)
        tst.b   wm_SpriteInterTbl(a3)
        beq.s   .obj
        clr.b   wm_SprObjStatus(a3)
        bra.s   .ret
.obj:   move.l  d2,-(sp)
        jsr     _spr_obj_interact
        addq.l  #4,sp
.ret:   movem.l (sp)+,d2-d3/a3
        rts
.unsup: tst.l   _mario_unsupported(a4)      ; spr_unsup (agua: sin portar)
        bne.s   .ret
        moveq   #MARIO_UNSUP_TILE,d0
        move.l  d0,_mario_unsupported(a4)
        bra.s   .ret

;----------------------------------------------------------------------
; u16 f7f4(u16 limit, u16 bg1v) = f7f4_c de mcam.c (CODE_00F7F4, el scroll
; vertical de la capa 1). Hacia arriba (v2 < 0) salta al C, que vuelve a
; escribir igual m0, m2, m4 y las direcciones antes de seguir.
; d1 = a / v2  d2 = y  d3 = limit  d4 = bg1v  d5 = valor de tabla
;----------------------------------------------------------------------
T16Y    macro                               ; \2.w = T16X(\1, y), y en d2
        lea     _rom00+(\1-ROM00_BASE)(a4),a0
        move.b  1(a0,d2.w),\2
        lsl.w   #8,\2
        move.b  (a0,d2.w),\2
        endm

        public  _f7f4
_f7f4:
        tst.b   _ram+wm_VertScrollHead(a4)
        bne.s   .on
        moveq   #0,d0
        move.w  10(sp),d0                   ; bg1v
        rts
.on:    movem.l d2-d5/a2,-(sp)
        lea     _ram(a4),a2
        move.w  20+6(sp),d3                 ; limit
        move.w  20+10(sp),d4                ; bg1v
        WR16    m4,d3
        moveq   #0,d2
        RD16    wm_MarioYPos,d1
        sub.w   d4,d1                       ; v0
        WR16    m0,d1
        move.w  d1,d0
        sub.w   #$0070,d0
        bmi.s   .y0
        moveq   #2,d2
.y0:    move.b  d2,wm_Layer1ScrollDir(a2)
        move.b  d2,wm_Layer2ScrollDir(a2)
        T16Y    DATA_00F69F,d5
        sub.w   d5,d1                       ; v2
        move.w  d1,d0                       ; (v2 ^ T16X(DATA_00F6A3, y)) & $8000
        lsr.w   #8,d0
        lea     _rom00+(DATA_00F6A3-ROM00_BASE)(a4),a0
        move.b  1(a0,d2.w),d5
        eor.b   d5,d0
        bmi.s   .keep
        moveq   #2,d2
        moveq   #0,d1
.keep:  WR16    m2,d1
        tst.w   d1
        bmi.s   .up
        clr.b   wm_ScrScrollToPlayer(a2)
        T16Y    DATA_00F6A7,d5              ; _00F883: limita la velocidad
        move.w  d1,d0
        sub.w   d5,d0
        eor.w   d5,d0
        bmi.s   .nc
        move.w  d5,d1
.nc:    add.w   d4,d1                       ; a + bg1v
        T16Y    DATA_00F6AD,d5
        move.w  d1,d0
        sub.w   d5,d0
        bpl.s   .ok
        move.w  d5,d1
.ok:    move.w  d1,d4                       ; bg1v = a
        moveq   #0,d0
        move.w  d3,d0
        sub.w   d4,d0
        bmi.s   .lim
        moveq   #0,d0
        move.w  d4,d0
        bra.s   .out
.lim:   clr.b   wm_EnableVertScroll(a2)
        moveq   #0,d0
        move.w  d3,d0
.out:   movem.l (sp)+,d2-d5/a2
        rts
.up:    movem.l (sp)+,d2-d5/a2              ; hacia arriba: el C
        jmp     _f7f4_c
