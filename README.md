# radiografia

Muestra el estado real (AS IS) de los repositorios de cada producto y lo compara, en este orden,
contra:

1. los ADR de arquitectura,
2. los estándares de arquitectura,
3. las decisiones del equipo (ADR-EQ) y del producto (ADR-<SIGLA>),
4. Sonar (SonarQube, incluida la Community Edition, o SonarCloud).

El resultado es una ficha por repositorio y por producto, con hallazgos respaldados por evidencia
(`ruta:línea` y cita del documento incumplido). `radiografia` no modifica los repositorios que
revisa ni escribe en ningún sistema externo.

## Requisitos

- macOS con Python 3.11 o superior, `git` y `make`.
- [Cursor](https://cursor.com), para los comandos que requieren criterio.
- Acceso de lectura por git (SSH o HTTPS) a los repositorios de arquitectura y de los productos,
  en GitLab o GitHub.
- `gitleaks` (`brew install gitleaks`), para buscar secretos.
- `pdftotext` (`brew install poppler`), para leer la documentación del proveedor en PDF.
- Un token de Sonar con permiso de lectura. El token de la plataforma git se necesita recién en la
  fase 2.

## Primer uso

**1. Preparar el entorno**

```sh
cp .env.example .env      # completar SONAR_TIPO, SONAR_URL y SONAR_TOKEN
make venv                 # crea el entorno de Python
make doctor               # verifica herramientas y configuración (no muestra valores)
```

**2. En Cursor**

Ante la duda, empezar por `/estado`: muestra en qué situación está todo y qué comando sigue.
El orden habitual es:

| Paso | Comando | Qué pasa |
|---|---|---|
| 1 | `/arquitectura` | pide los repositorios de arquitectura, los inspecciona y propone las fuentes |
| 2 | `/actualizar` | descarga los documentos, genera `arquitectura/INDICE.md` y verifica que las decisiones del equipo no choquen con arquitectura (`equipo/COHERENCIA.md`) |
| 3 | `/producto <nombre>` | pide los repositorios del producto, los inspecciona y los registra |
| 3b | `/adr <producto>` | opcional: reglas propias del producto, mejoras a partir de hallazgos, excepciones con vencimiento y ADR propuestos desde las historias de Jira (`--desde-historias`) |
| 4 | `/revisar <producto>` | revisa **un repositorio por conversación**: parte automática, AS IS, comparación con lo decidido y C4 inferido. Abrir un chat nuevo para cada repositorio |
| 5 | `/triar <producto>` | genera un archivo para marcar la decisión sobre cada hallazgo y muestra la calibración |
| 6 | `/historia <producto>` | crea Tareas, Spikes y Bugs (ADR-EQ-008), por ejemplo a partir de la deuda aceptada; en Jira solo con confirmación |

Cuando todos los repositorios de un producto tienen su revisión, `/revisar` consolida el producto en
`productos/<producto>/as-is/PRODUCTO.md`.

**Recomendación para la primera línea base:** revisar primero dos o tres repositorios
representativos, triar sus hallazgos y medir el consumo de Cursor antes de revisar el resto.

## Uso habitual

- `/actualizar` antes de revisar, para trabajar con la última versión de arquitectura.
- `/producto <nombre>` para agregar o retirar repositorios de un producto.
- `/revisar <producto>` toma el siguiente repositorio pendiente; un repositorio queda pendiente
  cuando su código cambió desde la última revisión.
- `/triar <producto>` después de cada revisión.

## Dónde mirar los resultados

| Archivo | Contenido |
|---|---|
| `productos/<p>/as-is/<repo>.md` | ficha del repositorio: datos, Sonar, AS IS, comparación por nivel y veredicto |
| `productos/<p>/as-is/PRODUCTO.md` | matriz de cumplimiento repositorio × documento, brechas y visión del producto |
| `productos/<p>/INDICE.md` | punto de entrada del producto: repositorios, ADR, revisiones y triaje pendiente |
| `productos/<p>/revisiones/<revisión>/` | reporte de cada revisión, paquetes de revisión y borradores C4 |
| `productos/<p>/agendas/` | hallazgos para conversar con el equipo |
| `equipo/COHERENCIA.md` | coherencia de las decisiones del equipo con arquitectura |
| `productos/<p>/decisiones/` | ADR del producto, su índice y su coherencia con arquitectura y con el equipo |
| `productos/<p>/terceros/INDICE.md` | producto comprado e integraciones: estado de cada ficha, contratos y documentos sin indexar |
| `arquitectura/INDICE.md` | documentos de arquitectura con su estado y su regla rápida |

## Estructura

Cada nivel de autoridad tiene la misma forma: una carpeta `decisiones/`, un `INDICE.md` y, si
corresponde, un `COHERENCIA.md`. Lo que está en mayúsculas lo genera el harness y no se edita; los
datos de las herramientas están siempre en `estado/`.

```
arquitectura/                 niveles 1 y 2: copia de arquitectura, no se edita
├── INDICE.md
├── decisiones/<fuente>/      ADR de arquitectura
├── estandares/<fuente>/      estándares y arquitecturas de referencia
└── estado/
equipo/                       nivel 3: decisiones del equipo
├── INDICE.md · COHERENCIA.md · README.md
├── decisiones/               ADR-EQ-NNN
├── plantillas/
└── estado/
productos/<producto>/
├── INDICE.md · producto.yaml
├── decisiones/               nivel 3: ADR-<SIGLA>-NNN, su INDICE.md y su COHERENCIA.md
├── terceros/<id>/            ficha.yaml y docs/ del producto comprado y de cada integración; INDICE.md
├── historias/                historias de usuario (Jira o CSV): INDICE.md con cambios y candidatas a ADR
├── as-is/                    fichas por repositorio y PRODUCTO.md
├── revisiones/<id>/          reporte, paquetes y borradores de cada revisión
├── triaje/ · agendas/
├── estado/                   hallazgos.json, coherencia.json
└── repos/                    copias de los repositorios (fuera de git)
herramientas/                 scripts deterministas y sus pruebas (make test)
.cursor/                      reglas y comandos de Cursor
```

El contrato de trabajo completo está en [AGENTS.md](AGENTS.md).

## Estado

**MVP:** `/estado`, `/arquitectura`, `/actualizar`, `/producto`, `/adr`, `/revisar`, `/triar` y `/historia`.

**Fase 2:** revisión de ramas (`--rama`, `--desde`) con publicación en el MR o PR (GitLab o GitHub) y
reporte semanal.

**Fase 3:** pruebas de integración y de carga.
