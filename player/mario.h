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

extern u8 ram[0x2000];
extern const unsigned char rom00[0x4000];   /* $00:C000-$00:FFFF */

/* Por que una rutina no pudo seguir: camino que todavia no se porto. */
enum {
    MARIO_OK = 0,
    MARIO_UNSUP_CAPE,       /* capa: planeo, giro, picada */
    MARIO_UNSUP_FIRE,       /* flor de fuego: bolas */
    MARIO_UNSUP_YOSHI       /* Yoshi con alas */
};
extern int mario_unsupported;

/* Etapa 8a: velocidad horizontal, salto, gravedad (en el orden de
   CODE_00CD82). */
void mario_D5F2(void);      /* CODE_00D5F2: velocidad X, agacharse, saltar */
void mario_D062(void);      /* CODE_00D062: capa / fuego */
void mario_D7E4(void);      /* CODE_00D7E4: gravedad, planeo */

#endif
