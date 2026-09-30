# ROADMAP.md — Plan a futuro y handoff del port-demo SMW → Amiga 500

> **Qué es este fichero.** El plan de trabajo desde el 2026-09-26 hasta el ADF
> final, escrito para que lo ejecute cualquier agente o persona sin contexto
> previo. `AGENTS.md` sigue siendo el contrato: reglas duras, formatos,
> pitfalls y resultados medidos. Este fichero dice **qué hacer, en qué orden y
> cómo saber que está hecho**. Si algo de acá contradice `AGENTS.md` §2 (reglas
> duras), manda `AGENTS.md`.
>
> Se reescribe, no se apila: al cerrar una sesión se actualizan §1 y la tabla
> de estado con la plantilla de §7. El historial detallado queda en los
> commits y en `AGENTS.md`.

---

## 0. Cómo usar este plan

1. Leer en este orden: §1 (handoff) → §2 (presupuesto) → la etapa que toca
   (§5) → §8 (scripts de comprobación) → `AGENTS.md` §2 (reglas), §7
   (convenciones), §8 (pitfalls P1-P76) y §11 (definición de "hecho"). Si
   la etapa es de optimización, también §9.
2. Trabajar **un paso por vez**. Cada paso dice dónde corre, qué hacer y
   cuándo está hecho. No se empieza el siguiente con el anterior en rojo.
3. Al cerrar un paso: commit `Etapa N.x: <qué>` y actualizar §1.2. Si aparece
   una trampa nueva, se agrega como `Pnn` en `AGENTS.md` §8 (la próxima es
   **P77**).
4. Al cerrar la sesión: handoff con la plantilla de §7, que reemplaza a §1.
5. Para repartir el trabajo entre subagentes (tarjetas por etapa, niveles,
   olas, mapa de conflictos y protocolo de integración): **`SUBAGENTES.md`**.
   Worktree por tarea: `sh tools/wt_new.sh <tarjeta>`.

**Reglas del proceso (no negociables, vienen de lo que ya costó caro):**

| # | Regla | Por qué |
|---|---|---|
| V1 | Todo cambio en `player/*.c` se verifica con `marioverify` (C del PC) **y** con `m68kverify` (binario 68000 de vbcc): `python3 tools/regress.py` hace las dos cosas y compara con `tools/baseline.json`. Ninguna métrica puede empeorar | P38: vbcc compiló mal código que gcc compilaba bien |
| V2 | Los tiempos solo valen en cycle-exact: `tools/fsuae_shot.sh` en cloud, `tools/shot.ps1 -Exact` en la PC. Musashi (`m68kverify --engine musashi`) es una **cota inferior** porque no tiene esperas de DMA | P30; Musashi daba 24 % y la Amiga 34 % |
| V3 | Toda imagen se compara contra el esperado del PC (`scroll_check.py`) y, en la PC, contra `SuperMarioWorldMap02.png`. **Primero lo que se nota a simple vista**, criterio del usuario | la captura de FS-UAE está reescalada ×2,125 y ensucia los bordes |
| V4 | Nada derivado de la ROM entra en git (R9). Las grabaciones del oráculo sí (`work/oracle_*.txt`, `work/oam_*.txt`) | `.gitignore` |
| V5 | Las decisiones marcadas **[usuario]** no las toma el agente: prepara los datos, recomienda y pregunta | D8 y D1 se cerraron así |
| V6 | Antes de pedirle al usuario que juegue para grabar, **probar el grabador** (`oamrec.py --test 10`) | límites del puerto Lua: 1024 caracteres por valor, 16 valores por respuesta, una sola conexión TCP |
| V7 | Antes de cada commit: `python3 tools/lint_port.py` y `python3 tools/regress.py` en verde. Una optimización, además, `tools/abcheck.py` (semántica IGUAL, ciclos menores). Detalle en §8; ideas de optimización en §9 | que el siguiente agente no herede un rojo que no se ve |

---

## 1. Handoff (estado al 2026-09-30)

### 1.1 Ramas

| rama | contenido |
|---|---|
| `master` | base hasta el 2026-09-27: primer ADF jugable (etapas 0, 6.1-6.3, 8.2, 6b) |
| `claude/brave-ritchie-mm5o6r` | sesión cloud del 2026-09-30, sobre `master`: oráculos sin usuario (snesorc), Etapa 9.1 (6 sprites más, `game` sin resincronizaciones), entrada y modo diagnóstico (6b.7), tres bugs arreglados (cámara vertical, copper de la línea 255, `mario_sprite` mal compilado) y herramientas de la 6.4. **Sin mergear a `master`**: lo decide el usuario |

- Trabajo en paralelo con 4 subagentes, cada uno en su worktree; el
  coordinador integró, arregló lo que quedó flojo y verificó todo junto.
- Lo único a medias está fuera del build: `tools/wip64/` (el diseño de la
  6.4, sin ensamblar; lo que falta está en la cabecera de
  `build_mid_incremental.s`).

### 1.2 Estado por etapa

| Etapa | Qué | Estado | Dónde está |
|---|---|---|---|
| 1-2b | Assets, paletas, nivel, capa 1 1:1 | **hecho** (6111/6111 bloques) | `tools/smw2amiga.py`, `palette.py`, `mklvl.py`, `m16diff.py` |
| 3-4 | Esqueleto Amiga y viabilidad | **hecho**; D1, D8 y D9 cerrados | `player/boot.s`, `bench*.s`, `copbench.s` |
| 5 | Conversor del nivel al formato (d) | **hecho en cloud**; falta compararlo contra la referencia en la PC (→ 7) | `tools/mkbg.py`, `mkd8in.py`, `mkleveld.py`, `render_d.py` |
| 6.1-6.3 | Scroll a 256 px, ida y vuelta, lo mueve la cámara del port | **hecho** (2026-09-27). El 2026-09-30: el copper no corría las líneas 212-223 (P59), arreglado | `player/scroll.s`, `tools/mkscroll.py` |
| 6.4 | Scroll ≤ 25 % en el peor frame | **NO hecha**. Ida: Musashi máx. 54,1 % (2 px/frame), FS-UAE máx. 78,8 % (4 px/frame, s = 4584). **Vuelta: Musashi media 36,6 %, máx. 94,8 %** (P72, no estaba medida). Perfil por zonas (`scrollprof.py --zones`), ida/vuelta simulada (`scrollsim.py --ret`); diseño incremental en `tools/wip64/` | Etapa 6.4 |
| 7 | Capa 2 contra la referencia | pendiente (solo PC) | — |
| 8a/8b | Física y colisión de Mario | **hecho**: `full` 6510/6547 en `oracle_yi1`; en las grabaciones nuevas, 99,6-99,8 % (los fallos son contactos con sprites) | `player/mario.c`, `mcoll.c`, `manim.c` |
| 8 (gfx, cámara) | Gráficos y cámara | **hecho**; `gfx` 100 % en los 5 oráculos. Cámara vertical hacia arriba arreglada (P69) | `player/mgfx.c`, `mcam.c` |
| 8c | Pendientes | **casi cerrada**: `oracle_hills` (colinas 1-4 a toda carrera en los dos sentidos, parado, deslizándose y saltando) da las pendientes 2154/2154 exactas. Falta la colina grande de x = `$AE0` (pendiente hacia el otro lado, 5 Rex encima) | `work/oracle_hills.txt` |
| 8.1 | Grabaciones | **oráculos sin usuario**: `work/snesorc` corre la ROM (U) en el emulador de snesrev/smw con entrada guionizada (`tools/snesorc/*.orc`) y reproduce `oracle_yi1` línea a línea (6871/6871). Grabadas: `normal`, `diagpipe`, `hills`, `banzai` | `tools/snesorc/`, `snesorc_setup.sh`, `snesorc_make.sh` |
| 8.2 | Optimizar la lógica | **hecha** el 2026-09-27 (peor frame con sprites 40,1 % en WinUAE). Con los sprites nuevos, peor frame en Musashi 43 116 → **45 896** (frame 9715: 2 pirañas, 1 Rex, `$8E`, `$C7`), **~45 % estimado** en la A500 (por encima del 40 %) | `player/logic68k.s` |
| 9.1 | Sprites: lógica | Rex, `$83`, `$B9`, **`$BD` Koopa deslizante, `$02` Koopa sin caparazón, `$9F` Banzai Bill, `$4F` piraña, `$8E` warp, `$C7` seta invisible**. `game`: **0 resincronizaciones** de Mario en los 5 oráculos; sprites exactos por tipo en `regress.py`. Faltan Chuck `$95`, caparazón rojo `$DB`, cinta de meta `$7B` y lo de D12 (la seta `$74` del bloque volador ya aparece en `oracle_yi1`) | `player/msprite.c` |
| 9.2 | Sprites: dibujo | Mario hecho; los del nivel sin empezar (se simulan, no se ven) | `player/mspr.c`, `mspr68k.s` |
| 6b | Integración | primer ADF jugable (2026-09-27) + **6b.7** (2026-09-30): entrada como `ControllerUpdate` (P60) y **modo diagnóstico** (P58) con historial del joypad y reproducción en el PC desde una captura. Faltan 6b.1 (vlink, compresión) y **6b.6 (compuerta D1)** | `player/game.s`, `tools/diag_read.py`, `gamesim.py`, `inputtest.py` |
| 10-12 | HUD, audio, pulido | no empezados | — |

### 1.3 Números de regresión (2026-09-30, cloud)

La fuente de verdad es `tools/baseline.json` (cloud: vbcc de cloud y
FS-UAE); la PC usa `tools/baseline_pc.json`. El 2026-09-27 la PC había
escrito sus ciclos en `baseline.json` (otro vbcc): el 2026-09-30 se volvió a
medir todo en cloud y se guardó con `--update --force`.

| qué | valor | antes (2026-09-27) |
|---|---|---|
| `marioverify full` / `gfx` / `loop` (`oracle_yi1`) | 6510/6547 · 6869/6869 · 37 resincronizaciones | igual |
| `marioverify game` (`oracle_yi1`) | **0 resincronizaciones**, tramo 3824; sprites exactos por tipo: 02 252, 4F 2599, 83 340, 8E 2518, 9F 454, AB 2635, B9 309, BD 322, C7 3178 (ninguno distinto) | 1 (Koopa `$02`, frame 5322) |
| `marioverify sprloop` / `sprload` | 2684/2684 · 20/20 | 2593/2594 · 20/20 |
| oráculos snesorc (`orc.*` en `regress.py`): `full` / `loop` / `game` | normal 1249/1254 · 5 · 0; diagpipe 2693/2699 · 6 · 0; hills 2147/2154 · 7 · 0; banzai 1078/1080 · 2 · 0 (las resincronizaciones de `loop` son pisotones: sprites) | — |
| 68000 `loop --sprites` (Musashi): resincronizaciones / media / p99 / máx. | **0** / 32 730 / 43 234 / 45 896 | 4 / 30 893 / 42 652 / 43 280 (base de la PC) |
| cruces PC = 68000 | `full`, `loop` y **RAM entera** tras cada `level_frame` (`--cross`): 0 diferencias en 6547 y 6549 llamadas | los dos primeros |
| `gamecheck.py` / `--spr` | 0 diferencias en 6181 RUN; `mario_sprite` vbcc = asm = referencia 6184/6184 | 6177 RUN; `--spr` se colgaba en cloud (P62) |
| capturas del replay (FS-UAE), fallos que no explica un vecino | frame 6000: fondo 30, Mario 0; frame 7000: fondo 16, Mario 0 (reescalado ×2,125) | WinUAE: 0 / 0 |
| `inputtest.py` / `diag_read.py --sim` | 35/35 · TODO OK | — |
| FS-UAE (`regress.py --level --emu logic,scrollbench,scrollimg`) | `logicbench` 23,2 % corriendo / 23,4 % saltando (256 px); `scroll.s -DBENCH -DSPEED=4`: con columna media 14,9 %, **máx. 78,8 %** (s = 4584), sin columna media 12,9 %, máx. 31,1 % (s = 4820); `scroll_check --mid` (fallos que no explica un vecino) 500: 15, 1000: 32, 1700: 31, 2500: 1, 3500: **6**, 4500: 47 | 26,5 / 26,9 % y 25,2 % / 307,5 % (320 px); imagen 74 / 31 / 94 / 46 / 72 / 127 (con el origen de 320 px: P59 y el arreglo de `scroll_check`) |

### 1.4 Qué se puede hacer en cada entorno

