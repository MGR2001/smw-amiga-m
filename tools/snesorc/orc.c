/*
 * orc.c - generador de oraculos SIN pantalla y SIN usuario (Etapa 8.1).
 *
 * Corre la ROM (U) de Super Mario World en el emulador 65816 que trae
 * snesrev/smw (https://github.com/snesrev/smw, se clona FUERA del repo con
 * tools/snesorc_setup.sh) con una entrada guionizada, y vuelca por frame
 * EXACTAMENTE el registro de tools/oambot.lua (el grabador de smwrecomp):
 * tools/oracle2bin.py y tools/marioverify.c lo leen sin cambios.
 *
 * Este fichero es solo nuestro: se enlaza con los objetos de snesrev (todos
 * menos main.c, opengl.c y glsl_shader.c) y reemplaza a su main.c.
 *
 * El oraculo es la RAM del EMULADOR DE LA ROM ("theirs"), no la del C
 * reimplementado de snesrev ("mine"):
 *   --mode rom    (por defecto) solo la ROM emulada, y ademas se deshacen
 *                 los parches de comportamiento que snesrev le mete a la ROM
 *                 (acarreos forzados, arreglos de bugs de Nintendo): la ROM
 *                 queda igual a la original salvo los ganchos que el marco
 *                 de emulacion necesita (espera de HBlank, subida al APU,
 *                 deteccion de mandos, lectura del APU en el NMI, DMA de 0
 *                 bytes de Mario), que no tocan la RAM de juego.
 *   --mode both   la ROM emulada CON los parches de snesrev, y en paralelo
 *                 el C de snesrev; se cuentan los frames en que difieren
 *                 (manda la ROM). Sirve para comparar los dos.
 *
 * Frame y registro (P35 y la convencion del oraculo de smwrecomp):
 * el registro del frame N es la RAM al terminar la logica del frame N, ANTES
 * del NMI (PC = $8077, justo despues de STZ wm_ExecuteGame: $10 = 0). Los
 * $15-$18 del registro son el joypad que uso esa logica, que el NMI del
 * frame anterior leyo del mando. Por eso la entrada de la linea k del guion
 * aparece en los $15-$18 del registro k+1 (un frame de retraso inherente).
 *
 *   work/snesorc --script tools/snesorc/diagpipe.orc --out work/oracle_diagpipe.txt
 *   work/snesorc --script ... --trace 1          (una linea de estado por frame, a stderr)
 *   work/snesorc --script tools/snesorc/boot_yi1.orc --replay work/oracle_yi1.txt
 *
 * Guion (.orc), una orden por linea, '#' comenta:
 *   N BOTONES           mantiene BOTONES N frames. BOTONES = '-' (nada) o
 *                       nombres unidos con '+': B Y A X L R UP DOWN LEFT
 *                       RIGHT START SELECT, o una palabra SNES cruda $hhhh
 *                       ($4219:$4218, bit 15 = B)
 *   until COND [max N] BOTONES
 *                       mantiene BOTONES hasta que COND se cumpla en el
 *                       registro del frame (error si pasan N frames; 3000
 *                       por defecto)
 *   pulse N BOTONES     N veces: 1 frame apretado, 1 suelto
 *   rec on|off|all      graba: on = solo modo $14 (como oamrec.py), all =
 *                       todos los frames, off = nada (por defecto: on)
 *   poke $ADDR V1 [V2..] escribe bytes (hex) en la WRAM entre dos frames
 *   assert COND         para con error si COND no se cumple
 *   print [texto]       una linea de estado a stderr
 *   include FICHERO     otro guion (ruta relativa al que lo incluye)
 * COND = [w]$ADDR OP VALOR, sin espacios: '$0100==14', 'w$0094>=0700',
 *   '$0072!=0', '$0015&80' (algun bit), '$0015!&80' (ningun bit). Todo en
 *   hex; 'w' = 16 bits little-endian. Se evalua sobre el registro del frame.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include "src/types.h"
#include "src/snes/snes.h"
#include "src/snes/cpu.h"
#include "src/snes/cart.h"
#include "src/snes/ppu.h"
#include "src/common_cpu_infra.h"
#include "src/common_rtl.h"
#include "src/smw_spc_player.h"
#include "assets/smw_assets.h"

/* ---- lo que snesrev espera de su main.c ---- */
bool g_debug_flag;
bool g_new_ppu = true;
bool g_other_image;
int g_got_mismatch_count;
struct SpcPlayer *g_spc_player;
const uint8 *g_asset_ptrs[kNumberOfAssets];
uint32 g_asset_sizes[kNumberOfAssets];

