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
  historias de origen modificadas, historias candidatas por analizar, documentos sin indexar y
  reporte semanal pendiente (más de 7 días).

## Reporte semanal (`/estado semanal`)

```sh
make semanal
```

Primero actualiza las copias de los repositorios. Después escribe, por producto,
`productos/<p>/semanal/<AAAA-Wnn>.md` con lo que cambió desde el reporte anterior (la primera vez, los
últimos 7 días):

| Sección | Contenido |
|---|---|
| Repositorios | commits en la rama principal, ramas activas, MR o PR abiertos y mergeados |
| Ramas activas | cada rama con commits en el período: último commit, commits adelante, su MR y el veredicto de su revisión (o "sin revisar", o "hay commits nuevos") |
| Hallazgos | nuevos, corregidos, reaparecidos y deuda vencida, con los bloqueantes y altos que requieren atención |

- Mide repositorios, ramas y MR, no personas.
- Los MR solo aparecen si la plataforma git está configurada; si no, quedan `NO DETERMINADO`.
- No publica nada ni crea incidencias: lo que surja se hace con `/revisar --rama`, `/triar` y `/crear`.
- Nada se ejecuta solo: el reporte se pide. `/estado` recuerda pedirlo cuando pasan más de 7 días.

## Ciclo semanal sugerido

1. `/estado semanal` para ver qué cambió.
2. `/actualizar` para trabajar con la última versión de arquitectura y de los repositorios.
3. `/revisar <producto> <repo> --rama <rama>` para las ramas activas sin revisar, y
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
| `make revisar P=<producto> [R=<repo>] [SIN_SONAR=1]` | parte automática de `/revisar` |
| `make revisar P=<producto> R=<repo> RAMA=<rama>` | preparar la revisión de una rama |
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
| `make indices` | regenera los `INDICE.md` |

## Configuración (`harness.yaml`)

| Sección | Contenido |
|---|---|
| `arquitectura.fuentes` | repositorios de arquitectura; se administran con `/actualizar fuentes` |
| `arquitectura.estados` | cómo se interpreta la sección Estado de los documentos |
| `calibracion` | `minimo_triados` y `maximo_falsos_positivos` |
| `publicacion.publicables` | fuentes cuyos hallazgos se publican en el MR sin triarlos |
| `jira` | valores para crear Tareas, Spikes y Bugs: Equipos, nombres de campos y tipos de incidencia |

`harness.yaml` se modifica solo mediante los scripts, que validan los datos y conservan los
comentarios.

## Reglas que siempre se cumplen

- Los repositorios de los productos (`productos/*/repos/`) y `arquitectura/` son de solo lectura.
  Nunca commit, push, merge, MR ni PR en ellos.
- Nada se escribe en Jira, Sonar o la plataforma git sin vista previa y confirmación explícita. En la
  plataforma git solo se escribe el comentario de la revisión de una rama.
- Nada se ejecuta solo: sin tareas programadas ni procesos en segundo plano.
- Los tokens viven solo en `.env`; ningún archivo, reporte ni mensaje muestra su valor.

El contrato completo está en [AGENTS.md](../AGENTS.md).

## Pruebas

```sh
make test
```

Ejecuta las pruebas de `herramientas/pruebas/`. Usan repositorios git temporales y respuestas
simuladas de Sonar, Jira y la plataforma git: no necesitan red ni tokens.
