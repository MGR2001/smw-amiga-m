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
   (§5) → `AGENTS.md` §2 (reglas), §7 (convenciones), §8 (pitfalls P1-P40) y
   §11 (definición de "hecho").
2. Trabajar **un paso por vez**. Cada paso dice dónde corre, qué hacer y
   cuándo está hecho. No se empieza el siguiente con el anterior en rojo.
3. Al cerrar un paso: commit `Etapa N.x: <qué>` y actualizar §1.2. Si aparece
   una trampa nueva, se agrega como `Pnn` en `AGENTS.md` §8 (la próxima es
   **P41**).
4. Al cerrar la sesión: handoff con la plantilla de §7, que reemplaza a §1.

**Reglas del proceso (no negociables, vienen de lo que ya costó caro):**

| # | Regla | Por qué |
|---|---|---|
| V1 | Todo cambio en `player/*.c` se verifica con `marioverify` (C del PC) **y** con `m68kverify` (binario 68000 de vbcc). Los números de §1.3 no pueden empeorar | P38: vbcc compiló mal código que gcc compilaba bien |
| V2 | Los tiempos solo valen en cycle-exact: `tools/fsuae_shot.sh` en cloud, `tools/shot.ps1 -Exact` en la PC. Musashi (`m68kverify --engine musashi`) es una **cota inferior** porque no tiene esperas de DMA | P30; Musashi daba 24 % y la Amiga 34 % |
| V3 | Toda imagen se compara contra el esperado del PC (`scroll_check.py`) y, en la PC, contra `SuperMarioWorldMap02.png`. **Primero lo que se nota a simple vista**, criterio del usuario | la captura de FS-UAE está reescalada ×2,125 y ensucia los bordes |
| V4 | Nada derivado de la ROM entra en git (R9). Las grabaciones del oráculo sí (`work/oracle_*.txt`, `work/oam_*.txt`) | `.gitignore` |
| V5 | Las decisiones marcadas **[usuario]** no las toma el agente: prepara los datos, recomienda y pregunta | D8 y D1 se cerraron así |
| V6 | Antes de pedirle al usuario que juegue para grabar, **probar el grabador** (`oamrec.py --test 10`) | límites del puerto Lua: 1024 caracteres por valor, 16 valores por respuesta, una sola conexión TCP |

---

## 1. Handoff (estado al 2026-09-26)

### 1.1 Ramas

| rama | commit | contenido |
|---|---|---|
| `master` | `f24ee9a` | **atrasada**: termina en el handoff del 24/09 temprano (solo la 8a) |
| `claude/agents-md-x4v1di` | `e66cfc0` | todo el trabajo de la sesión cloud del 24/09: etapas 5, 6, 8 y parte de la 9 |
| `claude/agents-future-plan-hsy1gm` | esta | `claude/agents-md-x4v1di` (avance rápido, sin cambios) + este plan |

- **Base de trabajo:** esta rama. Pendiente **[usuario]**: mergearla a
  `master` con un PR, para que las sesiones nuevas arranquen de ahí.
- Los dos últimos commits de código (`45e3857`, `e66cfc0`) son **WIP sin
  revisar** (optimizaciones de dos subagentes + cambios en `scroll.s`). Lo
  primero que hay que hacer es la **Etapa 0**.

### 1.2 Estado por etapa

