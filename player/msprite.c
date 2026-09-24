/*
 * msprite.c - etapa 9: el motor de sprites (sprite_*.s de SMW U). Ver
 * mario.h. Por ahora el cargador: LoadSprFromLevel (sprite_2-clus.s), que
 * crea los sprites del nivel cuando su columna entra por el borde.
 *
 * Datos del nivel (spr.lv): un byte de cabecera (& $3F = modo de memoria,
 * wm_SpriteMemory) y registros de 3 bytes, ordenados por pantalla:
 *   byte0 = yyyy EE s Y   y = fila (x16), s = bit 4 de la pantalla,
 *                          Y y EE van al byte alto de la Y (AND #$0D)
 *   byte1 = xxxx pppp     x = columna, pppp = pantalla (bits 0-3)
 *   byte2 = numero de sprite
 *   $FF = fin.
 */
#include "mario.h"
#include "gen/smwram.h"
#include "gen/smwtab.h"
#include "gen/smwtabx.h"
#include "smwmac.h"

const u8 *spr_level;        /* spr.lv del nivel (cabecera incluida) */
static void init_sprite_tables(u8 x);

/* sprites que el cargador creo en este frame: bit = ranura (verificacion) */
u8 spr_spawned;

/* LoadNormalSprite / _02A8DF .. CODE_02A9C9: crear el sprite y del nivel
   (index = m2, col/scr = m0/m1: columna y pantalla). Devuelve 0 si no hubo ranura
   (el cargador termina: RTS). */
static int spawn(u8 y, u8 index, u8 col, u8 scr, u8 state)
{
    const u8 *r = spr_level + y;            /* r[0] = byte0 */
    u8 mem = R8(wm_SpriteMemory), num = r[2], x, stop;
    x = tx_SpriteSlotMax[mem];
    stop = tx_SpriteSlotStart[mem];
    if (num == tx_ReservedSprite1[mem]) {
        x = tx_SpriteSlotMax1[mem];
        stop = tx_SpriteSlotStart1[mem];
    }
    if (num == tx_ReservedSprite2[mem] && (num != 0x64 || (col & 0x10))) {
        x = tx_SpriteSlotMax2[mem];
        stop = 0xFF;
    }
    for (;;) {
        if (!R8(wm_SpriteStatus + x))
            break;
        x--;
        if (x == stop) {
            if (num == 0x7B) {              /* cinta de meta: otra pasada */
                if (!mario_unsupported) mario_unsupported = MARIO_UNSUP_TILE;
                return 0;
            }
            W8(wm_SprLoadStatus + index, 0);    /* sin ranura: se reintenta */
            return 0;
        }
    }
    /* CODE_02A93C / CODE_02A95B: nivel horizontal */
    W8(wm_SpriteYLo + x, r[0] & 0xF0);
    W8(wm_SpriteYHi + x, r[0] & 0x0D);
    W8(wm_SpriteXLo + x, col);
    W8(wm_SpriteXHi + x, scr);
    W8(wm_SpriteStatus + x, state);
    W8(wm_SpriteNum + x, state == 0x09 ? (u8)(num - 0xDA + 4) : num);
    W8(wm_SprIndexInLvl + x, index);
    if (R8(wm_SilverPowTimer) && !mario_unsupported)
        mario_unsupported = MARIO_UNSUP_TILE;
    init_sprite_tables(x);
    W8(wm_OffscreenHorz + x, 1);
    W8(wm_DisSprCapeContact + x, 4);
    spr_spawned |= (u8)(1 << x);
    return 1;
}

