# radiografia

Herramienta para gobernar productos de software. Revisa el estado real (AS IS) de los repositorios de
cada producto y lo compara con lo que se decidió, en este orden de autoridad:

1. ADR de arquitectura
2. Estándares de arquitectura
3. Decisiones del equipo (ADR-EQ): aplican a todos los productos
4. Decisiones del producto (ADR-<SIGLA>): aplican a su producto y no pueden relajar ni contradecir
   las del equipo
5. Sonar

Además crea y gobierna el **harness de cada producto** (`harness-<producto>`): el repositorio de
trabajo donde se desarrollan las historias de ese producto.

## radiografia y harness-<producto>

| | radiografia | harness-<producto> |
|---|---|---|
| Para qué | gobernar: decisiones, AS IS, coherencia, triaje, revisión de MR y deuda | desarrollar las historias de Jira |
| Repositorios del producto | solo lectura | se desarrollan en `code/` |
| Decisiones | crea las del equipo, verifica la coherencia de todas y aprueba las del producto | recibe las reglas compiladas; propone las del producto |
| Uno por | todo el portafolio | producto |

## Cómo gobierna

```mermaid
flowchart LR
    ARQ["Arquitectura<br/>ADR y estándares"]
    JIRA["Jira<br/>historias"]

    subgraph GOB["radiografia"]
        DEC["Decisiones del equipo<br/>y coherencia"]
        ASIS["AS IS de cada repositorio<br/>componentes, terceros, hallazgos"]
        REV["Revisión de MR, triaje<br/>y reporte semanal"]
    end

    subgraph HAR["harness-producto"]
        REGLAS["Reglas generadas<br/>decisiones y contexto por repositorio"]
        ADRP["ADR del producto<br/>en Propuesto"]
        HDU["/hdu: tomar una historia"]
        CODE["code/<br/>repositorios del producto"]
        LISTO["/listo: verificar el cambio<br/>y armar el MR"]
    end

    MR["MR en GitLab"]

    ARQ -->|se descarga| DEC
    DEC -->|compila| REGLAS
    ASIS -->|compila| REGLAS
    ADRP -->|coherencia y aprobación por MR| DEC
    JIRA -->|"Medición HU<br/>Óptima, Completa o Adecuada"| HDU
    REGLAS --> HDU
    HDU --> CODE
    CODE --> LISTO
    LISTO --> MR
    MR -->|"revisión, cambios sensibles<br/>y contraste con /listo"| REV
    REV -->|"Tareas de deuda<br/>con confirmación"| JIRA
    CODE -.->|solo lectura| ASIS
```

| radiografia gobierna… | Cómo |
|---|---|
| Las reglas del código | Compila en cada harness la arquitectura vigente, los ADR del equipo y del producto y las excepciones aprobadas. El harness no las edita: se regeneran en cada `/actualizar` |
| El conocimiento de cada repositorio | Lo descubre en la revisión AS IS y lo entrega compilado: propósito, componentes, terceros y hallazgos abiertos |
| Las decisiones del producto | Viven en el harness y nacen en Propuesto. radiografia verifica su coherencia antes de aprobarlas por MR. Las excepciones se crean solo desde radiografia |
| La calidad de las historias | Propone la Medición HU; el harness solo toma historias Óptimas, Completas o Adecuadas |
| El resultado | Revisa cada MR por su cuenta: detecta cambios sensibles y contrasta lo que declaró `/listo`. La deuda declarada se lleva a Jira con confirmación |
| La estructura del harness | Lo crea desde su plantilla y le agrega lo nuevo sin pisar lo que el harness ya ajustó |
| Lo que se puede hacer | Guardias en Cursor: en el harness no hay push a `main` ni `--force`; radiografia no escribe en los repositorios del producto |

Cada hallazgo lleva su evidencia (`ruta:línea` y la cita del documento). Lo único que radiografia
escribe fuera es el comentario de la revisión en un MR y las Tareas, Spikes, Errores y Hotfix en Jira,
siempre con vista previa y confirmación. El push del harness es manual.

## Empezar

```sh
cp .env.example .env      # completar Sonar y, si se usan, Jira y la plataforma git
make venv
make doctor
```

Después, abrir la carpeta en Cursor y escribir `/estado`: indica qué hacer a continuación.

## Comandos

| Comando | Para qué |
|---|---|
| `/estado [semanal]` | ver qué hay pendiente y qué sigue; con `semanal`, qué cambió desde el reporte anterior |
| `/actualizar [fuentes]` | registrar y descargar arquitectura, verificar la coherencia de las decisiones y mantener los harness |
| `/producto <nombre> [harness]` | registrar un producto, sus repositorios y sus terceros; con `harness`, crear su harness |
| `/revisar <producto> [repo]` | revisar un repositorio (un chat por repositorio) |
| `/revisar mr` | bandeja de MR abiertos; revisar uno o la coherencia de un ADR propuesto en un harness |
| `/triar <producto>` | decidir qué hacer con cada hallazgo |
| `/crear <producto>` | crear un ADR, una excepción, o una Tarea, un Spike, un Error o un Hotfix para Jira |

En cada harness: `/hdu <CLAVE>` para tomar una historia y `/listo <CLAVE>` antes de abrir el MR. Ver
el [README del harness](herramientas/plantilla_harness/README.md).

## Documentación

La guía paso a paso está en [docs/](docs/README.md):

1. [Instalación](docs/01-instalacion.md)
2. [Conceptos](docs/02-conceptos.md): orden de autoridad, evidencia, hallazgos y veredicto
3. [Arquitectura y coherencia](docs/03-arquitectura.md)
4. [Productos y terceros](docs/04-productos.md)
5. [Revisión de repositorios y MR](docs/05-revisar.md)
6. [Triaje](docs/06-triar.md)
7. [Crear ADR, Tareas, Spikes, Errores y Hotfix](docs/07-crear.md)
8. [Mantenimiento](docs/08-mantenimiento.md)
9. [Harness del producto](docs/09-harness.md): el repositorio de trabajo de cada producto

Los productos gobernados están en [productos/INDICE.md](productos/INDICE.md) (portafolio generado), el
contrato de trabajo para Cursor en [AGENTS.md](AGENTS.md) y las decisiones del equipo en
[equipo/](equipo/README.md).

## Estado

- **Disponible:** los seis comandos de radiografia, la bandeja y la revisión de MR, y el harness de
  producto con `/hdu` y `/listo`.
- **Próximo:** medición de las historias en radiografia, y pruebas de integración y de carga.
