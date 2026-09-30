# SUBAGENTES.md — El resto del proyecto, en tareas para subagentes

> **Qué es.** El plan de **todo lo que falta** del port (desde el 2026-09-30
> hasta el ADF final), partido en **tarjetas** que puede ejecutar un
> subagente de menor potencia sin contexto previo, más el protocolo del
> coordinador que las reparte, las revisa y las integra.
>
> Relación con los otros ficheros: `AGENTS.md` es el contrato (reglas duras,
> formatos, pitfalls); `ROADMAP.md` dice qué etapa toca, con su estado y sus
> números (§1, handoff) y cómo optimizar (§9). Este fichero dice **cómo
> repartir el trabajo**. Si algo de aquí contradice a `AGENTS.md` §2, manda
> `AGENTS.md`. Al cerrar una tarjeta, su estado va a `ROADMAP.md` §1.2.

---

## 1. Roles y niveles

**Coordinador** (nivel F, el agente más capaz de la sesión): elige la ola,
crea los worktrees, escribe o ajusta las tarjetas, lanza los subagentes,
revisa cada rama, integra, corre la regresión completa, mantiene
`tools/baseline.json`, `AGENTS.md` y `ROADMAP.md`, y lleva las decisiones
**[usuario]** al usuario. No delega la revisión ni la integración.

**Niveles de subagente:**

| nivel | para qué sirve | ejemplos |
|---|---|---|
| **F** (fuerte) | diseño, temporización del copper, memoria/enlazado, depurar un fallo que no se entiende, todo lo que no tiene un verificador que diga "bien/mal" | `build_mid` incremental, pool de segmentos, vlink, diseño de la 9.2 |
| **M** (medio) | transcribir rutinas del ROM instrucción por instrucción **contra el oráculo**, pasar C a asm **contra `--cross`**, herramientas con autoprueba, integraciones acotadas | sprites de la 9.1, `sprite_run` en asm, `brr2pcm.py`, `memmap.py` |
| **C** (chico) | tareas mecánicas con una puerta automática trivial: guiones de snesorc, medidas, recuentos, tablas | grabar el Chuck, medir las líneas del HUD, `orc_has.py` |

**Regla para elegir nivel:** una tarjeta puede bajar de nivel solo si
(1) tiene una **puerta automática** que detecta el error (el oráculo,
`--cross`, una autoprueba, `imgdiff`), (2) es **transcripción o mecánica**,
no diseño, y (3) toca **un área** (sin razonar sobre tiempos del copper ni
sobre el mapa de memoria). Si falla una de las tres, sube un nivel.

---

## 2. Protocolo

### 2.1 Antes de lanzar (coordinador)

```bash
sh tools/setup_cloud.sh && sh tools/snesorc_setup.sh     # una vez por contenedor
python3 tools/lint_port.py && python3 tools/regress.py   # la base tiene que dar OK
sh tools/wt_new.sh <tarjeta>                             # ../wt-<tarjeta>, rama wt/<tarjeta>
```

`wt_new.sh` copia `work/` (ROM, oráculos, `snesorc`, `yi1_*.dat`) y
`player/gen/`, e imprime las variables que el subagente tiene que exportar
(`FSUAE_BASE`/`FSUAE_DISPLAY` propios, P76). **Nunca dos subagentes en el
mismo árbol**: compilar escribe en `work/`.

### 2.2 La tarjeta (plantilla del prompt)

Cada tarjeta de §4 tiene estos campos; el prompt del subagente es la
tarjeta + el bloque fijo de §2.3:

```
Tarea <ID> — <título>
Worktree: /home/user/wt-<id> (rama wt/<id>). Exporta: <línea de wt_new.sh>
Lee (solo esto): <ficheros y secciones exactas; nada de "lee AGENTS.md entero">
Contexto: <2-5 líneas: por qué, qué hay ya hecho, números de partida>
Hace: <pasos numerados, concretos>
Puerta (hecho cuando): <comandos exactos y lo que tienen que imprimir>
No toca: <ficheros de otras tarjetas de la misma ola>
Entrega: <qué poner en el informe>
```

### 2.3 Reglas fijas (se copian en todos los prompts)

1. Trabajás **solo** en tu worktree. No hagas push. Commits locales en
   español, estilo `Etapa N.x: <qué>`, con las líneas de atribución que te
   pase el coordinador.
2. **No edites** `AGENTS.md`, `ROADMAP.md`, `SUBAGENTES.md` ni
   `tools/baseline.json`. Las trampas nuevas y los números van en el
   informe; el coordinador los integra.
3. Antes de cada commit: `python3 tools/lint_port.py && python3
   tools/regress.py`. Si algo sale PEOR y es a propósito (más sprites que
   corren de verdad, por ejemplo), explicalo en el informe; si no, arreglalo.