/* LoadSprFromLevel (nivel horizontal) */
void sprite_load_level(void)
{
    u8 d, col, scrn, y, index;
    u16 c;
    spr_spawned = 0;
    if (R8(wm_FrameA) & 0x01)
        return;
    d = R8(wm_Layer1ScrollDir);
    c = (u16)(R8(wm_Bg1HOfs) + tx_02A7F6[d]);
    col = (u8)(c & 0xF0);                   /* m0: columna que entra */
    scrn = (u8)(R8(wm_Bg1HOfs + 1) + tx_02A7F9[d] + (c >> 8));   /* m1: pantalla */
    if (NEG(scrn))
        return;
    for (y = 1, index = 0; spr_level[y] != 0xFF; y += 3, index++) {
        u8 b0 = spr_level[y], b1 = spr_level[y + 1], num = spr_level[y + 2];
        u8 scr = (u8)(((b0 << 3) & 0x10) | (b1 & 0x0F));
        if (scr < scrn)
            continue;
        if (scr != scrn)
            return;                         /* ordenados por pantalla */
        if ((b1 & 0xF0) != col || R8(wm_SprLoadStatus + index))
            continue;
        W8(wm_SprLoadStatus + index, 1);
        if (num >= 0xE7 || num == 0xDE || num == 0xE0 || (num >= 0xCB && num < 0xDA)
            || num >= 0xE1 || (num >= 0xC9 && num < 0xCB)) {
            if (!mario_unsupported) mario_unsupported = MARIO_UNSUP_TILE;
            continue;                       /* generadores, plataformas, lanzadores */
        }
        if (!spawn(y, index, col, scrn, num >= 0xDA ? 0x09 : 0x01))
            return;
    }
}

/* ------------------------------------------------------------------ */
/* Motor de sprites (sprite_1-main.s, sprite_3-1.s), lo que usa el Rex.
   Convenciones de mario.c: x = ranura (el registro X del 65816). */

#define SPR(t, x)       R8((t) + (x))
#define SETSPR(t, x, v) W8((t) + (x), (v))

static void spr_unsup(void) { if (!mario_unsupported) mario_unsupported = MARIO_UNSUP_TILE; }

/* ZeroSpriteTables + LoadSpriteTables (sprite_tables.s) */
static void init_sprite_tables(u8 x)
{
    static const u16 zero[] = {
        wm_SprInWaterTbl, wm_SprBehindScrn, wm_SpriteState, wm_SpriteMiscTbl3,
        wm_SpriteMiscTbl4, wm_SpriteMiscTbl5, wm_SpriteDir, wm_SprObjStatus,
        wm_SpriteOffTbl, wm_SpriteGfxTbl, wm_SpriteDecTbl1, wm_SpriteDecTbl2,
        wm_SpriteDecTbl3, wm_SpriteDecTbl4, wm_DisSprCapeContact, wm_SprChainKillTbl,
        wm_SpriteMiscTbl6, wm_SpriteSpeedX, wm_SpriteXAcc, wm_SpriteSpeedY,
        wm_SpriteYAcc, wm_SpriteInterTbl, wm_SpriteEatenTbl, wm_SpriteDecTbl6,
        wm_Tweaker1656, wm_Tweaker1662, wm_Tweaker166E, wm_Tweaker167A,
        wm_Tweaker1686, wm_SprStompImmuneTbl, wm_SpriteMiscTbl8, wm_SpriteMiscTbl7,
        wm_SpriteMiscTbl1, wm_1FD6 };
    u8 n = SPR(wm_SpriteNum, x);
    unsigned k;
    for (k = 0; k < sizeof zero / sizeof zero[0]; k++)
        SETSPR(zero[k], x, 0);
    SETSPR(wm_OffscreenHorz, x, 1);
    SETSPR(wm_SpritePal, x, tx_166E[n] & 0x0F);
    SETSPR(wm_Tweaker1656, x, tx_1656[n]);
    SETSPR(wm_Tweaker1662, x, tx_1662[n]);
    SETSPR(wm_Tweaker166E, x, tx_166E[n]);
    SETSPR(wm_Tweaker167A, x, tx_167A[n]);
    SETSPR(wm_Tweaker1686, x, tx_1686[n]);
    SETSPR(wm_Tweaker190F, x, tx_190F[n]);
}

