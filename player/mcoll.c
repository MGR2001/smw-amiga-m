/*
 * mcoll.c - etapa 8b: movimiento y colision de Mario con los bloques de la
 * capa 1, portados de player.s (SMW U). Ver mario.h.
 *
 * Es el principio del frame del jugador en un nivel normal, CODE_00CD24:
 *   CODE_00DC2D  velocidad -> posicion (8.4 + fraccion)
 *   CODE_00E92B  colision con bloques: sondas en puntos fijos del cuerpo
 *                (DATA_00E832 / DATA_00E89C), lectura del buffer Map16,
 *                reaccion segun el numero de bloque ("acts like" = el
 *                propio indice Map16 en el juego original), pendientes
 *   CODE_00F595  techo del nivel y caida por abajo de la pantalla
 *   _00CD39      trepar / nadar (no portado: marca mario_unsupported)
 * y despues la 8a (mario.c): D5F2, D062, D7E4.
 *
 * Convenciones: las de mario.c. rX / rY son los registros X e Y del 65816
 * (8 bits): las sondas de CODE_00F44D avanzan X de 2 en 2 entre llamadas,
 * y el numero de bloque vuelve en Y, asi que hay que llevarlos como estado.
 *
 * Los efectos que no mueven a Mario (sonidos, puntos, sprites de rebote de
 * los bloques, monedas) se anotan en mario_events para que el verificador
 * sepa que paso; los cambios del mapa (monedas que desaparecen...) se hacen
 * de verdad con GenerateTile, que es lo que ve el frame siguiente.
 */
#include "mario.h"
#include "gen/smwram.h"
#include "gen/smwtab.h"
#include "smwmac.h"

u8 *map16_lo;               /* $7E:C800: byte bajo del indice Map16 */
u8 *map16_hi;               /* $7F:C800: pagina */
unsigned mario_events;

/* build de la Amiga (vbcc sin NOASM): lo que player/logic68k.s lee o escribe
   deja de ser static (MCS); en el PC todo sigue static */
#if defined(__VBCC__) && !defined(NOASM)
#define LOGIC68K 1
#define MCS
#else
#define MCS static
#endif
MCS u8 rX, rY;

#define TILESET     0x1931  /* wm_LvHeadTileset (fuera de la RAM grabada) */
#define SCR_BYTES   0x1B0

static void unsup(int why) { if (!mario_unsupported) mario_unsupported = why; }

/* DATA_00BA60/BA9C: inicio de cada pantalla en el buffer (s * $1B0), en
   tabla como en el ROM: el 68000 tarda hasta 70 ciclos en un MULU */
const u16 scr_ofs[32] = {                   /* tambien msprite.c */
    0x0000, 0x01B0, 0x0360, 0x0510, 0x06C0, 0x0870, 0x0A20, 0x0BD0,
    0x0D80, 0x0F30, 0x10E0, 0x1290, 0x1440, 0x15F0, 0x17A0, 0x1950,
    0x1B00, 0x1CB0, 0x1E60, 0x2010, 0x21C0, 0x2370, 0x2520, 0x26D0,
    0x2880, 0x2A30, 0x2BE0, 0x2D90, 0x2F40, 0x30F0, 0x32A0, 0x3450,
};
static void generate_tile(void);

/* ------------------------------------------------------------------ */
/* GenerateTile (gen_tile.s), solo la parte que toca el mapa, para la
   capa 1 de un nivel horizontal. wm_BlockXPos/YPos llevan los nombres
   cambiados en el desensamblado: BlockYPos = X, BlockXPos = Y. */
static const u8 tile_pg0[9] = { 0x25, 0x25, 0x25, 0x06, 0x49, 0x48, 0x2B, 0xA2, 0xC6 };
static const u8 tile_pg1[15] = { 0x52, 0x1B, 0x23, 0x1E, 0x32, 0x13, 0x15, 0x16,
                                 0x2B, 0x2C, 0x12, 0x68, 0x69, 0x32, 0x5E };

static void generate_tile(void)
{
    u8 id = R8(wm_BlockId);
    u16 x = R16(wm_BlockYPos), y = R16(wm_BlockXPos), o;
    if (!id || y >= 0x200)
        return;
    if (R8(wm_IsVerticalLvl) & 1) { unsup(MARIO_UNSUP_LAYER); return; }
    o = (u16)(scr_ofs[(x >> 8) & 0x1F] + (y & 0x1F0) + ((x >> 4) & 0x0F));
    mario_events |= MEV_TILE;
    if (id <= 8) {                          /* _00C077 */
        map16_hi[o] &= 0xFE;
        map16_lo[o] = tile_pg0[id];
    } else if (id <= 0x17) {                /* _00C0C4 */
        map16_hi[o] |= 0x01;
        map16_lo[o] = tile_pg1[id - 9];
    } else if (id == 0x18) {                /* CODE_00C1AC: moneda de Yoshi */
        map16_lo[o] = 0x25;
        map16_lo[o + 0x10] = 0x25;
    } else {
        unsup(MARIO_UNSUP_TILE);
    }
}

/* ------------------------------------------------------------------ */
/* CODE_00F545: bloques que cambian con los interruptores P. Entra A = pagina,
   devuelve A (el llamador mira A == 0). */
static u8 f545(u8 a)
{
    u8 y;
    if (a == 0) {
        y = R8(wm_Map16NumLo);
        if (y == 0x29) {
            if (!R8(wm_BluePowTimer))
                return a;
            W8(wm_Map16NumLo, 0x24);
            return 0x24;
        }
        if (y == 0x2B) {                    /* PSwitchCoinBrown */
            if (!R8(wm_BluePowTimer))
                return 0;
            W8(wm_Map16NumLo, 0x32);
            return 0x32;
        }
        a = (u8)(y - 0xEC);
        if (a >= 0x10)
            return 0;                       /* _00F592 */
        W8(wm_WhichSwitchPressed, a + 1);
        W8(wm_Map16NumLo, 0x32);
        return 0x32;
    }
    y = R8(wm_Map16NumLo);                  /* CODE_00F577 */
    if (y == 0x32) {
        if (!R8(wm_BluePowTimer))
            return a;
    } else if (y == 0x2F) {
        if (!R8(wm_SilverPowTimer))
            return a;
    } else {
        return a;
    }
    W8(wm_Map16NumLo, 0x2B);                /* _00F58D */
    return 0;
}

/* CODE_00F465 (desde _00F461): lee el bloque en (BlockYPos, BlockXPos).
   Deja el numero en rY y devuelve la pagina ajustada por F545.
   (nativo: la pantalla en 8 bits y el desplazamiento en 32 bits, para que
   vbcc no enmascare con and.l #$FFFF en cada paso) */