4. Nunca saltarse, desactivar ni aflojar una comprobación para llegar a la
   puerta. Nunca cambiar la semántica para ganar ciclos (ROADMAP §9.8).
5. Los ficheros con barras invertidas (macros `\1` de vasm, `\n` en C) se
   escriben con la herramienta de ficheros, no con heredoc de bash (P56).
6. **Parar y avisar** si: la puerta no se cumple después de 3 intentos
   distintos; hace falta tocar un fichero de "No toca"; aparece algo que
   contradice la tarjeta o `AGENTS.md`. Informe con la evidencia (salida
   de las herramientas), no con suposiciones.
7. Al terminar: nada sin commitear. Lo que quede a medias, en un commit
   `WIP: <qué falta verificar>`.
8. Informe final: qué hiciste, commits (hash + título), la salida de la
   puerta, números antes → después con su herramienta y emulador, qué no
   pudiste probar, trampas nuevas redactadas como `Pnn`.

### 2.4 Revisión e integración (coordinador)

Por cada rama:
1. `git log` + `git diff master...wt/<id>` (o la rama base de la sesión):
   ¿toca solo lo que decía la tarjeta? ¿el C sigue las convenciones
   (`AGENTS.md` §7)? ¿hay algo derivado de la ROM (R9)?
2. **Volver a correr la puerta** en el worktree; no fiarse del informe.
3. Integrar (`git merge --no-edit wt/<id>`), `python3 tools/smwtabx.py` si
   cambió, y la regresión completa en el árbol integrado. Al cerrar una ola:
   `regress.py --level --emu logic,scrollbench,scrollimg`,
   `game_build.sh` + `gamecheck.py --spr` y capturas del replay
   (`-DSTOPF=F-5145`, P75).
4. `regress.py --update` (o `--accept-last --force` con la explicación en
   el commit) si las métricas cambiaron a propósito.
5. Trampas nuevas a `AGENTS.md` §8 (renumeradas), estado a `ROADMAP.md`
   §1.2, `sh tools/wt_new.sh --rm <id>`.

### 2.5 Mapa de conflictos

Dos tarjetas de la misma ola no pueden tocar el mismo fichero. Las zonas:

| zona | ficheros | tarjetas |
|---|---|---|
| juego | `player/game.s`, `tools/game_build.sh` | O1, MA1, H3, Z1-Z6, C4 |
| modelo del copper | `tools/scrollsim.py`, `copcal.s`/`copcal.py` | E1, E2, S3 |
| scroll | `player/scroll.s`, `tools/mkscroll.py`, `mkleveld.py` | S*, G5, H3 |
| lógica de Mario | `player/mario.c`, `mcoll.c`, `manim.c`, `mgfx.c`, `mcam.c` | L1a, L1c, L3, P8, Z1-Z4 |
| sprites | `player/msprite.c` (o `player/spr_*.c`, I1) | P*, L1b, L1d, L2 |
| asm de la lógica | `player/logic68k.s` | L1*, L2, G4 |
| Mario en sprites | `player/mspr.c`, `mspr68k.s`, `tools/mkmario.py` | MA*, G4 |
| verificadores | `tools/marioverify.c`, `m68kverify.py`, `regress.py` | O3, P* (contadores), H4 |
| grabaciones | `tools/snesorc/*.orc`, `work/oracle_*.txt` | R* (cada una su fichero: se pueden paralelizar) |
| audio | `tools/brr2pcm.py`, `player/audio*.s` (nuevos) | A* |

`regress.py` y `marioverify.c` los tocan muchas tarjetas: que cada una
**solo agregue** una función o un modo nuevo, sin reordenar lo existente,
y el coordinador resuelve los conflictos al integrar.

---

## 3. Olas (orden y dependencias)

```
Ola 1 (ya)   I1 · O1 · R0 → R1…R6 · S1a+S2 · L1a
Ola 2        O3 · O4 [usuario: D1, D15, D16] · P1+P2 · P3 · MA1 · S4 (F) · L1c
Ola 3        S5 (F) · L1b+L1d+L2 · G1 · G2 (F) · C1 · H1 · A1 · A2 (F) · R7
Ola 4        S3 → S8 → S6 (F) · G3 · G4 · G6 · C2 (F) · C3 · H2 · A3 · R8 · P4…P10
Ola 5        G5 (F) · C4 · H4 · A4 · MA2 · E1 · E2 · E3
Ola 6        G7 · H3 · H5 · A5 · A6 · A7 · C5 · Z1…Z6 → Z8
Final        U1…U4 · Z7 (usuario / PC)
```