| Etapa | Qué | Estado | Dónde está |
|---|---|---|---|
| 1-2b | Assets, paletas, nivel, capa 1 1:1 | **hecho** (6111/6111 bloques) | `tools/smw2amiga.py`, `palette.py`, `mklvl.py`, `m16diff.py` |
| 3-4 | Esqueleto Amiga y viabilidad | **hecho**; D1, D8 y D9 cerrados | `player/boot.s`, `bench*.s`, `copbench.s` |
| 5 | Conversor del nivel al formato (d) | **hecho en cloud**; falta compararlo contra la referencia en la PC (→ 7) | `tools/mkbg.py`, `mkd8in.py`, `mkleveld.py` → `work/yi1_d.dat`, `render_d.py` |
| 6 | Scroll del nivel real | **prototipo funcionando**: solo hacia la derecha, a velocidad fija, a 320 px. Cuesta 33 % del frame sin columna y 43 % con columna | `tools/mkscroll.py` → `work/yi1_s.dat`, `player/scroll.s` |
| 7 | Capa 2 contra la referencia | pendiente (solo PC) | — |
| 8a/8b | Física y colisión de Mario | **hecho**: `full` 6510/6547; los 37 que fallan son contactos con sprites | `player/mario.c`, `mcoll.c`, `manim.c` |
| 8 (gfx, cámara) | Gráficos (OAM) y cámara | **hecho**: `gfx` 6869/6869; lazo cerrado solo con el joypad | `player/mgfx.c`, `mcam.c` |
| 8c | Pendientes | las de la partida salen exactas; **falta la grabación de las colinas** | — |
| 8d | Coste en la Amiga | **medido**: 31,6 % corriendo y 32,9 % saltando (FS-UAE, DPF encendido, sin sprites) | `player/logicbench.s` |
| 9 | Sprites: lógica | cargador (20/20), motor mínimo, **Rex**, bloque `?` volador (`$83`) y caja de mensaje (`$B9`). Falta el resto de D3 | `player/msprite.c` |
| 9 | Sprites: dibujo en la Amiga | no empezado | — |
| 10-12 | HUD, audio, pulido | no empezados | — |
| — | **Integración** (un binario que junte scroll + lógica + Mario + joystick) | **no empezada**: hoy el scroll (`scroll.s`) y la lógica (`logicbench.s`) son programas separados | — |

### 1.3 Números de regresión (la red de seguridad)

Se regeneran en cloud después de `sh tools/setup_cloud.sh`. Base = el código
**antes** del WIP (`bb66d2c`). El WIP no puede cambiar ninguno salvo los
ciclos, que tienen que bajar.

| comando | esperado |
|---|---|
| `work/marioverify work/oracle_yi1.bin` (8a sola) | TODOS los campos: 2989/3497 en el aire, 2962/3050 en el suelo |
| `work/marioverify work/oracle_yi1.bin full` | 3557/3573 en el aire, 2953/2974 en el suelo (6510/6547) |
| `work/marioverify work/oracle_yi1.bin gfx` | 6869/6869 |
| `work/marioverify work/oracle_yi1.bin loop` | 37 resincronizaciones (todas por contacto con sprites) |
| `work/marioverify work/oracle_yi1.bin sprload` | 20/20 nacimientos |
| `work/marioverify work/oracle_yi1.bin sprloop` | 2593/2594 Rex-frames |
| `work/marioverify work/oracle_yi1.bin game` | 1 resincronización de Mario (frame 5322, Koopa `$02` sin portar); Rex 3192/3194 |
| `python3 tools/m68kverify.py --engine musashi --mode loop` | 37 resincronizaciones; ~31 100 ciclos por frame de media |
| `python3 tools/m68kverify.py --engine musashi --mode loop --sprites` | 4 resincronizaciones; ~44 400 ciclos de media |
| `logicbench` en FS-UAE (§5, Etapa 0.2) | 31,6 % corriendo, 32,9 % saltando |
| `scroll_check.py --mid` en `f21a2e3` (fallos que no explica un vecino) | x=1000: 31, x=1700: 91, x=2500: 46, x=4500: 127 |
| `scroll.s -DBENCH -DSPEED=4` + `scroll_read.py --auto` | 33,9 % sin columna, 42,5 % con columna |
| `render_d.py` | 0 px distintos contra la imagen ideal; 0,018 % moviendo la cámara |

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

### 1.5 Arranque rápido en cloud

```bash
sh tools/setup_cloud.sh               # ~15 s con caché: vasm, vbcc, ROM, gen/, oráculo, marioverify
for m in "" full gfx loop sprload sprloop game; do work/marioverify work/oracle_yi1.bin $m | tail -4; done
sh tools/logicbench_build.sh          # (VBCC=~/vbcc) binario 68000 + ADF
python3 tools/m68kverify.py --engine musashi --mode loop
python3 tools/mkbg.py && python3 tools/mkd8in.py && python3 tools/mkleveld.py && python3 tools/mkscroll.py
```

