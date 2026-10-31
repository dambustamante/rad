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
├── GENERADO.json                         versión de lo generado, huellas de lo generado y de la plantilla
├── .env.example                          conexión a Jira (solo lectura)
├── .cursor/
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

```
/producto motor-fraudes harness
```

1. Conviene tener antes al menos una revisión de código del producto: lo generado lleva su AS IS,
   componentes y hallazgos.
2. `harness.py crear motor-fraudes`:
   - crea `productos/motor-fraudes/harness/` desde la plantilla (`herramientas/plantilla_harness/`);
   - **mueve** los ADR del producto de `productos/motor-fraudes/decisiones/` a `decisiones/` del
     harness: desde ahí los leen la coherencia, `/revisar` y `/crear`;
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

El push es manual. `/estado` avisa cuando el harness tiene commits sin subir.

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

## `/hdu <CLAVE>`: tomar una historia

```sh
python3 herramientas/hdu.py tomar FRAUD-123 [--repos fraude-core] [--sin-rama]
```

1. Lee la historia de Jira en solo lectura, con el token personal: título, descripción, tipo, estado,
   **Medición HU** y criterios de aceptación (la sección "Criterios de aceptación" de la descripción).
2. Decide con la Medición HU, sin IA:

   | Medición HU | Resultado |
   |---|---|
   | Óptima, Completa o Adecuada (`jira.medicion_aceptada` en `harness.yaml` de radiografia) | se toma |
   | vacía | se toma; `/listo` va a exigir la revisión de la deuda que deja |
   | cualquier otro valor | no se toma: se indica qué falta completar en la historia |

3. Identifica los repositorios que toca por los componentes, las etiquetas o las menciones de la
   historia. Si no surgen, Cursor pregunta y repite con `--repos`.
4. Crea la rama `feature/<CLAVE>-<título>` en cada repositorio, desde su rama principal. No cambia de
   rama un repositorio con cambios sin commit.
5. **Foco:** escribe `.cursorignore` para que Cursor vea solo esos repositorios, lo que ahorra tokens en
   búsquedas e índice. `make foco` lo restaura.
6. Escribe `trabajo/<CLAVE>/contexto.md`: criterios numerados, descripción y, por repositorio, la rama,
   los terceros, los componentes y los hallazgos abiertos relacionados (siempre los bloqueantes y altos;
   del resto, los que comparten palabras con la historia).
7. Cursor propone el plan, con **una prueba por criterio de aceptación**, y pide confirmación antes de implementar.

**Spike:** el contexto indica que el entregable es un ADR del producto. Se crea con
`python3 herramientas/harness.py adr --titulo "<decisión>" --historia FRAUD-126`, que toma el siguiente
número libre, lo deja en Propuesto con la historia de origen, y se completa y se propone por MR al
harness.

## `/listo <CLAVE>`: antes del MR

1. **Preparar** (sin IA): `python3 herramientas/listo.py preparar FRAUD-123`. Exige todo en commits y, por
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