static u8 f461_xy(u16 x, u16 y)
{
    u8 xs, lo, a;
    unsigned o;
    W8(wm_WhichSwitchPressed, 0);
    if (R8(wm_8E)) { unsup(MARIO_UNSUP_LAYER); rY = 0x25; return 0; }
    xs = (u8)(x >> 8);
    if (y >= 0x1B0 || xs >= R8(wm_ScreensInLvl)) {
        rY = 0x25;                          /* CODE_00F4A0: fuera del nivel */
        return 0;
    }
    o = (unsigned)scr_ofs[xs & 0x1F] + (unsigned)(y & 0x1F0) + (unsigned)((u8)x >> 4);
    lo = map16_lo[o];
    a = map16_hi[o];
    W8(wm_Map16NumLo, lo);
    rY = lo;
    /* atajo de F545: solo 6 bloques + los interruptores la cambian */
    if (a) {
        if (lo == 0x32 || lo == 0x2F) {
            a = f545(a);
            rY = R8(wm_Map16NumLo);
        }
    } else if (lo == 0x29 || lo == 0x2B || (u8)(lo - 0xEC) < 0x10) {
        a = f545(0);
        rY = R8(wm_Map16NumLo);
    }
    return a;
}
static u8 f461(void) { return f461_xy(R16(wm_BlockYPos), R16(wm_BlockXPos)); }

/* CODE_00F44D: siguiente sonda (X += 2) respecto de la posicion de Mario.
   (x, y) van a la RAM como en el ROM y ademas se pasan directos a F465:
   en el 68000 releer un valor de 16 bits de ram[] cuesta ~50 ciclos) */
#ifdef MCOLL_TRACE
#include <stdio.h>
#endif
/* Desplazamientos de las sondas (DATA_00E832-2 / DATA_00E89C por X/2),
   en tablas nativas de 16 bits que se arman una vez desde la ROM: leerlos
   de rom00 byte a byte costaba ~50 ciclos por valor en el 68000. */
MCS u16 probe_dx[64], probe_dy[64];
static u8 probe_ok;
/* La posicion de Mario para las sondas: eb77 la carga al empezar y la
   actualiza donde la cambia antes de otra sonda (CODE_00ED28). Asi F44D
   no relee MarioXPos/YPos de ram[] (4 bytes) en cada una de las 6. */
MCS u16 probe_mx, probe_my;
static void probe_init(void)
{
    int k;
    for (k = 0; k < 64; k++) {
        probe_dx[k] = T16(DATA_00E832 - 2 + 2 * k);
        probe_dy[k] = T16(DATA_00E89C + 2 * k);
    }
    probe_ok = 1;
}

#ifdef LOGIC68K
u8 f44d_c(void);                /* la referencia; f44d_asm cae aca con wm_8E */
u8 f44d_asm(void);
/* f44d_asm, con un bloque de los interruptores P: lo que hace el C */
u8 f44d_tail(u8 a);
u8 f44d_tail(u8 a)
{
    a = f545(a);
    rY = R8(wm_Map16NumLo);
    return a;
}
u8 f44d_c(void)
#else
static u8 f44d(void)
#endif
{
    u8 a, k, xs, lo;
    u16 x, y;
    unsigned o;
    rX = (u8)(rX + 2);
    k = (u8)(rX & 0x7E);                    /* 2 * ((rX >> 1) & 63), en bytes */
    x = (u16)(probe_mx + *(const u16 *)(const void *)((const u8 *)probe_dx + k));
    y = (u16)(probe_my + *(const u16 *)(const void *)((const u8 *)probe_dy + k));
    W16(wm_BlockYPos, x);
    W16(wm_BlockXPos, y);
    /* = f461_xy(x, y), copiada aqui: la llamada con 2 argumentos en la
       pila costaba ~100 ciclos en cada una de las 6 sondas */
    W8(wm_WhichSwitchPressed, 0);
    if (R8(wm_8E)) { unsup(MARIO_UNSUP_LAYER); rY = 0x25; a = 0; goto out; }
    xs = (u8)(x >> 8);
    if (y >= 0x1B0 || xs >= R8(wm_ScreensInLvl)) {
        rY = 0x25;                          /* CODE_00F4A0: fuera del nivel */
        a = 0;
        goto out;
    }
    o = (unsigned)*(const u16 *)(const void *)((const u8 *)scr_ofs + (u8)((xs & 0x1F) << 1))
        + (unsigned)(y & 0x1F0) + (unsigned)((u8)x >> 4);
    lo = map16_lo[o];
    a = map16_hi[o];
    W8(wm_Map16NumLo, lo);
    rY = lo;
    if (a) {
        if (lo == 0x32 || lo == 0x2F) {
            a = f545(a);
            rY = R8(wm_Map16NumLo);
        }
    } else if (lo == 0x29 || lo == 0x2B || (u8)(lo - 0xEC) < 0x10) {
        a = f545(0);
        rY = R8(wm_Map16NumLo);
    }
out:
#ifdef MCOLL_TRACE
    printf("    sonda X=%02X  (%04X,%04X) -> pagina %02X bloque %02X\n",
           rX, R16(wm_BlockYPos), R16(wm_BlockXPos), a, rY);
#endif
    return a;
}
#ifdef LOGIC68K
#define f44d f44d_asm            /* player/logic68k.s */
#endif

/* CODE_00F443: carry = ((XPos + 4) & $0F) >= 8 */
static int f443(void) { return ((u8)(R8(wm_MarioXPos) + 4) & 0x0F) >= 8; }

/* CODE_00F629 / KillMario / _NoButtons */
static void kill_mario(void)
{
    W8(wm_MarioSpeedY, 0x90);
    W8(wm_MusicCh1, 0x09);                  /* _00F60A */
    W8(wm_LevelMusicMod, 0xFF);
    W8(wm_MarioAnimation, 0x09);
    W8(wm_IsSpinJump, 0);
    W8(wm_PlayerAnimTimer, 0x30);
    W8(wm_SpritesLocked, 0x30);
    W8(wm_CapeGlidePhase, 0);
    W8(wm_188A, 0);
    mario_events |= MEV_DEATH;
}
static void no_buttons(void)
{
    W8(wm_JoyPadA, 0); W8(wm_JoyFrameA, 0); W8(wm_JoyPadB, 0); W8(wm_JoyFrameB, 0);
}
static void f629(void) { kill_mario(); no_buttons(); }

/* HurtMario: solo hay que saber que paso (cambia de modo: animacion) */
static void hurt_mario(void)
{
    if (R8(wm_MarioAnimation))
        return;
    if (R8(wm_PlayerHurtTimer) | R8(wm_StarPowerTimer) | R8(wm_EndLevelTimer))
        return;
    mario_events |= MEV_HURT;
    unsup(MARIO_UNSUP_HURT);
}