/* SubHorizPos: Y = 1 si Mario esta a la izquierda */
static u8 sub_horiz_pos(u8 x)
{
    u16 m = R16(wm_PlayerXPosLv);
    u16 s = (u16)(SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8);
    W8(m15, (u8)(m - s));
    return (u8)(((u16)(m - s) & 0x8000) ? 1 : 0);
}

/* SubSprYPosNoGrvty (o con o = $0C, SubSprXPosNoGrvty): velocidad 4.4 a
   la posicion; las tablas X estan $0C bytes despues de las Y */
static void spr_pos_axis(u8 x, u8 o)
{
    u8 v = SPR(wm_SpriteSpeedY + o, x), c, hi, lo, d;
    unsigned sum;
    if (!v) {
        W8(wm_SprPixelMove, 0);
        return;
    }
    sum = (unsigned)(u8)(v << 4) + SPR(wm_SpriteYAcc + o, x);
    SETSPR(wm_SpriteYAcc + o, x, (u8)sum);
    c = (u8)(sum >> 8);
    d = (u8)(v >> 4);
    hi = 0;
    if (d >= 8) { d |= 0xF0; hi = 0xFF; }
    sum = (unsigned)d + SPR(wm_SpriteYLo + o, x) + c;
    lo = (u8)sum;
    SETSPR(wm_SpriteYLo + o, x, lo);
    SETSPR(wm_SpriteYHi + o, x, (u8)(hi + SPR(wm_SpriteYHi + o, x) + (sum >> 8)));
    W8(wm_SprPixelMove, (u8)(d + c));
}

/* CODE_019441 / _01944D / CODE_0194BF: el bloque bajo el punto de choque
   y (0..3: derecha, izquierda, abajo, arriba). Deja m0, m10-m13, m15. */
static u8 spr_tile(u8 x, u8 y)
{
    u16 py, px, o;
    u8 a;
    W8(m15, y);
    y = (u8)(((SPR(wm_Tweaker1656, x) & 0x0F) << 2) + y);
    if ((u8)((R8(wm_TempTileGen) + 1) & R8(wm_IsVerticalLvl))) { spr_unsup(); return 0; }
    py = (u16)((SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8) + tx_SprObjClipY[y]);
    W8(m12, (u8)py);
    W8(m13, py >> 8);
    W8(m0, py & 0xF0);
    if (py >= 0x1B0) goto out;
    px = (u16)((SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8) + tx_SprObjClipX[y]);
    W8(m10, (u8)px);
    W8(m1, (u8)px);
    W8(m11, px >> 8);
    if ((px & 0x8000) || (px >> 8) >= R8(wm_ScreensInLvl)) goto out;
    o = (u16)((px >> 8) * 0x1B0 + (py & 0x1F0) + ((px >> 4) & 0x0F));
    W8(wm_Map16NumLo, map16_lo[o]);
    a = map16_hi[o];
    if (a ? (map16_lo[o] == 0x32 || map16_lo[o] == 0x2F)
          : (map16_lo[o] == 0x29 || map16_lo[o] == 0x2B || (u8)(map16_lo[o] - 0xEC) < 0x10))
        spr_unsup();                        /* bloques de los interruptores P */
    return a;
out:                                        /* CODE_0194B4 */
    W8(wm_Map16NumLo, 0);
    W8(wm_SprMoveDownPixels, 0);
    return 0;
}

/* _019435 */
static void spr_obj_bit(u8 x)
{
    SETSPR(wm_SprObjStatus, x, SPR(wm_SprObjStatus, x) | tx_019134[R8(m15)]);
}

