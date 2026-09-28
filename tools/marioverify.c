/*
 * marioverify.c - verifica la etapa 8a del port (player/mario.c) contra el
 * oraculo grabado en smwrecomp (work/oracle_yi1.bin, tools/oracle2bin.py).
 *
 * Frame "hibrido": para cada par de frames seguidos N, N+1 de Yoshi's
 * Island 1:
 *   - ram = estado del oraculo en N ($0000-$00FF, $13C0-$14FF);
 *   - joypad ($15-$18) y contador de frames ($13-$14) de N+1;
 *   - resultados de la colision de N+1 (etapa 8b, todavia sin portar):
 *     bloqueos $77, pendiente $13E1/$13EE, suelo $13EF, sprite solido
 *     $1471, posicion; en el aire $72 = 0 si en N+1 esta en el suelo;
 *   - se corren D5F2, D062 y D7E4 y se comparan los campos que escriben
 *     con N+1.
 * Los frames donde aterriza, choca un techo o pisa un enemigo fallan por
 * construccion hasta la 8b; se cuentan aparte (columna "suelo/aire").
 *
 *   gcc -O2 -Iplayer -o work/marioverify tools/marioverify.c player/mario.c player/mcoll.c player/manim.c player/mgfx.c player/mcam.c player/msprite.c player/gen/smwrom00.c
 *   work/marioverify work/oracle_yi1.bin
 *   work/marioverify work/oracle_yi1.bin full [work/yi1_map16.bin [CAMPO]]   (8b)
 *   work/marioverify work/oracle_yi1.bin fulldump FRAME salida.bin   (estado para logicbench)
 *   work/marioverify work/oracle_yi1.bin gfx [work/oracle_yi1_oam.bin]   (graficos de Mario)
 *   work/marioverify work/oracle_yi1.bin loop   (lazo cerrado: solo el joypad)
 *   work/marioverify work/oracle_yi1.bin sprload [spr.lv]   (cargador de sprites, etapa 9)
 *   FULL_FRAME=N work/mvtrace ... full   (un solo frame; mvtrace = -DMCOLL_TRACE)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mario.h"
#include "gen/smwram.h"
#include "gen/smwtab.h"
#include "smwmac.h"

#define REC 584             /* 8 de cabecera + 256 + 320 */

typedef struct { const char *name; int adr; int w; } Field;

static const Field fields[] = {
    {"AccSpeedX $7A-7B", wm_MarioAccSpeedX, 2},
    {"SpeedY $7D", wm_MarioSpeedY, 1},
    {"IsFlying $72", wm_IsFlying, 1},
    {"Direction $76", wm_MarioDirection, 1},
    {"IsDucking $73", wm_IsDucking, 1},
    {"DashTimer $13E4", wm_PlayerDashTimer, 1},
    {"IsSpinJump $140D", wm_IsSpinJump, 1},
    {"SlopePose $13ED", wm_PlayerSlopePose, 1},
};
#define NF ((int)(sizeof fields / sizeof fields[0]))

static unsigned char *db;
static long nrec;

static unsigned frame_of(long i) {
    unsigned char *p = db + i * REC;
    return p[0] | p[1] << 8 | p[2] << 16 | (unsigned)p[3] << 24;
}
static unsigned char *dp_of(long i) { return db + i * REC + 8; }
static unsigned char *w13_of(long i) { return db + i * REC + 8 + 256; }

static int orc(long i, int adr)             /* byte del oraculo en el frame i */
{
    if (adr < 0x100) return dp_of(i)[adr];
    if (adr >= 0x13C0 && adr < 0x1500) return w13_of(i)[adr - 0x13C0];
    return -1;
}

static int keep_ram;         /* modo full: la RAM no grabada persiste */
static void load(long i)
{
    if (!keep_ram) memset(ram, 0, sizeof ram);
    memcpy(ram, dp_of(i), 256);
    memcpy(ram + 0x13C0, w13_of(i), 320);
}

static void take(long j, int adr) { int v = orc(j, adr); if (v >= 0) ram[adr] = (u8)v; }

/* ------------------------------------------------------------------ */
/* Modo "full" (etapa 8b): el frame entero del jugador, colision incluida.
   De N+1 solo se toman las ENTRADAS (joypad, contador de frames); todo lo
   demas lo calcula el port desde el estado de N, contra el mapa de la
   capa 1 (work/yi1_map16.bin, tools/mkmapbin.py), que se recarga al
   empezar cada tramo del nivel y guarda los cambios (monedas...) que hace
   el propio port. */
static const Field ffields[] = {
    {"XPos $94-95", wm_MarioXPos, 2},
    {"YPos $96-97", wm_MarioYPos, 2},
    {"SpeedX $7B", wm_MarioSpeedX, 1},
    {"SpeedY $7D", wm_MarioSpeedY, 1},
    {"SubX $13DA", wm_PlayerXAccFixed, 1},
    {"SubY $13DC", wm_PlayerXAccFixed + 2, 1},
    {"AccSpeedX $7A", wm_MarioAccSpeedX, 1},
    {"ObjStatus $77", wm_MarioObjStatus, 1},
    {"OnGround $13EF", wm_IsOnGround, 1},
    {"IsFlying $72", wm_IsFlying, 1},
    {"SlopeA $13EE", wm_OnSlopeTypeA, 1},
    {"SlopeB $13E1", wm_OnSlopeTypeB, 1},
    {"SlopePose $13ED", wm_PlayerSlopePose, 1},
    {"Direction $76", wm_MarioDirection, 1},
    {"IsDucking $73", wm_IsDucking, 1},
    {"DashTimer $13E4", wm_PlayerDashTimer, 1},
    {"IsSpinJump $140D", wm_IsSpinJump, 1},
    {"FrameB $14", wm_FrameB, 1},
    {"MarioFrame $13E0", wm_MarioFrame, 1},
    {"WalkPose $13DB", wm_PlayerWalkPose, 1},
    {"AnimTimer $1496", wm_PlayerAnimTimer, 1},
    {"CapeImage $13DF", wm_CapeImage, 1},
    {"CapeWave $14A2", wm_CapeWaveTimer, 1},
    {"FrameIndex $13E5", wm_PlayerFrameIndex, 1},
};
#define NFF ((int)(sizeof ffields / sizeof ffields[0]))

static unsigned fdump_frame;        /* fulldump: volcar el estado preparado */
static const char *fdump_path;