/* ------------------------------------------------------------------ */
/* Bloques que rebotan (sprite_2-clus.s): CODE_028752 los crea al golpear
   un bloque; blocks_update() (CODE_02902D, fase de sprites) los mueve y
   cambia el bloque del mapa: solido invisible ($152) mientras rebota, y
   al final el bloque que corresponda (usado, giratorio...). Las cuatro
   ranuras viven en ram[] (wm_BounceSpr*), como en la SNES.
   OJO con los nombres del desensamblado: BounceSprYLo guarda la X y
   BounceSprXLo la Y, igual que BlockYPos / BlockXPos. */

/* _TileFromBounceSpr1: GenerateTile en la posicion de la ranura x */
static void tile_from_bounce(u8 x, u8 id)
{
    u16 p;
    W8(wm_BlockId, id);
    p = (u16)((RX8(wm_BounceSprYLo, x) | (RX8(wm_BounceSprYHi, x) << 8)) + 8);
    W8(wm_BlockYPos, p & 0xF0);
    W8(wm_BlockYPos + 1, p >> 8);
    p = (u16)((RX8(wm_BounceSprXLo, x) | (RX8(wm_BounceSprXHi, x) << 8)) + 8);
    W8(wm_BlockXPos, p & 0xF0);
    W8(wm_BlockXPos + 1, p >> 8);
    W8(wm_LayerInProcess, (RX8(wm_BounceSprTable, x) >> 7) & 1);
    generate_tile();
}

/* CODE_028752: m4 = tipo (7 = romper), m6 = lado, m7 = bloque final */
static void bounce_spawn(void)
{
    u8 y, kind = R8(m4);
    if (kind == 0x07) {                       /* bloque giratorio que se rompe */
        W8(wm_MarioSpeedY, 0xD0);
        mario_events |= MEV_BOUNCE;
        W8(wm_BlockId, 0x02);
        generate_tile();
        return;
    }
    for (y = 3; ; y--) {                    /* NotBreakable: ranura libre */
        if (!RX8(wm_BounceSprNum, y))
            goto found;
        if (y == 0)
            break;
    }
    y = (u8)(R8(wm_BounceSprAltIndex) - 1);
    if (NEG(y))
        y = 3;
    W8(wm_BounceSprAltIndex, y);
    if (RX8(wm_BounceSprNum, y) == 0x07) {  /* termina el giro de la anterior */
        u16 by = R16(wm_BlockYPos), bx = R16(wm_BlockXPos), p;
        u8 id = R8(wm_BlockId);
        W8(wm_BlockYPos, RX8(wm_BounceSprYLo, y));
        W8(wm_BlockYPos + 1, RX8(wm_BounceSprYHi, y));
        p = (u16)((RX8(wm_BounceSprXLo, y) | (RX8(wm_BounceSprXHi, y) << 8)) + 0x0C);
        W8(wm_BlockXPos, p & 0xF0);
        W8(wm_BlockXPos + 1, p >> 8);
        W8(wm_BlockId, RX8(wm_BounceSprBlock, y));
        generate_tile();
        W16(wm_BlockYPos, by);
        W16(wm_BlockXPos, bx);
        W8(wm_BlockId, id);
    }
found:
    if (kind >= 0x10)
        kind = 0;
    (RX8(wm_BounceSprNum, y) = (u8)(kind + 1));
    (RX8(wm_BounceSprInit, y) = (u8)(0));
    (RX8(wm_BounceSprYLo, y) = (u8)(R8(wm_BlockYPos)));
    (RX8(wm_BounceSprYHi, y) = (u8)(R8(wm_BlockYPos + 1)));
    (RX8(wm_BounceSprXLo, y) = (u8)(R8(wm_BlockXPos)));
    (RX8(wm_BounceSprXHi, y) = (u8)(R8(wm_BlockXPos + 1)));
    (RX8(wm_BounceSprTable, y) = (u8)(R8(m6) | ((R8(wm_LayerInProcess) & 1) << 7)));
    (RX8(wm_BounceSprBlock, y) = (u8)(R8(m7)));
    (RX8(wm_BounceSprTimer, y) = (u8)(0x08));
    if (kind + 1 == 0x07)
        (RX8(wm_SpinBlockTimer, y) = (u8)(0xFF));
    mario_events |= MEV_BOUNCE;
}

/* CODE_02902D / CODE_02904D: una vez por frame, despues de Mario */
static const u8 bnc_spd_y[4] = { 0x80, 0x80, 0x80, 0x00 };     /* DATA_0290D6 */
static const u8 bnc_spd_x[4] = { 0x80, 0xE0, 0x20, 0x80 };     /* DATA_0290DA */

void blocks_update(void)
{
    int xi;
    if (R8(wm_MultiCoinBlkTimer) >= 2 && !R8(wm_SpritesLocked))
        W8(wm_MultiCoinBlkTimer, R8(wm_MultiCoinBlkTimer) - 1);
    for (xi = 3; xi >= 0; xi--) {
        u8 x = (u8)xi, num = RX8(wm_BounceSprNum, x), y;
        if (!num)
            continue;
        if (!R8(wm_SpritesLocked) && RX8(wm_BounceSprTimer, x))
            (RX8(wm_BounceSprTimer, x) = (u8)(RX8(wm_BounceSprTimer, x) - 1));
        if (R8(wm_SpritesLocked))
            continue;
        if (num == 0x07) {                  /* TurnBlockSpr */
            if (!RX8(wm_BounceSprInit, x)) {
                (RX8(wm_BounceSprInit, x) = (u8)(1));
                tile_from_bounce(x, 0x09);
            }
            if (RX8(wm_BounceSprTimer, x) == 1) {
                u16 p = (u16)((RX8(wm_BounceSprXLo, x) | (RX8(wm_BounceSprXHi, x) << 8)) + 8);
                (RX8(wm_BounceSprXLo, x) = (u8)(p & 0xF0));
                (RX8(wm_BounceSprXHi, x) = (u8)(p >> 8));
                tile_from_bounce(x, 0x05);  /* gira: se puede atravesar */
            }
            if (RX8(wm_SpinBlockTimer, x)) {
                (RX8(wm_SpinBlockTimer, x) = (u8)(RX8(wm_SpinBlockTimer, x) - 1));
                continue;
            }
            tile_from_bounce(x, RX8(wm_BounceSprBlock, x));
            (RX8(wm_BounceSprNum, x) = (u8)(0));
            continue;
        }
        /* BounceBlockSpr (1..6). El movimiento del sprite (sube y vuelve)
           no se porta: la posicion final se redondea a la del bloque. */
        y = RX8(wm_BounceSprTable, x) & 0x03;
        if (y == 3) { unsup(MARIO_UNSUP_TILE); continue; }  /* bloque de nota */
        if (!RX8(wm_BounceSprInit, x)) {
            (RX8(wm_BounceSprInit, x) = (u8)(1));
            tile_from_bounce(x, 0x09);
            if (bnc_spd_y[y] != 0x80)
                W8(wm_MarioSpeedY, bnc_spd_y[y]);
            if (bnc_spd_x[y] != 0x80)
                W8(wm_MarioSpeedX, bnc_spd_x[y]);
        }
        if (RX8(wm_BounceSprTimer, x))
            continue;
        {                                   /* TileFromBounceSpr0 */
            u8 id = RX8(wm_BounceSprBlock, x);
            if ((id == 0x0A || id == 0x0B) && R8(wm_MultiCoinBlkTimer) == 1) {
                W8(wm_MultiCoinBlkTimer, 0);
                id = 0x0D;
            }
            tile_from_bounce(x, id);
        }
        if (num >= 6)
            W8(wm_OnOffStatus, R8(wm_OnOffStatus) ^ 1);
        (RX8(wm_BounceSprNum, x) = (u8)(0));
    }
}

