# 7. Crear ADR, Tareas, Spikes, Errores y Hotfix (`/crear`)

```
/crear motor-fraudes [adr | excepcion | tarea | spike | error | hotfix]
```

Sin tipo, Cursor pregunta qué crear. En todos los casos no se inventan respuestas: lo que el
usuario no sepa queda `NO DETERMINADO`.

| Tipo | Para qué | Dónde queda |
|---|---|---|
| `adr` | regla propia del producto, que `/revisar` evalúa | `productos/<p>/decisiones/` |
| `excepcion` | apartarse formalmente de una regla, con vencimiento | `productos/<p>/decisiones/` |
| `tarea` | Deuda Técnica o Deuda Operativa | `productos/<p>/historias/borradores/` y Jira |
| `spike` | investigar para decidir (2 días como máximo) | `productos/<p>/historias/borradores/` y Jira |
| `error` | algo que falla en producción | `productos/<p>/historias/borradores/` y Jira |
| `hotfix` | corregir de inmediato algo que falla en producción y no puede esperar | `productos/<p>/historias/borradores/` y Jira |

## Decisión del equipo (ADR-EQ)

```sh
.venv/bin/python herramientas/adr.py nuevo equipo --tipo decision --titulo "Versionado de APIs"
```

Crea `equipo/decisiones/ADR-EQ-010-versionado-de-apis.md` con el siguiente número libre, desde la
misma plantilla y sin la sección 14 (que es solo de los productos). Se completa igual que una
decisión del producto; sus criterios pueden ser `automática` o `revisión de código`. Después,
`/actualizar` verifica su coherencia con arquitectura.

## ADR del producto

### Paso 1: ver lo que hay

```sh
.venv/bin/python herramientas/adr.py listar motor-fraudes
```

Muestra cada ADR con su tipo, estado, vencimiento y efecto. Destaca las excepciones vencidas o
inactivas y los ADR marcados "revisar: …" porque cambió una historia de origen.

### Paso 2: crear

```sh
.venv/bin/python herramientas/adr.py nuevo motor-fraudes --tipo decision --titulo "Latencia de evaluación"
```

Asigna el número (`ADR-MF-001`) y crea el archivo desde `equipo/plantillas/adr.md`, la misma
plantilla que usan los ADR-EQ, con el formato de los ADR de arquitectura (secciones 2 a 13) más la
sección 14, "Tipo y alcance".

### Paso 3: completar con el usuario

**Decisión:** contexto, decisión verificable, regla rápida y criterios `MF-001.1`, `MF-001.2`…, cada
uno con su severidad. En un ADR de producto todos los criterios son de `revisión de código`.

**Excepción:** en la sección 14 se indica:

| Campo | Contenido |
|---|---|
| Criterios exceptuados | criterios del equipo o del producto (`EQ-001.1`, `MF-002.1`) o documentos de arquitectura (`fuente:ID`) |
| Repositorios | `todos` o una lista de `id` |
| Vence | fecha `AAAA-MM-DD`; al vencer, los criterios se vuelven a evaluar |
| Referencia de aprobación de arquitectura | ticket, acta o correo; obligatoria si exceptúa arquitectura; sin ella, la excepción queda inactiva |

También se documenta por qué se necesita y qué se hará para dejar de necesitarla.

### Paso 4: validar

```sh
.venv/bin/python herramientas/adr.py validar motor-fraudes --id ADR-MF-001
```

Detecta errores (tipo inválido, criterios exceptuados que no existen, fecha mal escrita,
repositorios que no están en el producto) y avisos (por ejemplo, una excepción de arquitectura sin
referencia de aprobación).

### Paso 5: coherencia y aprobación

1. Ejecutar `/actualizar`: compara la decisión con arquitectura y con los ADR-EQ (ver
   [Arquitectura y coherencia](03-arquitectura.md)).
2. Aprobar solo cuando el usuario lo indique: estado `Aprobado` y fecha de aprobación. Una decisión
   solo se aprueba si `decisiones/COHERENCIA.md` no muestra choques ni pares pendientes.

**Efecto en `/revisar`:**

- Una decisión Propuesta se evalúa en modo propuesta (informa, no afecta el veredicto); una
  Aprobada, con efecto.
- Una excepción Aprobada y vigente deja sus criterios como NO APLICA en su alcance hasta que vence.

Un ADR Aprobado no se edita: se crea uno nuevo que lo reemplaza y el anterior pasa a Reemplazado.

## Tareas, Spikes, Errores y Hotfix

Siguen ADR-EQ-009 (estructura) y ADR-EQ-008 (definición de terminado).

