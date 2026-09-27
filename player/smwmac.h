/*
 * smwmac.h - acceso a la RAM y a la ROM de la SNES desde el C del port
 * (compartido por mario.c y mcoll.c). Ver mario.h.
 */
#ifndef SMWMAC_H
#define SMWMAC_H

#define R8(a)       (ram[(a)])
#define W8(a, v)    (ram[(a)] = (u8)(v))
#define R16(a)      ((u16)(ram[(a)] | (ram[(a) + 1] << 8)))
#define W16(a, v)   do { u16 w_ = (u16)(v); ram[(a)] = (u8)w_; ram[(a) + 1] = (u8)(w_ >> 8); } while (0)
#define T8(a)       (rom00[(a) - ROM00_BASE])
#define T16(a)      ((u16)(rom00[(a) - ROM00_BASE] | (rom00[(a) - ROM00_BASE + 1] << 8)))
#define NEG(v)      ((v) & 0x80)

/* T8 con una direccion que solo se conoce en tiempo de ejecucion (un puntero
   leido de ram[], p. ej. R16(wm_SlopeSteepness) + y). Con T8 a secas, el
   vbcc de la PC (2022) pliega el -$C000 en el simbolo ("lea -49152+_rom00,a0",
   absoluto, P36); el (u16) obliga a calcular antes el indice (0..$3FFF, el
   mismo valor) y el acceso queda relativo a a4. */
#define T8V(a)      (rom00[(u16)((a) - ROM00_BASE)])

/* Tabla + indice de 8 bits: T8X(DATA_00E89C, x) == T8(DATA_00E89C + x).
   El puntero (rom00 + desplazamiento POSITIVO) queda relativo a a4 y el
   indice entra en el modo (d8,An,Dn.w): vbcc genera mucho menos codigo que
   con T8(a + x). OJO: no restar ROM00_BASE al puntero (rom00 - $C000):
   vbcc lo convierte en una direccion absoluta (tools/logicbench_build.sh
   lo detecta y para). */
#define T8X(t, i)   ((rom00 + ((t) - ROM00_BASE))[(u8)(i)])
#define T16X(t, i)  ((u16)((rom00 + ((t) - ROM00_BASE))[(u8)(i)] \
                           | ((rom00 + ((t) - ROM00_BASE + 1))[(u8)(i)] << 8)))

/* RAM + indice de 8 bits: RX8(wm_SpriteXLo, x) == R8(wm_SpriteXLo + x).
   Mismo truco que T8X: con R8(t + x) vbcc -O=991 suma en 16 bits, hace
   and.l #$FFFF y lea _ram en cada acceso (~50 ciclos); asi queda un
   lea t+_ram(a4) y el modo (d8,An,Dn.w). El indice tiene que caber en 8 bits. */
#define RX8(t, i)   ((ram + (t))[(u8)(i)])

/* ?Alguno de estos 2 / 4 bytes de ram[] es distinto de 0? En el 68000,
   una sola lectura de 16 / 32 bits (ram[] esta alineada a 4 bytes en el
   binario de vbcc: cnop 0,4; la direccion tiene que ser PAR). En el PC,
   byte a byte (sin problemas de alias ni de alineacion). */
#ifdef __VBCC__
#define NZ16(p)     (*(const unsigned short *)(const void *)(p))
#define NZ32(p)     (*(const unsigned long *)(const void *)(p))
#else
#define NZ16(p)     ((p)[0] | (p)[1])
#define NZ32(p)     ((p)[0] | (p)[1] | (p)[2] | (p)[3])
#endif
#define DEC1(p)     do { if (*(p)) (*(p))--; } while (0)
#define DEC4(p)     do { DEC1(p); DEC1((p) + 1); DEC1((p) + 2); DEC1((p) + 3); } while (0)

#endif