/* _00F17F: golpear un bloque. Entra A = tipo (0..$23), y = lado. */
static void f17f(u8 a, u8 y)
{
    u8 x = a, v, c;
    if (!(T8X(DATA_00F0EC, y) & T8X(DATA_00F0A4, x)))
        return;
    W8(m6, y);
    W8(m7, T8X(DATA_00F0C8, x));
    W8(m4, T8X(DATA_00F05C, x));
    v = T8X(DATA_00F080, x);
    if (NEG(v)) {
        if (v == 0xFF) {
            v = R8(wm_GreenStarCoins) ? 0x06 : 0x05;
            goto l_F1D0;
        }
        /* CODE_00F1AE: el contenido alterna segun la fila */
        c = v & 1;
        v = (u8)(((c << 7) | (R8(wm_BlockXPos) >> 1)) >> 3);
        v = T8X(DATA_00F100, v);
    }
    /* _00F1BA */
    c = v & 1;
    v >>= 1;
    if (c) {
        if (v == 0x03) {
            if (!R8(wm_StarPowerTimer))
                v = 0x06;
        } else if (!R8(wm_MarioPowerUp)) {
            v = 0x01;
        }
    }
l_F1D0:
    W8(m5, v);
    if (v == 0x05)
        W8(m7, 0x16);
    W8(wm_BlockYPos, R8(wm_BlockYPos) & 0xF0);
    W8(wm_BlockXPos, R8(wm_BlockXPos) & 0xF0);
    if (v == 0x06 && R8(TILESET) == 0x04) { unsup(MARIO_UNSUP_TILE); return; }
    bounce_spawn();
}

/* _00F160 */
static void f160(u8 a, u8 y)
{
    a = (u8)(a - 0x11);
    if (a < 0x1D) { f17f(a, y); return; }
    /* XBA / DATA_00A625[tileset]: 0 para el tileset 7 (y 0..3 en general) */
    if (R8(TILESET) != 7) { unsup(MARIO_UNSUP_TILE); return; }
    a = (u8)(a - 0x59);                     /* CODE_00F176, carry = 1 */
    if (a >= 2)
        return;
    f17f((u8)(a + 0x22), y);
}

/* _00F127 (y CODE_00F120 sin Yoshi) */
static void f127(u8 a, u8 y)
{
    u8 t = R8(TILESET);
    if (a == 0x2F)
        goto hurt;
    if (a < 0x59)
        goto pp;
    if (a < 0x5C) {
        if (t == 0x05 || t == 0x0D)
            goto hurt;
    }
    if (a < 0x5D)                           /* + CMP #$5D / BCC + */
        goto munch;
pp:
    if (a < 0x66 || a >= 0x6A) { f160(a, y); return; }
munch:
    if (t != 0x01) { f160(a, y); return; }  /* CODE_00F15F */
hurt:
    hurt_mario();
}

static void f120(u8 a, u8 y)
{
    if (R8(wm_OnYoshi)) { f160(a, y); return; }
    f127(a, y);
}

/* ------------------------------------------------------------------ */
/* CODE_00F3E9: entrar en una tuberia (vertical). A = direccion (2/3). */
static void f3e9(u8 dir)
{
    u8 a = (u8)(rY - 0x37), y;
    if (a >= 2)
        return;
    y = a;
    a = (u8)(R8(wm_PlayerBlkPosX) - T8X(DATA_00F3E3, y) - 1);   /* carry = 0 */
    if (a >= 5) { rY = R8(wm_Map16NumLo); return; }
    if (R8(wm_JoyPadA) & (dir == 2 ? 0x08 : 0x04)) {        /* PIPE_BUTTONS */
        mario_events |= MEV_PIPE;
        unsup(MARIO_UNSUP_PIPE);
    }
    rY = R8(wm_Map16NumLo);
}

/* CODE_00F3C4: tuberia horizontal ($3F) */
static void f3c4(u8 dir)
{
    if (rY != 0x3F)
        return;
    if (!R8(wm_8F)) {
        if (R8(wm_JoyPadA) & (dir ? 0x01 : 0x02)) {
            mario_events |= MEV_PIPE;
            unsup(MARIO_UNSUP_PIPE);
        }
    }
    rY = R8(wm_Map16NumLo);
}

/* CODE_00F267: agarrar un bloque para tirar ($12E con Y) */
static void f267(void)
{
    if (rY == 0x2E && (R8(wm_JoyFrameA) & 0x40)
        && !(R8(wm_IsCarrying2) | R8(wm_OnYoshi))) {
        mario_events |= MEV_SPRITE;
        unsup(MARIO_UNSUP_TILE);
    }
}

/* CODE_00F28C: puntos de control del 1-UP invisible */
static void f2c2(u8 a);
static void f28c(void)
{
    u8 a = (u8)(rY - 0x6F), ck;
    if (a >= 4) { f2c2(0x01); return; }     /* CODE_00F2C0 */
    ck = R8(wm_1UpInvsCheckPts);
    if (a != ck) {
        if ((u8)(a + 1) == ck || ck >= 4)
            return;
        a = 0xFF;
    }
    a = (u8)(a + 1);
    W8(wm_1UpInvsCheckPts, a);
    if (a == 4)
        mario_events |= MEV_1UP;
}