Igual que antes, con dos cambios: **en cloud ya se pueden grabar partidas**
(snesorc, con guion; no hace falta el usuario) y el juego arma en cloud
(`mkmario.py` usa `work/smw.sfc` si no está la ROM de la PC).

| tarea | Claude cloud | PC local (Windows) |
|---|---|---|
| compilar (vasm, vbcc, gcc) | sí (`setup_cloud.sh`) | sí |
| verificar contra el oráculo | sí | sí |
| **grabar oráculos** | **sí, con guion** (`snesorc_setup.sh`, `snesorc_make.sh`) | sí, jugando (`smwrecomp` + `oamrec.py`) |
| medir en cycle-exact | FS-UAE + AROS; varias capturas, de a una (P76) | WinUAE + KS 1.2 |
| probar el arranque en KS 1.2 y el teclado | **no** | sí |
| comparar contra `SuperMarioWorldMap02.png` | **no** | sí |

Notas de la PC del 2026-09-27 (gcc de msys64 primero en el PATH, el sdist de
`machine68k`, el vbcc de 2022, `scroll_check.py --sc 2`): siguen valiendo,
ver el historial de este fichero.

### 1.5 Arranque rápido en cloud

```bash
sh tools/setup_cloud.sh               # ~2 min la primera vez, ~15 s con caché
export VBCC=~/vbcc PY=python3
python3 tools/lint_port.py && python3 tools/regress.py        # ~1 min: PC + 68000 + 5 oráculos
sh tools/snesorc_setup.sh             # opcional: el generador de oráculos (work/snesorc)
sh tools/game_build.sh && python3 tools/gamecheck.py --spr    # el juego (replay) en Unicorn
GDEFS=" " OUT=work/live sh tools/game_build.sh                # el de jugar
```

### 1.6 Pendiente del usuario o de la PC

1. **Jugar `work/live/game.adf` en WinUAE con teclado** (KS 1.2, 512 KB
   chip + 512 KB slow, `work/play.uae`). Nunca se probó con teclas: el
   modo diagnóstico (ESPACIO cambia de página; RETURN, Z, A o el botón
   vuelven a empezar), el handshake del teclado y los dobles saltos (P55).
   Si se congela: captura de la **página 2** y
   `python3 tools/diag_read.py --shot X.png --repro --bin work/live/game.bin`
   (el `game.bin` del ADF que se usó) dice en qué frame y por qué.
2. **PC:** Etapa 7 (`cmp_ref.py` del blob de la etapa 5 contra la referencia).
3. **Usuario, opcional:** probar en una A500 real.
4. Las grabaciones de la 8.1 ya no necesitan al usuario (snesorc). Solo el
   audio de referencia de la 11 quedaría para la PC, si snesrev no lo da.
5. **[usuario] Mergear `claude/brave-ritchie-mm5o6r` a `master`.**

### Lo último que se hizo y lo siguiente

- **Hecho el 2026-09-30:** los oráculos en cloud, la 9.1 sin
  resincronizaciones en `game`, la 6b.7 y tres bugs que ningún verificador
  veía (P59, P62, P69). La 6.4 no se cerró: se midió y se entendió (P71,
  P72) y el diseño quedó en `tools/wip64/`.
- **Siguiente, en orden:**
  1. **6b.6, compuerta D1 [usuario]:** medir el peor frame del juego
     integrado en FS-UAE. Con lo medido por partes (lógica con sprites
     ~45 %, scroll hasta 79 % a la ida y 95 % a la vuelta en Musashi, Mario
     7 %) el peor caso **pasa del 100 %**: preparar las opciones de §2 con
     números y preguntar.
  2. **6.4:** terminar `tools/wip64/build_mid_incremental.s` (rebase en el
     sitio, append y truncado por la derecha; clasificación "tarde" fija),
     medir **ida y vuelta** con `scrollprof.py` y verificar con
     `scrollsim.py --ret` (9282 px, ida = vuelta).
  3. **9.1:** Chuck `$95` (x `$12A0`), caparazón rojo `$DB` (x `$D10`), cinta
     de meta `$7B` (x `$12E0`), seta `$74` y el resto de D12; cada uno con su
     grabación de snesorc (un guion `.orc` que llegue hasta ahí).
  4. **9.2:** dibujar los sprites del nivel (hoy hay Rex invisibles que
     Mario pisa: parece un doble salto).
  5. Sueltos, **sin comprobar**: en las 4 grabaciones de snesorc, el Koopa
     deslizante `$BD` difiere 1 frame justo al empezar el nivel (frame
     1455, ranura 7, `$AA` = SpeedY: port 0, ROM 3); en `diagpipe`,
     `sprload` da 31/33 (la ROM mete la piraña `$4F` en la ranura que un Rex
     deja libre en el mismo frame; el port no).
- Para retomar: `sh tools/setup_cloud.sh && python3 tools/regress.py`.
- El resto del proyecto, en tarjetas para subagentes: `SUBAGENTES.md`
  (olas 1-6; la ola 1 no depende de la compuerta D1).

---

## 2. El presupuesto del frame (lo que manda)

Un frame PAL son 20 ms, ~141 800 ciclos de CPU. Hoy, medido en cycle-exact
salvo donde se indica:

| componente | medido | objetivo propuesto (peor frame) | fuente |
|---|---|---|---|
| scroll: `build_mid` + columna nueva + lista del copper | ida, 4 px/frame, FS-UAE: media 14,9 %, **máx. 78,8 %** (s = 4584). **Vuelta**, 2 px/frame, Musashi (cota inferior, ×~1,3 en la Amiga): media 36,6 %, **máx. 94,8 %** (s = 2832) (2026-09-30, P72) | **≤ 25 %** en el peor frame, en los dos sentidos | `scroll.s -DBENCH`, `scrollprof.py` |
| lógica `level_frame` sin sprites | 20,2 % / 20,5 % (WinUAE, 256 px, tras la 8.2) | — | `logicbench` |
| lógica con sprites | peor frame 40,1 % (WinUAE, 2026-09-27); con los sprites de la 9.1, Musashi 43 116 → 45 896 ciclos: **~45 % estimado** | lógica total **≤ 40 %** | `logicbench -DWORST`, `m68kverify --sprites` |
| Mario en sprites de hardware (`mspr_draw`) | ~10 400 ciclos ≈ 7,3 % (Musashi) | — | `gamecheck.py --engine musashi` |
| dibujo de los sprites del nivel (sprites de hardware + copper) | sin medir | ≤ 10 % | — |
| bobs en PF1 (solo si un objeto pasa a bob) | 22,7-33,8 % (Banzai + 4 Rex, `bench2.s` W3) | caso raro, ver 9.2 | `bench2.s` |
| HUD | sin medir | ≤ 2 % | — |
| audio | sin medir | ≤ 3 % (D5) | — |
| **margen** | — | **≥ 10 %** | — |

**Hoy no entra a 50 Hz en el peor caso.** Por partes, el peor frame suma
scroll (79 % a la ida, ~95 % o más a la vuelta) + lógica con sprites (~45 %)
+ Mario (7 %): bastante más del 100 %, sin dibujar los sprites del nivel,
sin HUD y sin audio. De media: scroll ~15 % a la ida (~37 % a la vuelta) +
lógica ~23-30 % + Mario 7 %. Por eso la 6.4 va **antes** que las etapas que
suman coste (9.2, 10 y 11), y la compuerta D1 se prepara ya con estos
números (6b.6).

**Compuerta D1 [usuario]:** después de las Etapas 6.4, 8.2 y la 6b se mide el
**peor frame del juego integrado**. Si pasa del 100 %, se le presentan al
usuario estas opciones con números: (1) otra ronda de optimización, con
ensamblador a mano en las sondas de colisión y en `build_mid`; (2) dibujo a
25 Hz con la lógica a 50 Hz, que ahorra scroll y copper pero no lógica; (3)
recortar el alcance, por ejemplo menos sprites a la vez. Mover el código a
slow RAM **no** acelera (P29).

---

## 3. Decisiones

Cerradas por el usuario el 2026-09-26: se aceptan las recomendaciones, con
el **teclado primero** en los controles. El criterio general es el mejor
equilibrio entre 1:1 y coste. Solo queda abierta la compuerta D1.

| ID | Decisión | Qué se hace | Consecuencias | Etapa |
|---|---|---|---|---|
| D1 | 50 Hz o no | **abierta**: compuerta de §2 | se decide con el peor frame del juego integrado | después de la 6b |
| **D5** | Música | **secuenciador propio** que lee las secuencias N-SPC de SMW convertidas offline a un formato compacto de eventos (no MOD) | Conserva glissandos, vibrato, envolventes (ADSR aproximado por tick) y el tempo del SPC700 (tick por timer de CIA). **Sin mezcla por CPU**: cada voz va directa a un canal de Paula, 3 de música + 1 de efectos, con prioridad por tema; el eco se omite. Límites: ≤ 64 KB de muestras en chip RAM y **≤ 3 % de CPU** medido | 11 |
| **D10** | Ancho de pantalla | **256 px**, como la SNES | DIW centrada; el fetch empieza más tarde, así que vuelve el sprite 7 (4 columnas adosadas); 20 % menos de DMA de planos; la cámara y la aparición de enemigos quedan 1:1 | 6.1 |
| **D11** | HUD | **superpuesto (overlay)**, como la SNES | En las líneas del HUD el copper apunta PF1 a un bitmap fijo del HUD y PF2 sigue con su paralaje. Si en esas líneas aparece capa 1 del nivel, antes de renunciar al overlay se busca otra variante que lo conserve (10.1) y se consulta | 10 |
| **D12** | Power-ups | **todos los de Yoshi's Island 1** | ver la lista abajo | 9.1 |
| **D13** | Carga y memoria | **direcciones fijas, enlazado absoluto**; lo que lee el chipset en chip RAM y el resto en `$C00000` | ver el esquema abajo | 6b.1 |
| **D14** | Controles | **teclado primero**, joystick como alternativa | ver la asignación abajo | 6b.3 |

**D12 — qué hay en el nivel** (`lvparse.py --dump` de `obj.lv` y `spr.lv`):

| objeto | cantidad | da |
|---|---|---|
| bloque `?` (flor) | 1 | seta si Mario es chico; flor de fuego si es grande. Hay que portar las **bolas de fuego** (hoy `MARIO_UNSUP_FIRE`) |
| bloque giratorio "estrella 2 / 1-UP / enredadera" | 1 | lo decide el ROM según el estado: transcribir la rutina del golpe, no suponer. Incluye la **estrella** (invencibilidad, música propia) |
| luna 3-UP | 1 | 3 vidas |
| monedas de Yoshi | 4 | puntos; la 5.ª del recuento da 1-UP |
| bloques `!` amarillos | 5 | dependen del palacio amarillo: mirar en el oráculo si son sólidos, y si lo son, portar su contenido (seta) |
| champiñón invisible (sprite `$C7`) | 1 | 1-UP escondido |
| monedas (100) | — | 1-UP |

Estados de Mario: chico, grande y fuego, más la caja de reserva del HUD. En
el nivel no hay pluma: la capa queda fuera por el propio nivel, no por
recorte.

**D13 — esquema de carga** (lo más rápido de programar y de ejecutar dentro
de las reglas de la A500):
1. El bootblock carga con `trackdisk.device`, mientras el SO todavía está
   vivo, un **stage 2 pequeño** (el loader). En KS 1.x trackdisk solo lee a
   chip RAM.
2. El loader lee el resto del disco en bloques comprimidos a un buffer de
   chip, con un compresor LZ simple y rápido de descomprimir en 68000.
   Descomprime:
   - lo que lee el chipset (planos, `BLK`, `L2B`, listas del copper, frames
     de sprites, muestras) a **direcciones fijas de chip RAM**, con la
     alineación de §7 de `AGENTS.md`;
   - el código y los datos de CPU (`ram[]`, `rom00`, tablas, `MAP`, `CHG`,
     `MLX`, `MLD`, `INI`) a **direcciones fijas de `$C00000`**, después de
     comprobar que responde (P8).
3. Toma la máquina y salta al código.

Todo se enlaza en absoluto con **vlink**, en esas direcciones. Así
desaparecen el límite de 32 KB de datos relativos a `a4` (P36) y la
comprobación de referencias absolutas de `logicbench_build.sh`, y vbcc puede
usar direccionamiento absoluto corto donde convenga. El slow RAM no acelera
(P29): sirve para liberar chip RAM. **Medir** el tiempo de carga (con y sin
compresión) y dejar el que sea más corto.