`a → b`: el mismo agente, en serie (comparten ficheros o una depende de la
otra). `a+b`: una sola tarjeta. R0 es corta: primero ella y después R1-R6
en paralelo (cada guion es su fichero). P4…P10 van en paralelo gracias a
I1 (cada sprite en su `player/spr_*.c`), salvo P8, que toca la lógica de
Mario y va sola. Z1…Z6 tocan todos `game.s`: un agente, en serie.

- La **compuerta D1** (O4) puede cambiar el alcance de las olas 3-6 (por
  ejemplo, si se dibuja a 25 Hz): no lanzar la ola 3 antes de la
  respuesta del usuario.
- Después de cada ola: integración completa (§2.4) y handoff en
  `ROADMAP.md` §1.
- Tamaño de ola razonable: **3-5 subagentes a la vez**. Más, y la revisión
  del coordinador se vuelve el cuello de botella.

---

## 4. Tarjetas

Formato corto: **Nivel · Depende de · Toca**, y después Lee / Hace /
Puerta / No toca. "Regresión OK" = `lint_port.py` + `regress.py` sin PEOR
que no esté explicado.

### I — Infraestructura

#### I1 — Sprites nuevos en ficheros propios
**M · — · `tools/logicbench_build.sh`, `tools/regress.py`, `tools/setup_cloud.sh`, `tools/game_build.sh`**
- Lee: `logicbench_build.sh` (cómo parte cada `.s` de vbcc en datos y
  código, P36, P47), la lista `CSRC`/`LIBSRC` de `regress.py`, la línea
  `SRCS` de `setup_cloud.sh`.
- Hace: que cualquier `player/spr_*.c` entre solo en los tres builds (gcc
  del PC, biblioteca de `--cross`, vbcc del 68000) sin tocar las listas a
  mano; mover el Rex a `player/spr_rex.c` como prueba.
- Puerta: regresión OK **idéntica** (ninguna métrica cambia, ni los
  ciclos: `abcheck.py HEAD~1 --sprites` IGUAL).
- Por qué: con un fichero por sprite, las tarjetas P* se paralelizan.

### O — Medir el frame entero (ROADMAP §9.1; es la 6b.6)

#### O1 — `game.s -DBENCH`
**M · — · `player/game.s`, `tools/game_read.py` (nuevo)**
- Lee: ROADMAP §9.1; `player/bench.s` + `tools/bench_read.py` (cómo se
  mide con el timer A de CIA-B y se escribe en pantalla como bits);
  `player/game.s` (el bucle del frame: `game_step`, `scroll_frame`,
  `mspr_draw`); AGENTS P52, P75.
- Hace: con `-DBENCH`, medir por frame entrada, `level_frame`,
  `mspr_draw`, columna, `build_mid`, resto de `scroll_frame` y el total;
  guardar el peor de cada uno con su frame y su s; al terminar el replay
  (o con `-DSTOPF`), pintarlo como bits con palabras de sincronía;
  `game_read.py --shot X --auto` lo decodifica.
- Puerta: el replay con `-DBENCH` da una tabla con 7 filas y los máximos
  en frames plausibles; sin `-DBENCH`, `game.bin` **idéntico byte a byte**
  al de antes; `gamecheck.py` 0 diferencias.
- No toca: `scroll.s`, `msprite.c`.

#### O2 — Escenarios de estrés (= R6)
Ver R6.

#### O3 — El peor frame por parte en `regress.py`
**M · O1 · `tools/gamecheck.py`, `tools/regress.py`, `tools/scrollprof.py`**
- Hace: `gamecheck.py --engine musashi` corre también `scroll_frame` y da
  ciclos por parte (peor y media); `regress.py` los guarda (`game.*`) y
  agrega el scroll a la vuelta (`scrollprof.py -D RETURN=4864 --stopx 0`),
  y `--emu game` corre O1 en FS-UAE.
- Puerta: métricas nuevas presentes y estables en dos corridas seguidas.

#### O4 — Informe de la compuerta D1 **[usuario]**
**F (coordinador) · O1, O3, R6**
- Hace: tabla del peor frame del juego integrado (replay + escenarios de
  estrés) por parte, contra ROADMAP §2; las tres opciones de §2 con
  números (otra ronda de optimización con las ideas de §9, dibujo a 25 Hz,
  recortar alcance) y una recomendación. Preguntar al usuario.

### R — Grabaciones con snesorc (nivel C; cada una en su fichero)

Todas: el guion en `tools/snesorc/<nombre>.orc` (empieza con `include
boot_yi1.orc`), `sh tools/snesorc_make.sh <nombre>`, el `.txt` a git (V4),
el `.bin` no. Sintaxis: `N RIGHT+Y`, `until w$0094>=07B0 max 600 RIGHT+Y`,
`pulse`, `rec on|off|all`, `poke`, `assert $0071==00`, `print`, `include`
(ver `tools/snesorc/orc.c` y los guiones que ya hay). Las X de los objetos
salen de `spr.lv` (`python3 tools/lvparse.py --dump`) y de `AGENTS.md` §9 D3.
Lee: ROADMAP Etapa 8.1, AGENTS P67, P68, P70; `tools/snesorc/diagpipe.orc`
como ejemplo.