static int run_full(const char *mappath, const char *only, int verbose)
{
    static u8 map0[0x8000], map[0x8000];
    long i, pairs = 0, unsup = 0, skipped = 0, allok[2] = {0, 0}, tot[2] = {0, 0};
    long ok[NFF][2], bad[NFF][2], why[16], cls[8];
    int shown = 0, k, n;
    size_t mlen;
    FILE *f = fopen(mappath, "rb");
    if (!f) { perror(mappath); return 2; }
    mlen = fread(map0, 1, sizeof map0, f);
    fclose(f);
    memset(ok, 0, sizeof ok); memset(bad, 0, sizeof bad);
    memset(why, 0, sizeof why); memset(cls, 0, sizeof cls);
    map16_lo = map;
    map16_hi = map + mlen / 2;
    keep_ram = 1;
    memset(ram, 0, sizeof ram);

    for (i = 0; i + 1 < nrec; i++) {
        long j = i + 1;
        int air, all = 1, spr;
        /* tramo nuevo del nivel: el juego vuelve a cargar el mapa */
        if (i == 0 || frame_of(i) != frame_of(i - 1) + 1 || db[(i - 1) * REC + 4] != 0x29)
        { memcpy(map, map0, mlen); memset(ram, 0, sizeof ram); }
        if (frame_of(j) != frame_of(i) + 1) continue;
        if (db[i * REC + 4] != 0x29 || db[j * REC + 4] != 0x29) continue;
        if (orc(j, wm_MarioAnimation) || orc(i, wm_MarioAnimation)
            || orc(j, wm_SpritesLocked) || orc(i, wm_SpritesLocked)) { skipped++; continue; }
        if (getenv("FULL_FRAME") && frame_of(j) != (unsigned)atoi(getenv("FULL_FRAME")))
            continue;
        pairs++;
        load(i);
        take(j, 0x13);                      /* FrameA: lo sube el bucle del juego */
        for (k = 0x15; k <= 0x18; k++) take(j, k);
        /* camara de N+1 ($1A-$1D): CODE_00F6DB corre antes que Mario y
           todavia no esta portada (etapa 6); es una entrada mas */
        for (k = 0; k < 4; k++) take(j, wm_Bg1HOfs + k);
        ram[0x1931] = 0x07;                 /* wm_LvHeadTileset (no se graba) */
        if (fdump_frame && frame_of(j) == fdump_frame) {
            /* estado de N + entradas de N+1, para player/logicbench.s:
               $0000-$00FF y $13C0-$14FF, 576 bytes */
            FILE *o = fopen(fdump_path, "wb");
            fwrite(ram, 1, 256, o);
            fwrite(ram + 0x13C0, 1, 320, o);
            fclose(o);
            printf("estado del frame %u -> %s\n", fdump_frame, fdump_path);
        }
        for (k = 0; k < 128; k++) ram[0x0201 + 4 * k] = 0xF0;   /* wm_ClearOam */
        mario_unsupported = 0;
        mario_E2BD();                       /* orden de CODE_00A295 */
        if (!mario_unsupported) mario_player();
        if (!mario_unsupported) blocks_update();
        if (mario_unsupported) { unsup++; why[mario_unsupported & 15]++; continue; }

        air = orc(i, wm_IsFlying) != 0;
        /* los sprites corren DESPUES que Mario y pueden moverlo: pisar un
           enemigo, apoyarse en un sprite solido, empujones */
        spr = orc(j, wm_IsOnSolidSpr) || orc(i, wm_IsOnSolidSpr);
        tot[air]++;
        for (k = 0; k < NFF; k++) {
            int a = ffields[k].adr, m;
            m = ram[a] == orc(j, a) && (ffields[k].w == 1 || ram[a + 1] == orc(j, a + 1));
            if (m) ok[k][air]++; else { bad[k][air]++; all = 0; }
            if (!m && verbose && shown < 60 && (!only || strstr(ffields[k].name, only))) {
                shown++;
                printf("  frame %u (%s) %-16s port %02X%02X oraculo %02X%02X | x %04X y %04X vx %02X vy %02X "
                       "joy %02X/%02X vuela %02X->%02X st %02X->%02X suelo %02X->%02X spr %d ev %03X\n",
                       frame_of(j), air ? "aire" : "suelo", ffields[k].name,
                       ffields[k].w == 2 ? ram[a + 1] : 0, ram[a],
                       ffields[k].w == 2 ? orc(j, a + 1) : 0, orc(j, a),
                       orc(i, wm_MarioXPos) | orc(i, wm_MarioXPos + 1) << 8,
                       orc(i, wm_MarioYPos) | orc(i, wm_MarioYPos + 1) << 8,
                       orc(i, wm_MarioSpeedX), orc(i, wm_MarioSpeedY),
                       orc(j, 0x15), orc(j, 0x16),
                       orc(i, wm_IsFlying), orc(j, wm_IsFlying),
                       orc(i, wm_MarioObjStatus), orc(j, wm_MarioObjStatus),
                       orc(i, wm_IsOnGround), orc(j, wm_IsOnGround), spr, mario_events);
            }
        }
        allok[air] += all;
        if (!all) {
            if (spr) cls[0]++;
            else if (orc(j, wm_IsSpinJump) && !orc(i, wm_IsSpinJump)) cls[1]++;
            else cls[2]++;
        }
    }
    printf("\n[full] pares de frames seguidos en YI1: %ld (sin portar: %ld; sin fisica normal: %ld)\n",
           pairs, unsup, skipped);
    if (unsup) {
        printf("sin portar por causa:");
        for (n = 0; n < 16; n++) if (why[n]) printf(" %d:%ld", n, why[n]);
        printf("\n");
    }
    printf("frames con algun fallo: %ld sobre/junto a un sprite solido, %ld otros\n",
           cls[0], cls[2] + cls[1]);
    printf("%-20s %18s %18s\n", "campo", "en el aire (N)", "en el suelo (N)");
    for (k = 0; k < NFF; k++)
        printf("%-20s %8ld/%-8ld  %8ld/%-8ld\n", ffields[k].name,
               ok[k][1], ok[k][1] + bad[k][1], ok[k][0], ok[k][0] + bad[k][0]);
    printf("%-20s %8ld/%-8ld  %8ld/%-8ld\n", "TODOS los campos", allok[1], tot[1], allok[0], tot[0]);
    return 0;
}

/* ------------------------------------------------------------------ */
/* Modo "gfx": los gráficos de Mario (CODE_00E2BD, player/mgfx.c).  En el
   frame N+1 el juego dibuja a Mario ANTES de moverlo: con el estado de N y
   la camara de N+1.  Se compara la OAM que escribe el port (entradas
   visibles, en orden de slot) con la grabada al final de N+1
   (work/oracle_yi1_oam.bin): tienen que aparecer seguidas y exactas
   (x, y, tile, atributos, tamaño).  Tambien MarioScrPosX/Y. */
#define OREC 645
static int run_gfx(const char *oampath)
{
    unsigned char *odb;
    long i, n = 0, okoam = 0, okscr = 0, shown = 0, drawn = 0, tiles = 0;
    FILE *f = fopen(oampath, "rb");
    if (!f) { perror(oampath); return 2; }
    odb = malloc(nrec * OREC);
    if (fread(odb, OREC, nrec, f) != (size_t)nrec) { fprintf(stderr, "%s: lectura corta\n", oampath); return 2; }
    fclose(f);
    for (i = 0; i + 1 < nrec; i++) {
        long j = i + 1;
        unsigned char port[128 * 5], *rec = odb + j * OREC + 5;
        int np = 0, nr = odb[j * OREC + 4], s, k, found = 0, scr;
        if (frame_of(j) != frame_of(i) + 1) continue;
        if (db[i * REC + 4] != 0x29 || db[j * REC + 4] != 0x29) continue;
        if (orc(i, wm_MarioPowerUp) == 2) continue;          /* capa: sin portar */
        load(i);
        take(j, 0x13);
        for (k = 0; k < 4; k++) take(j, wm_Bg1HOfs + k);  /* $1A-$1D: camara de N+1 */
        for (s = 0; s < 128; s++) ram[0x0201 + 4 * s] = 0xF0;   /* wm_ClearOam */
        mario_unsupported = 0;
        mario_E2BD();
        if (mario_unsupported) continue;
        n++;
        for (s = 0; s < 128; s++) {
            unsigned char *o = ram + 0x0200 + 4 * s;
            if (o[1] == 0xF0) continue;
            port[np * 5] = o[0]; port[np * 5 + 1] = o[1]; port[np * 5 + 2] = o[2];
            port[np * 5 + 3] = o[3]; port[np * 5 + 4] = ram[0x0420 + s];
            np++;
        }
        for (k = 0; k + np <= nr && !found; k++)
            if (!memcmp(rec + 5 * k, port, 5 * np)) found = 1;
        if (np == 0) found = 1;                 /* no dibuja: nada que buscar */
        else { drawn++; tiles += np; }
        scr = ram[wm_MarioScrPosX] == orc(j, wm_MarioScrPosX)
              && ram[wm_MarioScrPosX + 1] == orc(j, wm_MarioScrPosX + 1)
              && ram[wm_MarioScrPosY] == orc(j, wm_MarioScrPosY)
              && ram[wm_MarioScrPosY + 1] == orc(j, wm_MarioScrPosY + 1);
        okoam += found; okscr += scr;
        if ((!found || !scr) && shown < 30) {
            shown++;
            printf("  frame %u: scr port %02X%02X,%02X%02X oraculo %02X%02X,%02X%02X | port",
                   frame_of(j), ram[wm_MarioScrPosX + 1], ram[wm_MarioScrPosX],
                   ram[wm_MarioScrPosY + 1], ram[wm_MarioScrPosY],
                   orc(j, wm_MarioScrPosX + 1), orc(j, wm_MarioScrPosX),
                   orc(j, wm_MarioScrPosY + 1), orc(j, wm_MarioScrPosY));
            for (k = 0; k < np; k++) printf(" %02x%02x%02x%02x%02x", port[5*k], port[5*k+1], port[5*k+2], port[5*k+3], port[5*k+4]);
            printf(" | oraculo");
            for (k = 0; k < nr && k < 8; k++) printf(" %02x%02x%02x%02x%02x", rec[5*k], rec[5*k+1], rec[5*k+2], rec[5*k+3], rec[5*k+4]);
            printf("\n");
        }
    }
    printf("\n[gfx] frames: %ld (con Mario dibujado: %ld, %ld entradas de OAM)\n"
           "      OAM de Mario exacta: %ld  MarioScrPosX/Y exacta: %ld\n", n, drawn, tiles, okoam, okscr);
    return 0;
}