**D14 — teclado** (códigos raw del Amiga, por posición física, válidos para
cualquier distribución nacional):

| SNES | tecla | raw |
|---|---|---|
| cruz | flechas: arriba / abajo / derecha / izquierda | `$4C` / `$4D` / `$4E` / `$4F` |
| B (salto) | Z | `$31` |
| A (salto con giro) | X | `$32` |
| Y (correr, agarrar, disparar) | A | `$20` |
| X (igual que Y en SMW) | S | `$21` |
| Start (pausa) | Return | `$44` |
| Select | Shift derecho | `$61` |

Joystick de alternativa: botón 1 = B, botón 2 (`POTGO`/`POTINP`) = Y, y
arriba + botón = A. Las dos entradas se combinan con un OR. Asignación
cambiable en un solo lugar (una tabla).

---

## 4. Orden de trabajo

```
Etapa 0 (consolidar el WIP)
   ├── Etapa 6.1-6.4 (scroll: 256 px, ida y vuelta, cámara, coste) ──┐
   ├── Etapa 8.2 (optimizar la lógica en C nativo)  ─────────────────┤
   └── Etapa 9.1 (lógica de sprites; en paralelo)                    │
                                                                     ▼
                         Etapa 6b (INTEGRACIÓN: primer ADF jugable) → compuerta D1
                                                                     ▼
                      Etapa 9.2 (dibujar sprites) → 10 (HUD) → 11 (audio) → 12 (pulido)

En la PC, cuando se pueda: 6.5, 7 y 8.1 (grabación única), y el arranque en KS 1.2.
```

Las ramas de un mismo nivel se pueden repartir entre agentes o subagentes,
siempre que no toquen los mismos ficheros. La 8.2 y la 9.1 tocan los dos
`player/*.c`, así que se coordinan: `msprite.c` es de la 9.1 y el resto de la
8.2.

---

## 5. Etapas

Formato de cada paso: **Dónde** · **Qué hacer** · **Hecho cuando**.

### Etapa 0 — Consolidar el WIP

**Dónde:** cloud. **Objetivo:** que la cabeza de la rama no tenga nada sin
verificar.

0.1 **Entorno.** `sh tools/setup_cloud.sh`. Correr §1.5 y anotar los números.
**Hecho cuando** §1.3 se reproduce, salvo lo que el WIP cambió.
**HECHO el 2026-09-26** (setup en ~2 min la primera vez, ROM con CRC32
`B19ED489`).

0.2 **Optimización de los subagentes** (`45e3857`: `manim.c`, `mario.c`,
`mcam.c`, `mcoll.c`, `mgfx.c`, `msprite.c`, `smwmac.h`).
- `marioverify` en los 7 modos tiene que dar lo mismo que en §1.3.
- `sh tools/logicbench_build.sh` (se para si hay una referencia absoluta);
  después `m68kverify --engine musashi --mode loop` (37) y `--mode loop
  --sprites` (4). Anotar los ciclos medios contra 31 100 / 44 400.
- Medir: `sh tools/fsuae_shot.sh work/logicbench.adf work/logicbench.png 30
  && python3 tools/logicbench_read.py --shot work/logicbench.png --auto`.
- Si algo no cuadra, bisecar por fichero (`git checkout bb66d2c --
  player/<f>.c`) y quedarse con lo que pasa.

**Hecho cuando** la verificación es idéntica, los ciclos bajan y la nueva
base de ciclos queda anotada en §1.3.
**HECHO el 2026-09-26:**
- `regress.py`: los 7 modos del PC dan exactamente la base y los cruces
  PC = 68000 cuadran.
- `abcheck.py bb66d2c` y `--sprites`: semántica IGUAL. Ciclos de media −17 %
  (31 124 → 25 909) y −19 % con sprites (44 364 → 35 779); peor frame −10 %
  y −18 %.
- FS-UAE: 26,5 % / 26,9 %, antes 31,6 % / 32,9 %.

Queda de esta etapa: los commits siguen llamándose "WIP" en el historial;
no hace falta reescribirlo, basta con esta nota.

0.3 **`scroll.s` del WIP** (escaneo de `wake` por bloques de 16 líneas con
`gmin_a/b`; `blit_steps`, la columna repartida en `BLITS`=4 pasos por frame).
- Imagen: `python3 tools/regress.py --quick --emu scrollimg` hace todo
  esto. A mano, para `X` en 500, 1000, 1700, 2500, 3500 y 4500 (la espera
  tiene que ser ≥ 50 + X/100 s: AROS tarda ~35 s en arrancar y el scroll va
  a 2 px por frame; con 60 s fijos, 3500 y 4500 se capturan antes de
  llegar):
  ```bash
  ~/vbcc/bin/vasmm68k_mot -Fbin -m68000 -I player -DSTOPX=X -o work/scroll.bin player/scroll.s
  python3 tools/mkadf.py --boot work/boot.bin --stage2 work/scroll.bin --data work/yi1_s.dat --out work/scroll.adf
  sh tools/fsuae_shot.sh work/scroll.adf work/scroll.png $((50 + X / 100))
  python3 tools/scroll_check.py --shot work/scroll.png --s X --mid
  ```
- Coste: `-DBENCH -DSPEED=4` y `scroll_read.py --auto`, o directamente
  `regress.py --emu scrollbench`. Mirar la **media y el máximo**; el
  máximo sale con la s donde ocurrió.
- Si la imagen empeora: `git checkout f21a2e3 -- player/scroll.s`.

**Hecho cuando** los fallos que no explica un vecino son iguales o menores
que en §1.3 y el coste baja, o el cambio queda revertido con el motivo
escrito.
**Estado el 2026-09-26:**
- **Imagen: igual a la base** en las 6 x (§1.3).
- **Coste:** media 25,2 %, contra ~36 % antes. No se compara 1:1: con
  `blit_steps` casi todos los frames cuentan como "con columna".
- **Falta — un pico de 307 % (61 ms) en s = 4504.** No es el primer frame:
  el banco ya descarta los 8 primeros (`BSKIP`) y guarda la s del peor
  frame (w8/w9, lo imprime `scroll_read.py`). Para cerrar:
  1. armar con `-DBENCH -DSTOPX=4520` y ver si se repite;
  2. perfilar ese frame en Musashi, con el listado `-L` de `scroll.s`;
  3. sospechosos: la rama "columna a medias: terminarla" (`moveq #99,d7`)
     y un recálculo completo de `build_mid`.

  Hasta explicarlo, el pico cuenta en el presupuesto.

**CERRADA el 2026-09-27 (PC):** el pico no es un bug. `tools/scrollprof.py`
(Musashi, el cuerpo real de `frame`) da 218 % solo de CPU en s = 4504, y
el 99 % es `build_mid`. En x = 4816-4856 del nivel hay un **borde vertical
de color en 144 líneas** (765 cargas); cuando entra por la derecha,
`build_mid` reconstruye ~140 líneas enteras (~2 200 ciclos cada una: recorre
todas las cargas de la línea, hasta 52) en 2-3 frames seguidos. No es el
único: a 2 px/frame hay **403 frames** cuyo trabajo pasa del comienzo de la
pantalla siguiente (s ≈ 1590-1970, 2630-2700, 4230-4680); el banco solo
mostraba el máximo. Confirmado en WinUAE KS 1.2: 309,9 % en s = 4504. El
arreglo es de la 6.4: reconstruir solo lo que cambia (agregar la carga que
entra, no rehacer la línea) y repartir entre frames.

0.4 **Los ~5 px del copper** (`WOFS`=8, un parche empírico). Leer lo que
dejó el subagente (`copcal_fine.py` y el diff de `copcal.s`/`copcal.py` en
`45e3857`). Si no hay conclusión, repetir el experimento: bandas con
`BPLCON1` a 0, 7 y 15 y un contenido de rayas de 1 px (`-DPATTERN`), y
comparar dónde cae el MOVE respecto de los píxeles del contenido y del borde
de la DIW. **Hecho cuando** hay una explicación y una fórmula en `scroll.s`
(y un **P42**), o `WOFS` queda documentado como empírico con la medida que
lo respalda.

**Pista nueva (2026-09-26):** dos builds de `scroll.s` que solo difieren
en la posición de las variables (`V_SIZE` 80 → 92, sin tocar el código que
dibuja) dan en x = 1700 3 fallos limpios más, con el mismo origen de ajuste
(91 → 94), y en x = 4500 125 → 127; en x = 1000 la captura es idéntica. Una
imagen que depende de la disposición en memoria apunta a una carrera de
tiempos entre la CPU y el copper, la misma familia que los ~5 px. Probar
con `imgdiff.py` sobre dos builds con relleno distinto (`ds.b` de más antes
de `vars`).

**CERRADA el 2026-09-27 (PC):** explicado y arreglado, sin `WOFS`.
- **P42:** con 6 planos el WAIT tiene rejilla de 8 px (h = `$40` y `$42`
  caen igual). Medido en WinUAE con `copcal.s -DPATTERN` + `COPCAL_FINE=1`:
  x = 8·⌊(h − `$38`)/4⌋ − 1. El modelo viejo fallaba 5 px con h ≡ 2 (mod 4).
  `BPLCON1` y el fetch se comportan como supone `scroll.s`. `TXOFS` no se
  usaba: borrado.
- Mirando en movimiento, el usuario vio **objetos que salen por la
  izquierda pintados con los colores del siguiente** (s = 846, 1936). Tres
  causas más, arregladas: **P43** (el borrado deja el copper libre ~60 px
  antes de x = 0: la primera carga de la línea va con WAIT), **P44** (los
  derrames de la etapa 5 alargan el tramo: `mkscroll.py`) y **P45** (una
  carga cortada por `LASTX` no bajaba el `vu`).
- La pista de la disposición en memoria (91 → 94) queda explicada por P42:
  cambiar el código cambia la fase de los WAIT en la rejilla.
- Herramientas nuevas: `tools/scrollsim.py` (la lista del copper de cada
  frame, simulada con el modelo medido, contra el render del PC),
  `tools/scrollprof.py` (ciclos por frame y por rutina de `scroll.s` en
  Musashi), `tools/shots6.ps1` (capturas de WinUAE en varias x, con
  reintentos) y `scroll_check.py --sc 2` (capturas de WinUAE ×2, sin el
  borroneo de FS-UAE).
- Queda (6.x): los postes de la meta (s ≈ 4540-4580) tienen más cambios de
  color de los que el copper alcanza (ancho de banda), y los 72 px de
  x = 3500 (iguales antes y después: no son del copper; sin investigar).

0.5 **HECHA:** commit sin "WIP" (rama `etapa0-cierre`). §1 actualizado.

### Etapa 6 — Terminar el scroll

**Dónde:** cloud; 6.5 en la PC. **Parte de:** `player/scroll.s`,
`tools/mkscroll.py` y el formato `yi1_s.dat` (documentado en la cabecera de
`mkscroll.py`).

6.1 **Pantalla de 256 px** (D10).
- DIW centrada, por ejemplo `DIWSTRT $2CA1` / `DIWSTOP $0CA1`, y fetch
  `DDFSTRT $40` (una palabra antes de `$48`) / `DDFSTOP $C0`. **Comprobar
  estos valores con una captura antes de construir encima.**
- `mkscroll.py`: `VIS = 256`. Recalibrar el modelo del copper (`HOFS`,
  `XKNEE`, `HKNEE`, `LASTX`, `BLANKH`) con `copcal.s` + `copcal.py gen/read`
  en la pantalla nueva, porque el borrado horizontal queda más largo.
- Confirmar con una captura que el sprite 7 tiene DMA. Después, volver a
  correr `oamstudy.py`, `d8demote.py` y `copsim.py` con el número real de
  columnas.

**Hecho cuando** `scroll_check` da lo mismo o menos que a 320 px, el coste
queda re-medido y las simulaciones de sprites están re-corridas y anotadas.

**HECHA el 2026-09-27 (PC, WinUAE KS 1.2):**
- `scroll.s` y las herramientas llevan `VIS` (256 por defecto; `-DVIS=320`
  arma la pantalla vieja **byte a byte igual** a la de antes). DIW
  `$2CA1`/`$0CA1`, fetch `$40`/`$C0`, 17 palabras por línea; los valores
  del roadmap eran correctos.
- Copper recalibrado (**P46**): la misma rejilla con h − `$48`,
  x = 8·⌊(h − `$48`)/4⌋ − 1 hasta h = `$C0` (x = 239); después `$C4` → 243,
  `$C8` → 247, `$CC` → 251, `$CE` → 255 (macro `TAILH`). El borrado sigue
  terminando antes de x = 0 (P43).