#### R0 — `tools/orc_has.py`
**C · — · `tools/orc_has.py` (nuevo)**
- Hace: dado un `oracle_*.txt`, lista por número de sprite en qué frames
  está en alguna ranura y con qué estado, y un resumen de Mario por tramo
  (X, `$19` = power-up, `$71` = animación). Formato del `.txt`: el que lee
  `tools/oracle2bin.py`.
- Puerta: sobre `work/oracle_yi1.txt` da los tramos que dice ROADMAP Etapa
  9.1 (Koopa `$BD` 4437-4597 y 5145-5305, Banzai `$9F` 5799-6077...).

#### R1 — La colina grande de x = `$AE0` (cierra la 8c)
**C · R0** · `hills2.orc`. A toda carrera en los dos sentidos, parado,
deslizándose y saltando, con los 5 Rex (pisarlos o esquivarlos).
Puerta: `marioverify work/oracle_hills2.bin full` sin fallos de
pendiente (la salida los clasifica por causa); `assert` al final.

#### R2 — Clappin' Chuck `$95` (x `$12A0`)
**C · R0** · `chuck.orc`: llegar, dejar que salte y aplauda, pisarlo 3
veces; otra variante en la que daña a Mario. Puerta: `orc_has.py --sprite 95`
lo muestra vivo ≥ 200 frames y con pisotones.

#### R3 — Caparazón rojo `$DB` (x `$D10`) y caparazones del Koopa
**C · R0** · `shells.orc`: patear el caparazón, que choque con un Rex,
agarrarlo (Y) y soltarlo; pisar el Koopa `$02` con caparazón.

#### R4 — Meta `$7B` (x `$12E0`)
**C · R0** · `goal.orc`: cortar la cinta a distintas alturas; pasar sin
cortarla. Grabar hasta el fin de la secuencia (`rec all`).

#### R5 — Power-ups (D12)
**C · R0** · un guion por objeto: seta (bloque volador), flor (bloque `?`
con Mario grande) y disparar, estrella, 1-UP, luna 3-UP, champiñón
invisible `$C7`, bloques `!`, monedas de Yoshi (las 4 + la 5.ª cuenta),
morir (caer y tocar enemigo), punto medio.
Puerta: `orc_has.py` muestra cada objeto y el cambio de `$19`/`$71`.

#### R6 — Estrés (= O2)
**C · R0** · `stress_back.orc` (volver a toda velocidad sobre s ≈
2600-2900 y 4100-4800), `stress_sprites.orc` (Banzai + 4 Rex + Mario a la
vez), `stress_piranha.orc` (las 2 pirañas del frame 9714 con Mario
corriendo) y `stress_vert.orc` (subir la cámara lo más posible: saltos a
toda carrera desde las tuberías y rebotando en Rex; da el mínimo de
`Bg1VOfs` para S8). Puerta: `orc_has.py` confirma los sprites a la vista a la vez;
la cámara (`$1A`) recorre esos tramos.

#### R7 — Contadores del HUD en el volcado
**M · — · `tools/snesorc/orc.c`, `tools/oracle2bin.py`, `tools/marioverify.c` (solo lectura del formato)**
- Hace: agregar al registro las direcciones del HUD (vidas `$0DBE`,
  monedas `$0DBF`, tiempo desde `$0F31`, puntuación desde `$0F34`, monedas
  de Yoshi, reserva; exactas en `equates/memory.i`) **sin romper el
  formato viejo** (campo nuevo al final, opcional).
- Puerta: `snesorc_make.sh --replay` sigue dando 6871/6871; los `.txt`
  viejos se leen igual; `regress.py` OK.

#### R8 — Audio de referencia
**M · — · `tools/snesorc/orc.c`**
- Hace: `--wav X.wav` que vuelque la salida del SPC700 emulado por
  snesrev en la misma corrida del guion.
- Puerta: el WAV de `normal.orc` suena (tema del nivel + saltos) y dura lo
  que el guion a 60 frames por segundo (la SNES NTSC). Documentar cómo se
  alinea con los frames de la Amiga, que van a 50.

### S — Scroll ≤ 25 % (ROADMAP Etapa 6.4 y §9.2)

