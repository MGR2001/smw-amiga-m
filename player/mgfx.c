/*
 * mgfx.c - gráficos de Mario: CODE_00E2BD de player.s (SMW U). Ver mario.h.
 *
 * Corre al principio del frame, ANTES que la fisica (orden de CODE_00A295:
 * camara -> E2BD -> C47E -> sprites), con la posicion del frame anterior:
 *   - paleta (estrella, parpadeo) y baja el temporizador de la estrella;
 *   - MarioScrPosX/Y (posicion en pantalla: la usa la colision despues);
 *   - las 4 entradas de OAM de Mario (tile, x, y, atributos, tamaño) en
 *     wm_OamSlot ($0300...) y wm_OamSize ($0460...), como en la SNES;
 *   - CODE_00F636: los punteros de DMA a los gráficos de Mario (wm_0D85),
 *     que dicen QUE imagen va en cada tile.
 * La capa (PowerUp 2) y Yoshi suelto no estan portados.
 */
#include "mario.h"
#include "gen/smwram.h"
#include "gen/smwtab.h"
#include "smwmac.h"

#ifndef DATA_00E2A2
#define DATA_00E2A2 0xE2A2      /* .DW de punteros a paletas: el generador no lo lee */
#endif
#ifndef MarioPalIndex
#define MarioPalIndex 0xE18C    /* .DB $00,$40: muy corto para buscarlo en la ROM */
#endif

#define OAM_X(y)    (0x0300 + (y))  /* wm_OamSlot.1.XPos,Y */
#define OAM_Y(y)    (0x0301 + (y))
#define OAM_T(y)    (0x0302 + (y))
#define OAM_P(y)    (0x0303 + (y))
#define OAM_SIZE    0x0460          /* wm_OamSize.1 */

/* CODE_00F636: punteros de DMA a los gráficos del jugador */
static void f636(u8 m10v, u8 m11v)
{
    u16 a;
    int c;

    a = (u16)(R8(m9) | (m10v << 8));
    c = (a | 0x0800) == a;                  /* CMP / BEQ + / CLC */
    a &= 0xF700;
    a = (u16)((a >> 1) | (c ? 0x8000 : 0));  /* ROR */
    c = a & 1;
    a >>= 1;                                /* LSR */
    a = (u16)(a + 0x2000 + c);
    W16(wm_0D85, a);
    W16(wm_0D85 + 10, a + 0x0200);

    a = (u16)(m10v | (m11v << 8));
    c = (a | 0x0800) == a;
    a &= 0xF700;
    a = (u16)((a >> 1) | (c ? 0x8000 : 0));
    c = a & 1;
    a >>= 1;
    a = (u16)(a + 0x2000 + c);
    W16(wm_0D85 + 2, a);
    W16(wm_0D85 + 12, a + 0x0200);

    a = (u16)((R8(m12) << 8) >> 3);    /* carry = 0 (ultimo bit, siempre 0) */
    a = (u16)(a + 0x2000);
    W16(wm_0D85 + 4, a);
    W16(wm_0D85 + 14, a + 0x0200);

    a = (u16)((R8(m13) << 8) >> 3);
    W16(wm_Tile7FPtr, a + 0x2000);
    W8(wm_PlayerDmaTiles, 0x0A);
}

