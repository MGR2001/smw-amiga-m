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

/* build de la Amiga: rutinas de player/logic68k.s en vez del C */
#if defined(__VBCC__) && !defined(NOASM)
#define LOGIC68K 1
#endif
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
        if (!RX8(wm_SpriteStatus, x))
            break;
        x--;
        if (x == stop) {
            if (num == 0x7B) {              /* cinta de meta: otra pasada */
                if (!mario_unsupported) mario_unsupported = MARIO_UNSUP_TILE;
                return 0;
            }
            (RX8(wm_SprLoadStatus, index) = (u8)(0));    /* sin ranura: se reintenta */
            return 0;
        }
    }
    /* CODE_02A93C / CODE_02A95B: nivel horizontal */
    (RX8(wm_SpriteYLo, x) = (u8)(r[0] & 0xF0));
    (RX8(wm_SpriteYHi, x) = (u8)(r[0] & 0x0D));
    (RX8(wm_SpriteXLo, x) = (u8)(col));
    (RX8(wm_SpriteXHi, x) = (u8)(scr));
    (RX8(wm_SpriteStatus, x) = (u8)(state));
    (RX8(wm_SpriteNum, x) = (u8)(state == 0x09 ? (u8)(num - 0xDA + 4) : num));
    (RX8(wm_SprIndexInLvl, x) = (u8)(index));
    if (R8(wm_SilverPowTimer) && !mario_unsupported)
        mario_unsupported = MARIO_UNSUP_TILE;
    init_sprite_tables(x);
    (RX8(wm_OffscreenHorz, x) = (u8)(1));
    (RX8(wm_DisSprCapeContact, x) = (u8)(4));
    spr_spawned |= (u8)(1 << x);
    return 1;
}

/* Primera entrada de spr_level con pantalla >= s, para s = 0..32: el bucle
   de LoadSprFromLevel salta con `continue` todas las de pantalla menor, asi
   que empezar ahi da lo mismo aunque la lista no estuviera ordenada, y no
   recorre el nivel entero cada 2 frames (~3 000 ciclos en el 68000). Se
   arma una vez por nivel (cuando cambia spr_level). */