#ifdef NOOAM
/* Modo "mspr" (build -DNOOAM, 6b.4): como "gfx", pero con las entradas que
   mgfx.c deja en mario_oam / mario_osz, y ademas los sprites de mspr.c
   contra un render de referencia hecho como la SNES: la VRAM de sprites
   armada como el DMA del NMI (wm_0D85: 5 punteros por fila de 64 bytes,
   wm_Tile7FPtr en el tile $7F) y las entradas con volteo y prioridad. */
static u8 g32[0x5D00];
static int ref_px(int x, int y)            /* color (0..15) de la referencia */
{
    static u8 vram[0x80][32];
    int e, i;
    for (i = 0; i < 5; i++) {
        int r;
        for (r = 0; r < 2; r++) {
            int p = (ram[wm_0D85 + 10 * r + 2 * i] | ram[wm_0D85 + 10 * r + 2 * i + 1] << 8) - 0x2000;
            if (p >= 0 && p + 64 <= (int)sizeof g32) {
                memcpy(vram[16 * r + 2 * i], g32 + p, 32);
                memcpy(vram[16 * r + 2 * i + 1], g32 + p + 32, 32);
            } else {
                memset(vram[16 * r + 2 * i], 0, 64);
            }
        }
    }
    {
        int p = (ram[wm_Tile7FPtr] | ram[wm_Tile7FPtr + 1] << 8) - 0x2000;
        if (p >= 0 && p + 32 <= (int)sizeof g32) memcpy(vram[0x7F], g32 + p, 32);
        else memset(vram[0x7F], 0, 32);
    }
    for (e = 0; e < 4; e++) {               /* la primera que tenga color */
        u8 *o = mario_oam + 4 * e;
        int sz = (mario_osz[e] & 2) ? 16 : 8, ex, ey, u, v, t, c;
        if (o[1] == 0xF0) continue;
        ex = o[0] | ((mario_osz[e] & 1) << 8); if (ex >= 256) ex -= 512;
        ey = o[1] >= 0xF0 ? o[1] - 256 : o[1];
        u = x - ex; v = y - ey;
        if (u < 0 || v < 0 || u >= sz || v >= sz) continue;
        if (o[3] & 0x40) u = sz - 1 - u;
        if (o[3] & 0x80) v = sz - 1 - v;
        t = o[2] + (u >> 3) + 16 * (v >> 3);
        if (!((t < 0x20 && (t & 15) < 10) || t == 0x7F)) continue;
        u &= 7; v &= 7;
        c = ((vram[t][2 * v] >> (7 - u)) & 1) | (((vram[t][2 * v + 1] >> (7 - u)) & 1) << 1)
            | (((vram[t][16 + 2 * v] >> (7 - u)) & 1) << 2) | (((vram[t][17 + 2 * v] >> (7 - u)) & 1) << 3);
        if (c) return c;
    }
    return 0;
}

static int run_mspr(const char *oampath, const char *g32path)
{
    unsigned char *odb;
    static u16 spr[4 * MSPR_WORDS];
    long i, n = 0, okoam = 0, okpx = 0, drawn = 0, shown = 0;
    FILE *f = fopen(oampath, "rb"), *g = fopen(g32path, "rb");
    if (!f) { perror(oampath); return 2; }
    if (!g || fread(g32, 1, sizeof g32, g) != sizeof g32) { perror(g32path); return 2; }
    fclose(g);
    gfx32 = g32;
    odb = malloc(nrec * OREC);
    if (fread(odb, OREC, nrec, f) != (size_t)nrec) { fprintf(stderr, "%s: lectura corta\n", oampath); return 2; }
    fclose(f);
    for (i = 0; i + 1 < nrec; i++) {
        long j = i + 1;
        unsigned char port[4 * 5], *rec = odb + j * OREC + 5;
        int np = 0, nr = odb[j * OREC + 4], k, found = 0, x, y, bad = 0, cols;
        static int got[240][256];
        if (frame_of(j) != frame_of(i) + 1) continue;
        if (db[i * REC + 4] != 0x29 || db[j * REC + 4] != 0x29) continue;
        if (orc(i, wm_MarioPowerUp) == 2) continue;
        load(i);
        take(j, 0x13);
        for (k = 0; k < 4; k++) take(j, wm_Bg1HOfs + k);
        mario_unsupported = 0;
        mario_E2BD();
        if (mario_unsupported) continue;
        n++;
        for (k = 0; k < 4; k++) {
            u8 *o = mario_oam + 4 * k;
            if (o[1] == 0xF0) continue;
            memcpy(port + 5 * np, o, 4);
            port[5 * np + 4] = mario_osz[k];
            np++;
        }
        for (k = 0; k + np <= nr && !found; k++)
            if (!memcmp(rec + 5 * k, port, 5 * np)) found = 1;
        if (np == 0) found = 1; else drawn++;
        okoam += found;
        /* los sprites, decodificados, contra la referencia */
        cols = mario_sprite(spr, 0x2C, 0xA0);
        memset(got, 0, sizeof got);
        for (k = 0; k < cols; k++) {
            u16 *a = spr + 2 * k * MSPR_WORDS, *b = a + MSPR_WORDS;
            int vs = (a[0] >> 8) | ((a[1] >> 2) & 1) << 8, ve = (a[1] >> 8) | ((a[1] >> 1) & 1) << 8;
            int hs = ((a[0] & 0xFF) << 1) | (a[1] & 1), l;
            if (!(b[1] & 0x80)) bad = 1;    /* la impar tiene que ir adosada */
            for (l = 0; l < ve - vs; l++)
                for (x = 0; x < 16; x++) {
                    int sx = hs - 0xA0 + x, sy = vs - 0x2C - 1 + l, c;
                    c = ((a[2 + 2 * l] >> (15 - x)) & 1) | (((a[3 + 2 * l] >> (15 - x)) & 1) << 1)
                        | (((b[2 + 2 * l] >> (15 - x)) & 1) << 2) | (((b[3 + 2 * l] >> (15 - x)) & 1) << 3);
                    if (sx >= 0 && sx < 256 && sy >= 0 && sy < 240 && c) got[sy][sx] = c;
                }
        }
        for (y = 0; y < 240 && !bad; y++)
            for (x = 0; x < 256; x++)
                if (got[y][x] != ref_px(x, y)) { bad = 1; break; }
        if (bad && getenv("MSPR_DBG") && shown < 1) {
            int e2;
            for (e2 = 0; e2 < 4; e2++) printf("e%d %02x %02x %02x %02x sz %d\n", e2, mario_oam[4*e2], mario_oam[4*e2+1], mario_oam[4*e2+2], mario_oam[4*e2+3], mario_osz[e2]);
            for (y = 0; y < 240; y++) for (x = 0; x < 256; x++) { int r = ref_px(x, y); if (got[y][x] || r) { if (got[y][x] != r) printf("(%d,%d) got %d ref %d\n", x, y, got[y][x], r); } }
        }
        okpx += !bad;
        if ((!found || bad) && shown++ < 20)
            printf("  frame %u: OAM %s, pixeles %s\n", frame_of(j), found ? "ok" : "MAL", bad ? "MAL" : "ok");
    }
    printf("\n[mspr] frames: %ld (con Mario dibujado: %ld)\n"
           "       mario_oam = OAM grabada: %ld  sprites = referencia: %ld\n", n, drawn, okoam, okpx);
    return !(okoam == n && okpx == n);
}
#endif