/* CODE_00E2BD */
void mario_E2BD(void)
{
    u8 a, x, y, c;
    u16 w, sx;

    if (R8(wm_HidePlayer) != 0xFF && R8(wm_LooseYoshiFlag)) {
        if (!mario_unsupported) mario_unsupported = MARIO_UNSUP_YOSHI;
        return;
    }
    y = R8(wm_FlashingPalTimer);
    if (y)
        goto l_shift;
    y = R8(wm_StarPowerTimer);
    if (!y) {
        a = (u8)((R8(wm_MarioPowerUp) << 1) | R8(wm_OWCharA));   /* CODE_00E314 */
        goto l_E31A;
    }
    if (R8(wm_HidePlayer) != 0xFF && !(R8(wm_FrameB) & 0x03))
        W8(wm_StarPowerTimer, R8(wm_StarPowerTimer) - 1);
    a = R8(wm_FrameA);
    if (y > 0x1E)
        goto l_E30C;
    if (y == 0x1E)
        mario_events |= MEV_SPRITE;         /* vuelve la musica: solo sonido */
l_shift:
    a = (u8)(R8(wm_FrameA) >> 2);
l_E30C:
    a = (u8)((a & 0x03) + 4);
l_E31A:
    W16(wm_PlayerPalPtr, T16(DATA_00E2A2 + (u8)(a << 1)));

    x = R8(wm_MarioFrame);
    c = 1;                                  /* CMP #$05 con WallWalkStatus <= 5 */
    if (R8(wm_WallWalkStatus) > 0x05) {
        a = R8(wm_WallWalkStatus);
        if (!R8(wm_MarioPowerUp) || x == 0x13)
            a ^= 1;
        c = a & 1;                          /* LSR */
    }
    sx = (u16)(R16(wm_MarioXPos) - R16(wm_Bg1HOfs) - (c ? 0 : 1));
    W16(wm_MarioScrPosX, sx);
    w = (u16)(R8(wm_PlayerImgYPos) + R16(wm_MarioYPos));
    if (R8(wm_MarioPowerUp) >= 1) {
        y = 1;
        c = 1;
    } else {
        w--;
        y = 0;
    }
    if (x < 0x0A)
        c = y >= R8(wm_PlayerWalkPose);     /* CPY wm_PlayerWalkPose */
    else
        c = 1;
    w = (u16)(w - R16(wm_Bg1VOfs) - (c ? 0 : 1));
    if (x == 0x1C)
        w = (u16)(w + 2);                   /* ADC #$0001 con carry */
    W16(wm_MarioScrPosY, w);

    a = R8(wm_PlayerHurtTimer);
    if (a) {
        if (!((T8(DATA_00E292 + (a >> 3)) & a) | R8(wm_SpritesLocked) | R8(wm_IsFrozen)))
            return;                         /* parpadeo: este frame no se dibuja */
    }

    /* CODE_00E385 */
    {
        /* m4, m5, m6, m10, m11 y HidePlayer en variables: nadie mas los lee
           durante las 4 entradas de OAM (CODE_00E45D); a la RAM van los
           valores finales, como en el ROM */
        u8 m4v, m5v, m6v, m10v, m11v, hp, k, *o;
        u16 sy = w;
        m4v = (x == 0x43) ? 0xE8 : 0xC8;
        if (x == 0x29 && !R8(wm_MarioPowerUp))
            x = 0x20;
        y = (u8)(T8X(DATA_00DCEC, x) | R8(wm_MarioDirection));
        m5v = T8X(DATA_00DD32, y);
        a = R8(wm_MarioFrame);
        if (a < 0x3D)
            a = (u8)(a + T8X(TilesetIndex, R8(wm_MarioPowerUp)));
        y = a;
        m6v = T8X(TileExpansion, y);
        m10v = T8X(DATA_00E00C, y);
        m11v = T8X(DATA_00E0CC, y);
        W8(m10, m10v);
        W8(m11, m11v);
        a = R8(wm_SpriteProp);
        x = R8(wm_IsBehindScenery);
        if (x)
            a = T8X(DATA_00E2B9, x);
        y = T8X(DATA_00E2B2, x);
        a |= T8X(MarioPalIndex, R8(wm_MarioDirection));
#ifdef NOOAM
        /* build de la Amiga: sin las 4 entradas de OAM (la 6b.4 dibuja a
           Mario con su pose). Solo los efectos que no son OAM: lo que el
           bucle deja en HidePlayer y en m4-m6 */
        (void)a; (void)k; (void)o; (void)sy; (void)sx;
        W8(wm_HidePlayer, R8(wm_HidePlayer) >> 4);
        W8(m4, (u8)(m4v << 4));
        W8(m5, (u8)(m5v + 8));
        W8(m6, (u8)(m6v + 4));
#else
        o = ram + 0x0300 + y;               /* wm_OamSlot.1,Y: X, Y, tile, prop */
        o[3] = a;
        o[4 + 3] = a;
        o[12 + 3] = a;
        o[16 + 3] = a;
        W8((u16)(0x02FB + y), a);           /* wm_ExOamSlot.63.Prop,Y */
        W8((u16)(0x02FF + y), a);           /* wm_ExOamSlot.64.Prop,Y */
        if (m4v == 0xE8)
            a ^= 0x40;
        o[8 + 3] = a;
        hp = R8(wm_HidePlayer);
        for (k = 4; k; k--) {               /* CODE_00E45D x 4 */
            u8 cc;
            cc = hp & 1;
            hp >>= 1;
            if (cc)
                goto l_plus;
            a = T8X(Mario8x8Tiles, m6v);
            if (NEG(a))
                goto l_plus;                /* c = 0 (del LSR) */
            o[2] = a;
            w = (u16)(sy + T16X(DATA_00DE32, m5v));
            if ((u16)(w + 0x10) >= 0x100) { cc = 1; goto l_plus; }
            o[1] = (u8)w;
            w = (u16)(sx + T16X(DATA_00DD4E, m5v));
            if ((u16)(w + 0x80) >= 0x200) { cc = 1; goto l_plus; }
            o[0] = (u8)w;
            cc = (u8)((w >> 8) & 1);        /* XBA / LSR: bit 8 de la X */
l_plus:
            RX8(OAM_SIZE, y >> 2) = (u8)(((m4v >> 6) & 2) | cc);
            m4v <<= 1;                      /* ASL m4: tamaño 16x16 */
            m5v += 2;
            m6v++;
            y += 4;
            o += 4;
        }
        W8(wm_HidePlayer, hp);
        W8(m4, m4v);
        W8(m5, m5v);
        W8(m6, m6v);
#endif
        if (R8(wm_MarioPowerUp) == 0x02) {
            if (!mario_unsupported) mario_unsupported = MARIO_UNSUP_CAPE;
            return;
        }
        f636(m10v, m11v);
    }
}
