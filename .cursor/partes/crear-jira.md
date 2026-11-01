# /crear: Tareas, Spikes, Errores y Hotfix

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

   **Error:**
   1. ¿Qué falla y dónde? (servicio, endpoint, proceso)
   2. ¿Desde cuándo y en qué entorno?
   3. ¿Cuál es el impacto? (transacciones, clientes o procesos afectados, con cantidades si se conocen)
   4. ¿Se puede reproducir? Pasos o datos de entrada.
   5. ¿Hay evidencia? Logs, `trace_id`, alertas o el incidente asociado.
   6. ¿Es el seguimiento de un Hotfix? Si lo es, su clave va en `--hotfix`.

   **Hotfix** (urgente: solo lo mínimo para actuar ya):
   1. ¿Qué falla en producción y dónde, y desde cuándo?
   2. ¿Cuál es el impacto?
   3. ¿Qué evidencia hay? (logs, `trace_id`, alertas)
   4. ¿Qué corrección se aplica y cómo se vuelve atrás si falla?

   No preguntar la causa ni cómo reproducirlo: van en el Error de seguimiento. Después de crear el
   Hotfix en Jira, ofrecer crear ese Error con `--hotfix <clave del Hotfix>`.

   **Tarea de Deuda Operativa:**
   1. ¿Qué tarea manual se hace hoy y por qué falta un backoffice para evitarla?
   2. ¿Con qué frecuencia se hace y cuánto tarda cada vez?
   3. ¿Quién la hace y qué riesgo tiene hacerla a mano?
   4. ¿Qué repositorios estarían involucrados en automatizarla?

   **Tarea desde la deuda de una historia** (`--deuda <CLAVE>`): la deuda que se declaró en `/listo`
   y que se registró al revisar sus MR. El contexto la lista; solo confirmar el título y si conviene una
   Tarea por cada punto o una para todos.

   **Tarea de Deuda Técnica:** con `--desde`, el contexto sale de los hallazgos: solo preguntar si
   conviene agrupar otros abiertos del mismo tema (el contexto los lista) y confirmar el título. Sin
   `--desde`: qué hay que corregir o mejorar, dónde, qué problema causa hoy y qué evidencia hay.

   En todos los casos, pedir unas palabras clave del tema si no surgen de las respuestas: sirven para
   buscar en la documentación de los terceros y en Jira.

2. **Borrador y contexto:**

   ```sh
   .venv/bin/python herramientas/jira.py nueva <producto> --tipo <tarea|spike|error|hotfix> --titulo "<título>" \
     [--categoria "Deuda Operativa"] [--desde H-0041,H-0052] [--repos <repo1,repo2>] [--tema "<palabras clave>"] \
     [--hotfix <clave>] [--deuda <CLAVE de la historia>]
   ```

   El título de una Tarea o un Spike empieza con un verbo en infinitivo ("Agregar…", "Evaluar…").
3. **Leer el contexto** (`…-contexto.md`): hallazgos, AS IS, decisiones, terceros y Sonar.
   Preguntar si alguna incidencia de Jira ya cubre lo mismo.
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
