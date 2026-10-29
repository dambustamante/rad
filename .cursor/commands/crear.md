# /crear

Crea un ADR del producto o una Tarea, un Spike o un Bug para Jira.

Uso:

- `/crear <producto>`: preguntar qué crear.
- `/crear <producto> adr` o `excepcion`: un ADR del producto (`productos/<producto>/decisiones/`).
- `/crear <producto> tarea`, `spike` o `bug`: un borrador con la estructura de ADR-EQ-009, que se crea
  en Jira solo con confirmación.
- `/crear <producto> tarea --desde H-0041,H-0052`: una Tarea de Deuda Técnica a partir de hallazgos
  (por ejemplo, los marcados como Deuda en `/triar`).
- `/crear <producto> adr --desde-historias`: proponer ADR a partir de las historias de usuario.
- `/crear equipo adr`: una decisión del equipo (ADR-EQ), con
  `.venv/bin/python herramientas/adr.py nuevo equipo --tipo decision --titulo "<título>"`. Se completa
  igual que una decisión del producto, pero sus criterios pueden ser `automática` o
  `revisión de código`; después, `/actualizar` verifica su coherencia con arquitectura.

| Qué | Cuándo |
|---|---|
| `adr` (decision) | Regla propia del producto, evaluable en `/revisar` |
| `excepcion` | Apartarse formalmente de una regla, con vencimiento |
| `tarea` · Deuda Técnica | Corregir o mejorar código o arquitectura |
| `tarea` · Deuda Operativa | Eliminar trabajo manual por falta de un backoffice |
| `bug` · Bau/Incidentes | Corregir algo que falla en producción |
| `spike` · Spike | Investigar para decidir (2 días como máximo) |

Si no se indicó qué crear, preguntarlo primero. No inventar respuestas: lo que el usuario no sepa
queda `NO DETERMINADO`.

## ADR y excepciones

1. **Mostrar lo que hay** con `.venv/bin/python herramientas/adr.py listar <producto>` (ADR, tipo,
   estado, vencimiento y efecto). Destacar las excepciones vencidas o inactivas y los ADR marcados
   "revisar: …". Preguntar si se crea uno nuevo o se completa o aprueba uno existente.
2. **Crear:**

   ```sh
   .venv/bin/python herramientas/adr.py nuevo <producto> --tipo <decision|excepcion> --titulo "<título>" [--historias FRAUD-123]
   ```

   Si el producto no tiene sigla, proponer una y asignarla con
   `.venv/bin/python herramientas/productos.py sigla <producto> --asignar <SIGLA>`.
3. **Completar con el usuario**, sección por sección:
   - **decision:** contexto, decisión verificable, regla rápida y criterios `XX-NNN.N` con su
     severidad. Todos los criterios son de `revisión de código`.
   - **excepcion:** qué criterios se exceptúan (`EQ-006.1`, `MF-002.1` o `fuente:ID` de
     arquitectura), en qué repositorios, por qué, hasta cuándo y qué se hará para dejar de
     necesitarla. Si exceptúa arquitectura, pedir la referencia de aprobación; sin ella, la
     excepción queda inactiva.
4. **Validar** con `.venv/bin/python herramientas/adr.py validar <producto> --id <ADR>`. Corregir los
   errores e informar los avisos.
5. **Coherencia** (solo `decision`): ejecutar `/actualizar`. Una decisión del producto nunca relaja
   ni contradice lo que tiene más autoridad.
6. **Aprobar**, solo cuando el usuario lo indique: estado `Aprobado` y fecha de aprobación. Una
   `decision` solo se aprueba si `decisiones/COHERENCIA.md` no muestra choques ni pares pendientes.

Efectos en `/revisar`: los criterios de una `decision` Propuesta o Aprobada se evalúan en el nivel 3
(en modo `propuesta` mientras está Propuesta). Una `excepcion` Aprobada y vigente deja sus criterios
como NO APLICA en su alcance hasta que vence.

### Desde historias de usuario (`--desde-historias`)

La mayoría de las historias no implica una decisión de arquitectura: se usan para **proponer**
decisiones a partir de requisitos no funcionales, restricciones y Spikes.

1. `.venv/bin/python herramientas/jira.py sincronizar <producto>` (solo lectura). Si el producto no
   tiene fuente, configurarla (ver "Fuente de historias").
2. `.venv/bin/python herramientas/jira.py candidatas <producto>`: el script ya filtró sin IA (Spike,
   Deuda Técnica y las que tienen señales de tiempos, disponibilidad, seguridad, resiliencia…).
3. Clasificar en un solo lote, `productos/<producto>/historias/clasificacion-lote.yaml`, y registrar
   con `.venv/bin/python herramientas/jira.py clasificar <producto>`:

   ```yaml
   historias:
     - clave: FRAUD-123
       clasificacion: candidata          # candidata | sin_impacto | choque
       tema: Latencia de evaluación      # agrupa varias historias en un mismo ADR
       cita: La evaluación responde en menos de 150 ms   # copiada tal cual de la historia
       explicacion: Requisito de latencia verificable en el código.
     - clave: FRAUD-140
       clasificacion: choque             # contradice un ADR o estándar vigente
       documento: decision-records:ADR-010
       cita: Los reintentos se hacen en cada servicio
       cita_documento: Los reintentos se configuran solo en el API Gateway
       explicacion: La historia pide algo que arquitectura prohíbe; conversar antes de implementar.
     - clave: FRAUD-151
       clasificacion: sin_impacto
   ```

   Las citas se validan contra la historia y el documento; si hay errores no se registra nada.