void NORETURN Die(const char *error)
{
    fprintf(stderr, "snesorc: %s\n", error);
    exit(1);
}
void RtlApuLock(void) {}
void RtlApuUnlock(void) {}
MemBlk FindInAssetArray(int asset, int idx)
{
    return FindIndexInMemblk((MemBlk){ g_asset_ptrs[asset], g_asset_sizes[asset] }, idx);
}
const uint8 *FindPtrInAsset(int asset, uint32 addr)
{
    return FindAddrInMemblk((MemBlk){ g_asset_ptrs[asset], g_asset_sizes[asset] }, addr);
}

extern uint8 g_runmode;                 /* common_cpu_infra.c: 0 ambos, 1 C, 2 ROM */
enum { RM_BOTH, RM_MINE, RM_THEIRS };

static void fail(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    fprintf(stderr, "snesorc: ");
    vfprintf(stderr, fmt, ap);
    fprintf(stderr, "\n");
    va_end(ap);
    exit(1);
}

static uint8 *read_file(const char *path, size_t *len)
{
    FILE *f = fopen(path, "rb");
    uint8 *d;
    long n;
    if (!f) fail("no se puede abrir %s", path);
    fseek(f, 0, SEEK_END);
    n = ftell(f);
    fseek(f, 0, SEEK_SET);
    d = malloc(n + 1);
    if (fread(d, 1, n, f) != (size_t)n) fail("lectura corta: %s", path);
    fclose(f);
    d[n] = 0;
    *len = n;
    return d;
}

/* smw_assets.dat (assets/restool.py de snesrev): 88 bytes de cabecera,
   kNumberOfAssets tamanos de 32 bits y los datos alineados a 4 */
static void load_assets(const char *path)
{
    size_t len, i;
    uint8 *d = read_file(path, &len);
    uint32 off;
    if (len < 88 + kNumberOfAssets * 4 || *(uint32 *)(d + 80) != kNumberOfAssets)
        fail("%s no es un smw_assets.dat de esta version de snesrev", path);
    off = 88 + kNumberOfAssets * 4 + *(uint32 *)(d + 84);
    for (i = 0; i < kNumberOfAssets; i++) {
        uint32 sz = *(uint32 *)(d + 88 + i * 4);
        off = (off + 3) & ~3u;
        if ((uint64)off + sz > len) fail("%s: corrupto", path);
        g_asset_sizes[i] = sz;
        g_asset_ptrs[i] = d + off;
        off += sz;
    }
}

/* ------------------------------------------------------------------ */
/* El frame de la ROM emulada, con un gancho antes del NMI.            */

static uint8 pre[0x20000];              /* WRAM antes del NMI = el registro */
static int pre_valid;
static void (*prenmi_hook)(void);

static uint32 cur_pc(void) { return ((uint32)g_snes->cpu->k << 16 | g_snes->cpu->pc) & 0x7fffff; }

static void run_until(uint32 pc1, uint32 pc2)
{
    uint32 last = cur_pc();
    long n;
    for (n = 0; n < 50000000; n++) {
        uint32 a;
        snes_runCpu(g_snes);
        a = cur_pc();
        if (a != last && (a == pc1 || a == pc2)) return;
        last = a;
    }
    fail("la CPU no llega a $%06X (colgada en $%06X)", pc1, cur_pc());
}

static void frame_emulated(void)
{
    Snes *s = g_snes;
    s->vPos = s->hPos = 0;
    s->cpu->nmiWanted = s->cpu->irqWanted = false;
    s->inVblank = s->inNmi = false;
    run_until(0x8077, 0x8077);          /* BRA del bucle principal: logica hecha */
    memcpy(pre, s->ram, sizeof pre);
    pre_valid = 1;
    if (prenmi_hook) prenmi_hook();
    s->cpu->nmiWanted = true;           /* NMI: DMA, mando, etc. */
    run_until(0x82C3, 0x83B9);          /* los dos RTI del NMI */
    snes_runCpu(s);
}

static RtlGameInfo my_info;

/* Ganchos de snesrev que el marco de emulacion necesita (no se deshacen). */
static const uint32 kKeepHooks[] = {
    0x00843B,   /* WaitForHBlank_Entry2 -> RTS (el marco no avanza el haz) */
    0x009A74,   /* deteccion de mandos (lee my_flags) */
    0x00811D, 0x0080F7, 0x0080FB,   /* subidas al APU */
    0x00817E,   /* LDY APUIO2 del NMI (solo musica) */
    0x00A33C, 0x00A358, 0x00A378,   /* DMA de Mario de 0 bytes (solo VRAM) */
};

