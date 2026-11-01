# radiografia

Muestra el estado real de cada producto y de sus repositorios: qué hacen, cómo están construidos, qué
componentes e integraciones tienen y qué reglas cumplen o no, con evidencia. También entrega esas reglas
al repositorio donde se desarrolla cada producto. Nunca modifica el código que revisa.

```text
Entra
  ADR de arquitectura
  Estándares de arquitectura
  ADR de equipo
  ADR de producto
  Código, documentación y MR de los productos
  Sonar
  Historias de Jira
  Documentos del producto: Confluence, PDF, conversaciones y dibujos
  Documentos de terceros
        │
        ▼
 ┌─────────────┐
 │ radiografia │
 └─────────────┘
        │
        ▼
Sale
  Estado de cada producto y repositorio
  Reglas para cada harness
  Comentario en el MR
  Tareas, Spikes, Errores y Hotfix en Jira
```

El estado queda en radiografia. Lo que se publica fuera (reglas, comentarios y Jira) necesita
confirmación. Los documentos de terceros se copian a mano en
`productos/<producto>/terceros/<id>/docs/`.

## Empezar

Se necesita Python 3.11, `git`, `make`, Cursor, `gitleaks`, acceso de lectura a los repositorios y un
token de Sonar.

```sh
cp .env.example .env      # completar Sonar y, si se usan, Jira y la plataforma git
make venv
make doctor
```

Abrir la carpeta en Cursor y escribir `/estado`: indica qué hacer a continuación. Los términos ADR, hallazgo, MR y
harness se explican en [Términos](#términos).

## Comandos

Detalle y todas las opciones: [docs/10-comandos.md](docs/10-comandos.md).

| Comando | Para qué sirve |
|---|---|
| `/estado` | Ver qué está pendiente y qué sigue |
| `/estado semanal` | Ver qué cambió en la semana |
| `/actualizar` | Traer las reglas nuevas de arquitectura y publicarlas en los harness. La primera vez, pide los repositorios de arquitectura |
| `/producto <nombre>` | Registrar un producto con sus repositorios, sus páginas de Confluence y su documentación, y crear su harness |
| `/revisar <producto>` | Revisar un repositorio del producto y dejar su estado y sus hallazgos |
| `/revisar mr` | Revisar los MR abiertos |
| `/triar <producto>` | Decidir qué hacer con cada hallazgo |
| `/crear <producto> <tipo>` | Crear un ADR, una excepción, o una Tarea de deuda, un Spike, un Error o un Hotfix en Jira |

## Una semana de ejemplo

Esta semana se recibe el producto `motor-fraudes`.

| Cuándo | Qué se necesita | Comando |
|---|---|---|
| **Todos los días** | Saber qué sigue | `/estado` |
| | Revisar los MR abiertos | `/revisar mr` |
| **Lunes** | Ver qué cambió | `/estado semanal` |
| | Traer las reglas nuevas | `/actualizar` |
| **Martes** | Registrar el producto y crear su harness | `/producto motor-fraudes` |
| | Revisar sus repositorios, un chat por cada uno | `/revisar motor-fraudes` |
| **Miércoles** | Decidir qué hacer con los hallazgos | `/triar motor-fraudes` |
| | Llevar a Jira los hallazgos que se van a corregir | `/crear motor-fraudes tarea --desde <hallazgos>` |

## Dónde ver los resultados

| Qué | Dónde |
|---|---|
| Todos los productos | `productos/INDICE.md` |
| Un producto y sus repositorios | `productos/<producto>/INDICE.md` y `as-is/` |
| Decisiones del equipo y su coherencia | `equipo/INDICE.md` y `equipo/COHERENCIA.md` |
| Decisiones de un producto | `decisiones/` de su harness |

## Dos repositorios distintos

| | radiografia | harness-\<producto\> |
|---|---|---|
| **Para qué sirve** | Mostrar el estado real, publicar las reglas y revisar MR | Desarrollar las historias de Jira |
| **Cuántos hay** | Uno | Uno por producto |
| **Código de los productos** | Copias de solo lectura | Se modifica en `code/` |
| **Comandos** | `/estado` `/actualizar` `/producto` `/revisar` `/triar` `/crear` | `/hdu` `/tarea` `/desarrollar` `/listo` |

Este documento explica radiografia. El harness tiene [su propio README](herramientas/plantilla_harness/README.md).

## Qué regla manda

Si dos reglas tratan lo mismo, se aplica la de número menor:

1. ADR de arquitectura
2. Estándares de arquitectura
3. Decisiones del equipo (`ADR-EQ`): aplican a todos los productos
4. Decisiones del producto (`ADR-<SIGLA>`): aplican a un producto
5. Sonar

## Términos

| Término | Qué es |
|---|---|
| **ADR** | Documento corto que registra una decisión técnica y la regla que deja |
| **Hallazgo** | Incumplimiento concreto de una regla, con archivo y línea |
| **MR** | Merge Request: propuesta de cambio que se revisa antes de integrarla |
| **Harness** | Repositorio donde se desarrolla un producto. Hay uno por producto |
| **Spec** | Página que dice qué construirá una Tarea, cómo se probará y qué reglas aplican. Se aprueba por MR antes de programar |

Más términos en [Conceptos](docs/02-conceptos.md).

## Garantías

- No modifica el código de los productos.
- Toda afirmación lleva evidencia. Lo que no se pudo verificar queda como `NO DETERMINADO`.
- Nada sale hacia GitLab, Jira o Sonar sin vista previa y confirmación.

## Más información

- [Guía paso a paso](docs/README.md)
- [Cómo se gobierna cada harness](docs/09-harness.md)
- [Decisiones del equipo](equipo/README.md)
- [Contrato de trabajo para Cursor](AGENTS.md)
