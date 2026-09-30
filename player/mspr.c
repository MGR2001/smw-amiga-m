/*
 * mspr.c - Etapa 6b.4: Mario en sprites de hardware de la Amiga.
 *
 * La SNES dibuja a Mario con las 4 entradas de OAM de CODE_00E45D (mgfx.c
 * las deja en mario_oam / mario_osz en el build NOOAM) y con los tiles que
 * el NMI copia por DMA de GFX32 ($7E:2000) a la VRAM de sprites, segun los
 * punteros de CODE_00F636 (wm_0D85, wm_Tile7FPtr). Aca se hace lo mismo
 * sobre un lienzo de 32 px de ancho (2 columnas de 16) y 4 planos, y se
 * escribe como dos parejas de sprites adosados (16 colores: COLOR16-31 =
 * la paleta 0 de sprites de la SNES, con la de Mario en 135..).
 *
 *   VRAM de sprites (pagina 0): el tile t (0..$1F) esta en la fila t >> 4
 *   (0: punteros wm_0D85 + 0, 2, 4...; 1: wm_0D85 + 10, 12...), en el
 *   puntero (t & 15) >> 1, mitad t & 1 (cada puntero trae 64 bytes = 2
 *   tiles de 8x8). El tile $7F viene de wm_Tile7FPtr (32 bytes). Los demas
 *   son de los sprites del nivel: aca no se dibujan (Mario no los usa).
 *
 * Prioridad como la SNES: la entrada anterior tapa a la siguiente.
 */
#include "mario.h"
#include "gen/smwram.h"
#include "smwmac.h"

#define GFX32_BASE  0x2000      /* GFX32 empieza en $7E:2000 */
#define GFX32_SIZE  0x5D00
#define MSPR_H      MSPR_LINES  /* alto maximo del lienzo (mario.h) */

const u8 *gfx32;                /* GFX32 descomprimido (lo pone el arranque) */
u8 mspr_rev[256];               /* bits al reves (volteo horizontal) */

static u8 cv[MSPR_H][2][4][2];  /* [linea][columna][plano][byte]: 32 px */

/* los 32 bytes de un tile de 8x8 de la VRAM de sprites, o 0 */
static const u8 *vram_tile(u8 t)
{
    u16 p;
    if (t == 0x7F)
        p = R16(wm_Tile7FPtr);
    else if (t < 0x20 && (t & 15) < 10)
        p = R16(wm_0D85 + ((t >> 4) ? 10 : 0) + ((t & 15) >> 1) * 2) + (t & 1) * 32;
    else
        return 0;
    if (p < GFX32_BASE || p > GFX32_BASE + GFX32_SIZE - 32)
        return 0;
    return gfx32 + (p - GFX32_BASE);
}

/* una fila de un tile de 8x8 en (x, y) del lienzo (x en 0..24), sin tapar
   lo que ya hay */
static void put8(const u8 *tile, u8 row, u8 x, u8 y, u8 hflip)
{
    u8 b[4], m, k, sh, c;
    u16 w;
    b[0] = tile[2 * row];
    b[1] = tile[2 * row + 1];
    b[2] = tile[16 + 2 * row];
    b[3] = tile[16 + 2 * row + 1];
    if (hflip)
        for (k = 0; k < 4; k++)
            b[k] = mspr_rev[b[k]];
    c = x >> 3;                             /* byte del lienzo (0..3) */
    sh = x & 7;
    for (k = 0; k < 2; k++) {               /* hasta 2 bytes del lienzo */
        u8 byte = (u8)(c + k), col = byte >> 1, half = byte & 1;
        if (byte > 3)
            break;
        m = (u8)(cv[y][col][0][half] | cv[y][col][1][half] | cv[y][col][2][half]
                 | cv[y][col][3][half]);
        for (w = 0; w < 4; w++) {
            u8 v = k ? (u8)(b[w] << (8 - sh)) : (u8)(b[w] >> sh);
            if (k && !sh)
                v = 0;
            cv[y][col][w][half] |= (u8)(v & ~m);
        }
    }
}

/* Escribe las dos parejas en spr (4 sprites seguidos de MSPR_WORDS palabras
   cada uno: SPRxPOS, SPRxCTL, MSPR_H x (DATA, DATB), 0, 0). Devuelve el
   numero de columnas usadas (0: Mario no se ve). vy0 = linea del display
   de la linea 0 de la pantalla, hx0 = HSTART de la x = 0. */