Si `apt-get` no puede instalar FS-UAE, todo lo demás sigue sirviendo; solo
se pierde la medida cycle-exact.

### 1.6 Pendiente del usuario o de la PC (juntarlo en una sola sesión)

1. **[usuario]** Mergear esta rama a `master` (PR).
2. **PC:** confirmar la 8d en WinUAE con KS 1.2 (esperado ~31,6 % / ~32,9 %).
   También prueba que el ADF de 58 KB arranca en KS 1.2. Comandos en
   `AGENTS.md`, "Qué hay que hacer en la PC", punto 1.
3. **PC:** Etapa 7 (`cmp_ref.py` del blob de la etapa 5 contra la referencia).
4. **PC + usuario, una única sesión de grabación** (Etapa 8.1). Se agrupa
   todo lo que hace falta grabar para no pedirle al usuario que juegue varias
   veces: colinas (8c), cobertura de sprites (9), contadores del HUD (10) y
   audio de referencia (11).
5. **[usuario]** Las decisiones abiertas de §3 (D10-D14).

---

## 2. El presupuesto del frame (lo que manda)

Un frame PAL son 20 ms, ~141 800 ciclos de CPU. Hoy, medido en cycle-exact
salvo donde se indica:

| componente | medido | objetivo propuesto (peor frame) | fuente |
|---|---|---|---|
| scroll: `build_mid` + columna nueva + lista del copper | 33,9 % sin columna / **42,5 %** con columna (320 px, 4 px/frame) | **≤ 25 %** | `scroll.s -DBENCH` |
| lógica `level_frame` sin sprites | 31,6 % / 32,9 % | — | `logicbench` |
| lógica de sprites | +13 300 ciclos de media ≈ +9 % **en Musashi, sin DMA**; peor frame 45,6 % en total | lógica total **≤ 40 %** | `m68kverify --sprites` |
| dibujo de sprites (sprites de hardware + copper) | sin medir | ≤ 10 % | — |
| bobs en PF1 (solo si un objeto pasa a bob) | 22,7-33,8 % (Banzai + 4 Rex, `bench2.s` W3) | caso raro, ver 9.2 | `bench2.s` |
| HUD | sin medir | ≤ 2 % | — |
| audio | sin medir | ≤ 5 % | — |
| **margen** | — | **≥ 10 %** | — |

**Hoy no entra a 50 Hz:** scroll (43 %) + lógica (33 % + sprites) ya pasan
del 85 % sin dibujar los sprites, sin HUD y sin audio. Por eso la
optimización (Etapas 6.4 y 8.2) va **antes** que las etapas que suman coste
(9.2, 10 y 11).

**Compuerta D1 [usuario]:** después de las Etapas 6.4, 8.2 y la 6b se mide el
**peor frame del juego integrado**. Si pasa del 100 %, se le presentan al
usuario estas opciones con números: (1) otra ronda de optimización, con
ensamblador a mano en las sondas de colisión y en `build_mid`; (2) dibujo a
25 Hz con la lógica a 50 Hz, que ahorra scroll y copper pero no lógica; (3)
recortar el alcance, por ejemplo menos sprites a la vez. Mover el código a
slow RAM **no** acelera (P29).

---

## 3. Decisiones abiertas

