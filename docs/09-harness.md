# 9. Harness del producto (`harness-<producto>`)

Cada producto tiene, además de radiografia, su **harness**: el repositorio donde se desarrolla. Reúne los repositorios del producto en `code/`, las decisiones que el código debe
cumplir y los ADR del producto.

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
│   ├── commands/                          /hdu, /tarea, /desarrollar y /listo
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

Cómo se usa el harness, comando por comando: [guía del harness](../herramientas/plantilla_harness/docs/comandos.md).
Las diferencias con radiografia están en el [README principal](../README.md).

## Qué se ve de cada MR en radiografia

La bandeja de radiografia (`/revisar mr`) muestra si el MR tiene `/listo` al día. La revisión vuelve a
verificar todo con el código de radiografia, detecta los cambios sensibles y contrasta lo que declaró
`/listo` (ver [Revisión de MR](05-revisar.md#revisión-de-mr-revisar-mr)).