4. Mostrar `jira.py propuestas <producto>` (candidatas por tema) y crear solo los ADR que el usuario
   elija, con `--historias`. Los choques se informan aparte: son temas para conversar, no ADR.

Si una historia de origen cambia o se retira, el ADR aparece en `listar` con "revisar: …". Ver el
antes y después en `historias/INDICE.md`: si el ADR sigue vigente,
`jira.py confirmar <producto> --adr <ADR>`; si no, ajustarlo (Propuesto) o reemplazarlo (Aprobado).

### Fuente de historias

Una sola vez por producto:

```sh
.venv/bin/python herramientas/productos.py historias <producto> --fuente jira --jql "project = FRAUD AND labels = motor-fraudes" --campo-tipo Tipo --proyecto FRAUD
.venv/bin/python herramientas/productos.py historias <producto> --fuente archivo --archivo export.csv --campo-tipo Tipo
.venv/bin/python herramientas/productos.py historias <producto> --fuente ninguna
```

Preferir `--jql` a `--tablero`: sigue funcionando aunque el tablero se elimine. Si el proyecto está
archivado, exportar a CSV y usar `--fuente archivo`. `--proyecto` es el destino de las Tareas,
Spikes y Bugs.

## Tareas, Spikes y Bugs

1. **Preguntas por tipo**, de a una o todas juntas:

   **Spike:**
   1. ¿Qué hay que decidir? Una sola pregunta concreta (por ejemplo, "¿Kafka o RabbitMQ para los
      eventos de evaluación?"). De ahí sale el título: "Evaluar… para decidir…".
   2. ¿Por qué hay que decidirlo ahora? Qué trabajo queda bloqueado.
   3. ¿Qué opciones se conocen de entrada?
   4. ¿Qué pesa más al decidir? (cumplimiento de ADR, latencia, costo, operación, soporte del proveedor…)
   5. ¿Qué repositorios o terceros toca?

   No preguntar la duración (2 días), el entregable (ADR de producto en Propuesto) ni los criterios
   fijos: ya vienen en la plantilla.

   **Bug:**
   1. ¿Qué falla y dónde? (servicio, endpoint, proceso)
   2. ¿Desde cuándo y en qué entorno?
   3. ¿Cuál es el impacto? (transacciones, clientes o procesos afectados, con cantidades si se conocen)
   4. ¿Se puede reproducir? Pasos o datos de entrada.
   5. ¿Hay evidencia? Logs, `trace_id`, alertas o el incidente asociado.

   **Tarea de Deuda Operativa:**
   1. ¿Qué tarea manual se hace hoy y por qué falta un backoffice para evitarla?
   2. ¿Con qué frecuencia se hace y cuánto tarda cada vez?
   3. ¿Quién la hace y qué riesgo tiene hacerla a mano?
   4. ¿Qué repositorios estarían involucrados en automatizarla?

   **Tarea de Deuda Técnica:** con `--desde`, el contexto sale de los hallazgos: solo preguntar si
   conviene agrupar otros abiertos del mismo tema (el contexto los lista) y confirmar el título. Sin
   `--desde`: qué hay que corregir o mejorar, dónde, qué problema causa hoy y qué evidencia hay.

   En todos los casos, pedir unas palabras clave del tema si no surgen de las respuestas: sirven para
   buscar en la documentación de los terceros y en Jira.

2. **Borrador y contexto:**

   ```sh
   .venv/bin/python herramientas/jira.py nueva <producto> --tipo <tarea|spike|bug> --titulo "<título>" \
     [--categoria "Deuda Operativa"] [--desde H-0041,H-0052] [--repos <repo1,repo2>] [--tema "<palabras clave>"]
   ```

   El título de una Tarea o un Spike empieza con un verbo en infinitivo ("Agregar…", "Evaluar…").
3. **Leer el contexto** (`…-contexto.md`): hallazgos, AS IS, decisiones, terceros, historias
   parecidas de Jira y Sonar. Si una historia de Jira ya cubre lo mismo, avisar antes de seguir.
4. **Redactar** `productos/<producto>/historias/borradores/<NNN>-<título>.md` sobre la plantilla ya
   cargada:
   - **Como**: un rol real, nunca "sistema". **Para**: el valor, sin repetir el Quiero.
   - **Criterios de aceptación**: al menos uno propio y medible, más los fijos de su tipo.
   - Las secciones de su tipo con evidencia (hallazgos, `archivo:línea`, métricas).
   - Solo las decisiones que el trabajo debe respetar, con su regla rápida.
   - No editar el encabezado YAML salvo para corregir el Tipo o los repositorios.
5. **Validar y ver la vista previa:** `.venv/bin/python herramientas/jira.py crear <producto> <borrador>`.
   Primero valida (ADR-EQ-009 y lenguaje); si hay errores, corregirlos y repetir. Sin errores, mostrar
   el título, el proyecto, el tipo y el texto completo.
6. **Crear en Jira** solo si el usuario lo confirma explícitamente sobre la vista previa:
   `.venv/bin/python herramientas/jira.py crear <producto> <borrador> --confirmar`. La clave queda
   en el borrador y en cada hallazgo de origen.

No se crean historias de tipo Producto u Otros.