Todas: Lee ROADMAP Etapa 6.4 y §9.2, AGENTS P39-P46, P50, P51, P59, P71,
P72; `player/scroll.s` (`build_mid`), `tools/mkscroll.py` (formato MLD).
Puerta común: `scrollsim.py --speed 2 --ret` ≤ 9282 px e ida = vuelta;
capturas FS-UAE en x = 500, 1000, 1700, 2500, 3500, 4500 con `imgdiff.py`
IDÉNTICAS (o `scroll_check --mid` ≤ base si cambia a propósito);
`game_build.sh` + `gamecheck.py` 0; el peor frame de `scrollprof.py` a 2 y
4 px/frame **en los dos sentidos**, antes → después.

#### S1a — Cargas "tarde" con clasificación fija y celda de 8 px
**M · — · `scroll.s`, `mkscroll.py`** · P71: "tarde" (a > 0 o b ≤ 0) se
decide en `mkscroll.py` y va en MLD; la línea con una tarde viva es
canónica (s0 = s) y la h de la tarde solo cambia cada 8 px de s.
Puerta extra: en s = 4580 las 24 líneas que hoy se reescriben en cada frame
pasan a reescribirse cada 4 frames (2 px/frame).

#### S2 — LNS por grupos de 16 líneas
**M · — (se puede con S1a en la misma tarjeta)** · el mínimo de cada
grupo para saltarlo entero. Puerta extra: `scrollprof.py --zones`
muestra el recorrido de LNS por debajo de ~1 500 ciclos.

#### S4 — Editar en el sitio **(F)**
**F · S1a** · terminar `tools/wip64/build_mid_incremental.s`: rebase de la
h de cada WAIT, append y truncado por la derecha.

#### S5 — Presupuesto por frame (EDF) **(F)**
**F · S4** · cola por plazo con tope de ciclos; neutralizar en el sitio las
cargas muertas (MOVE a `$1FE`).

#### S3 — Un segmento para las dos listas **(F)**
**F · S4** · pool de 2 ranuras por línea + reenganche. El primer paso es
medir con `copcal.s` si la "columna vertebral" de saltos entra en el
borrado (P43, P46); si no entra, documentar por qué y descartar.

#### S6 — Un plan por sentido **(F)**
**F · S5** · plan ALAP para ir a la izquierda (o cargas centradas en su
ventana), elegido por la dirección de la cámara; otro MLD en slow RAM.

#### S8 — La cámara vertical de YI1 (ROADMAP §10.2b) **(F)**
**F · R6 (el mínimo de `Bg1VOfs`) · `scroll.s`, `mkscroll.py`, `game.s` (pasarle cam_y)** ·
ventana de datos extendida K líneas hacia arriba; punteros de PF1/PF2 con
(cam_y − 192) y la mitad; segmentos del copper indexados por línea del
nivel, con la v de los WAIT parcheada cuando cambia cam_y. Puerta extra:
capturas del replay de `oracle_normal` en los frames 2672-2707 (la cámara
en `$BC`) iguales al esperado; `scroll_check.py` con cam_y ≠ 192.

#### S7 — Menos cargas desde el origen
**M · — · `mkleveld.py`, `mkscroll.py`** · primero la **estadística**
(nivel C: cargas por línea visible en todo el recorrido, histograma);
después, reparto de registros que reuse el que ya tiene el color.
Puerta extra: `regress.py --level` (`render_d`: 0 px contra la imagen
ideal) y menos cargas en total.

### L — Lógica ≤ 40 % (ROADMAP §9.3)

Todas: Lee ROADMAP §9.3 y 8.2, AGENTS P36-P38, P47-P49, P62-P64;
`player/logic68k.s` (cómo se reemplaza una rutina de C por asm solo en el
build de la Amiga, y cómo el asm cae al C en los casos raros); la función
de C que se reemplaza. Puerta común: regresión OK con los **cruces de RAM
entera** en `ok`; `abcheck.py HEAD~1 --sprites` con semántica IGUAL y los
ciclos del peor frame menores (dar el número).

#### L1a — Rama hacia arriba de `f7f4` en asm
**M · — · `logic68k.s`** · hoy `_f7f4` salta a `_f7f4_c` hacia arriba
(`mcam.c`, con el arreglo de P69). −~1 000 ciclos en los frames en que
Mario sube. Probar además con `oracle_normal`/`diagpipe` (las que mueven
la cámara en vertical: `marioverify ... loop`).

#### L1b — `sprite_run` + despacho de `sprite_main` en asm
**M · I1 · `logic68k.s`, `msprite.c` (solo quitar/poner `#ifdef`)**
Ojo: en la 8.2 partir `sprite_run` salió peor (vbcc deja de incorporar el
despacho): hacerlo entero.

#### L1c — `mario_E2BD` en asm
**M (grande; F si se traba) · — · `logic68k.s`** · ~4 000 ciclos por frame
hoy. Verificar también `marioverify gfx` en los 5 oráculos (lo corre
`regress.py`).

