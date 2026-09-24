# Port-demo de Super Mario World → Commodore Amiga 500 (1 MB / A501)

Documento de viabilidad y plan técnico. Fecha: 22/09/2026.

> **Documento histórico — manda `AGENTS.md`.** Revisado el 2026-09-22; estas
> partes están superadas o eran incorrectas:
>
> - **§3.2 Scroll: la premisa es falsa.** El OCS sí tiene scroll horizontal
>   fino por hardware (`BPLCON1`, 0-15 px) y `BPLxPT` pone el grueso. Mover la
>   imagen 1 px no exige re-blitear el playfield: solo se blitea la columna de
>   bloques nueva. Las opciones A/B/C y el "16 colores a 25 Hz" salen de ese
>   error. Ver `AGENTS.md` R5 y D1 (reabierta).
> - **§3.3 Sprites:** los sprites de hardware acoplados dan 15 colores, no 3.
> - **§3.4 RAM:** el presupuesto no incluye el segundo buffer para los bobs.
> - **§6 / §7:** las etapas 2 y 3 están hechas, y la capa 1 del nivel está 1:1
>   con la SNES (`AGENTS.md` §5c).
> - **§8 Toolchain:** el proyecto usa Kickstart **1.2**, bootblock propio con
>   lectura cruda y WinUAE (`AGENTS.md` §6).
> - **§4 Alcance / §7 etapa 6:** Goomba y Koopa Troopa **no aparecen** en
>   Yoshi's Island 1. Los enemigos reales son Rex (×18), Banzai Bill (×4),
>   Jumping Piranha (×3) y otros sueltos (`AGENTS.md` D3).
> - **§7 Plan por etapas:** reemplazado por el roadmap de `AGENTS.md` §10
>   (primero la prueba de viabilidad en el hardware, después la fidelidad).
> - El nivel de fidelidad objetivo es **lo más cercano posible a 1:1**
>   (pedido del usuario), no las cifras de la tabla del §0.

---

## 0. Veredicto rápido

**Un port-demo de UN nivel es viable. Un port completo no lo es.**

La Amiga 500 no puede reproducir SMW tal cual: la SNES tiene *hardware* que la
Amiga no tiene (scroll por hardware, 256 colores en pantalla, tilemaps, 128
sprites, 8 voces de audio). Pero la Amiga tiene algo que la SNES no tiene: un
**blitter** muy potente y un **copper** que reescribe registros por scanline.

La estrategia correcta no es *emular* la SNES, sino **reescribir el juego como
un juego de Amiga**, usando los datos del decompilado (gráficos, paletas,
física, niveles) como especificación. Es exactamente lo que hicieron los ports
de `snesrev` para PC, pero con muchas más limitaciones de hardware.

Nivel de fidelidad alcanzable en el demo:

| Aspecto | Fidelidad posible |
|---|---|
| Geometría del nivel, colisiones, layout | ~100% (son datos) |
| Física de Mario | ~95% (las tablas son extraíbles) |
| Gráficos (formas) | ~100% |
| Colores | ~70% (reducción 256 → 32) |
| Scroll | 80-100% según el compromiso que elijas |
| Sonido | ~60% (8 voces → 4 canales) |
| Velocidad | 25-50 Hz según el compromiso |

---

## 1. Qué material tienes realmente (corrección importante)

De los tres proyectos que tienes, **solo uno trae código fuente**:

| Carpeta | Qué es | ¿Sirve? |
|---|---|---|
| `smw-src-master/` | Desensamblado binario-exacto de GalaXyHaXz (WLA-DX, 65816) | **SÍ — es tu activo principal** |
| `smwre/` | `snesrev/smw`: reimplementación en C | Solo el `.exe`. **Sin fuentes** |
| `smwrecomp/` | `mstan/SuperMarioWorldRecomp`: recompilación estática a C | Solo el `.exe`. **Sin fuentes** |

Los dos últimos son binarios de Windows ya compilados; el C generado está
fuera del repo (`.gitignore`). No puedes reutilizar su código directamente —
tendrías que clonar los repositorios de GitHub por separado.