- Imagen, `scroll_check --mid --sc 2 --w 256`, fallos que no explica un
  vecino: 500: 0, 846: 1, 1000: 0, 1700: 0, 1936: 0, 2500: 0, 3500: 72,
  4500: 75 (a 320: 0, 0, 0, 0, 0, 0, 72, 54; en 4500 la ventana ve otra
  parte del nivel). `scrollsim --speed 2`: 14 868 px mal en todo el
  recorrido (320: 19 586).
- Coste, `-DBENCH -DSPEED=4`: media **22,1 %** (320: 27,3 %), máx. 278,5 %
  en s = 4568 (320: 320,6 %). Musashi: 26 813 ciclos de media (320:
  30 963). A 2 px/frame, 433 frames pasan del frame (320: 487).
- **Sprite 7 con DMA: sí.** `scroll.s -DSPRTEST` dibuja los 8 sprites: a
  256 px se ven los 8 (4 columnas adosadas); a 320, solo 0-5.
- `oamstudy`, `d8demote` y `copsim` dan lo mismo que lo anotado en
  `AGENTS.md` §9 (ya modelaban 256 px y 4 columnas; ahora la premisa está
  medida): 2310 líneas piden 5-6 columnas, 45 de 2500 frames sin resolver
  con un bob, 1916 cargas de la capa 1 que no entran. El borrado no es el
  límite (como mucho 9 MOVE); `--hbl` no cambia nada.

6.2 **Cámara en las dos direcciones.** Hoy `lo_tab`, `vu` y la lista de
cambios de color (`CHG`) solo avanzan.
- Guardar en `CHG` también el valor anterior (o repetir los cambios al
  revés).
- Dibujar la columna nueva por el borde izquierdo.
- Hacer que las sombras de `build_mid` (`vu`, `wake`) valgan también cuando
  `s` baja.
- Prueba: recorrer 0 → 4800 → 0 y comparar las capturas de ida y de vuelta
  en la misma x: tienen que ser idénticas.

**Hecho cuando** la ida y la vuelta dan la misma imagen en 6 puntos.

**HECHA el 2026-09-27 (PC, WinUAE KS 1.2), con una salvedad de 1 píxel:**
- `build_mid` reescrito: las cargas a mitad de línea se planifican en
  `mkscroll.py` **en coordenadas del nivel** (MLD, 12 bytes: clase, x,
  MOVE, a, b) y la Amiga solo copia, por línea, las que caen en
  `[s, s + LASTX]`. Lo escrito queda fijo en pantalla y vale mientras
  `s0 + a <= s < s0 + b` (intervalo por carga); la línea se reescribe cuando
  deja de valer, cuando entra o sale una carga, o cuando la cámara vuelve.
  Solo se miran las líneas de la lista `LNS[s >> 4]`. No depende de la
  dirección.
- `CHG` guarda también el color viejo (se deshace al volver); las columnas
  nuevas entran por el lado hacia el que va la cámara; `-DRETURN=r` y
  `-DS0=n` para probar.
- Simulación (`scrollsim.py`, 2 px/frame): 9282 px mal en todo el nivel
  (antes 14 868); ida y vuelta **idénticas en los 2431 frames** (tras P50).
- Coste (Musashi, CPU sin DMA): media **9,9 %**, peor **54,1 %** (s = 4580);
  antes 22,1 % / 278 % en WinUAE. A 4 px/frame, 13,4 % / 59,2 %.
- Capturas de WinUAE a ida y vuelta (`shots6.ps1 -Extra`, `work/r62f2`,
  `work/r62b2`): idénticas en 500, 1000, 2500, 3500 y 4500; en **1700
  difiere 1 píxel** (línea 174, x = 244): P51, el copper es más rápido
  después de `DDFSTOP` y el modelo no lo tiene. `scroll_check` (fallos que
  no explica un vecino): 0 / 0 / 43-44 / 0 / 72 / 45.

6.3 **Conectar la cámara del port (`mcam.c`) — modo replay.** El scroll deja
de avanzar solo: lo mueve `Bg1HOfs`, calculado por `level_frame()` a partir
del joypad **grabado en el oráculo** (`$15-$18` de `oracle_yi1.txt`, metido
en el ADF). Es la primera prueba de lazo cerrado en la Amiga.
- En el frame N, capturar y comparar con el esperado del PC para la cámara
  `$1A-$1B` del oráculo en N.
- Ventana vertical: en la partida la cámara no se movió nunca en Y (192).
  Confirmar con el ajuste de scroll vertical del header (byte 4, bits 4-5) y
  `lv_scroll.s` si en Yoshi's Island 1 puede moverse. Si puede, dejar el
  soporte vertical para el final y documentarlo.

**Hecho cuando** la Amiga sigue la partida grabada y las capturas coinciden
con el esperado en al menos 5 frames repartidos por el nivel.

**HECHA el 2026-09-27 (PC, WinUAE KS 1.2):**
- `player/game.s`: un solo binario con el C (`level_frame`, datos a menos
  de 32 KB de `binstart`, P36) y `scroll.s` como biblioteca (`SCROLL_LIB`:
  `scroll_init` / `scroll_frame`). Cada frame, desde la línea `$110`:
  entrada → `level_frame` → Mario (6b.4) → `scroll_frame` con
  s = `Bg1HOfs`. El binario se copia solo a la slow RAM (todo es relativo
  al PC o a `a4`) y libera la chip: no entraba en 512 KB. Build:
  `sh tools/game_build.sh` (`GDEFS`, `OUT`).
- `-DREPLAY`: `m68kverify.py --mode loop --sprites --replay` escribe
  `work/yi1_replay.bin`: el tramo 5145-11457 (6313 frames) con el joypad y
  las mismas resincronizaciones del lazo cerrado del PC (RUN 6177, SYNC 3,
  SKIP 129, RUNSYNC 4). La Amiga hace exactamente eso.
- `tools/gamecheck.py`: el binario del juego en Unicorn, frame a frame:
  **0 diferencias** con el oráculo en los 6177 RUN. La cámara recorre 0-2492
  y vuelve (el vertical queda en 192 toda la partida; el header de YI1 no
  tiene scroll vertical).
- Capturas (`tools/shots63.ps1`, `-DSTOPF`): frames 6000 / 7000 / 8000 /
  9000 / 10000 / 11000 → fallos que no explica un vecino **0 / 0 / 0 / 0 /
  0 / 6** (el 11000, con la cámara volviendo).
- Coste de la lógica en el juego (Musashi, sin DMA): media 20,9 %, peor
  29,3 % del frame.

6.4 **Bajar el coste a ≤ 25 %** en el peor frame con columna. Primero,
el pico de s = 4504 (Etapa 0.3). Ideas
anotadas en `AGENTS.md`: `blit_steps` (0.3); en `build_mid`, tablas en vez de
`mulu` y no reescribir las h si `s` no cambió; un solo WAIT por cadena de
cargas (P39). Perfil con `m68kverify.MusashiCPU` y el listado `-L`: el
script de perfil por zonas se perdió con el contenedor y hay que rehacerlo
en `tools/`, no en `/tmp`. **Hecho cuando** `scroll_read.py` da ≤ 25 % de
máximo sin empeorar la imagen.

**Estado al 2026-09-27: NO hecha.** Con el `build_mid` de 6.2 el peor frame
bajó de 278 % (WinUAE) a **54,1 %** (Musashi, cota inferior; en WinUAE sin
medir todavía con `-DBENCH`). Media 9,9 %. 172 de 2432 frames (a 2 px)
pasan del 25 %, en s ≈ 900, 1700-2000, 2600-2700 y 4100-4800.
- Perfil del peor frame (s = 4580, `scrollprof.py --at`): **`build_mid` es
  el 95 %**: reescribe 55 de las 108 líneas con cargas, 276 cargas. Cada
  carga cuesta ~130 ciclos (copiar el MOVE, el intervalo de validez con
  máx./mín., la clase) y cada línea reescrita ~450 más. El bucle ya está
  cerca del mínimo: pulirlo da < 10 %.
- **Hay que reescribir menos líneas.** Las cargas no tienen intervalos
  "sueltos" (ancho b − a: mediana 256, pero 5 % < 43) y casi todo el coste
  del peor frame es "entra una carga por la derecha" (38 de 52 líneas en
  s = 4580). Ideas medidas en simulación (`skipsim*.py`, scratchpad de la
  sesión): añadir por la derecha sin reescribir la línea (−4 % del máximo);
  reescribir desde la primera carga que deja de valer (y desde su WAIT);
  WAIT propio para las cargas de la cola (P51, arregla también 1 px).

**Estado al 2026-09-30 (cloud): sigue sin hacer, con el problema medido.**
- Herramientas: `scrollprof.py --zones` (ciclos por etiqueta de un frame,
  el perfil que se había perdido) y `scrollsim.py --ret` (ida y vuelta,
  compara la imagen simulada en cada s).
- Peor frame de la ida (s = 4580, 76 850 ciclos en Musashi): `build_mid`
  ~95 %, 55 líneas reescritas y 276 cargas (~124 ciclos por carga, ~520 por
  línea, ~7,8 k para recorrer las 108 líneas de LNS). Por qué se reescriben:
  24 líneas por una carga "tarde" (en **todos** los frames, P50; 34 cargas
  tarde en x ≈ 4817-4861, los postes de la meta), 25 porque entra una carga
  por la derecha y 6 porque caduca una.
- **La vuelta es peor que la ida** (P72): media 36,6 %, máx. 94,8 %.
- Probado y descartado: reescrituras completas con validez por ventana
  (modelo: ida máx. 48,6 %, vuelta 78,8 %). En la Amiga salió **peor**
  (máx. 97,6 %: ~330 ciclos por carga) y la ida y la vuelta diferían en
  s = 4684-4780 (P71).
- Siguiente: `tools/wip64/build_mid_incremental.s` (rebase de la h de cada
  WAIT en el sitio, append y truncado por la derecha; en el modelo, ida 38 %
  y vuelta 56 %); para los eventos en bordes verticales, repartirlos entre
  frames (holgura b + 6 px) y neutralizar las cargas muertas en el sitio
  (MOVE a `$1FE`); el recorrido de LNS por grupos de 16 líneas. Modelos en
  `tools/wip64/midsim*.py`.
- FS-UAE: `scroll_check.py` buscaba el origen solo hasta x = 200 (320 px);
  a 256 px daba ~30 % de fallos falsos. Arreglado.

6.5 **PC:** capturas de WinUAE `-Exact` **sin reescalar** en los 6 puntos
contra el esperado del PC, y arranque en KS 1.2.

### Etapa 7 — Capa 2 contra la referencia

**Dónde:** PC.
- `python tools/render_d.py` → `work/yi1_d_nivel.png` (imagen ideal, sin
  paralaje, igual que el mapa estático de la referencia).
- `cmp_ref.py --mine work/yi1_d_nivel.png --mask none --bits 4`. Los colores
  del blob están cuantizados a 12 bits: a 5 bits difiere todo.
- Recortes apilados de todo el nivel (5 tiras de 1024 px) con `crop_ref.py`.

**Hecho cuando** el diff baja del 25,52 % (el valor solo con la capa 1), lo
que queda cae debajo de sprites o es cuantización, y a la vista las montañas,
las nubes y los pilares coinciden.

### Etapa 8 — Mario: cerrar la 8c y bajar el coste

8.1 **Sesión de grabación única** (PC + usuario). Juntar todo lo que hace
falta grabar:
- **Colinas (8c):** a toda carrera en las dos direcciones, parado sobre la
  pendiente, deslizándose y saltando sobre pendientes.
- **Sprites (9):** pisar y tocar cada tipo de D3. Dejar que un Banzai Bill
  cruce la pantalla, que la piraña salga con Mario al lado de la tubería,
  pelear con el Chuck, patear el caparazón rojo y cortar la cinta de meta.
- **Power-ups (D12):** agarrar cada uno; con la flor, disparar.
- **Muerte, punto medio y meta** (12).
- **HUD (10):** hoy el grabador no guarda los contadores (vidas `$0DBE`,
  monedas `$0DBF`, tiempo desde `$0F31`, puntuación desde `$0F34`...). Agregarlos a
  `tools/oambot.lua` **respetando los límites** (V6). Direcciones exactas en
  `equates/memory.i`.
- **Audio (11):** grabar el audio de `smwrecomp` a WAV en la misma partida.

