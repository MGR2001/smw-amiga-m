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
   (convenciones), §8 (pitfalls P1-P41) y §11 (definición de "hecho"). Si
   la etapa es de optimización, también §9.
2. Trabajar **un paso por vez**. Cada paso dice dónde corre, qué hacer y
   cuándo está hecho. No se empieza el siguiente con el anterior en rojo.
3. Al cerrar un paso: commit `Etapa N.x: <qué>` y actualizar §1.2. Si aparece
   una trampa nueva, se agrega como `Pnn` en `AGENTS.md` §8 (la próxima es
   **P46**).
4. Al cerrar la sesión: handoff con la plantilla de §7, que reemplaza a §1.

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

## 1. Handoff (estado al 2026-09-27)

### 1.1 Ramas

| rama | commit | contenido |
|---|---|---|
| `master` | la cabeza | **base de trabajo**. Desde el 2026-09-26 contiene todo: la sesión cloud del 24/09, el plan, los scripts de §8 y las decisiones de §3 |
| `claude/agents-md-x4v1di` | `e66cfc0` | la sesión cloud del 24/09 (etapas 5, 6, 8 y parte de la 9); ya incluida en `master` |
| `claude/agents-future-plan-hsy1gm` | = `master` | donde se escribió este plan; mergeada a `master` por avance rápido |

- **Base de trabajo: `master`.** Cada sesión nueva trabaja en su propia rama
  a partir de `master`.
- Los dos últimos commits de código de la otra sesión (`45e3857`,
  `e66cfc0`) eran **WIP sin revisar**: optimizaciones de dos subagentes y
  cambios en `scroll.s`. El 2026-09-26 se verificó en cloud casi toda la
  **Etapa 0** con los scripts nuevos de §8: la optimización del C es
  correcta y más rápida, y la imagen del scroll no cambió. Lo que falta
  está en la Etapa 0.

### 1.2 Estado por etapa

| Etapa | Qué | Estado | Dónde está |
|---|---|---|---|
| 1-2b | Assets, paletas, nivel, capa 1 1:1 | **hecho** (6111/6111 bloques) | `tools/smw2amiga.py`, `palette.py`, `mklvl.py`, `m16diff.py` |
| 3-4 | Esqueleto Amiga y viabilidad | **hecho**; D1, D8 y D9 cerrados | `player/boot.s`, `bench*.s`, `copbench.s` |
| 5 | Conversor del nivel al formato (d) | **hecho en cloud**; falta compararlo contra la referencia en la PC (→ 7) | `tools/mkbg.py`, `mkd8in.py`, `mkleveld.py` → `work/yi1_d.dat`, `render_d.py` |
| 0 | Consolidar el WIP | **hecha** (2026-09-27, en la PC): 0.3 pico explicado (estructural, se arregla en 6.4); 0.4 explicado y arreglado (P42-P45) | §5, Etapa 0 |
| 6 | Scroll del nivel real | **prototipo funcionando**: solo hacia la derecha, a velocidad fija, a 320 px. Media **27,3 %** de un frame (WinUAE KS 1.2, 4 px/frame); **403 frames (a 2 px/frame) pasan del frame**, en s ≈ 1590-1970, 2630-2700 y 4230-4680, con el peor en s = 4504 (**320 %**) | `tools/mkscroll.py` → `work/yi1_s.dat`, `player/scroll.s`; `tools/scrollprof.py`, `tools/scrollsim.py` |
| 7 | Capa 2 contra la referencia | pendiente (solo PC) | — |
| 8a/8b | Física y colisión de Mario | **hecho**: `full` 6510/6547; los 37 que fallan son contactos con sprites | `player/mario.c`, `mcoll.c`, `manim.c` |
| 8 (gfx, cámara) | Gráficos (OAM) y cámara | **hecho**: `gfx` 6869/6869; lazo cerrado solo con el joypad | `player/mgfx.c`, `mcam.c` |
| 8c | Pendientes | las de la partida salen exactas; **falta la grabación de las colinas** | — |
| 8d | Coste en la Amiga | **medido**: 26,5 % corriendo y 26,9 % saltando (FS-UAE, DPF encendido, sin sprites), después de la optimización de los subagentes; antes, 31,6 % y 32,9 % | `player/logicbench.s` |
| 9 | Sprites: lógica | cargador (20/20), motor mínimo, **Rex**, bloque `?` volador (`$83`) y caja de mensaje (`$B9`). Falta el resto de D3 | `player/msprite.c` |
| 9 | Sprites: dibujo en la Amiga | no empezado | — |
| 10-12 | HUD, audio, pulido | no empezados | — |
| — | **Integración** (un binario que junte scroll + lógica + Mario + joystick) | **no empezada**: hoy el scroll (`scroll.s`) y la lógica (`logicbench.s`) son programas separados | — |

