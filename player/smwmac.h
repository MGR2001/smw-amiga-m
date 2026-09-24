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

#endif
