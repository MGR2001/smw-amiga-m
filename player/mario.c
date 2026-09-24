/*
 * mario.c - fisica de Mario portada de player.s (SMW U). Ver mario.h.
 *
 * Etapa 8a: CODE_00D5F2 (velocidad X, agacharse, saltar), CODE_00D062
 * (capa / fuego) y CODE_00D7E4 (gravedad), con sus auxiliares
 * CODE_00D968/_00D96A (medidor de carrera) y CODE_00FE4A (humo al frenar).
 *
 * Convenciones de la traduccion:
 *  - Cada bloque lleva la etiqueta de player.s que traduce.
 *  - A/X/Y son u8 (el juego corre con A e indices de 8 bits salvo donde
 *    hay REP #$20, que aca es una variable u16 explicita).
 *  - Los flags N/Z/C se traducen solo donde una instruccion los usa.
 *  - Los caminos de capa, fuego y Yoshi con alas NO estan portados: marcan
 *    mario_unsupported y vuelven, para que el verificador no los cuente.
 */
#include "mario.h"
#include "gen/smwram.h"
#include "gen/smwtab.h"

u8 ram[0x2000];
int mario_unsupported;

#include "smwmac.h"

/* Tablas de player.s que el generador no nombra (DATA_ sin datos propios en
   el fuente, o con nombre ambiguo): direccion tomada de la etiqueta. */
#ifndef DATA_00D5EB
#define DATA_00D5EB 0xD5EB
#endif

/* ------------------------------------------------------------------ */
/* CODE_00FE4A: humo al frenar / derrapar. Escribe solo las tablas de humo.
   No toca X. */
static void fe4a(void)
{
    u8 a, y;
    a = (u8)((R8(wm_FrameA) & 0x03) | R8(wm_IsFlying) | R8(wm_MarioScrPosX + 1)
             | R8(wm_MarioScrPosY + 1) | R8(wm_SpritesLocked));
    if (a)
        return;
    if (R8(wm_JoyPadA) & 0x04) {
        a = (u8)(R8(wm_MarioSpeedX) + 0x08);
        if (a < 0x10)                       /* CMP #$10 / BCC ++ */
            return;
    }
    for (y = 3; y != 0; y--) {              /* -: LDA wm_SmokeSprite,Y / BEQ */
        if (RX8(wm_SmokeSprite, y) == 0)
            goto fe72;
    }
    return;
fe72:                                       /* CODE_00FE72 */
    /* El ADC usa el carry que dejo el CMP #$10 (1) o el LDA (sin tocar):
       en los dos caminos que llegan aca el carry es 1 si hubo CMP, y del
       AND/ORA anteriores (no lo tocan) si no. Solo afecta a la posicion
       del humo, que el oraculo no compara. */
    (RX8(wm_SmokeSprite, y) = (u8)(0x03));
    (RX8(wm_SmokeXPos, y) = (u8)(R8(wm_MarioXPos) + 0x04));
    a = (u8)(R8(wm_MarioYPos) + 0x1A);
    if (R8(wm_OnYoshi))
        a = (u8)(a + 0x10);
    (RX8(wm_SmokeYPos, y) = (u8)(a));
    (RX8(wm_SmokeTimer, y) = (u8)(0x13));
}

/* CODE_00D968 / _00D96A: medidor de carrera. Devuelve Y (sube en 1 si el
   medidor llego a $70). */
static u8 d96a(u8 y)
{
    u8 a = (u8)(R8(wm_PlayerDashTimer) + T8X(DATA_00D5EB, y));
    if (NEG(a))
        a = 0;
    if (a >= 0x70) {                        /* CMP #$70 / BCC + */
        y++;
        a = 0x70;
    }
    W8(wm_PlayerDashTimer, a);
    return y;
}