### 1.3 Números de regresión (la red de seguridad)

**La fuente de verdad es `tools/baseline.json`**, que genera y compara
`tools/regress.py` (§8). Resumen de la base del 2026-09-26, sobre el código
del WIP ya verificado:

| qué | valor | antes del WIP (`bb66d2c`) |
|---|---|---|
| `marioverify` 8a (TODOS los campos) | 2989/3497 aire, 2962/3050 suelo | igual |
| `marioverify full` | 3557/3573 aire, 2953/2974 suelo (6510/6547) | igual |
| `marioverify gfx` | 6869/6869 | igual |
| `marioverify loop` | 37 resincronizaciones, tramo 1240 | igual |
| `marioverify sprload` / `sprloop` | 20/20 · 2593/2594 Rex-frames | igual |
| `marioverify game` | 1 resincronización (frame 5322, Koopa `$02`), tramo 3824; Rex 3192/3194 | igual |
| 68000 (`m68kverify`, Musashi) `full` | 6510 = PC | igual |
| 68000 `loop`: resincronizaciones / ciclos media / máx. | 37 / **25 909** / 48 194 | 37 / 31 124 / 53 260 |
| 68000 `loop --sprites` | 4 / **35 779** / 53 002 | 4 / 44 364 / 64 752 |
| `logicbench`, FS-UAE | **26,5 %** corriendo, **26,9 %** saltando | 31,6 % / 32,9 % |
| `scroll.s -DBENCH -DSPEED=4`, FS-UAE | media 25,2 %; **máx. 307,5 % en s = 4504** | sin/con columna 33,9 % / 42,5 % (otra forma de contar: ver Etapa 0.3) |
| `scroll.s -DBENCH -DSPEED=4`, **WinUAE KS 1.2** (2026-09-27) | media **27,3 %**; máx. 320,6 % en s = 4504 (antes de P42-P45: 25,4 % / 309,9 %) | el +1,9 es el precio de P44-P45 (más cargas con WAIT); Musashi: código −7 %, datos +14 % |
| `scroll_check --mid --sc 2`, **WinUAE** ×2, fallos que no explica un vecino (2026-09-27) | 500: 0, 846: 0, 1000: 0, 1700: 0, 1936: 0, 2500: 0, 3500: 72, 4346: 34, 4500: 54 | antes (`WOFS` = 8): 0, manchado, 0, 9, manchado, 3, 72, —, 58 |
| `scrollsim.py --speed 2` (color de la capa 1 en cada frame, simulado) | **19 586 px** en todo el recorrido; peor frame 194 px | antes: 298 060; peor 5409 (s = 844) |
| `logicbench`, **WinUAE KS 1.2** (8d) | 28,3 % corriendo, 28,8 % saltando | FS-UAE: 26,5 / 26,9 %; binario con el vbcc de la PC (2022), ver §1.4 |
| `scroll_check --mid`, fallos que no explica un vecino | x = 500: 74, 1000: 31, 1700: 91-94, 2500: 46, 3500: 72, 4500: 125-127 (±5 px entre builds, ver 0.4) | en `f21a2e3`: 1000: 31, 1700: 91, 2500: 46, 4500: 127 (500 y 3500 no se midieron) |
| `render_d.py` | 0 px contra la imagen ideal; 3966 px (0,018 %) moviendo la cámara | igual |

### 1.4 Qué se puede hacer en cada entorno

| tarea | Claude cloud | PC local (Windows) |
|---|---|---|
| compilar (vasm, vbcc, gcc) | sí (`setup_cloud.sh`) | sí |
| ROM | ensamblada desde el fuente (`work/smw.sfc`, CRC32 `B19ED489`) | la del usuario |
| verificar contra el oráculo (`marioverify`, `m68kverify`) | sí | sí (`m68kverify` necesita `unicorn` y `machine68k`) |
| medir en cycle-exact | FS-UAE + AROS (`fsuae_shot.sh`) | WinUAE + KS 1.2 (`shot.ps1 -Exact`) |
| probar el arranque en **KS 1.2** | **no** | sí |
| comparar contra `SuperMarioWorldMap02.png` | **no** (la imagen no está en el repo) | sí (`cmp_ref.py`, `m16diff.py`) |
| grabar partidas (`smwrecomp` + `oamrec.py`) | **no** | sí, con el usuario jugando |
| numpy / scipy | sí | **no** en el Python de §6: instalarlo o correr esas herramientas en cloud |