**Lo que sí tienes, y es mucho:**

```
smw-src-master/project/mw_e10/
  player.s            5.702 líneas   física de Mario, power-ups, animaciones
  game.s              5.557 líneas   bucle principal, game modes, HUD
  sprite_1-main.s     6.019 líneas   motor de sprites, spawner
  sprite_2-clus.s     6.932 líneas   enemigos (parte 1)
  sprite_3-1.s        7.056 líneas   enemigos (parte 2)
  lv_scroll.s         1.797 líneas   motor de scroll de nivel
  lv_read.s           1.645 líneas   carga de niveles
  map.s               3.007 líneas   overworld
  tiles.s             3.403 líneas   colisiones con el mapa de tiles
  ------------------------------------
  TOTAL              82.042 líneas de ensamblador 65816

  graphics/*.lz2      52 ficheros   gráficos comprimidos (LC_LZ2)
  palettes/*.a        paletas BGR555 de 15 bits
  levels/data/        niveles YA DESCOMPRIMIDOS  (.lv, formato de objetos)
  sound/              motor SPC700 + secuencias musicales + muestras BRR
  document/           ram_map.txt, graphics.txt, bug_fixes.txt...
```

Dos detalles que **cambian el plan a mejor**:

1. **Los niveles están descomprimidos** (`levels/data/world_1/1/obj.lv`, etc.).
   No hay que escribir un descompresor del formato de niveles.
2. **Las tablas de física están en claro** en `player.s` (`MarioAccel` en la
   línea 1757, tabla de velocidades máximas en la 1823, etc.), en punto fijo
   8.8. Ejemplo real:

   ```
   ; velocidades maximas (unidades de 1/16 px por frame)
   DATA_00D535:  .DB -20,20,-36,36,-36,36,-48,48   ; andar / correr / planear
   MarioAccel:   .DB 128,-2,128,-2,128,1,128,1     ; aceleracion por estado
   ```

---

## 2. Comparativa de hardware

| | SNES (SMW) | Amiga 500 (OCS/ECS) |
|---|---|---|
| CPU | 65816 @ 3,58 MHz | **68000 @ 7,09 MHz** ← mejor |
| RAM de trabajo | 128 KB WRAM | 512 KB chip + 512 KB slow |
| VRAM | 64 KB dedicada | **comparte** los 512 KB de chip RAM |
| Resolución | 256×224 | 320×256 (PAL) |
| Colores en pantalla | **256** (8 pal. × 16 BG + 8 × 16 spr) | **32** (5 planos) o 64 (EHB) |
| Capas de fondo | 2-3 con scroll hardware | 0 (o 2 en dual-playfield) |
| Scroll | por hardware, sub-píxel, gratis | **NO EXISTE** ← el gran problema |
| Sprites | 128, 32 por línea, 16 colores | 8, 16 px de ancho, 3 colores |
| Blitter | no | **sí, ~3,5 MB/s** ← tu mejor arma |
| Copper | HDMA (limitado) | **reescribe registros por línea** |
| Audio | SPC700 + DSP, 8 voces, BRR | Paula, 4 canales, 8 bits PCM |

---

## 3. Los cinco problemas duros

### 3.1 Color — 256 → 32

SMW usa una paleta de 256 entradas y cada tile elige su paleta de 16. En un
nivel típico se ven ~128 colores simultáneos.

La Amiga OCS da **32 colores** (5 planos). En modo EHB, 64 pero con la mitad
superior forzada a media intensidad.

**Soluciones combinadas:**

1. **Split por copper.** La barra de estado (arriba) usa una paleta distinta
   que el área de juego. Un cambio de paleta en `y=32` te da 32 + 32 = 64
   colores efectivos.
2. **Empaquetado inteligente.** En la práctica un nivel de SMW usa 1-2 paletas
   de BG + 1 de sprites. Asignación realista en 32 colores:
   `BG 12 + sprites 10 + compartidos 6 + HUD 4`.
3. **Reducción por distancia en RGB555.** Genera la paleta óptima por nivel
   offline y cuantiza los tiles. Es un paso de la pipeline, no del runtime.

