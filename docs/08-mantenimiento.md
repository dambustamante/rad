# 8. Mantenimiento y uso habitual

## `/estado`

Es el punto de entrada. Solo lee archivos locales: no usa la red ni IA.

```sh
make estado
```

Muestra un resumen y la lista "Qué sigue", en orden de prioridad:

- fuentes de arquitectura sin registrar, sin descargar o con más de 7 días;
- coherencia con pares sin evaluar;
- Sonar sin configurar;
- por producto: repositorios por revisar, consolidación pendiente, hallazgos sin triar, excepciones
  vencidas o inactivas, borradores sin crear en Jira, fichas de terceros incompletas, ADR con
  historias de origen modificadas, historias candidatas por analizar, documentos sin indexar,
  reporte semanal pendiente (más de 7 días) y la definición de terminado que se verifica sola: Tareas
  de Jira cuyos hallazgos de origen ya están corregidos (EQ-008.5, se pueden cerrar) y Spikes que
  superaron los 2 días sin un ADR de producto propuesto (EQ-008.8) y Hotfix sin su Error de
  seguimiento (EQ-008.9).

## Reporte semanal (`/estado semanal`)

```sh
make semanal
```

Primero actualiza las copias de los repositorios. Después escribe, por producto,
`productos/<p>/semanal/<AAAA-Wnn>.md` con lo que cambió desde el reporte anterior (la primera vez, los
últimos 7 días):

| Sección | Contenido |
|---|---|
| Repositorios | commits en la rama principal, ramas activas y cuántas de ellas están revisadas |
| Ramas activas | cada rama con commits en el período: último commit, commits adelante, su MR (si se revisó) y el veredicto de su revisión (o "sin revisar", o "hay commits nuevos") |
| Hallazgos | nuevos, corregidos, reaparecidos y deuda vencida, con los bloqueantes y altos que requieren atención |

- Mide repositorios y ramas, no personas.
- Usa solo git y el registro de radiografia: no consulta la API de la plataforma ni necesita token.
- No publica nada ni crea incidencias: lo que surja se hace con `/revisar mr`, `/triar` y `/crear`.
- Nada se ejecuta solo: el reporte se pide. `/estado` recuerda pedirlo cuando pasan más de 7 días.

## Ciclo semanal sugerido

1. `/estado semanal` para ver qué cambió.
2. `/actualizar` para trabajar con la última versión de arquitectura y de los repositorios.
3. `/revisar mr` para los MR abiertos (una o dos veces al día), y
   `/revisar <producto>` (un chat por repositorio) para la rama principal de los que cambiaron.
4. `/triar <producto>` con los hallazgos nuevos.
5. `/crear <producto> tarea --desde …` para la deuda que se lleva a Jira.

## Objetivos de `make`

`make help` los lista en dos grupos.

| Uso habitual | Qué hace |
|---|---|
| `make venv` | crea o actualiza el entorno de Python |
| `make estado` | estado general y qué sigue |
| `make actualizar` | parte automática de `/actualizar` |
| `make revisar P=<producto> [R=<repo>] [SIN_SONAR=1] [COMPLETA=1]` | parte automática de `/revisar` y, con `R`, el paquete de revisión |
| `make semanal` | reporte semanal de cada producto |
| `make test` | pruebas de las herramientas |

| Paso interno | Qué hace |
|---|---|
| `make doctor` | verifica herramientas, configuración y variables |
| `make sync-arquitectura` | descarga arquitectura y genera `arquitectura/INDICE.md` |
| `make coherencia` | regenera los `COHERENCIA.md` y lista los pares por evaluar |
| `make repos` | actualiza los repositorios activos de todos los productos |
| `make terceros` | indexa la documentación de terceros |
| `make historias` | sincroniza las historias de usuario configuradas |
| `make harness-traer` | trae la última versión de cada harness de producto |
| `make harness-generar` | regenera lo generado en cada harness y hace commit local si cambió |
| `make indices` | regenera los `INDICE.md` |

## Configuración (`harness.yaml`)

| Sección | Contenido |
|---|---|
| `arquitectura.fuentes` | repositorios de arquitectura; se administran con `/actualizar fuentes` |
| `arquitectura.estados` | cómo se interpreta la sección Estado de los documentos |
| `calibracion` | `minimo_triados` y `maximo_falsos_positivos` |
| `jira` | valores para crear Tareas, Spikes, Errores y Hotfix (Equipos, nombres de campos y tipos de incidencia), y el campo Medición HU con los valores con los que el harness toma una historia |

`harness.yaml` se modifica solo mediante los scripts, que validan los datos y conservan los
comentarios.

## Reglas que siempre se cumplen

- Los repositorios de los productos (`productos/*/repos/`) y `arquitectura/` son de solo lectura.
  Nunca commit, push, merge, MR ni PR en ellos.
- Nada se escribe en Jira, Sonar o la plataforma git sin vista previa y confirmación explícita. En la
  plataforma git solo se escribe el comentario de la revisión de una rama.
- Nada se ejecuta solo: sin tareas programadas ni procesos en segundo plano.
- Los tokens viven solo en `.env`; ningún archivo, reporte ni mensaje muestra su valor.

Las dos primeras reglas también las aplica Cursor antes de ejecutar cada comando de terminal, con el
hook de `.cursor/hooks.json` (`herramientas/guardia.py`):

| Comando | Qué pasa |
|---|---|
| commit, push, merge, rebase, reset, tag o cambio de rama en `productos/*/repos/` o `.cache/ramas/` | se bloquea |
| acciones sobre MR o PR con `glab` o `gh` (merge, approve, comment…) | se bloquea |
| escrituras HTTP directas (`curl` o `wget` con `POST`, `PUT`, `PATCH`, `DELETE` o datos) | se bloquea |
| cualquier comando con `--confirmar` (publicar en un MR o crear en Jira) | Cursor pide la aprobación del usuario |

Los comandos de lectura (`git log`, `git diff`, consultas a Sonar) y los de `make` funcionan normalmente.

El contrato completo está en [AGENTS.md](../AGENTS.md).

## Pruebas

```sh
make test
```

Ejecuta las pruebas de `herramientas/pruebas/`. Usan repositorios git temporales y respuestas
simuladas de Sonar, Jira y la plataforma git: no necesitan red ni tokens.
