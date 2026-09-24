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
#include "gen/smwtabx.h"
#include "smwmac.h"

const u8 *spr_level;        /* spr.lv del nivel (cabecera incluida) */

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
    /* InitSpriteTables (ZeroSpriteTables + LoadSpriteTables): pendiente */
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
