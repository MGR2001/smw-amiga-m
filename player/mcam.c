/*
 * mcam.c - la camara de un nivel horizontal: CODE_00F6DB de player.s
 * (SMW U). Ver mario.h.
 *
 * Corre al principio del frame, antes que los graficos y la fisica de
 * Mario (orden de CODE_00A295), con la posicion del frame anterior:
 *   - Bg1HOfs/VOfs a partir de L1NextPosX/Y y de donde esta Mario
 *     respecto de la zona muerta (PosToScrollScreen +- $0C);
 *   - scroll vertical (CODE_00F7F4) y el ajuste con L/R (CODE_00F8AB);
 *   - la capa 2 a su velocidad (media en Yoshi's Island 1: HorzScrollLyr2
 *     = VertScrollLyr2 = 2, AGENTS.md §9 etapa 4 punto 1);
 *   - L1CurXChange... (cuanto se movio cada capa) y L1NextPosX... para el
 *     frame siguiente.
 * El nivel vertical no esta portado.
 */
#include "mario.h"
#include "gen/smwram.h"
#include "gen/smwtab.h"
#include "smwmac.h"

#define S16(v)  ((s16)(u16)(v))

/* build de la Amiga: camera_F6DB en player/logic68k.s, que llama a estas
   dos (dejan de ser static) */
#if defined(__VBCC__) && !defined(NOASM)
#define LOGIC68K 1
#define MCS
void f8ab(void);
u16 f7f4(u16 limit, u16 bg1v);
#else
#define MCS static
#endif

/* CODE_00F8AB: la zona muerta despues de mover la camara con L/R */
MCS void f8ab(void)
{
    u8 x, y;
    u16 a, v2 = R16(m2);
    if (R8(wm_LRScrollFlag))
        return;
    x = R8(wm_LRScrollStop);
    y = 0x08;
    if (S16(R16(wm_PosToScrollScreen) - T16X(DATA_00F6B3, x)) < 0)
        y = 0x0A;
    if (!((T16X(DATA_00F6BF, y) ^ v2) & 0x8000))
        return;
    if (!((T16X(DATA_00F6BF, x) ^ v2) & 0x8000))
        return;
    a = (u16)(v2 + T16X(DATA_00F6CF, y));
    if (!a)
        return;
    W16(m2, a);
    W8(wm_LRMoveCamera, y);
}

/* CODE_00F7F4 / CODE_00F7FA: scroll vertical. Entra y sale Bg1VOfs en una
   variable (nativo: en el 68000 cada valor de 16 bits de ram[] cuesta ~50
   ciclos); escribe en la RAM lo mismo que el ROM. */
#ifdef LOGIC68K
u16 f7f4_c(u16 limit, u16 bg1v);    /* la referencia; f7f4 (asm) cae aca hacia arriba */
u16 f7f4_c(u16 limit, u16 bg1v)
#else
MCS u16 f7f4(u16 limit, u16 bg1v)
#endif
{
    u8 y, x;
    u16 a, v0, v2;

    if (!R8(wm_VertScrollHead))
        return bg1v;
    W16(m4, limit);
    y = 0;
    v0 = (u16)(R16(wm_MarioYPos) - bg1v);
    W16(m0, v0);
    if (S16(v0 - 0x0070) >= 0)
        y = 2;
    W8(wm_Layer1ScrollDir, y);
    W8(wm_Layer2ScrollDir, y);
    v2 = (u16)(v0 - T16X(DATA_00F69F, y));
    if (!((v2 ^ T16X(DATA_00F6A3, y)) & 0x8000)) {
        y = 2;
        v2 = 0;
    }
    W16(m2, v2);
    if (!(v2 & 0x8000)) {
        W8(wm_ScrScrollToPlayer, 0);
        a = v2;
        goto l_F883;
    }
    /* CODE_00F82A: hacia arriba. Con X != 0 (pared, planeo, trepar, globo,
       nube, Yoshi con alas, nadar volando) el ROM salta a `++` =
       STX wm_EnableVertScroll y hace scroll con la Y de siempre: no es un
       RTS. Con X = 0, CODE_00F875 si VertScrollHead = 1 o si el scroll
       vertical ya estaba habilitado; si no, Y = 4. */
    x = R8(wm_WallWalkStatus);
    if (x < 0x06)
        x = (u8)((R8(wm_YoshiHasWingsB) >> 1) | R8(wm_GlideTimer) | R8(wm_IsClimbing)
                 | R8(wm_PBalloonFrame) | R8(wm_IsInLakituCloud) | R8(wm_BouncingWithYoshi));
    if (!x) {
        if (R8(wm_OnYoshi) && R8(wm_YoshiHasWings) >= 0x02)
            x = R8(wm_YoshiHasWings);
        else if (R8(wm_IsSwimming) && R8(wm_IsFlying))
            x = R8(wm_IsFlying);
    }
    if (x) {
        W8(wm_EnableVertScroll, x);
    } else if (R8(wm_VertScrollHead) == 1 || R8(wm_EnableVertScroll)) {
        if (!R8(wm_ScrScrollToPlayer)) {    /* CODE_00F875 */
            if (R8(wm_IsFlying))
                return bg1v;
            W8(wm_ScrScrollToPlayer, R8(wm_ScrScrollToPlayer) + 1);
        }
    } else {
        y = 4;
    }
    a = v2;                                 /* _00F881 */
l_F883:
    {
        u16 v = T16X(DATA_00F6A7, y);
        if (!(((u16)(a - v) ^ v) & 0x8000))
            a = v;                          /* limita la velocidad */
        a = (u16)(a + bg1v);
        if (S16(a - T16X(DATA_00F6AD, y)) < 0)
            a = T16X(DATA_00F6AD, y);
        bg1v = a;
    }
    if (S16(limit - bg1v) >= 0)
        return bg1v;
    W8(wm_EnableVertScroll, 0);
    return limit;
}

