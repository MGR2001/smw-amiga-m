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
