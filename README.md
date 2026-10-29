# radiografia

Revisa el estado real (AS IS) de los repositorios de cada producto y lo compara con lo que se
decidió, en este orden:

1. ADR de arquitectura
2. Estándares de arquitectura
3. Decisiones del equipo (ADR-EQ) y del producto
4. Sonar

Cada hallazgo lleva su evidencia (`ruta:línea` y la cita del documento). `radiografia` no modifica
los repositorios que revisa. Lo único que escribe fuera son el comentario de la revisión de una rama
en su MR o PR, y Tareas, Spikes y Bugs en Jira; siempre con vista previa y confirmación.

## Empezar

```sh
cp .env.example .env      # completar Sonar y, si se usan, Jira y la plataforma git
make venv
make doctor
```

Después, abrir la carpeta en Cursor y escribir `/estado`: indica qué hacer a continuación.

Detalle en [Instalación](docs/01-instalacion.md).

## Comandos

| Comando | Para qué |
|---|---|
| `/estado [semanal]` | ver qué hay pendiente y qué sigue; con `semanal`, qué cambió desde el reporte anterior |
| `/actualizar [fuentes]` | registrar y descargar arquitectura, y verificar la coherencia de las decisiones |
| `/producto <nombre>` | registrar un producto, sus repositorios y sus terceros |
| `/revisar <producto> [repo] [--rama <rama>]` | revisar un repositorio (un chat por repositorio), o solo lo que cambia una rama y publicarlo en su MR |
| `/triar <producto>` | decidir qué hacer con cada hallazgo |
| `/crear <producto>` | crear un ADR, una excepción, o una Tarea, un Spike o un Bug para Jira |

Orden habitual: `/actualizar fuentes` → `/actualizar` → `/producto` → `/revisar` → `/triar` →
`/crear`.

## Documentación

La guía paso a paso está en [docs/](docs/README.md):

1. [Instalación](docs/01-instalacion.md)
2. [Conceptos](docs/02-conceptos.md): orden de autoridad, evidencia, hallazgos y veredicto
3. [Arquitectura y coherencia](docs/03-arquitectura.md)
4. [Productos y terceros](docs/04-productos.md)
5. [Revisión de repositorios y ramas](docs/05-revisar.md)
6. [Triaje](docs/06-triar.md)
7. [Crear ADR, Tareas, Spikes y Bugs](docs/07-crear.md)
8. [Mantenimiento](docs/08-mantenimiento.md)

El contrato de trabajo para Cursor está en [AGENTS.md](AGENTS.md), y las decisiones del equipo en
[equipo/](equipo/README.md).

## Estado

- **Disponible:** los seis comandos, incluidas la revisión de ramas con comentario en el MR o PR y
  el reporte semanal.
- **Próximo:** pruebas de integración y de carga.
