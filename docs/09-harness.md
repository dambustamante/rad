# 9. Harness del producto (`harness-<producto>`)

Cada producto tiene, además de radiografia, su **harness**: el repositorio donde se desarrolla. Reúne los repositorios del producto en `code/`, las decisiones que el código debe
cumplir y los ADR del producto.

| | radiografia | harness-<producto> |
|---|---|---|
| Qué hace | AS IS, decisiones del equipo, coherencia, triaje, revisión de MR, reporte semanal | desarrollo del día a día |
| Repositorios del producto | solo lectura (`productos/<p>/repos/`) | se desarrollan en `code/` |
| ADR del producto | los crea y verifica su coherencia | viven aquí, en `decisiones/`; nacen en Propuesto por MR |

## Estructura

```
harness-motor-fraudes/
├── AGENTS.md · README.md · Makefile      del equipo: se crean una vez y se mantienen por MR
├── repos.json                            repositorios del producto (generado)
├── config.json                           sigla y campos de Jira: Medición HU y valores aceptados (generado)
├── contexto.json                         hallazgos, componentes y terceros de cada repositorio, para /hdu (generado)
├── arquitectura.json                     extractos de arquitectura y commits de sus fuentes, para /hdu (generado)
├── GENERADO.json                         versión de lo generado, huellas de lo generado y de la plantilla
├── .env.example                          conexión a Jira
├── .cursor/
│   ├── arquitectura/<clave>.md               texto completo de los documentos vigentes (generado; se abre solo si hace falta)
│   ├── rules/00-general.mdc              remite a AGENTS.md
│   ├── rules/generado/decisiones.mdc     lo que el código debe cumplir (generado; se aplica siempre)
│   ├── rules/generado/repo-<id>.mdc      contexto de cada repositorio (generado; se aplica al trabajar en code/<id>/)
│   ├── commands/hdu.md · listo.md        comandos /hdu y /listo
│   └── hooks.json                        guardia de comandos
├── decisiones/                           ADR del producto, plantilla, INDICE.md y COHERENCIA.md (estos dos, generados)
├── herramientas/                         harness.py (code, doctor, foco, adr), hdu.py, listo.py y guardia.py
├── code/                                 repositorios del producto (fuera de git del harness)
└── trabajo/<CLAVE>/                      contexto de cada historia tomada (local, fuera de git)
```

**Lo generado** lo escribe radiografia y no se edita a mano:

- `decisiones.mdc`: documentos de arquitectura vigentes con su regla rápida, y las decisiones del
  equipo y del producto con los criterios que se aplican al código. Las decisiones sobre la forma de
  trabajar (definición de terminado, estructura de las historias) van solo con su regla rápida. Los
  criterios suspendidos por un choque no aparecen.
- `repo-<id>.mdc`: propósito y arquitectura real (del AS IS), componentes, terceros y hasta 15
  hallazgos abiertos, ordenados por severidad, para corregirlos si se toca ese código.

## Crear el harness

Todo producto nace con su harness: `/producto motor-fraudes` crea los dos.

1. El harness lleva las reglas desde el inicio. El AS IS, los componentes y los hallazgos llegan después de
   `/revisar`, con la siguiente publicación.
2. `productos.py crear` llama a `harness.py crear`, que:
   - crea `productos/motor-fraudes/harness/` desde la plantilla (`herramientas/plantilla_harness/`);
   - genera las reglas, `repos.json` y los índices;
   - hace `git init` y el primer commit en `main`.
3. Se crea el repositorio `harness-motor-fraudes` en GitLab, se sube con los dos comandos que muestra
   el script y se configuran las aprobaciones que necesitan sus MR.

## Mantenerlo (sin pasos extra)

`/actualizar` incluye dos pasos del harness:

| Paso | Cuándo | Qué hace |
|---|---|---|
| `harness-traer` | antes de la coherencia | `git pull` de la copia local, para evaluar los ADR propuestos por MR |
| `harness-generar` | al final | regenera lo generado; si algo cambió, sube la versión y hace commit local |

**Subirlos.** `harness.py subir` trae, regenera y muestra la vista previa de todos los harness; con
`--confirmar` hace el push. `/actualizar` y `/revisar mr` lo incluyen, así que un ADR nuevo llega en la
siguiente revisión diaria, sin procesos programados. Un harness con pares de coherencia por evaluar queda
retenido: una decisión en choque no se entrega antes de suspenderse. `/estado` avisa cuando hay commits sin
subir. La rama principal del harness debe permitir este push directo a quien administra radiografia.