/* CODE_0192C9: arriba / abajo */
static void spr_obj_vert(u8 x)
{
    u8 y, a, t;
    y = NEG(SPR(wm_SpriteSpeedY, x)) ? 3 : 2;
    a = spr_tile(x, y);
    W8(wm_SprOnTileYHi, a);
    W8(wm_SprOnTileYLo, R8(wm_Map16NumLo));
    if (!a)
        return;
    t = R8(wm_Map16NumLo);
    if (y != 2) {                           /* hacia arriba: techo */
        if (t < 0x11)
            return;
        if (t >= 0x6E && (t < R8(wm_LowestSolidSprTile) || t >= R8(wm_HighestSolidSprTile)))
            return;
        spr_obj_bit(x);                     /* CODE_019425 (BlockXPos...: sin uso aca) */
        W8(wm_SprOnBreakableBlk, t);
        return;
    }
    /* CODE_019310 -> CODE_01933B: el suelo */
    if (t >= 0x59 && t < 0x5C && (R8(0x1931) == 0x0E || R8(0x1931) == 0x03)) { spr_unsup(); return; }
    if (t < 0x11) {                         /* CODE_0193B0 */
        if ((R8(m12) & 0x0F) >= 5)
            return;
        goto l_B8;
    }
    if (t < 0x6E)
        goto l_B8;
    if (t >= 0xD8) { spr_unsup(); return; } /* CODE_019386 */
    {   /* pendiente: CODE_00FA19 */
        u8 s8 = T8(R16(wm_SlopeSteepness) + (u8)(t - 0x6E)), h;
        u16 idx = (u16)((s8 << 4) | (R8(m10) & 0x0F));
        W8(m8, s8);
        W8(m0, R8(m12) & 0x0F);
        h = T8(DATA_00E632 + idx);
        if (h == 0x10)
            return;
        if (h > 0x10) { spr_unsup(); return; }     /* CODE_019386 */
        if (R8(m0) < 0x0C && R8(m0) < h)
            return;
        W8(wm_SprMoveDownPixels, h);
        a = T8(DATA_00E53D + s8);
        SETSPR(wm_SpriteSlopeTbl, x, a);
        if (a == 0x04 || a == 0xFC) {
            if (NEG((u8)(a ^ SPR(wm_SpriteSpeedX, x))) && SPR(wm_SpriteSpeedX, x)) {
                spr_unsup();                /* FlipSpriteDir + CODE_03C1CA */
                return;
            }
            spr_unsup();                    /* CODE_03C1CA */
            return;
        }
    }
l_B8:                                       /* _0193B8 */
    if (!(SPR(wm_Tweaker1686, x) & 0x04)) {
        a = SPR(wm_SpriteStatus, x);
        if (a == 0x02 || a == 0x05 || a == 0x0B)
            return;
        t = R8(wm_Map16NumLo);
        if ((t == 0x0C || t == 0x0D) && !(R8(wm_FrameA) & 0x03)) { spr_unsup(); return; }
        if (!SPR(wm_SpriteEatenTbl, x))
            SETSPR(wm_SpriteYLo, x, (u8)((SPR(wm_SpriteYLo, x) & 0xF0) + R8(wm_SprMoveDownPixels)));
    }
    spr_obj_bit(x);
}

/* CODE_019140 (nivel horizontal, capa 1, sin agua) */
static void spr_obj_interact(u8 x)
{
    u8 a;
    W8(wm_SprMoveDownPixels, 0);
    SETSPR(wm_SprObjStatus, x, 0);
    SETSPR(wm_SpriteSlopeTbl, x, 0);
    W8(wm_TempTileGen, 0);
    W8(wm_CheckSprInter, SPR(wm_SprInWaterTbl, x));
    SETSPR(wm_SprInWaterTbl, x, 0);
    /* CODE_019211 */
    if (R8(wm_SpriteBuoyancy) || NEG(R8(wm_IsVerticalLvl))) { spr_unsup(); return; }
    if (!NEG(SPR(wm_Tweaker1686, x))) {
        spr_obj_vert(x);
        if (NEG(SPR(wm_Tweaker190F, x)) && !(SPR(wm_SpriteSpeedX, x) | SPR(wm_SpriteDecTbl5, x))) {
            spr_unsup();                    /* lados con la velocidad X a 0 */
            return;
        }
        if (SPR(wm_SpriteSpeedX, x)) {      /* CODE_019288: el lado hacia donde va */
            u8 y = (u8)(((SPR(wm_SpriteSpeedX, x) << 1) | (SPR(wm_SpriteSpeedX, x) >> 7)) & 1);
            a = spr_tile(x, y);
            W8(wm_SprOnTileXHi, a);
            if (a && R8(wm_Map16NumLo) >= 0x11 && R8(wm_Map16NumLo) < 0x6E) {
                spr_obj_bit(x);
                W8(wm_MirBlkCheck, R8(wm_Map16NumLo));
            }
            W8(wm_SprOnTileXLo, R8(wm_Map16NumLo));
        }
    }
    /* ++ */
    if (NEG(SPR(wm_Tweaker190F, x)) && (SPR(wm_SprObjStatus, x) & 0x03)) {
        spr_unsup();                        /* empujar fuera de la pared */
        return;
    }
    if (SPR(wm_SprInWaterTbl, x) != R8(wm_CheckSprInter))
        spr_unsup();                        /* entrar/salir del agua */
}