| ID | Decisión | Opciones | Recomendación | Hace falta en |
|---|---|---|---|---|
| D1 | 50 Hz o no | ver la compuerta de §2 | seguir con 50 Hz y medir | después de la 6b |
| D5 | Música | (a) convertir a MOD + replayer estándar; (b) secuenciador propio que lea las secuencias N-SPC convertidas offline | **(b)**: conserva los glissandos, el vibrato y el tempo por timer; un MOD obliga a cuantizar a filas | Etapa 11 |
| **D10** | Ancho de la pantalla | 320 px (lo que hace `scroll.s` hoy) o **256 px, como la SNES** | **256 px**, por cuatro motivos: (1) encuadre 1:1: la cámara (`mcam.c`) y el cargador de sprites trabajan con una pantalla de 256, y a 320 los enemigos **aparecen de golpe** dentro de la zona visible; (2) con `DDFSTRT $30` se pierde el sprite 7 (R5) y quedan 3 columnas adosadas en vez de las 4 que suponen `oamstudy`/`d8demote`/`copsim`; a 256 px el fetch empieza más tarde y vuelven las 8; (3) un 20 % menos de DMA de planos, que queda para la CPU y el copper; (4) las simulaciones de la etapa 5 ya usan 256 | Etapa 6.1 |
| **D11** | Dónde va el HUD | (a) superpuesto como en la SNES: en las líneas del HUD el copper apunta PF1 a un bitmap fijo y PF2 sigue con su paralaje; (b) en las 32 líneas PAL que sobran, fuera de la zona de juego | **(a)** si en Yoshi's Island 1 la capa 1 nunca aparece en esas líneas (medirlo, 10.1); si aparece, elegir con el usuario | Etapa 10 |
| **D12** | Alcance de power-ups | lo que da el nivel (seta, flor y sus bolas de fuego, estrella, 1-UP, luna) o solo la seta | **lo que da el nivel**, mismo criterio que D3. Antes, confirmar en los objetos del nivel qué da cada bloque | Etapa 9.1 |
| **D13** | Carga y mapa de memoria | (a) seguir con un binario plano relativo (`-sc -sd`: datos a menos de 32 KB de `a4`, P36); (b) al tomar la máquina, copiar el código y los datos de CPU a direcciones fijas (código y tablas en `$C00000`) y enlazar en absoluto | **(b)** cuando la integración pase de 32 KB de datos de C: `ram[]` (8 KB) + `rom00` (16 KB) + tablas ya rozan el límite. Libera chip RAM (P29: no acelera) y elimina la comprobación de referencias absolutas | Etapa 6b.1 |
| **D14** | Controles | la A500 trae joystick de 1 botón y SMW necesita salto (B), correr (Y) y giro (A) | joystick de 2 botones (el 2.º botón en `POTGO`/`POTINP`) + teclado como alternativa; arriba + botón para el giro. **Preguntar** | Etapa 6b.3 |

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

0.3 **`scroll.s` del WIP** (escaneo de `wake` por bloques de 16 líneas con
`gmin_a/b`; `blit_steps`, la columna repartida en `BLITS`=4 pasos por frame).
- Imagen: para `X` en 500, 1000, 1700, 2500, 3500 y 4500:
  ```bash
  ~/vbcc/bin/vasmm68k_mot -Fbin -m68000 -I player -DSTOPX=X -o work/scroll.bin player/scroll.s
  python3 tools/mkadf.py --boot work/boot.bin --stage2 work/scroll.bin --data work/yi1_s.dat --out work/scroll.adf
  sh tools/fsuae_shot.sh work/scroll.adf work/scroll.png 60
  python3 tools/scroll_check.py --shot work/scroll.png --s X --mid
  ```
- Coste: `-DBENCH -DSPEED=4` y `scroll_read.py --auto`. Mirar la **media y
  el máximo** con columna: el cambio tiene que bajar el pico del 42,5 %.
- Si la imagen empeora: `git checkout f21a2e3 -- player/scroll.s`.

**Hecho cuando** los fallos que no explica un vecino son iguales o menores
que en §1.3 y el coste baja, o el cambio queda revertido con el motivo
escrito.

0.4 **Los ~5 px del copper** (`WOFS`=8, un parche empírico). Leer lo que
dejó el subagente (`copcal_fine.py` y el diff de `copcal.s`/`copcal.py` en
`45e3857`). Si no hay conclusión, repetir el experimento: bandas con
`BPLCON1` a 0, 7 y 15 y un contenido de rayas de 1 px (`-DPATTERN`), y
comparar dónde cae el MOVE respecto de los píxeles del contenido y del borde
de la DIW. **Hecho cuando** hay una explicación y una fórmula en `scroll.s`
(y un **P41**), o `WOFS` queda documentado como empírico con la medida que
lo respalda.

