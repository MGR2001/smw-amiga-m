/*
 * manim.c - el frame entero del jugador en un nivel normal, portado de
 * player.s (SMW U). Ver mario.h.
 *
 *   CODE_00C500   FrameB, temporizadores de $1496-$14AE
 *   ResetAni      (MarioAnimation = 0)
 *     CODE_00CDDD   scroll de camara con L/R
 *     CODE_00CCC3   Mario bloqueado ($13FB)
 *     CODE_00CD24   movimiento + colision (mcoll.c)
 *     CODE_00CD82   8a (mario.c)
 *     CODE_00CEB1   animacion: pose (MarioFrame), paso, capa, y la
 *                   direccion durante el salto con giro
 *   _00C58F       NoteBlkBounceFlag = 0
 *
 * Lo que no esta portado (animaciones de $71, Yoshi, capa, final del
 * nivel...) marca mario_unsupported y vuelve.
 */
#include "mario.h"
#include "gen/smwram.h"
#include "gen/smwtab.h"
#include "smwmac.h"

#ifndef NumWalkingFrames
#define NumWalkingFrames (DATA_00DC7C - 4)  /* .DB 1,2,2,2 justo antes */
#endif

static void unsup_anim(int why) { if (!mario_unsupported) mario_unsupported = why; }