Pasos: probar el grabador (`oamrec.py --test 10`); grabar con `python
tools/oamrec.py --out work/oracle_<nombre>.txt`, **nunca** encima de
`oracle_yi1`; después `oracle2bin.py --inp ... --out ...` y `marioverify
<bin> full` / `loop`. Commitear los `.txt` (V4).

**Desde el 2026-09-30 se graba en cloud, sin el usuario** (P67, P68):
`sh tools/snesorc_setup.sh` clona snesrev/smw (commit fijo) fuera del repo
y compila `work/snesorc`, que corre la ROM (U) en su emulador con los
parches de snesrev deshechos. Un guion `.orc` (`tools/snesorc/`: `N
RIGHT+Y`, `until w$0094>=07B0 max 600 RIGHT+Y`, `assert`, `include`...)
arranca desde el encendido (`boot_yi1.orc` llega a YI1 en el frame 1452) y
vuelca el mismo formato que `oamrec.py`. `sh tools/snesorc_make.sh`
regenera los `.txt` y corre `marioverify`; `--replay` valida el generador
contra `oracle_yi1` (6871/6871 líneas idénticas). Limitaciones: sin
guardar/cargar estado (4000 frames tardan < 1 s), y cambiar una línea de un
guion mueve el RNG y los tiempos de lo que sigue (los `assert` lo detectan).
Lo único que sigue pidiendo la PC es el audio de referencia (11).

**Hecho cuando** las grabaciones están en git y la 8c da 100 % en los frames
de pendiente, o los fallos quedan listados por causa.

8.2 **Optimizar la lógica en C nativo** (cloud; el usuario ya eligió este
camino). Red de seguridad: V1 en cada commit.
1. Perfil: `PROF=1 sh tools/logicbench_build.sh && python3 tools/m68kprof.py
   --sprites`. `m68kprof` no tiene tope: si el binario se cuelga (P38), no
   termina nunca. Probar antes con `m68kverify`.
2. **Estado de Mario en variables nativas.** El coste de fondo es emular la
   WRAM byte a byte: cada valor de 16 bits son 2 lecturas + `lsl` + `or`,
   ~50 ciclos. El método:
   - un accesor (macro en `smwmac.h`) por cada campo caliente: posición,
     subpíxel, velocidades y flags de `$77`/`$72`;
   - en un commit por grupo, el almacenamiento del campo pasa de `ram[]` a
     una variable nativa big-endian;
   - todos los lectores, sprites incluidos, van por el accesor;
   - el verificador sincroniza `ram[]` ↔ variables en la frontera del frame,
     y solo en los builds de verificación.
3. Si el C no alcanza: las sondas de colisión (`f44d`/`f461`/`f545`, ~28 %
   de `level_frame`) en ensamblador a mano, verificadas con `m68kverify`.
4. **No optimizar `e45d`** (OAM de Mario, ~12 % de `level_frame`): en la Amiga Mario no usa
   OAM. En la 6b se reemplaza por la elección directa del frame de sprite.
   La versión OAM queda para el modo `gfx` del verificador.
5. Medir el **peor frame con sprites en cycle-exact**. Hace falta extender
   `logicbench`: meter `spr.lv` en el arnés (apuntar `_spr_level`),
   `level_sprites = 1` y un estado del oráculo con Rex a la vista.

**Hecho cuando** la lógica con sprites da ≤ 40 % en el peor frame (FS-UAE,
DPF encendido) y V1 es idéntica.

**HECHA el 2026-09-27 (PC).** Resultado, WinUAE KS 1.2 a 256 px:
- **Peor frame con sprites** (frame 7901, `logicbench -DWORST`):
  **40,1 %** medido, con ~0,4 % del propio banco (la entrada por
  `callframe`): **~39,7 %** real. Objetivo: ≤ 40 %. Semántica idéntica
  en todo (V1: `regress.py`, `abcheck.py` IGUAL en cada paso).
- **Sin sprites (8d):** 20,2 % corriendo / 20,5 % saltando (antes 25,8 /
  26,3 % a 256 px; 28,3 / 28,8 % a 320).
- Musashi, peor frame con sprites: 52 816 → **40 956** (−22,5 %); media
  con sprites 35 938 → 28 598.

Qué se hizo, por orden de ganancia:
1. **`NOOAM`** (el build de la Amiga no escribe la OAM: sin `ClearOam` ni
   las 4 entradas de Mario; quedan sus efectos en `HidePlayer`/`m4-m6`):
   −8 % en el peor frame, −11,6 % de media. `logicbench_build.sh` compila
   con `CDEFS=-DNOOAM` por defecto; el PC (modo `gfx`) sigue con la OAM.
2. **Ensamblador a mano, `player/logic68k.s`:** `spr_tile`, `f44d`,
   `spr_pos_axis` (con `addx`), `get_draw_info`, `camera_F6DB`, `f7f4`,
   `spr_mario_contact`, `rex_main`, `spr_update_pos`. Cada rutina
   reemplaza a la de C **solo** en el build de la Amiga (vbcc sin
   `NOASM`); el C queda como referencia y para los casos raros (el asm
   salta al C con los mismos argumentos). Las direcciones salen de
   `work/cc/smwram.i` (generado de `smwram.h`, `smwtab.h` y el enum de
   `mario.h`); las tablas de la ROM se leen por puntero
   (`logic68k_init`), nada de la ROM en el asm (R9).
3. C: `sprite_load_level` sin recorrer el nivel, `f04d` con tabla,
   `init_sprite_tables` desenrollado, `spr_tile` sin MULU.

Probado y descartado: flags de vbcc (igual o semántica rota, P38);
partir `sprite_run` para hacer los temporizadores en asm (vbcc deja de
incorporar el despacho y sale peor). Queda sin ensamblador, si hiciera
falta margen: `spr_obj_vert`, `spr_obj_interact`, `spr_spr_interact`,
`eb77`, `f636`, `e92b`, `sprite_run` entero.

**Estado intermedio (histórico):**
- **Dónde estamos.** `logicbench -DVIS256` (la pantalla de la 6.1) en WinUAE
  KS 1.2: 25,8 % corriendo / 26,3 % saltando. Factor WinUAE/Musashi del
  mismo trabajo: **1,39** a 256 px (1,50 a 320). Peor frame con sprites en
  Musashi: 51 354 ciclos → **~50 % estimado** en la Amiga. Objetivo 40 %:
  falta **~−20 %** en el peor frame (≤ ~40 800 ciclos en Musashi).
  El paso 5 (medir el peor frame con sprites directamente en cycle-exact)
  sigue pendiente; esto es una estimación con el factor medido.
- **Perfil** (`m68kprof.py --sprites --every 1 --worst N --at F --hot N`):
  **plano**, ninguna instrucción pasa del 1 %. Por familia: `move` con
  `ram[]` 17 %, `movem`+`jsr`/`rts` ~15 % (llamadas; el build real
  incorpora en línea parte), `and.l #255` y desplazamientos ~14 %
  (promoción de `u8` a `int`). El peor frame persistente (7856-7996) es
  de sprites: `spr_tile` (colisión de sprites con bloques, NO es OAM),
  `sprite_load_level`, `spr_pos_axis`, `get_draw_info`, `rex_main`,
  interacciones; el peor absoluto (9670) es un frame con aparición.
- **Hecho:** `sprite_load_level` sin recorrer el nivel (−2,2 %),
  `init_sprite_tables` desenrollado, `spr_tile` sin MULU (−0,6 %). Peor
  frame con sprites 52 816 → **51 354** (−2,8 %), semántica IGUAL.
- **Descartado:** flags de vbcc. `-speed`, `-inline-size`,
  `-maxoptpasses`, `-unroll-size` dan el mismo binario; `-O=1023`/`4095`
  cambian la semántica (433 resincronizaciones en vez de 37: P38).
- **Lo que queda, por tamaño estimado:**
  1. **OAM fuera del build de la Amiga** (lo que la 6b.4/9.2 reemplaza):
     solo las escrituras directas a `$200-$46F` son el 4,6 % de la media
     (casi todo `ClearOam`); con `e45d` y los gráficos de sprites, ~8-12 %.
     El verificador (`gfx`) sigue con la OAM. Es diseño de la 6b.4: se
     consulta antes.
  2. **Ensamblador a mano** en `f44d`/`f461` (sondas), `spr_tile` y
     `camera_F6DB` (paso 3): ~12 000 ciclos del peor frame; a la mitad,
     ~−12 %.
  3. **Estado nativo** (paso 2): el perfil dice que las rearmadas de 16
     bits ya son pocas; ganancia estimada ≤ 5-8 %.
  Con 1 + 2 se llega; con micro-optimizaciones de C (0,5-2 % cada una)
  no.

### Etapa 6b — Integración: el primer ADF jugable

**Dónde:** cloud; arranque en KS 1.2 en la PC. **Objetivo:** un solo
binario que tome la máquina, cargue el nivel y cada frame lea el joystick,
corra `level_frame()`, mueva el scroll y dibuje a Mario.

6b.1 **Carga y memoria (D13).** Inventario de la chip RAM, estimado a partir
de las constantes actuales (320 px):

| bloque | bytes |
|---|---|
| PF1 circular | 59 136 |
| 2 listas del copper | ~98 800 |
| `yi1_s.dat` | ~126 KB |
| código + datos del C | ~58 KB |

Unos 340 KB antes de sprites y audio. En `yi1_s.dat`, `BLK` y `L2B` las lee
el chipset y se quedan en chip; `MAP`, `CHG`, `MLX`, `MLD` e `INI` las lee
solo la CPU y van a slow RAM.

Pasos, con el esquema de D13 (§3):
1. `tools/mkgame.py` (nuevo): parte los datos en secciones "chip" y "CPU",
   las comprime y escribe la tabla de carga (dirección destino, tamaño,
   alineación), que el loader recorre.
2. Script de enlace de vlink con las direcciones fijas.
3. Loader nuevo (`player/loader.s`), que reemplaza la carga de `demo.s` y
   `scroll.s`, y `tools/mkadf.py` extendido para varios bloques.
4. `tools/memmap.py` (§8.2) comprueba el mapa.

**Hecho cuando** hay un mapa de memoria escrito en `AGENTS.md` §4, con
cifras medidas, el loader lo respeta, el tiempo de carga está medido y
V1 pasa sobre el binario enlazado en absoluto.

6b.2 **Bucle del frame.** Latencia de un frame, como la SNES, que sube en el
NMI lo que calculó el frame anterior:

```
VBL: cambiar a la lista del copper preparada → lanzar el blit de la columna
     → leer la entrada → level_frame() (cámara, Mario, sprites)
     → preparar la lista siguiente (build_mid, punteros de planos y sprites) → esperar el VBL
```

Juntar `scroll.s` y el arnés del C, enlazados en absoluto con vlink (D13).
`m68kverify`/`abcheck` tienen que aprender a cargar el binario en su
dirección fija, en vez de en `BASE`. Después de juntarlos, correr V1 sobre
el binario nuevo.

6b.3 **Entrada (D14), teclado primero.**
- **Teclado.** Al tomar la máquina, el SO ya no lee el teclado: hace falta
  un manejador propio.
  - Interrupción de nivel 2 (`PORTS`, CIA-A `ICR` bit `SP`).
  - Leer `CIA-A SDR`; el código raw es `~byte` rotado un bit a la derecha
    (`not.b` + `ror.b #1`); el bit 7 = tecla soltada.
  - **Handshake:** poner `CIA-A CRA` bit 6 (`SPMODE` salida) durante
    ≥ 85 µs (unas 2 líneas; medir con `VHPOSR`, no con un bucle) y volverlo
    a entrada. Sin handshake, el teclado reintenta y se pierden teclas.
  - Mantener un mapa de 128 bits de teclas apretadas.
- Asignación de §3 (D14) en una tabla.
- **Joystick** (alternativa): `JOY1DAT`, fuego en CIA-A `PRA` bit 7 y 2.º
  botón en `POTGO`/`POTINP`; se combina con el teclado con un OR.
- Convertir al formato de la SNES en `$15-$18`: `JoyPadA/B` = mantenido y
  `JoyFrameA/B` = recién apretado (`nuevo & ~anterior`), que es lo que
  espera el port.
- Teclas de depuración reservadas, que no usa el juego: pausa por frames y
  modo replay.

6b.4 **Mario en sprites de hardware.**
- Herramienta nueva `tools/mkmario.py`: toma las poses que aparecen en el
  oráculo (el modo `gfx` da los tiles de cada frame) y los tiles de `chr` a
  4 bpp, y genera frames de **sprites adosados** (16 colores) con las
  versiones volteadas precalculadas: el hardware no voltea.