#### L1d — `spr_obj_interact`, `spr_obj_vert`, `spr_spr_interact`, `jumping_piranha` en asm
**M · I1 · `logic68k.s`** · una rutina por commit.

#### L2 — Descartes rápidos
**M · — · `msprite.c`** · `spr_spr_interact` y el contacto con Mario:
descartar por |dx| (y |dy|) antes de la caja completa, con el mismo
resultado.

#### L3 — Estado nativo de Mario **(F)**
**F · L1a-L1d** · ROADMAP 8.2 paso 2. Solo si después de L1-L2 el peor
frame sigue por encima del 40 %.

### MA — Mario en sprites (ROADMAP §9.4)

#### MA1 — No redibujar si la pose no cambió
**M · — · `player/mspr68k.s`, `player/game.s` (solo la llamada)** · clave
= punteros `wm_0D85` + `wm_Tile7FPtr` + OAM relativa (el recuento está en
ROADMAP §9.4: cambia en el 33,5 % de los frames). Doble buffer: redibujar
en el buffer libre solo si cambia.
Puerta: `gamecheck.py --spr` 6184/6184; la media de `mspr_draw` en Musashi
baja ~60 %; capturas del replay iguales.

#### MA2 — `mspr_draw` más barato por dentro
**M · MA1** · perfil por etiquetas y atacar lo que salga (§9.4 M4).
Objetivo ≤ 3 % en el peor frame.

### P — Sprites: lógica (ROADMAP Etapa 9.1)

Todas: Lee ROADMAP Etapa 9.1; AGENTS P27, P33-P38, P62, P65, P66;
`player/msprite.c` (cómo está hecho el Rex, el mejor ejemplo); la rutina
del ROM en `/home/user/smw-src-master/project/mw_e10/sprite_*.s` (buscar
el número en la tabla de punteros de `sprite_1-main.s`). Método:
**transcribir instrucción por instrucción** sobre `ram[]`, con el estado de
A, X, Y y `m0..` anotado en comentarios; tablas de otros bancos con
`tools/smwtabx.py`. Puerta común: `marioverify <oráculo>.bin game` con
`sprite XX: seguidos N exactos N` en la grabación que lo contiene, 0
resincronizaciones de Mario, y ninguna métrica existente peor salvo los
ciclos (anotarlos).

| tarjeta | nivel | depende de | qué | oráculo |
|---|---|---|---|---|
| **P1** | M | — | el Koopa `$BD` difiere 1 frame al empezar el nivel (frame 1455, ranura 7, `$AA`: port 0, ROM 3) en las 4 grabaciones de snesorc | `oracle_normal` |
| **P2** | M | — | `diagpipe`: `sprload` 31/33 (la ROM mete la piraña `$4F` en la ranura que un Rex deja libre en el mismo frame) | `oracle_diagpipe` |
| **P3** | M | R2, I1 | Clappin' Chuck `$95` | `oracle_chuck` |
| **P4** | M | R3, I1 | caparazones: rojo `$DB` (estado 9), Koopa `$02` con caparazón, patear, agarrar, soltar | `oracle_shells` |
| **P5** | M | R4, I1 | cinta de meta `$7B` y el disparo de la secuencia final (la secuencia en sí es Z3) | `oracle_goal` |
| **P6** | M | R5, I1 | seta (`$74`), 1-UP, champiñón invisible `$C7` dando la vida, luna 3-UP; lo que sale de los bloques | `oracle_<objeto>` |
| **P7** | M | R5, P6 | flor de fuego y **bolas de fuego** (sprites extendidos: hoy `MARIO_UNSUP_FIRE`) | `oracle_flower` |
| **P8** | M | R5 | crecer, encoger y morir de Mario (`$71`, hoy "sin física normal"); estrella (invencibilidad) | `oracle_<objeto>` |
| **P9** | M | R5 | monedas de Yoshi, monedas que salen de bloques, sprites de puntos | `oracle_yoshicoin` |
| **P10** | M | P6 | caja de reserva (lo que va y lo que cae) | `oracle_reserve` |

P6-P10 cambian cosas que hoy congelan el juego (el modo diagnóstico, P58):
comprobar con `tools/diag_read.py --sim` y con el replay que el motivo ya
no aparece.

### G — Sprites: gráficos en la Amiga (ROADMAP Etapa 9.2, §9.5)

#### G1 — Volver a correr los estudios con la configuración actual
**C · — · solo lectura + informe** · `oamstudy.py`, `d8demote.py`,
`copsim.py` con 256 px y 4 columnas adosadas **libres** (Mario usa 2: hay
que descontarlas), sobre `oam_yi1.txt` y, si se puede, sobre las
grabaciones de snesorc. Entrega: tabla de líneas que piden más columnas y
frames sin resolver.