/* ------------------------------------------------------------------ */
/* Modo "loop": LAZO CERRADO.  Desde el primer frame de cada tramo el port
   corre solo, recibiendo del oraculo unicamente el joypad ($15-$18), con
   el orden de CODE_00A295: FrameA++, wm_ClearOam, camara (F6DB), graficos
   de Mario (E2BD), el jugador (C500...) y los bloques que rebotan.  Se
   compara cada frame con el oraculo; en la primera diferencia se anota el
   frame y el campo, se vuelve a cargar el estado grabado (resincronizar) y
   se sigue.  Tramos mas largos = el port reproduce la partida solo. */
static const Field lfields[] = {
    {"Bg1HOfs $1A", wm_Bg1HOfs, 2}, {"Bg1VOfs $1C", wm_Bg1VOfs, 2},
    {"Bg2HOfs $1E", wm_Bg2HOfs, 2}, {"Bg2VOfs $20", wm_Bg2VOfs, 2},
    {"ScrPosX $7E", wm_MarioScrPosX, 2}, {"ScrPosY $80", wm_MarioScrPosY, 2},
};
#define NLF ((int)(sizeof lfields / sizeof lfields[0]))

static int run_loop(const char *mappath)
{
    static u8 map0[0x8000], map[0x8000];
    long i, frames = 0, resync = 0, longest = 0, cur = 0, longest_end = 0;
    long cause[NFF + NLF + 2];
    size_t mlen;
    int k, shown = 0, synced = 0;
    FILE *f = fopen(mappath, "rb");
    if (!f) { perror(mappath); return 2; }
    mlen = fread(map0, 1, sizeof map0, f);
    fclose(f);
    map16_lo = map;
    map16_hi = map + mlen / 2;
    keep_ram = 1;
    memset(cause, 0, sizeof cause);

    for (i = 0; i < nrec; i++) {
        int bad = -1;
        int newseg = i == 0 || frame_of(i) != frame_of(i - 1) + 1 || db[(i - 1) * REC + 4] != 0x29;
        if (db[i * REC + 4] != 0x29) { synced = 0; continue; }
        if (newseg) { memcpy(map, map0, mlen); memset(ram, 0, sizeof ram); synced = 0; }
        if (orc(i, wm_MarioAnimation) || orc(i, wm_SpritesLocked)) { synced = 0; continue; }
        if (!synced) {                          /* (re)arrancar desde el oraculo */
            load(i);
            ram[0x1931] = 0x07;
            synced = 1;
            if (cur > longest) { longest = cur; longest_end = frame_of(i); }
            cur = 0;
            continue;
        }
        /* un frame del juego con las entradas de i */
        for (k = 0x15; k <= 0x18; k++) take(i, k);
        level_frame();
        frames++;
        if (mario_unsupported) bad = NFF + NLF;
        for (k = 0; k < NFF && bad < 0; k++) {
            int a = ffields[k].adr;
            if (ram[a] != orc(i, a) || (ffields[k].w == 2 && ram[a + 1] != orc(i, a + 1))) bad = k;
        }
        for (k = 0; k < NLF && bad < 0; k++) {
            int a = lfields[k].adr;
            if (ram[a] != orc(i, a) || (lfields[k].w == 2 && ram[a + 1] != orc(i, a + 1))) bad = NFF + k;
        }
        if (bad < 0) { cur++; continue; }
        cause[bad]++;
        resync++;
        if (shown < 40) {
            int a = bad < NFF ? ffields[bad].adr : bad < NFF + NLF ? lfields[bad - NFF].adr : 0;
            shown++;
            printf("  frame %u: tras %ld frames solo, difiere %s (port %02X%02X oraculo %02X%02X)%s\n",
                   frame_of(i), cur,
                   bad < NFF ? ffields[bad].name : bad < NFF + NLF ? lfields[bad - NFF].name : "(sin portar)",
                   a ? ram[a + 1] : 0, a ? ram[a] : 0, a ? orc(i, a + 1) : 0, a ? orc(i, a) : 0,
                   orc(i, wm_IsOnSolidSpr) ? "  [sobre un sprite]" : "");
        }
        if (getenv("LOOP_DIFF") && shown <= 40) {  /* todos los bytes grabados distintos */
            int adr;
            printf("      distintos (port/oraculo):");
            for (adr = 0; adr < 0x1500; adr++) {
                int v = orc(i, adr);
                if (v >= 0 && ram[adr] != v) printf(" $%04X=%02X/%02X", adr, ram[adr], v);
                if (adr == 0xFF) adr = 0x13BF;
            }
            printf("\n");
        }
        if (cur > longest) { longest = cur; longest_end = frame_of(i); }
        cur = 0;
        load(i);                                /* resincronizar */
        ram[0x1931] = 0x07;
    }
    if (cur > longest) { longest = cur; longest_end = frame_of(nrec - 1); }
    printf("\n[loop] frames corridos por el port: %ld, resincronizaciones: %ld\n", frames, resync);
    printf("       tramo mas largo sin diferencias: %ld frames (hasta el %ld)\n", longest, longest_end);
    printf("       primer campo distinto en cada resincronizacion:");
    for (k = 0; k < NFF; k++) if (cause[k]) printf(" %s:%ld", ffields[k].name, cause[k]);
    for (k = 0; k < NLF; k++) if (cause[NFF + k]) printf(" %s:%ld", lfields[k].name, cause[NFF + k]);
    if (cause[NFF + NLF]) printf(" sin-portar:%ld", cause[NFF + NLF]);
    printf("\n");
    return 0;
}

/* ------------------------------------------------------------------ */
/* Modo "sprload" (etapa 9): el cargador de sprites (LoadSprFromLevel).
   En N+1 el juego lo corre al final del frame con la camara de N+1 y las
   ranuras como quedaron tras los sprites: se toman del oraculo, quitando
   las que nacen en N+1 (estado 1 en N+1 y no en N).  El port tiene que
   crear exactamente esas: misma ranura, numero, X e Y.  wm_SprLoadStatus
   (no se graba) lo lleva el port; al empezar un tramo se marcan cargados
   los sprites a la vista, y cuando uno desaparece de 8 a 0 (salio de
   pantalla) se libera su indice, como hace el juego. */
