# AGENTS.md — Manual de implementación del port-demo SMW → Amiga 500

> Este fichero define **cómo trabajar** en este proyecto. Es el contrato entre
> quien implementa (persona o agente de IA) y el hardware objetivo.
> Para el *porqué* de cada decisión, lee primero **`PLAN.md`**.
>
> **Qué hacer ahora y en qué orden: `ROADMAP.md`** (plan a futuro por etapas
> y handoff vigente, 2026-09-26). Las secciones "Dónde quedó el trabajo" y
> "Handoff cloud → sesión local" de abajo son el detalle histórico del
> 2026-09-24.

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

**P33 — `wm_BlockXPos` guarda la Y y `wm_BlockYPos` la X.**
Los nombres del desensamblado están cambiados (`CODE_00F44D` pone la X de
Mario + desplazamiento en `wm_BlockYPos`). Lo mismo con `wm_BounceSprXLo`
(guarda la Y) y `wm_BounceSprYLo` (la X). En el port se transcribe tal cual,
con un comentario donde importa; "arreglar" los nombres rompe la
correspondencia con el ROM.

**P34 — Golpear un bloque cambia el MAPA después, en la fase de sprites.**
`CODE_028752` crea un "sprite de rebote" (4 ranuras, `wm_BounceSpr*`) y es
`CODE_02902D`, después de Mario, quien pone el bloque en sólido invisible
(`$152`) y, al terminar, el bloque final. Un bloque giratorio (`$11E`) queda
en `$048` (**atravesable**) durante 255 frames. Sin portar esto, Mario choca
con bloques que en el juego ya se pueden atravesar (fue la mayor fuente de
fallos de la 8b). Además, en los golpes de costado el rebote cambia la
`SpeedX` de Mario.

**P35 — Los gráficos de Mario se calculan ANTES que su física.**
`CODE_00A295`: cámara (`F6DB`) → `E2BD` (gráficos, con la posición del frame
anterior y la cámara nueva; calcula `MarioScrPosX/Y`) → `C47E` (física; la
colisión usa esas `MarioScrPosX/Y`) → sprites. Verificar los gráficos con el
estado del mismo frame da un frame de desfase.

**P36 — vbcc `-sd`: los datos tienen que estar a menos de 32 KB de `a4`.**
Cada dato se direcciona `simbolo(a4)` con desplazamiento de 16 bits y
`a4 = binstart`. `logicbench_build.sh` parte cada `.s` de vbcc en datos y
código e incluye primero todos los datos; el código y el mapa quedan
detrás y el arnés los llama con `binstart + desplazamiento` (un `bsr`
tampoco llega a más de 32 KB). Además, las etiquetas locales de vbcc
(`l12`...) se repiten entre ficheros: el build les pone un prefijo.

**P37 — vbcc incorpora en línea las funciones `static`.**
Con `-O=991` no dejan símbolo: un perfil por símbolo global atribuye sus
ciclos al global anterior. Para perfilar, `PROF=1 sh
tools/logicbench_build.sh` arma una variante sin inline y sin `static`
(`work/prof/`). **No** sirve para medir la 8d.

**P38 — vbcc `-O=991` puede sumar dos veces la base de un puntero.**
`u8 *p = ram + x; if (p[wm_SpriteDecTbl1]) p[wm_SpriteDecTbl1]--;` salió
como `lea 5440+_ram(a4),a1` + `add.l d0,a1` y después `subq.b #1,5440(a1)`
(y `tst.b 5452(a1)` para la tabla siguiente): cada byte, al doble de
desplazamiento. gcc lo compila bien, así que **`marioverify` no lo ve**: lo
vio `m68kverify` (el frame llegaba al tope de 10 M ciclos). Arreglo: el
puntero apunta a la primera tabla y los índices son relativos
(`p[wm_X - wm_SpriteDecTbl1]`). **Después de cada cambio en C, correr
`m68kverify` con el binario del 68000, no solo `marioverify`.**

**P39 — En DPF, un WAIT del copper gasta una ranura igual que un MOVE.**
Con 6 planos el copper tiene una ranura cada 16 px (§9 punto 8), y el
WAIT también la ocupa. Una simulación que cuente solo los MOVE (como
`dpfsplit.py`/`render_d.py`) promete cargas de color que la Amiga no
puede hacer: con 4-5 registros cambiando en 47 px, las cargas se retrasan
en cadena. Para cargas seguidas, un solo WAIT y después MOVE (con relleno
donde no hay carga).

**P40 — En 68000, `(An,Dn.w)` suma el índice CON signo.**
Una lista del copper de 224 × 220 bytes pasa de 32 767 en la línea 149:
con `(a1,d1.w)` las escrituras caen 64 KB antes (en `scroll.s`, las de la
lista B aterrizaban justo en la A, que por eso se veía bien). Para
desplazamientos que pueden pasar de 32 KB: `moveq #0,d1` + `move.w` +
`(a1,d1.l)`. Lo mismo con un array de registros de 16 bytes indexado por
un número de registro de más de 2047.

**P41 — Una captura de FS-UAE con tiempo fijo puede no estar donde se cree.**
AROS tarda ~35 s en arrancar y `scroll.s` avanza 2 px por frame: con 60 s de
espera, `-DSTOPX=3500` y `4500` se capturaban **antes de llegar** y
`scroll_check` daba ~35 000 fallos (la imagen era de otra parte del nivel).
Esperar **≥ 50 + STOPX/100 s**. `tools/regress.py` ya lo hace, y avisa si
una captura difiere en más del 20 % (posición equivocada, no fallo de
imagen). Descubierto el 2026-09-26; ver `ROADMAP.md` §8. En WinUAE con
KS 1.2 pasa lo mismo: `tools/shots6.ps1` espera 25 + STOPX/100 s.

**P42 — En DPF de 6 planos, el WAIT del copper tiene rejilla de 8 px, no de 4.**
Medido en WinUAE (`copcal.s -DPATTERN`, `COPCAL_FINE=1`, h de a 2): el
MOVE después de `WAIT h` cambia el color en
**x = 8·⌊(h − $38)/4⌋ − 1** hasta h = `$D0` (x = 303), y después en
x = 303 + (h − `$D0`). `h = $40` y `$42` dan los dos x = 15; `$44` y `$46`,
x = 23. Con 6 planos el copper solo tiene una ranura cada 4 cc. `BPLCON1`
no mueve el cambio, y con `BPLCON1` = 0 el píxel 0 de la palabra cae justo
en el borde de la DIW (el scroll de `scroll.s` es correcto). `copcal` solo
había medido h múltiplos de 8 (error de 1 px) y el modelo x = 2·(h − $38)
fallaba por **5 px** con h ≡ 2 (mod 4): era el adelanto "sin explicar" que
tapaba `WOFS` = 8. Para caer en x ≥ objetivo: q = (objetivo + 8) >> 3,
h = $38 + 4q (cabecera de `scroll.s`). Además, como el camino rápido de
`build_mid` mueve el WAIT con la cámara y su fase en la rejilla cambia, los
MOVE sin WAIT que lo siguen se deciden con la **cota inferior** (el
objetivo), no con la x real de ese frame.