#### G2 — Diseño **(F)**
**F · G1** · documento en `ROADMAP.md` Etapa 9.2 (lo escribe el
coordinador con el informe del F): formato de los frames precalculados
por pose en chip, reuso vertical de canales, colores por fila, cuándo pasa
algo a bob, presupuesto de chip (hoy ~117 KB libres) y de CPU (≤ 8 %).

#### G3 — Conversor `tools/mksprgfx.py`
**M · G2** · GFX `20` (Rex, Banzai) y los demás → frames de sprites
adosados + máscara de bob, con `--selftest` de ida y vuelta (como
`mkmario.py`). Puerta: autoprueba OK en todas las poses que aparecen en los
oráculos.

#### G4 — Asignador de columnas (C de referencia + asm)
**M (F si se traba) · G2 · `player/msprasg.c` (nuevo), `logic68k.s`** ·
objetos → columnas por franja de líneas; la referencia de verdad es
`copsim.py`.

#### G5 — El copper: `SPRxPOS`/`SPRxPT` y colores por línea en `scroll.s` **(F)**
**F · G4 · `scroll.s`** · encaja con `build_mid` (misma lista); P39, P42,
P46.

#### G6 — `tools/sprcop_verify.py`
**M · G4** · ROADMAP §8.2 fila 9.2: el asignador del 68000 en Musashi sobre
los frames de `oam_yi1.txt` contra `copsim.py`. Puerta: 0 objetos sin
mostrar.

#### G7 — Bobs en PF1
**M · G5** · restaurar desde `BLK`; las dos copias del buffer circular;
cola de blits por interrupción (P31). Puerta: capturas del replay con el
Banzai como bob.

### C — Carga y memoria (ROADMAP Etapa 6b.1, D13)

#### C1 — `tools/memmap.py`
**M · — · nuevo** · ROADMAP §8.2 fila 6b.1: desde el listado de vasm y la
tabla del loader, todo lo que lee el chipset < `$80000`, alineaciones (8,
4, 2) y total de chip ≤ 512 KB. Puerta: sobre el `game.lst` de hoy da el
mapa de `AGENTS.md` §4.

#### C2 — Enlazado absoluto con vlink **(F)**
**F · C1** · direcciones fijas en chip y en `$C00000`; desaparecen P36 y
P52. `m68kverify`/`abcheck`/`gamecheck` aprenden a cargar en la dirección
fija (E3).

#### C3 — Compresor y descompresor
**M · — · `tools/lzpack.py`, `player/unlz.s` (nuevos)** · LZ simple y
rápido de descomprimir en 68000. Puerta: ida y vuelta en Unicorn sobre
`yi1_s.dat` y el binario; ciclos por KB medidos en Musashi.

#### C4 — Loader nuevo
**M (F revisa) · C2, C3 · `player/loader.s`, `tools/mkadf.py`** · recorre
la tabla de carga, comprueba `$C00000` (P8), descomprime y salta.
Puerta: el ADF arranca en FS-UAE y el replay coincide (capturas).

#### C5 — Tiempo de carga
**C · C4** · con y sin compresión, en FS-UAE; se queda la más rápida.

### H — HUD (ROADMAP Etapa 10, D11)

#### H1 — Medir el HUD
**C · — · informe** · con la cámara Y de la partida (192), cuántas líneas
ocupa la barra de la SNES y si la capa 1 aparece en ellas (desde
`yi1_d.dat` y la referencia de la capa 3).

#### H2 — Gráficos de la barra
**M · H1 · `tools/mkhud.py` (nuevo)** · tiles de capa 3 a 2 bpp (`gb-*`,
`gb-1` = caracteres) → bitmap de PF1 y la paleta de 7 colores. Puerta:
PNG comparado a simple vista con la referencia + autoprueba.

#### H3 — Overlay por copper
**M (F si la capa 1 aparece en esas líneas) · H2 · `game.s`, `scroll.s` (solo las líneas del HUD)** ·
PF1 apunta al bitmap fijo en esas líneas (retardo 0), PF2 sigue con su
paralaje. Puerta: captura con la barra.

#### H4 — Lógica de la barra + `marioverify hud`
**M · R7, H2 · `player/mhud.c` (nuevo), `marioverify.c`** · portar la
actualización de la barra de `game.s` del ROM; comparar los contadores
contra los grabados. Puerta: todos los frames.

#### H5 — Blitear solo lo que cambia
**M · H3, H4** · ≤ 2 % medido con O1.

### A — Audio (ROADMAP Etapa 11, D5)

#### A1 — `tools/brr2pcm.py`
**M · — · nuevo** · BRR → PCM de 8 bits **con signo** (P7), sin sesgo DC,
`--selftest`. Puerta: correlación ≥ 0,99 contra las muestras del WAV de R8.