static int run_sprload(const char *sprpath)
{
    static u8 spr[1024];
    long i, frames = 0, want = 0, got = 0, ok = 0, bad = 0;
    int k, shown = 0;
    FILE *f = fopen(sprpath, "rb");
    if (!f) { perror(sprpath); return 2; }
    if (fread(spr, 1, sizeof spr, f) < 4) return 2;
    fclose(f);
    spr_level = spr;
    keep_ram = 1;
    memset(ram, 0, sizeof ram);
    for (i = 0; i + 1 < nrec; i++) {
        long j = i + 1;
        int newseg = i == 0 || frame_of(i) != frame_of(i - 1) + 1 || db[(i - 1) * REC + 4] != 0x29;
        u8 expect = 0;
        if (db[i * REC + 4] != 0x29) continue;
        if (newseg) {
            int y, idx;
            unsigned cam = orc(i, wm_Bg1HOfs) | orc(i, wm_Bg1HOfs + 1) << 8;
            memset(ram, 0, sizeof ram);
            for (k = 0; k < 12; k++) ram[wm_SprIndexInLvl + k] = 0xFF;
            for (y = 1, idx = 0; spr[y] != 0xFF; y += 3, idx++) {
                unsigned sx = (((spr[y] << 3) & 0x10) | (spr[y + 1] & 0x0F)) << 8 | (spr[y + 1] & 0xF0);
                if (sx + 0x30 >= cam && sx < cam + 0x120) ram[wm_SprLoadStatus + idx] = 1;
            }
        }
        if (frame_of(j) != frame_of(i) + 1 || db[j * REC + 4] != 0x29) continue;
        load(i);
        ram[wm_SpriteMemory] = spr[0] & 0x3F;
        for (k = 0; k < 4; k++) take(j, wm_Bg1HOfs + k);
        take(j, wm_Layer1ScrollDir); take(j, wm_FrameA);
        for (k = 0; k < 12; k++) {
            int si = orc(i, wm_SpriteStatus + k), sj = orc(j, wm_SpriteStatus + k);
            if (si == 8 && sj == 0 && ram[wm_SprIndexInLvl + k] != 0xFF) {
                /* salio de pantalla (y no murio a la vista: un salto con
                   giro mata de 8 a 0 y el indice queda cargado) */
                int sx = orc(i, wm_SpriteXLo + k) | orc(i, wm_SpriteXHi + k) << 8;
                int cx = orc(i, wm_Bg1HOfs) | orc(i, wm_Bg1HOfs + 1) << 8;
                if (sx < cx - 0x20 || sx > cx + 0x110)
                    ram[wm_SprLoadStatus + ram[wm_SprIndexInLvl + k]] = 0;
            }
            ram[wm_SpriteStatus + k] = (u8)sj;
            if (sj == 1 && si != 1) { expect |= (u8)(1 << k); ram[wm_SpriteStatus + k] = 0; }
        }
        mario_unsupported = 0;
        sprite_load_level();
        frames++;
        for (k = 0; k < 8; k++) {
            int e = (expect >> k) & 1, p = (spr_spawned >> k) & 1, m = e == p;
            want += e; got += p;
            if (e && p)
                m = ram[wm_SpriteNum + k] == orc(j, wm_SpriteNum + k)
                    && ram[wm_SpriteXLo + k] == orc(j, wm_SpriteXLo + k)
                    && ram[wm_SpriteXHi + k] == orc(j, wm_SpriteXHi + k)
                    && ram[wm_SpriteYLo + k] == orc(j, wm_SpriteYLo + k)
                    && ram[wm_SpriteYHi + k] == orc(j, wm_SpriteYHi + k);
            if (!e && !p) continue;
            if (m) ok++;
            else {
                bad++;
                if (shown++ < 30)
                    printf("  frame %u ranura %d: oraculo %s num %02X x %02X%02X y %02X%02X | port %s num %02X x %02X%02X y %02X%02X (camara %02X%02X dir %d)\n",
                           frame_of(j), k, e ? "nace" : "-", orc(j, wm_SpriteNum + k),
                           orc(j, wm_SpriteXHi + k), orc(j, wm_SpriteXLo + k),
                           orc(j, wm_SpriteYHi + k), orc(j, wm_SpriteYLo + k),
                           p ? "nace" : "-", ram[wm_SpriteNum + k], ram[wm_SpriteXHi + k],
                           ram[wm_SpriteXLo + k], ram[wm_SpriteYHi + k], ram[wm_SpriteYLo + k],
                           orc(j, wm_Bg1HOfs + 1), orc(j, wm_Bg1HOfs), orc(j, wm_Layer1ScrollDir));
            }
        }
    }
    printf("\n[sprload] frames: %ld  nacimientos en el oraculo: %ld  del port: %ld  exactos: %ld  distintos: %ld\n",
           frames, want, got, ok, bad);
    return 0;
}

/* ------------------------------------------------------------------ */
/* Modo "sprloop" (etapa 9): los Rex en LAZO CERRADO.  Mario y la camara
   son entradas (del oraculo en cada frame: $94-$97, PlayerXPosLv, $1A-$1D,
   $55, FrameA, $9D); los sprites los corre el port: temporizadores,
   HandleSprite, el Rex, y el cargador al final.  Solo se siguen los Rex que
   nacen a la vista del port (de los que ya estaban no se conocen sus tablas
   que no se graban); los demas sprites se copian del oraculo.  Se compara
   cada Rex seguido: estado, X, Y, velocidades, subestado; en la primera
   diferencia se anota y se resincroniza esa ranura. */
