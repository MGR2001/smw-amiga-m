# AGENTS.md — Manual de implementación del port-demo SMW → Amiga 500

> Este fichero define **cómo trabajar** en este proyecto. Es el contrato entre
> quien implementa (persona o agente de IA) y el hardware objetivo.
> Para el *porqué* de cada decisión, lee primero **`PLAN.md`**.

---

## 1. Objetivo

Port-demo **jugable** del nivel **"Yoshi's Island 1"** (nivel `105`,
`world_1/1/`) de Super Mario World a **Commodore Amiga 500 PAL con 1 MB**
(512 KB chip + 512 KB A501).

Entregable: un **ADF booteable** (bootblock propio, KS 1.2) que toma la máquina y muestra el nivel
con Mario controlable, scroll, **los enemigos reales del nivel** (D3), HUD y música.

**Criterio de fidelidad: lo más cercano posible a 1:1 con la SNES.** Una
métrica que pasa no es "hecho" si a la vista hay una diferencia.

**No** es un emulador de SNES. **No** es un port completo del juego.
Es una reimplementación de un nivel usando los datos del decompilado.

---

## 2. Reglas duras (NO negociables)

Violar cualquiera de estas invalida la implementación.

| # | Regla | Consecuencia si se viola |
|---|---|---|
| R1 | **Solo PAL** (320×256, 50 Hz) | En NTSC (320×200) no caben las 224 líneas |
| R2 | **Slow RAM ($C00000) es solo para la CPU** | El chipset NO la ve. Nunca pongas ahí bitplanes, tilesets, muestras de audio ni listas de copper |
| R3 | **Presupuesto de chip RAM: 512 KB** | Todo lo que toque el chipset vive aquí |
| R4 | **Máximo 32 colores** (5 planos). Nunca EHB | EHB fuerza la mitad superior a media intensidad |
| R5 | **El scroll horizontal fino es `BPLCON1` (0-15 px); el grueso, `BPLxPT` (16 px)** | Ver "R5 en detalle": NO hay que re-blitear el playfield para mover 1 px |
| R6 | **Máximo 8 sprites de hardware**, 16 px de ancho, 3 colores | Los sprites de juego van por blitter |
| R7 | **Ancho de banda del blitter ≈ 3,5 MB/s, compartido** con la CPU y el DMA de audio | Asume que solo dispondrás del 60-70% |
| R8 | **Máximo 4 canales de audio** | Música: 2-3 canales. Efectos: 1-2 |
| R9 | **Nunca redistribuir** la ROM ni los assets derivados | Es material con copyright |

### R5 en detalle — CORREGIDO el 2026-09-22