/* CODE_00F309: monedas, monedas de Yoshi, luna */
static void f309(void)
{
    u8 y = rY;
    if (y < 0x2F && y >= 0x2A) {
        /* CODE_00F32B */
        if (y == 0x2A && !R8(wm_BluePowTimer))
            return;
        if (y < 0x2D) {                     /* CODE_00F367: moneda */
            mario_events |= MEV_COIN;
            W8(wm_BlockId, 0x01);
        } else {
            if (y != 0x2D)                  /* mitad de abajo: sube un bloque */
                W8(wm_BlockXPos, R8(wm_BlockXPos) - 0x10);
            mario_events |= MEV_COIN;
            W8(wm_YoshiCoinsCollected, R8(wm_YoshiCoinsCollected) + 1);
            W8(wm_YoshiCoinsDisp, R8(wm_YoshiCoinsDisp) + 1);
            W8(wm_SoundCh1, 0x1C);
            W8(wm_BlockId, 0x18);
        }
        generate_tile();
        return;
    }
    if (y != 0x6E)
        return;
    mario_events |= MEV_COIN;               /* luna 3-UP */
    W8(wm_3UpMoonsCol, R8(wm_3UpMoonsCol) + 1);
    W8(wm_BlockId, 0x01);
    generate_tile();
}

/* CODE_00F2C9 */
static void f2c9(u8 a)
{
    u8 y = rY;
    if (y == 0x38) {                        /* cinta del punto medio */
        W8(wm_BlockId, 0x02);
        generate_tile();
        mario_events |= MEV_MIDWAY;
        if (!R8(wm_MarioPowerUp))
            W8(wm_MarioPowerUp, 0x01);
        W8(wm_SoundCh1, 0x05);
        return;
    }
    if (y != 0x06) {                        /* CODE_00F2EE */
        if (y < 0x07 || y >= 0x1D) { f309(); return; }
        a |= 0x80;
    }
    if (a == 0x01)
        a |= 0x18;
    W8(wm_8B, R8(wm_8B) | a);
    W8(wm_8C, R8(wm_PlayerBlkSide));
}

/* _00F2C2 */
static void f2c2(u8 a)
{
    if (rY < 0x06) { W8(wm_8A, R8(wm_8A) | a); return; }
    f2c9(a);
}

/* CODE_00F04D: bloques de agua de la pagina 1 */
static int f04d(u8 a)
{
    int x;
    for (x = 0x19; x >= 0; x--)
        if (T8X(DATA_00EAC1, x) == a)
            return 1;
    return 0;
}

/* CODE_00EFBC / _00EFCD: cintas transportadoras */
static void efcd(u8 x)
{
    if (R8(wm_FrameA) & 0x03)
        return;
    W16(wm_MarioXPos, R16(wm_MarioXPos) + T16X(DATA_00E913, x));
    W16(wm_MarioYPos, R16(wm_MarioYPos) + T16X(DATA_00E91F, x));
}
static void efbc(void)
{
    u8 x = R8(wm_Map16NumLo);
    if (x >= 0xCE && x < 0xD2)
        efcd((u8)((x - 0xCC) << 1));
}

/* CODE_00F005: empezar a correr por la pared (triangulos $0E/$0F).
   Devuelve 1 si hizo PLA/PLA/JMP _00EE35 (con Yoshi). */
static int f005(void)
{
    u8 a = (u8)(rY - 0x0E), x, t;
    if (a >= 2)
        return 0;
    a ^= 1;
    if (a != R8(wm_MarioDirection))
        return 0;
    x = a;
    t = R8(wm_PlayerBlkPosX);
    if (x & 1)
        t ^= 0x0F;
    if (t >= 8)
        return 0;
    if (R8(wm_OnYoshi)) {
        W8(wm_SoundCh3, 0x08);
        W8(wm_MarioSpeedY, 0x80);
        W8(wm_BouncingWithYoshi, 0x80);
        return 1;
    }
    if (NEG((u8)(R8(wm_MarioSpeedX) - T8X(DATA_00EAB9, x)) ^ T8X(DATA_00EAB9, x)))
        return 0;
    if (R8(wm_IsCarrying2) | R8(wm_IsDucking))
        return 0;
    W8(wm_WallWalkStatus, x + 2);
    return 0;
}

/* ------------------------------------------------------------------ */
/* _00EEE1: apoyar a Mario en el suelo (Y = tipo de pendiente) */
static void eee1(u8 y)
{
    u8 a, x;
    a = T8X(DATA_00E53D, y);
    if (a)
        goto p1;
    x = R8(wm_PlayerSlopePose);
    if (!x)
        goto p3;
    x = R8(wm_MarioSpeedX);
    if (!x)
        goto p2;
p1:
    W8(wm_OnSlopeTypeA, a);
    if (!(R8(wm_JoyPadA) & 0x04))
        goto p3;
    if (R8(wm_IsCarrying2) | R8(wm_PlayerSlopePose))
        goto p3;
    x = 0x1C;
p2:
    W8(wm_PlayerSlopePose, x);
p3:
    x = T8X(DATA_00E4B9, y);
    W8(wm_OnSlopeTypeB, x);
    if (y >= 0x1C)
        goto ef38;
    if (!R8(wm_MarioSpeedX) || !T8X(DATA_00E53D, y))
        goto ef31;
    if (!NEG(T8X(DATA_00E53D, y) ^ R8(wm_MarioSpeedX)))
        goto ef31;
    W8(wm_PlayerFrameIndex, x);
    a = R8(wm_MarioSpeedX);
    if (NEG(a))
        a = (u8)(-a);
    if (a >= 0x28) {
        a = T8X(DATA_00E4FB, y);
        goto ef60;
    }
    y = 0x20;                               /* CODE_00EF2F */
ef31:
    a = R8(wm_MarioSpeedY);
    if (a < T8X(DATA_00E4DA, y))
        goto ef3b;
ef38:
    a = T8X(DATA_00E4DA, y);
ef3b:
    if (NEG(R8(wm_8E))) { unsup(MARIO_UNSUP_LAYER); return; }
ef60:
    W8(wm_MarioSpeedY, a);
    if (NEG(a))
        W8(wm_IsOnGround, R8(wm_IsOnGround) + 1);
    W8(wm_FollowCage, 0);
    W8(wm_IsFlying, 0);
    W8(wm_IsClimbing, 0);
    W8(wm_BouncingWithYoshi, 0);
    W8(wm_IsSpinJump, 0);
    W8(wm_MarioObjStatus, R8(wm_MarioObjStatus) | 0x04);
    y = R8(wm_CapeGlidePhase);
    if (y) {                                /* CODE_00EF99 */
        W8(wm_SprChainStomped, 0);
        W8(wm_CapeGlidePhase, 0);
        if (y >= 5) {
            if (R8(wm_8F))
                mario_events |= MEV_POUND;
            return;
        }
        if (R8(wm_MarioPowerUp) == 2)
            W8(wm_PlayerSlopePose, (R8(wm_PlayerSlopePose) >> 1) | 0x80);
        return;
    }
    if (R8(wm_OnYoshi) && R8(wm_8F) && R8(wm_YoshiHasStomp))
        mario_events |= MEV_POUND;
    W8(wm_SprChainStomped, 0);
}