**PC, 2026-09-27** (lo que hizo falta para correr todo en la PC):
- `regress.py` desde Python: poner `C:\msys64\ucrt64\bin` **primero** en el
  PATH (`export PATH=/c/msys64/ucrt64/bin:$PATH`); si no, `cc1` de gcc 16
  muere sin mensaje.
- ROM: `../smwre/smw.sfc` (CRC32 `B19ED489`) → `work/smw.sfc`; después
  `smwgen.py --rom work/smw.sfc`, `smwtabx.py`, `oracle2bin.py`,
  `mkmapbin.py` (como `setup_cloud.sh`).
- `machine68k` (Musashi) no compila con pip en Windows: bajar el sdist y
  cambiar en `setup.py` el `cmd = [gen_tool, ...]` por la ruta absoluta con
  `.exe`; después `pip install .`.
- El **vbcc de la PC (2022) no es el de cloud**: pliega `rom00 - $C000` en
  una referencia absoluta con un puntero leído de `ram[]` (se arregló con
  `T8V`, `smwmac.h`) y da ~+0,8 % de ciclos en Musashi. Por eso la PC usa
  su propia base: `regress.py --baseline tools/baseline_pc.json`.
- WinUAE ×2 sin reescalar: `scroll_check.py --sc 2`, `scroll_read.py` sin
  `--auto`, `tools/shots6.ps1 -Dir DIR` (espera 25 + x/100 s: KS 1.2 tarda
  más en arrancar de lo que se creía).

### 1.5 Arranque rápido en cloud

```bash
sh tools/setup_cloud.sh               # ~2 min la primera vez (compila WLA-DX y ensambla la ROM), ~15 s con caché
export VBCC=~/vbcc
python3 tools/lint_port.py            # 1 s
python3 tools/regress.py              # 4 s: compila y verifica PC + 68000 contra tools/baseline.json
python3 tools/regress.py --level      # + la cadena del nivel: deja work/yi1_d.dat y work/yi1_s.dat
```

Si `apt-get` no puede instalar FS-UAE, todo lo demás sigue sirviendo; solo
se pierde la medida cycle-exact.

### 1.6 Pendiente del usuario o de la PC (juntarlo en una sola sesión)

1. ~~**PC:** confirmar la 8d en WinUAE con KS 1.2~~ **hecho el
   2026-09-27:** 28,3 % / 28,8 % (FS-UAE daba 26,5 / 26,9 %) y el ADF
   arranca en KS 1.2. Diferencia sin explicar: puede ser el emulador o el
   vbcc de la PC (2022, distinto del de cloud; ver §1.4).
2. **PC:** Etapa 7 (`cmp_ref.py` del blob de la etapa 5 contra la referencia).
3. **PC + usuario, una única sesión de grabación** (Etapa 8.1). Se agrupa
   todo lo que hace falta grabar para no pedirle al usuario que juegue varias
   veces: colinas (8c), cobertura de sprites (9), power-ups (D12), contadores
   del HUD (10) y audio de referencia (11).

Las decisiones D5 y D10-D14 están cerradas (§3), y la rama está mergeada a
`master`. Solo queda abierta la compuerta D1.

---

## 2. El presupuesto del frame (lo que manda)

Un frame PAL son 20 ms, ~141 800 ciclos de CPU. Hoy, medido en cycle-exact
salvo donde se indica:

| componente | medido | objetivo propuesto (peor frame) | fuente |
|---|---|---|---|
| scroll: `build_mid` + columna nueva + lista del copper | media 25,2 % (320 px, 4 px/frame); **un frame de 307 % en s = 4504** | **≤ 25 %** en el peor frame | `scroll.s -DBENCH` |
| lógica `level_frame` sin sprites | 26,5 % / 26,9 % | — | `logicbench` |
| lógica de sprites | +9 900 ciclos de media ≈ +7 % **en Musashi, sin DMA**; peor frame 53 002 ciclos = 37,4 % en total | lógica total **≤ 40 %** | `m68kverify --sprites` |
| dibujo de sprites (sprites de hardware + copper) | sin medir | ≤ 10 % | — |
| bobs en PF1 (solo si un objeto pasa a bob) | 22,7-33,8 % (Banzai + 4 Rex, `bench2.s` W3) | caso raro, ver 9.2 | `bench2.s` |
| HUD | sin medir | ≤ 2 % | — |
| audio | sin medir | ≤ 3 % (D5) | — |
| **margen** | — | **≥ 10 %** | — |