/* ------------------------------------------------------------------ */
/* CODE_00D5F2 */
void mario_D5F2(void)
{
    u8 a, x, y, c;
    u16 w;

    mario_unsupported = MARIO_OK;
    if (R8(wm_IsFlying))
        goto l_D682;

    /* CODE_00D5F9 */
    W8(wm_IsDucking, 0);
    if (R8(wm_PlayerSlopePose) == 0) {
        a = R8(wm_JoyPadA) & 0x04;
        if (a) {
            W8(wm_IsDucking, a);
            W8(wm_CapeCanHurt, 0);
        }
    }
    if (R8(wm_IsOnSolidSpr) != 0x02 && !(R8(wm_MarioObjStatus) & 0x08)
        && NEG(R8(wm_JoyFrameA) | R8(wm_JoyFrameB)))
        goto l_D630;
    if (!R8(wm_IsDucking))
        goto l_D682;
    if (R8(wm_MarioSpeedX) && !R8(wm_IsSlipperyLevel))
        fe4a();
    goto l_D764;

l_D630:                                     /* CODE_00D630: empieza el salto */
    a = R8(wm_MarioSpeedX);
    if (NEG(a))
        a = (u8)(-a);
    x = (u8)((a >> 2) & 0xFE);
    if (NEG(R8(wm_JoyFrameB)) && !R8(wm_IsCarrying2)) {
        W8(wm_IsSpinJump, 1);               /* LDA IsCarrying2 (0) / INC A */
        W8(wm_SoundCh3, 0x04);
        W8(wm_SpinFireTimer, T8(DATA_00D5F0 + R8(wm_MarioDirection)));
        if (R8(wm_OnYoshi))
            goto l_D682;
        x++;
    } else {
        W8(wm_SoundCh2, 0x01);              /* CODE_00D65E */
    }
    /* _00D663 */
    W8(wm_MarioSpeedY, T8X(DATA_00D2BD, x));
    a = 0x0B;
    if (R8(wm_PlayerDashTimer) >= 0x70) {
        if (!R8(wm_GlideTimer))
            W8(wm_GlideTimer, 0x50);
        a = 0x0C;
    }
    W8(wm_IsFlying, a);
    W8(wm_PlayerSlopePose, 0);

l_D682:                                     /* _00D682 */
    if (!NEG(R8(wm_PlayerSlopePose))) {
        a = R8(wm_JoyPadA) & 0x03;
        if (a)
            goto l_D6B1;
        /* _00D68D */
        if (!R8(wm_PlayerSlopePose))
            goto l_D764;
    }
    fe4a();
    if (!R8(wm_OnSlopeTypeA))
        goto l_D764;
    (void)d96a(0);                          /* CODE_00D968 */
    a = R8(wm_OnSlopeTypeB);
    c = (u8)((a >> 1) & 1);                 /* carry del segundo LSR */
    a >>= 2;
    y = a;
    x = (u8)(a + 0x76 + c);                 /* ADC #$76 */
    c = (u8)(y & 1);                        /* TYA / LSR */
    y = (u8)((y >> 1) + 0x87 + c);          /* ADC #$87 / TAY */
    goto l_D742;

l_D6B1:                                     /* CODE_00D6B1 */
    W8(wm_PlayerSlopePose, 0);
    a &= 0x01;
    if (R8(wm_CapeGlidePhase)) {
        mario_unsupported = MARIO_UNSUP_CAPE;
        return;
    }
    /* CODE_00D6D5 */
    if (a != R8(wm_MarioDirection)) {
        if (R8(wm_IsCarrying2)) {
            if (R8(wm_FaceCamImgTimer))
                goto l_D6D5_pp;
            W8(wm_FaceCamImgTimer, 0x08);
        }
        W8(wm_MarioDirection, a);
    }
l_D6D5_pp:
    W8(m1, a);
    x = (u8)((a << 2) | R8(wm_OnSlopeTypeB));
    if (R8(wm_MarioSpeedX) && NEG(R8(wm_MarioSpeedX) ^ T8X(MarioAccel + 1, x))
        && !R8(wm_SlideImgTimer)) {
        if (!R8(wm_IsSlipperyLevel)) {
            W8(wm_PlayerTurningPose, 0x0D);
            fe4a();
        }
        x = (u8)(x + 0x90);
    }

    /* _00D713 */
    y = 0;
    if (R8(wm_JoyPadA) & 0x40) {            /* BIT / BVC: Y = correr */
        x = (u8)(x + 2);
        y++;
        a = R8(wm_MarioSpeedX);
        if (NEG(a))
            a = (u8)(-a);
        if (!NEG((u8)(a - 0x23))) {         /* CMP #$23 / BMI */
            if (!R8(wm_IsFlying)) {
                W8(wm_RunCapeTimer, 0x10);
                y++;
            } else if (R8(wm_IsFlying) == 0x0C) {
                y++;
            }
        }
    }
    /* _00D737 */
    y = d96a(y);
    y = (u8)((y << 1) | R8(wm_OnSlopeTypeB) | R8(m1));

l_D742:                                     /* _00D742 */
    a = (u8)(R8(wm_MarioSpeedX) - T8X(DATA_00D535, y));
    if (a == 0 || !NEG(a ^ T8X(DATA_00D535, y)))
        goto l_D76B;
    w = T16X(MarioAccel, x);
    if (R8(wm_IsSlipperyLevel) && !R8(wm_IsFlying))
        w = T16X(DATA_00D43D, x);
    w = (u16)(w + R16(wm_MarioAccSpeedX));
    W16(wm_MarioAccSpeedX, w);              /* _00D7A0 */
    return;

l_D764:                                     /* CODE_00D764 */
    (void)d96a(0);
    if (R8(wm_IsFlying))
        return;

l_D76B:                                     /* _00D76B */
    a = (u8)(R8(wm_OnSlopeTypeB) >> 1);
    y = a;
    x = (u8)(a >> 1);
    /* _00D772 */
    if (NEG((u8)(R8(wm_MarioSpeedX) - T8X(DATA_00D5C9 + 1, x))))
        y = (u8)(y + 2);
    if ((R8(wm_EndLevelTimer) | R8(wm_IsFlying)) == 0) {
        w = T16X(DATA_00D309, y);
        /* BIT wm_IsWaterLevel con A de 16 bits: N = bit 15 = bit 7 del
           byte SIGUIENTE */
        if (!NEG(R8(wm_IsWaterLevel + 1)))
            w = T16X(DATA_00D2CD, y);
    } else {
        w = T16X(DATA_00D2CD, y);
    }
    w = (u16)(w + R16(wm_MarioAccSpeedX));
    W16(wm_MarioAccSpeedX, w);
    if (!(((u16)(w - T16X(DATA_00D5C9, x)) ^ T16X(DATA_00D2CD, y)) & 0x8000))
        W16(wm_MarioAccSpeedX, T16X(DATA_00D5C9, x));   /* _00D7A0 */
}