> **La versión anterior de esta regla era falsa** ("el scroll por hardware NO
> existe; para mover 1 px hay que re-blitear el playfield entero"). Todo el
> análisis de D1 (opciones A/B/C, 16 colores a 25 Hz) partía de ahí.

El OCS **sí** tiene scroll horizontal fino por hardware:

```
BPLCON1 ($DFF102)  bits 0-3 = retardo PF1 (0..15 px), bits 4-7 = PF2
BPLxPT             desplazamiento grueso, en palabras (16 px)
DDFSTRT            se adelanta una palabra ($0030 en vez de $0038) para
                   leer los 16 px extra que el retardo va a meter en pantalla
BPLxMOD            = ancho_buffer - ancho_visible - 2

scroll_x:  BPLxPT = base + (scroll_x >> 4) * 2
           BPLCON1 = (15 - (scroll_x & 15)) * $11
```

Todo eso lo escribe el copper una vez por frame: **mover la imagen 1 px cuesta
cero ciclos de blitter.** Lo único que hay que blitear es la **columna de
bloques nueva** que entra por el borde: 14 bloques de 16×16 cada 16 px de
scroll, o sea menos de 1 bloque por frame a velocidad de carrera. Es la técnica
estándar de los plataformas de Amiga a 50 Hz.

Consecuencias que hay que cerrar en la etapa 4, la prueba de viabilidad (no están decididas):

- **Buffer de playfield**: un buffer circular más ancho que la pantalla (p.ej.
  pantalla + 32 px, con la columna nueva escrita dos veces o con reenganche por
  copper), en vez de redibujar.
- **DDFSTRT=$0030 quita el sprite de hardware 7** (el fetch extra usa su slot
  de DMA). Quedan 7 sprites.
- **Sprites de hardware "attached"**: dos sprites acoplados dan **15 colores**
  a 16 px de ancho. Mario puede ir por hardware y liberar al blitter (R6 dice
  "3 colores", que es solo el modo no acoplado).
- **5 planos en lowres no roban ciclos de CPU apreciables** (6 sí). 32 colores
  a 50 Hz es plausible; lo que cuesta blitter son los **bobs** (enemigos) y su
  restauración, con doble buffer.

**D1 se cerró con la etapa 4** (medido en cycle-exact): 1 px / 5 planos /
50 Hz, con scroll + 5 bobs en el 48-68 % del frame. Ver §9, "Etapa 4 —
resultados".

---

## 3. Material de partida

```
C:/Users/JC/Downloads/sma/
├── smw-src-master/          <-- ÚNICO con código fuente. Tu activo principal.
│   ├── project/mw_e10/
│   │   ├── player.s         5.702 líneas  fisica de Mario  <-- tablas clave
│   │   ├── game.s           5.557 líneas  bucle principal, HUD
│   │   ├── sprite_1-main.s  6.019 líneas  motor de sprites
│   │   ├── sprite_2-clus.s  6.932 líneas  enemigos
│   │   ├── sprite_3-1.s     7.056 líneas  enemigos
│   │   ├── lv_scroll.s      1.797 líneas  scroll de nivel
│   │   ├── tiles.s          3.403 líneas  colisiones con tiles
│   │   ├── graphics/*.lz2   52 ficheros   graficos LC_LZ2
│   │   ├── palettes/*.a     paletas BGR555
│   │   └── levels/data/     niveles YA DESCOMPRIMIDOS (.lv)
│   └── document/            ram_map.txt, graphics.txt, bug_fixes.txt
├── smwre/                   solo .exe (snesrev/smw)  - SIN FUENTES
├── smwrecomp/               solo .exe (mstan/...)    - SIN FUENTES
└── port-amiga/              <-- ESTE PROYECTO
    ├── .gitignore           repo git: solo codigo y docs; nada derivado de la ROM (R9)
    ├── AGENTS.md            este fichero
    ├── PLAN.md              analisis de viabilidad (historico, ver su cabecera)
    ├── build.ps1            build / shot / run / clean (bootblock + ADF + WinUAE)
    ├── a500.uae             config CYCLE-EXACT de referencia para medir
    ├── player/              boot.s (bootblock), demo.s (stage 2), exec.i
    ├── tools/               pipeline de assets, nivel y comparacion (ver §5c)
    ├── assets-out/          salida generada
    └── work/                renders, capturas, ADF (todo regenerable)
```

**Aviso:** `smwre/` y `smwrecomp/` son binarios precompilados sin código.
No intentes extraer lógica de ellos. Si los necesitas, clona sus repositorios
(`snesrev/smw`, `mstan/SuperMarioWorldRecomp`) por separado.

**Nivel objetivo:**
```
smw-src-master/project/mw_e10/levels/data/world_1/1/
  obj.lv    283 B   objetos del nivel (formato de 3 bytes)
  obj-1.lv   55 B   objetos secundarios
  spr.lv    104 B   posiciones de sprites/enemigos iniciales
```

---

## 4. Mapa de memoria objetivo

```
$000000 - $07FFFF   CHIP RAM (512 KB)   <- accesible por CPU, blitter,
                                            copper, Denise y Paula
$BFD000 - $BFDFFF   CIA-A
$BFE001 - $BFEFFF   CIA-B
$C00000 - $C7FFFF   SLOW RAM (512 KB)   <- SOLO CPU (expansion A501)
$DC0000             reloj RTC (no existe en A500)
$DFF000 - $DFF1FF   registros de los chips custom
$F80000             Kickstart ROM (no la usaremos: bootblock propio)
```

### Reparto dentro de nuestro programa

**Chip RAM (presupuesto 512 KB, planificado ~168 KB):**

| Bloque | Bytes | Alineación |
|---|---|---|
| Playfield 272×224 × 4 planos (margen de scroll) | 30.464 | 8 bytes |
| Barra de estado 320×32 × 2 planos | 2.560 | 8 bytes |
| Tiles del jugador (`chr`, 744 tiles × 32 B — es Mario, no objetos, P6) | 23.808 | 8 bytes |
| Tileset del nivel (tileset 7 = `obj-2`+`obj-5`+`bg-3`+`obj-3`, 512 tiles; mejor **pre-renderizado a bloques Map16 de 16×16**: la capa 1 usa **80 bloques únicos** (medido) × 128 B a 4 planos) | 10.240 | 8 bytes |
| **Segundo playfield para doble buffer de bobs** (no estaba presupuestado) | 30.464 | 8 bytes |
| Gráficos de sprites + máscaras | ~33.000 | 8 bytes |
| Muestras de audio (PCM 8 bits) | ~64.000 | 2 bytes |
| Listas de copper + punteros + tablas | ~10.000 | 4 bytes |

**Slow RAM (512 KB, uso libre):**

| Bloque | Bytes |
|---|---|
| Código 68000 (hoy corre en chip; moverlo aquí libera chip RAM pero **no lo acelera**, P29) | ~60.000 |
| Tilemap del nivel (16×16 celdas) | ~4.000 |
| Tablas de objetos y sprites | ~8.000 |
| Tablas de física 8.8 | ~2.000 |
| Buffers de descompresión / trabajo | ~32.000 |

**Regla de oro:** si el blitter o el copper tienen que leerlo, va en chip RAM.
Sin excepciones.

---

## 5. Pipeline de assets (etapa 1 — HECHA)

```bash
# entorno
PY="C:/Users/JC/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"

# convertir todo
cd port-amiga/tools
$PY smw2amiga.py --all --selftest --planes 4

# solo algunos ficheros, con 5 planos (32 colores)
$PY smw2amiga.py --gfx chr obj-3 spr-2 --planes 5
```

**Estado verificado (22/09/2026):**
- 52/52 ficheros descomprimidos con tamaños exactos
- Auto-test de ida y vuelta del codificador planar: **pasa en 52/52**
- Salida total: **228,5 KB** de tilesets planares

**Verificación visual obligatoria:** antes de dar por buena cualquier salida,
abre el PNG correspondiente y confirma que las formas son reconocibles.
Referencias que ya sabemos correctas:
- `spr-1.lz2` @ 3bpp → logo **"Nintendo Presents"** + seta + flor + estrella
- `chr.lz2` @ **4bpp** → bloques `?`, monedas, setas, tuberías
- `obj-3.lz2` @ 3bpp → suelo de hierba, rampas, arbusto, tubería fina

### Profundidades de color (tabla autoritativa)

| Ficheros | bpp |
|---|---|
| `chr` | **4** |
| `boss-6` | **4** |
| `gb-1` … `gb-5` | **2** |
| todo lo demás (`spr-*`, `obj-*`, `bg-*`, `map-*`, `boss-1..5`, `cin-*`, `anim`) | **3** |

Fuente: `document/graphics.txt` (IDs en hex) + verificación empírica del
tamaño descomprimido. **`chr.lz2` está mal documentado — es 4bpp, confirmado
renderizando.** La verificación visual (4/3/2 bpp de cada fichero) está en
`work/bpp_matrix.png`: `spr-1`=3bpp da el logo "Nintendo Presents",
`gb-1`=2bpp da el set de caracteres, `chr`=4bpp da la cara de Mario.

### Pendiente en la pipeline

- [x] Resolver el layout real de las paletas → `tools/palette.py`, ver §8b
- [x] Corregir `BPP_TABLE` con verificación visual → `work/bpp_matrix.png`
- [x] Parsear `.lv` → buffer Map16 → `tools/lvparse.py`, ver §5b
- [x] Mapear tileset → ficheros GFX y Map16 → tile + paleta
      → `tools/mklvl.py` + `tools/map16.py`
- [x] Corregir el orden de cuadrantes Map16 y el filtro de cuadrante vacío
      → §5b / P12 / P13
- [x] Comparación 1:1 contra la referencia SNES → §5c
- [x] Herramientas de diagnóstico: `tools/m16sheet.py` (tabla Map16 como
      grilla, `--order row|col`), `tools/tilesheet.py` (tiles crudos de un
      fichero GFX), `tools/quadtest.py` (las dos hipótesis de orden lado a
      lado), `tools/diag_pipe.py` (recortes de tubería)
- [x] Handlers de objeto: 92/92, capa 1 **1:1 con la referencia** (§5c)
- [ ] Capa de fondo del nivel (cielo, pilares, nubes) — etapa 7, **después** de decidir D8
- [x] Cerrar D7 (color de tuberías) → paleta por pantalla, P28
- [ ] Cuantización 128 → 16/32 colores por nivel
- [ ] Generar máscaras de sprite
- [ ] BRR → PCM 8 bits
- [ ] Secuencias SMW → MOD de 4 canales
- [ ] Transcribir las tablas de física de `player.s`

---

## 5b. Formato de nivel (etapa 2 — HECHA)

Referencias: `document/` no trae nada del formato de nivel. La fuente de verdad
es el desensamblado (`lv_read.s`, `tiles.s`) cruzado con la documentación
pública (SnesLab / SMW Speedruns). **Los tres coinciden.**

### Cabecera primaria (5 bytes al principio de Layer 1)

```
byte0 : BBBLLLLL   BBB = paleta de BG (0..7)   LLLLL = nº de pantallas - 1
byte1 : CCCOOOOO   CCC = color de fondo        OOOOO = modo de nivel
byte2 : 3MMMSSSS   3 = prioridad layer 3       MMM = musica   SSSS = gfx sprites
byte3 : TTPPPFFF   TT = tiempo  PPP = pal sprites  FFF = pal de FG
byte4 : IIVVZZZZ   II = item memory  VV = scroll vertical  ZZZZ = tileset
```

Yoshi's Island 1 = `33 40 08 80 27`: 20 pantallas, modo 0, bgcolor 2,
tileset 7, pal FG 0, pal sprites 0.

### Objetos (3 bytes; 4 el "screen exit")

```
byte0 : NBBYYYYY   N = flag "nueva pantalla" (screen++)
                   BB = 2 bits altos del nº de objeto
                   YYYYY = Y (0..31)
byte1 : bbbbXXXX   bbbb = 4 bits bajos del nº de objeto
                   XXXX = X dentro de la pantalla (0..15)
byte2 : SSSSSSSS   settings (objeto estandar)
                   o nº de objeto extendido (si el nº estandar = 0)

nº de objeto (6 bits) = bbbb | (BB << 4)      ; 0..63
    == 0  -> EXTENDIDO  (byte2 = nº 0..255, dispatch en CODE_0DA106)
    != 0  -> ESTANDAR   (byte2 = settings, dispatch en CODE_0DA44B por nº-1)
```

`$FF` como primer byte = fin de datos.

Semántica del byte de settings de los objetos estándar (nibble alto, nibble bajo):

| Objeto | Semántica | | Objeto | Semántica |
|---|---|---|---|---|
| 01-0E | Height, Width | | 14 Ground ledge | Height, Width |
| 0F Vertical pipes | Height, Type | | 15 Midway/Goal | Height, Type |
| 10 Horizontal pipes | Type, Width | | 16 Blue coins | Height, Width |
| 11 Bullet shooter | Height, Unused | | 17 Rope/Clouds | Type, Width |
| 12 Slopes | Height, Type | | 1C Donut bridge | Unused, Width |
| 13 Ledge edges | Height, Type | | 1E Net vertical edge | Height, Type |
|  |  | | 21 Long ground ledge | **Width (byte entero)** |

### Buffer Map16

El nivel se divide en pantallas de **27 filas × 16 columnas** (confirmado por
`tiles.s:_0DA95D`, que avanza el puntero $1B0 = 27*16 bytes al cruzar de
pantalla). Cada pantalla tiene **dos arrays paralelos** de $1B0 bytes:

- `wm_Map16BlkPtrL` → **índice Map16** (9 bits, ver abajo)
- `wm_Map16BlkPtrH` → byte alto del índice

`offset dentro de la pantalla = Y * 16 + X` (row-major).

**IMPORTANTE — el buffer NO guarda tile numbers, guarda índices Map16.**
El nombre (`wm_Map16BlkPtr`) lo dice. Esto es lo que hacía que el primer render
saliera con los colores del gradiente del cielo: usaba el índice como si fuera
un tile number y le aplicaba la paleta 0.

`tiles.s:BlockIsPage1` escribe $00 y `BlockIsPage2` escribe $01 en el **byte
alto** del índice → el índice es `valor | (page << 8)`, de 9 bits (0..511).

### Resolución de un índice Map16

`tools/map16.py`. Cada entrada son **8 bytes = 4 palabras**. Formato de palabra:

```
bits 0-9   tile number de VRAM (0..1023)
bits 10-12 paleta (0..7)
bit  13    prioridad
bit  14    flip X
bit  15    flip Y
```

**ORDEN DE LAS 4 PALABRAS (esto costó un rato): son column-major.**
`word0=TL`, `word1=BL`, `word2=TR`, `word3=BR`. NO es el orden raster.

Confirmado de dos formas independientes:

1. Empírica: `tools/m16sheet.py --order row|col` renderiza la tabla completa.
   Con column-major aparecen objetos coherentes (tuberías, cerros redondeados,
   bloques `?`, monedas, bloques `ON`/`OFF` legibles); con row-major todo sale
   despedazado.
2. En el desensamblado, el expansor Map16→tilemap (`lv_read.s:1161`) escribe
   `word0` y `word2` en la MISMA columna (`TopLeft` y `TopLeft+2`) y `word1` y
   `word3` en la otra (`BottomLeft` y `BottomLeft+2`).

**Cuadrante vacío = la palabra entera `$0000`**, no `tile == 0`. El tile number
0 es un tile válido (p.ej. la boquilla de tubería es el tile 0 a paleta 5,
palabra `$1400`). Hay que comprobar la palabra cruda; para eso
`Map16.get_raw(idx)`.

Ficheros (`project/mw_e10/tilemaps/`): comunes 0x000-0x1FF repartidos en
`000-072`, `100-106`, `111-152`, `16E-1C3`, `1C4-1C7`, `1C8-1EB`, `1EC-1EF`,
`1F0-1FF`; específicos del estilo en `set_N/073-0FF`, `set_N/107-110`,
`set_N/153-16D`. El tileset 7 usa **set_0** (Normal). Los índices ≥ 0x200 son
específicos del tileset y viven en el banco que da `TilesetMAP16Loc`.

### Mapa tileset → GFX → VRAM

`game.s:OBJECTGFXLIST` (13 filas de 8 bytes, indexado con `Y = tileset*4`) da
4 índices de fichero GFX. Cada uno sube **128 tiles** (bucle `LDY #$7F`) a un
bloque de **$800 palabras**:

```
bloque 0  VRAM $0000  tiles   0..127   <- OBJECTGFXLIST[t*4 + 0]
bloque 1  VRAM $0800  tiles 128..255   <- OBJECTGFXLIST[t*4 + 1]
bloque 2  VRAM $1000  tiles 256..383   <- OBJECTGFXLIST[t*4 + 2]
bloque 3  VRAM $1800  tiles 384..511   <- OBJECTGFXLIST[t*4 + 3]
```

(el orden sale invertido porque el bucle hace `LDA OBJECTGFXLIST,Y / STA m4,X`
con `X` de 3 a 0)

Los ficheros GFX son `main.S:99-168` → `GFX00`..`GFX31`. Tileset 7 da
**obj-2 + obj-5 + bg-3 + obj-3**.

### Cómo se renderiza

`tools/mklvl.py` transcribe los handlers de `tiles.s` (rectángulos de índices
Map16), y luego resuelve índice → 4 cuadrantes → tile + paleta.

Primeros handlers transcritos (la lista completa, 92/92, está más abajo):

| Objeto | Handler | Fórmula |
|---|---|---|
| 01-0E | `CODE_0DA8C3` | rect (w+1)×(h+1) de `DATA_0DA8B4[num-1]`; `+256` si `idx>=7` |
| 0F Vertical pipes | `CODE_0DAA26` | `DATA_0DAA12/17` arriba, `$35/$36` cuerpo, `DATA_0DAA1C/21` abajo |
| 13 Ledge edges | `CODE_0DB075` | `DATA_0DB039` / `DATA_0DB048` / `DATA_0DB057` / `DATA_0DB066` |
| 14 Ground ledge | `CODE_0DB1D4` | fila de `$100` + `h+1` filas de `$3F` |
| 21 Long ground ledge | `CODE_0DB1C8` | fila de `$100` (width+1) + 2 filas de `$3F` |
| 3C Arch ledge | `CODE_0DB604` | `DATA_0DB5E8` |
| 3F Bushes | `CODE_0DB5B7` | `DATA_0DB5A8` + n×`DATA_0DB5AD` + `DATA_0DB5B2` |
| ext 10-42 | `CODE_0DA57B` | `DATA_0DA548[type-0x10]`, `+256` si `type-0x10 >= 0x13` |
| ext 8E ! block | `CODE_0DB583` | `$6B` |

Verificación: `work/level_final.png` (5120×432) reproduce Yoshi's Island 1 —
suelo de tierra con hierba, arbustos, colinas, bloques `!` amarillos y
tuberías (boquilla + cuerpo de 2 tiles). Paletas usadas: 2 (suelo), 4, 5
(tuberías), 6 (bloques). Comparado 1:1 contra el mapa de SNESMaps: la
geometría del primer tramo coincide (ver §5c).

### Handlers: 92 de 92 (HECHO 2026-09-22)

Los 12 que faltaban están transcritos y verificados contra la referencia:

| objeto | rutina | forma |
|---|---|---|
| `Yoshi Coin` (ext 0x41) | `CODE_0DB2CA` | `$02D` arriba, `$02E` abajo |
| `Midway/Goal point` (0x15) | `CODE_0DB224` | 3 columnas × (h+1) filas, poste `$25` |
| `Rope/Clouds` (0x17) | `CODE_0DB3BD` | (w+1) bloques en fila, `$105`/`$106` |
| `Midway point rope` (ext 0x46) | `CODE_0DA68E` | `$035` a la izquierda, `$038` en la posición |
| `Arrow sign` (ext 0x86) | `CODE_0DA7E7` | 2×2: `$066`-`$069` |
| `Vert. Pipe/Bone/Log` (0x1F) | `CODE_0DB51F` | columna: `$153`, (h-1)×`$154`, `$155` |
| `Right facing diagonal pipe` (0x39) | `CODE_0DB73F` | `DATA_0DB72F` con página 2 |
| `Left facing diagonal ledge` (0x3A) | `CODE_0DB7AA` | escalera `$1AA`/`$1E2`/`$1F7` + relleno `$03F` |
| `Slopes` (0x12) | `CODE_0DAB3E` | tipo = `(settings & 0x0F) mod 10` → 10 rutinas |
| `3-UP moon` (ext 0x18) | `CODE_0DA57B` | `DATA_0DA548[8]` = `$06E` |
| `Turn block Star` (ext 0x2B) | `CODE_0DA57B` | `DATA_0DA548[0x1B]` = `$11C` |
| `? block (Flower)` (ext 0x30) | `CODE_0DA57B` | `DATA_0DA548[0x20]` = `$121` |

Los extendidos `0x10..0x40` (menos `0x17`) son todos "escribir un bloque"
(`CODE_0DA57B` → `DATA_0DA548[type-0x10]`, página 2 si el índice ≥ `0x13`).

### El cursor de bloques (`tools/mklvl.py: class Cur`)

Los handlers NO escriben en un buffer 2D: mueven un puntero con estas
primitivas, y **la diferencia entre ellas es la forma del objeto**. Modelarlas
mal hace que una tubería diagonal salga como una escalera al revés.

**El estado del cursor son TRES cosas distintas, y hay que modelarlas por
separado** (P25):

| estado | en el ROM | en `Cur` |
|---|---|---|
| puntero a la pantalla (vivo / guardado) | `wm_Map16BlkPtrL` / `m4,m5` | `scr` / `saved` |
| fila y columna **base**, persistentes | `wm_BlockSubScrPos` | `row` / `pcol` |
| columna donde se escribe | registro `Y` | `col` |

| primitiva | rutina | efecto |
|---|---|---|
| `w()` | `CODE_0DA95B` + `_0DA95D` | escribe y avanza `col`; al pasar de la 15 → col 0 de la **pantalla siguiente**, fila base |
| `put()` | `STA [ptr],Y` | escribe **sin** avanzar |
| `down()` | `CODE_0DA97D` | `pos += $10`: fila base +1 (permanente), `col = pcol` |
| `down_left()` | `CODE_0DA992` | `pos += $0F`; de la col 0 → col 15 de la pantalla ANTERIOR, y mueve **también** `saved` |
| `down_right()` | `CODE_0DA9B4` | `pos += $11`; simétrico |
| `set_pos()` | `STY wm_BlockSubScrPos` | la columna actual pasa a ser la base |
| `save()` | `CODE_0DA6B1` | `saved = scr` (**solo** el puntero de pantalla) |
| `restore()` | `CODE_0DA6BA` | `scr = saved`; **NO** toca ni la fila ni la columna |

**Trampa que costó una iteración entera:** media docena de handlers escriben con
`STA [ptr],Y` seguido de `CODE_0DA97D` (columna fija, baja fila), NO con
`CODE_0DA95B` (avanza columna). Si se usa `w()` en lugar de `put()` el objeto se
va corriendo una columna por fila. Le pasó a `Midway/Goal point`, `Yoshi Coin` y
`Vert. Pipe/Bone/Log` — el poste del goal apareció 10 columnas a la derecha, en
la pantalla siguiente.

### Dos "blends" que hay que respetar

Dos rutinas no escriben el tile tal cual: lo **ajustan según lo que ya haya** en
la celda. Hay que leer el byte bajo del bloque existente:

- `CODE_0DABFD` (`_abfd`): si ya hay `$03` → `+4`; si `$01` → `+3`; si `$3F` → `+1`.
- `CODE_0DB84E` (`_84e`): si ya hay `$25` → `+0`; si `$3F` → `+1`; si no → `+2`.

Las mezclas leen lo que YA hay en la celda, y **una celda vacía vale `$25`** en
el ROM (P26). En nuestro `Level` el vacío es la palabra 0, así que `_low_at()`
traduce 0 → `$25`. `h_ledge_edges` tiene además sus propias mezclas
(`CODE_0DB114` para el tope, `CODE_0DB198` para el cuerpo), ya transcritas.

Y ojo con el bug de Nintendo en `CODE_0DB7AA`: pone `LDA.W BlockIsPage1` donde
debería ir `JSR`. `BlockIsPage1/2` **escriben el byte alto en la celda
actual** (`STA [wm_Map16BlkPtrH],Y`), así que sin la llamada el `$A1` conserva
la página que ya tenía la celda: vacía → 0 → **`Map16 $0A1`** (la cima de las
colinas). Hay que reproducir el bug así (P21, corregido).

---

## 5c. Comparar contra la referencia real de SNES (HECHO)

Tener un "oráculo" visual cambia el juego: en vez de razonar si un tile está
bien, se mira. La referencia que usa Az es el mapa completo de Yoshi's Island 1
de **SNESMaps.com** (Rick N. Bruns, 2013), fichero
`C:\Users\JC\Downloads\SuperMarioWorldMap02.png`.

**Dato clave: esa imagen está alineada 1:1 con nuestro render.**

| | referencia | nuestro render |
|---|---|---|
| tamaño | 5120 × 432 | 5120 × 432 (`--scale 1`, el defecto; ver P24) |
| ancho | 20 pantallas × 256 px | 20 × 16 tiles × 16 px |
| alto | 27 tiles × 16 px | 27 tiles × 16 px |
| corte | el panel de leyenda empieza exactamente en y=432 | — |

O sea: `ref.crop((0,0,5120,432))` se superpone píxel a píxel con
`work/level_final.png`. Se puede comparar cualquier columna directamente.

Cómo se comprueba (el patrón que hay que repetir):

```python
ref  = Image.open(r'C:\Users\JC\Downloads\SuperMarioWorldMap02.png').convert('RGB').crop((0,0,5120,432))
mine = Image.open('work/level_final.png').convert('RGB')
# mismo recorte en las dos, apiladas -> se ve al instante qué falta o está corrido
```

Resultado de la comparación (2026-09-22, **capa 1 cerrada**):

| métrica | antes | ahora | qué mide |
|---|---|---|---|
| **bloques Map16 correctos** | 5999 / 6109 = 98.2 % | **6111 / 6111 = 100 %** | la capa 1, bloque a bloque |
| imagen completa, 5 bits, `--mask none` | 33.52 % | **25.52 %** | incluye capa 2 y sprites, que no dibujamos |
| píxeles que dibujamos y difieren | — | **0.95 %** | todos caen bajo sprites (Rex, Bullet Bill, `?` volador) |

El último dato se comprobó pintando de magenta, sobre la referencia, cada píxel
nuestro que no coincide: **todos** están debajo de un sprite. No queda ningún
error de terreno. (El denominador pasó de 6109 a 6111 porque las tuberías
lavanda ahora se identifican, ver P28.)

**Regla: para comparar dos versiones nuestras, usar siempre `--mask none`.** La
máscara `--mask mine` depende de lo que dibujamos, así que dos renders distintos
dan denominadores distintos y los porcentajes no se pueden restar.

### El barrido de colores: el diagnóstico más rápido que tenemos

Comparar los **colores** de la referencia contra el CGRAM reconstruido delata
errores de paleta al instante, y no depende de la geometría:

```python
# cuantos colores distintos tiene la referencia (5 bits) y cuales no estan en
# nuestro CGRAM.  Un color con muchos pixeles que no exista en el CGRAM es un
# bug de paleta; un color con 1..17 px es antialiasing de la imagen de origen.
```

Estado actual: **24 colores de la referencia no están en nuestro CGRAM**, y solo
uno importa de verdad — `$5D80` (el cielo, que por diseño no va al CGRAM,
ver P14). Todos los demás tienen ≤ 64 px. Con esto se encontró el bug de la
moneda de Yoshi (P22): `$27FF` aparecía exactamente 400 px = 4 monedas.

Lo que falta, en orden de peso visual:

- **capa de fondo (layer 2)**: cielo con pilares, nubes y la plataforma blanca.
  Es casi todo el 25.5 % que queda. Va en la etapa 7, cuando D8 diga cómo existe en la Amiga.
- sprites (etapa 6) y el frame de animación de la moneda de Yoshi (P23).

### Cómo se cerraron los 110 bloques (2026-09-22)

No eran tres bugs de handlers sino **cinco errores de modelo**, casi todos
compartidos por varios handlers. Por eso un solo arreglo movía decenas de
bloques:

| arreglo | efecto | pitfall |
|---|---|---|
| `Cur.restore()` solo repone el puntero de pantalla; `down*()` mueven la fila base de forma permanente | 110 → 26 (pendientes de las pantallas 5 y 11, cornisa de la 0) | P25 |
| `h_ledge_edges`: nº de filas + mezclas `CODE_0DB114`/`CODE_0DB198`; celda vacía = `$25` | 26 → 11 | P26 |
| `h_diag_ledge_left`: faltaba `STY wm_BlockSubScrPos` (`set_pos()`) | 11 → 1 | P25 |
| `h_bushes`: w−1 piezas de medio, no w | 1 → 0 | — |
| `render()`: paso de 8 px por bloque (P24), tablas `_2` y tuberías por pantalla (P28), página del bug de Nintendo (P21) | invisibles para `m16diff`; 33.5 % → 25.5 % de píxeles | P21, P24, P28 |

**Lección:** `m16diff` al 100 % **no basta**. Los bloques con capa 2 detrás son
"no identificables" y ahí se escondían las pendientes en escalera, la boca de la
tubería diagonal y el color de las tuberías. Después de `m16diff` hay que
**mirar** los recortes apilados de todo el nivel (5 tiras de 1024 px).

### Herramientas de comparación (2026-09-22)

Todas en `port-amiga/tools/`. La cadena completa es:

```
m16diff.py     <- LA ÚTIL: nuestra grilla Map16 vs la leída de la referencia
  m16find.py   <- dado un bloque de la referencia, qué índice Map16 lo reproduce
    gridread.py  <- dado un bloque, qué TILE de qué GFX reproduce cada cuadrante
  crop_ref.py  <- recortes lado a lado para mirar con los ojos
  cmp_ref.py   <- métrica de píxeles (con --bits 5 y --mask none)
  m16vs.py     <- referencia vs una entrada Map16 concreta, ampliado
```

**`m16diff.py` es la que hay que correr primero.** Construye un índice inverso
"firma de píxeles → índices Map16 que la producen" y luego, bloque a bloque,
dice exactamente *"en la columna 8, fila 21, esperaba `$159` y tenemos `$000`"*.
Eso convierte "algo se ve mal" en una lista de trabajo concreta. Salida actual:

```
bloques comparables : 6111
  correctos         : 6111 (100.0%)
  erroneos          : 0
  no identificables : 2529 (capa de fondo encima)
```

Construye un índice de firmas **por `pantalla & 3`**, porque las tuberías
cambian de paleta según la pantalla (P28).

**Trampa de `m16diff`:** un bloque de la referencia que es cielo puro coincide
con las entradas Map16 **totalmente transparentes** (`$0C7`..`$0CA`). Como en
nuestro `Level.M` el `0` es el centinela de "vacío", hay que tratarlo como
acierto cuando la referencia también es cielo — si no, salen 5000 falsos errores
y la métrica da 17 %. (Y ojo: `Map16 $000` NO está vacío, son los tiles
`$70`-`$73` a paleta 7.)

**Trampa de espacio de color (importante):** la referencia expande 5→8 bits con
`v << 3` y nuestro `palmod.snes_to_rgb8` usa replicación de bits
(`v<<3 | v>>2`). A 8 bits **todo** difiere por 1..7 unidades. **Todas las
comparaciones van a 5 bits** (`c >> 3`). Esto ya está por defecto en `cmp_ref`
(`--bits 5`) y en `m16find`/`m16diff`.

**Tuberías (antes "diferencia abierta", hoy CERRADA — P28):** el color de las
tuberías `$133`-`$13A` depende de la **pantalla** (`MAP16AppTable`). En
Yoshi's Island 1 las de la pantalla 7 son lavanda, igual que en la referencia.

---

## 6. Toolchain (la que se usa de verdad)

> Corregido el 2026-09-22: esta sección describía un flujo que el proyecto no
> usa (hunks + `xdftool` con **FFS**, `fs-uae`, Kickstart 1.3). Un disquete FFS
> **no arranca en Kickstart 1.x**, y el usuario solo tiene **KS 1.2**.

| pieza | ruta / valor |
|---|---|
| Ensamblador | `C:\Users\JC\vbcc\bin\vasmm68k_mot.exe` — `-Fbin -m68000 -no-opt` |
| C (cuando haga falta) | vbcc `+kick13` (sin libc; ver §7) |
| Python | `C:/Users/JC/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe` (Pillow, **sin numpy**) |
| Emulador | WinUAE `C:\Program Files\WinUAE\winuae64.exe` |
| Kickstart | **1.2**, `C:\Users\JC\Downloads\amivideo\kick12.rom` |

**Arranque:** sin AmigaDOS ni hunks (`HUNK_RELOC32SHORT` da "error 121" en KS
1.x). `player/boot.s` es un bootblock propio que lee el stage 2 en crudo con
`trackdisk.device` a chip RAM y salta; `tools/mkadf.py` arma el ADF.

```powershell
.\build.ps1 build            # boot.bin + demo.bin + demo.dat -> work\smw.adf
.\build.ps1 shot             # build + WinUAE + captura PNG (config RAPIDA)
.\build.ps1 run              # build + WinUAE interactivo
```

**Banco de pruebas de rendimiento (etapa 4):**

```bash
vasmm68k_mot -Fbin -m68000 -no-opt -I player -o work/bench.bin player/bench.s
python tools/mkadf.py --boot work/boot.bin --stage2 work/bench.bin --out work/bench.adf
```
```powershell
.\tools\shot.ps1 -Exact -Adf work\bench.adf -Out work\bench.png -Wait 80
```
```bash
python tools/bench_read.py --shot work/bench.png    # tabla en ms / lineas / % de frame
```

La Amiga mide con el timer A de CIA-B y escribe los resultados en pantalla como
bits; `bench_read.py` los decodifica y comprueba dos palabras de sincronía.
Para medir algo nuevo: añadir una rutina `workN` y una fila más.

**Dos configuraciones de emulador, con usos distintos:**

| config | para qué | por qué |
|---|---|---|
| `tools/shot.ps1` (y `build.ps1 shot`, que lo llama) | capturas y verificación visual | `cpu_speed=max`, `immediate_blits=true`: rápida, **tiempos falsos** |
| `tools/shot.ps1 -Exact` | capturas **con temporización real**; lo que hay que usar para medir | mismos valores que `a500.uae`: `cycle_exact=true`, `cpu_speed=real`, `immediate_blits=false` |
| `a500.uae` | sesiones interactivas en WinUAE (ROM y ADF se eligen a mano) | referencia de la config cycle-exact |

`shot.ps1` borra la captura anterior, espera a que la ventana tenga contenido y
sale con código 1 si no pudo capturar: `verify_shot.py` nunca compara una
imagen vieja.

Limitación del entorno: la herramienta PowerShell de este entorno no ejecuta
binarios nativos ni devuelve stdout. Compilar con bash (vasm + python) y usar
PowerShell solo para WinUAE + captura (`tools/shot.ps1`); los scripts escriben
logs en `work/*.log`.

> **"Arrancar sin Kickstart" no existe:** la A500 siempre arranca por el
> Kickstart de la ROM, que es quien carga el bootblock. Lo que hacemos es
> **tomar el control** después (`LoadView(0)`, `WaitTOF`, DMA propio). Lo que
> ocupa el SO en ese momento son decenas de KB, no ~256 KB, y se recupera al
> tomar la máquina.

---

## 7. Convenciones de código

### Reparto de responsabilidades

| Lenguaje | Para qué |
|---|---|
| **68000 asm** | rutinas de blitter, listas de copper, ISR del VBL, cambio de contexto |
| **C** | física, colisiones, IA de sprites, máquina de estados, HUD |

### Convenciones de ensamblador

- **ABI (la de vbcc/AmigaOS):** `d0/d1/a0/a1` son de trabajo y los destruye
  cualquier llamada; `d2-d7`/`a2-a6` los preserva quien los use. Vale para
  llamadas a librerías del sistema **y** para toda rutina asm llamada desde C.
  (Corregido 2026-09-22: esta sección decía "preservar `a2-a4`", que dejaba
  fuera `a5`/`a6`, y `demo.s` guardaba GfxBase en `a0` a través de `LoadView`.)
- **Registros con dueño en el código actual:** `a4` = `CUSTOM` (`$DFF000`),
  `a6` = ExecBase mientras se usa el SO; recargar siempre de `4.w`, nunca
  confiar en que sobrevivió. No reservar registros "globales" entre C y asm:
  vbcc usa `a5` de frame pointer y `a4` para el modelo small-data.
- El stack nunca baja de `$800`.
- Las direcciones de los chips custom se acceden vía `a4` con offset, nunca
  con literales absolutos.
- **El código no se acelera moviéndolo a `$C00000`** (P29).

### Convenciones de C

- Sin `malloc`. Sin libc completa. Solo lo que escribas.
- Tipos: `u8`, `s8`, `u16`, `s16`, `u32`, `s32`. Nada de `int` a secas.
- Punto fijo 8.8 para toda la física (igual que la SNES): `typedef s16 fix88;`
- Prohibido `float`/`double` — no hay FPU.

### Alineación (crítico)

- Bitplanes y tilesets: **8 bytes** (los blits son por palabra)
- Listas de copper: **4 bytes**
- Muestras de audio: **2 bytes**

### Estilo de comentarios

En español. Cada rutina de hardware (blitter/copper) lleva arriba:
```
; --- nombre_rutina ---
; entrada:  a0 = ...
; salida:   d0 = ...
; registros destruidos: d0-d3
; ciclos:   ~N (medido en emulador)
```

---

## 8. Pitfalls conocidos

**P1 — El layout de paletas de SMW no es un array 8×16. ✅ RESUELTO.**
`PALETTE_Sprites` en `palettes/palettes.a` tiene solo 42 palabras, no 128:
está empaquetado para la rutina de subida. **No asumas
`paletas[n*16:(n+1)*16`.** La solución completa está en §8b y en
`tools/palette.py`, que emula `LoadPalette` y reconstruye el CGRAM exacto.

**P2 — El blitter tiene prioridad sobre la CPU y la "roba" ciclos.**
Usa el bit *blitter nasty* (DMACON `$0400`) solo cuando necesites el blit
terminado ya. Si no, deja que la CPU siga y sincroniza en el VBL.

**P3 — Las listas de copper deben estar en chip RAM y alineadas a 4 bytes.**
El registro `COP1LC` ignora los bits bajos.

**P4 — Los punteros de bitplane deben ser múltiplos de 2.**
El bit 0 se ignora silenciosamente. Un fallo aquí produce un desplazamiento
de 1 píxel que no se ve hasta que algo se sale de pantalla.

**P5 — Los back-references de LC_LZ2 apuntan a offsets ABSOLUTOS** en el
buffer de salida y pueden solaparse consigo mismos. Hay que copiar byte a
byte, no con `memcpy`. Ya está resuelto en `smw2amiga.py`.

**P6 — `chr.lz2` no es lo que dice la documentación.** Es 4bpp, no 3bpp.
Ya resuelto en la tabla de §5. Corregido además su contenido: **no son
"objetos comunes" sino los tiles del jugador** (Mario/Luigi) más el huevo de
Yoshi. Se ve la cara de Mario al renderizarlo.

**P9 — `document/graphics.txt` usa IDs de fichero, no nombres.**
El mapeo `chr`/`spr-N`/`obj-N`/… → ID es por *propósito*, no secuencial:
`obj-1` = ID 07 (ghost house) pero `obj-2` = ID 14 (tubería/moneda), y
`obj-3` = ID 15 (suelo de hierba). No hay atajo: hay que mirar
`levels/*.a` (`.INCBIN`) y `graphics.s` para mapear cada nombre.

**P10 — La paleta del jugador no viene de `LoadPalette`.**
`CODE_00B03E` (game.s:5527) copia `PALETTE_Mario` (10 colores) a
`wm_PaletteCopy` **empezando en el color 135** (CGRAM `$87`), y el sprite se
dibuja con la paleta de sprites 0 (colores 128-143). Por eso la vista de 16
colores del jugador es la paleta 8 con Mario superpuesto en 135. Ver
`build_player_palette()` en `tools/mkdemo.py`.

**P7 — Las muestras de audio en Paula son PCM de 8 bits FIRMADO.**
BRR es ADPCM de 4 bits sin signo explícito. Cuidado con el sesgo DC.

**P9b — El buffer Map16 guarda ÍNDICES Map16, no tile numbers.**
`wm_Map16BlkPtrL/H` (a pesar del nombre "Ptr") contiene índices de 9 bits que
hay que resolver con `tilemaps/*.bin` para obtener tile + **paleta**. Si los
tratas como tile numbers y les aplicas la paleta 0 te sale el gradiente del
cielo en vez del terreno. Costó un render entero descubrirlo. Ver §5b.

**P10b — El índice Map16 incluye el bit de página.**
`BlockIsPage1/2` no son "flags": escriben el **byte alto** del índice. El
índice real es `valor | (page << 8)`, o sea 0..511. Los ficheros de rango
cubren exactamente 0x000-0x1FF por eso.

**P11 — El orden de los bloques GFX está invertido respecto a la lista.**
`OBJECTGFXLIST[t*4 + 0]` va a VRAM $0000, `+1` a $0800, `+2` a $1000 y `+3` a
$1800, porque el bucle hace `LDA OBJECTGFXLIST,Y / STA m4,X` con X de 3 a 0.
Con tileset 7 (obj-2, obj-5, bg-3, obj-3) el bloque 0 es obj-2 y el 2 es bg-3.

**P12 — Las 4 palabras de una entrada Map16 van en column-major, no raster.**
`word0=TL`, `word1=BL`, `word2=TR`, `word3=BR`. Con el orden raster las
tuberías salen "garbled" (esa fue exactamente la queja de Az). Se ve al
instante con `tools/m16sheet.py --order row|col`. Ver §5b.

**P13 — El cuadrante vacío es la palabra `$0000`, no `tile == 0`.**
Filtrar con `if tile == 0: continue` borra cuadrantes legítimos que usan el
tile 0 (la boquilla de tubería, por ejemplo) y deja huecos negros en el medio
del gráfico. Hay que mirar la palabra entera (`Map16.get_raw()`).

**P14 — El color de fondo del nivel no está en `cgram[0]`.**
`LoadPalette` (game.s:5039) calcula el color de cielo con
`PALETTE_Sky[wm_LvHeadBgCol]` y lo **devuelve aparte** (`wm_LvBgColor`); no lo
escribe en el CGRAM. `cgram[0]` queda a 0. Usar `cgram[0]` como fondo pinta el
cielo de negro. `palette.build_cgram()` devuelve `(cgram, bg_color)` — hay que
usar el segundo.

**P15 — Los handlers de objeto no comparten la página.**
Cada rutina llama a `BlockIsPage1` o `BlockIsPage2` según el tile. Los
arbustos (`CODE_0DB5B7`) usan **Page1** → índices `$073/$074/$079`, que caen en
la zona *específica del estilo* (`set_N/073-0FF.bin`), no en la común. Copiar
la página de memoria o asumir que "todo va a la página 2" da gráficos de otro
tileset.

**P16 — Los handlers NO escriben todos con `CODE_0DA95B`.**
El escritor que avanza columna (`w()`) es solo para las filas de terreno y las
tuberías. Muchos objetos escriben con `STA [ptr],Y` puro (columna fija) y bajan
con `CODE_0DA97D` (`down()`): *Midway/Goal point* (`CODE_0DB224`),
*Yoshi Coin* (`CODE_0DB2CA`) y *Vert. Pipe/Bone/Log* (`CODE_0DB51F`) son así.
Si les metés `w()` te corren **una columna por fila** y el objeto aparece como
una escalera diagonal gigante. Fue exactamente el bug que mandó el poste de
meta a la pantalla 19 y bajó el score de 43.75 % a 49.4 %.

**P17 — `down_left`/`down_right` cambian de PANTALLA al dar la vuelta.**
`CODE_0DA992` (`down_left`) hace `Y -= $10`; si la columna era 0, el resultado
es negativo y el `BPL` de `_0DA97D` no se toma: el puntero retrocede `$B0` y
`DEC wm_MirrorScrnNum`. O sea **col 0 → col 15 de la pantalla ANTERIOR**.
`down_right` (`CODE_0DA9B4`) hace lo simétrico: col 15 → col 0 de la siguiente.
Usar `(col ± 1) % 16` deja la escritura en la pantalla equivocada — verificado
contra la referencia: la tubería diagonal que arranca en la pantalla 8 aterriza
en la **columna 15 de la pantalla 7**.

**P18 — `DATA_0DB72F` y compañía son ÍNDICES Map16, no tile numbers.**
La tabla de la tubería diagonal (`tiles.s`, `DATA_0DB72F`) es
`C4 C5 C7 EC ED C6 C7 EE 59 5A EF C7 EE 59 5B 5C` y se escribe con
`BlockIsPage2` → los índices reales son `$1C4, $1C5, $1C7, $1EC, $1ED, $1C6,
$1EE, $159, $15A, $1EF, $15B, $15C`. Igual pasa con `DATA_0DEB93`
(`tiles4.s:289`): es la casa de Yoshi en índices Map16, no el nivel.
De ahí sale que `$159`-`$15C` (en `set_0`) sean las piezas de la tubería
diagonal y `$15D`-`$160` las variantes de la tubería recta.

**P19 — La capa de fondo (layer 2) no la dibujamos, y domina la métrica.**
Cielo, pilares, nubes y la plataforma blanca detrás de los arbustos viven en
la capa 2, que **no está implementada**. Por eso el diff de píxeles de imagen
completa está clavado en ~33.5 % y no se mueve aunque arregles el primer plano.
**Para medir el primer plano usá la métrica de bloques Map16 (`m16diff.py`),
no el diff de píxeles.**

**P20 — `--mask mine` NO es comparable entre versiones nuestras.**
El denominador cambia según cuánto dibujemos (321 k → 380 k píxeles), así que
un porcentaje "mejor" puede ser solo un denominador más chico. **Para comparar
dos versiones nuestras, siempre `--mask none`.** `--mask mine` sirve solo para
inspeccionar el primer plano contra la referencia.

**P21 — El bug de Nintendo en `CODE_0DB7AA` hay que REPRODUCIRLO (corregido 2026-09-22).**
La rama izquierda de la cornisa diagonal hace `LDA.W BlockIsPage1` donde debería
ir un `JSR` (el decomp lo marca con `; FIX SHOULD BE JSR NINTENDO`).
`BlockIsPage1/2` **no son un "modo"**: hacen `STA [wm_Map16BlkPtrH],Y`, o sea
escriben el byte alto en la celda actual. Sin la llamada, la celda **conserva la
página que ya tenía** (vacía → 0 → `Map16 $0A1`, la cima de la colina). La
versión anterior de este pitfall decía "la página queda en 2 → `$1A1`": era
falso, y dibujaba un saliente de hierba en la cima de todas las colinas. En
`Level.put()` se modela con `page=None`.

**P22 — El color de la MONEDA DE YOSHI es una animación de paleta, no $7C3F.**
`CODE_00A418` (game.s:4148) corre **todos los frames** y hace:
```
LDA #$64 / STA CGADD            ; $64 = palabra $32 = paleta 6, color 4
LDA wm_FrameB / AND #$1C / LSR  ; -> 0,2,4,...,14
TAY / LDA PALETTE_Flashing,Y / STA CGDATAW
```
O sea: el color 4 de la paleta 6 **no** es el `$7C3F` (magenta) que carga
`PALETTE_Objects` (palettes.a:58), sino que se **pisa cada frame** con un valor
de `PALETTE_Flashing` (palettes.a:157, fila *Yellow*). Los 8 pasos son
`$02DF $27FF $73FF $27FF $01BF $001B $0018 $001F`.
La referencia de SNES capturó el paso 1 (`$27FF`). Sin esto la moneda sale
**magenta**. Implementado en `palette.build_cgram(..., coin_frame=1)` →
`palette.COIN_ANIM` / `COIN_ANIM_REF`, así lo heredan todas las herramientas.
Detectado con el barrido "colores de la referencia que no están en nuestro
CGRAM": `$27FF` aparecía exactamente 400 px = 4 monedas × 100 px, en las
pantallas 1, 5, 11 y 18 (justo donde el nivel tiene monedas).

**P23 — La moneda de Yoshi también anima sus TILES.**
`CODE_00A390` (game.s:4096) hace DMA a VRAM desde `wm_GfxAnimFrame1/2/3` y
termina en `_00A418`. O sea que las palabras de Map16 `$02D`/`$02E` de
`set_0`/`000-072.bin` son **solo el frame 0** de la animación; la forma que
captura la referencia es otro frame. Consecuencia práctica: **`m16find`/
`m16diff` nunca van a identificar el bloque de la moneda** (diferencia de
forma, no de geometría). No es un bug de posición: la moneda está en el tile
correcto (verificado: el `$27FF` de la referencia cae exactamente en
`(11,3,14)`, que es el `y=14` del objeto).

**P24 — `render()` dibujaba con paso de 8 px por bloque (corregido 2026-09-22).**
`BW = lv.W * 8` y `ox = gx * 8 + ...`, pero un bloque Map16 mide 16×16. Con
`--scale 2` la imagen salía de 5120 px (parecía alineada con la referencia),
pero cada bloque pisaba la mitad derecha e inferior del anterior: **solo se veía
el cuadrante superior izquierdo de cada bloque, ampliado 2×**. En tierra y
césped uniformes no se nota; en pendientes convierte la diagonal en escalera.
Ahora el paso es 16 y `--scale 1` (el defecto) da los 5120×432 alineados.

**P25 — `restore()` NO devuelve el cursor al punto guardado.**
`CODE_0DA6B1`/`CODE_0DA6BA` guardan y reponen **solo el puntero de pantalla**
(`m4/m5`). La fila y la columna base viven en `wm_BlockSubScrPos`, y
`CODE_0DA97D`/`0DA992`/`0DA9B4` las **reescriben** (bajar una fila es
permanente). Modelar `restore()` como "volver a (pantalla, fila, col)" hacía que
todos los bucles `save/restore/down` reescribieran la misma fila: pendientes
huecas, cornisas deformes. Además, cuando `down_left`/`down_right` cruzan de
pantalla, `CODE_0DA9D6`/`0DA9EF` mueven también la copia guardada. Y alguna
rutina hace `STY wm_BlockSubScrPos` a mano (`set_pos()`). Tabla completa en §5b.

**P26 — Una celda vacía vale `$25` en el ROM, no 0.**
El buffer se inicializa con el bloque en blanco `$025`, y las mezclas
(`CODE_0DB84E`, `CODE_0DB114`) comparan con `CMP #$25`. Nuestro `Level` usa la
palabra 0 como vacío, así que `_low_at()` traduce 0 → `$25`. Sin eso,
`CODE_0DB84E` suma +2 donde el ROM no suma nada.

**P27 — Leer las tablas `.DB` del handler ANTES de contar bucles.**
Tres de los errores de esta sesión eran de conteo (`DEC m0 / BNE` vs `BPL`, un
`y += 1` incondicional). Transcribir instrucción por instrucción, con el estado
de `m0`, `X` e `Y` anotado, y no "por la forma" del objeto.

**P28 — El ROM reapunta entradas Map16 según el tileset y la PANTALLA.**
Dos sustituciones que `map16.py` no hacía (ahora sí, `Map16(..., tileset=t)` y
`get(idx, screen)`):
1. Tilesets 0 y 7 (`lv_read.s:283`): `$1C4`-`$1C7` y `$1EC`-`$1EF` pasan a
   `1C4-1C7_2.bin`/`1EC-1EF_2.bin` (`DATA_0D8A70`). Son la **boca de la tubería
   diagonal**; las tablas normales son pendientes de tierra.
2. Tuberías `$133`-`$13A` (`MAP16AppTable`, `lv_read.s:805`): al subir la
   columna `c` se elige la variante `(c >> 4) & 3`, o sea **pantalla & 3** →
   paleta 3 / 5 (verde) / 6 / 7 (lavanda). Esto **cierra D7**. El puerto tiene
   que reproducirlo en el conversor de nivel (resolver el color por pantalla al
   generar el tilemap de Amiga).

**P29 — El "slow RAM" de la A501 comparte el bus del chipset.**
`$C00000` no es fast RAM: cuelga del bus de chip y la CPU espera los mismos
ciclos que roban el DMA de bitplanes, el copper y el blitter (por eso se llama
*slow*). Moverle el código **libera chip RAM, pero no lo acelera**. Hoy el stage
2 corre en chip RAM (trackdisk en KS 1.x solo lee a chip); la etapa 4 tiene que
medir la CPU con el código donde vaya a vivir y con los planos y bobs reales
activos. R2 sigue valiendo: el chipset no *lee* de `$C00000`.

**P30 — `tools/shot.ps1` sin `-Exact` no sirve para medir.**
Sin la opción usa `cpu_speed=max` e `immediate_blits=true`: la imagen es
correcta, los tiempos son falsos. `-Exact` usa la temporización de `a500.uae`.
Verificado el 2026-09-22: el ADF arranca en KS 1.2 con temporización real y la
captura coincide al 100 % con el oráculo del PC.

**P31 — Cada blit cuesta ~42 µs de CPU además de los datos.**
Medido en la etapa 4 (W1 contra W3, `bench.s`): preparar los registros y
esperar a que el blitter termine, con el código en chip RAM, cuesta unos 42 µs
por blit. 160 bloques sueltos de 16×16 son ~6.7 ms solo de eso. Preferir
**pocos blits grandes** (una columna entera de una vez, bloques de pantalla
entrelazada en un solo blit de h×5 filas) y no esperar al blitter entre blits
si la CPU tiene otra cosa que hacer. `BLTPRI` (blitter nasty) ahorra un 12-25 %
**solo** mientras la CPU no tiene nada que hacer (P2).

**P32 — Con 5 planos los sprites de hardware comparten los colores 16-31.**
Los sprites del OCS usan COLOR17-19, 21-23, 25-27 y 29-31, que con 5 planos son
también colores del playfield. Poner a Mario en sprites de hardware **no suma
colores**: salen del mismo presupuesto de 31 por línea (D9).

**P8 — El slow RAM de la A501 no está disponible si el software lo desactiva.**
Algunas rutinas de arranque desactivan `/EXRAM`. Verifica que `$C00000`
responde antes de usarlo.

---

## 8b. El layout de paletas de SMW (RESUELTO)

Reconstruido emulando `LoadPalette` (`game.s:5039`) y verificado: el color
de fondo de Yoshi's Island 1 sale `$5D80` = rgb(0,99,189), el celeste
clásico. Implementado en `tools/palette.py`.

### Las dos rutinas

```
LoadCol8Pal(value, X):                 ; game.s:5145
    escribe `value` en X, X+$20, ..., X+$E0   (8 filas seguidas)

LoadColors(m0, m4, m6, m8):            ; game.s:5157
    s = m0 ; base = m4
    repetir m8+1 veces:
        d = base
        copiar m6+1 palabras: CGRAM[d] = bank[s] ; s += 1 ; d += 2
        base += $20                    ; una fila de 16 colores
```

Claves que hay que tener presentes:

- `m4` es un **offset en BYTES** dentro del shadow de CGRAM (`wm_Palette`,
  `COL_DATA 256` = 512 B). Color *n* vive en el byte `n*2`.
- `m0` **avanza contiguamente** entre pasadas; el destino es el que salta.
  Por eso `PALETTE_Objects` declara 36 palabras pero la rutina lee 60: las
  otras 24 viven tras las etiquetas `DATA_B298/B2A4/B2BC` que hay en medio.
  **Hay que leer `palettes.a` en orden, no por etiquetas.**
- `DATA_00ABD3` (`game.s:5026`) es una tabla de offsets en bytes a
  sub-paletas dentro de un blob: `$00,$18,…,$A8` (paso 12 palabras) para los
  8 primeros, `$00,$14,$28,$3C` (paso 10) para los 4 últimos.
- Los índices de paleta del header del nivel son **3 bits** (0-7), no 4:
  `FgPal = byte3 & 7`, `SprPal = (byte3>>3) & 7`, `BgPal = byte0>>5`,
  `BgCol = byte1>>5`.

### A dónde va cada cosa

| Destino | Fuente |
|---|---|
| color 1 de paletas BG 0-7 | `$7FDD` (LoadCol8Pal) |
| color 1 de paletas SPR 0-7 | `$7FFF` (LoadCol8Pal) |
| BG 0-1, col 2-7 | `PALETTE_Background + 12·BgPal` |
| BG 0-1, col 8-15 | `PALETTE_Layer3` |
| BG 2-3, col 2-7 | `PALETTE_Foreground + off(FgPal)` |
| BG 4-7, col 2-7 | `PALETTE_Objects` grupos 0-3 |
| SPR 0-5, col 2-7 | `PALETTE_Objects` grupos 4-9 |
| SPR 6-7, col 2-7 | `PALETTE_Sprites + off(SprPal)` |
| pal 2,3,4 col 9-14 | `PALETTE_YoshiBerry` |
| pal 9,10,11 col 9-14 | `PALETTE_YoshiBerry` |
| SPR 0 col 7-15 | `PALETTE_Mario/Luigi` (fuera de LoadPalette, ver P10) |

Resultado en Yoshi's Island 1 (header `33 40 08 80 27`): paleta 5 = hierba
(tostado/verdes), paleta 6 = bloques `?` (marrón/naranja/amarillo), paleta
10 = monedas y `?` como sprite. Volcado completo en `work/cgram_swatch.png`.

### Consecuencia para el port

SMW usa **128 colores** en pantalla; la Amiga tiene 32 como máximo y el demo
va a 16. Por eso D1 es una decisión de diseño, no un detalle: hay que
**fusionar** paletas. Candidatos para Yoshi's Island 1:

- terreno + fondo: BG 5 (hierba) + BG 1 (cielo) → ~13 colores
- objetos: BG 6 (`?` blocks) → +8 colores

Estrategia recomendada: 16 colores fijos para el nivel, y **partir el copper**
a media pantalla para el HUD (barra de estado con su propia paleta), que es
justo lo que hace la SNES con CGRAM.

---

## 9. Decisiones abiertas

| ID | Decisión | Opciones | Estado |
|---|---|---|---|
| D1 | Compromiso de scroll/color/frecuencia | **1 px (`BPLCON1`) / 5 planos, 31 colores / 50 Hz** | **cerrado** con la etapa 4: scroll + 5 bobs = 48-68 % del frame. Queda por medir la lógica de juego (etapas 8-9); si no entra, 25 Hz |
| D2 | Nivel objetivo | **Yoshi's Island 1** (`world_1/1/`) | cerrado |
| **D3** | Enemigos del demo | Los que tiene el nivel de verdad (`spr.lv`, ver abajo). **Goomba y Koopa Troopa NO aparecen en Yoshi's Island 1** | **corregido** — mínimo: Rex + Banzai Bill + Jumping Piranha |
| D4 | Lenguaje principal | C para lógica + asm para hardware | cerrado |
| D5 | Música | MOD 4 canales propio vs. motor existente | abierto |
| D6 | Arranque | **bootblock propio** leyendo sectores crudos; funciona en KS 1.2 y 1.3 | cerrado |
| D7 | Color de las tuberías verticales | — | **cerrado**: depende de la pantalla (`MAP16AppTable`), ver P28 |
| **D8** | Cómo existe la capa 2 (fondo) en la Amiga | **(d) dual playfield + recarga de colores a mitad de línea con el copper**: capa 1 = PF1 (3 planos, índices fijos por línea del nivel), capa 2 = PF2 (3 planos, paralaje por hardware), Mario y enemigos = sprites de hardware con colores 17-31 recargados por línea, bob en PF1 cuando hay más de 4 columnas. Las demás opciones y sus medidas, en §9 "Etapa 4 — resultados" puntos 4-10 | **cerrado** (usuario, 2026-09-23) |
| D9 | Presupuesto de color | Vista real: **25 colores por línea, 40 por pantalla** (capas + sprites) | **cerrado**: 5 planos + paleta recargada por bandas con el copper. Ojo con P32 (los sprites comparten los colores 16-31) |

### D3 — los sprites reales de Yoshi's Island 1

Leído de `levels/data/world_1/1/spr.lv` (registros de 3 bytes, byte 2 = nº de
sprite; nombres de `sprite_1-main.s`):

| sprite | nº | cuántos | nota |
|---|---|---|---|
| Rex | `$AB` | **18** | el enemigo del nivel |
| Banzai Bill | `$9F` | 4 | **64×64**: el bob más caro del proyecto |
| Jumping Piranha Plant | `$4F` | 3 | sale de las tuberías |
| Info Box | `$B9` | 2 | mensaje de texto |
| Clappin' Chuck | `$95` | 1 | |
| Sliding Koopa sin caparazón | `$BD` | 1 | |
| Bloque `?` volador (izquierda) | `$83` | 1 | |
| Bloques "warp hole" invisibles | `$8E` | 1 | sin gráfico |
| Champiñón invisible | `$C7` | 1 | sin gráfico |
| Caparazón de Koopa rojo, quieto | `$DB` | 1 | `sprite_2-clus.s:_02A971`: `$DA`-`$DF` se cargan con estado 9 y nº `id - $DA + 4` → `$05` (Red Koopa) |
| Cinta de meta | `$7B` | 1 | |

El gráfico de Rex y Banzai Bill es el GFX `20` (`graphics.txt:40`), no `spr-2`.

### D8/D9 — datos medidos (2026-09-22)

| medida | valor |
|---|---|
| colores CGRAM distintos que usa la capa 1 en todo el nivel | **38** + el cielo |
| máximo en una ventana de 2 pantallas (lo que se ve a la vez) | **31** |
| colores de la referencia (capa 1 + capa 2 + sprites) por ventana de 320 px, >16 px | **20 a 41** |

O sea: **solo el terreno ya llena 32 colores**; 16 (la vieja opción B) está
lejos del 1:1. Antes de elegir D8 hay que averiguar **cómo se mueve la capa 2
en este nivel** (si va a otra velocidad que la capa 1, la opción (b) deja de ser
1:1) leyendo la configuración de scroll del nivel en `lv_read.s`.

### Etapa 4 — resultados (2026-09-22)

#### 1. Cómo se mueve la capa 2 en Yoshi's Island 1 (sin hardware)

`levels/tables.a:DATA_05F000[$105]` = `%0101 1011` → ajuste de scroll 5 →
`L2HorzScrollSettings[5] = 2` (`map_l1.s:45`) → en `player.s:5396`,
**`Bg2HOfs = Bg1HOfs >> 1`: paralaje a media velocidad**. Vertical:
`L2VertScrollSettings[5] = 2`, también a media velocidad. El fondo es
`Layer2Mountains` (`Layer2Ptrs`, fila 100-107).

#### 2. Colores (medidos sobre nuestro render y la referencia)

| medida | valor | consecuencia |
|---|---|---|
| capa 1, colores por línea (ancho completo del nivel) | **22** | necesita 5 planos por sí sola |
| capa 2, colores con peso (incluye el cielo) | **~8** | cabe en 3 planos |
| vista de cámara real (256×224), capa 1 + capa 2 + sprites, por **línea** | **25** | cabe en 31 |
| ídem, por **pantalla** | **40** | hace falta recargar paleta por bandas con el copper |

#### 3. Blitter en la A500 (`player/bench.s`, `a500.uae`, cycle-exact)

Medido por la propia Amiga con el timer A de CIA-B (709379 Hz), 32
repeticiones por carga, con **5 planos entrelazados en pantalla a 320 px**
(peor caso: con 256 px de ancho hay menos contención). Calibración: 14210
ticks/frame contra 14188 teóricos (+0.16 %). Máximo ≈ media en todas las
cargas: la medida es estable.

| carga | BLTPRI off | BLTPRI on |
|---|---|---|
| W1: columna nueva (14 bloques, cada 16 px de scroll) | 5.51 ms · 27 % frame | 4.86 ms · 24 % |
| W2: **recomponer toda la pantalla** (fondo 336×224 + 160 bloques) | 69.3 ms · **346 %** | 58.1 ms · **290 %** |
| W3: bobs (Banzai Bill 64×64 + 4 Rex 16×32, restaurar + dibujar) | 12.6 ms · 63 % | 9.4 ms · 47 % |

| presupuesto por frame a 50 Hz | BLTPRI off | BLTPRI on |
|---|---|---|
| sin paralaje, scroll 1 px/frame + bobs | 64 % | **48 %** |
| sin paralaje, scroll 3 px/frame (carrera) + bobs | 68 % | **51 %** |
| paralaje recomponiendo todo + bobs | 408 % | 337 % → ni a 16.7 Hz |

Deducido de W1 contra W3 (mismos tipos de blit, distinto número): **cada blit
cuesta ~42 µs de CPU** en preparación y espera, además de los datos (P31).

#### 4. Qué opciones de D8 quedan

| opción | colores capa 1 | paralaje | coste | veredicto |
|---|---|---|---|---|
| (a) dual playfield | **7** (necesita 22) | sí | barato | ✗ por color |
| recomponer todo cada frame | 22 | sí | 290-346 % de frame | ✗ por tiempo |
| split por copper (DPF arriba, 5 planos abajo) | ≤ 7 arriba, 22 abajo | solo arriba del corte | barato | con el corte en la fila 15 (el más bajo que deja ≤7 colores arriba) **el 79 % de la capa 2 visible queda debajo, sin paralaje** |
| **(b) fondo pre-compuesto, sin paralaje** | 22 | **no**: el fondo se mueve con el terreno | 48-68 % de frame con bobs | ✓ viable a 50 Hz |

Con el hardware del OCS **no hay forma medida de tener a la vez los colores de
la capa 1 y el paralaje de la capa 2**. La pérdida de fidelidad hay que
elegirla: colores (DPF) o movimiento del fondo (b).

#### 5. Cómo lo hicieron otros juegos del OCS (investigado 2026-09-23)

Fuentes: hilo de Lemon Amiga `viewtopic.php?t=8512` ("Parallax on the Amiga"),
Codetapper *Sprite Tricks* (Brian the Lion, Risky Woods, R-Type 2, Jim Power,
Videokid, Beast, Agony) y la entrevista de Codetapper a **Chris Sorrell**
(James Pond 1/2). Ningún juego del OCS tiene un primer plano de 31 colores
**y** un fondo con paralaje: todos bajan el primer plano a 3 o 4 planos.

| técnica | juegos | primer plano | fondo | paralaje H |
|---|---|---|---|---|
| dual playfield + barras de copper | Lionheart, Kid Chaos, Beast, Agony | 7 + copper | 7 + copper | gratis (`BPLCON1` PF2) |
| **4 planos + 5.º plano de fondo**, paleta 16-31 = copia de 0-15 | James Pond 1 y 2 | 15 + copper | **1 color + copper** (0/16) | ver paridad ↓ |
| sprites detrás del playfield, recolocados por copper | Risky Woods, R-Type 2 (patrón de 64 px, 15 colores); Brian the Lion (el copper escribe `SPRxDATA` cada 8 px, 2 colores) | 15 (4 planos) | según el truco | gratis (`SPRxPOS`) |

**Paridad de planos.** `BPLCON1` tiene un retardo para los planos impares
(1, 3, 5) y otro para los pares (2, 4). En un solo playfield, el plano de fondo
siempre comparte retardo con planos del primer plano. Por eso el paralaje H fino
del 5.º plano **no sale del hardware**: hay que redibujarlo o desplazarlo con
el blitter. Sorrell: el plano 5 de Robocod "se redibuja entero cada 16 px de
scroll", y el paralaje horizontal "no llegué a hacerlo". El vertical sí es
gratis (mover `BPL5PT`). Coste de un blit de desplazamiento de 1 plano:
**sin medir**, se mide con `bench.s`.

**Sprites.** Todas estas variantes necesitan un primer plano de 4 planos. Con 5
planos los sprites pisan los colores 16-31 (P32) y el 5.º plano le roba ranuras
al copper, que ya no llega a una escritura cada 8 px como en Brian the Lion.
Risky Woods y R-Type 2 repiten un patrón de 64 px, y las montañas de SMW no son
periódicas a 64 px.

#### 6. Colores re-medidos por ventana de cámara (2026-09-23)

El "22" de arriba es por línea **a lo ancho de todo el nivel**. Dentro de lo que
se ve (256 px), sobre `work/level_final.png`:

| medida (capa 1, sin el cielo) | valor |
|---|---|
| máx. colores por línea en cualquier ventana de 256 px | **17** |
| líneas con ≤ 15 en cualquier ventana | 428 / 432 |
| líneas con ≤ 7 en cualquier ventana | 307 / 432 (las que fallan: filas 14-23 de bloques, terreno) |
| capa 2 (referencia donde la capa 1 es cielo), píxeles exactos con 1 / 3 / 7 colores por línea | 45 % / 81 % / 98 % |

Simulación (`work/d8_dpf_sim.png`, `d8_cmp_b.png`, `d8_cmp_c.png`):

- **DPF, paleta fija por línea**: rompe la pantalla 7 (bloques de cemento y
  tuberías lavanda/gris pasan a marrón). Con la paleta **siguiendo a la
  cámara**, las tuberías y los bloques siguen perdiendo sombreado. **DPF no es
  1:1 para la capa 1.**
- **Robocod (4+1)**, paleta siguiendo a la cámara: capa 1 **idéntica** en la
  misma ventana. Precio: el fondo queda en 1 color por línea más el cielo
  (las montañas pasan a siluetas con degradado), y la paleta por línea tiene
  que cambiar con la cámara en X. Eso obliga a re-indexar los bloques por zona
  en el conversor. Sin prototipar.
- **Render del nivel entero con (c)** (2026-09-23): `work/d8_c_nivel.png`,
  comparado con (b) en `d8_b_vs_c.png` y `d8_b_vs_c_zoom.png`, ambos sin
  sprites. El fondo limpio se reconstruye con la moda de sus 10 repeticiones
  (período 512 px, 97.8 % de coincidencia). Terreno: 1 píxel distinto en todo
  el nivel. Fondo con el color de mínimo error por línea: **14 % de píxeles
  exactos**. Montañas, nubes y pilares se funden en una sola masa celeste por
  franja, sin contornos, sin sombreado y sin los puntos.

#### 7. Dos ideas más, medidas sobre los datos (2026-09-23)

- **Recomponer solo los bloques cuyo fondo cambia** (5 planos, fondo que se
  mueve 1 px): **90-115 de 224 bloques** por paso. W2 (160 bloques) ya costaba
  290 %. ✗
- **DPF + el copper cambiando colores a mitad de línea.** Es asignación de
  registros: 7 índices por línea y cada color vive entre su primer y su último
  uso. Si se puede reasignar un índice en un hueco de 16 px, **las 432 líneas
  caben en 7 colores vivos**. Con huecos de 32 px ya no caben 79 líneas. Pero
  una línea de cámara llega a necesitar **29 cargas de color**, y con 6 planos
  en lowres el copper da aprox. 1 MOVE cada 16 px, unas 16 por línea de 256 px
  (**estimado, sin medir**). Sería la única vía hacia la capa 1 1:1 **y** el
  fondo a 7 colores con paralaje. Queda sin cerrar hasta simularla con las
  restricciones reales del copper.

#### 8. Opción (d): DPF + recarga de colores a mitad de línea — simulada y medida (2026-09-23)

**Simulación** (`tools/dpfsplit.py`): índices de la capa 1 asignados **fijos
por posición del nivel** (coloreo de intervalos con 7 registros y derrame al
color más cercano). Por frame, el copper carga en el borrado el color inicial
de cada índice y a mitad de línea los que cambian, en ranuras cada 16 px con
±8 px de margen. Si una carga no entra, ese tramo se ve con el color anterior.
Capa 2: fondo limpio de período 512, con ≤ 7 colores por línea salvo una
línea que tiene 8.

| medida (gap 48, margen 8, cámara cada 1 px) | valor |
|---|---|
| capa 1, derrame fijo | 330 px de 359 010 (0.09 %) |
| capa 1, cargas que no entran | 0.010 % de los píxeles vistos; peor encuadre 114 px |
| cargas a mitad de línea | máx. 11 por línea (hay ~20 ranuras en 320 px) |
| cargas en el borrado (capa 1 + capa 2, solo lo que cambia) | máx. **8** (presupuesto 14); 0 líneas-frame por encima |
| peor frame, cargas a mitad de línea | 456 en 89 líneas |
| variantes de bloque por índices | 244 (22 KB + máscara) |
| nivel entero, (d) contra (b) | **346 px distintos de 2.2 M** |

Robusto: con gap 32-64 y margen 4-16 el error queda siempre < 0.2 %.
Renders: `work/d8d_g48m8_nivel.png`, `d8d_g48m8_worst.png`,
`d8d_g48m8_err.png` y `d8_b_vs_d.png`.

**Medida en la Amiga** (`player/copbench.s` + `tools/copbench_read.py`,
`a500.uae` cycle-exact, fetch de 336 px, DMA de sprites encendido):

| modo | separación entre MOVE en pantalla |
|---|---|
| 4 planos | 8 px (= Brian the Lion, calibración) |
| 5 planos | 8/12/12 px (~10.7) |
| **DPF 6 planos** | **16 px** (el supuesto de la simulación ✓) |

DPF 6 planos, pantalla de 320 px: **35 MOVE por línea**, de las que **14-15
caen entre el borde derecho y el izquierdo** de la línea siguiente.

Trampa encontrada al medir: en un WAIT, `or.w #$0f01,d0` también toca la
línea (byte alto). Para la posición h hay que usar `or.w #$000f`.

**Sin medir / abierto** (en orden de riesgo):
1. **Bobs (enemigos) en la capa 1**: necesitan índices libres en sus líneas.
   Los sprites de hardware quedan libres con los colores 16-31 (en DPF no
   los usa nadie): Mario puede ir 1:1 en un sprite adosado de 15 colores.
   Rex y Banzai Bill no entran todos en 8 sprites. Sin estudiar.
2. **CPU para regenerar la lista del copper**: 456 cargas en el peor frame;
   a 60-100 ciclos cada una, 20-32 % de frame (**estimado**).
3. Blitter: la capa 1 son 3 planos (antes 5) y la capa 2 no se blitea, pero
   6 planos le roban más ciclos durante la pantalla. Hay que re-medir W1/W3
   en DPF.
4. Chip RAM de la capa 2: 832 px (512 + pantalla) × ~328 líneas × 3 planos
   ≈ 100 KB.

#### 9. Opción (d): los objetos, con una partida real (2026-09-23)

**Datos**: el usuario jugó Yoshi's Island 1 en `smwrecomp` mientras
`tools/oamrec.py` + `tools/oambot.lua` grababan por el puerto Lua TCP la OAM
visible, la cámara y las ranuras de sprites de cada frame:
`work/oam_yi1.txt`, 2500 frames de translevel $29 sin huecos. Trampas del
protocolo, medidas: **cada valor devuelto se corta a 1024 caracteres, van
como máximo 16 valores por respuesta y hay una sola conexión a la vez** (una
segunda conexión rompe la primera). El mensaje de la intro también es modo $14
(translevel 0).

**Modelo Amiga**: 8 canales de 16 px, que dan 4 columnas adosadas de 15
colores (17-31) u 8 de 3 colores (cada par comparte 3). El copper corre cada
columna entre líneas (`SPRxPOS`) y recarga los colores 17-31 por línea.

| medida (`tools/oamstudy.py`, `tools/d8objs.py`, `tools/d8demote.py`) | valor |
|---|---|
| líneas con sprites que caben en ≤ 4 columnas | 98.3 % (2310 de 138 629 piden 5-6) |
| quién pide 5-6 columnas | siempre Banzai Bill (4) + Mario, a veces + Rex: 130 frames (5 %) |
| colores por línea de 16 px: Mario / Rex / Banzai / Piranha / Chuck | 4 / 6 / 6 / 5 / 7 |
| peor unión de una línea de Mario con una de cualquier enemigo | 11 (≤ 15 ✓) |
| Banzai en pares sin adosar (≤ 3 colores por franja de 32 px) | ✗: 42-63 de 63 líneas tienen más |
| líneas de 5-6 columnas que se resuelven pasando un objeto a bob en PF1 | 77.7 % (Banzai 61.6 %, Rex 25.8 %, Mario 21.6 %) |
| **frames que quedan con alguna línea sin resolver** | **45 de 2500 (1.8 %)** |

Contando los colores por paleta entera (Mario 11 + enemigo 7) salía que el
33 % de los frames se pasaba de 15. Contando por línea, que es lo que carga
el copper, no se pasa nunca.

**Diseño que sale de esto**: Mario y los enemigos van en sprites adosados, y
el copper recarga los colores 17-31 por línea. Cuando un Banzai Bill comparte
líneas con Mario y un Rex, uno de los tres (casi siempre el Banzai, que vuela
por aire donde el terreno deja registros libres) pasa a bob en PF1. En el
1.8 % restante el bob usa el color más cercano.

**Sin medir**: cuántas MOVE por línea piden las recargas de colores de los
sprites y de los bobs (hay ~6 libres en el borrado y ~9 a mitad de línea
después de la capa 1). Las filas de color de Rex y Banzai salen de la pose
de la referencia, no de cada frame.

#### 10. Opción (d): copper completo, CPU y blitter — simulado y medido (2026-09-23)

**Copper con todo junto** (`tools/copsim.py`, los 2500 frames de la partida,
560 000 líneas): capa 1 + capa 2 + colores de sprites + `SPRxPOS`.

| medida | peor línea | presupuesto |
|---|---|---|
| MOVE en el borrado | 9 | 14 |
| ranuras a mitad de línea | 10 | 16 (256 px) |
| cargas que no entran | 1916 en 492 frames: **todas de la capa 1** (las ventanas estrechas del punto 8); sprites y fondo no suman fallos | — |
| entradas por frame | media 432, máx. 857 (3.4 KB) | — |

Aproximación: las filas de color de Mario salen del bloque 16x32 con más
píxeles de su hoja de gráficos, no de su pose en cada frame.

**Medido en la Amiga** (`player/bench2.s` y sus variantes `bench2v.s` y
`bench2m.s`, `tools/bench2_read.py`, `a500.uae` cycle-exact, DPF 6 planos en
pantalla: capa 1 de 3 planos entrelazados + capa 2 de 3):

| carga | durante la pantalla | después de la última línea visible |
|---|---|---|
| W1 columna nueva, 14 bloques de 3 planos, copia directa | 5.6-6.4 % | 9.0-9.3 % |
| W2 lista del copper del peor frame, bucle por línea (224 WAIT + 633 MOVE) | **38.1 %** | 30.9 % |
| W2 misma lista copiada en bloque con `movem` | — | **15.1 %** |
| W3 bobs Banzai + 4 Rex, 3 planos (BLTPRI off / on) | 47.6 / 33.8 % | 26.2 / 22.7 % |

Con 5 planos (etapa 4) la columna costaba 27 % y los bobs 63/47 %: en DPF el
blitter trabaja con 3 planos y no compone el fondo.

**Lectura**:
- Lo que pesa en la lista del copper es la **CPU** (~52 ciclos por entrada,
  casi todo de la vuelta por línea), no la contención (+20 %).
- En la partida la cámara **no se movió nunca en vertical** y en horizontal
  se movió en el 57 % de los frames. Entre un frame y el siguiente solo
  cambian las líneas con cargas a mitad de línea (~19) y las que tienen
  sprites (~55).
- Diseño propuesto (**sin medir**): un segmento de copper por línea,
  encadenado con `COP2LCL` + `COPJMP2` (2 MOVE; `COP2LCH` fijo si toda la
  lista está en el mismo banco de 64 KB). Cada segmento tiene dos copias:
  la CPU reescribe solo las líneas que cambian, en la copia libre, y cambia
  el puntero de la línea anterior. Estimado: ~75 líneas × ~150 ciclos ≈ 8 %
  de frame.
- En (d) los enemigos van en sprites de hardware; W3 solo pesa en los
  frames que pasan un objeto a bob (punto 9).

**Presupuesto del peor frame, conservador** (BLTPRI encendido): lista del
copper 15 % (en bloque) + bobs 34 % + columna 9 % ≈ **58 %**, sin contar la
lógica del juego (etapas 8-9, sin medir), que es el siguiente riesgo.

Conclusión: los trucos de la época **confirman** el veredicto de D8, que no hay
1:1 de las dos capas con paralaje en el OCS. Además dejan una tercera opción
concreta: **(c) Robocod**, con la capa 1 1:1 y paralaje H+V real a cambio de
un fondo de 1 color por línea.

### D7 — cómo se cerró

La hipótesis "selección de paleta que no encontramos" era la buena, pero no es
por nivel sino **por pantalla**: `MAP16AppTable` (`lv_read.s:805`) tiene cuatro
versiones de las entradas `$133`-`$13A`, idénticas salvo la paleta (3, 5, 6, 7),
y el cargador de columnas elige `(columna >> 4) & 3`. Las tuberías de la
pantalla 7 de Yoshi's Island 1 caen en la variante 3 = paleta 7 = lavanda, que
es lo que muestra la referencia. Detalle en P28.

---

## Dónde quedó el trabajo (2026-09-24) — leer primero

**Etapa 8 en curso.** 8a (física de Mario: velocidad horizontal, gravedad y
saltos) está portada en `player/mario.c` y verificada contra el oráculo con
`tools/marioverify.c`:

- 6547 pares de frames verificados; ninguno toca código sin portar y 322 se
  saltan porque no corre la física normal.
- En el aire coinciden todos los campos en 2989 de 3497 frames; en el suelo,
  en 2962 de 3050.
- Los fallos que quedan son de partes todavía sin portar:

| causa | frames | parte que lo resuelve |
|---|---|---|
| giro (animación `CODE_00CEB1`) | 499 | portar `CODE_00CEB1` (opcional) |
| pared o techo | 21 | 8b |
| pendiente | 42 | 8c |
| encima de un sprite | 23 | etapa 9 |
| otros: 10 rebotes al pisar (`$D0`) y 1 golpe a un bloque (`$10`) | 11 | — |

**Paso siguiente, 8d (sin hacer):** medir en la Amiga el coste de 8a.

- `sh tools/logicbench_build.sh` genera `work/logicbench.adf`: vbcc con
  `-sc -sd -const-in-data` y todas las secciones fundidas en `CODE`. El
  binario ocupa 28.5 KB y cabe en el alcance de `a4` (32 KB). Ya se revisó
  el listado: no hay ninguna referencia absoluta.
- Ventanas: W1 = copiar el estado; W2 = estado "corriendo" (frame 5410) + 8a;
  W3 = estado "salto" (frame 10983) + 8a.
- Los estados se generan con
  `marioverify work/oracle_yi1.bin dump FRAME work/cc/state_run.bin` (o
  `state_jump.bin` para el frame 10983).
- Para correrlo y leerlo:
  `.\tools\shot.ps1 -Exact -Adf work\logicbench.adf -Out work\logicbench.png -Wait 80`
  y después `python tools/logicbench_read.py`. Coste de 8a = W2−W1 y W3−W1.
  Hay que anotarlo en §9.
- **`tools/logicbench_read.py` no se probó nunca.** Supone el mismo formato
  de captura que `bench2_read.py`; confirmarlo antes de creerle.

**Después:**

1. 8b: colisiones con bloques, con la tabla "acts like" del ROM.
2. 8c: pendientes. Antes, el usuario tiene que grabar una sesión en las
   colinas: a toda carrera en las dos direcciones, parado en la pendiente,
   deslizándose y saltando sobre pendientes. Se graba con
   `tools/oamrec.py --out` a un fichero **distinto** de `oracle_yi1`.
3. Etapas 5 y 6, ya desbloqueadas porque D8 = (d).

**Qué no está en git y cómo recuperarlo** (regla R9):

- `work/` no se versiona: ahí van la ROM, los oráculos grabados, los ADF y
  los renders.
- `player/gen/smwrom00.c` tampoco. Se regenera con `python tools/smwgen.py`,
  que necesita la ROM (U).
- En Claude cloud no hay ROM, ni WinUAE, ni `smwrecomp`, ni el oráculo
  grabado. Allí solo se puede leer y editar código: nada de verificar ni de
  medir. **8d, la verificación con `marioverify` y la grabación de las
  colinas tienen que correr en la PC local.**
- El grabador tiene límites que ya costaron partidas: 1024 caracteres por
  valor, 16 valores por respuesta y una sola conexión TCP. **Probar siempre
  el grabador antes de pedirle al usuario que juegue.**

## 10. Roadmap

Reordenado el 2026-09-22 con un criterio: **primero se mide en el hardware lo
que puede tumbar el proyecto, después se pule la fidelidad.** La versión
anterior dejaba perfecto el fondo en el PC (2c) antes de saber en qué formato
iba a existir en la Amiga, y ponía la prueba de rendimiento en cuarto lugar.

### Hecho

| Etapa | Contenido | Criterio | Estado |
|---|---|---|---|
| 1 | Pipeline de assets | 52/52 ficheros + round-trip OK + PNG verificados | **HECHO** |
| 1b | Paletas reales | CGRAM reconstruido emulando `LoadPalette` | **HECHO** |
| 2 | Parsear `.lv` → buffer Map16 | Volcar el nivel 105 como imagen legible | **HECHO** |
| 2b | Capa 1 1:1 | 92/92 objetos, `m16diff` 100 % **y** inspección visual del nivel entero | **HECHO** — 6111/6111; solo difieren píxeles bajo sprites |
| 3 | Esqueleto Amiga | ADF arranca (KS 1.2) y muestra el tileset estático | **HECHO**, pero **sin medida válida**: los "49.9 fps" son de la config rápida. Se re-mide en la etapa 4 |

### Pendiente

| Etapa | Contenido | Criterio de "hecho" | Cierra |
|---|---|---|---|
| **4** | **Prueba de viabilidad en `a500.uae`** (cycle-exact) | Tabla de costes medida en la Amiga + cómo se mueve la capa 2 | **HECHO** (2026-09-22) — ver "Etapa 4 — resultados" en §9. Cerró D1 y D9; D8 queda para el usuario con los datos. El scroll del **nivel real** no se hizo aquí (hace falta el conversor de la etapa 5): pasa a la etapa 6. `player/bench.s` + `tools/bench_read.py` |
| 5 | **Conversor de nivel → Amiga, formato (d)** | Capa 1: 3 planos con la asignación de índices de `dpfsplit.py` (244 variantes de bloque) + tablas del copper por línea del nivel (cargas en el borrado y a mitad de línea con su ventana). Capa 2: bitmap de 3 planos de período 512 px + paleta por línea. `render_dat.py` renderiza el blob en el PC aplicando las tablas y se compara contra `d8d_g48m8_nivel.png` y la referencia con `cmp_ref.py` | — |
| 6 | Scroll del nivel real en la Amiga | PF1 con `BPLCON1` bits 0-3 + columna nueva; PF2 con bits 4-7 a media velocidad (paralaje); lista del copper por frame (segmentos por línea encadenados, §9 punto 10). Recorre las 20 pantallas a 50 Hz; captura de WinUAE = render del PC en varios puntos; coste medido con el método de `bench2.s` | — |
| 7 | **Capa 2** | En (d) la hacen las etapas 5 y 6 (PF2 con scroll por hardware). Queda la verificación: recortes apilados contra `SuperMarioWorldMap02.png`, el diff tiene que bajar del 25.5 % | — |
| 8 | **Mario**, por partes verificadas bit a bit contra el oráculo `work/oracle_yi1.txt` (partida real grabada en `smwrecomp`: joypad + WRAM `$0000-$00FF` y `$13C0-$14FF` por frame): **8a** velocidad horizontal, gravedad y saltos; **8b** colisiones con bloques (tabla "acts like" del ROM); **8c** pendientes de 45° (hace falta grabar las colinas: a toda carrera, en las dos direcciones, parado encima y deslizándose); **8d** coste medido en la Amiga | Cada parte: el estado de Mario del port = el del oráculo en todos los frames de sus tramos | — |
| 9 | **Sprites del nivel** (D3): Rex, Banzai Bill, Jumping Piranha; después Chuck, Sliding Koopa, bloque volador, Info Box, meta | Aparecen en las posiciones de `spr.lv` y se comportan como en la SNES | — |
| 10 | HUD | Barra de estado con su propia paleta (copper) | — |
| 11 | Audio (D5) | Música del nivel + efectos, 4 canales | — |
| 12 | Pulido | Muerte, punto medio, meta, transiciones | — |

**La etapa 4 decide el proyecto.** Su resultado puede cambiar las etapas 5-7
(formato de los bloques, paleta, cómo se dibuja el fondo). Por eso va antes que
cualquier trabajo de fidelidad nuevo.

---

## 11. Verificación (definición de "hecho")

Ninguna etapa se marca como completada sin **las tres**:

1. **Test automático.** Para assets: `smw2amiga.py --selftest` debe dar
   `Auto-test planar: TODO OK`. Para código: un test que compare el estado
   de la física contra los valores esperados de las tablas de `player.s`.
2. **Evidencia visual.** Captura del emulador (o PNG de la pipeline) donde se
   distinga claramente lo que se pretendía dibujar. **Y para el nivel, comparar
   1:1 contra `SuperMarioWorldMap02.png`** (ver §5c): mismo recorte apilado,
   referencia arriba, nuestro render abajo.
3. **Medida de rendimiento.** Cuando aplique, ciclos por frame medidos con el
   contador del emulador. No se acepta "parece que va fluido".
   **Solo vale una medida hecha con `a500.uae`** (`cycle_exact=true`,
   `cpu_speed=real`, `immediate_blits=false`). El `.uae` que genera
   `build.ps1` para las capturas usa `cpu_speed=max` e `immediate_blits=true`:
   sirve para ver la imagen, **no** para medir tiempos.

### Regla de diagnóstico (aprendida a la mala)

Si algo sale "garbled" pero **en la posición correcta**, el problema está en la
cadena de indirección (orden de cuadrantes, página, paleta, índice), **nunca**
en la geometría. No tocar el código de posiciones: aislar el objeto, renderizar
su tabla/entrada aislada y comparar. En esta sesión las tuberías estaban en el
lugar exacto y fallaban tres cosas distintas de la indirección a la vez.

### Comprobaciones rápidas

```bash
# ¿la capa 1 sigue 1:1?  (regresion: tiene que dar 100 % y 0 erroneos)
$PY tools/mklvl.py --out work/level_final.png && $PY tools/m16diff.py
$PY tools/cmp_ref.py --mask none --bits 5      # hoy 25.52 %; baja solo con capa 2

# ¿cabe en chip RAM?
$PY -c "print('playfield', 272*224*4//8, 'B')"

# ¿el fichero convertido tiene el tamano esperado?
#   n_tiles * 8 filas * (cols*8/8) bytes * planos
```

---

## 12. Antipatrones prohibidos

- **Portar las 82.000 líneas de 65816.** No. Reimplementa el nivel 1.
- **Usar el CPU para dibujar píxeles.** Todo el dibujado va por blitter.
- **Poner gráficos en slow RAM.** El chipset no los verá (R2).
- **Asumir que existe scroll por hardware.** No existe (R5).
- **Asumir que el layout de paletas es un array plano.** No lo es (P1).
- **Usar `float`.** No hay FPU. Punto fijo 8.8.
- **Copiar código de `smwre`/`smwrecomp`.** No tienes sus fuentes.
- **Redistribuir assets derivados de la ROM.** (R9)

---

## 13. Nota legal

El decompilado exige poseer el juego original, y el propietario lo tiene.
Un port-demo personal no es un problema. Distribuir la ROM o los assets
convertidos (gráficos, música) **sí** sería redistribución de material con
copyright. Este proyecto es de uso personal.