/* SubUpdateSprPos */
static void spr_update_pos(u8 x)
{
    u8 v, keep;
    spr_pos_axis(x, 0);
    if (SPR(wm_SprInWaterTbl, x)) { spr_unsup(); return; }
    v = (u8)(SPR(wm_SpriteSpeedY, x) + tx_019030[0]);
    if (!NEG(v) && v >= tx_01902E[0])
        v = tx_01902E[0];
    SETSPR(wm_SpriteSpeedY, x, v);
    keep = SPR(wm_SpriteSpeedX, x);
    spr_pos_axis(x, 0x0C);
    SETSPR(wm_SpriteSpeedX, x, keep);
    if (SPR(wm_SpriteInterTbl, x))
        SETSPR(wm_SprObjStatus, x, 0);
    else
        spr_obj_interact(x);
}

/* GetDrawInfoBnk3: solo los flags de fuera de pantalla (el dibujo, en la
   etapa 6). Devuelve 0 si el sprite esta lejos (PLA/PLA: no se dibuja). */
static int get_draw_info(u8 x)
{
    u16 sx = (u16)(SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8), cam = R16(wm_Bg1HOfs);
    u8 y;
    SETSPR(wm_OffscreenVert, x, 0);
    SETSPR(wm_OffscreenHorz, x, (u8)((((sx - cam) >> 8) & 0xFF) != 0 ? 1 : 0));
    SETSPR(wm_SpriteOffTbl, x, (u8)((u16)(sx - cam + 0x40) >= 0x180));
    if (SPR(wm_SpriteOffTbl, x))
        return 0;
    y = (SPR(wm_Tweaker1662, x) & 0x20) ? 1 : 0;
    for (;;) {
        u16 syy = (u16)((SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8) + tx_03B75C[y]);
        if (((syy - R16(wm_Bg1VOfs)) >> 8) & 0xFF)
            SETSPR(wm_OffscreenVert, x, SPR(wm_OffscreenVert, x) | tx_03B75E[y]);
        if (y == 0)
            break;
        y--;
    }
    return 1;
}

/* SubOffscreen0Bnk3 (nivel horizontal) */
static void sub_offscreen3(u8 x)
{
    u8 y, e = 0;
    if (!(SPR(wm_OffscreenHorz, x) | SPR(wm_OffscreenVert, x)))
        return;
    if ((u16)((SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8) + 0x50) >= 0x200
        && !NEG((u8)((((SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8) + 0x50) >> 8))))
        e = 1;
    if (!e) {
        u16 lim;
        if (SPR(wm_Tweaker167A, x) & 0x04)
            return;
        y = R8(wm_FrameA) & 0x01;           /* m3 = 0 */
        lim = (u16)(R16(wm_Bg1HOfs) + (tx_03B83F[y] | tx_03B847[y] << 8));
        {
            s16 d = (s16)(u16)(((lim >> 8) - SPR(wm_SpriteXHi, x)
                                - ((u8)lim < SPR(wm_SpriteXLo, x) ? 1 : 0)) << 8);
            u8 m0v = (u8)((u16)d >> 8);
            if (y)
                m0v ^= 0x80;
            if (!NEG(m0v))
                return;
        }
    }
    if (SPR(wm_SpriteStatus, x) >= 0x08 && SPR(wm_SprIndexInLvl, x) != 0xFF)
        W8(wm_SprLoadStatus + SPR(wm_SprIndexInLvl, x), 0);
    SETSPR(wm_SpriteStatus, x, 0);
}