/* _00EED1: subir a Mario hasta la superficie y apoyarlo */
static void eed1(u8 y)
{
    u16 p;
    W8(wm_IsOnGround, R8(wm_IsOnGround) + 1);
    p = (u16)(R16(wm_MarioYPos)
              - (R8(wm_PlayerExitBlkPos) | (R8(wm_PlayerBlkPosY) << 8)));
    W16(wm_MarioYPos, p);
    eee1(y);
}

/* _00EE1D / CODE_00EE2D / _00EE35 */
static void ee1d(void)
{
    if (R8(wm_IsOnSolidSpr) && !NEG(R8(wm_MarioSpeedY))) {
        W8(wm_8E, 0);
        eee1(0x20);
        return;
    }
    if ((R8(wm_MarioObjStatus) & 0x04) | R8(wm_IsFlying))
        return;
    W8(wm_IsFlying, 0x24);
}

/* _00EE85 */
static void ee85(u8 y)
{
    if (NEG(R8(wm_MarioSpeedY)) && R8(wm_8D) < 2)
        return;
    if (R8(wm_WhichSwitchPressed)) {        /* interruptor de palacio */
        mario_events |= MEV_SWITCH;
        unsup(MARIO_UNSUP_TILE);
        return;
    }
    eed1(y);
}