- Comprobar el ancho máximo de las poses. Si alguna pasa de 16 px, usar un
  segundo par de sprites.
- La paleta de Mario (P10) va a los colores 17-31, cuantizados a 12 bits.
  En DPF esos colores no los usa nadie.
- Ajustar `BPLCON2` (`PF1P`/`PF2P`) para que los sprites queden delante de
  las dos capas. Hoy vale `$0000` porque no hay sprites.

6b.5 **Verificación.** El modo replay de la 6.3 + Mario: la captura del
frame N tiene que coincidir con el render del PC para la cámara y la OAM de
Mario del oráculo en N. Extender `scroll_check.py` o escribir
`game_check.py`.

6b.6 **Medida.** Peor frame del juego integrado, con `-DBENCH` y FS-UAE →
**compuerta D1** (§2).

**Estado al 2026-09-27 (en curso):**
- 6b.1: el juego carga con el loader de siempre (`boot.s` + `mkadf.py`):
  binario (~180 KB) a slow RAM y `yi1_s.dat` a chip. Sin compresión ni
  vlink todavía.
- 6b.2: hecho en `game.s` (arriba, 6.3). Latencia de un frame: la lista del
  copper, los punteros de sprites y la paleta de Mario de un frame se ven
  juntos.
- 6b.3: `game.s` sin `-DREPLAY` = en vivo. Teclado por la interrupción de
  nivel 2 (handshake de >= 2 líneas con `VHPOSR`), tabla D14 (`keytab`),
  joystick del puerto 2 (botón 1 = B, arriba + botón = A, botón 2 = Y), OR
  de los dos → `$15-$18`. Lo que el port no tiene (animaciones de Mario,
  meta, tuberías...) congela el frame: a los 1,5 s el nivel vuelve a
  empezar (se guardan al cargar los datos del C y el mapa). Daño sin
  animación: grande → chico con invulnerabilidad; chico → reinicio.
  **Sin probar con teclas en el emulador todavía.**
- 6b.4: `mgfx.c` (NOOAM) deja las 4 entradas de Mario en `mario_oam` /
  `mario_osz` y la paleta en `mario_pal`; `player/mspr.c` (referencia) y
  `player/mspr68k.s` (el caso de siempre, con `MOVEP.W`, ~10 400 ciclos =
  7,3 %) arman dos parejas de sprites adosados desde GFX32
  (`tools/mkmario.py`: `gfx32.bin`, `gfx32f.bin` volteado, `mario_pal.bin`).
  `marioverify mspr` (PC, `-DNOOAM`): OAM = oráculo y sprites = render de
  referencia en 6869/6869; `gamecheck.py --spr`: vbcc y asm = referencia en
  6184/6184 (el asm fue al C 1 vez). Coste extra de la lógica por llenar
  `mario_oam`: ~2 300 ciclos (Musashi, peor frame con sprites 43 280).
- 6b.5: `tools/game_check.py` (fondo + Mario contra la captura).

**Hecho cuando** el ADF se juega con joystick en FS-UAE y en WinUAE con
KS 1.2, el replay coincide con el oráculo y el presupuesto está medido y
presentado al usuario.

### Etapa 9 — Sprites del nivel

9.1 **Lógica** (cloud; en paralelo con la 6 y la 8.2).
- Orden (D3, por frecuencia y porque destraba la verificación):
  1. Koopa sin caparazón (`$02`, sale del Sliding Koopa `$BD`): es la última
     resincronización de `game`;
  2. Banzai Bill (`$9F`);
  3. Jumping Piranha (`$4F`);
  4. Clappin' Chuck (`$95`);
  5. caparazón rojo (`$DB` → `$05`, estado 9);
  6. cinta de meta (`$7B`);
  7. warp hole (`$8E`) y champiñón invisible (`$C7`);
  8. lo que sale de los bloques (D12, §3): seta, flor y **bolas de fuego**
     (`MARIO_UNSUP_FIRE`), estrella (invencibilidad + música), 1-UP, luna
     3-UP, champiñón invisible, monedas, monedas de Yoshi y puntos. Más la
     caja de reserva y el crecer / encoger de Mario (animación `$71`, hoy
     "sin física normal").
- Método (P27): transcribir `sprite_*.s` instrucción por instrucción, sobre
  `ram[]` como el Rex; tablas de otros bancos con `tools/smwtabx.py`.
- Verificar con `marioverify game` / `sprloop` y `m68kverify --sprites`
  (V1). Trampas conocidas de la 9: `ROL` del carry en `CODE_01A56D`,
  `RexSpinKill` pasa a estado 4 y no a 0, y al resincronizar hay que copiar
  también `SpriteXAcc`/`YAcc`.
- Si la grabación no cubre el comportamiento de algún sprite, pedirlo en la
  sesión única (8.1), no en una aparte.

**Hecho cuando** `game` da 0 resincronizaciones, o solo por eventos
documentados como fuera de alcance.

**Estado al 2026-09-30:** portados y verificados `$BD`, `$02` (sin la
parte de caparazones), `$9F`, `$4F`, `$8E` y `$C7`, más el contacto por
defecto con Mario (pisotón, salto con giro, daño), los estados 2-4,
`GetDrawInfoBnk1`, `FlipSpriteDir`, las pendientes empinadas y la carga de
los sprites al empezar el nivel (P65). `game` da 0 resincronizaciones en
`oracle_yi1` y en las 4 grabaciones de snesorc; `regress.py` cuenta los
frames exactos por tipo de sprite (`pc.game.spr_XX.*`). Sin verificar:
Banzai pisado, `$02` con caparazones, salto con giro sobre el Koopa, tocar
el `$C7`. Sin portar: Chuck (`$95`, nunca aparece en `oracle_yi1`: grabarlo
con snesorc), caparazón rojo, cinta de meta y los power-ups.

9.2 **Dibujo en la Amiga** (cloud; diseño de D8 (d), `AGENTS.md` §9 puntos 9
y 10).
1. **Antes de programar**, volver a correr `oamstudy.py`, `d8demote.py` y
   `copsim.py` con el número real de columnas (6.1) y la pantalla final.
2. Conversor: gráficos de cada sprite (Rex y Banzai en el GFX `20`) →
   frames de sprites adosados, más la versión bob con máscara. Paleta por
   fila de cada objeto.
3. Asignador por frame (CPU): objetos → columnas por franja de líneas. El
   copper recoloca `SPRxPOS` entre líneas y recarga los colores 17-31 por
   línea. Si una línea pide más columnas de las que hay, un objeto pasa a
   bob en PF1: casi siempre el Banzai (`d8demote`). `copsim.py` es la
   implementación de referencia: la salida de la Amiga se compara contra la
   suya.
4. Bobs en PF1: se restauran desde `BLK`. Ojo con el buffer circular: un bob
   que cruza el reenganche tiene que ir a las dos copias.
5. Verificar: el replay contra el esperado con la OAM de `oam_yi1.txt`.
   Medir el peor frame: Banzai + 4 Rex + Mario.

**Hecho cuando** los objetos se ven 1:1 en las capturas del replay y el
coste entra en §2.

### Etapa 10 — HUD

1. Medir en `yi1_d` con la cámara Y final cuántas líneas ocupa el HUD de la
   SNES y si en ellas aparece alguna vez la capa 1. Si aparece, buscar una
   variante que conserve el overlay antes de consultar (D11). Por ejemplo:
   el HUD en PF1 con los colores 1-7 del HUD y la capa 1 de esas líneas
   compuesta en el mismo bitmap, que es barato si son pocas líneas.
2. Overlay (D11): en esas líneas, el copper apunta PF1 a un bitmap fijo del
   HUD (retardo de PF1 = 0, colores 1-7 del HUD) y PF2 sigue igual. Gráficos
   de la barra: tiles de capa 3 a 2 bpp (los `gb-*`; `gb-1` es el juego de
   caracteres). Los números y la reserva se blitean solo cuando cambian.
3. Lógica: portar la actualización de la barra de `game.s` (tiempo,
   monedas, vidas, puntuación, monedas de Yoshi, estrellas, reserva).
   Verificar contra los contadores de la grabación 8.1.

**Hecho cuando** la barra coincide con la referencia y con los contadores
grabados, y el coste es ≤ 2 %.

### Etapa 11 — Audio (D5)

1. `tools/brr2pcm.py`: BRR (ADPCM) → PCM de 8 bits **con signo** (P7), sin
   sesgo DC. Verificar contra el WAV de `smwrecomp` (8.1).
2. D5: convertir offline las secuencias de `sound/` (N-SPC) a un formato
   compacto de eventos con los efectos ya resueltos:
   - notas con periodo de Paula precalculado;
   - glissando y vibrato como tablas de deltas por tick;
   - envolvente ADSR como tabla de volumen por tick.

   El secuenciador 68000 solo recorre eventos y escribe `AUDxPER`/`AUDxVOL`/
   `AUDxLC`/`AUDxLEN`: nada de mezcla ni de cálculo por muestra. El tick sale
   de un timer de CIA, no del VBL: el tempo del SPC700 no depende de 50/60 Hz.
3. 8 voces → 3 de música + 1 de efectos. Elegir las voces por prioridad en
   cada tema (y la de la estrella). El eco no existe: se omite. Cuando suena
   un efecto, la voz de música que comparte canal se silencia, como en la
   SNES con prioridades.
4. Efectos: el port ya escribe los disparadores (`wm_SoundCh1/2/3`, por
   ejemplo en `mario.c`): engancharlos ahí.
5. Presupuesto: ≤ 64 KB de muestras en chip RAM y **≤ 3 %** de CPU
   (medido con el método de `bench2.s`).

**Hecho cuando** el tema del nivel y los efectos principales (salto,
moneda, pisotón, power-up, 1-UP) suenan reconocibles contra el WAV de
referencia, con el coste medido.

### Etapa 12 — Pulido y entrega

- Muerte y reinicio, punto medio, cinta de meta y secuencia final, tiempo
  agotado, transiciones con fundido por copper.
- Si alguna tubería del nivel es entrable (mirar las salidas de pantalla
  del nivel), su transición.
- Prioridad sprite/capa 1 donde la SNES pone a Mario detrás, por ejemplo
  el poste de la meta.
- ADF final: bootblock propio + loader de todas las pistas, ≤ 880 KB.
  Probado en WinUAE con KS 1.2 y 1.3, y en hardware real si el usuario
  quiere (opcional).
- R9: el ADF lleva material derivado de la ROM; es de uso personal y no se
  distribuye.

**Hecho cuando** se puede jugar el nivel de principio a fin en la
configuración objetivo, a la frecuencia que fijó D1, y `AGENTS.md` §10 queda
cerrado.

---

## 6. Riesgos principales

| riesgo | señal | mitigación |
|---|---|---|
| El frame no entra a 50 Hz | §2: la suma pasa del 100 % | optimizar antes de sumar coste (6.4, 8.2); compuerta D1 |
| Picos escondidos | un frame suelto muy caro (hoy: 307 % en s = 4504 en el scroll) que la media no muestra | medir siempre el máximo **y dónde ocurre**; los bancos descartan solo los frames de arranque |
| Faltan columnas de sprites | con `DDFSTRT $30` solo quedan 3 adosadas | D10 = 256 px; bob en PF1 (`d8demote`) |
| vbcc compila mal | `m68kverify` llega al tope de 10 M ciclos o difiere de `marioverify` | V1 siempre (P38) |
| Datos del C > 32 KB con `-sd` | `logicbench_build.sh` falla o hay referencias absolutas | D13: enlazado absoluto con vlink (6b.1) |
| Índices de 16 bits con signo | escrituras 64 KB antes a partir de 32 KB | `(An,Dn.l)` con `moveq #0` antes (P40) |
| El modelo de tiempos del copper | cargas corridas unos píxeles | calibrar con `copcal` en cada pantalla nueva (0.4, 6.1); los WAIT cuestan ranura (P39) |
| El oráculo no cubre un caso | un sprite o una pendiente sin frames que verificar | sesión de grabación única (8.1) |
| Chip RAM | ~340 KB antes de sprites y audio | D13: lo que solo lee la CPU, a `$C00000` |

---

## 7. Plantilla de handoff (para el que cierra la sesión)

Reemplaza §1 entero. Tiene que caber en una pantalla o dos.

