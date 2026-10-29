# 2. Conceptos

## Orden de autoridad

Cada repositorio se compara contra cuatro niveles. Un problema se reporta **una sola vez**, en el
nivel más alto en que aparece.

| Nivel | Fuente | Dónde vive | Quién la escribe |
|---|---|---|---|
| 1 | ADR de arquitectura vigentes | `arquitectura/decisiones/` | arquitectura (se descarga, no se edita) |
| 2 | Estándares de arquitectura vigentes | `arquitectura/estandares/` | arquitectura (se descarga, no se edita) |
| 3 | Decisiones del equipo (ADR-EQ) y del producto (ADR-<SIGLA>) | `equipo/decisiones/`, `productos/<p>/decisiones/` | el equipo |
| 4 | Sonar | API de Sonar | análisis de Sonar (solo lectura) |

- Arquitectura prevalece siempre. Si una decisión del equipo choca con arquitectura, sus criterios
  afectados quedan suspendidos hasta resolver el choque.
- Un documento de arquitectura que no está vigente (Propuesto, Reemplazado, Deprecado, Rechazado)
  no se usa para evaluar.
- Una decisión del equipo o del producto en estado **Propuesto** se evalúa en **modo propuesta**:
  sus hallazgos se informan, pero no afectan el veredicto. Sirve para calibrarla antes de aprobarla.
- La única forma de apartarse de una regla es un ADR de producto de tipo **excepción**, aprobado y
  con vencimiento.

## Evidencia

Toda afirmación lleva su etiqueta:

| Etiqueta | Significado |
|---|---|
| `[hecho] ruta:línea` | verificado en el código o en un archivo |
| `[doc] ruta` | lo afirma la documentación del repositorio |
| `[inferencia]` | deducción razonable, marcada como tal |
| `[recomendación]` | propuesta; nunca se presenta como hecho |
| `NO DETERMINADO - <motivo>` | no se pudo verificar |

Los scripts validan la evidencia: rechazan archivos o líneas que no existen, fragmentos que no
están en el código y citas que no aparecen textualmente en el documento.

## Evaluaciones y hallazgos

Cada elemento a evaluar (un documento de arquitectura o un criterio de una decisión) recibe un
resultado: `CUMPLE`, `NO CUMPLE`, `NO APLICA - <motivo>` o `NO DETERMINADO - <motivo>`.

Todo `NO CUMPLE` genera al menos un **hallazgo**:

| Campo | Valores |
|---|---|
| `id` | `H-0001`, estable para siempre |
| `nivel` | 1 a 4 |
| `fuente` y `criterio` | por ejemplo `ADR-EQ-002` y `EQ-002.1`, o `decision-records:ADR-010` |
| `categoria` | `incumplimiento`, `diseño`, `error`, `seguridad`, `deuda`, `documentacion` |
| `severidad` | `bloqueante`, `alta`, `media`, `baja` |
| `estado` | `abierto`, `corregido`, `reaparecido` |
| `modo` | `vigente` o `propuesta` |

- **Huella estable:** el hallazgo se reconoce entre revisiones por su fuente, archivo y fragmento.
  Si desaparece del código queda `corregido`; si vuelve, `reaparecido`.
- **Absorción:** si un issue de Sonar está en la misma ubicación que un hallazgo de nivel superior,
  queda asociado a ese hallazgo y no se cuenta dos veces.
- **Sin cita, no hay incumplimiento:** un hallazgo sin cita del documento es como máximo `diseño`,
  `error` o `deuda`.

## Veredicto

Un repositorio **NO PASA** si tiene algún hallazgo `bloqueante` o `alta` que esté abierto, en modo
vigente, no absorbido y no descontado por el triaje (deuda aceptada sin vencer o falso positivo).
En cualquier otro caso, **PASA**.

## Estructura de carpetas

Cada nivel tiene la misma forma: `decisiones/`, un `INDICE.md` y, si corresponde, un
`COHERENCIA.md`. Los archivos en MAYÚSCULAS los generan los scripts y no se editan. Los datos de las
herramientas viven siempre en `estado/`.

```
arquitectura/                 niveles 1 y 2: copia de arquitectura
├── INDICE.md
├── decisiones/<fuente>/
├── estandares/<fuente>/
└── estado/                   commit sincronizado de cada fuente
equipo/                       nivel 3: decisiones del equipo
├── INDICE.md · COHERENCIA.md · README.md
├── decisiones/               ADR-EQ-NNN
├── plantillas/               ADR, Tarea, Spike, Error, Hotfix, README y C4
├── lenguaje.yaml             expresiones a evitar
└── estado/                   coherencia.json
productos/<producto>/
├── INDICE.md · producto.yaml
├── decisiones/               ADR-<SIGLA>-NNN, INDICE.md y COHERENCIA.md
├── terceros/<id>/            ficha.yaml y docs/; terceros/INDICE.md
├── historias/                INDICE.md y borradores/ para Jira
├── as-is/                    <repo>.md y PRODUCTO.md
├── revisiones/<id>/          reporte, paquetes, lotes, AS IS y borradores C4
├── triaje/                   planillas de triaje y agendas
├── semanal/                  reportes semanales (AAAA-Wnn.md)
├── estado/                   hallazgos.json, historias, índices de terceros
├── repos/                    copias de los repositorios (fuera de git, solo lectura)
└── harness/                  copia del harness del producto, con sus ADR (fuera de git; ver la guía 9)
.cache/ramas/                 copias de las ramas en revisión (fuera de git, solo lectura)
.cursor/                      commands/ (comandos), partes/ (pasos que un comando lee solo cuando los
                              necesita), rules/ y hooks.json (guardia de comandos)
```

## Lenguaje

Todo lo que se escribe (AS IS, hallazgos, ADR, historias) va en español neutro y técnico,
comprensible desde un desarrollador junior hasta un arquitecto:

- se nombra el componente, la tecnología y el dato concreto;
- frases cortas, voz activa y siglas explicadas la primera vez;
- sin voseo ni regionalismos, sin adornos ("robusto", "potenciar") ni muletillas ("Es importante
  destacar").

La lista está en `equipo/lenguaje.yaml`. `herramientas/lenguaje.py` la verifica: **bloquea** lo que
va a Jira y **avisa** en el resto.

```sh
.venv/bin/python herramientas/lenguaje.py <archivo> [--estricto]
```