**Hoy no entra a 50 Hz con margen.** De media, scroll (25 %) + lógica
(27 % + ~7-10 % de sprites) ya rondan el 60 %, sin dibujar los sprites, sin
HUD y sin audio. El pico del scroll (307 %) rompe cualquier frame en el que
caiga. Por eso la optimización (Etapas 6.4 y 8.2) va **antes** que las
etapas que suman coste (9.2, 10 y 11).

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

6.4 **Bajar el coste a ≤ 25 %** en el peor frame con columna. Primero,
el pico de s = 4504 (Etapa 0.3). Ideas
anotadas en `AGENTS.md`: `blit_steps` (0.3); en `build_mid`, tablas en vez de
`mulu` y no reescribir las h si `s` no cambió; un solo WAIT por cadena de
cargas (P39). Perfil con `m68kverify.MusashiCPU` y el listado `-L`: el
script de perfil por zonas se perdió con el contenedor y hay que rehacerlo
en `tools/`, no en `/tmp`. **Hecho cuando** `scroll_read.py` da ≤ 25 % de
máximo sin empeorar la imagen.

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

## 9. Optimización: ideas concretas

**Método (siempre):** perfil → cambiar **una** cosa → `abcheck.py` →
`regress.py --emu`. Se optimiza el **peor frame**, no la media: el frame
que no entra en 20 ms es el que se nota. `m68kverify` imprime el frame más
caro (hoy el 4438 sin sprites y el 7997 con sprites): empezar por ahí.

### 9.1 Dónde se va hoy el tiempo del C

`abcheck.py bb66d2c --prof`, ciclos propios por frame, en Musashi y sin
inline, con el WIP de los subagentes:

| función | qué es | ciclos/frame |
|---|---|---|
| `f44d` (con `f461_xy` dentro) | sondas de colisión | ~4 100 |
| `mario_E2BD` (con `e45d` dentro) | gráficos de Mario + OAM | ~4 100 |
| `camera_F6DB` | cámara | ~2 100 |
| `level_frame` | bucle de ranuras de sprites + pegamento | ~2 100 |
| `eb77`, `f7f4`, `D5F2`, `f636`, `dc4f`, `e92b` | colisión, cámara, física | ~1 000-1 300 cada una |

La media del frame bajó de 31 124 a 25 909 ciclos (−17 %) y, con sprites,
de 44 364 a 35 779 (−19 %), con la semántica intacta.

### 9.2 CPU: C con vbcc para el 68000

1. **Estado nativo, no `ram[]` byte a byte** (Etapa 8.2). Es la ganancia
   grande que queda. `R16()` son 2 lecturas de byte + `lsl` + `or`, ~50
   ciclos; un `move.w d16(a4),Dn` son 12.
2. **`int` es de 32 bits en vbcc 68000.** Un `u8` se promociona a `int`, y
   eso trae `ext.w`/`ext.l`/`and.l #$FF` de más. Intermedios y contadores en
   `u16`/`s16`, y revisar el asm de las funciones caras
   (`work/cc/<f>.code.s`): buscar `ext.l`, `and.l`, `lsl.l`, `mulu`/`muls` y
   llamadas a rutinas del runtime de vbcc. Las operaciones `.l` cuestan 8
   ciclos entre registros; las `.w`, 4.
3. **Nada de multiplicar ni dividir en caliente**: `mulu` cuesta 38-70
   ciclos y `divu` hasta 140. Tablas (ya: `L·SEG`, `L·SHSZ` en
   `build_mid`) o desplazamientos. Una multiplicación de 32 bits no existe en
   el 68000 y vbcc llama a una rutina. Quedan un `divu #SLOTS` y un
   `mulu #15` en cada llamada a `blit_steps`: se pueden cambiar por un
   contador de columna que avanza y por una tabla.
4. **Punteros que avanzan en vez de índices:** `(An)+` cuesta 8 ciclos;
   `d8(An,Dn)`, 14. En los bucles sobre ranuras de sprites, un puntero a la
   ranura y desplazamientos fijos (y con P38 en mente: el puntero apunta a
   la primera tabla y los índices son relativos).
5. **Lo caliente en variables locales**, que vbcc pone en registros; una
   global de small-data es `d16(a4)`.
6. **Tablas de la ROM pasadas a nativo una vez** (ya: `probe_dx/dy`,
   `T8X`/`T16X`): palabras big-endian alineadas, no bytes de `rom00`.
7. **Desenrollar bucles de vueltas fijas** (ya: los 7 temporizadores de
   `sprite_run`) y `dbf` en asm.
