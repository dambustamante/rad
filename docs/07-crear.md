# 7. Crear ADR, Tareas, Spikes y Bugs (`/crear`)

```
/crear motor-fraudes [adr | excepcion | tarea | spike | bug]
```

Sin tipo, Cursor pregunta qué crear. En todos los casos no se inventan respuestas: lo que el
usuario no sepa queda `NO DETERMINADO`.

| Tipo | Para qué | Dónde queda |
|---|---|---|
| `adr` | regla propia del producto, que `/revisar` evalúa | `productos/<p>/decisiones/` |
| `excepcion` | apartarse formalmente de una regla, con vencimiento | `productos/<p>/decisiones/` |
| `tarea` | Deuda Técnica o Deuda Operativa | `productos/<p>/historias/borradores/` y Jira |
| `spike` | investigar para decidir (2 días como máximo) | `productos/<p>/historias/borradores/` y Jira |
| `bug` | algo que falla en producción | `productos/<p>/historias/borradores/` y Jira |

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

## ADR a partir de historias de usuario

```
/crear motor-fraudes adr --desde-historias
```

Requiere la fuente de historias configurada (ver [Productos y terceros](04-productos.md)). La
mayoría de las historias no implica una decisión de arquitectura: se usan para **proponer**
decisiones a partir de requisitos no funcionales, restricciones y Spikes.

1. **Sincronizar** (solo lectura):

   ```sh
   .venv/bin/python herramientas/jira.py sincronizar motor-fraudes
   ```

   Guarda cada historia con su descripción y criterios de aceptación. En `historias/INDICE.md`
   registra las nuevas, las modificadas (con el antes y el después) y las retiradas.

2. **Candidatas** (sin IA):

   ```sh
   .venv/bin/python herramientas/jira.py candidatas motor-fraudes
   ```

   Incluye siempre los Spikes y la Deuda Técnica; las demás, solo si tienen señales de tiempos,
   disponibilidad, retención, seguridad o resiliencia.

3. **Clasificar en un lote**, `historias/clasificacion-lote.yaml`:

   ```yaml
   historias:
     - clave: FRAUD-123
       clasificacion: candidata
       tema: Latencia de evaluación
       cita: La evaluación responde en menos de 150 ms
       explicacion: Requisito de latencia verificable en el código.
     - clave: FRAUD-140
       clasificacion: choque
       documento: decision-records:ADR-010
       cita: Los reintentos se hacen en cada servicio
       cita_documento: Los reintentos se configuran solo en el API Gateway
       explicacion: La historia pide algo que arquitectura prohíbe; conversar antes de implementar.
     - clave: FRAUD-151
       clasificacion: sin_impacto
   ```

   ```sh
   .venv/bin/python herramientas/jira.py clasificar motor-fraudes
   ```

   Las citas se validan contra la historia y el documento. Una historia ya analizada no se vuelve a
   pedir mientras no cambie.

4. **Proponer:** `jira.py propuestas motor-fraudes` agrupa las candidatas por tema. Se crea un ADR
   por cada tema que el usuario elija:

   ```sh
   .venv/bin/python herramientas/adr.py nuevo motor-fraudes --tipo decision --titulo "Latencia de evaluación" --historias FRAUD-123,FRAUD-130
   ```

   Los choques no generan ADR: se informan como temas para conversar.

5. **Seguimiento:** si una historia de origen cambia o se retira, el ADR aparece en `listar` con
   "revisar: …". Si sigue vigente, se confirma con `jira.py confirmar motor-fraudes --adr ADR-MF-001`;
   si no, se ajusta (si está Propuesto) o se reemplaza (si está Aprobado).

## Tareas, Spikes y Bugs

Siguen ADR-EQ-009 (estructura) y ADR-EQ-008 (definición de terminado).

| Incidencia | Campo Tipo | Criterios fijos que agrega la plantilla |
|---|---|---|
| Tarea | Deuda Técnica | la revisión ya no reporta los hallazgos de origen |
| Tarea | Deuda Operativa | la tarea manual deja de ser necesaria |
| Bug | Bau/Incidentes | se reproduce el error, la causa queda documentada y hay una prueba que evita que se repita |
| Spike | Spike | la pregunta tiene respuesta documentada, hay un ADR de producto Propuesto y se respetó la duración máxima |

Los tipos Producto y Otros no se crean desde aquí. El campo Equipos siempre es `Back`.

### Paso 1: preguntas por tipo

| Tipo | Qué pregunta Cursor |
|---|---|
| Spike | qué hay que decidir (una sola pregunta), por qué ahora, qué opciones se conocen, qué pesa más al decidir y qué repositorios o terceros toca |
| Bug | qué falla y dónde, desde cuándo y en qué entorno, el impacto, cómo reproducirlo y la evidencia (logs, `trace_id`, incidente) |
| Deuda Operativa | qué tarea manual se hace hoy, con qué frecuencia y cuánto tarda, quién la hace y con qué riesgo, y qué repositorios intervienen |
| Deuda Técnica | con `--desde`, solo si conviene agrupar otros hallazgos del mismo tema; sin `--desde`, qué corregir, dónde, qué problema causa y qué evidencia hay |

Además pide unas palabras clave del tema para buscar en la documentación de terceros y en Jira.

### Paso 2: borrador y contexto

```sh
.venv/bin/python herramientas/jira.py nueva motor-fraudes --tipo tarea --titulo "Agregar timeout al cliente del buró" \
  --desde H-0041,H-0052 --tema "timeout buró"
```

Opciones: `--categoria "Deuda Operativa"`, `--repos <repo1,repo2>`, `--desde <hallazgos>`,
`--tema "<palabras clave>"`. Crea dos archivos en `historias/borradores/`:

- `<NNN>-<título>.md`: el borrador, con la plantilla de su tipo ya cargada;
- `<NNN>-<título>-contexto.md`: lo que Cursor necesita para redactarlo: hallazgos de origen y
  relacionados, AS IS de los repositorios, decisiones que pueden aplicar, terceros, documentación
  encontrada, historias parecidas de Jira y Sonar.

Si una historia de Jira ya cubre lo mismo, Cursor avisa antes de seguir.

### Paso 3: redactar

- **Como** un rol real (nunca "sistema"), **Quiero** lo concreto, **Para** el valor sin repetir el
  Quiero.
- **Criterios de aceptación:** al menos uno propio y medible, más los fijos de su tipo.
- Las secciones del tipo con evidencia: hallazgos, `archivo:línea`, métricas.
- Solo las decisiones que el trabajo debe respetar, con su regla rápida.
- El título de una Tarea o un Spike empieza con un verbo en infinitivo ("Agregar…", "Evaluar…").

### Paso 4: validar

```sh
.venv/bin/python herramientas/jira.py validar motor-fraudes <borrador>
```

Verifica la combinación de incidencia y Tipo, Equipos, Como/Quiero/Para, las secciones del tipo,
los criterios fijos, al menos un criterio propio medible, que un Spike tenga una sola pregunta y
como máximo 2 días, y la regla de lenguaje. Se corrige hasta que no haya errores.

### Paso 5: vista previa

```sh
.venv/bin/python herramientas/jira.py crear motor-fraudes <borrador>
```

Sin `--confirmar` no escribe nada: muestra el proyecto, el tipo, el título y el texto completo tal
como quedará en Jira.

### Paso 6: crear en Jira

Solo si el usuario lo confirma explícitamente sobre la vista previa:

```sh
.venv/bin/python herramientas/jira.py crear motor-fraudes <borrador> --confirmar
```

La clave de Jira (por ejemplo `FRAUD-210`) queda en el borrador y en cada hallazgo de origen.