#### A2 — Estudio del formato N-SPC **(F)**
**F · — · informe** · qué hay en `sound/` del fuente, cómo se leen las
secuencias, qué efectos usa el tema de YI1, qué 3 voces quedan (D5).

#### A3 — Conversor de secuencias
**M · A2 · `tools/nspc2ev.py` (nuevo)** · eventos con el periodo de Paula
precalculado, glissando/vibrato y ADSR como tablas por tick. Puerta: un
render offline (Python) contra el WAV de R8: notas a ±1 tick y ±5 cents.

#### A4 — Secuenciador del 68000
**M · A3 · `player/audio.s` (nuevo)** · tick por timer de CIA, escribe
`AUDxPER/VOL/LC/LEN`, sin mezcla. Puerta: en FS-UAE suena; el estado por
tick en Musashi = el render offline.

#### A5 — Efectos
**C · A4** · engancharlos a `wm_SoundCh1/2/3` (ya los escribe el port) con
prioridad sobre la voz de música que comparte canal.

#### A6 — Comparación
**M · A4, R8** · captura de audio de FS-UAE contra el WAV de referencia.

#### A7 — Coste
**C · A4** · ≤ 3 % medido con el método de `bench2.s` / O1.

### Z — Pulido y entrega (ROADMAP Etapa 12)

| tarjeta | nivel | depende de | qué | puerta |
|---|---|---|---|---|
| **Z1** | M | P8 | muerte y reinicio del nivel con la animación del ROM (hoy el diagnóstico) | `oracle_death` (R5) exacto |
| **Z2** | M | R5 | punto medio: el poste, el estado guardado, reaparecer ahí | grabación de R5 |
| **Z3** | M (F revisa) | P5, R4 | secuencia de la meta hasta el final | `oracle_goal` |
| **Z4** | C | — | tiempo agotado | guion que espera |
| **Z5** | M | — | fundidos por copper al entrar y salir | captura |
| **Z6** | M | G5 | Mario detrás del poste de la meta (prioridad sprite/capa 1) | captura en la meta |
| **Z7** | usuario/PC | todo | ADF final probado en WinUAE KS 1.2 y 1.3 (y A500 real, opcional) | — |
| **Z8** | M | Z3 | el replay completo hasta la meta como prueba de `regress.py` (ROADMAP §8.2 fila 12) | llega a la meta en el mismo frame que el oráculo |

### E — Deuda técnica

| tarjeta | nivel | qué |
|---|---|---|
| **E1** | M | P51: medir con `copcal.s` el copper después de `DDFSTOP` a 256 px y meterlo en el modelo (`scrollsim.py`, `mkscroll.py`) |
| **E2** | M | `scrollsim.py` supone que corren todos los segmentos: agregar una comprobación de que la lista termina donde tiene que terminar (P59) |
| **E3** | M | después de C2: `m68kverify`, `abcheck`, `gamecheck`, `gamesim` con la carga en la dirección fija |

### U — Usuario / PC (no se delegan)

| | qué |
|---|---|
| **U1** | jugar `work/live/game.adf` en WinUAE con teclado; si se congela, captura de la página 2 del diagnóstico → `diag_read.py --repro` |
| **U2** | Etapa 7: `cmp_ref.py` contra `SuperMarioWorldMap02.png` |
| **U3** | probar en una A500 real (opcional) |
| **U4** | arranque en KS 1.2 después de cada cambio del loader (C4) |
| **D1** | la compuerta de §2 de `ROADMAP.md` (O4) |

---

## 5. Lo que aprendió el coordinador (2026-09-30, 4 subagentes a la vez)

- **Worktrees siempre**; el script (`wt_new.sh`) evita repetir a mano la
  copia de `work/` y `player/gen/`.
- Pedirles que **no toquen** `AGENTS.md`/`ROADMAP.md`/la base: tres de
  cuatro propusieron trampas con el mismo número (P59-P65).
- Los informes de los subagentes son buenos pero **no son verificación**:
  al integrar aparecieron un fallo que el subagente vio y dejó de lado
  (`gamecheck --spr` se colgaba: era P62, un fallo real en la Amiga) y un
  arreglo de otro (`scroll_check` a 256 px) que cambió los números de un
  tercero. Siempre volver a correr las puertas en el árbol integrado.
- Un aviso de tiempo ("quedan 15 minutos: redondeá") funciona: todos
  dejaron el árbol limpio y un informe completo.
- Las tarjetas con una **puerta automática exacta** salieron bien a la
  primera (9.1 contra el oráculo, snesorc contra `oracle_yi1`). La que era
  diseño con temporización (6.4) no cerró: esas van a nivel F y con un
  primer paso de medida.