static uint32 snes_addr(uint32 off) { return (off >> 15) << 16 | 0x8000 | (off & 0x7fff); }

static int keep_hook(uint32 adr)
{
    size_t i;
    for (i = 0; i < sizeof kKeepHooks / sizeof kKeepHooks[0]; i++)
        if (adr == kKeepHooks[i]) return 1;
    return 0;
}

/* Deshace en la ROM emulada todo parche de snesrev salvo kKeepHooks. */
static void restore_rom(const uint8 *orig, size_t len, int verbose)
{
    uint8 *rom = g_snes->cart->rom;
    size_t i, n = g_snes->cart->romSize < len ? g_snes->cart->romSize : len;
    int restored = 0, kept = 0;
    for (i = 0; i < n; i++) {
        if (rom[i] == orig[i]) continue;
        if (keep_hook(snes_addr(i))) { kept++; continue; }
        if (verbose) fprintf(stderr, "  ROM $%06X: %02X -> %02X (original)\n", snes_addr(i), rom[i], orig[i]);
        rom[i] = orig[i];
        restored++;
    }
    fprintf(stderr, "snesorc: ROM original restaurada en %d bytes; %d ganchos del marco se quedan\n",
            restored, kept);
}

/* --replay (mas abajo): la grabacion y el registro sincronizado con 'pre' */
typedef struct { long frame; uint8 mode, tl; uint8 dp[256], w13[320]; char *line; } Rec;
static Rec *rp;
static long nrp, rp_pos = -1;           /* registro de la grabacion sincronizado con 'pre' */

/* ------------------------------------------------------------------ */
/* Registro de oambot.lua                                               */

static FILE *out;
static int rec_mode = 1;                /* 0 off, 1 modo $14, 2 todo */
static long frame_no, recorded;

static unsigned rd(uint32 a) { return pre[a]; }
static unsigned rd16(uint32 a) { return pre[a] | pre[a + 1] << 8; }

static void emit(const uint8 *m, long fno, FILE *f)
{
    int i, k;
    fprintf(f, "%ld %02x %02x %04x %04x %04x %04x %04x %04x %02x ", fno, m[0x100], m[0x13bf],
            m[0x1462] | m[0x1463] << 8, m[0x1464] | m[0x1465] << 8, m[0x1466] | m[0x1467] << 8,
            m[0x1468] | m[0x1469] << 8, m[0x94] | m[0x95] << 8, m[0x96] | m[0x97] << 8, m[0x19]);
    for (i = 0; i < 128; i++) {
        const uint8 *o = m + 0x200 + 4 * i;
        if (o[1] != 0xf0) fprintf(f, "%02x%02x%02x%02x%02x", o[0], o[1], o[2], o[3], m[0x420 + i]);
    }
    fputc(' ', f);
    for (k = 0; k < 12; k++)
        if (m[0x14c8 + k])
            fprintf(f, "%02x%02x%02x%02x%02x%02x%02x", k, m[0x14c8 + k], m[0x9e + k], m[0xe4 + k],
                    m[0x14e0 + k], m[0xd8 + k], m[0x14d4 + k]);
    fputc(' ', f);
    for (i = 0; i < 256; i++) fprintf(f, "%02x", m[i]);
    fputc(' ', f);
    for (i = 0x13c0; i < 0x1500; i++) fprintf(f, "%02x", m[i]);
    fputc('\n', f);
}

static int trace_every;
static void status(const char *txt)
{
    int k;
    fprintf(stderr, "f%-6ld modo %02X tl %02X x %04X y %04X vx %02X vy %02X aire %02X pw %02X cam %04X anim %02X"
            " bloq %02X ow %04X,%04X joy %02X%02X |",
            frame_no, rd(0x100), rd(0x13bf), rd16(0x94), rd16(0x96), rd(0x7b), rd(0x7d), rd(0x72), rd(0x19),
            rd16(0x1a), rd(0x71), rd(0x9d), rd16(0x1f17), rd16(0x1f19), rd(0x15), rd(0x17));
    for (k = 0; k < 12; k++)                        /* sprites: numero:estado@x,y */
        if (rd(0x14c8 + k))
            fprintf(stderr, " %02X:%X@%04X,%04X", rd(0x9e + k), rd(0x14c8 + k),
                    rd(0xe4 + k) | rd(0x14e0 + k) << 8, rd(0xd8 + k) | rd(0x14d4 + k) << 8);
    fprintf(stderr, " %s\n", txt ? txt : "");
}

