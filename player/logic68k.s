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
_spr_tile_asm:
        movem.l d2-d4/a2,-(sp)
        moveq   #0,d1
        move.b  16+7(sp),d1                 ; x
        moveq   #0,d2
        move.b  16+11(sp),d2                ; y
        lea     _ram(a4),a2
        lea     (a2,d1.w),a1                ; a1 = ram + x: tablas de sprite
        move.b  d2,m15(a2)                  ; con d16(a1) ((d8,An,Dn) no llega)
        move.b  wm_Tweaker1656(a1),d0
        and.b   #$0f,d0
        lsl.b   #2,d0
        add.b   d0,d2                       ; y = punto de choque
        move.b  wm_TempTileGen(a2),d0
        addq.b  #1,d0
        and.b   wm_IsVerticalLvl(a2),d0
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
        move.b  d3,m12(a2)
        move.w  d3,d0
        lsr.w   #8,d0
        move.b  d0,m13(a2)
        moveq   #-16,d0                     ; $F0
        and.b   d3,d0
        move.b  d0,m0(a2)
        cmp.w   #$1b0,d3
        bhs     .out
        ; px = X del sprite + SprObjClipX[y]
        moveq   #0,d4
        move.b  wm_SpriteXHi(a1),d4
        lsl.w   #8,d4
        move.b  wm_SpriteXLo(a1),d4
        move.l  _spr_clip_x(a4),a0
        moveq   #0,d0
        move.b  (a0,d2.w),d0
        add.w   d0,d4
        move.b  d4,m10(a2)
        move.b  d4,m1(a2)
        move.w  d4,d0
        lsr.w   #8,d0
        move.b  d0,m11(a2)
        tst.w   d4
        bmi     .out
        cmp.b   wm_ScreensInLvl(a2),d0
        bhs     .out
        ; o = scr_ofs[pantalla] + (py & $1F0) + (px & $FF) >> 4  (< $3600)
        and.w   #$1f,d0
        add.w   d0,d0
        lea     _scr_ofs(a4),a0
        move.w  (a0,d0.w),d0
        and.w   #$1f0,d3
        add.w   d3,d0
        moveq   #0,d3
        move.b  d4,d3
        lsr.b   #4,d3
        add.w   d3,d0
        move.l  _map16_lo(a4),a0
        move.b  (a0,d0.w),d2                ; lo
        move.l  _map16_hi(a4),a0
        move.b  (a0,d0.w),d3                ; pagina
        move.b  d2,wm_Map16NumLo(a2)
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
.ret:   moveq   #0,d0
        move.b  d3,d0
        movem.l (sp)+,d2-d4/a2
        rts
.out:   clr.b   wm_Map16NumLo(a2)           ; CODE_0194B4
        clr.b   wm_SprMoveDownPixels(a2)
        moveq   #0,d0
        movem.l (sp)+,d2-d4/a2
        rts
.inc:   movem.l (sp)+,d2-d4/a2              ; los argumentos siguen en la pila
        jmp     _spr_tile_c

;----------------------------------------------------------------------
; u8 f44d_asm(void) = f44d de mcoll.c (CODE_00F44D): la sonda siguiente
; (rX += 2) respecto de la posicion de Mario (probe_mx/my), el bloque que
; toca y su pagina. Deja BlockYPos/XPos, Map16NumLo y rY como el C. Con
; wm_8E (capa 2) salta al C; con un bloque de los interruptores P llama a
; f44d_tail (f545 en C).
;----------------------------------------------------------------------
        public  _f44d_asm
_f44d_asm:
        tst.b   _ram+wm_8E(a4)
        bne     .c
        movem.l d2-d3/a2,-(sp)
        lea     _ram(a4),a2
        move.b  _rX(a4),d0
        addq.b  #2,d0
        move.b  d0,_rX(a4)
        moveq   #$7e,d1
        and.b   d0,d1                       ; k = 2 * ((rX >> 1) & 63)
        lea     _probe_dx(a4),a0
        move.w  (a0,d1.w),d2
        add.w   _probe_mx(a4),d2            ; x
        lea     _probe_dy(a4),a0
        move.w  (a0,d1.w),d3
        add.w   _probe_my(a4),d3            ; y
        move.b  d2,wm_BlockYPos(a2)         ; (el ROM pone x en BlockYPos)
        move.w  d2,d0
        lsr.w   #8,d0                       ; d0 = xs = pantalla
        move.b  d0,wm_BlockYPos+1(a2)
        move.b  d3,wm_BlockXPos(a2)
        move.w  d3,d1
        lsr.w   #8,d1
        move.b  d1,wm_BlockXPos+1(a2)
        clr.b   wm_WhichSwitchPressed(a2)
        cmp.w   #$1b0,d3
        bhs.s   .off
        cmp.b   wm_ScreensInLvl(a2),d0
        bhs.s   .off
        and.w   #$1f,d0
        add.w   d0,d0
        lea     _scr_ofs(a4),a0
        move.w  (a0,d0.w),d0
        and.w   #$1f0,d3
        add.w   d3,d0
        moveq   #0,d1
        move.b  d2,d1
        lsr.b   #4,d1
        add.w   d1,d0                       ; o (< $3600)
        move.l  _map16_lo(a4),a0
        move.b  (a0,d0.w),d1                ; lo
        move.l  _map16_hi(a4),a0
        move.b  (a0,d0.w),d0                ; pagina
        move.b  d1,wm_Map16NumLo(a2)
        move.b  d1,_rY(a4)
        tst.b   d0
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
.sw:    and.l   #$ff,d0                     ; interruptores P: f545 en C
        move.l  d0,-(sp)
        jsr     _f44d_tail
        addq.l  #4,sp
.ret:   and.l   #$ff,d0
        movem.l (sp)+,d2-d3/a2
        rts
.off:   move.b  #$25,_rY(a4)                ; CODE_00F4A0: fuera del nivel
        moveq   #0,d0
        movem.l (sp)+,d2-d3/a2
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