/* ------------------------------------------------------------------ */
/* CODE_00CEB1 */
void mario_CEB1(void)
{
    u8 a, x, y, b;

    if (R8(wm_CapeWaveTimer))
        goto l_14A2;
    x = R8(wm_CapeImage);
    a = R8(wm_IsFlying);
    if (!a)
        goto l_ground;                      /* "MarioAnimAir" */
    y = 0x04;
    if (!NEG(R8(wm_MarioSpeedY))) {
        x++;                                /* CODE_00CECD */
        if (x < 0x05)
            x = 0x05;
        else if (x >= 0x0B)
            x = 0x07;
        goto l_CF0A;
    }
    if (a == 0x0C || R8(wm_IsSwimming))
        goto l_CEFD;
    goto l_notwater;

l_ground:
    a = R8(wm_MarioSpeedX);
    if (a)
        goto l_CEF0;
    y = 0x08;
l_notwater:
    if (x == 0)
        goto l_CF0A;
    x--;
    if (x >= 0x03)
        x = 0x02;
    goto l_CF0A;

l_CEF0:
    if (NEG(a))
        a = (u8)(-a);
    y = T8(DATA_00DC7C + (a >> 3));
l_CEFD:
    x++;
    if (x < 0x03)
        x = 0x05;
    if (x >= 0x07)
        x = 0x03;
l_CF0A:
    W8(wm_CapeImage, x);
    a = y;
    if (R8(wm_IsSwimming))
        a <<= 1;
    W8(wm_CapeWaveTimer, a);

l_14A2:
    if (R8(wm_IsSpinJump) | R8(wm_CapeSpinTimer)) {
        W8(wm_IsDucking, 0);
        x = R8(wm_FrameB) & 0x06;
        y = x;
        if (R8(wm_IsFlying) && !NEG(R8(wm_MarioSpeedY)))
            y++;
        W8(wm_CapeImage, T8X(DATA_00CEA9, y));
        if (R8(wm_MarioPowerUp))
            x++;
        W8(wm_MarioDirection, T8X(DATA_00CEA1, x));
        if (R8(wm_MarioPowerUp) == 0x02) { unsup_anim(MARIO_UNSUP_CAPE); return; }  /* CODE_00D044 */
        a = T8X(DATA_00CE99, x);
        goto l_D01A;
    }

    /* CODE_00CF4E */
    a = R8(wm_PlayerSlopePose);
    if (a) {
        if (!NEG(a))
            goto l_D01A;
        y = (u8)((R8(wm_OnSlopeTypeB) >> 2) | R8(wm_MarioDirection));
        a = T8X(DATA_00CE79 + 6, y);
        goto l_D01A;
    }
    /* CODE_00CF62 */
    a = R8(wm_IsCarrying2) ? 0x1D : 0x3C;
    if (R8(wm_IsDucking))
        goto l_D01A;
    if (R8(wm_FireballImgTimer)) {
        a = R8(wm_IsFlying) ? 0x16 : 0x3F;
        goto l_D01A;
    }
    a = 0x0E;                               /* CODE_00CF7E */
    if (R8(wm_KickImgTimer))
        goto l_D01A;
    a = 0x1D;                               /* CODE_00CF88 */
    if (R8(wm_PickUpImgTimer))
        goto l_D01A;
    a = 0x0F;
    if (R8(wm_FaceCamImgTimer))
        goto l_D01A;
    a = 0x00;
    if (R8(wm_IsInLakituCloud))
        goto l_noabs;
    a = R8(wm_IsFlying);
    if (a) {
        if (R8(wm_RunCapeTimer))
            goto l_CFBC;
        y = R8(wm_CapeGlidePhase);
        if (y)
            a = T8X(DATA_00CE79 - 1, y);
        if (R8(wm_IsCarrying2))
            a = 0x09;
        goto l_D01A;                        /* en el aire: la pose es $72 */
    }
    a = R8(wm_PlayerTurningPose);           /* CODE_00CFB7 */
    if (a)
        goto l_D01A;
l_CFBC:
    a = R8(wm_MarioSpeedX);
    if (NEG(a))
        a = (u8)(-a);
l_noabs:
    x = a;
    if (x == 0) {                           /* parado */
        if (R8(wm_JoyPadA) & 0x08)
            W8(wm_OWCreditsPose, 0x03);     /* mirar arriba */
        a = 0;
        goto l_pp;
    }
    /* CODE_00CFD4 */
    if (R8(wm_IsSlipperyLevel)) {
        if (!(R8(wm_JoyPadA) & 0x03)) {
            a = 0;
            goto l_pp;
        }
        W8(wm_PlayerFrameIndex, 0x68);
    }
    a = R8(wm_PlayerWalkPose);
    if (R8(wm_PlayerAnimTimer))
        goto l_pp;
    a--;
    if (NEG(a))
        a = T8(NumWalkingFrames + R8(wm_MarioPowerUp));
    b = a;
    W8(wm_PlayerAnimTimer, T8(DATA_00DC7C + ((x >> 3) | R8(wm_PlayerFrameIndex))));
    a = b;
l_pp:
    W8(wm_PlayerWalkPose, a);
    a = (u8)(a + R8(wm_OWCreditsPose));
    if (R8(wm_IsCarrying2))
        a = (u8)(a + 0x07);
    else if (x >= 0x2F)
        a = (u8)(a + 0x04);                 /* ADC #$03 con carry */

l_D01A:
    y = R8(wm_WallWalkStatus);
    if (y) {
        W8(wm_MarioDirection, y & 0x01);
        a = 0x10;
        if (y >= 0x06)
            a = (u8)(R8(wm_PlayerWalkPose) + 0x11);
    }
    W8(wm_MarioFrame, a);
}