**P43 — El borrado deja al copper libre ~60 px ANTES de x = 0.**
El borrado de la línea L empieza en (L − 1, `$E2`): en el borrado
horizontal no hay DMA de planos y los 7 MOVE terminan mucho antes de x = 0.
`build_mid` suponía T = 0 al empezar las cargas de la línea: una carga
cuyo tramo anterior todavía se veía en x = 1..40 salía sin WAIT (o con 1-2
MOVE de relleno) y caía **antes de x = 0**. Síntoma: los objetos que salen
por la izquierda se pintan con los colores del objeto siguiente (tubo
diagonal con franjas de tierra en s = 846, caja de piedras verde en
s = 1936; lo vio el usuario en movimiento). Las capturas con el scroll
parado en las 6 x de siempre no lo veían porque ahí no hay un objeto
saliendo por el borde. Arreglo: T = `TLINE` (−64) al empezar la línea, así
la primera carga de cada línea lleva WAIT. `tools/scrollsim.py` simula la
lista del copper en **cada frame** del recorrido con este modelo (T0 = −56).

**P46 — A 256 px (DIW `$2CA1`, fetch `$40`-`$C0`) el copper es otro modelo.**
Medido en WinUAE (`copcal.s -DW256 -DPATTERN`, `COPCAL_W256=1..3`): la
rejilla de 8 px de P42 corrida a h − `$48` (x = 8·⌊(h − `$48`)/4⌋ − 1)
hasta h = `$C0` (x = 239) y, al terminar el fetch, `$C4` → 243,
`$C8` → 247, `$CC` → 251, `$CE` → 255; desde `$D0` ya está fuera de la
pantalla. **Cada cambio de DIW o de fetch pide recalibrar** con `copcal`.

**P44 — Los "derrames" de la etapa 5 alargan el tramo anterior.**
`mkleveld.py` asigna los píxeles que quedan fuera de todo tramo al registro
que *todavía conserva* el color: después del fin de un tramo puede haber
píxeles de ese registro que necesitan el color viejo (línea 152, COLOR01:
tramo hasta x = 4571, píxel en 4579). `mkscroll.py` liberaba la carga en
el fin del tramo y el copper, legal según los datos, la ponía encima. Ahora
la carga (y el cambio del borrado) se libera después del último píxel del
registro antes del tramo nuevo. Coste: ventanas más cortas, más cargas con
WAIT (en el plan, 9 de 3409 no llegan, antes 2).

**P45 — Una carga cortada por `LASTX` tiene que bajar el `vu` de la línea.**
Si `.mv` abandonaba una carga con x > `LASTX` sin tocar el `vu`, la línea no
se volvía a mirar cuando la carga entraba en pantalla y las de detrás
quedaban sin escribir (s = 4346, línea 162: 4 de 6).

Con P42-P45 (`tools/scrollsim.py --speed 2`, todo el recorrido): 298 060 px
de la capa 1 con el color mal → **19 586** (−93 %), peor frame 5409 → 194
px. Lo que queda son los postes de la meta (muchos colores en pocos px:
ancho de banda del copper) y puntos sueltos.

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

## 9. Decisiones

| ID | Decisión | Opciones | Estado |
|---|---|---|---|
| D1 | Compromiso de scroll/color/frecuencia | **1 px (`BPLCON1`) / 5 planos, 31 colores / 50 Hz** | **cerrado** con la etapa 4: scroll + 5 bobs = 48-68 % del frame. Queda por medir la lógica de juego (etapas 8-9); si no entra, 25 Hz |
| D2 | Nivel objetivo | **Yoshi's Island 1** (`world_1/1/`) | cerrado |
| **D3** | Enemigos del demo | Los que tiene el nivel de verdad (`spr.lv`, ver abajo). **Goomba y Koopa Troopa NO aparecen en Yoshi's Island 1** | **corregido** — mínimo: Rex + Banzai Bill + Jumping Piranha |
| D4 | Lenguaje principal | C para lógica + asm para hardware | cerrado |
| **D5** | Música | **secuenciador propio** sobre las secuencias N-SPC convertidas offline (no MOD), sin mezcla por CPU, 3 voces de música + 1 de efectos, ≤ 64 KB de muestras, ≤ 3 % de CPU | **cerrado** (usuario, 2026-09-26); detalle en `ROADMAP.md` §3 |
| D6 | Arranque | **bootblock propio** leyendo sectores crudos; funciona en KS 1.2 y 1.3 | cerrado |
| D7 | Color de las tuberías verticales | — | **cerrado**: depende de la pantalla (`MAP16AppTable`), ver P28 |
| **D8** | Cómo existe la capa 2 (fondo) en la Amiga | **(d) dual playfield + recarga de colores a mitad de línea con el copper**: capa 1 = PF1 (3 planos, índices fijos por línea del nivel), capa 2 = PF2 (3 planos, paralaje por hardware), Mario y enemigos = sprites de hardware con colores 17-31 recargados por línea, bob en PF1 cuando hay más de 4 columnas. Las demás opciones y sus medidas, en §9 "Etapa 4 — resultados" puntos 4-10 | **cerrado** (usuario, 2026-09-23) |
| D9 | Presupuesto de color | Vista real: **25 colores por línea, 40 por pantalla** (capas + sprites) | **cerrado**: 5 planos + paleta recargada por bandas con el copper. Ojo con P32 (los sprites comparten los colores 16-31) |
| **D10** | Ancho de pantalla | **256 px**, como la SNES (el scroll de hoy muestra 320) | **cerrado** (usuario, 2026-09-26): encuadre y aparición de enemigos 1:1, vuelve el sprite 7, 20 % menos de DMA |
| **D11** | HUD | **superpuesto (overlay)** con el copper sobre PF1 | **cerrado** (usuario, 2026-09-26), "si se puede": ver `ROADMAP.md` Etapa 10 |
| **D12** | Power-ups | **todos los de Yoshi's Island 1**: seta, flor + bolas de fuego, estrella, 1-UP, luna 3-UP, champiñón invisible (no hay pluma en el nivel) | **cerrado** (usuario, 2026-09-26) |
| **D13** | Carga y memoria | loader propio con `trackdisk`; lo que lee el chipset a chip RAM y el código y los datos de CPU a `$C00000`, todo en **direcciones fijas enlazadas en absoluto** (vlink) | **cerrado** (usuario, 2026-09-26); esquema en `ROADMAP.md` §3 |
| **D14** | Controles | **teclado primero** (flechas, Z = B, X = A, A = Y, S = X, Return = Start, Shift der. = Select), joystick como alternativa | **cerrado** (usuario, 2026-09-26) |

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

## Dónde quedó el trabajo (2026-09-24, tarde)

> Superado por `ROADMAP.md` §1 (handoff del 2026-09-26). Se deja como detalle
> de lo medido y de los comandos.

**Etapa 8: el frame entero del jugador está portado y verificado contra el
oráculo**, en el PC y en el binario 68000 real. Todo corre en Claude cloud
(ver más abajo).

| parte | fichero | rutinas del ROM | verificación |
|---|---|---|---|
| 8a física | `player/mario.c` | `D5F2`, `D062`, `D7E4` | `marioverify` (modo 8a) |
| 8b colisión con la capa 1 | `player/mcoll.c` | `CD24`: `DC2D`, `E92B` (sondas, pendientes, bloques), `F595`; `GenerateTile`; bloques que rebotan `CODE_028752` / `CODE_02902D` | `marioverify ... full` |
| frame del jugador + animación | `player/manim.c` | `C500` (temporizadores), `ResetAni`, scroll L/R `CDDD`, `CEB1` | `marioverify ... full` |
| gráficos de Mario | `player/mgfx.c` | `E2BD`, `E45D`, `F636` | `marioverify ... gfx` |
| cámara + frame de nivel | `player/mcam.c`, `level_frame()` en `manim.c` | `F6DB` (`F7F4`, `F8AB`), principio de `01808C`, orden de `A295` | `marioverify ... loop` |