static int run_sprloop(const char *sprpath, const char *mappath)
{
    static u8 spr[1024], map0[0x8000], map[0x8000];
    static const int cmp[] = { wm_SpriteStatus, wm_SpriteXLo, wm_SpriteXHi, wm_SpriteYLo,
                               wm_SpriteYHi, wm_SpriteSpeedX, wm_SpriteSpeedY, wm_SpriteState,
                               wm_SpriteXAcc, wm_SpriteYAcc };
    static const char *cname[] = { "estado", "xlo", "xhi", "ylo", "yhi", "vx", "vy", "subestado",
                                   "subx", "suby" };
#define NCMP 10
    long i, frames = 0, tracked = 0, okf = 0, badf = 0, cause[NCMP] = {0};
    long bounce_port = 0, bounce_orc = 0, bounce_ok = 0;
    int k, c, shown = 0, follow[12] = {0};
    size_t mlen;
    FILE *f = fopen(sprpath, "rb");
    if (!f) { perror(sprpath); return 2; }
    if (fread(spr, 1, sizeof spr, f) < 4) return 2;
    fclose(f);
    f = fopen(mappath, "rb");
    if (!f) { perror(mappath); return 2; }
    mlen = fread(map0, 1, sizeof map0, f);
    fclose(f);
    spr_level = spr;
    map16_lo = map;
    map16_hi = map + mlen / 2;
    keep_ram = 1;
    for (i = 0; i + 1 < nrec; i++) {
        long j = i + 1;
        int newseg = i == 0 || frame_of(i) != frame_of(i - 1) + 1 || db[(i - 1) * REC + 4] != 0x29;
        if (db[i * REC + 4] != 0x29) continue;
        if (newseg) {
            int y, idx;
            unsigned cam = orc(i, wm_Bg1HOfs) | orc(i, wm_Bg1HOfs + 1) << 8;
            memset(ram, 0, sizeof ram);
            memcpy(map, map0, mlen);
            load(i);
            ram[0x1931] = 0x07;
            ram[wm_SpriteMemory] = spr[0] & 0x3F;
            ram[wm_LowestSolidSprTile] = ram[wm_HighestSolidSprTile] = 0xFF;   /* tileset 7 */
            for (k = 0; k < 12; k++) { ram[wm_SprIndexInLvl + k] = 0xFF; follow[k] = 0; }
            for (y = 1, idx = 0; spr[y] != 0xFF; y += 3, idx++) {
                unsigned sx = (((spr[y] << 3) & 0x10) | (spr[y + 1] & 0x0F)) << 8 | (spr[y + 1] & 0xF0);
                if (sx + 0x30 >= cam && sx < cam + 0x120) ram[wm_SprLoadStatus + idx] = 1;
            }
        }
        if (frame_of(j) != frame_of(i) + 1 || db[j * REC + 4] != 0x29) continue;
        /* entradas: Mario, camara, contador, bloqueo */
        for (k = 0; k < 4; k++) { take(j, wm_MarioXPos + k); take(j, wm_Bg1HOfs + k); }
        take(j, wm_PlayerXPosLv); take(j, wm_PlayerXPosLv + 1);
        take(j, wm_Layer1ScrollDir); take(j, wm_FrameA); take(j, wm_SpritesLocked);
        take(j, wm_SlopeSteepness); take(j, wm_SlopeSteepness + 1);
        for (k = 0; k < 2; k++) { take(j, wm_PlayerYPosLv + k); }
        take(j, wm_IsDucking); take(j, wm_MarioPowerUp); take(j, wm_IsSpinJump);
        take(j, wm_IsClimbing); take(j, wm_StarPowerTimer); take(j, wm_PlayerHurtTimer);
        take(j, wm_MarioAnimation); take(j, wm_IsBehindScenery); take(j, 0x15);
        /* la SpeedY de Mario ANTES de los sprites: la de N+1 salvo que un
           sprite la cambie (pisoton $D0/$A8): se reconstruye del oraculo */
        {
            int vy = orc(j, wm_MarioSpeedY);
            ram[wm_MarioSpeedY] = (u8)((vy == 0xD0 || vy == 0xA8) ? 0x20 : vy);
        }
        mario_unsupported = 0;
        for (k = 11; k >= 0; k--) {
            if (!follow[k]) {                   /* no seguido: copiar del oraculo (estado de N+1) */
                for (c = 0; c < NCMP; c++) take(j, cmp[c] + k);
                take(j, wm_SpriteNum + k);
                if (orc(j, wm_SpriteStatus + k) == 0) ram[wm_SprIndexInLvl + k] = 0xFF;
                if (orc(j, wm_SpriteStatus + k) == 1 && orc(i, wm_SpriteStatus + k) != 1)
                    ram[wm_SpriteStatus + k] = 0;   /* nace en N+1: lo crea el cargador */
                if (ram[wm_SpriteStatus + k]) sprite_tweakers((u8)k);
                continue;
            }
            mario_unsupported = 0;
            sprite_run((u8)k);
            if (mario_unsupported) { follow[k] = 0; continue; }
        }
        {   /* rebote de Mario: lo hace el Rex (BoostMarioSpeed) */
            int pv = ram[wm_MarioSpeedY], ov = orc(j, wm_MarioSpeedY);
            int pb = pv == 0xD0 || pv == 0xA8, ob = ov == 0xD0 || ov == 0xA8;
            bounce_port += pb; bounce_orc += ob; bounce_ok += pb && ob && pv == ov;
        }
        sprite_load_level();
        for (k = 0; k < 12; k++)
            if ((spr_spawned >> k) & 1) {
                if (ram[wm_SpriteNum + k] == 0xAB) follow[k] = 1;
            }
        frames++;
        for (k = 0; k < 12; k++) {
            int bad = -1;
            if (!follow[k]) continue;
            if (ram[wm_SpriteStatus + k] == 0 && orc(j, wm_SpriteStatus + k) == 0) { follow[k] = 0; continue; }
            tracked++;
            for (c = 0; c < NCMP && bad < 0; c++)
                if (ram[cmp[c] + k] != orc(j, cmp[c] + k)) bad = c;
            if (bad < 0) { okf++; continue; }
            badf++; cause[bad]++;
            if (shown++ < 25)
                printf("  frame %u ranura %d: %s port %02X oraculo %02X | x %02X%02X/%02X%02X y %02X%02X/%02X%02X vx %02X/%02X vy %02X/%02X mario x %02X%02X y %02X%02X\n",
                       frame_of(j), k, cname[bad], ram[cmp[bad] + k], orc(j, cmp[bad] + k),
                       ram[wm_SpriteXHi + k], ram[wm_SpriteXLo + k], orc(j, wm_SpriteXHi + k), orc(j, wm_SpriteXLo + k),
                       ram[wm_SpriteYHi + k], ram[wm_SpriteYLo + k], orc(j, wm_SpriteYHi + k), orc(j, wm_SpriteYLo + k),
                       ram[wm_SpriteSpeedX + k], orc(j, wm_SpriteSpeedX + k),
                       ram[wm_SpriteSpeedY + k], orc(j, wm_SpriteSpeedY + k),
                       orc(j, wm_MarioXPos + 1), orc(j, wm_MarioXPos), orc(j, wm_MarioYPos + 1), orc(j, wm_MarioYPos));
            /* el contacto con Mario (MarioSprInteract) no esta portado: si el
               oraculo muestra un pisoton (subestado +1), se aplica lo que hace
               el Rex al recibirlo (SmushRex / segundo golpe) */
            if (orc(j, wm_SpriteState + k) == ram[wm_SpriteState + k] + 1) {
                if (orc(j, wm_SpriteState + k) == 2) ram[wm_SpriteDecTbl3 + k] = 0x20;
                else { ram[wm_DisSprCapeContact + k] = 0x0C; ram[wm_Tweaker1662 + k] = 0; }
            }
            for (c = 0; c < NCMP; c++) take(j, cmp[c] + k);       /* resincronizar */
            if (orc(j, wm_SpriteSpeedX + k))    /* la direccion no se graba: la del Rex es el signo de vx */
                ram[wm_SpriteDir + k] = (orc(j, wm_SpriteSpeedX + k) & 0x80) ? 1 : 0;
            if (orc(j, wm_SpriteStatus + k) != 8) follow[k] = 0;
        }
    }
    printf("\n[sprloop] frames: %ld  Rex-frames seguidos: %ld  exactos: %ld  con diferencia: %ld\n",
           frames, tracked, okf, badf);
    printf("          rebotes de Mario sobre un Rex: port %ld, oraculo %ld, coinciden %ld\n",
           bounce_port, bounce_orc, bounce_ok);
    printf("          primer campo distinto:");
    for (c = 0; c < NCMP; c++) if (cause[c]) printf(" %s:%ld", cname[c], cause[c]);
    printf("\n");
    return 0;
}

/* ------------------------------------------------------------------ */
/* Modo "game": el frame de nivel entero en lazo cerrado. Mario desde el
   joypad (como "loop") y, en el mismo frame y en el orden del juego, los
   sprites (los Rex que nacen a la vista los corre el port; el resto se
   copia del oraculo, como en "sprloop"). Asi los pisotones de Mario salen
   de los Rex del port. Resincroniza a Mario en cada diferencia (sin tocar
   los sprites que sigue el port). */