/* ------------------------------------------------------------------ */
/* Un frame con la entrada 'snes' (palabra SNES: bit 15 = B ... bit 4 = R) */

static long mismatch_frames;

static uint16 swap16bits(uint16 x)
{
    uint16 r = 0;
    int i;
    for (i = 0; i < 16; i++, x >>= 1) r = (uint16)(r << 1 | (x & 1));
    return r;
}

static void step(uint16 snes)
{
    /* RtlRunFrame quiere los botones en el orden de LakeSnes (bit 0 = B);
       el bit 30 dice que el mando 1 esta enchufado */
    uint32 in = swap16bits(snes) & 0xfff;
    g_got_mismatch_count = 1;           /* != 0: snesrev no guarda instantaneas de bugs */
    pre_valid = 0;
    RtlRunFrame(in | 1u << 30);
    if (g_got_mismatch_count) mismatch_frames++;
    if (!pre_valid) fail("el frame %ld no paso por $8077", frame_no);
    frame_no++;
    if (out && (rec_mode == 2 || (rec_mode == 1 && rd(0x100) == 0x14))) {
        emit(pre, rp_pos >= 0 ? rp[rp_pos].frame : frame_no, out);
        recorded++;
    }
    if (trace_every && frame_no % trace_every == 0) status(NULL);
}

/* ------------------------------------------------------------------ */
/* Guion                                                               */

static const struct { const char *name; uint16 bit; } kButtons[] = {
    {"B", 0x8000}, {"Y", 0x4000}, {"SELECT", 0x2000}, {"START", 0x1000},
    {"UP", 0x0800}, {"DOWN", 0x0400}, {"LEFT", 0x0200}, {"RIGHT", 0x0100},
    {"A", 0x0080}, {"X", 0x0040}, {"L", 0x0020}, {"R", 0x0010},
};

static const char *cur_file;
static int cur_line;
#define SFAIL(...) do { fprintf(stderr, "%s:%d: ", cur_file, cur_line); fail(__VA_ARGS__); } while (0)

static uint16 parse_buttons(char *s)
{
    uint16 v = 0;
    char *t;
    if (!strcmp(s, "-")) return 0;
    if (s[0] == '$') return (uint16)strtoul(s + 1, NULL, 16);
    for (t = strtok(s, "+"); t; t = strtok(NULL, "+")) {
        size_t i;
        for (i = 0; i < sizeof kButtons / sizeof kButtons[0]; i++)
            if (!strcasecmp(t, kButtons[i].name)) { v |= kButtons[i].bit; break; }
        if (i == sizeof kButtons / sizeof kButtons[0]) SFAIL("boton desconocido '%s'", t);
    }
    return v;
}

typedef struct { uint32 adr; int w; char op[3]; unsigned val; } Cond;

static Cond parse_cond(const char *s)
{
    Cond c;
    const char *p = s;
    char *e;
    memset(&c, 0, sizeof c);
    if (*p == 'w' || *p == 'W') { c.w = 1; p++; }
    if (*p != '$') SFAIL("condicion '%s': falta $direccion", s);
    c.adr = (uint32)strtoul(p + 1, &e, 16);
    p = e;
    if (!strncmp(p, "==", 2) || !strncmp(p, "!=", 2) || !strncmp(p, ">=", 2) || !strncmp(p, "<=", 2)
        || !strncmp(p, "!&", 2)) { memcpy(c.op, p, 2); p += 2; }
    else if (*p == '<' || *p == '>' || *p == '&') { c.op[0] = *p++; }
    else SFAIL("condicion '%s': operador", s);
    if (*p == '$') p++;
    c.val = (unsigned)strtoul(p, &e, 16);
    if (*e) SFAIL("condicion '%s': valor", s);
    if (c.adr >= sizeof pre) SFAIL("direccion fuera de la WRAM");
    return c;
}

static int eval_cond(const Cond *c)
{
    unsigned v = c->w ? rd16(c->adr) : rd(c->adr);
    if (!strcmp(c->op, "==")) return v == c->val;
    if (!strcmp(c->op, "!=")) return v != c->val;
    if (!strcmp(c->op, ">=")) return v >= c->val;
    if (!strcmp(c->op, "<=")) return v <= c->val;
    if (!strcmp(c->op, "<")) return v < c->val;
    if (!strcmp(c->op, ">")) return v > c->val;
    if (!strcmp(c->op, "&")) return (v & c->val) != 0;
    if (!strcmp(c->op, "!&")) return (v & c->val) == 0;
    return 0;
}