Coste: los degradados de cielo y las cascadas de color del castillo se verán
"escalonados" en vez de continuos.

### 3.2 Scroll — el problema real

**La Amiga no tiene scroll por hardware.** Los punteros de bitplane
(`BPLxPT`) solo pueden moverse en pasos de **1 palabra = 16 píxeles**. No hay
registro de offset fino.

Consecuencia: para desplazar la imagen 1 píxel hay que **re-blitear el
playfield entero**. Los números:

```
Playfield 256×224, 4 planos
  datos de destino           256×224×4/8 = 28.672 B
  + fuente (A) + máscara (B)  ≈ 3× trafico = 86 KB
  blitter OCS (A+B+D)         ≈ 1 palabra / 4 ciclos = 3,55 MB/s
  ->  ~25 ms por frame completo

Playfield 256×224, 5 planos (32 colores)
  ->  ~107 KB  ->  ~30 ms
```

Un frame a 50 Hz dura 20 ms. **No cabe.** Las tres salidas honestas:

| Opción | Scroll | Color | Frecuencia |
|---|---|---|---|
| **A** | pasos de 16 px (a saltos) | 32 | 50 Hz |
| **B** | 1 px suave | 16 | 25-30 Hz |
| **C** | 1 px suave | 32 | 20-25 Hz |

Además el blitter **comparte el bus con la CPU y con el DMA de audio**, así que
en la práctica pierde ~30-40% del ancho de banda.

Recomendación para el demo: **opción A o B**. La opción B (16 colores a 25-30
Hz) se siente mucho mejor que la A; muchos platformers de Amiga corrían a 25
Hz con scroll suave.

> Nota técnica: existe la técnica de "tiles pre-desplazados" (16 copias de
> cada tile), pero **no resuelve** este problema: si el offset fino cambia,
> TODOS los tiles de la pantalla cambian de desplazamiento, así que igual hay
> que redibujar todo. Solo evita el shift del blitter, no el redibujado.

### 3.3 Sprites

SMW mueve hasta 12+ sprites con 16 colores cada uno. La Amiga tiene 8 sprites
de hardware, de 16 px de ancho y **3 colores**.

**Solución: sprites por software con el blitter.** Es lo que la Amiga hace
mejor. Cada sprite necesita:

- datos planar (4 planos = 16 colores)
- una **máscara** (para el recorte con transparencia)
- 16 versiones pre-desplazadas, o usar el *barrel shifter* del blitter
  (el blitter puede desplazar la fuente 0-15 px en el mismo blit, así que
  basta con leer la fuente una palabra antes)

Presupuesto realista: **10-14 sprites de 16×16 o 16×32 en pantalla**, con
recorte, a 25-30 Hz. Suficiente para Mario + 4-6 enemigos + monedas.

### 3.4 RAM — aquí tienes buenas noticias

Primero, una aclaración importante sobre tu A501:

> Los 512 KB de la expansión 501 están en **$C00000** y son **"slow RAM"**:
> la CPU los ve, pero **el chipset NO**. Agnus/Denise/Paula y el blitter solo
> acceden a los primeros 512 KB (chip RAM). Así que **los gráficos, las
> muestras de audio y las listas de copper tienen que vivir en chip RAM**,
> sí o sí. El slow RAM solo sirve para código y datos de la CPU.

Presupuesto del demo (chip RAM):

| Elemento | Bytes |
|---|---|
| Pantalla 272×224 × 4 planos (con margen de scroll) | 30.464 |
| Barra de estado 320×32 × 2 planos | 2.560 |
| Tileset común (`chr`, 744 tiles × 32 B) | 23.808 |
| Tileset del nivel (`obj-3`, 128 tiles × 32 B) | 4.096 |
| Gráficos de sprites (4 ficheros) + máscaras | ~33.000 |
| Muestras de audio (BRR → PCM 8 bits) | ~64.000 |
| Listas de copper, punteros, tablas | ~10.000 |
| **TOTAL** | **~168 KB de 512 KB** |