static int run_game(const char *sprpath, const char *mappath)
{
    static u8 spr[1024], map0[0x8000], map[0x8000], keep[0x2000];
    static const int scmp[] = { wm_SpriteStatus, wm_SpriteXLo, wm_SpriteXHi, wm_SpriteYLo,
                                wm_SpriteYHi, wm_SpriteSpeedX, wm_SpriteSpeedY, wm_SpriteState,
                                wm_SpriteXAcc, wm_SpriteYAcc, wm_SpriteNum };
    long i, frames = 0, resync = 0, longest = 0, cur = 0, rexf = 0, rexok = 0;
    long cause[NFF + 2];
    int k, c, synced = 0, follow[12] = {0}, shown = 0;
    size_t mlen;
    FILE *f = fopen(sprpath, "rb");
    if (!f) { perror(sprpath); return 2; }
    if (fread(spr, 1, sizeof spr, f) < 4) return 2;
    fclose(f);
    f = fopen(mappath, "rb");
    if (!f) { perror(mappath); return 2; }
    mlen = fread(map0, 1, sizeof map0, f);
    fclose(f);
    spr_level = spr;
    map16_lo = map;
    map16_hi = map + mlen / 2;
    keep_ram = 1;
    memset(cause, 0, sizeof cause);
    for (i = 0; i < nrec; i++) {
        int bad = -1;
        int newseg = i == 0 || frame_of(i) != frame_of(i - 1) + 1 || db[(i - 1) * REC + 4] != 0x29;
        if (db[i * REC + 4] != 0x29) { synced = 0; continue; }
        if (newseg) {
            int y, idx;
            unsigned cam = orc(i, wm_Bg1HOfs) | orc(i, wm_Bg1HOfs + 1) << 8;
            memcpy(map, map0, mlen);
            memset(ram, 0, sizeof ram);
            for (k = 0; k < 12; k++) follow[k] = 0;
            for (y = 1, idx = 0; spr[y] != 0xFF; y += 3, idx++) {
                unsigned sx = (((spr[y] << 3) & 0x10) | (spr[y + 1] & 0x0F)) << 8 | (spr[y + 1] & 0xF0);
                if (sx + 0x30 >= cam && sx < cam + 0x120) ram[wm_SprLoadStatus + idx] = 1;
            }
            synced = 0;
        }
        if (orc(i, wm_MarioAnimation) || orc(i, wm_SpritesLocked)) { synced = 0; continue; }
        if (!synced) {
            memcpy(keep, ram, sizeof keep);
            load(i);
            for (k = 0; k < 12; k++)            /* los sprites que sigue el port se quedan */
                if (follow[k]) for (c = 0; c < 11; c++) ram[scmp[c] + k] = keep[scmp[c] + k];
            ram[0x1931] = 0x07;
            ram[wm_SpriteMemory] = spr[0] & 0x3F;
            ram[wm_LowestSolidSprTile] = ram[wm_HighestSolidSprTile] = 0xFF;
            synced = 1;
            if (cur > longest) longest = cur;
            cur = 0;
            continue;
        }
        for (k = 0x15; k <= 0x18; k++) take(i, k);
        /* level_frame con los sprites en medio */
        ram[wm_FrameA]++;
        for (k = 0; k < 128; k++) ram[0x0201 + 4 * k] = 0xF0;
        mario_unsupported = 0;
        camera_F6DB();
        if (!mario_unsupported) mario_E2BD();
        W16(wm_PlayerXPosLv, R16(wm_MarioXPos));        /* CODE_00A2F3 */
        W16(wm_PlayerYPosLv, R16(wm_MarioYPos));
        if (!mario_unsupported) mario_player();
        if (!mario_unsupported) sprites_begin();
        for (k = 11; k >= 0; k--) {
            if (!follow[k]) {
                for (c = 0; c < 11; c++) take(i, scmp[c] + k);
                if (orc(i, wm_SpriteStatus + k) == 1 && (i == 0 || orc(i - 1, wm_SpriteStatus + k) != 1))
                    ram[wm_SpriteStatus + k] = 0;
                if (ram[wm_SpriteStatus + k]) sprite_tweakers((u8)k);
                continue;
            }
            {
                int u = mario_unsupported;
                mario_unsupported = 0;
                sprite_run((u8)k);
                if (mario_unsupported) follow[k] = 0;
                mario_unsupported = u;
            }
        }
        blocks_update();
        sprite_load_level();
        for (k = 0; k < 12; k++)
            if (((spr_spawned >> k) & 1) && (ram[wm_SpriteNum + k] == 0xAB || ram[wm_SpriteNum + k] == 0xB9
                 || ram[wm_SpriteNum + k] == 0x83))
                follow[k] = 1;
        frames++;
        for (k = 0; k < 12; k++) {
            int okr = 1;
            if (!follow[k]) continue;
            if (!ram[wm_SpriteStatus + k] && !orc(i, wm_SpriteStatus + k)) { follow[k] = 0; continue; }
            rexf++;
            for (c = 0; c < 10; c++) if (ram[scmp[c] + k] != orc(i, scmp[c] + k)) okr = 0;
            rexok += okr;
            if (!okr && getenv("GAME_SHOW")) {
                printf("  rex frame %u ranura %d:", frame_of(i), k);
                for (c = 0; c < 10; c++) if (ram[scmp[c] + k] != orc(i, scmp[c] + k))
                    printf(" [%04X] %02X/%02X", scmp[c], ram[scmp[c] + k], orc(i, scmp[c] + k));
                printf("\n");
            }
            if (!okr) {
                for (c = 0; c < 10; c++) take(i, scmp[c] + k);
                if (orc(i, wm_SpriteSpeedX + k)) ram[wm_SpriteDir + k] = (orc(i, wm_SpriteSpeedX + k) & 0x80) ? 1 : 0;
                if (orc(i, wm_SpriteStatus + k) != 8) follow[k] = 0;
            }
        }
        if (!getenv("GAME_NOADOPT"))              /* Rex que ya existian: los corre el port */
            for (k = 0; k < 12; k++)
                if (!follow[k] && ram[wm_SpriteNum + k] == 0xAB && ram[wm_SpriteStatus + k] == 8) {
                    follow[k] = 1;
                    ram[wm_SpriteDir + k] = (ram[wm_SpriteSpeedX + k] & 0x80) ? 1 : 0;
                }
        if (mario_unsupported) bad = NFF;
        for (k = 0; k < NFF && bad < 0; k++) {
            int a = ffields[k].adr;
            if (ram[a] != orc(i, a) || (ffields[k].w == 2 && ram[a + 1] != orc(i, a + 1))) bad = k;
        }
        if (bad < 0) { cur++; continue; }
        cause[bad]++;
        resync++;
        if (shown++ < 25)
            printf("  frame %u: tras %ld frames, difiere %s%s\n", frame_of(i), cur,
                   bad < NFF ? ffields[bad].name : "(sin portar)",
                   orc(i, wm_IsOnSolidSpr) ? "  [sobre un sprite]" : "");
        if (cur > longest) longest = cur;
        cur = 0;
        memcpy(keep, ram, sizeof keep);
        load(i);
        for (k = 0; k < 12; k++)
            if (follow[k]) for (c = 0; c < 11; c++) ram[scmp[c] + k] = keep[scmp[c] + k];
        ram[0x1931] = 0x07;
    }
    if (cur > longest) longest = cur;
    printf("\n[game] frames: %ld  resincronizaciones de Mario: %ld  tramo mas largo: %ld\n",
           frames, resync, longest);
    printf("       Rex seguidos: %ld Rex-frames, exactos %ld\n", rexf, rexok);
    printf("       primer campo distinto:");
    for (k = 0; k < NFF; k++) if (cause[k]) printf(" %s:%ld", ffields[k].name, cause[k]);
    if (cause[NFF]) printf(" sin-portar:%ld", cause[NFF]);
    printf("\n");
    return 0;
}