static void run_script(const char *path, int depth)
{
    size_t len;
    char *text, *line, *save = NULL;
    const char *pf = cur_file;
    int pl = cur_line;
    if (depth > 8) fail("include demasiado profundo");
    text = (char *)read_file(path, &len);
    cur_file = path;
    cur_line = 0;
    for (line = strtok_r(text, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        char *tok[16], *c, *sv2 = NULL;
        int nt = 0;
        cur_line++;
        /* strtok_r salta lineas vacias: recontar */
        {
            char *q;
            int nl = 0;
            for (q = text; q < line; q++) if (*q == '\n' || *q == 0) nl++;
            cur_line = nl + 1;
        }
        if ((c = strchr(line, '#'))) *c = 0;
        for (c = strtok_r(line, " \t\r", &sv2); c && nt < 16; c = strtok_r(NULL, " \t\r", &sv2)) tok[nt++] = c;
        if (!nt) continue;
        if (!strcmp(tok[0], "rec")) {
            if (nt < 2) SFAIL("rec on|off|all");
            rec_mode = !strcmp(tok[1], "off") ? 0 : !strcmp(tok[1], "all") ? 2 : 1;
        } else if (!strcmp(tok[0], "include")) {
            char buf[1024];
            const char *slash = strrchr(path, '/');
            if (nt < 2) SFAIL("include FICHERO");
            if (tok[1][0] != '/' && slash)
                snprintf(buf, sizeof buf, "%.*s/%s", (int)(slash - path), path, tok[1]);
            else
                snprintf(buf, sizeof buf, "%s", tok[1]);
            run_script(strdup(buf), depth + 1);
            cur_file = path;
        } else if (!strcmp(tok[0], "poke")) {
            uint32 a;
            int i;
            if (nt < 3 || tok[1][0] != '$') SFAIL("poke $ADDR V1 [V2...]");
            a = (uint32)strtoul(tok[1] + 1, NULL, 16);
            for (i = 2; i < nt; i++) g_ram[(a + i - 2) & 0x1ffff] = (uint8)strtoul(tok[i][0] == '$' ? tok[i] + 1 : tok[i], NULL, 16);
        } else if (!strcmp(tok[0], "assert")) {
            Cond cd;
            if (nt < 2) SFAIL("assert COND");
            cd = parse_cond(tok[1]);
            if (!eval_cond(&cd)) { status("<- assert"); SFAIL("assert %s: falla en el frame %ld", tok[1], frame_no); }
        } else if (!strcmp(tok[0], "print")) {
            char buf[256] = "";
            int i;
            for (i = 1; i < nt; i++) { strncat(buf, tok[i], 200); strncat(buf, " ", 2); }
            status(buf);
        } else if (!strcmp(tok[0], "until")) {
            Cond cd;
            long max = 3000, i;
            uint16 b;
            int k = 2;
            if (nt < 3) SFAIL("until COND [max N] BOTONES");
            cd = parse_cond(tok[1]);
            if (!strcmp(tok[2], "max")) { if (nt < 5) SFAIL("until COND max N BOTONES"); max = atol(tok[3]); k = 4; }
            b = parse_buttons(tok[k]);
            for (i = 0;; i++) {
                if (i >= max) { status("<- until"); SFAIL("until %s: no se cumplio en %ld frames", tok[1], max); }
                step(b);
                if (eval_cond(&cd)) break;
            }
        } else if (!strcmp(tok[0], "pulse")) {
            long n, i;
            uint16 b;
            if (nt < 3) SFAIL("pulse N BOTONES");
            n = atol(tok[1]);
            b = parse_buttons(tok[2]);
            for (i = 0; i < n; i++) { step(b); step(0); }
        } else if (tok[0][0] >= '0' && tok[0][0] <= '9') {
            long n = atol(tok[0]), i;
            uint16 b;
            if (nt < 2) SFAIL("N BOTONES");
            b = parse_buttons(tok[1]);
            for (i = 0; i < n; i++) step(b);
        } else {
            SFAIL("orden desconocida '%s'", tok[0]);
        }
    }
    cur_file = pf;
    cur_line = pl;
}

/* ------------------------------------------------------------------ */
/* --replay: reproduce una grabacion de smwrecomp (oamrec.py) desde el
   primer frame de su primer tramo del nivel.  El guion (--script) tiene
   que dejar el juego ANTES de entrar al nivel; en el primer frame del
   nivel (modo $14, translevel = el de la grabacion) se copian encima
   $0000-$00FF y $13C0-$14FF de la grabacion (frames, RNG, todo lo que
   depende de la historia) y desde ahi se alimenta el joypad grabado y se
   compara cada registro con el grabado. */

static uint8 rp_prev_ap, rp_prev_bp;    /* bytes crudos del mando ($4219, $4218) del frame anterior */
static int rp_sync_tl, rp_seg = 1;

static void load_replay(const char *path)
{
    size_t len;
    char *text = (char *)read_file(path, &len), *line, *save = NULL;
    long cap = 1024;
    rp = malloc(cap * sizeof *rp);
    for (line = strtok_r(text, "\n", &save); line; line = strtok_r(NULL, "\n", &save)) {
        char *f[16], *c, *sv = NULL, *dup = strdup(line);
        int n = 0, i;
        for (c = strtok_r(dup, " ", &sv); c && n < 16; c = strtok_r(NULL, " ", &sv)) f[n++] = c;
        /* los campos vacios (oam o ranuras) se comen: el dp es el penultimo */
        if (n < 12 || strlen(f[n - 2]) != 512 || strlen(f[n - 1]) != 640) { free(dup); continue; }
        if (nrp == cap) { cap *= 2; rp = realloc(rp, cap * sizeof *rp); }
        rp[nrp].frame = atol(f[0]);
        rp[nrp].mode = (uint8)strtoul(f[1], NULL, 16);
        rp[nrp].tl = (uint8)strtoul(f[2], NULL, 16);
        for (i = 0; i < 256; i++) { unsigned v; sscanf(f[n - 2] + 2 * i, "%2x", &v); rp[nrp].dp[i] = (uint8)v; }
        for (i = 0; i < 320; i++) { unsigned v; sscanf(f[n - 1] + 2 * i, "%2x", &v); rp[nrp].w13[i] = (uint8)v; }
        rp[nrp].line = strdup(line);
        nrp++;
        free(dup);
    }
    fprintf(stderr, "snesorc: %ld registros en %s\n", nrp, path);
}

/* bytes crudos del mando que dan exactamente los $15-$18 del registro r,
   sabiendo los del frame anterior (ControllerUpdate, game.s).  $15 bit 7 =
   B | A y bit 6 = Y | X: con A (X) apretado no se sabe B (Y); se elige el
   valor que no inventa un "recien apretado" ni ahora ni en el registro
   siguiente (nx, puede ser NULL). */
static void raw_from_rec(const Rec *pv, const Rec *r, const Rec *nx, uint8 prev_ap, uint8 prev_bp, uint8 *ap, uint8 *bp)
{
    uint8 j15 = r->dp[0x15], j16 = r->dp[0x16], j17 = r->dp[0x17], j18 = r->dp[0x18];
    uint8 a = j15 & 0x3f, b = j17 & 0xf0;
    if (!(j15 | j16 | j17 | j18) && r->dp[0x71] && pv && !pv->dp[0x71]) {
        /* _NoButtons (player.s): en el frame en que empieza una animacion
           la logica borra $15-$18 DESPUES de usarlos (p. ej. al entrar en
           una tuberia).
           Lo apretado de verdad no se grabo: se mantiene lo del frame
           anterior, mas lo que el siguiente tiene apretado y no nuevo */
        a = prev_ap;
        b = prev_bp;
        if (nx) {
            uint8 nnew_a = nx->dp[0x16] & ~(nx->dp[0x18] & 0x40), nnew_b = nx->dp[0x18] & 0xf0;
            uint8 na = (nx->dp[0x15] & 0x3f) | (nx->dp[0x15] & 0xc0 & ~(nx->dp[0x17] & 0xc0));
            uint8 nb = nx->dp[0x17] & 0xf0;
            a = (uint8)((a | (na & ~nnew_a)) & ~nnew_a);
            b = (uint8)((b | (nb & ~nnew_b)) & ~nnew_b);
            /* entrar en una tuberia pide la direccion: se deduce del
               movimiento de Mario en el registro siguiente */
            if (r->dp[0x71] == 6)
                a |= (nx->dp[0x96] | nx->dp[0x97] << 8) > (r->dp[0x96] | r->dp[0x97] << 8) ? 0x04 : 0x08;
            if (r->dp[0x71] == 5)
                a |= (nx->dp[0x94] | nx->dp[0x95] << 8) < (r->dp[0x94] | r->dp[0x95] << 8) ? 0x02 : 0x01;
        }
        *ap = a;
        *bp = b;
        return;
    }
    if (!(b & 0x80)) a |= j15 & 0x80;
    else if (j16 & 0x80) a |= 0x80;                          /* B recien apretado */
    else if ((prev_ap & 0x80) && !(nx && (nx->dp[0x16] & 0x80))) a |= 0x80;   /* sigue apretado */
    if (!(b & 0x40)) a |= j15 & 0x40;
    else if ((j16 & 0x40) && !(j18 & 0x40)) a |= 0x40;       /* Y recien apretado (no X) */
    else if ((prev_ap & 0x40) && !(nx && (nx->dp[0x16] & 0x40) && !(nx->dp[0x18] & 0x40))) a |= 0x40;
    *ap = a;
    *bp = b;
}

static long rp_frames, rp_ok, rp_first_bad = -1, rp_badbytes;
static long rp_bad_at[0x1500];

static void replay_hook(void)
{
    long j;
    uint8 ap, bp;
    if (rp_pos < 0) {
        /* primer frame del nivel en esta corrida */
        long i;
        if (pre[0x100] != 0x14 || pre[0x13bf] != rp_sync_tl) return;
        {
            int seg = 0;
            for (i = 0; i < nrp; i++)
                if (rp[i].mode == 0x14 && rp[i].tl == rp_sync_tl
                    && (i == 0 || rp[i - 1].frame != rp[i].frame - 1 || rp[i - 1].tl != rp_sync_tl)
                    && ++seg == rp_seg) break;
        }
        if (i == nrp) fail("--replay: la grabacion no tiene el tramo %d del translevel %02X", rp_seg, rp_sync_tl);
        rec_mode = 1;                              /* se graba el tramo, con los frames de la grabacion */
        rp_pos = i;
        memcpy(g_snes->ram, rp[i].dp, 256);
        memcpy(g_snes->ram + 0x13c0, rp[i].w13, 320);
        memcpy(pre, g_snes->ram, sizeof pre);
        raw_from_rec(NULL, &rp[i], NULL, rp[i].dp[0x15], rp[i].dp[0x17], &rp_prev_ap, &rp_prev_bp);
        g_snes->ram[0x0daa] = rp_prev_ap;          /* wm_JoyDisP1L: $4219 anterior */
        g_snes->ram[0x0dac] = rp_prev_bp;          /* wm_JoyDisP1H: $4218 anterior */
        fprintf(stderr, "snesorc: sincronizado en el frame %ld con el registro %ld (frame %ld de la grabacion)\n",
                frame_no + 1, i, rp[i].frame);
    } else {
        long k;
        int bad = 0;
        rp_pos++;
        if (rp_pos >= nrp || rp[rp_pos].frame != rp[rp_pos - 1].frame + 1 || rp[rp_pos].tl != rp_sync_tl) {
            rp_pos = -2;                           /* fin del tramo */
            prenmi_hook = NULL;
            rec_mode = 0;
            return;
        }
        rp_frames++;
        for (k = 0; k < 256; k++) if (pre[k] != rp[rp_pos].dp[k]) { bad++; rp_bad_at[k]++; }
        for (k = 0; k < 320; k++) if (pre[0x13c0 + k] != rp[rp_pos].w13[k]) { bad++; rp_bad_at[0x13c0 + k]++; }
        if (!bad) rp_ok++;
        else {
            rp_badbytes += bad;
            if (rp_first_bad < 0) {
                rp_first_bad = rp[rp_pos].frame;
                fprintf(stderr, "snesorc: primer frame distinto: %ld (grabacion) =", rp_first_bad);
                for (k = 0; k < 0x1500; k++) {
                    int v;
                    if (k == 0x100) k = 0x13c0;
                    v = k < 0x100 ? rp[rp_pos].dp[k] : rp[rp_pos].w13[k - 0x13c0];
                    if (pre[k] != v) fprintf(stderr, " $%04lX=%02X/%02X", k, pre[k], v);
                }
                fprintf(stderr, "  (nuestro/grabado)\n");
            }
        }
    }
    /* el NMI de este frame lee el mando que usa el registro siguiente */
    j = rp_pos + 1;
    if (j < nrp && rp[j].frame == rp[rp_pos].frame + 1) {
        raw_from_rec(&rp[rp_pos], &rp[j], j + 1 < nrp && rp[j + 1].frame == rp[j].frame + 1 ? &rp[j + 1] : NULL,
                     rp_prev_ap, rp_prev_bp, &ap, &bp);
        rp_prev_ap = ap;
        rp_prev_bp = bp;
        g_snes->input1_currentState = swap16bits((uint16)(ap << 8 | bp)) & 0xfff;
    }
}

/* ------------------------------------------------------------------ */

static void usage(void)
{
    fprintf(stderr,
        "uso: snesorc --script GUION.orc [--out ORACULO.txt] [--rom smw.sfc] [--assets smw_assets.dat]\n"
        "             [--mode rom|both] [--trace N] [--replay GRABACION.txt [--replay-tl 29] [--replay-seg N]]\n");
    exit(2);
}

int main(int argc, char **argv)
{
    const char *rom_path = "work/smw.sfc", *assets = NULL, *script = NULL, *outp = NULL, *replay = NULL;
    const char *mode = "rom";
    size_t rom_len;
    uint8 *rom;
    int i, verbose = 0;
    char defassets[1024];
    const char *home = getenv("HOME");
    snprintf(defassets, sizeof defassets, "%s/.cache/snesrev-smw/smw_assets.dat", home ? home : ".");
    assets = getenv("SNESORC_ASSETS") ? getenv("SNESORC_ASSETS") : defassets;
    rp_sync_tl = 0x29;
    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--rom") && i + 1 < argc) rom_path = argv[++i];
        else if (!strcmp(argv[i], "--assets") && i + 1 < argc) assets = argv[++i];
        else if (!strcmp(argv[i], "--script") && i + 1 < argc) script = argv[++i];
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) outp = argv[++i];
        else if (!strcmp(argv[i], "--mode") && i + 1 < argc) mode = argv[++i];
        else if (!strcmp(argv[i], "--trace") && i + 1 < argc) trace_every = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--replay") && i + 1 < argc) replay = argv[++i];
        else if (!strcmp(argv[i], "--replay-tl") && i + 1 < argc) rp_sync_tl = (int)strtol(argv[++i], NULL, 16);
        else if (!strcmp(argv[i], "--replay-seg") && i + 1 < argc) rp_seg = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-v")) verbose = 1;
        else usage();
    }
    if (!script) usage();
    if (!strcmp(mode, "rom")) g_runmode = RM_THEIRS;
    else if (!strcmp(mode, "both")) g_runmode = RM_BOTH;
    else usage();

    load_assets(assets);
    rom = read_file(rom_path, &rom_len);
    if (rom_len != 524288) fail("%s: se espera la ROM (U) sin cabecera (512 KB)", rom_path);
    if (!SnesInit(rom, (int)rom_len)) fail("snesrev no pudo cargar la ROM");
    g_spc_player = SmwSpcPlayer_Create();
    g_spc_player->initialize(g_spc_player);
    my_info = *g_rtl_game_info;
    my_info.run_frame_emulated = &frame_emulated;
    g_rtl_game_info = &my_info;
    if (g_runmode == RM_THEIRS) restore_rom(rom, rom_len, verbose);
    memset(g_sram, 0, g_sram_size);     /* SRAM vacia: los tres ficheros nuevos */

    if (outp && !(out = fopen(outp, "w"))) fail("no se puede escribir %s", outp);
    if (replay) {
        load_replay(replay);
        prenmi_hook = replay_hook;
    }
    run_script(script, 0);
    if (replay) {
        if (rp_pos == -1) fail("--replay: el guion no llego al nivel %02X", rp_sync_tl);
        /* seguir hasta que se acabe el tramo grabado */
        while (prenmi_hook) step(0);
        printf("[replay] frames comparados: %ld  identicos (dp + $13C0-$14FF): %ld  primer distinto: %ld\n",
               rp_frames, rp_ok, rp_first_bad);
        if (rp_badbytes) {
            long k;
            printf("         bytes distintos por direccion:");
            for (k = 0; k < 0x1500; k++) if (rp_bad_at[k]) printf(" $%04lX:%ld", k, rp_bad_at[k]);
            printf("\n");
        }
    }
    if (out) fclose(out);
    fprintf(stderr, "snesorc: %ld frames corridos, %ld registros grabados%s%s", frame_no, recorded,
            outp ? " -> " : "", outp ? outp : "");
    if (g_runmode == RM_BOTH) fprintf(stderr, "; frames en que el C de snesrev difiere de la ROM: %ld", mismatch_frames);
    fprintf(stderr, "\n");
    return 0;
}