**Qué llega a `/hdu`.** Un ADR de arquitectura o de equipo está disponible para `/hdu` cuando se subió el
harness. `/hdu` no puede saber que un ADR-EQ se aprobó y aún no se sube. Sí detecta, con `git ls-remote`, si
una fuente de arquitectura tiene commits más nuevos, y lo avisa sin detener el trabajo.

**Archivos nuevos de la plantilla.** Cuando la plantilla de radiografia agrega un archivo (por ejemplo un
comando nuevo), `harness-generar` lo **agrega** al harness. Nunca pisa un archivo que el equipo ya tiene:
si la plantilla cambió uno de esos archivos, avisa una vez ("La plantilla cambió AGENTS.md") y el cambio se
lleva por MR. Para saberlo, `GENERADO.json` guarda la huella de cada archivo tal como lo entregó la
plantilla.

Un ADR del producto creado desde radiografia (`/crear motor-fraudes adr`) se escribe en la copia del
harness y se guarda con `harness.py guardar motor-fraudes --mensaje "…"`.

## Uso diario

```sh
git clone <url>/harness-motor-fraudes && cd harness-motor-fraudes
cp .env.example .env    # JIRA_URL, JIRA_EMAIL y JIRA_TOKEN personales, con lectura del proyecto
make doctor             # git, Python 3.11, gitleaks y que code/ quede fuera de git
make code               # clona los repositorios en code/; ENLAZAR=~/repos reutiliza clones existentes (enlaces)
```

Se abre la carpeta del harness en Cursor y se trabaja en `code/<repo>/`, en una rama propia.
`make actualizar` trae la versión nueva del harness y las novedades de los repositorios, sin cambiar
la rama de trabajo ni descartar cambios.

**Guardia** (`.cursor/hooks.json`): bloquea el push a `main` o `master`, el push con
`--force`, aprobar o mergear MR con `glab` o `gh` y las escrituras HTTP directas. El resto del flujo de
git funciona normalmente.

## Flujo de una historia

Una historia se desarrolla en una **Tarea** de Jira con el campo Tipo en `Producto`. `/tarea <HISTORIA>` la crea y la
enlaza, con vista previa y confirmación; es el único comando del harness que escribe en Jira. También se puede crear
a mano. Una historia ya no se toma directo con `/hdu`.

| Paso | Dónde | Qué pasa |
|---|---|---|
| 1. `/hdu <CLAVE>` | Harness | Crea la rama y el borrador de la spec |
| 2. MR de la spec | Harness | Se revisa y se aprueba antes de programar |
| 3. `/desarrollar <CLAVE>` | `code/<repo>/` | Se trabaja contra la spec aprobada |
| 4. `/listo <CLAVE>` | Harness | Verifica que el código cumple la spec |
| 5. MR del código | Repositorio del producto | Se revisa y se aprueba como siempre |
| 6. `/revisar mr` | radiografia | Contrasta el MR con la spec y las reglas |

**Aprobada** significa integrada en `main` del harness. Un Hotfix no espera la aprobación: su spec se completa
antes de `/listo` y se integra después. Un Spike no lleva spec: entrega un ADR.

## `/hdu <CLAVE>`: tomar una historia

```sh
python3 herramientas/hdu.py tomar FRAUD-123 [--repos fraude-core] [--sin-rama]
```

0. **Actualiza el harness** (`git pull --ff-only`). Si no puede, se detiene: no se propone código con reglas
   viejas. Sin remoto, sigue.
1. Lee la Tarea de Jira y su historia enlazada: de ahí salen la Medición HU, los criterios y la descripción. Una Tarea
   sin historia usa los suyos y queda sin medir. Lo hace en solo lectura, con el token personal: título, descripción, tipo, estado,
   **Medición HU** y criterios de aceptación (la sección "Criterios de aceptación" de la descripción).
2. Decide con la Medición HU, sin IA:

   | Medición HU | Resultado |
   |---|---|
   | Óptima, Completa o Adecuada (`jira.medicion_aceptada` en `harness.yaml` de radiografia) | se toma |
   | vacía | se toma; `/listo` va a exigir la revisión de la deuda que deja |
   | cualquier otro valor | no se toma: se indica qué falta completar en la historia |

3. Identifica los repositorios que toca por los componentes, las etiquetas o las menciones de la
   historia. Si no surgen, Cursor pregunta y repite con `--repos`.
4. Crea la rama `<tipo>/<CLAVE>-<título>` en cada repositorio (ADR-EQ-010): `fix` para un Error o un Hotfix, `chore`
   para una Tarea de deuda y `feat` para el resto; `--tipo` lo cambia. La crea desde su rama principal. No cambia de
   rama un repositorio con cambios sin commit.
5. **Foco:** escribe `.cursorignore` para que Cursor vea solo esos repositorios, lo que ahorra tokens en
   búsquedas e índice. `make foco` lo restaura.