/* CODE_00F6DB */
#ifdef LOGIC68K
void camera_F6DB_c(void);   /* la referencia; el asm cae aca en nivel vertical */
void camera_F6DB_c(void)
#else
void camera_F6DB(void)
#endif
{
    u8 y;
    u16 a, v0, v2, pts, bg1h, bg1v, bg2h, bg2v;

    pts = R16(wm_PosToScrollScreen);
    W16(wm_CanScrollScreen, pts - 0x000C);
    W16(wm_CanScrollScreen + 2, pts - 0x000C + 0x0018);
    bg1h = R16(wm_L1NextPosX);
    bg1v = R16(wm_L1NextPosY);
    bg2h = R16(wm_L2NextPosX);
    bg2v = R16(wm_L2NextPosY);
    if (R8(wm_IsVerticalLvl) & 1) {         /* CODE_00F75C */
        if (!mario_unsupported) mario_unsupported = MARIO_UNSUP_LAYER;
        return;
    }
    W16(wm_Bg1HOfs, bg1h);                  /* f8ab no la lee; se escribe igual */
    bg1v = f7f4(0x00C0, bg1v);
    if (R8(wm_HorzScrollHead)) {
        y = 2;
        v0 = (u16)(R16(wm_MarioXPos) - bg1h);
        W16(m0, v0);
        if (S16(v0 - pts) < 0)
            y = 0;
        W8(wm_Layer1ScrollDir, y);
        W8(wm_Layer2ScrollDir, y);
        a = (u16)(v0 - (u16)(pts - 0x000C + (y ? 0x0018 : 0)));
        if (a && ((a ^ T16X(DATA_00F6A3, y)) & 0x8000)) {
            W16(m2, a);
            f8ab();
            v2 = R16(m2);
            a = (u16)(v2 + bg1h);
            if (a & 0x8000)
                a = 0;
            bg1h = a;
            a = (u16)(((R16(wm_LastScreenHorz) - 1) & 0xFF) << 8);  /* DEC A / XBA / AND */
            if (a & 0x8000)
                a = 0x0080;
            if (S16(a - bg1h) < 0)
                bg1h = a;
        }
    }
    /* _00F79D: la capa 2 */
    y = R8(wm_HorzScrollLyr2);
    if (y)
        bg2h = (y != 1) ? (u16)(bg1h >> 1) : bg1h;
    y = R8(wm_VertScrollLyr2);
    if (y) {
        a = bg1v;
        if (y == 2)
            a >>= 1;
        else if (y != 1)
            a >>= 5;
        bg2v = (u16)(a + R16(wm_VertL2ScrollLength));
    }
    W16(wm_Bg1HOfs, bg1h);
    W16(wm_Bg1VOfs, bg1v);
    W16(wm_Bg2HOfs, bg2h);
    W16(wm_Bg2VOfs, bg2v);
    W8(wm_L1CurXChange, R8(wm_Bg1HOfs) - R8(wm_L1NextPosX));
    W8(wm_L1CurYChange, R8(wm_Bg1VOfs) - R8(wm_L1NextPosY));
    W8(wm_L2CurXChange, R8(wm_Bg2HOfs) - R8(wm_L2NextPosX));
    W8(wm_L2CurYChange, R8(wm_Bg2VOfs) - R8(wm_L2NextPosY));
    /* L1NextPosX..L2NextPosY = Bg1HOfs..Bg2VOfs (8 bytes), con las
       variables: el bucle con indice costaba ~1000 ciclos en el 68000 */
    W16(wm_L1NextPosX, bg1h);
    W16(wm_L1NextPosX + 2, bg1v);
    W16(wm_L1NextPosX + 4, bg2h);
    W16(wm_L1NextPosX + 6, bg2v);
}
