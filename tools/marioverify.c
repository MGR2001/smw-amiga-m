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
 *   gcc -O2 -Iplayer -o work/marioverify tools/marioverify.c player/mario.c player/mcoll.c player/manim.c player/mgfx.c player/gen/smwrom00.c
 *   work/marioverify work/oracle_yi1.bin
 *   work/marioverify work/oracle_yi1.bin full [work/yi1_map16.bin [CAMPO]]   (8b)
 *   work/marioverify work/oracle_yi1.bin fulldump FRAME salida.bin   (estado para logicbench)
 *   work/marioverify work/oracle_yi1.bin gfx [work/oracle_yi1_oam.bin]   (graficos de Mario)
 *   FULL_FRAME=N work/mvtrace ... full   (un solo frame; mvtrace = -DMCOLL_TRACE)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mario.h"
#include "gen/smwram.h"

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