/* ------------------------------------------------------------------ */
/* CODE_00EB77: las sondas de la capa 1 */
static void eb77(void)
{
    u8 a, y, t;

    if (!probe_ok)
        probe_init();
    probe_mx = R16(wm_MarioXPos);
    probe_my = R16(wm_MarioYPos);
    rX = 0;
    if (R8(wm_MarioPowerUp) && !R8(wm_IsDucking))
        rX = 0x18;
    if (R8(wm_OnYoshi))
        rX = (u8)(rX + 0x30);
    a = R8(wm_MarioXPos) & 0x0F;
    y = a;
    W8(wm_PlayerBlkPosX, (a + 8) & 0x0F);
    W8(wm_PlayerBlkSide, 0);
    if (y >= 8) {
        rX = (u8)(rX + 0x0C);               /* TXA / ADC #$0B con carry */
        W8(wm_PlayerBlkSide, 1);
    }
    W8(wm_PlayerExitBlkPos,
       (R8(wm_PlayerBlkPosY) + T8X(DATA_00E89C + 8, rX)) & 0x0F);

    /* --- sonda 1: el costado, a la altura de la cabeza ------------- */
    a = f44d();
    if (a == 0)
        goto l_EBDD;
    if (rY < 0x11)
        goto l_EC24;
    if (rY < 0x6E)
        goto l_EBC9;
    if (f04d(rY))
        W8(wm_8A, R8(wm_8A) | 0x01);
    goto l_EC24;

l_EBC9:
    rX = (u8)(rX + 4);
    a = rY;
    rY = (a == 0x1E || a == 0x52) ? 0 : 2;
    goto l_EC6F;

l_EBDD:
    y = rY;
    if (y == 0x9C && R8(TILESET) == 0x01)
        goto l_door3;
    if (y == 0x20)
        goto l_door2;
    if (y != 0x1F) {
        if (!R8(wm_BluePowTimer))
            goto l_EC21;
        if (y == 0x28)
            goto l_door2;
        if (y != 0x27)
            goto l_EC21;
    }
    if (R8(wm_MarioPowerUp))
        goto l_EC24;
l_door2:
    if (f443())
        goto l_EC24;
l_door3:
    if (R8(wm_8F) || !(R8(wm_JoyFrameA) & 0x08))
        goto l_EC24;
    mario_events |= MEV_PIPE;               /* puerta */
    unsup(MARIO_UNSUP_PIPE);
    return;

l_EC21:
    f28c();

    /* --- sonda 2: el costado, a la altura del cuerpo --------------- */
l_EC24:
    a = f44d();
    if (a == 0) {
        f2c9(0x10);                         /* CODE_00EC35 */
        goto l_EC3A;
    }
    if (rY < 0x11 || rY >= 0x6E)
        goto l_EC3A;
    rX = (u8)(rX + 2);
    goto l_EC4E;

    /* --- sonda 3: el costado, a la altura de los pies -------------- */
l_EC3A:
    a = f44d();
    if (a == 0) {
        f2c9(0x08);
        goto l_EC8A;
    }
    if (rY < 0x11 || rY >= 0x6E)
        goto l_EC8A;

l_EC4E:
    if (R8(wm_MarioDirection) != R8(wm_PlayerBlkSide)) {
        u8 sx = rX;
        f3c4(R8(wm_MarioDirection));
        f267();
        rY = R8(wm_Map16NumLo);
        rX = sx;
    }
    W8(wm_PlayerFrameIndex, 0x03);
    y = R8(wm_PlayerBlkSide);
    if ((R8(wm_MarioXPos) & 0x0F) == T8X(DATA_00E911, y))
        goto l_EC8A;
    rY = y;

l_EC6F:
    if (R8(wm_NoteBlkBounceFlag) && R8(wm_Map16NumLo) == 0x52)
        goto l_EC8A;
    a = T8X(DATA_00E90A, rY);
    W8(wm_MarioObjStatus, R8(wm_MarioObjStatus) | a);
    rY = a & 0x03;
    f127(R8(wm_Map16NumLo), rY);

    /* --- sonda 4: la cabeza (techo) -------------------------------- */
l_EC8A:
    a = f44d();
    if (a != 0)
        goto l_ECB1;
    f2c2(0x02);
    if (!NEG(R8(wm_MarioSpeedY)))
        goto l_ED4A;
    a = R8(wm_Map16NumLo);
    if (a < 0x21 || a >= 0x25)
        goto l_ED4A;
    f17f((u8)(a - 0x04), 0);                /* CODE_00ECA6: bloque de nota... */
    a = 0xF0;
    goto l_ED0F;

l_ECB1:
    if (rY < 0x11)
        goto l_ED4A;
    if (rY < 0x6E)
        goto l_ECFA;
    if (rY >= 0xD8) {
        W16(wm_BlockXPos, R16(wm_BlockXPos) + 0x10);
        a = f461();
        if (a == 0)
            goto l_ED4A;
        if (rY < 0x6E || rY >= 0xD8)
            goto l_ED4A;
        W8(wm_PlayerExitBlkPos, R8(wm_PlayerExitBlkPos) - 0x10);  /* SBC #$0F, C=0 */
    }
    t = T8V(R16(wm_SlopeSteepness) + (u8)(rY - 0x6E));
    a = T8(DATA_00E632 + ((t << 4) | R8(wm_PlayerBlkPosX)));
    if (NEG(a))
        goto l_ED0F;
    goto l_ED4A;

l_ECFA:
    f3e9(0x02);
    a = rY;
    rY = 0;
    f127(a, 0);
    if (R8(wm_Map16NumLo) == 0x1E)
        goto l_ED3B;
    a = 0xF0;                               /* _00ED0D */
l_ED0F:
    a = (u8)(a + R8(wm_PlayerExitBlkPos));
    if (!NEG(a))
        goto l_ED4A;
    if (a >= 0xF9 || R8(wm_IsFlying)) {
        /* CODE_00ED28 */
        if (R8(wm_IsFlying)) {
            probe_my = (u16)(probe_my + (u8)~a);
            W16(wm_MarioYPos, probe_my);
        }
        W8(wm_MarioObjStatus, R8(wm_MarioObjStatus) | 0x08);
    } else {
        W8(wm_MarioObjStatus, (R8(wm_MarioObjStatus) & 0xFC) | 0x09);
        W8(wm_MarioSpeedX, 0);
    }
l_ED3B:
    if (NEG(R8(wm_MarioSpeedY))) {
        W8(wm_MarioSpeedY, 0);
        if (!R8(wm_SoundCh1))
            W8(wm_SoundCh1, 1);
    }

    /* --- sonda 5: los pies (suelo) --------------------------------- */
l_ED4A:
    a = f44d();
    if (a == 0)
        goto l_EDDB;
    if (rY < 0x6E) {
        f3e9(0x03);
        goto l_EDF7;
    }
    if (rY < 0xD8)
        goto l_ED86;
    if (rY >= 0xFB) {
        f629();
        return;
    }
    /* CODE_00ED69 */
    W16(wm_BlockXPos, R16(wm_BlockXPos) - 0x10);
    a = f461();
    if (a == 0 || rY < 0x6E || rY >= 0xD8)
        goto l_EDE9;
    W8(wm_PlayerBlkPosY, R8(wm_PlayerBlkPosY) + 0x10);   /* ADC #$10, C=0 */

l_ED86:
    t = R8(TILESET);
    if ((t == 0x03 || t == 0x0E) && rY >= 0xD2)
        goto l_EDE9;
    t = T8V(R16(wm_SlopeSteepness) + (u8)(rY - 0x6E));
    a = (u8)(R8(wm_PlayerBlkPosY) - T8(DATA_00E632 + ((t << 4) | R8(wm_PlayerBlkPosX))));
    if (NEG(a))
        W8(wm_IsOnGround, R8(wm_IsOnGround) + 1);
    rY = t;
    if (a >= T8X(DATA_00E51C, rY))
        goto l_EDE9;
    W8(wm_PlayerExitBlkPos, a);
    W8(wm_PlayerBlkPosY, 0);
    if (f005()) {
        W8(wm_IsFlying, 0x24);              /* PLA/PLA/JMP _00EE35 */
        return;
    }
    if (rY >= 0x1C) {
        W8(wm_SlideImgTimer, 0x08);
        eed1(rY);
        return;
    }
    efbc();                                 /* CODE_00EDD5 */
    ee85(rY);
    return;

l_EDDB:
    if (rY == 0x05)
        f629();
    else
        f2c2(0x04);

    /* --- sonda 6: los pies, segundo punto -------------------------- */
l_EDE9:
    a = f44d();
    if (a == 0) {
        f309();
        ee1d();
        return;
    }
    if (rY >= 0x6E) {
        ee1d();
        return;
    }
l_EDF7:
    if (NEG(R8(wm_MarioSpeedY)))
        return;
    t = R8(TILESET);
    if ((t == 0x03 || t == 0x0E) && R8(wm_Map16NumLo) >= 0x59 && R8(wm_Map16NumLo) < 0x5C) {
        ee1d();
        return;
    }
    a = R8(wm_PlayerBlkPosY) & 0x0F;
    W8(wm_PlayerBlkPosY, 0);
    W8(wm_PlayerExitBlkPos, a);
    if (a >= 8) {
        ee1d();
        return;
    }
    /* CODE_00EE3A: de pie sobre un bloque solido */
    rY = R8(wm_Map16NumLo);
    if (t == 0x02 || t == 0x08) {
        a = (u8)(rY - 0x0C);
        if (a < 2) {
            efcd((u8)(a << 1));
            ee85(0x20);
            return;
        }
    }
    f267();                                 /* CODE_00EE57 */
    rY = 0x03;
    a = R8(wm_Map16NumLo);
    if (a == 0x1E) {
        if (R8(wm_8F) && R8(wm_MarioPowerUp) && R8(wm_IsSpinJump)) {
            f17f(0x21, 0x03);               /* romper el bloque giratorio */
            ee1d();
            return;
        }
    } else {
        if (a == 0x32)
            W8(wm_RunEaterBlock, 0);
        f120(a, rY);
    }
    ee85(0x20);                             /* _00EE83 */
}

/* CODE_00EADB */
static void eadb(void)
{
    W8(wm_PlayerBlkPosY, R8(wm_MarioYPos) & 0x0F);
    if (R8(wm_WallWalkStatus)) {            /* CODE_00EAE9: correr por la pared */
        unsup(MARIO_UNSUP_WALL);
        return;
    }
    eb77();
}

/* CODE_00EAA6 */
static void eaa6(void)
{
    W8(wm_PlayerFrameIndex, 0);
    W8(wm_MarioObjStatus, 0);
    W8(wm_OnSlopeTypeB, 0);
    W8(wm_OnSlopeTypeA, 0);
    W8(wm_8A, 0);
    W8(wm_8B, 0);
    W8(wm_IsTouchLayer2, 0);
}