0.5 Commit sin "WIP". Actualizar §1.

### Etapa 6 — Terminar el scroll

**Dónde:** cloud; 6.5 en la PC. **Parte de:** `player/scroll.s`,
`tools/mkscroll.py` y el formato `yi1_s.dat` (documentado en la cabecera de
`mkscroll.py`).

6.1 **Pantalla de 256 px** (si D10 = 256).
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

6.4 **Bajar el coste a ≤ 25 %** en el peor frame con columna. Ideas
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
solo la CPU y pueden ir a slow RAM. Comprobar que `$C00000` responde (P8)
antes de usarla. **Hecho cuando** hay un mapa de memoria escrito en
`AGENTS.md` §4, con cifras medidas, y el loader lo respeta.

6b.2 **Bucle del frame.** Latencia de un frame, como la SNES, que sube en el
NMI lo que calculó el frame anterior:

```
VBL: cambiar a la lista del copper preparada → lanzar el blit de la columna
     → leer la entrada → level_frame() (cámara, Mario, sprites)
     → preparar la lista siguiente (build_mid, punteros de planos y sprites) → esperar el VBL
```

Juntar `scroll.s` y el arnés del C: se construye como `logicbench_build.sh`,
o enlazado en absoluto si D13 = (b). Después de juntarlos, correr V1 sobre
el binario nuevo.

6b.3 **Entrada (D14).** Leer `JOY1DAT`, el botón de fuego (CIA-A `PRA`
bit 7) y el 2.º botón (`POTGO`/`POTINP`), más el teclado si se decide.
Convertir al formato de la SNES en `$15-$18`: `JoyPadA/B` = mantenido y
`JoyFrameA/B` = recién apretado, que es lo que espera el port.

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
  8. lo que sale de los bloques según D12, monedas y puntos.
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
   SNES y si en ellas aparece alguna vez la capa 1 → D11.
2. Si D11 = (a): en esas líneas, el copper apunta PF1 a un bitmap fijo del
   HUD (retardo de PF1 = 0, colores 1-7 del HUD) y PF2 sigue igual. Gráficos
   de la barra: tiles de capa 3 a 2 bpp (los `gb-*`; `gb-1` es el juego de
   caracteres). Números y reserva: se blitean
   solo cuando cambian.
3. Lógica: portar la actualización de la barra de `game.s` (tiempo,
   monedas, vidas, puntuación, monedas de Yoshi, estrellas, reserva).
   Verificar contra los contadores de la grabación 8.1.

**Hecho cuando** la barra coincide con la referencia y con los contadores
grabados, y el coste es ≤ 2 %.

### Etapa 11 — Audio (D5)

1. `tools/brr2pcm.py`: BRR (ADPCM) → PCM de 8 bits **con signo** (P7), sin
   sesgo DC. Verificar contra el WAV de `smwrecomp` (8.1).
2. Si D5 = (b): convertir offline las secuencias de `sound/` a un formato
   compacto de eventos, y escribir un secuenciador 68000 que maneje Paula.
   El tick sale de un timer de CIA, no del VBL: el tempo del SPC700 no
   depende de 50/60 Hz.
3. 8 voces → 3 de música + 1 de efectos. Elegir las voces por prioridad en
   cada tema. El eco no existe: se omite.
4. Efectos: el port ya escribe los disparadores (`wm_SoundCh1/2/3`, por
   ejemplo en `mario.c`): engancharlos ahí.
5. Presupuesto: ≤ 64 KB de muestras en chip RAM y ≤ 5 % de CPU (medido).

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
| Faltan columnas de sprites | con `DDFSTRT $30` solo quedan 3 adosadas | D10 = 256 px; bob en PF1 (`d8demote`) |
| vbcc compila mal | `m68kverify` llega al tope de 10 M ciclos o difiere de `marioverify` | V1 siempre (P38) |
| Datos del C > 32 KB con `-sd` | `logicbench_build.sh` falla o hay referencias absolutas | D13 = (b) |
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
