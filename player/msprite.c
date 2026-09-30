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

/* build de la Amiga: rutinas de player/logic68k.s en vez del C; lo que el
   asm llama deja de ser static (MSS) */
#if defined(__VBCC__) && !defined(NOASM)
#define LOGIC68K 1
#define MSS
#else
#define MSS static
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
static void load_column(void);
void sprite_load_level(void)
{
    spr_spawned = 0;
    if (R8(wm_FrameA) & 0x01)
        return;
    load_column();
}

/* _02A802: la columna que entra por el borde (sin mirar FrameA) */
static void load_column(void)
{
    u8 d, col, scrn, y, index;
    u16 c;
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

static void spr_unsup(void);

/* CODE_02ABF2 + CODE_02ACA1 (lv_read.s llama a CODE_02A751 al cargar el
   nivel, antes de CODE_01808C): vacia las ranuras y wm_SprLoadStatus y
   crea los sprites de las 32 columnas desde Bg1HOfs - $60 (dos llamadas
   al cargador por columna, con Layer1ScrollDir = 1). Nivel horizontal, sin
   objeto llevado de otro nivel. Despues hay que inicializarlos con una
   pasada de CODE_01808C (level_start_sprites, manim.c). */
void sprite_level_start(void)
{
    u8 k, dir;
    u16 h, i;
    spr_spawned = 0;
    for (k = 0; k < 0x40; k++)
        RX8(wm_SprLoadStatus, k) = 0;
    k = 12;
    do {
        k--;
        RX8(wm_SprIndexInLvl, k) = 0xFF;
        if (RX8(wm_SpriteStatus, k) == 0x0B)
            spr_unsup();                    /* un objeto llevado: pasa a la ranura 0 */
        RX8(wm_SpriteStatus, k) = 0;
    } while (k);
    for (i = 0; i <= 0x27A; i++)            /* $1693-$190D */
        W8(wm_Map16NumLo + i, 0);
    W8(wm_ScrollSprNum, 0);
    W8(wm_ScrollSprL2, 0);
    if (R8(wm_IsVerticalLvl) & 1) {         /* CODE_02AC5C: nivel vertical */
        spr_unsup();
        return;
    }
    dir = R8(wm_Layer1ScrollDir);           /* CODE_02ACA1 */
    h = R16(wm_Bg1HOfs);
    W8(wm_Layer1ScrollDir, 1);
    W16(wm_Bg1HOfs, h - 0x60);
    for (k = 0; k < 0x20; k++) {
        W8(wm_18B6, k);
        load_column();
        load_column();
        W16(wm_Bg1HOfs, R16(wm_Bg1HOfs) + 0x10);
    }
    W8(wm_18B6, 0x20);
    W16(wm_Bg1HOfs, h);
    W8(wm_Layer1ScrollDir, dir);
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

/* FlipSpriteDir: media vuelta (no si DecTbl5 corre: acaba de darla) */
static void flip_sprite_dir(u8 x)
{
    if (SPR(wm_SpriteDecTbl5, x))
        return;
    SETSPR(wm_SpriteDecTbl5, x, 0x08);
    SETSPR(wm_SpriteSpeedX, x, (u8)-SPR(wm_SpriteSpeedX, x));
    SETSPR(wm_SpriteDir, x, SPR(wm_SpriteDir, x) ^ 1);
}

/* FlipIfTouchingObj: contra una pared en la direccion en que mira */
static void flip_if_touching_obj(u8 x)
{
    if ((u8)(SPR(wm_SpriteDir, x) + 1) & SPR(wm_SprObjStatus, x) & 0x03)
        flip_sprite_dir(x);
}

/* SetAnimationFrame: 2 poses, 8 frames cada una */
static void set_anim_frame(u8 x)
{
    SETSPR(wm_SpriteMiscTbl6, x, SPR(wm_SpriteMiscTbl6, x) + 1);
    SETSPR(wm_SpriteGfxTbl, x, (SPR(wm_SpriteMiscTbl6, x) >> 3) & 1);
}

/* SetSomeYSpeed: en el suelo, SpeedY = 0 ($18 en pendiente o sobre la capa 2) */
static void set_some_yspeed(u8 x)
{
    SETSPR(wm_SpriteSpeedY, x,
           (NEG(SPR(wm_SprObjStatus, x)) || SPR(wm_SpriteSlopeTbl, x)) ? 0x18 : 0x00);
}

/* GetSpriteClippingA (a) + GetSpriteClippingB (b) + CheckForContact: 1 si
   las cajas de los dos sprites se tocan (sin dejar m0-m15) */
static int spr_spr_contact(u8 a, u8 b)
{
    u8 ca = SPR(wm_Tweaker1662, a) & 0x3F, cb = SPR(wm_Tweaker1662, b) & 0x3F, i;
    for (i = 0; i < 2; i++) {               /* X = 1 (Y), X = 0 (X) */
        u16 pa, pb;
        u8 wa, wb;
        if (!i) {
            pa = (u16)((SPR(wm_SpriteYLo, a) | SPR(wm_SpriteYHi, a) << 8) + (u16)(s16)(s8)tx_ClipDispY[ca]);
            pb = (u16)((SPR(wm_SpriteYLo, b) | SPR(wm_SpriteYHi, b) << 8) + (u16)(s16)(s8)tx_ClipDispY[cb]);
            wa = tx_ClipHeight[ca];
            wb = tx_ClipHeight[cb];
        } else {
            pa = (u16)((SPR(wm_SpriteXLo, a) | SPR(wm_SpriteXHi, a) << 8) + (u16)(s16)(s8)tx_ClipDispX[ca]);
            pb = (u16)((SPR(wm_SpriteXLo, b) | SPR(wm_SpriteXHi, b) << 8) + (u16)(s16)(s8)tx_ClipDispX[cb]);
            wa = tx_ClipWidth[ca];
            wb = tx_ClipWidth[cb];
        }
        if ((u16)(pb - pa + 0x80) >= 0x100)
            return 0;
        if ((u8)(wb + wa) < (u8)((u8)pa - (u8)pb + wa))
            return 0;
    }
    return 1;
}

/* _OffScrEraseSprite (banco 1): fuera; si tenia indice, se puede volver a
   cargar (el $1F, Lakitu, pide reaparecer: sin portar) */
static void off_scr_erase(u8 x)
{
    if (SPR(wm_SpriteNum, x) == 0x1F)
        spr_unsup();
    if (SPR(wm_SpriteStatus, x) >= 0x08 && SPR(wm_SprIndexInLvl, x) != 0xFF)
        W8(wm_SprLoadStatus + SPR(wm_SprIndexInLvl, x), 0);
    SETSPR(wm_SpriteStatus, x, 0);
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
const u8 *mcl_dy, *mcl_h, *cl_dx, *cl_dy, *cl_w, *cl_h, *rex_speed, *upd_grav, *upd_max;
u8 logic68k_zero;               /* siempre 0: con "tabla + 0 de la RAM" vbcc
                                   calcula la direccion con lea d16(a4); con
                                   "= tabla" emite move.l #etiqueta (absoluta) */
void logic68k_init(void)
{
    /* ya estan: un solo puntero dice si hay que (re)hacerlos (con un flag no
       alcanza: logicbench -DWORST restaura punteros de Musashi) */
    if (spr_clip_x == tx_SprObjClipX + logic68k_zero)
        return;
    spr_clip_x = tx_SprObjClipX + logic68k_zero;
    spr_clip_y = tx_SprObjClipY + logic68k_zero;
    gdi_ofs = tx_03B75C + logic68k_zero;
    gdi_bit = tx_03B75E + logic68k_zero;
    mcl_dy = tx_MarioClipDispY + logic68k_zero;
    mcl_h = tx_MarioClipH + logic68k_zero;
    cl_dx = tx_ClipDispX + logic68k_zero;
    cl_dy = tx_ClipDispY + logic68k_zero;
    cl_w = tx_ClipWidth + logic68k_zero;
    cl_h = tx_ClipHeight + logic68k_zero;
    rex_speed = tx_RexSpeed + logic68k_zero;
    upd_grav = tx_019030 + logic68k_zero;
    upd_max = tx_01902E + logic68k_zero;
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
        if (a == 0x04 || a == 0xFC) {       /* muy empinada: resbala */
            u16 v;
            u8 k;
            if (NEG((u8)(a ^ SPR(wm_SpriteSpeedX, x))) && SPR(wm_SpriteSpeedX, x))
                flip_sprite_dir(x);
            k = NEG(a) ? 1 : 0;             /* CODE_03C1CA: 2 px hacia abajo */
            v = (u16)((SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8)
                      + (u16)(tx_03C1C6[k] | tx_03C1C8[k] << 8));
            SETSPR(wm_SpriteXLo, x, (u8)v);
            SETSPR(wm_SpriteXHi, x, v >> 8);
            SETSPR(wm_SpriteSpeedY, x, 0x18);
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
MSS void spr_obj_interact(u8 x)
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
#ifdef LOGIC68K
void spr_update_pos_asm(u8 x);
#define spr_update_pos spr_update_pos_asm   /* player/logic68k.s */
#else
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
#endif

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

/* GetDrawInfoBnk1 (SubSprGfx2Entry1, SmushedGfxRt...): como get_draw_info
   (banco 3) con otros puntos verticales (DATA_01A361 = $10/$20, bits
   DATA_01A363 = 1/2) y otra condicion para el segundo (estado != 9 y
   Tweaker190F bit 5). Devuelve 0 si el sprite esta lejos.
   OJO: con un puntero u8 *p = &RX8(wm_SpriteXLo, x) y p[t - wm_SpriteXLo]
   vbcc -O=991 cargo en el puntero la base de OTRA tabla (XHi) y leyo mal
   todo (el PC, bien): se queda con SPR(). */
static int get_draw_info1(u8 x)
{
    u16 d;
    u8 v;
    d = (u16)((SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8) - R16(wm_Bg1HOfs));
    SETSPR(wm_OffscreenHorz, x, (d >> 8) ? 1 : 0);
    if ((u16)(d + 0x40) >= 0x180) {
        SETSPR(wm_OffscreenVert, x, 0);
        SETSPR(wm_SpriteOffTbl, x, 1);
        return 0;
    }
    SETSPR(wm_SpriteOffTbl, x, 0);
    d = (u16)((SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8) - R16(wm_Bg1VOfs));
    v = 0;
    if (SPR(wm_SpriteStatus, x) != 0x09 && (SPR(wm_Tweaker190F, x) & 0x20) && ((u16)(d + 0x20) >> 8))
        v = 2;
    if ((u16)(d + 0x10) >> 8)
        v |= 1;
    SETSPR(wm_OffscreenVert, x, v);
    return 1;
}

/* SubOffscreen0Bnk3 (nivel horizontal) */
MSS void sub_offscreen3(u8 x)
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
#ifdef LOGIC68K
int spr_mario_contact_asm(u8 x);
#define spr_mario_contact spr_mario_contact_asm     /* player/logic68k.s */
#else
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
#endif

/* BoostMarioSpeed: el rebote al pisar (mas alto con el boton apretado) */
static void boost_mario(void)
{
    if (!R8(wm_IsClimbing))
        W8(wm_MarioSpeedY, NEG(R8(wm_JoyPadA)) ? 0xA8 : 0xD0);
}

/* CODE_01AB46: puntos por pisoton en cadena (la puntuacion y su sprite,
   GivePoints, son de la etapa 10: MEV_SPRITE) */
static void chain_points(u8 x)
{
    u8 y = (u8)(R8(wm_SprChainStomped) + SPR(wm_SprChainKillTbl, x) + 1);
    W8(wm_SprChainStomped, R8(wm_SprChainStomped) + 1);
    if (y < 8)
        W8(wm_SoundCh1, tx_01A61E[y - 1]);   /* DATA_01A61E */
    mario_events |= MEV_SPRITE;
}

/* _01A8D8: rebote de Mario (DisplayContactGfx: la estrellita, grafico) */
static void stomp_bounce(void)
{
    W8(wm_SoundCh1, 0x02);
    boost_mario();
    mario_events |= MEV_SPRITE;
}

/* DefaultInteractR (sprite_1-main.s): el contacto de Mario con un sprite
   sin reaccion propia (Tweaker167A bit 7 = 0). Portado: el pisoton normal
   (rebote, puntos, aplastado / muerto / o solo rebote si es inmune), el
   salto con giro que lo deshace en humo y el dano a Mario (HurtMario:
   MEV_HURT, como el Rex). Sin portar: estrella, deslizandose, caparazones,
   sprites que al pisarlos se cambian por otro, aturdidos. */
static void default_interact(u8 x)
{
    u8 c;
    u16 sy;
    if (R8(wm_StarPowerTimer) && !(SPR(wm_Tweaker167A, x) & 0x02)) {
        spr_unsup();                        /* _01A847: lo mata la estrella */
        return;
    }
    W8(wm_StarKillPoints, 0);               /* CODE_01A87E */
    if (SPR(wm_SpriteDecTbl2, x))
        return;
    SETSPR(wm_SpriteDecTbl2, x, 0x08);
    if (SPR(wm_SpriteStatus, x) == 0x09) {
        spr_unsup();                        /* CODE_01AA42: patear o agarrar */
        return;
    }
    /* CODE_01A897: m5/m11 = Y de la caja del sprite (GetSpriteClippingA) */
    c = SPR(wm_Tweaker1662, x) & 0x3F;
    sy = (u16)((SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8) + (u16)(s16)(s8)tx_ClipDispY[c]);
    if (!((u16)((u16)(sy - 0x14) - R16(wm_PlayerYPosLv)) & 0x8000)
        && (!NEG(R8(wm_MarioSpeedY)) || (SPR(wm_Tweaker190F, x) & 0x10) || R8(wm_SprChainStomped))
        && (!(SPR(wm_SprObjStatus, x) & 0x04) || R8(wm_IsFlying))) {
        /* Mario por encima y bajando (o en cadena) */
        if (SPR(wm_Tweaker1656, x) & 0x10) {    /* CODE_01A91C: se puede pisar */
            if (R8(wm_IsSpinJump) | R8(wm_OnYoshi)) {   /* _01A924: se deshace en humo */
                mario_events |= MEV_SPRITE; /* DisplayContactGfx, CODE_07FC3B */
                W8(wm_MarioSpeedY, 0xF8);
                if (R8(wm_OnYoshi))
                    boost_mario();
                SETSPR(wm_SpriteStatus, x, 0x04);   /* _019ACB */
                SETSPR(wm_SpriteDecTbl1, x, 0x1F);
                chain_points(x);
                W8(wm_SoundCh1, 0x08);
                if (SPR(wm_SpriteNum, x) == 0x1E)
                    spr_unsup();            /* _01A9F2: Lakitu */
                return;
            }
            stomp_bounce();                 /* CODE_01A947 */
            if (SPR(wm_SprStompImmuneTbl, x)) {
                W8(wm_MarioSpeedX, sub_horiz_pos(x) ? 0xE8 : 0x18);
                return;
            }
            chain_points(x);                /* CODE_01A95D */
            if (SPR(wm_Tweaker1686, x) & 0x40) {
                spr_unsup();                /* se cambia por otro sprite (Koopa -> caparazon...) */
                return;
            }
            if (((u8)(SPR(wm_SpriteNum, x) - 4) < 0x0D && R8(wm_CapeGlidePhase))
                || (SPR(wm_Tweaker1656, x) & 0x20)) {       /* CODE_01A9BE: aplastado */
                SETSPR(wm_SpriteStatus, x, 0x03);
                SETSPR(wm_SpriteDecTbl1, x, 0x20);
                SETSPR(wm_SpriteSpeedX, x, 0);
                SETSPR(wm_SpriteSpeedY, x, 0);
                return;
            }
            if (SPR(wm_Tweaker1662, x) & 0x80) {        /* CODE_01A9E2: cae muerto */
                SETSPR(wm_SpriteStatus, x, 0x02);
                SETSPR(wm_SpriteSpeedX, x, 0);
                SETSPR(wm_SpriteSpeedY, x, 0);
                if (SPR(wm_SpriteNum, x) == 0x1E)
                    spr_unsup();            /* _01A9F2: Lakitu */
                return;
            }
            spr_unsup();                    /* CODE_01AA01: aturdido */
            return;
        }
        if (R8(wm_IsSpinJump) | R8(wm_OnYoshi)) {
            stomp_bounce();                 /* _01A8D8: rebota sin hacerle nada */
            return;
        }
    }
    /* CODE_01A8E6: Mario de costado o de abajo */
    if (R8(wm_PlayerSlopePose) && !(SPR(wm_Tweaker190F, x) & 0x04)) {
        spr_unsup();                        /* deslizandose: lo mata (_01A847) */
        return;
    }
    if (R8(wm_PlayerHurtTimer) | R8(wm_OnYoshi))
        return;
    if (!(SPR(wm_Tweaker1686, x) & 0x10))
        SETSPR(wm_SpriteDir, x, sub_horiz_pos(x));
    if (SPR(wm_SpriteNum, x) != 0x53) {
        mario_events |= MEV_HURT;
        spr_unsup();                        /* HurtMario */
    }
}

/* MarioSprInteractRt, hasta el contacto. 1 si hay contacto y la reaccion
   la hace el propio sprite (Tweaker167A bit 7, el Rex); si no, la hace
   DefaultInteractR y devuelve 0. */
static int process_interact(u8 x);
MSS int mario_spr_interact(u8 x)
{
    if (!(SPR(wm_Tweaker167A, x) & 0x20)
        && (((x ^ R8(wm_FrameA)) & 1) | SPR(wm_OffscreenHorz, x)))
        return 0;
    if (!process_interact(x))
        return 0;
    if (!NEG(SPR(wm_Tweaker167A, x))) {
        default_interact(x);
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
MSS void spr_spr_interact(u8 y);

static void flying_block(u8 x)
{
    get_draw_info1(x);                      /* SubSprGfx2Entry1: flags */
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
        W8(wm_SoundCh3, 0x22);
        SETSPR(wm_SpriteDecTbl3, x, 0);
        SETSPR(wm_SpriteState, x, 0);
        W8(wm_MsgBoxTrig, (u8)(((SPR(wm_SpriteXLo, x) >> 4) & 1) + 1));
        mario_events |= MEV_SPRITE;
    }
    {   /* GenericSprGfxRt2 (flags para el frame siguiente) con la camara
           movida lo que rebota la caja (DATA_038D66) */
        u16 v = R16(wm_Bg1VOfs);
        W16(wm_Bg1VOfs, v + tx_038D66[SPR(wm_SpriteDecTbl3, x) >> 1]);
        get_draw_info1(x);
        W16(wm_Bg1VOfs, v);
    }
}

/* SubSprSprInteract: la ranura y (la que corre) contra las de abajo.
   Portado el caso estado 8 contra estado 8 (CODE_01A56D: se dan vuelta);
   el resto marca mario_unsupported. */
MSS void spr_spr_interact(u8 y)
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
/* el Rex toco a Mario (mario_spr_interact): pisoton, giro o golpe */
MSS void rex_contact(u8 x);

#ifdef LOGIC68K
void rex_main_asm(u8 x);
#define rex_main rex_main_asm               /* player/logic68k.s */
#else
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
    rex_contact(x);
}
#endif

MSS void rex_contact(u8 x)
{
    if (R8(wm_StarPowerTimer)) { spr_unsup(); return; }     /* RexStarKill */
    if (SPR(wm_SpriteDecTbl2, x))
        return;
    SETSPR(wm_SpriteDecTbl2, x, 0x08);
    if (NEG((u8)(R8(wm_MarioSpeedY) - 0x10))) {             /* RexWins */
        u16 d;
        if (R8(wm_PlayerHurtTimer) | R8(wm_OnYoshi))
            return;
        d = (u16)(R16(wm_MarioXPos) - (SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8));
        W8(m15, (u8)d);                     /* SubHorzPosBnk3: mira a Mario */
        SETSPR(wm_SpriteDir, x, (d & 0x8000) ? 1 : 0);
        mario_events |= MEV_HURT;
        spr_unsup();                        /* HurtMario */
        return;
    }
    chain_points(x);                       /* RexPoints (DATA_038000 = DATA_01A61E) */
    boost_mario();                          /* BoostMarioSpeed, DisplayContactGfx */
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

/* SubOffscreen0Bnk1 = SubOffscreen0Bnk3 con m3 = 0 (mismas tablas en las
   entradas 0 y 1); solo cambia el $1F (Lakitu), que no esta en el nivel */
#define sub_offscreen1 sub_offscreen3

/* SlidingKoopa (sprite_3-1.s), el $BD: baja las pendientes deslizandose,
   frena en el llano y, parado $20 frames, sale el Koopa sin caparazon
   ($02, InitSpriteTables: mismas X/Y y direccion). El humo al deslizarse
   (CODE_0389FF) es solo grafico: no se porta. */
static void sliding_koopa(u8 x)
{
    u8 v = SPR(wm_SpriteSpeedX, x), y, s;
    if (v)
        SETSPR(wm_SpriteDir, x, NEG(v) ? 1 : 0);
    get_draw_info1(x);                      /* GenericSprGfxRt2 */
    if (SPR(wm_SpriteDecTbl3, x) == 1) {    /* sale el Koopa */
        y = SPR(wm_SpriteDir, x);
        SETSPR(wm_SpriteNum, x, 0x02);
        init_sprite_tables(x);
        SETSPR(wm_SpriteDir, x, y);
    }
    if (SPR(wm_SpriteStatus, x) != 0x08)
        return;
    sub_offscreen3(x);
    spr_spr_interact(x);                    /* SprSprMarioSprRts */
    mario_spr_interact(x);
    if (R8(wm_SpritesLocked) | SPR(wm_SpriteDecTbl1, x) | SPR(wm_SpriteDecTbl3, x))
        return;
    spr_update_pos(x);
    if (!(SPR(wm_SprObjStatus, x) & 0x04))
        return;
    v = SPR(wm_SpriteSpeedX, x);
    s = SPR(wm_SpriteSlopeTbl, x);
    y = 0;                                  /* pegado a la pendiente al bajar, */
    if (v && s)                             /* despedido hacia arriba al subir */
        y = NEG((u8)(s ^ v)) ? 0xD0 : (NEG(v) ? (u8)-v : v);
    SETSPR(wm_SpriteSpeedY, x, y);
    if (R8(wm_FrameA) & 0x01)
        return;
    if (!s) {                               /* llano: frena; parado, sale el Koopa */
        if (!v)
            SETSPR(wm_SpriteDecTbl3, x, 0x20);
        else
            SETSPR(wm_SpriteSpeedX, x, NEG(v) ? v + 1 : v - 1);
        return;
    }
    y = NEG(s) ? 1 : 0;                     /* CODE_0389EC: acelera cuesta abajo */
    if (v != tx_038954[y])
        SETSPR(wm_SpriteSpeedX, x, v + tx_038956[y]);
}

/* ShellessKoopas (sprite_1-main.s), el $02 (azul, sin caparazon): camina
   ($0C), da la vuelta en los bordes y contra las paredes. Sin portar: lo
   que hace con los caparazones (patearlos, meterse, saltarlos) y el
   deslizamiento de cuando lo sacan de uno (MiscTbl4). */
static const u8 spr013_speed[4] = { 8, 0xF8, 12, 0xF4 };   /* Spr0to13SpeedX */
#define KOOPA02_PROP 0x03                   /* Spr0to13Prop[$02] */
static void shellless_koopa(u8 x)
{
    u8 a, y;
    if (!R8(wm_SpritesLocked)) {            /* CODE_018952 */
        a = SPR(wm_SpriteDecTbl6, x);
        if (a == 0x80) {
            SETSPR(wm_SpriteDir, x, sub_horiz_pos(x));      /* _FaceMario */
            SETSPR(wm_SpriteDecTbl6, x, 0);
        } else if (a == 0x01) {
            y = SPR(wm_SpriteMiscTbl8, x);
            if (SPR(wm_SpriteStatus, y) == 0x09
                && (u8)(SPR(wm_SpriteXLo, x) - SPR(wm_SpriteXLo, y) + 0x12) < 0x24) {
                spr_unsup();                /* patea el caparazon */
                return;
            }
        }
        if (!a)
            goto run;
    }
    /* _018908: bloqueado (o recien sacado del caparazon) */
    if (SPR(wm_SpriteDecTbl6, x) >= 0x80 && !R8(wm_SpritesLocked)) {
        set_anim_frame(x);
        SETSPR(wm_SpriteGfxTbl, x, SPR(wm_SpriteGfxTbl, x) + 5);
    }
    mario_spr_interact(x);                  /* CODE_018931 ($02) */
    spr_update_pos(x);
    SETSPR(wm_SpriteSpeedX, x, 0);
    if (SPR(wm_SprObjStatus, x) & 0x04)
        SETSPR(wm_SpriteSpeedY, x, 0);
    goto tail;
run:
    if (SPR(wm_SpriteMiscTbl4, x) | SPR(wm_SpriteMiscTbl5, x)) {
        spr_unsup();                        /* deslizandose / con un caparazon */
        return;
    }
    a = SPR(wm_SpriteState, x);             /* _018A88 */
    if (a) {
        SETSPR(wm_SpriteState, x, a - 1);
        SETSPR(wm_SpriteGfxTbl, x, a >= 0x08 ? 4 : 0);
        mario_spr_interact(x);              /* _018B00 */
        goto tail;
    }
    if (SPR(wm_SpriteDecTbl3, x) == 1) {    /* CODE_018A9B: meterse en un caparazon */
        y = SPR(wm_SpriteMiscTbl7, x);
        if (SPR(wm_SpriteStatus, y) >= 0x08 && !NEG(SPR(wm_SpriteSpeedY, y))
            && SPR(wm_SpriteNum, y) != 0x21 && spr_spr_contact(x, y))
            spr_unsup();
        return;
    }
    /* Spr0to13Main */
    if (SPR(wm_SprObjStatus, x) & 0x04) {
        u8 v;
        y = SPR(wm_SpriteDir, x);
        if (KOOPA02_PROP & 0x01)
            y += 2;
        v = spr013_speed[y];
        if (NEG((u8)(v ^ SPR(wm_SpriteSlopeTbl, x))))
            v = (u8)(v + SPR(wm_SpriteSlopeTbl, x));
        SETSPR(wm_SpriteSpeedX, x, v);
    }
    if ((u8)(SPR(wm_SpriteDir, x) + 1) & SPR(wm_SprObjStatus, x) & 0x03)
        SETSPR(wm_SpriteSpeedX, x, 0);
    if (SPR(wm_SprObjStatus, x) & 0x08)
        SETSPR(wm_SpriteSpeedY, x, 0);
    sub_offscreen1(x);                      /* _018B43 */
    spr_update_pos(x);
    set_anim_frame(x);
    if (SPR(wm_SprObjStatus, x) & 0x04) {
        set_some_yspeed(x);
        SETSPR(wm_SpriteMiscTbl3, x, 0);    /* (Prop bits 2-3: los otros colores) */
    } else {                                /* SpriteInAir (Prop bit 7 = 0) */
        SETSPR(wm_SpriteMiscTbl6, x, 0);
        if ((KOOPA02_PROP & 0x02) && !(SPR(wm_SpriteMiscTbl3, x) | SPR(wm_SpriteDecTbl3, x)
                                       | SPR(wm_SpriteMiscTbl4, x) | SPR(wm_SpriteMiscTbl5, x))) {
            flip_sprite_dir(x);             /* no se cae de los bordes */
            SETSPR(wm_SpriteMiscTbl3, x, 1);
        }
    }
    mario_spr_interact(x);                  /* _018BB0 (MiscTbl4 = 0) */
    spr_spr_interact(x);
    flip_if_touching_obj(x);
    goto gfx;
tail:                                       /* _018B03 */
    spr_spr_interact(x);
gfx:                                        /* _Spr0to13Gfx */
    if (SPR(wm_SpriteDecTbl5, x))
        SETSPR(wm_SpriteGfxTbl, x, 2);      /* (girando: la direccion solo para el dibujo) */
    get_draw_info1(x);                      /* SubSprGfx2Entry1 */
}

/* BanzaiRotating -> CODE_02D587 (sprite_2-2.s), el $9F: vuela recto a la
   izquierda ($E8). GetDrawInfo2 y SubOffscreen0Bnk2 son los del banco 3
   (mismas tablas); si GetDrawInfo2 lo ve lejos solo se salta el dibujo.
   Aunque SubOffscreen lo borre, el resto del frame sigue (como el ROM). */
static void banzai_bill(u8 x)
{
    get_draw_info(x);                       /* CODE_02D5E4 */
    if (SPR(wm_SpriteStatus, x) == 0x02 || R8(wm_SpritesLocked))
        return;
    sub_offscreen3(x);
    SETSPR(wm_SpriteSpeedX, x, 0xE8);
    spr_pos_axis(x, 0x0C);                  /* UpdateXPosNoGrvty2 */
    mario_spr_interact(x);                  /* DefaultInteractR: pisarlo lo tira (estado 2) */
}

/* JumpingPiranhaMain -> CODE_02E0CD (sprite_2-2.s), el $4F: salta de la
   tuberia (sube a $C0 y frena), baja flotando hasta posarse y espera $40
   frames; no salta con Mario a menos de ~$1B px. Las bolas de fuego del $50
   no estan (no hay en el nivel). */
static void jumping_piranha(u8 x)
{
    u8 v;
    u16 y;
    SETSPR(wm_SpritePal, x, tx_166E[SPR(wm_SpriteNum, x)] & 0x0F);     /* LoadSpriteTables */
    sprite_tweakers(x);
    /* dibujo: la cabeza (GenericSprGfxRt2) y el tallo 8 px mas abajo
       (GenericSprGfxRt0); los flags de pantalla quedan los del tallo */
    y = (u16)(SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8);
    SETSPR(wm_SpriteYLo, x, (u8)(y + 8));
    SETSPR(wm_SpriteYHi, x, (u16)(y + 8) >> 8);
    get_draw_info1(x);
    SETSPR(wm_SpriteYLo, x, (u8)y);
    SETSPR(wm_SpriteYHi, x, y >> 8);
    SETSPR(wm_SpriteGfxTbl, x, ((SPR(wm_SpriteMiscTbl3, x) & 0x04) >> 2) + 1);
    SETSPR(wm_SpritePal, x, 0x0A);
    if (R8(wm_SpritesLocked))
        return;
    sub_offscreen3(x);                      /* SubOffscreen0Bnk2 */
    spr_spr_interact(x);                    /* SprSprMarioSprRts */
    mario_spr_interact(x);
    spr_pos_axis(x, 0);                     /* UpdateYPosNoGrvty2 */
    switch (SPR(wm_SpriteState, x)) {
    case 0:                                 /* CODE_02E13C: en la tuberia */
        SETSPR(wm_SpriteSpeedY, x, 0);
        if (SPR(wm_SpriteDecTbl1, x))
            return;
        v = (u8)(R8(wm_MarioXPos) - SPR(wm_SpriteXLo, x));    /* CODE_02D4FA */
        W8(m15, v);
        if ((u8)(v + 0x1B) < 0x37)
            return;                         /* Mario cerca: no sale */
        SETSPR(wm_SpriteSpeedY, x, 0xC0);
        SETSPR(wm_SpriteState, x, 1);
        SETSPR(wm_SpriteGfxTbl, x, 0);
        return;
    case 1:                                 /* CODE_02E159: sube frenando */
        v = SPR(wm_SpriteSpeedY, x);
        if (NEG(v) || v < 0x40)
            SETSPR(wm_SpriteSpeedY, x, v + 2);
        SETSPR(wm_SpriteMiscTbl6, x, SPR(wm_SpriteMiscTbl6, x) + 1);
        if (!NEG((u8)(SPR(wm_SpriteSpeedY, x) - 0xF0))) {
            SETSPR(wm_SpriteDecTbl1, x, 0x50);
            SETSPR(wm_SpriteState, x, 2);
        }
        return;
    case 2:                                 /* CODE_02E177: baja flotando */
        SETSPR(wm_SpriteMiscTbl3, x, SPR(wm_SpriteMiscTbl3, x) + 1);
        SETSPR(wm_SpriteMiscTbl6, x, SPR(wm_SpriteMiscTbl6, x) + 1);   /* _02E17F */
        if (!(R8(wm_FrameB) & 0x03) && NEG((u8)(SPR(wm_SpriteSpeedY, x) - 0x08)))
            SETSPR(wm_SpriteSpeedY, x, SPR(wm_SpriteSpeedY, x) + 1);
        spr_obj_interact(x);                /* CODE_019138 */
        if (SPR(wm_SprObjStatus, x) & 0x04) {
            SETSPR(wm_SpriteState, x, 0);
            SETSPR(wm_SpriteDecTbl1, x, 0x40);
        }
        return;
    }
    spr_unsup();                            /* (ExecutePtr fuera de la tabla) */
}

/* WarpBlocksMain -> CODE_02EADA (sprite_2-2.s), el $8E (bloques "warp
   hole" invisibles): si Mario lo toca, lo deja quieto en su X + $0A. No
   desaparece fuera de pantalla. */
static void warp_blocks(u8 x)
{
    if (!mario_spr_interact(x))             /* Tweaker167A bit 7: el contacto es suyo */
        return;
    W8(wm_MarioSpeedX, 0);
    W16(wm_MarioXPos, (u16)((SPR(wm_SpriteXLo, x) | SPR(wm_SpriteXHi, x) << 8) + 0x0A));
}

/* InvisMushroom (sprite_3-2.s), el $C7: invisible; si Mario lo toca, sale
   una seta ($74, sin portar: D12) hacia donde no va Mario */
static void invis_mushroom(u8 x)
{
    u16 y;
    if (!get_draw_info(x))                  /* GetDrawInfoBnk3: lejos, nada */
        return;
    if (!mario_spr_interact(x))
        return;
    SETSPR(wm_SpriteNum, x, 0x74);
    init_sprite_tables(x);
    SETSPR(wm_SpriteDecTbl2, x, 0x20);
    y = (u16)((SPR(wm_SpriteYLo, x) | SPR(wm_SpriteYHi, x) << 8) - 0x0F);
    SETSPR(wm_SpriteYLo, x, (u8)y);
    SETSPR(wm_SpriteYHi, x, y >> 8);
    SETSPR(wm_SpriteDir, x, NEG(R8(wm_MarioSpeedX)) ? 1 : 0);  /* _PopupMushroom */
    SETSPR(wm_SpriteSpeedY, x, 0xC0);
    W8(wm_SoundCh3, 0x02);
    mario_events |= MEV_SPRITE;
}

static void sprite_main(u8 x, u8 n);

/* _HandleSprKilled (estado 2): cae muerto, fuera de pantalla desaparece.
   Con Tweaker167A bit 0 (Rex, Banzai) su propia rutina lo dibuja; si no,
   el dibujo generico (solo los flags de GetDrawInfoBnk1). */
static void handle_killed(u8 x)
{
    u8 n = SPR(wm_SpriteNum, x);
    if (n == 0x86 || n == 0x1E || n == 0x53 || n == 0x4C) {
        spr_unsup();                        /* Wiggler, Lakitu, bloque, bloque que explota */
        return;
    }
    if (SPR(wm_Tweaker1656, x) & 0x80) {    /* _019ACB: nube */
        SETSPR(wm_SpriteStatus, x, 0x04);
        SETSPR(wm_SpriteDecTbl1, x, 0x1F);
        return;
    }
    if (!R8(wm_SpritesLocked))              /* CODE_019AD6 */
        spr_update_pos(x);
    sub_offscreen1(x);
    if (SPR(wm_Tweaker167A, x) & 0x01) {    /* HandleSpriteDeath */
        sprite_main(x, n);
        return;
    }
    SETSPR(wm_SpriteGfxTbl, x, 0);          /* CODE_019B1D (dibujo) */
    get_draw_info1(x);
}

/* HandleSprSmushed (estado 3): aplastado $20 frames; despues, fuera (sin
   liberar su indice: no vuelve a salir) */
static void handle_smushed(u8 x)
{
    if (!R8(wm_SpritesLocked)) {
        if (!SPR(wm_SpriteDecTbl1, x)) {
            SETSPR(wm_SpriteStatus, x, 0);
            return;
        }
        spr_update_pos(x);                  /* ShowSmushedGfx */
        if (SPR(wm_SprObjStatus, x) & 0x04) {
            set_some_yspeed(x);
            SETSPR(wm_SpriteSpeedX, x, 0);
        }
    }
    get_draw_info1(x);                      /* SmushedGfxRt (el $6F: SubSprGfx2Entry1) */
}

/* HandleSprSpinJump (estado 4): la nube del salto con giro; al terminar, fuera */
static void handle_spin_jump(u8 x)
{
    if (!SPR(wm_SpriteDecTbl1, x)) {
        off_scr_erase(x);
        return;
    }
    get_draw_info1(x);                      /* SubSprGfx2Entry1 */
}

/* CallSpriteMain: la rutina de cada sprite portado */
static void sprite_main(u8 x, u8 n)
{
    W8(wm_SprPixelMove, 0);
    if (n == 0xAB) { rex_main(x); return; }
    if (n == 0x83) { flying_block(x); return; }
    if (n == 0xB9) { info_box(x); return; }
    if (n == 0xBD) { sliding_koopa(x); return; }
    if (n == 0x02) { shellless_koopa(x); return; }
    if (n == 0x9F) { banzai_bill(x); return; }
    if (n == 0x4F) { jumping_piranha(x); return; }
    if (n == 0x8E) { warp_blocks(x); return; }
    if (n == 0xC7) { invis_mushroom(x); return; }
    spr_unsup();
}

/* CODE_0180D2 (los temporizadores) + HandleSprite, para una ranura */
void sprite_run(u8 x)
{
    u8 st = SPR(wm_SpriteStatus, x), n;
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
    n = SPR(wm_SpriteNum, x);
    if (st == 0x08) {
        sprite_main(x, n);
        return;
    }
    if (st == 0x01) {                       /* CallSpriteInit */
        if (n == 0xAB) {                    /* Rex: _FaceMario */
            SETSPR(wm_SpriteStatus, x, 0x08);
            SETSPR(wm_SpriteDir, x, sub_horiz_pos(x));
            return;
        }
        if (n == 0x83) {                    /* InitFlyingBlock */
            SETSPR(wm_SpriteStatus, x, 0x08);
            SETSPR(wm_SpriteMiscTbl3, x, (SPR(wm_SpriteXLo, x) >> 4) & 0x03);
            SETSPR(wm_SpriteDir, x, SPR(wm_SpriteDir, x) + 1);
            return;
        }
        if (n == 0xB9 || n == 0x8E || n == 0xC7) {  /* sin init propio (_Return0185C2) */
            SETSPR(wm_SpriteStatus, x, 0x08);
            return;
        }
        if (n == 0xBD) {                    /* InitSlidingKoopa */
            SETSPR(wm_SpriteStatus, x, 0x08);
            SETSPR(wm_SpriteDecTbl1, x, 0x04);
            return;
        }
        if (n == 0x4F) {                    /* _InitPiranha: al centro de la tuberia */
            SETSPR(wm_SpriteStatus, x, 0x08);
            SETSPR(wm_SpriteXLo, x, SPR(wm_SpriteXLo, x) + 8);     /* (sin acarreo) */
            SETSPR(wm_SpriteYLo, x, SPR(wm_SpriteYLo, x) - 1);
            if (SPR(wm_SpriteYLo, x) == 0xFF)
                SETSPR(wm_SpriteYHi, x, SPR(wm_SpriteYHi, x) - 1);
            return;
        }
        if (n == 0x9F) {                    /* InitBanzai: solo si Mario esta a la izquierda */
            SETSPR(wm_SpriteStatus, x, 0x08);
            if (!sub_horiz_pos(x))
                off_scr_erase(x);
            else
                W8(wm_SoundCh3, 0x09);
            return;
        }
        spr_unsup();
        return;
    }
    if (st == 0x02) { handle_killed(x); return; }
    if (st == 0x03) { handle_smushed(x); return; }
    if (st == 0x04) { handle_spin_jump(x); return; }
    spr_unsup();                            /* muerto cayendo, aturdido... */
}