const u8 *sll_for;              /* global: logicbench -DWORST lo corrige */
static u8 sll_y[33], sll_i[33];
static void sll_build(void)
{
    /* una pasada: las s ya llenas son siempre un prefijo [0, hi) (la
       primera entrada con pantalla >= s llena todas las s <= su pantalla
       que faltaban), asi que cada entrada solo llena de hi a su pantalla */
    u8 y, i, hi = 0, scr;
    for (y = 1, i = 0; spr_level[y] != 0xFF; y += 3, i++) {
        scr = (u8)(((spr_level[y] << 3) & 0x10) | (spr_level[y + 1] & 0x0F));
        for (; hi <= scr; hi++) {
            sll_y[hi] = y;
            sll_i[hi] = i;
        }
    }
    for (; hi < 33; hi++) {                 /* sin entradas: el final */
        sll_y[hi] = y;
        sll_i[hi] = i;
    }
    sll_for = spr_level;
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
    if (spr_level != sll_for)
        sll_build();
    y = sll_y[scrn > 32 ? 32 : scrn];
    index = sll_i[scrn > 32 ? 32 : scrn];
    for (; spr_level[y] != 0xFF; y += 3, index++) {
        u8 b0 = spr_level[y], b1 = spr_level[y + 1], num = spr_level[y + 2];
        u8 scr = (u8)(((b0 << 3) & 0x10) | (b1 & 0x0F));
        if (scr < scrn)
            continue;
        if (scr != scrn)
            return;                         /* ordenados por pantalla */
        if ((b1 & 0xF0) != col || RX8(wm_SprLoadStatus, index))
            continue;
        (RX8(wm_SprLoadStatus, index) = (u8)(1));
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

#define SPR(t, x)       RX8(t, x)
#define SETSPR(t, x, v) (RX8(t, x) = (u8)(v))

static void spr_unsup(void) { if (!mario_unsupported) mario_unsupported = MARIO_UNSUP_TILE; }

/* ZeroSpriteTables + LoadSpriteTables (sprite_tables.s) */
static void init_sprite_tables(u8 x)
{
    /* desenrollado con desplazamientos constantes: el bucle sobre una tabla
       de u16 costaba ~3 900 ciclos en el 68000 cada vez que aparece uno */
    u8 n = SPR(wm_SpriteNum, x);
    SETSPR(wm_SprInWaterTbl, x, 0);     SETSPR(wm_SprBehindScrn, x, 0);
    SETSPR(wm_SpriteState, x, 0);       SETSPR(wm_SpriteMiscTbl3, x, 0);
    SETSPR(wm_SpriteMiscTbl4, x, 0);    SETSPR(wm_SpriteMiscTbl5, x, 0);
    SETSPR(wm_SpriteDir, x, 0);         SETSPR(wm_SprObjStatus, x, 0);
    SETSPR(wm_SpriteOffTbl, x, 0);      SETSPR(wm_SpriteGfxTbl, x, 0);
    SETSPR(wm_SpriteDecTbl1, x, 0);     SETSPR(wm_SpriteDecTbl2, x, 0);
    SETSPR(wm_SpriteDecTbl3, x, 0);     SETSPR(wm_SpriteDecTbl4, x, 0);
    SETSPR(wm_DisSprCapeContact, x, 0); SETSPR(wm_SprChainKillTbl, x, 0);
    SETSPR(wm_SpriteMiscTbl6, x, 0);    SETSPR(wm_SpriteSpeedX, x, 0);
    SETSPR(wm_SpriteXAcc, x, 0);        SETSPR(wm_SpriteSpeedY, x, 0);
    SETSPR(wm_SpriteYAcc, x, 0);        SETSPR(wm_SpriteInterTbl, x, 0);
    SETSPR(wm_SpriteEatenTbl, x, 0);    SETSPR(wm_SpriteDecTbl6, x, 0);
    /* Tweaker1656..1686: los pone abajo (en el ROM se ponen a 0 y despues
       se cargan; escribirlos dos veces hace que el vbcc de 2022 saque la
       direccion como absoluta, P36) */
    SETSPR(wm_SprStompImmuneTbl, x, 0);
    SETSPR(wm_SpriteMiscTbl8, x, 0);    SETSPR(wm_SpriteMiscTbl7, x, 0);
    SETSPR(wm_SpriteMiscTbl1, x, 0);    SETSPR(wm_1FD6, x, 0);
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
#ifdef LOGIC68K
void spr_pos_axis_asm(u8 x, u8 o);
#define spr_pos_axis spr_pos_axis_asm       /* player/logic68k.s */
#else
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
#endif

/* CODE_019441 / _01944D / CODE_0194BF: el bloque bajo el punto de choque
   y (0..3: derecha, izquierda, abajo, arriba). Deja m0, m10-m13, m15. */
#if defined(__VBCC__) && !defined(NOASM)
/* build de la Amiga: la llama player/logic68k.s (spr_tile_asm) en los
   casos raros; el asm usa estas tablas y scr_ofs */
u8 spr_tile_c(u8 x, u8 y);
u8 spr_tile_asm(u8 x, u8 y);
/* punteros asignados en tiempo de ejecucion (logic68k_init): uno
   inicializado en la declaracion guardaria la direccion ABSOLUTA del
   ensamblado, y el binario se carga en cualquier sitio (P36) */
const u8 *spr_clip_x, *spr_clip_y, *gdi_ofs, *gdi_bit;
u8 logic68k_zero;               /* siempre 0: con "tabla + 0 de la RAM" vbcc
                                   calcula la direccion con lea d16(a4); con
                                   "= tabla" emite move.l #etiqueta (absoluta) */
void logic68k_init(void)
{
    spr_clip_x = tx_SprObjClipX + logic68k_zero;
    spr_clip_y = tx_SprObjClipY + logic68k_zero;
    gdi_ofs = tx_03B75C + logic68k_zero;
    gdi_bit = tx_03B75E + logic68k_zero;
}
u8 spr_tile_c(u8 x, u8 y)
#else
static u8 spr_tile(u8 x, u8 y)
#endif
{
    u16 py, px, o;
    u8 a, lo;
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
    if ((px & 0x8000) || (u8)(px >> 8) >= R8(wm_ScreensInLvl)) goto out;
    /* tabla de pantallas en vez de MULU, y el bloque en locales: con
       map16_lo[o] en cada comparacion vbcc releia el puntero y el byte
       (escribir ram[] podria cambiarlos) */
    o = (u16)(scr_ofs[(u8)(px >> 8) & 0x1F] + (py & 0x1F0) + ((u8)px >> 4));
    lo = map16_lo[o];
    a = map16_hi[o];
    W8(wm_Map16NumLo, lo);
    if (a ? (lo == 0x32 || lo == 0x2F)
          : (lo == 0x29 || lo == 0x2B || (u8)(lo - 0xEC) < 0x10))
        spr_unsup();                        /* bloques de los interruptores P */
    return a;
out:                                        /* CODE_0194B4 */
    W8(wm_Map16NumLo, 0);
    W8(wm_SprMoveDownPixels, 0);
    return 0;
}

#ifdef LOGIC68K
#define spr_tile spr_tile_asm
#endif

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
    if (t >= 0xD8)
        goto l_386;
    {   /* pendiente: CODE_00FA19 */
        u8 s8 = T8V(R16(wm_SlopeSteepness) + (u8)(t - 0x6E)), h;
        u16 idx = (u16)((s8 << 4) | (R8(m10) & 0x0F));
        W8(m8, s8);
        W8(m0, R8(m12) & 0x0F);
        h = T8(DATA_00E632 + idx);
        if (h == 0x10)
            return;
        if (h > 0x10)
            goto l_386;
        if (R8(m0) < 0x0C && R8(m0) < h)
            return;
        W8(wm_SprMoveDownPixels, h);
        a = T8X(DATA_00E53D, s8);
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
    goto l_B8;
l_386:                                      /* CODE_019386: sube 1 px y repite */
    if ((R8(m12) & 0x0F) >= 5)
        return;
    a = SPR(wm_SpriteStatus, x);
    if (a == 0x02 || a == 0x05 || a == 0x0B)
        return;
    {
        u16 v = (u16)((SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8) - 1);
        SETSPR(wm_SpriteYLo, x, (u8)v);
        SETSPR(wm_SpriteYHi, x, v >> 8);
    }
    spr_obj_vert(x);
    return;
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
#ifdef LOGIC68K
int get_draw_info_asm(u8 x);
#define get_draw_info get_draw_info_asm     /* player/logic68k.s */
#else
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
#endif

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

/* GetMarioClipping + GetSpriteClippingA + CheckForContact: 1 si las cajas
   de Mario y del sprite se tocan. */
static int spr_mario_contact(u8 x)
{
    u8 k = 0, i, c;
    u16 mx, my, sx, sy;
    u8 mw = 0x0C, mh, sw, sh;
    if (!(R8(wm_IsDucking) == 0 && R8(wm_MarioPowerUp)))
        k = 1;
    if (R8(wm_OnYoshi))
        k += 2;
    mx = (u16)(R16(wm_MarioXPos) + 2);
    my = (u16)(R16(wm_MarioYPos) + tx_MarioClipDispY[k]);
    mh = tx_MarioClipH[k];
    c = SPR(wm_Tweaker1662, x) & 0x3F;
    sx = (u16)((SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8) + (s8)tx_ClipDispX[c]);
    sy = (u16)((SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8) + (s8)tx_ClipDispY[c]);
    sw = tx_ClipWidth[c];
    sh = tx_ClipHeight[c];
    for (i = 0; i < 2; i++) {               /* X = 1 (Y), X = 0 (X) */
        u16 a = i ? mx : my, b = i ? sx : sy;
        u8 wa = i ? mw : mh, wb = i ? sw : sh;
        if ((u16)(a - b + 0x80) >= 0x100)
            return 0;
        if ((u8)(wa + wb) < (u8)((u8)b - (u8)a + wb))
            return 0;
    }
    return 1;
}

/* MarioSprInteractRt, hasta el contacto (el Rex tiene Tweaker167A bit 7:
   la reaccion la hace el propio sprite) */
static int process_interact(u8 x);
static int mario_spr_interact(u8 x)
{
    if (!(SPR(wm_Tweaker167A, x) & 0x20)
        && (((x ^ R8(wm_FrameA)) & 1) | SPR(wm_OffscreenHorz, x)))
        return 0;
    if (!process_interact(x))
        return 0;
    if (!NEG(SPR(wm_Tweaker167A, x))) {
        spr_unsup();                        /* DefaultInteractR: otros sprites */
        return 0;
    }
    return 1;
}

/* ProcessInteract: distancia gruesa + cajas (1 = contacto) */
static int process_interact(u8 x)
{
    (void)sub_horiz_pos(x);
    if ((u8)(R8(m15) + 0x50) >= 0xA0)
        return 0;
    {   /* CODE_01AD42 */
        u16 d = (u16)(R16(wm_PlayerYPosLv) - (SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8));
        W8(m14, (u8)d);
        if ((u8)((u8)d + 0x60) >= 0xC0)
            return 0;
    }
    if (R8(wm_MarioAnimation) >= 1)
        return 0;
    if (!(R8(wm_LevelMode) & 0x40) && (R8(wm_IsBehindScenery) ^ SPR(wm_SprBehindScrn, x)))
        return 0;
    return spr_mario_contact(x);
}

/* CODE_01B457 (InvisBlkMainRt): el sprite como bloque solido para Mario */
static const s8 blk_push_lo[6] = { 14, -15, 16, -32, 31, -15 };  /* DATA_01B4F9 */
static const u8 blk_push_hi[6] = { 0, 0xFF, 0, 0xFF, 0, 0xFF };  /* DATA_01B4FF */
static void invis_blk(u8 x)
{
    u8 m0v, a, y, n;
    if (!process_interact(x))
        return;
    m0v = (u8)(SPR(wm_SpriteYLo, x) - R8(wm_Bg1VOfs));
    if (NEG((u8)((u8)(R8(wm_MarioScrPosY) + 0x18) - m0v))) {    /* encima */
        u16 p;
        if (NEG(R8(wm_MarioSpeedY)) || (R8(wm_MarioObjStatus) & 0x08))
            return;
        W8(wm_MarioSpeedY, 0x10);
        W8(wm_IsOnSolidSpr, 1);
        p = (u16)((SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8)
                  - (R8(wm_OnYoshi) ? 0x2F : 0x1F));
        W16(wm_MarioYPos, p);
        if (!(R8(wm_MarioObjStatus) & 0x03))
            W16(wm_MarioXPos, R16(wm_MarioXPos) + (u16)(s16)(s8)SPR(wm_SpriteMiscTbl4, x));
        return;
    }
    /* CODE_01B4B4 */
    if (SPR(wm_Tweaker190F, x) & 1)
        return;
    a = (R8(wm_IsDucking) || !R8(wm_MarioPowerUp)) ? 0x08 : 0x00;
    if (R8(wm_OnYoshi))
        a = (u8)(a + 0x08);                 /* ADC #$08, carry 0 */
    if ((u8)(a + R8(wm_MarioScrPosY)) >= m0v) {  /* desde abajo */
        if (!NEG(R8(wm_MarioSpeedY)))
            return;
        W8(wm_MarioSpeedY, 0x10);
        if (SPR(wm_SpriteNum, x) >= 0x83) {
            SETSPR(wm_SpriteDecTbl4, x, 0x0F);
            if (!SPR(wm_SpriteState, x)) {
                SETSPR(wm_SpriteState, x, 1);
                SETSPR(wm_SpriteDecTbl3, x, 0x10);
            }
        }
        W8(wm_SoundCh1, 0x01);
        return;
    }
    /* CODE_01B505: de costado */
    y = sub_horiz_pos(x);
    n = SPR(wm_SpriteNum, x);
    if (n == 0xA9)
        y += 2;
    else if (n == 0x9C || n == 0xBB || n == 0x60 || n == 0x49)
        y += 4;
    W16(wm_MarioXPos, (u16)((SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8)
                            + (u16)(s16)blk_push_lo[y]));
    (void)blk_push_hi;
    W8(wm_MarioSpeedX, 0);
}

/* FlyingBlock (sprite_1-1.s), el $83: vuela hacia la izquierda en onda */
static void spr_spr_interact(u8 y);

static void flying_block(u8 x)
{
    get_draw_info(x);                       /* SubSprGfx2Entry1: flags */
    SETSPR(wm_SpriteMiscTbl4, x, 0);
    if (!SPR(wm_SpriteState, x) && !R8(wm_SpritesLocked)) {
        if (!(R8(wm_FrameA) & 1)) {
            u8 y = SPR(wm_SpriteMiscTbl7, x) & 1, v;
            v = (u8)(SPR(wm_SpriteSpeedY, x) + tx_01AD68[y]);
            SETSPR(wm_SpriteSpeedY, x, v);
            if (v == tx_01AD6A[y])
                SETSPR(wm_SpriteMiscTbl7, x, SPR(wm_SpriteMiscTbl7, x) + 1);
        }
        spr_pos_axis(x, 0);
        if (SPR(wm_SpriteNum, x) != 0x83) { spr_unsup(); return; }
        SETSPR(wm_SpriteSpeedX, x, 0xF4);
        spr_pos_axis(x, 0x0C);
        SETSPR(wm_SpriteMiscTbl4, x, R8(wm_SprPixelMove));
        SETSPR(wm_SpriteMiscTbl6, x, SPR(wm_SpriteMiscTbl6, x) + 1);
    }
    spr_spr_interact(x);
    invis_blk(x);
    sub_offscreen3(x);
    if (SPR(wm_SpriteDecTbl3, x) == 0x08 && SPR(wm_SpriteState, x) != 0x02) {
        SETSPR(wm_SpriteState, x, SPR(wm_SpriteState, x) + 1);
        SETSPR(wm_SpriteDecTbl6, x, 0x50);
        W16(wm_BlockYPos, (u16)(SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8));
        W16(wm_BlockXPos, (u16)(SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8));
        SETSPR(wm_SprIndexInLvl, x, 0xFF);
        mario_events |= MEV_BOUNCE;         /* _02887D: suelta el objeto (pendiente) */
    }
}

/* InfoBox (sprite_3-1.s) */
static void info_box(u8 x)
{
    invis_blk(x);
    sub_offscreen3(x);
    if (SPR(wm_SpriteDecTbl3, x) == 1) {    /* termina el rebote: abre el mensaje */
        SETSPR(wm_SpriteDecTbl3, x, 0);
        SETSPR(wm_SpriteState, x, 0);
        W8(wm_MsgBoxTrig, (u8)(((SPR(wm_SpriteXLo, x) >> 4) & 1) + 1));
        mario_events |= MEV_SPRITE;
    }
    get_draw_info(x);                       /* GenericSprGfxRt2: flags para el frame siguiente */
}

/* SubSprSprInteract: la ranura y (la que corre) contra las de abajo.
   Portado el caso estado 8 contra estado 8 (CODE_01A56D: se dan vuelta);
   el resto marca mario_unsupported. */
static void spr_spr_interact(u8 y)
{
    int x;
    if (!y || !((y ^ R8(wm_FrameA)) & 1))
        return;
    for (x = y - 1; x >= 0; x--) {
        u16 a, b;
        u8 d, m0v, old;
        if (SPR(wm_SpriteStatus, x) < 0x08)
            continue;
        if ((((SPR(wm_Tweaker1686, x) | SPR(wm_Tweaker1686, y)) & 0x08) | SPR(wm_SpriteDecTbl4, x)
             | SPR(wm_SpriteDecTbl4, y) | SPR(wm_SpriteEatenTbl, x)
             | (SPR(wm_SprBehindScrn, x) ^ SPR(wm_SprBehindScrn, y))))
            continue;
        W8(wm_CheckSprInter, (u8)x);
        a = (u16)(SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8);
        b = (u16)(SPR(wm_SpriteXLo, y) | SPR(wm_SpriteXHi, y) << 8);
        if ((u16)(a - b + 0x10) >= 0x20)
            continue;
        a = (u16)((SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8)
                  + ((SPR(wm_Tweaker1662, x) & 0x0F) ? 10 : 2));
        b = (u16)((SPR(wm_SpriteYLo, y) | SPR(wm_SpriteYHi, y) << 8)
                  + ((SPR(wm_Tweaker1662, y) & 0x0F) ? 10 : 2));
        if ((u16)(a - b + 0x0C) >= 0x18)
            continue;
        /* CODE_01A4BA */
        if (SPR(wm_SpriteStatus, y) != 0x08 || SPR(wm_SpriteStatus, x) != 0x08) {
            spr_unsup();
            continue;
        }
        /* CODE_01A56D */
        a = (u16)(SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8);
        b = (u16)(SPR(wm_SpriteXLo, y) | SPR(wm_SpriteXHi, y) << 8);
        m0v = (u8)(a >= b);                /* ROL: el carry de la resta (sin prestamo) */
        if (!(SPR(wm_Tweaker1686, y) & 0x10)) {
            old = SPR(wm_SpriteDir, y);
            SETSPR(wm_SpriteDir, y, m0v);
            if (old != m0v && !SPR(wm_SpriteDecTbl5, y))
                SETSPR(wm_SpriteDecTbl5, y, 0x08);
        }
        if (!(SPR(wm_Tweaker1686, x) & 0x10)) {
            d = (u8)(m0v ^ 1);
            old = SPR(wm_SpriteDir, x);
            SETSPR(wm_SpriteDir, x, d);
            if (old != d && !SPR(wm_SpriteDecTbl5, x))
                SETSPR(wm_SpriteDecTbl5, x, 0x08);
        }
    }
}

/* LoadTweakerBytes (para sprites que no corre el port) */
void sprite_tweakers(u8 x)
{
    u8 n = SPR(wm_SpriteNum, x);
    SETSPR(wm_Tweaker1656, x, tx_1656[n]);
    SETSPR(wm_Tweaker1662, x, tx_1662[n]);
    SETSPR(wm_Tweaker166E, x, tx_166E[n]);
    SETSPR(wm_Tweaker167A, x, tx_167A[n]);
    SETSPR(wm_Tweaker1686, x, tx_1686[n]);
    SETSPR(wm_Tweaker190F, x, tx_190F[n]);
}

/* RexMainRt */
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
    spr_spr_interact(x);
    if (!mario_spr_interact(x))
        return;
    if (R8(wm_StarPowerTimer)) { spr_unsup(); return; }     /* RexStarKill */
    if (SPR(wm_SpriteDecTbl2, x))
        return;
    SETSPR(wm_SpriteDecTbl2, x, 0x08);
    if (NEG((u8)(R8(wm_MarioSpeedY) - 0x10))) {             /* RexWins */
        if (R8(wm_PlayerHurtTimer) | R8(wm_OnYoshi))
            return;
        mario_events |= MEV_HURT;
        spr_unsup();                        /* HurtMario */
        return;
    }
    mario_events |= MEV_SPRITE;             /* RexPoints, DisplayContactGfx */
    if (!R8(wm_IsClimbing))                 /* BoostMarioSpeed */
        W8(wm_MarioSpeedY, NEG(R8(wm_JoyPadA)) ? 0xA8 : 0xD0);
    if (R8(wm_IsSpinJump) | R8(wm_OnYoshi)) {   /* RexSpinKill */
        SETSPR(wm_SpriteStatus, x, 0x04);
        SETSPR(wm_SpriteDecTbl1, x, 0x1F);
        W8(wm_SoundCh1, 0x08);
        return;
    }
    SETSPR(wm_SpriteState, x, SPR(wm_SpriteState, x) + 1);
    if (SPR(wm_SpriteState, x) == 2) {
        SETSPR(wm_SpriteDecTbl3, x, 0x20);
        return;
    }
    SETSPR(wm_DisSprCapeContact, x, 0x0C);  /* SmushRex */
    SETSPR(wm_Tweaker1662, x, 0);
}

/* CODE_0180D2 (los temporizadores) + HandleSprite, para una ranura */
void sprite_run(u8 x)
{
    u8 st = SPR(wm_SpriteStatus, x);
    W8(wm_SprProcessIndex, x);
    if (st && !R8(wm_SpritesLocked)) {      /* CODE_0180D2: los temporizadores */
        u8 *p = ram + wm_SpriteDecTbl1 + x; /* desenrollado (un bucle sobre una */
        u8 v;                               /* tabla de direcciones costaba ~450 */
        if ((v = p[0]) != 0) p[0] = v - 1;  /* ciclos). Desplazamientos relativos */
        if ((v = p[12]) != 0) p[12] = v - 1;/* a DecTbl1: con p[wm_...] vbcc */
        if ((v = p[24]) != 0) p[24] = v - 1;/* -O=991 sumaba la base dos veces */
        if ((v = p[36]) != 0) p[36] = v - 1;
        if ((v = p[wm_DisSprCapeContact - wm_SpriteDecTbl1]) != 0)
            p[wm_DisSprCapeContact - wm_SpriteDecTbl1] = v - 1;
        if ((v = p[wm_SpriteDecTbl5 - wm_SpriteDecTbl1]) != 0)
            p[wm_SpriteDecTbl5 - wm_SpriteDecTbl1] = v - 1;
        if ((v = p[wm_SpriteDecTbl6 - wm_SpriteDecTbl1]) != 0)
            p[wm_SpriteDecTbl6 - wm_SpriteDecTbl1] = v - 1;
    }
    if (!st) {                              /* EraseSprite */
        SETSPR(wm_SprIndexInLvl, x, 0xFF);
        return;
    }
    if (SPR(wm_SpriteNum, x) == 0x83) {     /* bloque ? volador */
        if (st == 0x01) {                   /* InitFlyingBlock */
            SETSPR(wm_SpriteStatus, x, 0x08);
            SETSPR(wm_SpriteMiscTbl3, x, (SPR(wm_SpriteXLo, x) >> 4) & 0x03);
            SETSPR(wm_SpriteDir, x, SPR(wm_SpriteDir, x) + 1);
            return;
        }
        if (st == 0x08) { flying_block(x); return; }
        spr_unsup();
        return;
    }
    if (SPR(wm_SpriteNum, x) == 0xB9) {     /* caja de mensaje: sin init propio */
        if (st == 0x01) { SETSPR(wm_SpriteStatus, x, 0x08); return; }
        if (st == 0x08) { info_box(x); return; }
        spr_unsup();
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