```markdown
## 1. Handoff (estado al AAAA-MM-DD)

### 1.1 Ramas
rama base, commit de la cabeza, qué hay sin mergear, si queda algo WIP y por qué.

### 1.2 Estado por etapa
la tabla, con cifras medidas (no "funciona"): %, px, frames, ciclos.

### 1.3 Números de regresión
la tabla, con los valores nuevos donde cambiaron y la fecha.

### 1.4 / 1.5
solo si cambió el entorno o el arranque.

### 1.6 Pendiente del usuario o de la PC
decisiones, grabaciones y pruebas que el agente no puede hacer.

### Lo último que se hizo y lo siguiente
3-6 viñetas: paso de §5 en el que se quedó, qué falta para cerrarlo, el
comando exacto para retomar, y las hipótesis sin comprobar (marcadas así).
```

Reglas: nada sin commitear al cerrar (si queda a medias, commit `WIP:` que
diga qué falta verificar); cifras con su fuente (herramienta y emulador); lo
estimado, marcado como **estimado**; lo que se perdió con el contenedor
(scripts en `/tmp`), recreado en `tools/` o anotado.

---

## 8. Comprobaciones: los scripts

Todo cambio pasa por estos scripts **antes del commit**. Corren en cloud y
en la PC; solo necesitan la biblioteca estándar de Python, salvo lo que se
indica.

| script | qué comprueba | cuándo | tiempo |
|---|---|---|---|
| `tools/lint_port.py` | reglas que el compilador no ve. **Errores**: R9 (nada derivado de la ROM en git), `float`/`double`, `malloc`, `#include <...>` fuera de un `#if`, el patrón de P38 (`p = ram + x` indexado con `p[wm_X]`). **Avisos**: `(An,Dn.w)` en asm (P40; una línea revisada se marca con `; P40 ok`) e `int` a secas | antes de cada commit | 1 s |
| `tools/regress.py` | **compila desde el código actual** y compara ~40 métricas (~55 con `--level --emu`) con `tools/baseline.json`. Cubre los 7 modos de `marioverify`, `m68kverify` (full, loop y loop con sprites, con ciclos) y los **cruces PC = 68000** (si el binario de vbcc no da lo mismo que gcc es P38, no el port) | antes de cada commit que toque `player/` o las herramientas del port | 4 s |
| `tools/regress.py --level` | + la cadena de la etapa 5 (`mkbg` → `mkleveld` → `mkscroll` → `render_d`); necesita numpy | si se tocó el conversor | ~1-2 min |
| `tools/regress.py --emu logic,scrollbench,scrollimg` | + medidas en FS-UAE cycle-exact: `logicbench` (% de frame), `scroll.s -DBENCH` (media y máximo, con la s del peor frame) y `scroll_check --mid` en 6 x del nivel (`--scroll-x` para elegirlas). Si una captura no está en la x pedida (> 20 % distinto), lo dice en vez de contarlo como fallo de imagen | al cerrar un paso de optimización o del scroll | ~13 min |
| `tools/regress.py --shots DIR` | lee capturas ya hechas (en la PC, las de `shot.ps1 -Exact`): `DIR/logicbench.png`, `DIR/scrollb.png`. La base del repo es de FS-UAE: en la PC usar `--baseline tools/baseline_winuae.json` (se crea con `--update` la primera vez) para no mezclar emuladores | en la PC | s |
| `tools/abcheck.py BASE [--sprites] [--prof]` | A/B de una optimización: compila `BASE` (en un worktree) y el árbol actual y los corre en Musashi. Dice si la **semántica es igual** (resincronizaciones y tramo) y cuánto cambian los ciclos de media, p99 y máximo; con `--prof`, también por función | cada optimización del C | 3 s (`--prof`: ~2 min) |
| `tools/imgdiff.py A.png B.png` | dos capturas del mismo emulador son **idénticas** (sale con 0) o no, con la caja y un PNG de las diferencias. Las capturas de FS-UAE son deterministas: comprobado con dos corridas de x = 1000 | optimizar `scroll.s` (antes/después); scroll de ida y de vuelta (6.2) | s |

Resultados de `regress.py`, por métrica:
- **OK:** igual a la base, dentro de la tolerancia.
- **MEJOR:** no falla. Si el cambio es intencional, `--update` y explicarlo
  en el commit.
- **PEOR** o **FALTA** (la herramienta murió o cambió su salida): fallan, y
  el script sale con 1.

Las métricas tienen dirección: `eq` (tiene que dar exactamente lo mismo),
`max` (más es mejor), `min` (menos es mejor) e `info` (solo se muestra).
Detalles de uso:
- La salida completa de cada herramienta queda en `work/regress.log`; lo
  medido, en `work/regress_last.json`.
- `--update` **se niega** si hay fallos (una base peor esconde regresiones);
  `--update --force` solo para un cambio de alcance explicado en el commit.
- `--accept-last` pasa a la base lo de la última corrida sin volver a medir
  (útil después de una corrida `--emu` larga).

### 8.1 Flujo según lo que se cambia

| cambio | pasos |
|---|---|
| lógica en C (`player/*.c`) | `lint_port.py` → `regress.py` → si era para ganar ciclos, `abcheck.py <commit anterior> --sprites` (semántica IGUAL y ciclos menores) → al cerrar el paso, `regress.py --emu logic` → commit. Si algo sale MEJOR, `--update` en el mismo commit |
| optimización de `scroll.s` | capturas con el mismo `-DSTOPX` antes y después → `imgdiff.py` tiene que dar IDENTICAS en las 6 x → `regress.py --emu scrollbench` (media y **máximo** menores). La versión "antes" sale de `git show BASE:player/scroll.s > work/scroll_base.s` y se arma igual, con `-I player` |
| función nueva de `scroll.s` | `scroll_check.py --mid` en las 6 x (fallos que no explica un vecino ≤ base) → `regress.py --emu scrollimg,scrollbench` → `--update` |
| conversor del nivel | `regress.py --level` (`render_d`: 0 px contra la imagen ideal) |
| etapa nueva | agregarle métricas a `regress.py` (una función `xxx_checks` que corre la herramienta y hace `r.put(nombre, valor, dirección)`) y guardarlas con `--update` |

### 8.2 Comprobaciones que hay que crear con cada etapa

Cada etapa futura tiene que dejar su propia comprobación automática, y
engancharla en `regress.py`. Especificación mínima:

| etapa | script a crear | qué compara | pasa si |
|---|---|---|---|
| 6.1 | parametrizar `scroll_check.py` (`--w`, `--sc`, origen) | capturas a 256 px y capturas de WinUAE ×2, no solo FS-UAE ×2,125 | lo mismo que hoy a 320 px |
| 6.2 | `-DRETURN` en `scroll.s` + `imgdiff.py` | captura en x a la ida y a la vuelta | IDENTICAS en 6 x |
| 6.3 / 6b.5 | `tools/replay_check.py` | ADF en modo replay parado en el frame N (`-DSTOPFRAME=N`) contra el esperado del PC: cámara `$1A-$1D` del oráculo + `yi1_d.dat` (+ la OAM de Mario de `oracle_yi1_oam.bin` desde la 6b) | ≤ 0,25 % de fallos limpios que no explica un vecino, en ≥ 5 frames repartidos por el nivel |
| 6b.1 | `tools/memmap.py` + chequeos en el arranque | a partir del listado de vasm (`-L`) y de la tabla del loader: todo lo que lee el chipset < `$80000`; planos alineados a 8, listas del copper a 4 y audio a 2; total de chip ≤ 512 KB. En la Amiga, al arrancar: `$C00000` responde (P8) y cada `AllocMem` quedó alineado; si no, color de borde de error, como `demo.s` | 0 violaciones; el arranque no pinta el borde de error |
| 6b.3 | `tools/inputtest.c` | tabla de casos de la conversión joystick → `$15-$18` (flanco: `JoyFrame = nuevo & ~anterior`) | todos los casos |
| 6b.4 | `tools/mkmario.py --selftest` | ida y vuelta: frames de sprite adosado → píxeles contra los tiles de `chr` renderizados, volteados incluidos | todas las poses idénticas |
| 9.1 | modo `marioverify game` con contadores por número de sprite | frames exactos de cada tipo (Banzai, piraña, Chuck...) | 100 % o fallos listados por causa |
| 9.2 | `tools/sprcop_verify.py` | el asignador de columnas del 68000, corrido en Musashi (como `m68kverify`) sobre los frames de `oam_yi1.txt`, contra el modelo de `copsim.py`: palabras de control de sprite, MOVE de color, objetos que pasan a bob | 0 objetos sin mostrar; colores mal solo donde `copsim` también falla |
| 10 | modo `marioverify hud` | contadores del port contra los grabados en la 8.1 (vidas, monedas, tiempo, puntos) | todos los frames |
| 11 | `tools/brr2pcm.py --selftest` + un render offline del secuenciador | PCM contra el WAV de `smwrecomp` (correlación ≥ 0,99 por muestra); notas a ±1 tick y ±5 cents | los umbrales |
| 12 | replay completo sobre el ADF final | el modo replay se queda en el binario final como opción de compilación: la partida grabada termina en la meta en el mismo frame que el oráculo | llega a la meta, mismo frame |

---

## 9. Optimización: plan e ideas (2026-09-30)

**Método (siempre):** medir el peor frame y **dónde** ocurre → cambiar
**una** cosa → verificar la semántica (`regress.py`; el C con `abcheck.py`;
`scroll.s` con `scrollsim.py --ret` + `imgdiff.py`) → medir en cycle-exact
(`regress.py --emu`). Se optimiza el **peor frame**, no la media: el frame
que no entra en 20 ms es el que se nota.

**Regla de conversión** (medida en la 8.2 y en la 6.4): en la A500, con el
DMA de 6 planos, un trabajo cuesta ~1,3-1,4 veces lo que da Musashi.
O sea, **~1 000-1 100 ciclos de Musashi por cada 1 % de frame** en la
Amiga (un frame PAL son 141 876 ciclos; en la parte visible de cada línea
el DMA de planos se lleva la mitad de las ranuras pares).

### 9.0 Dónde estamos y a dónde hay que llegar

Peor frame por partes (el del juego entero sin medir: es el paso O1):

| parte | peor frame hoy | dónde | objetivo | falta |
|---|---|---|---|---|
| scroll a la ida (`build_mid` + columna) | 78,8 % (FS-UAE, 4 px/frame) | s = 4584 (postes de la meta) | ≤ 25 % | −54 puntos |
| scroll a la vuelta | 94,8 % en Musashi (≈ 125 % en la Amiga, **estimado**) | s = 2832 | ≤ 25 % | −100 puntos |
| lógica con sprites (`level_frame`) | 45 896 ciclos en Musashi ≈ 45 % | frame 9714 (2 pirañas, Rex, `$8E`, `$C7`) | ≤ 40 % | −6 000 ciclos |
| Mario en sprites (`mspr_draw`) | ~10 400 ciclos ≈ 7,3 % | cada cambio de pose | ≤ 3 % | −4 000 ciclos |
| sprites del nivel (9.2) | sin hacer | — | ≤ 8 % | diseñarlo barato (9.5) |
| HUD / audio | sin hacer | — | ≤ 2 % / ≤ 3 % | — |
| **margen** | — | — | **≥ 10 %** | — |

La suma de los objetivos da 81 % + margen. Hoy el peor caso pasa del
130 %. **Lo que manda es el scroll**; la lógica está cerca.

### 9.1 Paso 0: medir el frame entero (O1-O3)

Sin esto se optimiza a ciegas; además es la **6b.6 (compuerta D1)**.

- **O1. `game.s -DBENCH`:** timer A de CIA-B al principio y al final de
  cada parte (entrada, `level_frame`, `mspr_draw`, `scroll_frame`:
  columna, `build_mid`, lista), **por frame**, en el replay. Se guardan el
  peor frame de cada parte y el del total, con su frame y su s, y se
  escriben en pantalla como bits (el método de `bench.s`), con un lector
  `tools/game_read.py --auto`. Enganchar a `regress.py --emu game`.
- **O2. Escenarios de estrés con snesorc:** `oracle_yi1` no recorre los
  peores casos. Guiones `.orc` nuevos:
  - la cámara volviendo a toda velocidad sobre s ≈ 2600-2900 y 4100-4800,
    las zonas caras del scroll;
  - Banzai + 4 Rex + Mario a la vez en pantalla;
  - las 2 pirañas del frame 9714 con Mario corriendo.

  Pasarlos por `m68kverify.py --replay` → `game.s -DREPLAY -DBENCH`.
