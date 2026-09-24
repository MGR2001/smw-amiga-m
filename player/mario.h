/*
 * mario.h - fisica de Mario portada de player.s (SMW U), etapa 8.
 *
 * Primero exacta, despues rapida: las rutinas trabajan sobre ram[], que
 * imita la WRAM baja de la SNES ($0000-$1FFF) con las MISMAS direcciones
 * (gen/smwram.h), y leen las tablas de la ROM por su direccion SNES
 * (gen/smwtab.h, gen/smwrom00.c). Los accesos de 16 bits se arman byte a
 * byte en little-endian, asi que el mismo C da lo mismo en el PC y en el
 * 68000. Se verifica bit a bit contra el oraculo grabado en smwrecomp
 * (tools/marioverify.c).
 */
#ifndef MARIO_H
#define MARIO_H

typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef signed short s16;

extern u8 ram[0x2000];
extern const unsigned char rom00[0x4000];   /* $00:C000-$00:FFFF */

/* Por que una rutina no pudo seguir: camino que todavia no se porto. */
enum {
    MARIO_OK = 0,
    MARIO_UNSUP_CAPE,       /* capa: planeo, giro, picada */
    MARIO_UNSUP_FIRE,       /* flor de fuego: bolas */
    MARIO_UNSUP_YOSHI,      /* Yoshi con alas */
    MARIO_UNSUP_LAYER,      /* capa 2 interactiva, nivel vertical, salida lateral */
    MARIO_UNSUP_TILE,       /* bloques especiales (interruptor de palacio, bloque para tirar...) */
    MARIO_UNSUP_HURT,       /* un bloque lo dania (munchers, espinas) */
    MARIO_UNSUP_PIPE,       /* entra en una tuberia o una puerta */
    MARIO_UNSUP_WATER,      /* agua */
    MARIO_UNSUP_CLIMB,      /* trepar */
    MARIO_UNSUP_WALL        /* correr por la pared */
};
extern int mario_unsupported;

/* Etapa 8b (mcoll.c): el mapa de la capa 1 con el layout de la WRAM
   ($7E:C800 / $7F:C800, pantalla s en s*$1B0) y lo que paso en el frame
   que no mueve a Mario (para el verificador). */
extern u8 *map16_lo, *map16_hi;
enum {
    MEV_TILE = 1, MEV_COIN = 2, MEV_BOUNCE = 4, MEV_DEATH = 8, MEV_HURT = 16,
    MEV_PIPE = 32, MEV_MIDWAY = 64, MEV_1UP = 128, MEV_POUND = 256,
    MEV_SWITCH = 512, MEV_SPRITE = 1024
};
extern unsigned mario_events;

/* Etapa 8a: velocidad horizontal, salto, gravedad (en el orden de
   CODE_00CD82). */
void mario_D5F2(void);      /* CODE_00D5F2: velocidad X, agacharse, saltar */
void mario_D062(void);      /* CODE_00D062: capa / fuego */
void mario_D7E4(void);      /* CODE_00D7E4: gravedad, planeo */

/* Etapa 8b: CODE_00CD24 (movimiento DC2D + colision E92B + F595) y el
   frame entero del jugador (colision + 8a). */
void mario_collide(void);
void blocks_update(void);   /* CODE_02902D: bloques que rebotan (fase de sprites) */

/* manim.c: el frame entero del jugador (CODE_00C500 + ResetAni: colision,
   8a y animacion CODE_00CEB1) */
void mario_player(void);
void mario_CEB1(void);

/* mgfx.c: CODE_00E2BD, graficos de Mario (OAM, MarioScrPosX/Y, DMA) */
void mario_E2BD(void);

/* mcam.c: CODE_00F6DB, la camara (antes que los graficos y la fisica) */
void camera_F6DB(void);

/* manim.c: el principio de CODE_01808C y un frame de nivel entero */
void sprites_begin(void);
void level_frame(void);

/* msprite.c: etapa 9 */
extern const u8 *spr_level;     /* spr.lv del nivel */
extern u8 spr_spawned;          /* ranuras creadas por el cargador en este frame */
void sprite_load_level(void);   /* LoadSprFromLevel */
void sprite_run(u8 x);          /* CODE_0180D2 + HandleSprite de la ranura x (Rex) */
void sprite_tweakers(u8 x);     /* LoadTweakerBytes */

#endif