/* ------------------------------------------------------------------ */
/* CODE_00CDDD: mover la camara con L/R */
static void cddd(void)
{
    u8 a, x, y;
    u16 w;

    if (!R8(wm_HorzScrollHead))
        return;
    y = R8(wm_LRScrollDir);
    a = R8(wm_LRScrollFlag);
    W8(wm_SpritesLocked, a);
    if (a)
        goto l_CE4C;
    a = R8(wm_LRMoveCamera);
    if (a) {
        W8(wm_LRScrollDir, 0);
        y = a;                              /* _00CE48: TAY */
        goto l_pp;
    }
    /* CODE_00CDF6 */
    if ((R8(wm_JoyPadB) & 0xCF) | R8(wm_JoyPadA))
        goto l_pp;
    a = R8(wm_JoyPadB) & 0x30;
    if (!a || a == 0x30)
        goto l_pp;
    a >>= 3;
    W8(wm_LRFrameTimer, R8(wm_LRFrameTimer) + 1);
    if (R8(wm_LRFrameTimer) < 0x10)
        goto l_CE4C;
    x = a;
    if (R16(wm_PosToScrollScreen) == T16X(DATA_00F6CB, x))
        goto l_CE4C;
    W8(wm_PosToScrollScreen, R8(wm_PosToScrollScreen) & 0xFE);
    W8(wm_LRScrollFlag, R8(wm_LRScrollFlag) + 1);
    a = 0;
    if (x == 0x02)
        a = (u8)(R8(wm_LastScreenHorz) - 1);
    if ((u16)(a << 8) != R16(wm_Bg1HOfs))
        W8(wm_SoundCh3, 0x0E);
    W8(wm_LRScrollDir, x);
    y = x;
l_pp:
    W8(wm_LRFrameTimer, 0);
l_CE4C:
    x = 0;
    W8(wm_LRScrollStop, R8(wm_MarioDirection) << 1);
    w = R16(wm_PosToScrollScreen);
    if (w != T16X(DATA_00F6CB, y)) {
        w = (u16)(w + T16X(DATA_00F6BF, y));
        if (w != T16(DATA_00F6B3 + R8(wm_LRScrollStop)))
            goto l_store;
        W8(wm_LRScrollDir, x);
    }
    W8(wm_LRScrollFlag, x);
l_store:
    W16(wm_PosToScrollScreen, w);
    W8(wm_LRMoveCamera, x);
}

/* ------------------------------------------------------------------ */
/* CODE_00C500 ... _00C58F, sin el ojo de cerradura ni los modos
   especiales: un frame del jugador. */
void mario_player(void)
{

    mario_unsupported = MARIO_OK;
    mario_events = 0;
    if (!R8(wm_SpritesLocked)) {
        u8 *p = ram + wm_PlayerAnimTimer;   /* $1496: PAR */
        W8(wm_FrameB, R8(wm_FrameB) + 1);
        /* ColorFadeTimer+1..+$13 ($1496-$14A8) y, cada 4 frames, $14A9-$14AE.
           Casi todos valen 0: se miran de a 4 (NZ32) y solo se bajan los
           grupos con algo (el bucle byte a byte costaba ~600 ciclos) */
        if (NZ32(p)) DEC4(p);
        if (NZ32(p + 4)) DEC4(p + 4);
        if (NZ32(p + 8)) DEC4(p + 8);
        if (NZ32(p + 12)) DEC4(p + 12);
        if (NZ16(p + 16)) { DEC1(p + 16); DEC1(p + 17); }
        DEC1(p + 18);                       /* $14A8 */
        if (!(R8(wm_FrameB) & 0x03)) {
            /* (musica del interruptor P y del juego de bonus: solo sonido) */
            DEC1(p + 19);                   /* $14A9 */
            if (NZ32(p + 20)) DEC4(p + 20); /* $14AA-$14AD */
            DEC1(p + 24);                   /* $14AE */
        }
    }
    /* CODE_00C593 -> ResetAni */
    if (R8(wm_MarioAnimation)) { unsup_anim(MARIO_UNSUP_TILE); return; }
    if (R8(wm_EndLevelTimer)) { unsup_anim(MARIO_UNSUP_TILE); return; }   /* CODE_00C915 */
    /* CODE_00CCC3 */
    cddd();
    if (!R8(wm_SpritesLocked)) {
        W8(wm_CapeCanHurt, 0);
        W8(wm_OWCreditsPose, 0);
        if (R8(wm_LockMarioTimer)) {
            W8(wm_LockMarioTimer, R8(wm_LockMarioTimer) - 1);
            W8(wm_MarioSpeedX, 0);
            W8(wm_MarioFrame, 0x0F);
        } else if (NEG(R8(wm_LevelMode)) && !(R8(wm_LevelMode) & 1)) {
            unsup_anim(MARIO_UNSUP_LAYER);       /* capa 2 que mueve a Mario */
            return;
        } else {
            mario_collide();                /* CODE_00CD24 + _00CD39 */
            if (mario_unsupported)
                return;
            mario_D5F2();                   /* CODE_00CD82 */
            if (!mario_unsupported) mario_D062();
            if (!mario_unsupported) mario_D7E4();
            if (mario_unsupported)
                return;
            mario_CEB1();
            if (R8(wm_OnYoshi)) { unsup_anim(MARIO_UNSUP_YOSHI); return; }
        }
    }
    if (R8(wm_JoyFrameA) & 0x20)            /* SELECT: soltar el item de reserva */
        mario_events |= MEV_SPRITE;
    W8(wm_NoteBlkBounceFlag, 0);            /* _00C58F */
}