- **O3. En `regress.py`:** los ciclos del peor frame por parte en Musashi
  (`gamecheck.py --engine musashi`, que tiene que aprender a correr
  también `scroll_frame`) y el scroll en los **dos sentidos**
  (`scrollprof.py -D RETURN=4864 --stopx 0`). Hoy `-DBENCH` solo mide la
  ida (P72).

### 9.2 Scroll: `build_mid` (lo más grande)

Reparto del peor frame de la ida (s = 4580, 76 850 ciclos en Musashi, ver
Etapa 6.4): 55 líneas reescritas enteras, 276 cargas (~124 ciclos cada
una) + ~520 por línea + ~7 800 para recorrer las 108 líneas de LNS.
Por qué se reescriben:

| motivo | líneas |
|---|---|
| una carga "tarde" (se reescribe en **todos** los frames, P50) | 24 |
| entra una carga por la derecha | 25 |
| caduca una carga | 6 |

A la vuelta, casi todo se reescribe en cada paso (P72). Ideas, de más
barata a más cara:

- **S1. Las cargas "tarde", arregladas en origen.** Son 34, en
  x ≈ 4817-4861 (los postes de la meta), y cada una fuerza su línea unos 128
  frames seguidos.
  - (a) Clasificación fija, con la línea canónica (P71) y la h en celdas de
    8 px: la línea se reescribe cada 8 px de s, no en cada frame.
  - (b) En `mkleveld.py`/`mkscroll.py`, repartir los registros cerca de los
    postes para que las ventanas se puedan cumplir. Si hace falta, aceptar
    un derrame de 1 px donde no se ve (P44).
  - (c) Dibujar los postes con 2 sprites de hardware adosados (15
    colores). En la meta casi no hay enemigos: saca esas cargas del copper.
  - Estimado: −20-30 % del peor frame de la ida.
- **S2. Recorrer LNS por grupos de 16 líneas** con el mínimo de cada grupo
  (el `gmin_a/b` del WIP viejo): de ~7 800 a ~1 000 ciclos en los frames en
  que casi no cambia nada.
- **S3. Escribir cada cambio una sola vez.** Hoy cada lista (A y B) tiene
  su sombra (`V_LSA`/`V_LSB`) y **cada línea que cambia se reescribe dos
  veces**: en la lista de este frame y en la del siguiente. Como un
  segmento vale para un intervalo de s, las dos listas pueden compartirlo:
  un pool con 2 ranuras por línea; la que cambia se escribe en la ranura
  libre y las dos listas se reenganchan (2 palabras cada una). La trampa:
  el salto al segmento siguiente está **dentro** del segmento, así que
  compartirlo obliga a sacar los saltos a una "columna vertebral" por
  lista, que gasta MOVE del copper en el borrado. Medir primero con
  `copcal` si entran (P39, P43, P46). Estimado: hasta −50 % de
  `build_mid` en régimen.
- **S4. Editar en el sitio en vez de reescribir la línea** (el diseño de
  `tools/wip64/`): rebase (solo el byte h de cada WAIT), append y truncado
  por la derecha. En el modelo: ida 48,6 → 38 %, vuelta 78,8 → 56 %. La
  imagen queda igual por construcción si la clasificación "tarde" es fija.
- **S5. Repartir entre frames con un presupuesto.** Cada evento tiene una
  holgura de b + 6 px, así que no hace falta atenderlo en el frame en que
  aparece. Una cola por plazo (EDF) con un tope de ciclos por frame: lo
  urgente primero, el resto después. Aplana el pico hacia la media (hoy
  14,9 % a la ida). Las cargas muertas se neutralizan en el sitio (el MOVE
  pasa a `$1FE`) en vez de reescribir.
- **S6. Un plan por sentido.** El plan pone las cargas lo antes posible
  (a ≈ 0), así que sirve hacia la derecha y casi nada hacia la izquierda
  (P72). Un segundo plan con las cargas lo más tarde posible (ALAP) para
  cuando la cámara va a la izquierda, o las cargas en el centro de su
  ventana para los dos sentidos. Cuesta otro MLD en slow RAM.
- **S7. Menos cargas desde el origen.** Cada carga que no existe ahorra
  CPU y ranuras del copper. Mejor asignación de registros en
  `mkleveld.py` (intervalos que se reusan, preferir el registro que ya
  tiene el color) y más variantes de bloque. Hoy son 244; quedan ~117 KB
  de chip. Medir antes la distribución de cargas por línea visible.
- **S8. El blitter copia los segmentos.** Si las palabras del copper de
  cada segmento están precalculadas en chip, un blit A → D las copia
  mientras la CPU corre la lógica; la CPU solo parchea las h. Evaluarlo
  después de S3-S5: depende de cuánta chip haga falta.

Orden propuesto: S1a + S2 (baratas) → S4 → S5 → S3 → S6. Hecho cuando el
máximo es ≤ 25 % **en los dos sentidos** y en los escenarios de O2, con
`scrollsim.py --ret` (≤ 9282 px, ida = vuelta) y las capturas de las 6 x
sin empeorar.

### 9.3 Lógica (`level_frame` con sprites)

Perfil del 2026-09-30 (`PROF=1 sh tools/logicbench_build.sh &&
python3 tools/m68kprof.py --sprites --worst 5`), en ciclos propios por
frame, sin inline:

| función | media | peor frame real (9709) |
|---|---|---|
| `mario_E2BD` (gráficos de Mario) | 3 970 (12 %) | 4 020 |
| `f44d_asm` (sondas, 5,5 por frame) | 3 060 | 2 740 |
| `spr_tile_asm` | 890 | **2 300** |
| `sprite_run` (temporizadores, ~500 por ranura) | 980 | **2 020** |
| `camera_F6DB` | 1 720 | 1 810 |
| `eb77` / `sprites_all` / `f636` / `mario_D5F2` | 1 030-1 350 cada una | 1 040-1 540 |
| `f7f4_c` (scroll vertical hacia arriba: el asm cae al C) | 510 | **1 390** |
| `spr_obj_interact` / `spr_obj_vert` / `sprite_main` / `jumping_piranha` | 470-550 | 1 050-1 250 cada una |

(El frame 4437 cuesta 53 818 porque paga `probe_init`, 21 454 ciclos: no
es un frame del juego, P64.)

Ideas, por ganancia estimada en el peor frame (hacen falta −6 000):

- **L1. Ensamblador a mano** (el C queda de referencia, como en la 8.2):
  - la rama hacia arriba de `f7f4`: −1 000 en los frames en que Mario sube;
  - `sprite_run` + el despacho de `sprite_main`: −1 000-1 500 con varios
    sprites vivos;
  - `mario_E2BD`: −1 500-2 000 en todos los frames;
  - `spr_obj_interact`/`spr_obj_vert`/`spr_spr_interact` y
    `jumping_piranha`.
- **L2. Descartes rápidos:** `spr_spr_interact` es O(n²): descartar por
  |dx| antes de la caja completa. Lo mismo con el contacto con Mario
  (`DefaultInteractR` en C). Casi siempre están lejos.
- **L3. Estado nativo** de los campos calientes de Mario (8.2, paso 2):
  ≤ 5-8 % estimado. Queda para el final: toca todo el C.
- Verificar cada paso con `abcheck.py <base> --sprites` (semántica IGUAL) y
  con `regress.py`, que corre los cruces de la RAM entera (`--cross`); el
  vbcc de cloud compila mal cosas que gcc compila bien (P38, P62).

Hecho cuando el peor frame con sprites da ≤ 40 % en cycle-exact
(`logicbench -DWORST`) y en los escenarios de O2.

### 9.4 Mario en sprites (`mspr_draw`, 7,3 %)

Medido en el replay (6313 frames): la pose dibujada (punteros de tiles
`wm_0D85` + la OAM relativa) cambia en el **33,5 %** de los frames, y hay
**987** combinaciones distintas.

- **M1. No redibujar si la pose no cambió:** solo SPRxPOS/SPRxCTL. −66 %
  de media. **No** baja el peor frame, que es un cambio de pose.
- **M2. Precalcular todas las poses:** 987 × ~544 B ≈ 530 KB: no entra en
  chip. Descartado.
- **M3. Caché LRU de N poses** en chip (16 × 544 B ≈ 9 KB): ayuda a la
  media (el ciclo de caminar repite 3 poses), no al peor frame.
- **M4. Bajar el coste del dibujo en sí:** perfilar `mspr_draw` por
  etiquetas (como `scrollprof.py --zones`) y atacar lo que salga: filas
  vacías, entradas que se tapan entre sí, el camino del volteo. Objetivo:
  ≤ 3 %.
- **M5. Hacerlo fuera de la pantalla:** es trabajo de bus puro. Hacerlo en
  las 88 líneas sin DMA de planos lo abarata ~1,3×.

### 9.5 Sprites del nivel (9.2): baratos desde el diseño

- Frames **precalculados** por pose (Rex, Banzai, piraña, Koopa...) en chip,
  listos para el DMA de sprites. La CPU solo escribe las palabras de
  control y los punteros; nada de dibujar por CPU.
- Reusar un canal en vertical sin copper: después de la última línea de un
  objeto van las palabras de control del siguiente (0 MOVE).
- Colores 17-31 recargados por el copper solo donde cambian (filas de
  color precalculadas por pose, `copsim.py`).
- Asignador de columnas con coste acotado: ≤ ~10 objetos en pantalla,
  ordenados por Y una vez por frame (inserción: casi ordenados de un frame
  al siguiente).
- Bobs en PF1 solo en el caso raro de `d8demote` (1,8 % de los frames).
- Medir con O1 desde el primer día. Objetivo ≤ 8 %.

### 9.6 Organización del frame y DMA

- Hay **88 líneas sin DMA de planos** (el 28 % del frame). Ahí la CPU va a
  velocidad completa: el trabajo de bus puro (copiar segmentos del copper,
  `mspr_draw`) rinde más ahí. Medir cada trabajo en las dos franjas (método
  de `bench2.s`) y ordenar el frame según eso.
- El blitter trabaja en paralelo: columna nueva y bobs en una cola servida
  por la interrupción del blitter. Nunca esperar a que termine un blit si
  la CPU tiene otra cosa que hacer (P31). `BLTPRI` solo mientras la CPU
  espera (P2).
- Mover código a `$C00000` libera chip pero **no acelera** (P29).
- Si D1 termina en "dibujar a 25 Hz": la lógica sigue a 50 y el scroll se
  calcula cada 2 frames, pero con el doble de desplazamiento por paso. El
  pico de `build_mid` no se divide por 2 automáticamente: medirlo con O1.

### 9.7 Técnicas del 68000 y de vbcc (lo que ya sirvió)

1. **Estado nativo, no `ram[]` byte a byte:** `R16()` son 2 lecturas + `lsl`
   + `or` (~50 ciclos) contra 12 de un `move.w d16(a4),Dn`.
2. **`int` es de 32 bits en vbcc:** los `u8` se promocionan con
   `ext`/`and.l #$FF`. Intermedios en `u16`/`s16`; revisar
   `work/cc/<f>.code.s` buscando `ext.l`, `and.l`, `mulu` y llamadas al
   runtime.
3. **Nada de `mulu`/`divu` en caliente** (38-140 ciclos): tablas o
   desplazamientos.
4. **Punteros que avanzan** (`(An)+`, 8 ciclos) en vez de `d8(An,Dn)` (14),
   con P38 y P62 en mente.
5. Lo caliente en variables locales (registros); las tablas de la ROM
   pasadas a palabras nativas una vez; desenrollar los bucles de vueltas
   fijas; `movem.l` para copiar bloques (la lista del copper: 38 % con un
   bucle, 15 % con `movem`).
6. **Asm a mano solo en lo que el perfil pone arriba**, con la misma
   interfaz que el C, que queda de referencia y para los casos raros.
7. Una palabra en dirección impar cuelga el 68000 (`even`, `cnop 0,2`).
   Los desplazamientos de más de 32 KB van con `(An,Dn.l)` (P40). `tst` y
   `eor` no aceptan `(pc)` ni memoria de origen (P73).

### 9.8 Qué NO hacer

- Cambiar la semántica para ganar ciclos: saltarse sprites, simplificar la
  física o la cámara. Rompe el 1:1, y está bien que el verificador lo marque.
- Tomar Musashi como coste real, o medir con la config rápida (P30).
- Optimizar sin perfil, o por la media en vez de por el peor frame.
- Dar por buena una optimización del scroll probada en un solo sentido
  (P72) o solo en `oracle_yi1` (P69).