**La RAM no es el cuello de botella.** Sobra chip RAM de sobra para un nivel,
y los 512 KB de slow RAM dan para todo el código, los datos del nivel y las
tablas de objetos.

El cuello de botella es el **ancho de banda del blitter** y la **falta de
scroll/color por hardware**.

### 3.5 CPU

68000 @ 7,09 MHz contra 65816 @ 3,58 MHz: el 68000 es bastante más rápido por
instrucción. Pero la SNES delegaba mucho trabajo a hardware que aquí hay que
hacer a mano. Conclusión: la CPU da de sobra para la **lógica** del juego
(física, colisiones, IA de sprites) siempre que **el dibujado lo haga el
blitter** y no la CPU.

### 3.6 Sonido

| | SNES | Amiga |
|---|---|---|
| Voces | 8 | 4 |
| Muestras | BRR (ADPCM 4 bits) | PCM 8 bits firmado |
| Frecuencia | hasta 32 kHz | hasta ~28,8 kHz |

Plan: convertir BRR → PCM 8 bits (la propia decomp trae
`script/samples.bat` para decodificar BRR), y reducir 8 voces a 4 canales.
Reparto típico: **2-3 canales de música + 1-2 de efectos**.

La música de SMW (Koji Kondo) es muy "tracker-friendly"; de hecho ya existen
conversiones de sus temas a MOD. La decomp tiene las secuencias en
`sound/music*.S` y el motor en `sound/engine.S`, así que se puede escribir un
conversor de secuencia SMW → MOD.

---

## 4. Alcance propuesto del demo

**Un nivel jugable: "Yoshi's Island 1" (nivel `105`, `world_1/1/`).**

Incluye:
- Mario con física real (tablas de `player.s`), correr, saltar, giro, daño
- Tilemap real del nivel, con colisiones reales
- 2 tipos de enemigo: **Goomba** y **Koopa Troopa** (de `spr-2.lz2`)
- Scroll horizontal con el compromiso elegido (A o B)
- HUD: monedas, tiempo, vidas, puntuación
- Música del nivel 1 + 2-3 efectos
- Arranque desde disco (ADF booteable, bootblock propio, sin Kickstart)

**Fuera de alcance:** overworld, Yoshi, cape, power-ups más allá de la seta,
jefes, el resto de los 96 niveles.

---

## 5. Arquitectura propuesta

```
                    [ slow RAM $C00000 — 512 KB ]
   código 68000 | datos del nivel | tablas de objetos | buffers de lógica
                    (la CPU sola, el chipset no lo ve)
                              |
   ============== CPU 68000 @ 7,09 MHz ==============
        física | colisiones | IA | máquina de estados
                              |
                    [ chip RAM $000000 — 512 KB ]
     playfield (4-5 planos) | tilesets | sprites+máscaras | audio | copper
                              |
   ============== BLITTER + COPPER + PAULA ==========
        dibujado de tiles | sprites por software | paletas | 4 canales
```

Bucle por frame:
1. Leer joystick → estado de entrada
2. Física de Mario (tablas 8.8) + colisiones contra el tilemap
3. Actualizar sprites y sus colisiones
4. Calcular el delta de scroll → blitear **solo la columna nueva** (o
   redibujar si toca el offset fino)
5. Reconstruir la lista de sprites de hardware + encolar los blits de sprites
6. Copper: cambiar paleta en `y=32` para la barra de estado
7. Esperar al VBL

---

## 6. Pipeline de assets — YA FUNCIONA

Esta etapa está **hecha y verificada**. Herramienta: `tools/smw2amiga.py`.

Lo que hace:
1. **Descompresor LC_LZ2** — verificado: los 52 ficheros de gráficos salen
   con tamaños exactos (3072 B = 128 tiles de 3bpp, etc.)
2. **Decodificador de tiles SNES** 2/3/4 bpp (planar entrelazado)
3. **Codificador planar Amiga** — con **auto-test de ida y vuelta** que pasa
   en los 52 ficheros
4. **Paletas** BGR555 (15 bits) → Amiga 0x0RGB (12 bits), volcadas como
   `dc.w` listas para el copper
5. **Previews PNG** para verificación visual