| Incidencia | Campo Tipo | Criterios fijos que agrega la plantilla |
|---|---|---|
| Tarea | Deuda Técnica | la revisión ya no reporta los hallazgos de origen |
| Tarea | Deuda Operativa | la tarea manual deja de ser necesaria |
| Error | Bau/Incidentes | se reproduce el error, la causa queda documentada y hay una prueba que evita que se repita |
| Hotfix | Bau/Incidentes | la corrección está en producción y el servicio vuelve a funcionar, y hay un Error de seguimiento |
| Spike | Spike | la pregunta tiene respuesta documentada, hay un ADR de producto Propuesto y se respetó la duración máxima |

Los tipos Producto y Otros no se crean desde aquí: las Tareas de desarrollo de una historia se crean con `/hdu` en el
harness o a mano. El campo Equipos siempre es `Back`.

**Hotfix y Error de seguimiento.** Un Hotfix se escribe con lo mínimo para corregir ya. Después de
crearlo en Jira se crea su Error de seguimiento, que documenta la causa y agrega la prueba que
reproduce la falla:

```sh
.venv/bin/python herramientas/jira.py nueva motor-fraudes --tipo error --hotfix FRAUD-300 \
  --titulo "Rechazo masivo por timeout del buró en fraude-core"
```

La clave del Hotfix queda en las historias relacionadas del Error. `/estado` avisa si un Hotfix creado
todavía no tiene su Error de seguimiento (EQ-008.9).

### Paso 1: preguntas por tipo

| Tipo | Qué pregunta Cursor |
|---|---|
| Spike | qué hay que decidir (una sola pregunta), por qué ahora, qué opciones se conocen, qué pesa más al decidir y qué repositorios o terceros toca |
| Error | qué falla y dónde, desde cuándo y en qué entorno, el impacto, cómo reproducirlo, la evidencia (logs, `trace_id`, incidente) y si es el seguimiento de un Hotfix |
| Hotfix | solo lo mínimo para actuar ya: qué falla y desde cuándo, el impacto, la evidencia y la corrección con su vuelta atrás. La causa y cómo reproducirlo van en el Error de seguimiento |
| Deuda Operativa | qué tarea manual se hace hoy, con qué frecuencia y cuánto tarda, quién la hace y con qué riesgo, y qué repositorios intervienen |
| Deuda Técnica | con `--desde`, solo si conviene agrupar otros hallazgos del mismo tema; sin `--desde`, qué corregir, dónde, qué problema causa y qué evidencia hay |

Además pide unas palabras clave del tema para buscar en la documentación de terceros y en Jira.

### Paso 2: borrador y contexto

```sh
.venv/bin/python herramientas/jira.py nueva motor-fraudes --tipo tarea --titulo "Agregar timeout al cliente del buró" \
  --desde H-0041,H-0052 --tema "timeout buró"
```

Opciones: `--categoria "Deuda Operativa"`, `--repos <repo1,repo2>`, `--desde <hallazgos>`,
`--tema "<palabras clave>"` y, en un Error, `--hotfix <clave>`. Crea dos archivos en `historias/borradores/`:

- `<NNN>-<título>.md`: el borrador, con la plantilla de su tipo ya cargada;
- `<NNN>-<título>-contexto.md`: lo que Cursor necesita para redactarlo: hallazgos de origen y
  relacionados, AS IS de los repositorios, decisiones que pueden aplicar, terceros, documentación
  encontrada y Sonar.

Si una historia de Jira ya cubre lo mismo, Cursor avisa antes de seguir.

### Paso 3: redactar

- **Como** un rol real (nunca "sistema"), **Quiero** lo concreto, **Para** el valor sin repetir el
  Quiero.
- **Criterios de aceptación:** al menos uno propio y medible, más los fijos de su tipo.
- Las secciones del tipo con evidencia: hallazgos, `archivo:línea`, métricas.
- Solo las decisiones que el trabajo debe respetar, con su regla rápida.
- El título de una Tarea o un Spike empieza con un verbo en infinitivo ("Agregar…", "Evaluar…").

### Paso 4: validar y ver la vista previa

```sh
.venv/bin/python herramientas/jira.py crear motor-fraudes <borrador>
```

Primero valida: la combinación de incidencia y Tipo, Equipos, Como/Quiero/Para, las secciones del
tipo, los criterios fijos, al menos un criterio propio medible, que un Spike tenga una sola pregunta
y como máximo 2 días, y la regla de lenguaje. Si hay errores, se corrigen y se repite.

Sin errores, y sin `--confirmar`, no escribe nada: muestra el proyecto, el tipo, el título y el
texto completo tal como quedará en Jira.

### Paso 5: crear en Jira

Solo si el usuario lo confirma explícitamente sobre la vista previa:

```sh
.venv/bin/python herramientas/jira.py crear motor-fraudes <borrador> --confirmar
```

La clave de Jira (por ejemplo `FRAUD-210`) queda en el borrador y en cada hallazgo de origen.