/* RexMainRt, sin el contacto con Mario ni con otros sprites (pendiente:
   MarioSprInteract, SprSprInteract) */
static void rex_main(u8 x)
{
    u8 a, y;
    /* RexGfxRt: la pose y los flags de pantalla */
    if (SPR(wm_SpriteDecTbl3, x)) SETSPR(wm_SpriteGfxTbl, x, 5);
    if (SPR(wm_DisSprCapeContact, x)) SETSPR(wm_SpriteGfxTbl, x, 2);
    get_draw_info(x);
    if (SPR(wm_SpriteStatus, x) != 0x08 || R8(wm_SpritesLocked))
        return;
    a = SPR(wm_SpriteDecTbl3, x);
    if (a) {
        SETSPR(wm_SpriteEatenTbl, x, a);
        if (a == 1)
            SETSPR(wm_SpriteStatus, x, 0);
        return;
    }
    sub_offscreen3(x);
    SETSPR(wm_SpriteMiscTbl6, x, SPR(wm_SpriteMiscTbl6, x) + 1);
    a = (u8)(SPR(wm_SpriteMiscTbl6, x) >> 2);
    a = SPR(wm_SpriteState, x) ? (u8)((a & 1) + 3) : (u8)((a >> 1) & 1);
    SETSPR(wm_SpriteGfxTbl, x, a);
    if (SPR(wm_SprObjStatus, x) & 0x04) {
        SETSPR(wm_SpriteSpeedY, x, 0x10);
        y = SPR(wm_SpriteDir, x);
        if (SPR(wm_SpriteState, x))
            y += 2;
        SETSPR(wm_SpriteSpeedX, x, tx_RexSpeed[y]);
    }
    if (!SPR(wm_DisSprCapeContact, x))
        spr_update_pos(x);
    if (SPR(wm_SprObjStatus, x) & 0x03)
        SETSPR(wm_SpriteDir, x, SPR(wm_SpriteDir, x) ^ 1);
}

/* CODE_0180D2 (los temporizadores) + HandleSprite, para una ranura */
void sprite_run(u8 x)
{
    u8 st = SPR(wm_SpriteStatus, x);
    W8(wm_SprProcessIndex, x);
    if (st && !R8(wm_SpritesLocked)) {
        static const u16 dec[] = { wm_SpriteDecTbl1, wm_SpriteDecTbl2, wm_SpriteDecTbl3,
                                   wm_SpriteDecTbl4, wm_DisSprCapeContact, wm_SpriteDecTbl5,
                                   wm_SpriteDecTbl6 };
        unsigned k;
        for (k = 0; k < sizeof dec / sizeof dec[0]; k++)
            if (SPR(dec[k], x))
                SETSPR(dec[k], x, SPR(dec[k], x) - 1);
    }
    if (!st) {                              /* EraseSprite */
        SETSPR(wm_SprIndexInLvl, x, 0xFF);
        return;
    }
    if (SPR(wm_SpriteNum, x) != 0xAB) { spr_unsup(); return; }
    if (st == 0x01) {                       /* CallSpriteInit: Rex = _FaceMario */
        SETSPR(wm_SpriteStatus, x, 0x08);
        SETSPR(wm_SpriteDir, x, sub_horiz_pos(x));
        return;
    }
    if (st == 0x08) {
        rex_main(x);
        return;
    }
    spr_unsup();                            /* aplastado, muerto... */
}