int mario_sprite(u16 *spr, u16 vy0, u16 hx0)
{
    int e, bx = 1000, by = 1000, ex, ey, x1 = -1000, y1 = -1000, n, i, j, cols;
    u16 *s;

    if (!mspr_rev[1]) {                     /* la tabla, la primera vez */
        for (i = 0; i < 256; i++) {
            u8 r = 0;
            for (j = 0; j < 8; j++)
                if (i & (1 << j))
                    r |= (u8)(0x80 >> j);
            mspr_rev[i] = r;
        }
    }
    /* caja de las entradas que se ven */
    for (e = 0; e < 4; e++) {
        u8 *o = mario_oam + 4 * e;
        int sz = (mario_osz[e] & 2) ? 16 : 8;
        if (o[1] == 0xF0)
            continue;
        ex = o[0] | ((mario_osz[e] & 1) << 8);
        if (ex >= 256)
            ex -= 512;
        ey = o[1] >= 0xF0 ? o[1] - 256 : o[1];
        if (ex < bx) bx = ex;
        if (ey < by) by = ey;
        if (ex + sz > x1) x1 = ex + sz;
        if (ey + sz > y1) y1 = ey + sz;
    }
    s = spr;
    if (bx == 1000 || x1 - bx > 32 || y1 - by > MSPR_H) {
        for (i = 0; i < 4; i++, s += MSPR_WORDS)
            s[0] = s[1] = 0;                /* sin sprite */
        return 0;
    }
    for (i = 0; i < MSPR_H; i++)
        for (j = 0; j < 16; j++)
            ((u8 *)cv[i])[j] = 0;
    /* las entradas, de la de mas prioridad a la de menos */
    for (e = 0; e < 4; e++) {
        /* los 4 bytes de la entrada a variables: con `u8 *o` y `prop = o[3]`
           el vbcc de cloud dejaba o + 3 en el registro y leia o[0..2] desde
           ahi (x = prop, y = el tile...): escribia fuera de cv (P38) */
        u8 o0 = mario_oam[4 * e], o1 = mario_oam[4 * e + 1];
        u8 o2 = mario_oam[4 * e + 2], prop = mario_oam[4 * e + 3];
        u8 hf = (prop >> 6) & 1, vf = (prop >> 7) & 1;
        int big = mario_osz[e] & 2, nt = big ? 2 : 1, tx, ty, r;
        if (o1 == 0xF0)
            continue;
        ex = o0 | ((mario_osz[e] & 1) << 8);
        if (ex >= 256)
            ex -= 512;
        ey = o1 >= 0xF0 ? o1 - 256 : o1;
        for (ty = 0; ty < nt; ty++)
            for (tx = 0; tx < nt; tx++) {
                /* el tile de la VRAM que va en (tx, ty) de la entrada */
                const u8 *t = vram_tile((u8)(o2 + (hf ? nt - 1 - tx : tx)
                                             + 16 * (vf ? nt - 1 - ty : ty)));
                if (!t)
                    continue;
                for (r = 0; r < 8; r++)
                    put8(t, (u8)(vf ? 7 - r : r), (u8)(ex - bx + 8 * tx),
                         (u8)(ey - by + 8 * ty + r), hf);
            }
    }
    /* las dos parejas: 0/1 = columna 0 (planos 0-1 / 2-3), 2/3 = columna 1 */
    cols = x1 - bx > 16 ? 2 : 1;
    n = y1 - by;
    for (i = 0; i < 4; i++, s += MSPR_WORDS) {
        int col = i >> 1, pl = (i & 1) * 2;
        u16 vs = (u16)(vy0 + by + 1), ve = (u16)(vs + n);   /* +1: la SNES */
        u16 hs = (u16)(hx0 + bx + 16 * col);
        u16 *d = s + 2;
        if (col >= cols) {
            s[0] = s[1] = 0;
            continue;
        }
        s[0] = (u16)(((vs & 0xFF) << 8) | ((hs >> 1) & 0xFF));
        s[1] = (u16)(((ve & 0xFF) << 8) | ((i & 1) << 7) | (((vs >> 8) & 1) << 2)
                     | (((ve >> 8) & 1) << 1) | (hs & 1));
        for (j = 0; j < n; j++) {
            *d++ = (u16)((cv[j][col][pl][0] << 8) | cv[j][col][pl][1]);
            *d++ = (u16)((cv[j][col][pl + 1][0] << 8) | cv[j][col][pl + 1][1]);
        }
        *d++ = 0;
        *d = 0;
    }
    return cols;
}