8. **Asm a mano solo en las 2-3 funciones de arriba del perfil, después del
   C nativo**, con la misma interfaz que la función en C, que queda como
   referencia. Se verifica con `m68kverify`/`abcheck` como cualquier cambio.
   Candidatas: `f44d` (sondas) y el camino común de `camera_F6DB`.
9. **No optimizar lo que se va a tirar:** `e45d` (OAM) se reemplaza en la
   6b.4 por la elección directa del frame de sprite.
10. **Una palabra en dirección impar cuelga el 68000** (Address Error; un
    020 no se queja). Al pasar tablas de bytes a palabras: `even` /
    `cnop 0,2` en asm y tipos alineados en C.

### 9.3 El DMA le roba a la CPU (lo que Musashi no ve)

- Con 6 planos en lowres, durante las 224 líneas de pantalla la CPU pierde
  ciclos: antes del WIP, la lógica costaba ~24 % de media en Musashi y
  ~34 % medida en la A500. En las ~88 líneas sin pantalla no hay fetch de
  planos. Medido en `bench2.s`, durante la pantalla contra después de la
  última línea visible:
  - la lista del copper (CPU): 38 % contra 31 %;
  - los bobs: 34-48 % contra 23-26 %;
  - la columna, al revés: 6 % contra 9 %.

  **Medir cada trabajo en las dos franjas** (el método de `bench2.s`) y
  ordenar el frame en consecuencia; lo que no depende de la posición del
  haz, en general, fuera de la pantalla.
- **Pantalla de 256 px (D10):** 20 % menos de fetch de planos en cada
  línea.
- **Slow RAM no acelera** (P29): sirve para liberar chip RAM.
- **`BLTPRI` solo mientras la CPU espera al blitter** (P2): si no, le quita
  a la CPU los ciclos que le faltan.

### 9.4 Blitter

- **Pocos blits grandes:** cada blit cuesta ~42 µs de CPU además de los
  datos (P31). Con planos entrelazados, los 3 planos de un bloque van en un
  solo blit (ya).
- **No esperar al blitter después de lanzarlo.** Una cola de blits que se
  sirve desde la interrupción del blitter (`INTENA` BLIT) deja a la CPU
  trabajando; `WaitBlit` solo antes de reprogramarlo.
- **Registros constantes una sola vez** (máscaras `BLTAFWM`/`BLTALWM`,
  módulos, `BLTCON`): en el bucle, solo punteros y `BLTSIZE`.
- **Repartir entre frames lo que no es urgente** (`blit_steps`: la columna
  en 4 pasos) para bajar el pico, que es lo que cuenta.
- **Bobs:** máscara precalculada, restaurar solo el rectángulo sucio,
  cookie-cut `A·B + ¬A·C → D` con una palabra extra para el desplazamiento.

### 9.5 Copper y sprites

- **Un WAIT gasta una ranura como un MOVE** (P39): cadenas de MOVE sin WAIT
  intermedios y, para temporizar, MOVE de relleno a un registro inocuo
  (`$1FE`).
- **Segmentos por línea encadenados** (`COP2LC` + `COPJMP2`) y dos listas.
  La CPU reescribe solo las líneas que cambian (ya: `wake`/`vu`). Si toda
  la lista está en un mismo banco de 64 KB, `COP2LCH` es fijo y cada salto
  cuesta un MOVE menos.
- **Precalcular offline todo lo que no depende de la cámara** (en
  `mkscroll.py`): palabras del copper listas para copiar y x planificada.
  Copiar bloques con `movem.l` (la lista del copper: 38 % con un bucle, 15 %
  con `movem`).
- **Reusar un canal de sprite en vertical sin copper:** en los datos del
  sprite, después de la última línea de un objeto van las palabras de
  control del siguiente, que empieza al menos una línea más abajo. No cuesta
  ninguna MOVE; el copper solo recarga los colores 17-31 entre uno y otro.
  Esto baja la carga que `copsim.py` cuenta para `SPRxPOS`.
- **Colores de sprite solo donde cambian**: las filas de color de cada
  objeto son fijas por pose, así que se precalcula qué línea recarga qué.

### 9.6 Qué NO hacer

- Cambiar la semántica para ganar ciclos: saltarse sprites, simplificar la
  física o la cámara. Rompe el 1:1 y el verificador lo marca: está bien que
  lo marque.
- Tomar Musashi como coste real, o medir con la config rápida (P30).
- Mover código a `$C00000` esperando velocidad (P29).
- Optimizar sin perfil, o por la media en vez de por el peor frame.
