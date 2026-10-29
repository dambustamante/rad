# 9. Harness del producto (`harness-<producto>`)

radiografia es la herramienta del TL. Cada producto tiene además su **harness**, el repositorio de
trabajo de los devs: reúne los repositorios del producto en `code/`, las decisiones que el código debe
cumplir y los ADR del producto.

| | radiografia | harness-<producto> |
|---|---|---|
| Quién lo usa | el TL | los devs del producto |
| Qué hace | AS IS, decisiones del equipo, coherencia, triaje, revisión de MR, reporte semanal | desarrollo del día a día |
| Repositorios del producto | solo lectura (`productos/<p>/repos/`) | se desarrollan en `code/` |
| ADR del producto | los crea, verifica su coherencia y los aprueba junto con un par dev | viven aquí, en `decisiones/`; nacen en Propuesto por MR |

## Estructura

```
harness-motor-fraudes/
├── AGENTS.md · README.md · Makefile      del equipo: se crean una vez y se mantienen por MR
├── repos.json                            repositorios del producto (generado)
├── GENERADO.json                         versión de lo generado y huella de cada archivo
├── .cursor/
│   ├── rules/00-general.mdc              remite a AGENTS.md
│   ├── rules/generado/decisiones.mdc     lo que el código debe cumplir (generado; se aplica siempre)
│   ├── rules/generado/repo-<id>.mdc      contexto de cada repositorio (generado; se aplica al trabajar en code/<id>/)
│   └── hooks.json                        guardia de comandos del dev
├── decisiones/                           ADR del producto, plantilla, INDICE.md y COHERENCIA.md (estos dos, generados)
├── herramientas/                         harness.py (make code, make doctor) y guardia.py
└── code/                                 repositorios del producto (fuera de git del harness)
```

**Lo generado** lo escribe radiografia y no se edita a mano:

- `decisiones.mdc`: documentos de arquitectura vigentes con su regla rápida, y las decisiones del
  equipo y del producto con los criterios que se aplican al código. Las decisiones sobre la forma de
  trabajar (definición de terminado, estructura de las historias) van solo con su regla rápida. Los
  criterios suspendidos por un choque no aparecen.
- `repo-<id>.mdc`: propósito y arquitectura real (del AS IS), componentes, terceros y hasta 15
  hallazgos abiertos, ordenados por severidad, para corregirlos si se toca ese código.

## Crear el harness (TL)

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
3. El TL crea el repositorio `harness-motor-fraudes` en GitLab, lo sube con los dos comandos que
   muestra el script y configura que sus MR necesiten la aprobación de un par dev y del TL.

## Mantenerlo (TL, sin pasos extra)

`/actualizar` incluye dos pasos del harness:

| Paso | Cuándo | Qué hace |
|---|---|---|
| `harness-traer` | antes de la coherencia | `git pull` de la copia local, para evaluar los ADR que propusieron los devs |
| `harness-generar` | al final | regenera lo generado; si algo cambió, sube la versión y hace commit local |

El push lo hace el TL. `/estado` avisa cuando el harness tiene commits sin subir.

Un ADR del producto creado desde radiografia (`/crear motor-fraudes adr`) se escribe en la copia del
harness y se guarda con `harness.py guardar motor-fraudes --mensaje "…"`.

## Uso del dev

```sh
git clone <url>/harness-motor-fraudes && cd harness-motor-fraudes
make doctor     # git, Python 3.11, gitleaks
make code       # clona los repositorios del producto en code/
```

Se abre la carpeta del harness en Cursor y se trabaja en `code/<repo>/`, en una rama propia.
`make actualizar` trae la versión nueva del harness y las novedades de los repositorios, sin cambiar
la rama de trabajo ni descartar cambios.

**Guardia del dev** (`.cursor/hooks.json`): bloquea el push a `main` o `master`, el push con
`--force`, aprobar o mergear MR con `glab` o `gh` y las escrituras HTTP directas. El resto del flujo de
git funciona normalmente.

## Próximas fases

- `/hdu <clave>`: tomar una historia de Jira (solo si su Medición HU es Óptima, Completa o Adecuada)
  con su contexto y un plan con una prueba por criterio.
- `/listo`: verificar el cambio, proponer la deuda que deja y armar la descripción del MR.
- Bandeja de MR en radiografia, con la coherencia de los ADR que se proponen en el harness.