/* CODE_00E92B */
static void e92b(void)
{
    u8 a, y;
    u16 t;
    int n;

    eaa6();
    if (R8(wm_FallThroughFlag)) {
        ee1d();
        goto l_E98C;
    }
    W8(wm_8D, R8(wm_IsOnGround));
    W8(wm_IsOnGround, 0);
    W8(wm_8F, R8(wm_IsFlying));
    if (NEG(R8(wm_IsVerticalLvl))) {        /* capa 2 interactiva */
        unsup(MARIO_UNSUP_LAYER);
        return;
    }
    W8(wm_IsOnGround, R8(wm_IsOnGround) << 1);
    a = R8(wm_IsVerticalLvl) & 0x41;
    W8(wm_8E, a);
    if (!NEG((u8)(a << 1))) {
        W8(wm_LayerInProcess, 0);
        W8(wm_8D, R8(wm_8D) << 1);
        eadb();
    }

l_E98C:
    if (R8(wm_SideExitFlag)) { unsup(MARIO_UNSUP_LAYER); return; }

    /* CODE_00E9A1: bordes de la pantalla */
    if (R8(wm_MarioScrPosX) >= 0xF0) {
        f629();
        goto l_EA32;
    }
    if (R8(wm_MarioObjStatus) & 0x03)
        goto l_E9FB;
    y = 0;
    t = (u16)(R16(wm_L1NextPosX) + 0x00E8);
    n = (s16)(u16)(t - R16(wm_MarioXPos));
    if (n != 0 && n > 0) {
        y = 1;
        n = (s16)(u16)(R16(wm_MarioXPos) - 0x0008 - R16(wm_L1NextPosX));
    }
    if (n == 0 || n > 0)                    /* _00E9C8: BEQ / BPL */
        goto l_E9FB;
    if (!R8(wm_HorzScrollHead)) {
        u8 sp;
        W8(wm_MarioObjStatus, R8(wm_MarioObjStatus) | 0x80);
        sp = (u8)(R16(wm_ScrollSpeedL1X) >> 4);
        if (!NEG((u8)((u8)(sp - R8(wm_MarioSpeedX)) ^ T8X(DATA_00E90D + 1, y)))) {
            W8(wm_MarioSpeedX, sp);
            W8(wm_PlayerXAccFixed, R8(wm_SprScrollL1X));
        }
    }
    W8(wm_MarioObjStatus, R8(wm_MarioObjStatus) | T8X(DATA_00E90A, y));

l_E9FB:
    if ((R8(wm_MarioObjStatus) & 0x1C) == 0x1C && !R8(wm_IsOnSolidSpr)) {
        f629();                             /* aplastado */
        goto l_EA32;
    }
    /* CODE_00EA0D */
    a = R8(wm_MarioObjStatus) & 0x03;
    if (a) {
        y = a & 0x02;
        W16(wm_MarioXPos, R16(wm_MarioXPos) + T16X(DATA_00E90D, y));
        if (NEG(R8(wm_MarioObjStatus)))
            goto l_EA34;
        W8(wm_PlayerFrameIndex, 0x03);
        if (!NEG(R8(wm_MarioSpeedX) ^ T8X(DATA_00E90D, y)))
            goto l_EA34;
l_EA32:
        W8(wm_MarioSpeedX, 0);
    }
l_EA34:
    if (R8(wm_IsBehindScenery) == 0x01 && !R8(wm_8B))
        W8(wm_IsBehindScenery, 0);
    W8(wm_IsOnWaterTop, 0);
    if (R8(wm_IsWaterLevel) || (R8(wm_8A) & 0x01)) {
        unsup(MARIO_UNSUP_WATER);
        return;
    }
    W8(wm_IsSwimming, 0);                   /* _00EAA3 */
}

/* CODE_00DC4F: velocidad (4.4 con signo) -> posicion + fraccion */
static void dc4f(u8 x)
{
    u8 v = RX8(wm_MarioSpeedX, x), f;
    u16 d;
    unsigned sum;
    sum = (unsigned)(u8)(v << 4) + RX8(wm_PlayerXAccFixed, x);
    f = (u8)sum;
    (RX8(wm_PlayerXAccFixed, x) = (u8)(f));
    d = (u16)((v >> 4) & 0x0F);
    if (d >= 8)
        d |= 0xFFF0;
    W16(wm_MarioXPos + x, (u16)(d + R16(wm_MarioXPos + x) + (sum >> 8)));
}

/* CODE_00DC2D */
static void dc2d(void)
{
    u8 a;
    W8(wm_8A, R8(wm_MarioSpeedY));
    if (R8(wm_WallWalkStatus)) {
        a = R8(wm_MarioSpeedX);
        if (R8(wm_WallWalkStatus) & 1)
            a = (u8)(-a);
        W8(wm_MarioSpeedY, a);
    }
    dc4f(0);
    dc4f(2);
    W8(wm_MarioSpeedY, R8(wm_8A));
}

/* CODE_00F595 */
static void f595(void)
{
    u16 t = (u16)(0xFF80 + R16(wm_Bg1VOfs));
    if (!((u16)(t - R16(wm_MarioYPos)) & 0x8000))
        W16(wm_MarioYPos, t);
    if (NEG((u8)(R8(wm_MarioScrPosY + 1) - 1)))
        return;
    if (R8(wm_YoshiWingsAboveGrnd)) { unsup(MARIO_UNSUP_YOSHI); return; }
    /* _00F60A: se cayo por abajo */
    W8(wm_MusicCh1, 0x09);
    W8(wm_LevelMusicMod, 0xFF);
    W8(wm_MarioAnimation, 0x09);
    W8(wm_IsSpinJump, 0);
    W8(wm_PlayerAnimTimer, 0x30);
    W8(wm_SpritesLocked, 0x30);
    W8(wm_CapeGlidePhase, 0);
    W8(wm_188A, 0);
    mario_events |= MEV_DEATH;
}

/* ------------------------------------------------------------------ */
/* CODE_00CD24 ... CODE_00CD82: un frame de Mario en un nivel normal
   (modo < $80), sin trepar ni nadar. */
void mario_collide(void)
{
    mario_unsupported = MARIO_OK;
    mario_events = 0;
    if (NEG(R8(wm_MarioSpeedY)) && (R8(wm_MarioObjStatus) & 0x08))
        W8(wm_MarioSpeedY, 0);
    dc2d();
    e92b();
    if (mario_unsupported)
        return;
    f595();
    /* _00CD39 */
    W8(wm_PlayerTurningPose, 0);
    if (R8(wm_PBalloonFrame)) { unsup(MARIO_UNSUP_TILE); return; }
    if (R8(wm_CanClimbAir))
        W8(wm_8B, 0x1F);
    if (R8(wm_IsClimbing)) { unsup(MARIO_UNSUP_CLIMB); return; }
    if (!(R8(wm_IsCarrying2) | R8(wm_OnYoshi)) && (R8(wm_8B) & 0x1B) == 0x1B
        && (R8(wm_JoyPadA) & 0x0C)
        && (R8(wm_IsFlying) || (R8(wm_JoyPadA) & 0x08) || (R8(wm_8B) & 0x04))) {
        unsup(MARIO_UNSUP_CLIMB);
        return;
    }
    if (R8(wm_IsSwimming)) { unsup(MARIO_UNSUP_WATER); return; }
}
