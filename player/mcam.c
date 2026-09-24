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

/* CODE_00F8AB: la zona muerta despues de mover la camara con L/R */
static void f8ab(void)
{
    u8 x, y;
    u16 a, v2 = R16(m2);
    if (R8(wm_LRScrollFlag))
        return;
    x = R8(wm_LRScrollStop);
    y = 0x08;
    if (S16(R16(wm_PosToScrollScreen) - T16(DATA_00F6B3 + x)) < 0)
        y = 0x0A;
    if (!((T16(DATA_00F6BF + y) ^ v2) & 0x8000))
        return;
    if (!((T16(DATA_00F6BF + x) ^ v2) & 0x8000))
        return;
    a = (u16)(v2 + T16(DATA_00F6CF + y));
    if (!a)
        return;
    W16(m2, a);
    W8(wm_LRMoveCamera, y);
}

/* CODE_00F7F4 / CODE_00F7FA: scroll vertical. m4 = tope de abajo. */
static void f7f4(u16 limit)
{
    u8 y, x;
    u16 a, v0, v2;

    if (!R8(wm_VertScrollHead))
        return;
    W16(m4, limit);
    y = 0;
    v0 = (u16)(R16(wm_MarioYPos) - R16(wm_Bg1VOfs));
    W16(m0, v0);
    if (S16(v0 - 0x0070) >= 0)
        y = 2;
    W8(wm_Layer1ScrollDir, y);
    W8(wm_Layer2ScrollDir, y);
    v2 = (u16)(v0 - T16(DATA_00F69F + y));
    W16(m2, v2);
    if (!((v2 ^ T16(DATA_00F6A3 + y)) & 0x8000)) {
        y = 2;
        v2 = 0;
        W16(m2, 0);
    }
    if (!(v2 & 0x8000)) {
        W8(wm_ScrScrollToPlayer, 0);
        a = v2;
        goto l_F883;
    }
    /* CODE_00F82A: hacia arriba, solo en algunos casos */
    x = R8(wm_WallWalkStatus);
    if (x < 0x06)
        x = (u8)((R8(wm_YoshiHasWingsB) >> 1) | R8(wm_GlideTimer) | R8(wm_IsClimbing)
                 | R8(wm_PBalloonFrame) | R8(wm_IsInLakituCloud) | R8(wm_BouncingWithYoshi));
    if (x)
        return;
    if (R8(wm_OnYoshi) && R8(wm_YoshiHasWings) >= 0x02)
        return;
    if (R8(wm_IsSwimming) && R8(wm_IsFlying))
        return;
    if (R8(wm_VertScrollHead) == 1) {       /* CODE_00F875 */
        if (!R8(wm_ScrScrollToPlayer)) {
            if (R8(wm_IsFlying))
                return;
            W8(wm_ScrScrollToPlayer, R8(wm_ScrScrollToPlayer) + 1);
        }
    } else if (!R8(wm_EnableVertScroll)) {
        y = 4;
    }
    a = v2;                                 /* _00F881 */
l_F883:
    {
        u16 v = T16(DATA_00F6A7 + y);
        if (!(((u16)(a - v) ^ v) & 0x8000))
            a = v;                          /* limita la velocidad */
        a = (u16)(a + R16(wm_Bg1VOfs));
        if (S16(a - T16(DATA_00F6AD + y)) < 0)
            a = T16(DATA_00F6AD + y);
        W16(wm_Bg1VOfs, a);
    }
    if (S16(R16(m4) - R16(wm_Bg1VOfs)) >= 0)
        return;
    W16(wm_Bg1VOfs, R16(m4));
    W8(wm_EnableVertScroll, 0);
}

/* CODE_00F6DB */
void camera_F6DB(void)
{
    u8 y;
    u16 a, v0, v2;
    int k;

    W16(wm_CanScrollScreen, R16(wm_PosToScrollScreen) - 0x000C);
    W16(wm_CanScrollScreen + 2, R16(wm_PosToScrollScreen) - 0x000C + 0x0018);
    W16(wm_Bg1HOfs, R16(wm_L1NextPosX));
    W16(wm_Bg1VOfs, R16(wm_L1NextPosY));
    W16(wm_Bg2HOfs, R16(wm_L2NextPosX));
    W16(wm_Bg2VOfs, R16(wm_L2NextPosY));
    if (R8(wm_IsVerticalLvl) & 1) {         /* CODE_00F75C */
        if (!mario_unsupported) mario_unsupported = MARIO_UNSUP_LAYER;
        return;
    }
    f7f4(0x00C0);
    if (R8(wm_HorzScrollHead)) {
        y = 2;
        v0 = (u16)(R16(wm_MarioXPos) - R16(wm_Bg1HOfs));
        W16(m0, v0);
        if (S16(v0 - R16(wm_PosToScrollScreen)) < 0)
            y = 0;
        W8(wm_Layer1ScrollDir, y);
        W8(wm_Layer2ScrollDir, y);
        a = (u16)(v0 - R16(wm_CanScrollScreen + y));
        if (a && ((a ^ T16(DATA_00F6A3 + y)) & 0x8000)) {
            W16(m2, a);
            f8ab();
            v2 = R16(m2);
            a = (u16)(v2 + R16(wm_Bg1HOfs));
            if (a & 0x8000)
                a = 0;
            W16(wm_Bg1HOfs, a);
            a = (u16)(((R16(wm_LastScreenHorz) - 1) & 0xFF) << 8);  /* DEC A / XBA / AND */
            if (a & 0x8000)
                a = 0x0080;
            if (S16(a - R16(wm_Bg1HOfs)) < 0)
                W16(wm_Bg1HOfs, a);
        }
    }
    /* _00F79D: la capa 2 */
    y = R8(wm_HorzScrollLyr2);
    if (y) {
        a = R16(wm_Bg1HOfs);
        if (y != 1)
            a >>= 1;
        W16(wm_Bg2HOfs, a);
    }
    y = R8(wm_VertScrollLyr2);
    if (y) {
        a = R16(wm_Bg1VOfs);
        if (y == 2)
            a >>= 1;
        else if (y != 1)
            a >>= 5;
        W16(wm_Bg2VOfs, a + R16(wm_VertL2ScrollLength));
    }
    W8(wm_L1CurXChange, R8(wm_Bg1HOfs) - R8(wm_L1NextPosX));
    W8(wm_L1CurYChange, R8(wm_Bg1VOfs) - R8(wm_L1NextPosY));
    W8(wm_L2CurXChange, R8(wm_Bg2HOfs) - R8(wm_L2NextPosX));
    W8(wm_L2CurYChange, R8(wm_Bg2VOfs) - R8(wm_L2NextPosY));
    for (k = 7; k >= 0; k--)
        W8(wm_L1NextPosX + k, R8(wm_Bg1HOfs + k));
}