Resultados (`work/oracle_yi1.txt`, 6547 pares de frames de Yoshi's Island 1):

- **`full`: 6510 / 6547 pares exactos en 24 campos** (posición, subpíxel,
  velocidades, `$77`, suelo, `$72`, pendientes, dirección, agachado, carrera,
  giro, `FrameB`, pose, paso, temporizadores de animación, capa). De N+1 solo
  se toman las **entradas**: joypad, `FrameA` y la cámara (`$1A-$1D`, que
  todavía no está portada). Los 37 que fallan son **todos contacto con
  sprites** (etapa 9): 23 sobre un sprite sólido y 14 al pisar o golpear un
  enemigo (`SpeedY` = `$D0` / `$10`).
- **`gfx`: 6869 / 6869 frames con la OAM de Mario y `MarioScrPosX/Y`
  exactas** (13 432 entradas de OAM en 6718 frames con Mario visible).
- **`loop` (lazo cerrado): el port reproduce la partida él solo**, desde el
  primer frame de cada tramo y recibiendo **solo el joypad** (la cámara, el
  `FrameA`, todo lo demás lo calcula). Tramo más largo: **1240 frames
  seguidos idénticos** (~25 s). Se resincroniza 37 veces en 6547 frames:
  exactamente los contactos con sprites. El binario 68000 da lo mismo.
- Las pendientes de la partida (42 frames que antes fallaban) ya salen
  exactas: buena parte de la **8c** está hecha, pero falta la grabación de
  las colinas para darla por cerrada.
- **El binario 68000 de vbcc da exactamente lo mismo que el C del PC**
  (`tools/m68kverify.py`, Unicorn y Musashi).

Coste estimado de un frame de nivel sin sprites (`level_frame`: cámara,
`E2BD`, jugador, bloques) en un 68000 **sin esperas de DMA** (Musashi):
**34 529 ciclos de media = 24,3 % de un frame PAL; peor frame 38 712 =
27,3 %**. Solo el jugador (`E2BD` + `mario_player` + `blocks_update`): 26 674
de media (18,8 %). Con
el DMA de 6 planos será más. Dónde se va (`tools/m68kprof.py`): las sondas
de colisión (`f44d` + `f461` + `f545`, 5,5 por frame) ≈ 28 %, las 4 entradas
de OAM (`e45d`) ≈ 12 %, `E2BD` ≈ 9 %, los bucles de temporizadores de
`mario_player` ≈ 8 %. Es código "emulador" (valores de 16 bits armados byte
a byte en `ram[]` little-endian): hay margen de optimización, y el
verificador asegura que no se rompe nada.

**8d, MEDIDA (2026-09-24, en cloud con FS-UAE cycle-exact):** un frame de
nivel sin sprites (`level_frame`: cámara + gráficos + jugador + bloques),
con la pantalla DPF de 6 planos encendida y el código en chip RAM:

| estado | ticks CIA | ciclos | % de un frame PAL |
|---|---|---|---|
| corriendo (frame 5410) | 4857 | ~48 600 | **34,2 %** |
| empieza un salto (frame 10983) | 5065 | ~50 700 | **35,6 %** |

Musashi, sin DMA, estimaba 24,3 % de media: el resto es contención (DMA de
6 planos, código en chip RAM).

Primera ronda de optimización (sin cambiar la semántica: el verificador en
PC y en 68000 sigue exacto): tablas del ROM con índice de 8 bits
(`T8X`/`T16X`), temporizadores y OAM por puntero, las sondas pasan X/Y en
variables. **Queda en 31,6 % corriendo y 32,9 % saltando** (Musashi: 31 972
ciclos, −7,4 %). Lo que queda ya no son descuidos: es el precio de emular la
RAM de la SNES byte a byte (cada valor de 16 bits son 2 lecturas + `lsl` +
`or`, ~50 ciclos) y de las tablas leídas de a bytes.

**Implicación para D1 (decisión del usuario):** el presupuesto conservador
del peor frame de vídeo era 58 % (§9 punto 10); con el jugador (~33 %) ya
son ~91 %, y faltan los sprites (etapa 9: 18 Rex, Banzai Bill...). A 50 Hz
no entra sin una optimización de otro nivel. Opciones: (1) reescribir las
rutinas calientes con el estado de Mario en variables nativas del 68000 (y
seguir verificando contra el oráculo), (2) bajar a 25 Hz (lógica cada 2
frames: la previsión de §9 D1), (3) ensamblador a mano en las sondas y la
OAM. Mover el código a slow RAM no ayuda (P29). Se repite con:

```bash
sh tools/logicbench_build.sh && sh tools/fsuae_shot.sh work/logicbench.adf work/logicbench.png 30
python3 tools/logicbench_read.py --shot work/logicbench.png --auto
```

**FS-UAE en cloud (`tools/fsuae_shot.sh`) sustituye a WinUAE para medir.**
A500 por defecto de FS-UAE = cycle-exact (`cpu_cycle_exact`,
`blitter_cycle_exact`, `cpu_speed=real`, `immediate_blits=false`), 512 KB
chip + 512 KB slow; sin Kickstart propio usa el AROS que trae dentro, que
arranca nuestro bootblock (lo que se mide toma la máquina después).
Validación: `bench2.s` da W1 5,5-6,2 %, W2 38,1 %, W3 47,5/33,7 %, contra
5,6-6,4 / 38,1 / 47,6-33,8 % en WinUAE; la calibración, 14 210 ticks por
frame, es la misma. Las capturas salen a ×2,125: los `*_read.py` tienen
`--auto`, que encuentra la rejilla de bits por las palabras de sincronía.
**Lo que no sirve para probar en FS-UAE+AROS: el arranque en KS 1.2.**

**Después (todo se puede hacer en cloud):**

1. Optimizar el frame del jugador con el verificador como red (`marioverify
   full/loop`, `m68kverify`) y midiendo con FS-UAE: sondas de colisión,
   `e45d`, temporizadores, cámara.
2. Etapa 6: el scroll en la Amiga con el blob de la etapa 5
   (`work/yi1_d.dat`, formato en la cabecera de `tools/mkleveld.py`) y la
   cámara ya portada (`player/mcam.c`).
3. Etapa 9 (sprites): son los 37 frames que faltan en `full` y `loop`.
4. 8c: el usuario graba las colinas (ver el grabador más abajo).

**En Claude cloud, primero correr `sh tools/setup_cloud.sh`** (~15 s). Deja
todo listo para compilar **y verificar**:

- vasm y vbcc para el 68000, desde espejos de GitHub (la red del entorno no
  deja bajar de `sun.hasenbraten.de` ni de `phoenix.owl.de`);
- las librerías de Python (numpy, pillow, scipy);
- el fuente de SMW, clonado desde https://github.com/galaxyhaxz/smw-src en
  `../../smw-src-master`, que es donde lo busca `smwgen.py`;
- **la ROM (U), ensamblada desde ese fuente** en `work/smw.sfc`: WLA-DX del
  2016-07-29 (misma fecha que el `wla-65816.exe` de smw-src) con `DL` en
  `.ENUM`, más `tools/smwsrc_wla.py`, que traduce las etiquetas `@` y el
  `.ASC "...\n"` de la WLA modificada. El script comprueba **CRC32
  `B19ED489`** = Super Mario World (U) [!];
- `player/gen/*`, el mapa `work/yi1_map16.bin` (`tools/mkmapbin.py`),
  `work/oracle_yi1.bin` + `work/oracle_yi1_oam.bin`, `work/marioverify` (y
  `work/mvtrace`, con traza de las sondas) y los estados de `logicbench`;
- Unicorn y machine68k (Musashi) para `tools/m68kverify.py` y
  `tools/m68kprof.py`.

Comprobaciones (todas en cloud):

```bash
work/marioverify work/oracle_yi1.bin            # 8a sola (modo híbrido antiguo)
work/marioverify work/oracle_yi1.bin full       # frame del jugador: 6510/6547
work/marioverify work/oracle_yi1.bin gfx        # gráficos de Mario: 6869/6869
work/marioverify work/oracle_yi1.bin loop       # lazo cerrado: 37 resincronizaciones (sprites)
work/marioverify work/oracle_yi1.bin sprload    # cargador de sprites: 20/20
work/marioverify work/oracle_yi1.bin sprloop    # Rex en lazo cerrado: 2411/2412
work/marioverify work/oracle_yi1.bin game       # Mario + Rex: 26 resincronizaciones, tramo 2711
python3 tools/m68kverify.py --engine musashi --mode loop   # lo mismo en 68000 + ciclos
python3 tools/mkbg.py && python3 tools/mkd8in.py && python3 tools/mkleveld.py && python3 tools/render_d.py
FULL_FRAME=11180 work/mvtrace work/oracle_yi1.bin full   # un frame, con las sondas
sh tools/logicbench_build.sh                    # (VBCC=~/vbcc) binario 68000 + ADF
python3 tools/m68kverify.py --engine musashi    # el binario 68000 contra el oráculo + ciclos
PROF=1 sh tools/logicbench_build.sh && python3 tools/m68kprof.py   # perfil por función
```

Comprobado el 2026-09-24 en cloud: `marioverify` (modo 8a) da exactamente
los números del handoff de la PC (2989/3497 en el aire, 2962/3050 en el
suelo) y `logicbench_build.sh` arma el ADF.

**Qué no está en git y cómo recuperarlo** (regla R9):

- `work/` no se versiona (salvo `oracle_*.txt` y `oam_*.txt`): ahí van la
  ROM, los `.bin` del oráculo, los ADF y los renders.
- `player/gen/smwrom00.c` tampoco. Se regenera con `python tools/smwgen.py`,
  que necesita la ROM (U).
- En Claude cloud no hay WinUAE, ni KS 1.2, ni `smwrecomp`: se compila, se
  verifica contra el oráculo y **se mide con FS-UAE + AROS**; lo que queda
  para la PC local es grabar partidas (8c: las colinas) y probar el
  arranque en KS 1.2.
- El grabador tiene límites que ya costaron partidas: 1024 caracteres por
  valor, 16 valores por respuesta y una sola conexión TCP. **Probar siempre
  el grabador antes de pedirle al usuario que juegue.**

## Handoff cloud → sesión local (2026-09-24) — para el agente en la PC

Esta sesión de Claude cloud trabajó en la rama `claude/agents-md-x4v1di`.
Antes de nada: `git fetch && git checkout claude/agents-md-x4v1di` (o
mergearla), y leer "Dónde quedó el trabajo" justo arriba.

**Actualización (2026-09-24, 14:10 UTC) — optimización (cierre de sesión, LEER PRIMERO)**

Hecho y **commiteado**:
- `build_mid`: las cargas a mitad de línea quedan **fijas en pantalla**
  mientras valen (`vu` = mínimo de `principio del tramo nuevo − x − VMARG`,
  `wake` = `vu`; sin camino rápido por frame). Musashi: **29 800 → 16 300
  ciclos** por frame, imagen igual o mejor (fallos que no se explican por
  un vecino: 1000: 31, 1700: 91, 2500: 46, 4500: 127).

En el árbol **SIN commitear** (`player/scroll.s`; ensambla, **sin
verificar en imagen ni medir en FS-UAE**):
- escaneo de `wake` por bloques de 16 líneas con su mínimo (`gmin_a/b`):
  Musashi 16 300 → **13 400** ciclos;
- `blit_steps`: la columna nueva repartida entre frames (`BLITS` = 4 pasos
  por frame; paso 14 = la segunda copia). Busca bajar el pico de los
  frames con columna (hoy 42 % contra 33 %). `blit_column` quedó sin uso.
- Para cerrarlo: `scroll_check.py --mid` en x = 1000/1700/2500/4500 y
  `-DBENCH -DSPEED=4` + `scroll_read.py --auto`; si todo está bien,
  commit. Perfil por zonas de `build_mid` en Musashi: el script estaba en
  `/tmp/b/me_prof.py` (se pierde con el contenedor; rehacerlo con
  `tools/m68kverify.MusashiCPU` y el listado `-L`).

**Dos subagentes quedaron trabajando al cerrar** (sus cambios están en el
árbol, **sin commitear y sin revisar**):
1. Optimización del frame de Mario + sprites en C (`player/manim.c`,
   `mario.c`, `mcam.c`, `mcoll.c`, `mgfx.c`, `msprite.c`, `smwmac.h`).
   Criterio de aceptación: `marioverify` full/gfx/loop/game/sprloop
   idénticos a la base (full 3557/3573 2953/2974, gfx 6869/6869, loop 37,
   game 1 resincronización) y `m68kverify --mode loop` (37) y
   `--sprites` (4) iguales; base de ciclos: 31 100 / 44 400 (Musashi).
   **Revisar con `git diff` y correr todo eso antes de commitear**; si algo
   no cuadra, `git checkout` de esos ficheros.
2. La causa del adelanto de ~5 px de las cargas con WAIT en el scroll
   (hoy tapado con `WOFS` = 8), con `player/copcal.s` + `tools/copcal.py`
   (modificados en el árbol): hipótesis, el retardo de `BPLCON1` o la
   escala de la captura. Si no dejó conclusión, repetir el experimento
   (bandas con distinto `BPLCON1` y contenido de franjas de 1 px).

**Actualización (2026-09-24, 13:40 UTC) — etapa 6: copper calibrado, franja arreglada**

1. **Calibración del copper** (`player/copcal.s` + `tools/copcal.py`, en la
   pantalla del scroll: DPF de 6 planos, fetch `$30`-`$D0`, sin sprites):

   | medida | valor |
   |---|---|
   | h → x de pantalla (WAIT + MOVE, copper libre) | x = 2·(h − `$38`) hasta h = `$D0` (x = 303); después **1 px por h** (`$D4` → 307, `$DC` → 315, `$E0` ya fuera) |
   | MOVE seguidos | uno cada 16 px |
   | un WAIT, aunque ya haya pasado | **32 px** (WAIT + MOVE = 48 px) |
   | borrado de 2 WAIT + 14 MOVE en (v, `$07`) | termina en x ≈ 64-79 |
   | borrado en (v−1, `$E2`): 7 MOVE / 14 MOVE | termina antes de x = 0 / en x ≈ 32 |

   `copcal.py gen` genera `work/copcal_lines.i`; con `COPCAL_RIGHT=1`,
   las pruebas del borde derecho.
2. **`scroll.s` con ese modelo:** `HOFS` = `$38` (antes `$40`: todo caía 16
   px tarde), con el quiebre de x > 304; la h se redondea **hacia arriba**
   (va de 4 en 4 px; redondear hacia abajo escribía hasta 3 px antes de
   que termine el tramo anterior); borrado en (v−1, `$E2`) con los 7 de PF1
   y **solo los de PF2 que cambian**; cargas colocadas con el tiempo T del
   copper (MOVE si ya se puede, 1-2 MOVE de relleno a `$1FE` si falta ≤ 32
   px, WAIT si no); ninguna carga después de x = 316.
3. **`mkscroll.py` planifica** las cargas por plazo con el mismo modelo (2 de
   3409 llegan tarde) y guarda la x planificada: MLD de 16 bytes.
4. **Tres bugs de verdad** (P40): `apply_colors` indexaba con 16 bits con
   signo (desde la línea 149 las escrituras de la lista B caían en la A);
   al ordenar por x planificada, las cargas caducadas detrás de una viva
   se seguían emitiendo; y "la línea tenía cargas" contaba solo los WAIT
   (las líneas con cargas sin WAIT no se limpiaban).

Fallos limpios contra el esperado, en 6 puntos del nivel (FS-UAE):

| x | antes | ahora |
|---|---|---|
| 500 | — | 132 (0,18 %) |
| 1000 | 268 | **45 (0,06 %)** |
| 1700 | 1025 (la franja) | **116 (0,16 %)** |
| 2500 | — | **52 (0,07 %)** |
| 3500 | — | 163 (0,23 %) |
| 4500 | — | 635 (0,89 %): a la vista iguales; son bordes verticales de las montañas de la capa 2 (muestreo de la captura ×2,125) |

Descontando el muestreo (`scroll_check.py` imprime también los fallos que
no se explican por un vecino, ±1 px, ±1 línea): 500 → 74, 1000 → 45,
1700 → 113, 2500 → 18, 3500 → 72, 4500 → 172. **Todos < 0,25 %.** Lo que
queda son marcas sueltas en bordes de tubería y escalón.

Coste (`-DBENCH`): 33,9 % sin columna, 42,5 % con columna (igual que antes).

**Después (13:58):** el usuario vio en la captura de x = 4500 la piedra
gris sin su esquina y marcas de colores en la tierra, junto al escalón.
Causa: **en el scroll, las cargas con WAIT caían ~5 px antes** de lo que
dice `copcal` (el tramo anterior todavía se veía). Sin explicar (¿el
retardo de `BPLCON1`? ¿escala de la captura?); corregido de forma empírica
con `WOFS` = 8 (los WAIT, 8 px más tarde): la piedra sale entera y queda
un solo punto en la tierra. Fallos que no se explican por un vecino:
1700 → 98, 2500 → 44, 4500 → 126. **Pendiente:** entender los 5 px con
`copcal` a distintos retardos de `BPLCON1`.
También: `build_mid` no hace nada si la cámara no se movió desde la
última vez que se escribió esa lista, y tablas L·SEG / L·SHSZ en vez de
`mulu` (coste con scroll continuo: 33 % / 42 %, casi igual).
**Criterio del usuario: priorizar lo que se nota a simple vista**; el
magenta del fondo en `scroll_check` es casi todo reescalado.

**Siguiente (etapa 6):** bajar el coste de `build_mid`; cámara hacia la izquierda;
conectar `mcam.c`. Para dar la imagen por cerrada, comparar en la PC con
capturas de WinUAE sin reescalar (el ×2,125 de FS-UAE ensucia los bordes).

**Actualización (2026-09-24, 13:00 UTC) — etapa 6, segunda hora**

1. **Cargas de color a mitad de línea: hechas.** `mkscroll.py` guarda por
   línea las cargas en coordenadas del nivel (MLX/MLD). En `scroll.s`
   cada línea es un **segmento** de copper de 172 bytes y largo variable:
   2 WAIT + 14 MOVE del borrado + hasta 12 cargas (WAIT + MOVE) + salto
   al segmento siguiente (`COP2LCH`/`COP2LCL`/`COPJMP2`), así los huecos
   no le cuestan tiempo al copper. Dos listas: la CPU escribe una mientras
   se ve la otra y cambia `COP1LC`. Una carga a menos de 16 px de la
   anterior va sin WAIT: en DPF el copper tiene una ranura cada 16 px y
   **un WAIT gasta ranuras igual que un MOVE**. Sin eso la tercera carga
   seguida llegaba tarde (líneas sueltas de otro color en las pendientes).
   `scroll_check.py` cuenta ahora los **fallos limpios** (color OCS exacto
   y distinto; las mezclas son del reescalado de la captura): **273 px
   (0,38 %) contra el esperado con las cargas**, 952 contra el de solo
   borrado.
2. **Columna nueva por blitter: hecha** (`blit_column`): un blit por
   bloque (1 palabra × 48 filas: 16 líneas × 3 planos a `ROWB1`) y la
   segunda copia de una vez (1 × 672). Misma imagen que con la CPU. El
   dibujo inicial sigue con la CPU (el SO todavía es dueño del blitter).
3. **Coste medido** (`-DBENCH`, CIA-B, FS-UAE cycle-exact, 4 px/frame,
   1200 frames; `tools/scroll_read.py --auto`):

   | versión | sin columna, media | con columna, media |
   |---|---|---|
   | sin `build_mid` (`-DNOMID`) | 1,2 % | 7,1 % |
   | `build_mid` recalculando todo cada frame | 83,5 % | 104,2 % |
   | + atajo de líneas sin cargas (`nxt`) | **73,2 %** | **90,1 %** |

   El máximo (~250 %) es el primer frame (`lo_tab` avanza desde 0).
   Musashi (sin DMA): `build_mid` = ~72 000 ciclos de media; en x=1004,
   224 líneas, 66 por el camino completo, ~760 ciclos cada una. **Es
   CPU, no contención.** Con esto el scroll no entra en 50 Hz junto al
   jugador.

**Después, en la misma hora (13:00 UTC):**

- **`build_mid` incremental: hecho.** Por lista y por línea una sombra:
  `vu` (hasta qué `s` vale la estructura: sale la carga más vieja, entra
  una por la derecha o empieza a verse una saltada) y, por cada WAIT, su
  posición en el segmento y su x objetivo; con `s < vu` solo se
  recalculan las h. Más un array `wake[L]` por lista (0 si la línea tiene
  cargas escritas, `vu` si no) que un bucle mínimo recorre para entrar
  solo en las líneas que hacen falta (~26 de 224).
- La columna nueva va **lo primero** del frame, en el borrado vertical:
  ahí el blitter tiene el bus, y la copia de 672 filas corre mientras la
  CPU hace `build_mid`.
- Objetivo de cada carga: **fin del tramo anterior + 5 px** (`TXOFS`), no
  el centro de la ventana. Si cambian varios registros juntos, cada MOVE
  llega 16 px después del anterior.

| `build_mid` | Musashi (sin DMA) | FS-UAE, sin columna | con columna |
|---|---|---|---|
| recalcular todo | ~80 000 ciclos | 83,5 % | 104,2 % |
| + atajo de líneas sin cargas | ~72 000 | 73,2 % | 90,1 % |
| incremental (sombras) | ~37 000 | 35,0 % | 52,9 % |
| + columna primero | — | 35,0 % | 44,7 % |
| + `wake` | ~29 000 | **33,0 %** | **43,1 %** |

Imagen: x = 1000 → **268 px de fallo limpio (0,37 %)**; x = 1700 →
**1025 px (1,43 %)**, casi todo en una **franja de ~16 líneas justo encima
del suelo**: la parte de abajo de las tuberías lavanda sale verde, el
arbusto gris, la base de los bloques de cemento mal. **No es del camino
incremental**: la versión que recalcula todo da lo mismo (1093 px). Ahí
tres registros cambian dentro de una ventana estrecha (~27 px entre el
arbusto y la tubería). Sospechas, sin comprobar:
1. la colocación de las cargas no hace el reparto por plazo en ranuras de
   16 px que usan `dpfsplit.py`/`render_d.py` (para ellos solo falla el
   0,018 %): hay que precalcularlo en `mkscroll.py` y guardar la x
   objetivo en MLD;
2. el borrado (2 WAIT + 14 MOVE) empieza en h = `$07` de cada línea. En
   DPF el copper solo tiene libres 14-15 MOVE entre el borde derecho y el
   izquierdo (§9 punto 8), y así pierde el tramo del borde derecho de la
   línea anterior: las últimas cargas del borrado caen ya dentro de la
   pantalla.

**Causa de la franja, encontrada (13:05):** en la línea 182 (x = 1700), entre
x = 66 y x = 113 (47 px de ventana) tienen que cambiar 4-5 registros. En
DPF el copper tiene **una ranura cada 16 px y un WAIT gasta una ranura
igual que un MOVE**: WAIT + 4 MOVE = 5 ranuras ≈ 80 px > 47. Las cargas se
retrasan en cadena (el `$88C` del registro 2 aparece en x = 255 en vez de
115). **`dpfsplit.py`/`render_d.py` solo contaban los MOVE, no los WAIT**:
por eso daban 0,018 % de fallos. Es un error del modelo de la etapa 5,
no del scroll. (Probado y descartado: empezar el borrado al final de la
línea anterior, WAIT (v−1, `$E2`): no cambia nada.)

Dos salidas:
- **(a)** Un flujo de MOVE **sin WAIT intermedios**: después del primer
  WAIT, cada carga en su ranura de 16 px, con MOVE de relleno a un
  registro inocuo donde no hay carga. Cada carga cuesta una ranura, como
  suponía la simulación. Las posiciones relativas no cambian con la
  cámara (solo la fase `s mod 16` y lo que entra o sale por los bordes),
  así que encaja con las sombras de `build_mid`.
- **(b)** Rehacer el reparto de registros de `dpfsplit.py` contando los
  WAIT, y volver a simular antes de tocar la Amiga.

Probado y descartado (13:07, revertido): planificar las cargas por plazo
(EDF en ranuras de 16 px, como `dpfsplit`) en `mkscroll.py` y ordenar MLD
por la x planificada. Con el modelo "1 ranura por carga" solo quedaban 3
cargas tarde en todo el nivel, pero en la Amiga x = 1700 **empeoró** (1335
px contra 1025). O sea: **el modelo de tiempos del copper no está
calibrado** (dónde cae de verdad cada MOVE respecto a la h del WAIT,
`HOFS`, cuánto cuesta un WAIT intercalado en medio de una cadena). Antes
de (a) o (b) hay que **medirlo** con una prueba de copper (como
`copbench.s`): una línea con WAIT + N MOVE de color y ver en la captura
dónde cambia cada uno.

**Siguiente (etapa 6), en orden:**
- Calibrar el copper (arriba) y después la franja: (a) o (b). Comprobar varias x con
  `scroll_check.py --mid`, no solo 1000 y 1700.
- Bajar el 33 % de `build_mid`: tablas de desplazamientos por línea en vez
  de los dos `mulu` de cada visita, y no volver a escribir las h de los
  WAIT cuando `s` no cambió (Mario quieto).
- Cámara hacia la izquierda (`lo_tab`, `vu` y la lista de cambios solo
  avanzan) y conectar `mcam.c`.

**Lo que había escrito antes de hacerlo (referencia):**
- **`build_mid` incremental.** Entre dos frames, el conjunto de cargas de
  una línea solo cambia cuando la cámara cruza un umbral (una carga entra
  por la derecha, sale por la izquierda o se pega al borde). Si no, todas
  sus h bajan lo mismo (`Δs/2`). Guardar por lista y por línea (primera y
  última carga, s de la última escritura) y, si no cambió, solo restar a
  las palabras WAIT (~20 ciclos por carga, sin tocar MOVE ni salto).
  De media hay 24 líneas y 70 cargas a la vista.
- Baratos: guardar la x objetivo de cada carga en MLD (ahorra el cálculo),
  no reescribir el salto si el número de cargas no cambió.
- Cámara hacia la izquierda (`lo_tab` y la lista de cambios solo avanzan)
  y conectar `mcam.c`.

```bash
~/vbcc/bin/vasmm68k_mot -Fbin -m68000 -I player -DBENCH -DSPEED=4 -o work/scrollb.bin player/scroll.s
python3 tools/mkadf.py --boot work/boot.bin --stage2 work/scrollb.bin --data work/yi1_s.dat --out work/scrollb.adf
sh tools/fsuae_shot.sh work/scrollb.adf work/scrollb.png 70
python3 tools/scroll_read.py --shot work/scrollb.png --auto
```

**Actualización (2026-09-24, 12:05 UTC) — etapa 6, primer prototipo (media hora)**

- `tools/mkscroll.py`: de `work/yi1_d.dat` a `work/yi1_s.dat` (126 KB, en
  el orden de la Amiga). Ventana vertical fija, líneas 192-415: la cámara
  no se mueve en Y en toda la partida (`Bg1VOfs` = `Bg2VOfs` = 192).
  Colores de la capa 1: el valor de cada registro en el borrado solo
  cambia cuando la cámara pasa el final de un evento → **lista de 3409
  cambios ordenada por x**, que la Amiga aplica a la lista del copper
  según avanza (barato: un puntero que avanza).
- `player/scroll.s`: toma la máquina como `demo.s` y se desplaza sola a 2
  px/frame hasta `STOPX` (`-DSTOPX=n`). PF1: buffer circular de 22
  columnas escrito dos veces (704 px, 3 planos entrelazados); puntero =
  palabra `(s-1)>>4`, retardo `(-s)&15` (con `DDFSTRT $30` la fórmula de
  R5 da 1 px de desfase; esta no). PF2: bitmap de 848 px (512 + 336) a
  `s/2`: paralaje por hardware. Lista del copper: 64 bytes por línea (2
  WAIT + 7 + 7 MOVE; el segundo WAIT es el `$FFDF` en la línea 256).
  La columna nueva la copia **la CPU** (~24 000 ciclos cada 16 px): el
  definitivo va por blitter.
- Verificado en FS-UAE (`STOPX=1000`, 60 s de captura: con AROS tarda en
  arrancar, a los 30 s todavía no llegó) con `tools/scroll_check.py`,
  contra el frame esperado con el mismo modelo (paralaje + solo borrado):
  **~6-7 % de píxeles distintos, todos bordes de 1 px y puntos de la
  tierra del reescalado ×2,125 de la captura**; a la vista son idénticos.
  Ojo: la imagen "ideal" de `render_d.py` / `yi1_d_nivel.png` pone la capa
  2 a la misma velocidad que la 1 (sin paralaje): no sirve de esperado
  para el scroll.
- Falta (en orden): las cargas de mitad de línea (sin ellas, franjas de
  color en las pendientes y en los bloques; `scroll_check.py --mid` es el
  esperado final); la columna por blitter; la lista del copper por
  segmentos encadenados (§9 punto 10); medir el coste por frame; conectar
  la cámara de `mcam.c` en vez del avance automático.

```bash
python3 tools/mkscroll.py
~/vbcc/bin/vasmm68k_mot -Fbin -m68000 -I player -DSTOPX=1000 -o work/scroll.bin player/scroll.s
python3 tools/mkadf.py --boot work/boot.bin --stage2 work/scroll.bin --data work/yi1_s.dat --out work/scroll.adf
sh tools/fsuae_shot.sh work/scroll.adf work/scroll.png 60
python3 tools/scroll_check.py --shot work/scroll.png --s 1000
```

**Actualización (2026-09-24, 07:00 UTC) — cierre de la hora de trabajo**

Sobre lo de 06:25 (abajo), en esta última media hora:

- **Sprites nuevos**: bloque `?` volador (`$83`, sólido, golpe desde
  abajo) y `CODE_019386` (sprite sobre un tile de pendiente ≥ `$D8`: sube
  1 px y repite `CODE_0192C9`). Antes, en las colinas, cortaba el
  seguimiento del Rex.
- `marioverify ... game` adopta los Rex vivos del oráculo que nacieron
  antes del tramo (`GAME_NOADOPT=1` lo apaga, `GAME_SHOW=1` imprime los
  campos distintos). **Resincronizaciones de Mario: 26 → 1** (la que queda
  es el frame 5322: pisotón al Koopa sin caparazón `$02`, sin portar).
  **Rex exactos 3192/3194**; `sprloop` 2593/2594.
- **Los sprites ya están en el binario del 68000**: `msprite.c` entra en
  `logicbench_build.sh` y en el arnés; `level_frame` corre las 12
  ranuras (`sprite_run`) y el cargador si `level_sprites = 1` (apagado
  por defecto: `logicbench` y la 8d miden lo mismo que antes).
- `m68kverify.py --mode loop --sprites` (lazo cerrado del binario 68000
  con TODOS los sprites en el port: los sin portar no hacen nada) y
  `m68kprof.py --sprites`. Medido en Musashi (sin DMA), antes de
  optimizar el motor de sprites: **media 48 054 ciclos por frame (33,9 %
  de un frame PAL), p99 67 420, máx. 68 638 (48,4 %)**; sin sprites, 31 056
  (21,9 %). Mario: 4 resincronizaciones en 6547 frames (en `game` hay 1,
  porque allí los sprites sin portar se copian del oráculo).
- Perfil con sprites (`m68kprof.py --sprites`): `sprite_run` se llevaba
  6120 ciclos/frame (510 por ranura), casi todo del bucle de los 7
  temporizadores sobre una tabla de direcciones. Desenrollado: **48 054 →
  44 364 ciclos de media (31,3 %), máx. 64 752 (45,6 %)**, con el mismo
  resultado. La primera versión la compiló mal vbcc (P38).
  Sin sprites: 31 124 (+68 por el `tst` de `level_sprites`).
- Trampa de `m68kprof.py`: va instrucción a instrucción y **no tiene
  tope**. Si el binario se cuelga (P38), no termina nunca. Probar antes
  con `m68kverify.py`, que corta a los 10 M ciclos.

**Siguiente (en este orden):**
1. Seguir con el perfil de sprites (`PROF=1 sh tools/logicbench_build.sh
   && python tools/m68kprof.py --sprites`): `level_frame` pasó de 2708 a
   3944 ciclos propios (bucle de 12 ranuras + cargador en línea),
   `spr_tile` 947, `get_draw_info` 673.
2. Koopa sin caparazón (`$02`, sale del `$BD`): es la última
   resincronización de `game` (frame 5322). Después Banzai Bill (`$9F`),
   piraña saltarina (`$4F`), Chuck (`$95`).
3. Medir `level_frame` con `level_sprites = 1` en FS-UAE/WinUAE: hace
   falta meter `spr.lv` en el arnés (hoy solo `m68kverify`/`m68kprof`
   lo cargan en memoria y apuntan `_spr_level`) y un estado del oráculo
   con Rex a la vista.

**Actualización (2026-09-24, 06:25 UTC) — pasos 1 y 2 del plan de D1**

El usuario eligió: optimizar en C nativo verificando contra el oráculo
(paso 1) y escribir los sprites directamente así (paso 2). Estado:

- **Paso 1 (nativo, primera parte):** sondas de colisión con tablas
  nativas y atajo de `F545`; cámara con variables locales. Musashi:
  31 972 → 30 848 ciclos por `level_frame`. Todo sigue exacto. **Falta** la
  parte grande: el estado de Mario en variables nativas (ver "Implicación
  para D1"), medir con FS-UAE después de cada paso.
- **Paso 2 (sprites), `player/msprite.c`:**
  - cargador `LoadSprFromLevel`: `marioverify ... sprload` → **20/20
    nacimientos exactos** (ranura, número, X, Y) y ninguno de más;
  - motor mínimo: `InitSpriteTables`, temporizadores, `HandleSprite`
    (init + main), `SubUpdateSprPos`, colisión con el nivel
    (`CODE_019140`, nivel horizontal de capa 1), `GetDrawInfo` (flags),
    `SubOffscreen`, contacto Mario-sprite (`MarioSprInteract`, cajas,
    `CheckForContact`), `BoostMarioSpeed`, choque sprite-sprite (estado 8
    contra 8) y **el Rex completo**;
  - `marioverify ... sprloop` (los Rex que nacen a la vista corren solos;
    Mario y la cámara son entradas): **2411/2412 Rex-frames exactos**, los
    pisotones, el doble pisotón y la muerte con giro incluidos; los 11
    rebotes de Mario sobre esos Rex coinciden con el oráculo;
  - `marioverify ... game` (Mario desde el joypad + los Rex del port en el
    mismo frame): resincronizaciones de Mario **37 → 26**; tramo más largo
    **1240 → 2711 frames idénticos** (~54 s). Lo que queda: 23 frames
    parado sobre la **caja de mensaje** (`$B9`, sprite sólido), y 3
    rebotes: Koopa sin caparazón (`$02`, frame 5322), bloque `?` volador
    (`$83`, 6393) y un Rex que ya estaba al empezar el tramo (6909).
  - Tablas de otros bancos: `tools/smwtabx.py` → `player/gen/smwtabx.h`
    (generado, no se versiona). `smwgen.py` ahora lee también las tablas
    de sprites (`INSTANCEOF` en `memory.i`): `smwram.h` cambió.
  - Trampas nuevas: en `CODE_01A56D` el `ROL` guarda el **carry** de la
    resta (sin préstamo), no el signo; `RexSpinKill` pasa a estado 4 (no a
    0); al resincronizar un sprite hay que copiar también la fracción
    (`SpriteXAcc`/`YAcc`, grabadas) y deducir la dirección (no grabada).
  - **Los sprites todavía no están en `logicbench`** ni medidos en la
    Amiga: `level_frame` no los llama (los llama el verificador). Siguiente:
    caja de mensaje, bloque `?` volador, Koopa, Banzai Bill, piraña; meter
    los sprites en `level_frame` y medir con FS-UAE.

**Qué cambió (resumen; el detalle está arriba y en §8 P33-P37):**
- 8b, animación, gráficos de Mario y cámara portados y verificados:
  `player/mcoll.c`, `manim.c`, `mgfx.c`, `mcam.c`, `smwmac.h`.
  `marioverify` tiene los modos `full`, `gfx`, `loop` y `fulldump`.
- `logicbench` ahora mide `level_frame` (cámara + gráficos + jugador +
  bloques) y lleva el mapa del nivel dentro (`work/yi1_map16.bin`, lo
  genera `tools/mkmapbin.py`). `logicbench_build.sh` compila 5 ficheros
  C, parte datos/código y **se para si hay referencias absolutas**.
- Etapa 5: `tools/mkbg.py` (capa 2 desde el ROM), `mkd8in.py`,
  `mkleveld.py` → `work/yi1_d.dat`, `render_d.py`.
- 8d medida en cloud con FS-UAE + AROS: **31,6 % / 32,9 % de un frame**.

**Qué hay que hacer en la PC (lo que cloud no puede):**
1. **Confirmar la 8d en WinUAE con KS 1.2** (la de cloud es FS-UAE + AROS):
   ```bash
   python tools/mkmapbin.py
   gcc -O2 -Iplayer -o work/marioverify tools/marioverify.c player/mario.c player/mcoll.c player/manim.c player/mgfx.c player/mcam.c player/msprite.c player/gen/smwrom00.c
   work/marioverify work/oracle_yi1.bin fulldump 5410 work/cc/state_run.bin
   work/marioverify work/oracle_yi1.bin fulldump 10983 work/cc/state_jump.bin
   python tools/smwgen.py && python tools/smwtabx.py
   sh tools/logicbench_build.sh
   ```
   ```powershell
   .\tools\shot.ps1 -Exact -Adf work\logicbench.adf -Out work\logicbench.png -Wait 80
   ```
   ```bash
   python tools/logicbench_read.py        # esperado: ~31,6 % y ~32,9 %
   ```
   Si difiere de FS-UAE en más de 1 punto, anotarlo: la validación con
   `bench2.s` dio los mismos números en los dos emuladores.
   Esto también prueba que el ADF **arranca en KS 1.2** con el binario de
   58 KB (en cloud solo se probó con AROS).
2. **Etapa 5 contra la referencia**: `cmp_ref.py` / recortes apilados de
   `work/yi1_d_nivel.png` contra `SuperMarioWorldMap02.png` (la de cloud
   se comparó con la imagen ideal sacada del ROM, no con la referencia).
   Ojo: los colores del blob están cuantizados a 12 bits (OCS); comparar a
   4 bits por canal o esperar diferencias de 1 bit en todo.
3. **8c: grabar las colinas** (a toda carrera en las dos direcciones,
   parado encima, deslizándose, saltando) con `tools/oamrec.py --out` a un
   fichero **distinto** de `oracle_yi1`. **Probar el grabador antes** de
   pedirle al usuario que juegue (límites de 1024 caracteres, 16 valores y
   una sola conexión). Después: `oracle2bin.py --inp ... --out ...` y
   `marioverify <bin> full` / `loop` (el mapa es el mismo nivel).
4. Esperar la **decisión del usuario sobre D1** (ver "Implicación para D1"
   arriba) antes de empezar la etapa 9: define si los sprites se portan al
   estilo byte a byte (fácil de verificar, lento) o en C nativo pensado
   para el 68000.

**Diferencias de entorno a tener en cuenta en la PC:**
- `tools/mkd8in.py`, `mkleveld.py`, `render_d.py` y `dpfsplit.py` usan
  **numpy**, y el Python local (§6) no lo tiene: instalarlo o correrlos en
  cloud. `m68kverify.py` / `m68kprof.py` necesitan `unicorn` y
  `machine68k` (pip).
- `logicbench_build.sh` llama a `python tools/mkmapbin.py` si falta el
  mapa: necesita `../../smw-src-master` como siempre.
- `work/smw.sfc` en cloud es la ROM **ensamblada desde el fuente** (CRC32
  `B19ED489`, idéntica a la (U)); en la PC se sigue usando la del usuario.
- Los `*_read.py` aceptan `--auto` (capturas con otra escala, p. ej.
  FS-UAE); sin la opción siguen leyendo las capturas de `shot.ps1` como
  antes.

## 10. Roadmap

> El plan detallado de lo que falta (pasos, criterios de hecho, presupuesto del
> frame y decisiones D10-D14) está en `ROADMAP.md`.

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
| 5 | **Conversor de nivel → Amiga, formato (d)** | Capa 1: 3 planos con la asignación de índices de `dpfsplit.py` (244 variantes de bloque) + tablas del copper por línea del nivel (cargas en el borrado y a mitad de línea con su ventana). Capa 2: bitmap de 3 planos de período 512 px + paleta por línea. `render_dat.py` renderiza el blob en el PC aplicando las tablas y se compara contra `d8d_g48m8_nivel.png` y la referencia con `cmp_ref.py` | **HECHO en cloud** (2026-09-24): `tools/mkd8in.py` → `tools/mkleveld.py` → `work/yi1_d.dat` (199 KB) → `tools/render_d.py`. Todo sale de los datos del ROM (la capa 2 también: `tools/mkbg.py`). Colores cuantizados a 12 bits (OCS) antes de repartir registros. 244 bloques, 9575 eventos, derrame 357 px (0,1 %). El render **solo desde el blob** = la imagen ideal (0 px distintos); moviendo la cámara cada 4 px, 0,018 % de píxeles mal (peor encuadre 132 px). **Falta en la PC**: `cmp_ref.py` contra `SuperMarioWorldMap02.png` |
| 6 | Scroll del nivel real en la Amiga | PF1 con `BPLCON1` bits 0-3 + columna nueva; PF2 con bits 4-7 a media velocidad (paralaje); lista del copper por frame (segmentos por línea encadenados, §9 punto 10). Recorre las 20 pantallas a 50 Hz; captura de WinUAE = render del PC en varios puntos; coste medido con el método de `bench2.s` | **Primer prototipo** (2026-09-24, cloud): `tools/mkscroll.py` → `work/yi1_s.dat`, `player/scroll.s` (ver el handoff). Nivel real en DPF, PF1 con buffer circular + columna nueva, PF2 con paralaje por hardware, colores por línea con cargas en el borrado **y a mitad de línea** (segmentos de copper encadenados, dos listas, `build_mid` incremental), columna nueva por blitter. Fallos limpios contra el esperado: 0,37 % en x = 1000, 1,43 % en x = 1700 (una franja sobre el suelo; arreglada: copper calibrado + tres bugs, ver el handoff de las 13:40): hoy 0,06-0,23 % en 5 de 6 puntos. **Coste medido: 33 % de un frame sin columna, 43 % con columna.** Falta: la franja, bajar el coste, cámara hacia la izquierda y conectar `mcam.c` |
| 7 | **Capa 2** | En (d) la hacen las etapas 5 y 6 (PF2 con scroll por hardware). Queda la verificación: recortes apilados contra `SuperMarioWorldMap02.png`, el diff tiene que bajar del 25.5 % | — |
| 8 | **Mario**, por partes verificadas bit a bit contra el oráculo `work/oracle_yi1.txt` (partida real grabada en `smwrecomp`: joypad + WRAM `$0000-$00FF` y `$13C0-$14FF` + OAM por frame): **8a** velocidad horizontal, gravedad y saltos; **8b** colisiones con bloques (en SMW el "acts like" es el propio índice Map16); **8c** pendientes de 45° (hace falta grabar las colinas: a toda carrera, en las dos direcciones, parado encima y deslizándose); **8d** coste medido en la Amiga | Cada parte: el estado de Mario del port = el del oráculo en todos los frames de sus tramos | **8a, 8b, animación, gráficos y cámara HECHOS** (2026-09-24): 6510/6547 pares exactos, los 37 restantes son sprites (etapa 9); OAM 6869/6869; lazo cerrado solo con el joypad. 8c: las pendientes de la partida salen exactas, falta la grabación de las colinas. **8d medida: 31,6-32,9 % de un frame** (FS-UAE cycle-exact, tras la 1.ª optimización) |
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
# ANTES DE CADA COMMIT (ROADMAP.md §8): reglas estáticas + regresión completa
python3 tools/lint_port.py && python3 tools/regress.py

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
