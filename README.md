# radiografia

Muestra el estado real (AS IS) de los repositorios de cada producto y lo compara, en este orden,
contra:

1. los ADR de arquitectura,
2. los estándares de arquitectura,
3. las decisiones del equipo (ADR-EQ) y del producto (ADR-<SIGLA>),
4. Sonar (SonarQube, incluida la Community Edition, o SonarCloud).

El resultado es una ficha por repositorio y por producto, con hallazgos respaldados por evidencia
(`ruta:línea` y cita del documento incumplido). Un problema se reporta una sola vez, en el nivel más
alto en que aparece.

`radiografia` no modifica los repositorios que revisa. Lo único que escribe fuera es una Tarea, un
Spike o un Bug en Jira, y solo después de mostrar la vista previa y recibir confirmación explícita.

## Requisitos

- macOS con Python 3.11 o superior, `git` y `make`.
- [Cursor](https://cursor.com), para los comandos que requieren criterio.
- Acceso de lectura por git (SSH o HTTPS) a los repositorios de arquitectura y de los productos,
  en GitLab o GitHub.
- `gitleaks` (`brew install gitleaks`), para buscar secretos.
- `pdftotext` (`brew install poppler`), para leer documentación de terceros en PDF.
- Un token de Sonar con permiso de lectura.
- Opcional: un token de Jira Cloud, para leer historias de usuario y crear Tareas, Spikes y Bugs.
- El token de la plataforma git se necesita recién en la fase 2.

## Primer uso

**1. Preparar el entorno**

```sh
cp .env.example .env      # completar Sonar y, si se usa, Jira
make venv                 # crea el entorno de Python
make doctor               # verifica herramientas y configuración (no muestra valores)
```

**2. En Cursor**

Ante la duda, empezar por `/estado`: muestra en qué situación está todo y qué comando sigue.
El orden habitual es:

| Paso | Comando | Qué pasa |
|---|---|---|
| 1 | `/actualizar fuentes` | pide los repositorios de arquitectura, los inspecciona y propone las fuentes |
| 2 | `/actualizar` | descarga arquitectura, genera los índices y verifica la coherencia de las decisiones del equipo |
| 3 | `/producto <nombre>` | registra el producto, sus repositorios y sus terceros |
| 4 | `/revisar <producto>` | revisa **un repositorio por conversación**; abrir un chat nuevo para cada uno |
| 5 | `/triar <producto>` | registra qué se hace con cada hallazgo |
| 6 | `/crear <producto>` | crea ADR del producto, excepciones, o Tareas, Spikes y Bugs para Jira |

**Recomendación para la primera línea base:** revisar primero dos o tres repositorios
representativos, triar sus hallazgos y medir el consumo de Cursor antes de revisar el resto.

## Comandos

### `/estado`

Es el punto de entrada y no usa red ni IA. Muestra:

- la antigüedad de la copia de arquitectura;
- la coherencia pendiente;
- la configuración de Sonar;
- por producto: repositorios por revisar, hallazgos sin triar, excepciones vencidas, terceros
  incompletos, historias por analizar y borradores sin crear en Jira.

Termina con la lista de qué comando sigue.

### `/actualizar [fuentes]`

- **Fuentes de arquitectura** (`/actualizar fuentes`): inspecciona cada repositorio, propone las
  fuentes (ADR, estándares o referencias, con rama y carpeta) y las registra con confirmación.
- **Sincronización:**
  - descarga arquitectura solo con git y fija el commit de cada fuente;
  - lee el estado de cada ADR (Aprobado, Propuesto, Reemplazado…); lo que no se puede leer queda
    `NO DETERMINADO`;
  - informa los documentos nuevos, modificados y eliminados, y los cambios de vigencia.
- **Coherencia:**
  - compara cada ADR-EQ con arquitectura, y cada ADR de producto con arquitectura y con el equipo;
  - primero filtra por tema y después compara con citas textuales validadas;
  - un `choca` suspende solo los criterios afectados hasta que se resuelva;
  - solo se vuelve a evaluar lo que cambió.
- **Repositorios y documentos:** actualiza las copias de los repositorios activos, vuelve a indexar
  la documentación de terceros que cambió, sincroniza las historias de Jira y regenera los índices.

### `/producto <nombre>`

- Crea el producto con una sigla para numerar sus ADR (por ejemplo `MF` para motor-fraudes).
- Agrega o retira repositorios: inspecciona cada uno y propone tipo (`propio`, `proveedor` o
  `config`), rama y clave de Sonar.
- **Terceros:** registra el producto comprado y cada integración en `terceros/<id>/`.
  - **Ficha:** protocolo, autenticación, tiempo de respuesta p95, límites, y la política ante falla
    con su justificación.
  - **Documentación:** una carpeta `docs/` con los archivos tal como llegan. Se indexa para buscarla
    y citarla: PDF, Word, PowerPoint, Excel, HTML, markdown y texto.
  - Los contratos OpenAPI y AsyncAPI se reconocen por su contenido.
  - Informa qué documentos no se pudieron leer y qué hacer con ellos.
- Configura la fuente de historias de usuario: una consulta JQL (Jira Query Language) o un tablero
  de Jira, o un CSV para proyectos archivados.

### `/revisar <producto> [repo]`

Revisa un repositorio por conversación:

1. **Parte automática** (`make revisar`):
   - actualiza la copia y detecta el stack;
   - busca secretos con gitleaks, también en el historial y sin mostrar valores;
   - verifica los criterios automáticos de los ADR-EQ (C4, contratos, README, logs);
   - lee Sonar: quality gate, issues, hotspots, métricas y desfase entre el análisis y el commit
     revisado.
2. **Paquete de revisión:** un único archivo con lo que la IA necesita, para no leer el repositorio
   completo:
   - qué evaluar por nivel;
   - señales en el código con `archivo:línea`;
   - terceros del repositorio;
   - resultados automáticos.
3. **AS IS y C4 inferido:**
   - el AS IS cubre propósito, arquitectura real, componentes, integraciones, contratos, datos,
     configuración, observabilidad y riesgos;
   - incluye un borrador de C4 de contexto y de contenedores.
4. **Registro en lote:** todas las evaluaciones y hallazgos van en un archivo YAML.
   - El script rechaza archivos o líneas que no existen, fragmentos que no están en el código y
     citas que no están en el documento.
   - Sin cita, un hallazgo no puede ser `incumplimiento`.
5. **Cierre:** veredicto del repositorio y avisos de lenguaje.

Además:

- **Revisión incremental:** si el código cambió poco desde la última revisión, solo se revisa lo que
  cambió y se heredan las evaluaciones anteriores. `--completa` fuerza una revisión completa.
- **Hallazgos con huella estable:** cada hallazgo se reconoce entre revisiones como abierto,
  corregido o reaparecido. Un hallazgo de Sonar se absorbe en el de nivel superior en la misma
  ubicación.
- **Modo propuesta:** los criterios de decisiones en estado Propuesto se informan, pero no afectan
  el veredicto. Sirven para calibrar antes de aprobar.
- **Excepciones:** una excepción aprobada y vigente deja sus criterios como NO APLICA en su alcance
  hasta que vence.
- **Producto:** cuando todos los repositorios están revisados, consolida
  `as-is/PRODUCTO.md` con la matriz repositorio × documento y las brechas comunes.

### `/triar <producto> [repo]`

- Genera una planilla con los hallazgos pendientes. Cada uno recibe una de cuatro decisiones:
  - **Resolver**;
  - **Conversar**;
  - **Deuda**, con vencimiento (90 días por defecto);
  - **Falso positivo**, con motivo; no reaparece mientras el código no cambie.

  También se puede decidir en grupo.
- Se aplica todo o nada. Los hallazgos para conversar quedan en una agenda por tema
  (`triaje/agenda-<fecha>.md`).
- **Calibración por fuente:**
  - con al menos 5 hallazgos triados y menos de 20% de falsos positivos, una fuente queda lista para
    publicar;
  - si es ruidosa, sugiere el ajuste: precisar el criterio, cambiar la severidad o desactivar la
    regla de Sonar.
- Ofrece convertir la deuda en una Tarea de Deuda Técnica con `/crear`.

### `/crear <producto> [tipo]`

| Tipo | Para qué |
|---|---|
| `adr` | Regla propia del producto, con criterios que `/revisar` evalúa |
| `excepcion` | Apartarse formalmente de una regla, con vencimiento; si exceptúa arquitectura, necesita su referencia de aprobación |
| `tarea` | Deuda Técnica (código o arquitectura) o Deuda Operativa (trabajo manual sin backoffice) |
| `spike` | Investigar para decidir, 2 días como máximo; termina con un ADR de producto propuesto |
| `bug` | Algo que falla en producción |

- **ADR desde historias de usuario** (`adr --desde-historias`):
  - sincroniza Jira en solo lectura;
  - filtra sin IA las candidatas: Spikes, Deuda Técnica y requisitos no funcionales;
  - las clasifica en lote con citas validadas y propone un ADR por tema;
  - detecta historias que chocan con arquitectura;
  - si una historia de origen cambia o se retira, el ADR queda marcado para revisión.
- **Tarea desde hallazgos** (`tarea --desde H-0041,H-0052`): arma el contexto con los hallazgos, el
  AS IS, las decisiones que aplican, los terceros, historias parecidas de Jira y Sonar.
- **Tareas, Spikes y Bugs** siguen ADR-EQ-009:
  - Como/Quiero/Para, criterios de aceptación medibles y los criterios fijos de su tipo;
  - Equipos = Back, y el campo Tipo según la combinación válida;
  - el borrador se valida y se muestra la vista previa;
  - se crea en Jira solo con `--confirmar`, y la clave queda en el borrador y en cada hallazgo de
    origen.

## Decisiones del equipo

Nueve ADR-EQ, numerados por importancia (detalle en [equipo/README.md](equipo/README.md)):

| ADR-EQ | Tema |
|---|---|
| 001 | Datos sensibles |
| 002 | Integraciones resilientes |
| 003 | Logs |
| 004 | Contratos como código |
| 005 | SOLID y KISS |
| 006 | C4 |
| 007 | README |
| 008 | Definición de terminado |
| 009 | Estructura de Tareas, Spikes y Bugs |

- **Plantilla:** todas las decisiones, del equipo y de los productos, usan una sola plantilla
  (`equipo/plantillas/adr.md`) con el formato de los ADR de arquitectura.
- **Criterios:** cada uno tiene un identificador estable (`EQ-NNN.N`, `<SIGLA>-NNN.N`) y su forma de
  verificación: `automática`, `revisión de código` o, para la forma de trabajar,
  `revisión de la historia` o `revisión del MR`.

## Lenguaje

Todo lo que se escribe va en español neutro y técnico, comprensible desde un desarrollador junior
hasta un arquitecto: sin voseo, sin adornos ni muletillas y con las siglas explicadas la primera vez.
La lista está en `equipo/lenguaje.yaml` y la verifica `herramientas/lenguaje.py`: bloquea lo que va a
Jira y solo avisa en el resto.

## Dónde mirar los resultados

| Archivo | Contenido |
|---|---|
| `productos/<p>/INDICE.md` | punto de entrada del producto: repositorios, ADR, terceros, revisiones y triaje pendiente |
| `productos/<p>/as-is/<repo>.md` | ficha del repositorio: datos, Sonar, AS IS, comparación por nivel y veredicto |
| `productos/<p>/as-is/PRODUCTO.md` | matriz de cumplimiento repositorio × documento, brechas y visión del producto |
| `productos/<p>/revisiones/<revisión>/` | reporte de cada revisión, paquetes de revisión y borradores C4 |
| `productos/<p>/triaje/agenda-<fecha>.md` | hallazgos para conversar con el equipo |
| `productos/<p>/decisiones/` | ADR del producto, su índice y su coherencia con arquitectura y con el equipo |
| `productos/<p>/terceros/INDICE.md` | producto comprado e integraciones: estado de cada ficha, contratos y documentos sin indexar |
| `productos/<p>/historias/INDICE.md` | historias de usuario, sus cambios y las candidatas a ADR |
| `productos/<p>/historias/borradores/` | borradores de Tareas, Spikes y Bugs, con la clave de Jira una vez creados |
| `equipo/INDICE.md` · `equipo/COHERENCIA.md` | decisiones del equipo y su coherencia con arquitectura |
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
├── plantillas/               ADR, Tarea, Spike, Bug, README y C4
├── lenguaje.yaml             expresiones a evitar
└── estado/
productos/<producto>/
├── INDICE.md · producto.yaml
├── decisiones/               nivel 3: ADR-<SIGLA>-NNN, su INDICE.md y su COHERENCIA.md
├── terceros/<id>/            ficha.yaml y docs/ del producto comprado y de cada integración; INDICE.md
├── historias/                historias de usuario (Jira o CSV) y borradores para Jira
├── as-is/                    fichas por repositorio y PRODUCTO.md
├── revisiones/<id>/          reporte, paquetes y borradores de cada revisión
├── triaje/                   planillas de triaje y agendas para conversar con el equipo
├── estado/                   hallazgos.json, coherencia.json
└── repos/                    copias de los repositorios (fuera de git)
herramientas/                 scripts deterministas y sus pruebas
.cursor/                      reglas y comandos de Cursor
harness.yaml                  fuentes de arquitectura, estados, calibración y fuentes publicables
.env                          conexiones y tokens (no versionado; ver .env.example)
```

## Make

`make help` lista los objetivos.

- **Uso habitual:** `make estado`, `make actualizar`, `make revisar P=<producto> [R=<repo>]` y
  `make test`.
- **Pasos internos de `make actualizar`**, que también se pueden ejecutar por separado: `doctor`,
  `sync-arquitectura`, `coherencia`, `repos`, `terceros`, `historias` e `indices`.

El contrato de trabajo completo está en [AGENTS.md](AGENTS.md).

## Estado

**MVP:** `/estado`, `/actualizar`, `/producto`, `/revisar`, `/triar` y `/crear`.

**Fase 2:** revisión de ramas (`--rama`, `--desde`) con publicación en el MR o PR (GitLab o GitHub) y
reporte semanal.

**Fase 3:** pruebas de integración y de carga.