int main(int argc, char **argv)
{
    const char *path = argc > 1 ? argv[1] : "work/oracle_yi1.bin";
    const char *only = argc > 2 ? argv[2] : NULL;    /* mostrar solo este campo */
    /* marioverify oraculo.bin dump FRAME salida.bin: vuelca el estado
       preparado de ese frame (para player/logicbench.s) */
    unsigned dump_frame = (argc > 4 && !strcmp(argv[2], "dump")) ? (unsigned)atoi(argv[3]) : 0;
    const char *dump_path = argc > 4 ? argv[4] : NULL;
    if (dump_frame) only = "\001";              /* no mostrar fallos */
    FILE *f = fopen(path, "rb");
    long i, pairs = 0, unsup = 0, skipped = 0;
    long cause[5] = {0, 0, 0, 0, 0};    /* giro, pared/techo, otro, pendiente, sprite solido */
    long ok[NF][2], bad[NF][2], allok[2] = {0, 0}, tot[2] = {0, 0};
    int shown = 0;
    if (!f) { perror(path); return 2; }
    fseek(f, 0, SEEK_END);
    nrec = ftell(f) / REC;
    fseek(f, 0, SEEK_SET);
    db = malloc(nrec * REC);
    if (fread(db, REC, nrec, f) != (size_t)nrec) { fprintf(stderr, "lectura corta\n"); return 2; }
    fclose(f);
    if (only && !strcmp(only, "full"))
        return run_full(argc > 3 ? argv[3] : "work/yi1_map16.bin",
                        argc > 4 ? argv[4] : NULL, 1);
    if (only && !strcmp(only, "game"))
        return run_game(argc > 3 ? argv[3]
                        : "../smw-src-master/project/mw_e10/levels/data/world_1/1/spr.lv",
                        "work/yi1_map16.bin");
    if (only && !strcmp(only, "sprloop"))
        return run_sprloop(argc > 3 ? argv[3]
                           : "../smw-src-master/project/mw_e10/levels/data/world_1/1/spr.lv",
                           "work/yi1_map16.bin");
    if (only && !strcmp(only, "sprload"))
        return run_sprload(argc > 3 ? argv[3]
                           : "../smw-src-master/project/mw_e10/levels/data/world_1/1/spr.lv");
    if (only && !strcmp(only, "loop"))
        return run_loop(argc > 3 ? argv[3] : "work/yi1_map16.bin");
#ifdef NOOAM
    if (only && !strcmp(only, "mspr"))
        return run_mspr(argc > 3 ? argv[3] : "work/oracle_yi1_oam.bin",
                        argc > 4 ? argv[4] : "work/cc/gfx32.bin");
#endif
    if (only && !strcmp(only, "gfx"))
        return run_gfx(argc > 3 ? argv[3] : "work/oracle_yi1_oam.bin");
    if (only && !strcmp(only, "fulldump") && argc > 4) {
        fdump_frame = (unsigned)atoi(argv[3]);
        fdump_path = argv[4];
        return run_full("work/yi1_map16.bin", NULL, 0);
    }
    memset(ok, 0, sizeof ok);
    memset(bad, 0, sizeof bad);

    for (i = 0; i + 1 < nrec; i++) {
        long j = i + 1;
        int k, air, all = 1;
        if (frame_of(j) != frame_of(i) + 1) continue;
        if (db[i * REC + 4] != 0x29 || db[j * REC + 4] != 0x29) continue;
        /* la fisica normal (ResetAni) solo corre con $71 = 0 y sin sprites
           bloqueados ($9D): muerte, tuberias, crecer, mensajes... no */
        if (orc(j, wm_MarioAnimation) || orc(i, wm_MarioAnimation)
            || orc(j, wm_SpritesLocked)) { skipped++; continue; }
        pairs++;
        load(i);
        take(j, 0x13); take(j, 0x14);
        for (k = 0x15; k <= 0x18; k++) take(j, k);
        take(j, wm_MarioObjStatus);
        take(j, wm_OnSlopeTypeA); take(j, wm_OnSlopeTypeB);
        take(j, wm_IsOnGround); take(j, wm_IsOnSolidSpr);
        for (k = 0; k < 4; k++) take(j, wm_MarioXPos + k);
        take(j, wm_SpritesLocked);
        if (orc(j, wm_IsFlying) == 0) ram[wm_IsFlying] = 0;
        /* la colision (8b) pone la velocidad vertical a 0 al estar apoyado
           ($77 bit 2 = bloqueado abajo) antes de que D7E4 sume gravedad */
        if (orc(j, wm_MarioObjStatus) & 0x04) ram[wm_MarioSpeedY] = 0;
        /* aterrizar borra el giro (colision, 8b) */
        if (orc(i, wm_IsFlying) && !orc(j, wm_IsFlying)) ram[wm_IsSpinJump] = 0;
        /* caer de un borde sin saltar: la colision marca "cayendo" ($0B) y
           D7E4 lo pasa a $24; si hay salto, la colision todavia lo ve en el
           suelo y es D5F2 quien pone $0B/$0C */
        if (!orc(i, wm_IsFlying) && orc(j, wm_IsFlying)
            && !((orc(j, wm_JoyFrameA) | orc(j, wm_JoyFrameB)) & 0x80))
            ram[wm_IsFlying] = 0x0B;

        if (dump_frame && frame_of(j) == dump_frame) {
            /* estado ya preparado (hibrido) para el banco de la Amiga:
               $0000-$00FF y $13C0-$14FF, 576 bytes */
            FILE *o = fopen(dump_path, "wb");
            fwrite(ram, 1, 256, o);
            fwrite(ram + 0x13C0, 1, 320, o);
            fclose(o);
            printf("estado del frame %u -> %s\n", dump_frame, dump_path);
        }
        mario_D5F2();
        if (!mario_unsupported) mario_D062();
        if (!mario_unsupported) mario_D7E4();
        if (mario_unsupported) { unsup++; continue; }

        air = orc(i, wm_IsFlying) != 0 && orc(j, wm_IsFlying) != 0;
        int other = !orc(j, wm_IsSpinJump) && !(orc(j, wm_MarioObjStatus) & 0x0B)
                    && !orc(j, wm_OnSlopeTypeA) && !orc(i, wm_OnSlopeTypeA)
                    && !orc(j, wm_IsOnSolidSpr) && !orc(i, wm_IsOnSolidSpr);
        int want = !only || (strcmp(only, "otros") == 0 ? other : 1);
        tot[air]++;
        for (k = 0; k < NF; k++) {
            int a = fields[k].adr, m;
            m = ram[a] == orc(j, a) && (fields[k].w == 1 || ram[a + 1] == orc(j, a + 1));
            if (m) ok[k][air]++; else { bad[k][air]++; all = 0; }
            if (!m && shown < 40 && want
                && (!only || !strcmp(only, "otros") || strstr(fields[k].name, only))) {
                shown++;
                printf("  frame %u (%s) %-18s port %02X%02X oraculo %02X%02X | vx %02X vy %02X "
                       "joy %02X/%02X %02X/%02X vuela %02X->%02X bloq %02X giro %02X\n",
                       frame_of(j), air ? "aire" : "suelo", fields[k].name,
                       fields[k].w == 2 ? ram[a + 1] : 0, ram[a],
                       fields[k].w == 2 ? orc(j, a + 1) : 0, orc(j, a),
                       orc(i, wm_MarioSpeedX), orc(i, wm_MarioSpeedY),
                       orc(j, 0x15), orc(j, 0x16), orc(j, 0x17), orc(j, 0x18),
                       orc(i, wm_IsFlying), orc(j, wm_IsFlying), orc(j, wm_MarioObjStatus),
                       orc(j, wm_IsSpinJump));
            }
        }
        allok[air] += all;
        if (!all) {
            if (orc(j, wm_IsSpinJump)) cause[0]++;
            else if (orc(j, wm_MarioObjStatus) & 0x0B) cause[1]++;   /* der/izq/techo */
            else if (orc(j, wm_OnSlopeTypeA) || orc(i, wm_OnSlopeTypeA)) cause[3]++;
            else if (orc(j, wm_IsOnSolidSpr) || orc(i, wm_IsOnSolidSpr)) cause[4]++;
            else cause[2]++;
        }
    }
    printf("\npares de frames seguidos en YI1: %ld (sin portar: %ld; sin fisica normal: %ld)\n",
           pairs, unsup, skipped);
    printf("frames con algun fallo: %ld en giro (animacion, CODE_00CEB1), %ld contra pared/techo "
           "(colision, 8b), %ld en pendiente (8c), %ld sobre un sprite (etapa 9), %ld otros\n",
           cause[0], cause[1], cause[3], cause[4], cause[2]);
    printf("%-20s %18s %18s\n", "campo", "en el aire", "en el suelo");
    for (int k = 0; k < NF; k++)
        printf("%-20s %8ld/%-8ld  %8ld/%-8ld\n", fields[k].name,
               ok[k][1], ok[k][1] + bad[k][1], ok[k][0], ok[k][0] + bad[k][0]);
    printf("%-20s %8ld/%-8ld  %8ld/%-8ld\n", "TODOS los campos", allok[1], tot[1], allok[0], tot[0]);
    return 0;
}