/* ------------------------------------------------------------------ */
/* CODE_01808C, solo el principio (el motor de sprites es la etapa 9):
   lo que el jugador ve de los sprites se borra cada frame y los sprites lo
   vuelven a poner (sobre un sprite solido, llevando algo, Lakitu...) */
void sprites_begin(void)
{
    W8(wm_IsCarrying, R8(wm_IsCarrying2));
    W8(wm_IsCarrying2, 0);
    W8(wm_IsOnSolidSpr, 0);
    W8(wm_IsInLakituCloud, 0);
    W8(wm_LooseYoshiFlag, R8(wm_YoshiSlot));
    W8(wm_YoshiSlot, 0);
}

/* Un frame de nivel, en el orden de CODE_00A295 (sin la barra de estado,
   el scroll de los tiles de la capa 1 ni los sprites):
   FrameA, wm_ClearOam, camara, graficos de Mario, jugador, sprites,
   bloques que rebotan. */
u8 level_sprites;          /* 1: level_frame corre tambien los sprites (etapa 9) */

void level_frame(void)
{
    u8 *p = ram + 0x0201;                   /* wm_ClearOam: la Y de las 128 */
    W8(wm_FrameA, R8(wm_FrameA) + 1);       /* entradas a $F0 (fuera de pantalla), */
#define CLR4(o)  p[o] = 0xF0; p[(o) + 4] = 0xF0; p[(o) + 8] = 0xF0; p[(o) + 12] = 0xF0;
#define CLR16(o) CLR4(o) CLR4((o) + 16) CLR4((o) + 32) CLR4((o) + 48)
    CLR16(0) CLR16(64) CLR16(128) CLR16(192)        /* desenrollado: el bucle */
    CLR16(256) CLR16(320) CLR16(384) CLR16(448)     /* costaba ~800 ciclos mas */
#undef CLR16
#undef CLR4
    mario_unsupported = MARIO_OK;
    camera_F6DB();
    if (!mario_unsupported) mario_E2BD();
    W16(wm_PlayerXPosLv, R16(wm_MarioXPos));        /* CODE_00A2F3 */
    W16(wm_PlayerYPosLv, R16(wm_MarioYPos));
    if (!mario_unsupported) mario_player();
    if (mario_unsupported)
        return;
    sprites_begin();
    if (level_sprites) {                    /* CODE_01808C: ranuras 11..0 */
        u8 k = 12;
        do {
            k--;
            if (RX8(wm_SpriteStatus, k)) {
                sprite_run(k);
                mario_unsupported = MARIO_OK;   /* un sprite sin portar no para el frame */
            } else {                        /* ranura vacia: lo que hace sprite_run */
                W8(wm_SprProcessIndex, k);  /* (EraseSprite) sin llamarla */
                RX8(wm_SprIndexInLvl, k) = 0xFF;
            }
        } while (k);
    }
    blocks_update();
    if (level_sprites)
        sprite_load_level();                /* al final de CODE_028AB1 */
}