/* ------------------------------------------------------------------ */
/* CODE_00D062: capa (giro) y flor de fuego. Mario chico o grande no hace
   nada aqui. */
void mario_D062(void)
{
    u8 p = R8(wm_MarioPowerUp);
    if (p == 0x02) {
        if (!(R8(wm_JoyFrameA) & 0x40))
            return;
        if (R8(wm_IsDucking) | R8(wm_OnYoshi) | R8(wm_IsSpinJump))
            return;
        W8(wm_CapeSpinTimer, 0x12);
        W8(wm_SoundCh3, 0x04);
        return;
    }
    if (p == 0x03)
        mario_unsupported = MARIO_UNSUP_FIRE;   /* ShootFireball: sin portar */
}

/* ------------------------------------------------------------------ */
/* CODE_00D7E4 */
void mario_D7E4(void)
{
    u8 a, y;

    if (R8(wm_CapeGlidePhase)) {
        mario_unsupported = MARIO_UNSUP_CAPE;   /* CODE_00D824 */
        return;
    }
    if (R8(wm_IsFlying) && !(R8(wm_IsCarrying2) | R8(wm_OnYoshi) | R8(wm_IsSpinJump))) {
        a = R8(wm_PlayerSlopePose);
        if (NEG(a) || a == 0) {
            W8(wm_PlayerSlopePose, 0);
            if (R8(wm_MarioPowerUp) == 0x02 && !NEG(R8(wm_MarioSpeedY))
                && R8(wm_GlideTimer)) {
                mario_unsupported = MARIO_UNSUP_CAPE;   /* CODE_00D814 */
                return;
            }
        }
    }

    /* CODE_00D8CD */
    if (R8(wm_IsFlying)) {
        if (R8(wm_OnYoshi) && (R8(wm_YoshiHasWings) >> 1)) {
            mario_unsupported = MARIO_UNSUP_YOSHI;
            return;
        }
        /* CODE_00D8E7 */
        if (R8(wm_MarioPowerUp) == 0x02) {
            mario_unsupported = MARIO_UNSUP_CAPE;
            return;
        }
    }

    /* _00D928 */
    y = NEG(R8(wm_JoyPadA)) ? 1 : 0;        /* B apretado: gravedad menor */
    a = R8(wm_MarioSpeedY);
    if (!NEG(a)) {
        if (a >= T8X(DATA_00D7AF, y))       /* CMP / BCC: sin signo */
            a = T8X(DATA_00D7AF, y);
        if (R8(wm_IsFlying) == 0x0B)
            W8(wm_IsFlying, 0x24);
    }
    /* _00D948 */
    W8(wm_MarioSpeedY, a + T8X(DATA_00D7A5, y));
}