Resultado: **228,5 KB** de tilesets en formato planar, listos para el blitter.

Verificación visual: `spr-1.lz2` decodificado produce el logo
**"Nintendo Presents"** con la seta, la flor de fuego, la estrella y el
P-switch perfectamente reconocibles. `obj-3.lz2` produce el tileset de suelo
de hierba con las rampas, el arbusto y la tubería fina.

### Lo que falta en la pipeline

- [ ] Parsear el formato de objetos de nivel `.lv` → tilemap de 16×16
- [ ] Resolver el layout **real** de las paletas de SMW (no es un array 8×16;
      está compactado para la rutina de subida de paletas — ver
      `PALETTE_Sprites` que solo tiene 42 palabras)
- [ ] Cuantización de color 256 → 32 por nivel
- [ ] Generación de máscaras de sprite
- [ ] BRR → PCM 8 bits
- [ ] Secuencias SMW → MOD de 4 canales
- [ ] Extraer y transcribir las tablas de física de `player.s`

---

## 7. Plan por etapas

| Etapa | Contenido | Estado |
|---|---|---|
| **1** | Pipeline de assets (gráficos + paletas) | **HECHO** |
| **2** | Parsear niveles `.lv` → tilemap + colisiones | siguiente |
| **3** | Esqueleto Amiga: bootblock, pantalla 4 planos, copper, tileset | |
| **4** | Scroll + dibujado de tiles con el blitter | el más crítico |
| **5** | Mario: física, animación, colisiones con el tilemap | |
| **6** | Sprites por software + Goomba y Koopa | |
| **7** | HUD + paleta partida por copper | |
| **8** | Audio: 4 canales + replayer | |
| **9** | Pulido: transiciones, muerte, meta | |

El hito que decide el proyecto es la **etapa 4**. Si el scroll no rinde,
hay que bajar a la opción C y todo lo demás se recalcula.

---

## 8. Toolchain

**Ensamblador / compilador (host Windows):**
- `vasm` + `vlink` (Motorola 68k) — el estándar actual, muy buen soporte
- `GCC 6 m68k-amigaos` o `VBCC` si prefieres C
- Recomendado: **C para la lógica + ensamblador para blitter/copper**

**Emulador para probar (exactamente tu configuración):**
- **WinUAE** o **FS-UAE**
- Config: `A500` + `512 KB chip` + `512 KB slow (A501)` + `OCS` + `Kickstart 1.3`
- Esto reproduce exactamente tu máquina objetivo

**Distribución:** ADF booteable de 880 KB con bootblock propio (toma el
control de la máquina y te da el 1 MB completo; con Kickstart el SO se come
~256 KB).

**IMPORTANTE — PAL, no NTSC.** SMW son 224 líneas. La Amiga en NTSC da
320×200 → no caben. Necesitas **Amiga PAL** (320×256, 50 Hz).

---

## 9. Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| El scroll no rinde a 50 Hz | **alta** | Ya asumido: opción A (16 px) o B (25 Hz) |
| Los colores quedan irreconocibles | media | Empaquetado manual + split por copper |
| El layout de paletas es complicado | media | Rutina de subida de paletas en `game.s` |
| Muchos sprites saturan el blitter | media | Límite duro de 10-14 sprites |
| 82.000 líneas de 65816 son demasiado | **alta** | No portar el código: reimplementar el nivel 1 |
| La música no cuadra en 4 canales | baja | Ya hay precedentes de SMW en MOD |

---

## 10. Siguientes pasos

1. **Decidir el compromiso de scroll** (opción A, B o C) — condiciona todo.
2. Parsear `levels/data/world_1/1/obj.lv` a un tilemap de 16×16.
3. Montar el esqueleto Amiga y dibujar el tileset estático en pantalla.
4. Implementar el scroll y medir con el emulador.

---

## Nota legal

El decompilado exige poseer el juego original, y tú lo tienes. Un port-demo
personal no es un problema. Lo que **no** debes hacer es distribuir la ROM ni
los assets convertidos (gráficos, música) — eso sí sería redistribución de
material con copyright. Mantenlo como proyecto personal.