6. Escribe `trabajo/<CLAVE>/contexto.md`: criterios numerados, descripción y, por repositorio, la rama,
   los terceros, los componentes y los hallazgos abiertos relacionados (siempre los bloqueantes y altos;
   del resto, los que comparten palabras con la historia).
7. **Arquitectura:** agrega al contexto hasta 3 extractos (máximo 1.500 caracteres cada uno) de los documentos
   que comparten más palabras con la historia. Se elige sin IA y se lee una sola vez. La regla rápida de todos
   los documentos sigue en `decisiones.mdc`; si una toca el cambio, se abre su texto completo.
8. **Spec:** crea la rama `docs/<CLAVE>-spec` del harness y el borrador `specs/<CLAVE>/spec.md`, de una página como
   máximo. Cursor lo completa, con **una prueba por criterio de aceptación**, y pide confirmación.
   `hdu.py spec <CLAVE>` la valida antes de abrir su MR.

## `/desarrollar <CLAVE>`: programar contra la spec

`hdu.py desarrollar <CLAVE>` vuelve a `main`, actualiza el harness y se detiene si la spec no está aprobada. Cursor
propone los pasos por criterio, pide confirmación en el plan y en los cambios delicados, implementa en
`code/<repo>/` y ejecuta las pruebas. Un cambio menor se declara como desvío en `/listo`; un cambio de alcance o de
diseño exige corregir la spec en un MR.

**Spike:** el contexto indica que el entregable es un ADR del producto. Se crea con
`python3 herramientas/harness.py adr --titulo "<decisión>" --historia FRAUD-126`, que toma el siguiente
número libre, lo deja en Propuesto con la historia de origen, y se completa y se propone por MR al
harness.

## `/listo <CLAVE>`: antes del MR

1. **Preparar** (sin IA): `python3 herramientas/listo.py preparar FRAUD-123`. Trae la última versión de las
   reglas e indica si cambiaron desde `/hdu`; si no puede traerlas, lo deja como `NO DETERMINADO`. Exige todo en commits y, por
   cada repositorio de la historia, compara la rama con su rama principal:

   | Verificación | Qué busca |
   |---|---|
   | Secretos | gitleaks sobre los commits de la rama |
   | Consola | `System.out`, `console.log`, `print(` fuera de las pruebas |
   | Pendientes | `TODO`, `FIXME` o `XXX` agregados |
   | Contrato | la API cambió y `docs/contratos/` no (EQ-004) |
   | Integraciones | clientes HTTP nuevos: revisar timeout, ficha del tercero y C4 |
   | Pruebas debilitadas | `@Disabled`, `skip`, `assert true` o pruebas borradas |

   Escribe `trabajo/FRAUD-123/listo-paquete.md` con el diff y los resultados.
2. **Revisar:** Cursor contrasta el diff con las decisiones de `.cursor/rules/generado/`; lo que no
   cumple se corrige antes del MR (y se vuelve al paso 1).
3. **Registrar** `trabajo/FRAUD-123/listo.json`: la prueba de cada criterio de aceptación
   (`<repo>:<archivo>:<línea>`), la **deuda que deja la historia** (técnica u operativa: la propone el
   harness y se confirma antes de cerrar), las decisiones que aplican y, si apareció, una decisión propuesta. En una HU sin medir, decidir la deuda es obligatorio (`"sin_deuda": true` si no hay).
4. **Cerrar:** `python3 herramientas/listo.py cerrar FRAUD-123`. Rechaza un criterio sin prueba, una prueba
   que no es parte del cambio o está deshabilitada, una evidencia inexistente y los avisos de lenguaje.
   Escribe `trabajo/FRAUD-123/mr-<repo>.md` con la descripción del MR y restaura el foco.

La descripción del MR trae los criterios con su prueba, la deuda que deja la historia, la definición de
terminado como lista y, al final, un **registro** (comentario HTML) para la revisión: commit, versión
del harness, resultados de las verificaciones, criterios y deuda.

**Dónde queda la deuda:** en la descripción del MR, no en un archivo del harness. Así no hace falta un MR al
harness (con su aprobación) por cada historia. radiografia la toma de ahí al revisar el MR y la lleva a Jira
con `/crear <producto> tarea --deuda <CLAVE>`.

## Qué se ve de cada MR en radiografia

La bandeja de radiografia (`/revisar mr`) muestra si el MR tiene `/listo` al día. La revisión vuelve a
verificar todo con el código de radiografia, detecta los cambios sensibles y contrasta lo que declaró
`/listo` (ver [Revisión de MR](05-revisar.md#revisión-de-mr-revisar-mr)).
