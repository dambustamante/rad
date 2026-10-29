# /historia

Crea una Tarea, un Spike o un Bug del equipo Back con la estructura de ADR-EQ-008, a partir de la
información del producto, y la crea en Jira solo con confirmación del usuario.

Uso:

- `/historia <producto>`: preguntar qué se necesita.
- `/historia <producto> --desde H-0041,H-0052`: una Tarea de Deuda Técnica a partir de hallazgos
  (por ejemplo, los marcados como Deuda en `/triar`).
- `/historia <producto> --spike`: un Spike.

## Tipos

| Tipo de incidencia | Campo Tipo | Cuándo |
|---|---|---|
| Tarea | Deuda Técnica | Corregir o mejorar código o arquitectura |
| Tarea | Deuda Operativa | Eliminar trabajo manual por falta de un backoffice |
| Bug | Bau/Incidentes | Corregir algo que falla en producción |
| Spike | Spike | Investigar para decidir (2 días como máximo) |

## Pasos

1. **Entender el pedido.** Si no se indicó el tipo, preguntarlo primero. Después hacer las preguntas
   de ese tipo, de a una o todas juntas, y no inventar respuestas: lo que el usuario no sepa queda
   `NO DETERMINADO`.

   **Spike** (`--spike`):

   1. ¿Qué hay que decidir? Una sola pregunta concreta (por ejemplo, "¿Kafka o RabbitMQ para los
      eventos de evaluación?"). De ahí sale el título: "Evaluar… para decidir…".
   2. ¿Por qué hay que decidirlo ahora? Qué trabajo o historia queda bloqueado.
   3. ¿Qué opciones se conocen de entrada?
   4. ¿Qué pesa más al decidir? Para ordenar los criterios: cumplimiento de ADR, latencia, costo,
      operación, soporte del proveedor…
   5. ¿Qué repositorios o integraciones toca?

   No preguntar la duración máxima (2 días), el entregable (ADR de producto en Propuesto) ni los
   criterios de aceptación fijos: ya vienen en la plantilla.

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

   **Tarea de Deuda Técnica:**

   - Con `--desde`, el contexto sale de los hallazgos: solo preguntar si conviene agrupar otros
     hallazgos abiertos del mismo tema (el contexto los lista en "Otros hallazgos abiertos
     relacionados") y confirmar el título.
   - Sin `--desde`: qué hay que corregir o mejorar, dónde, qué problema causa hoy y qué evidencia hay.

   En todos los casos, pedir unas palabras clave del tema si no surgen de las respuestas: sirven para
   buscar en la documentación del proveedor y en Jira.

2. **Crear el borrador y el contexto:**

   ```sh
   .venv/bin/python herramientas/historia.py nueva <producto> --tipo <tarea|spike|bug> --titulo "<título>" \
     [--categoria "Deuda Operativa"] [--desde H-0041,H-0052] [--repos <repo1,repo2>] [--tema "<palabras clave>"]
   ```

   El título de una Tarea o un Spike empieza con un verbo en infinitivo ("Agregar…", "Evaluar…").

3. **Leer el contexto** (`…-contexto.md`): hallazgos de origen y relacionados, AS IS de los
   repositorios, decisiones que pueden aplicar, integraciones, documentación del proveedor y de
   terceros, historias parecidas de Jira y Sonar. Si una historia de Jira ya cubre lo mismo,
   avisar al usuario antes de seguir.

4. **Redactar el borrador** (`productos/<producto>/historias/borradores/<NNN>-<título>.md`) con la
   plantilla ya cargada:

   - **Como**: un rol real; nunca "sistema". **Para**: el valor, sin repetir el Quiero.
   - **Criterios de aceptación**: al menos uno propio y medible, más los fijos de su tipo, que ya
     vienen en la plantilla.
   - Las secciones de su tipo, con evidencia del contexto (hallazgos, `archivo:línea`, métricas).
     Lo que no se sepa se marca `NO DETERMINADO`; no se inventa.
   - Solo las decisiones que el trabajo debe respetar, con su regla rápida.
   - Lenguaje técnico y claro, comprensible para cualquier seniority, sin adornos ni muletillas
     (`equipo/lenguaje.yaml`).

5. **Validar:**

   ```sh
   .venv/bin/python herramientas/historia.py validar <producto> <borrador>
   ```

   Corregir hasta que no haya errores.

6. **Vista previa.** Ejecutar sin `--confirmar` y mostrar al usuario el título, el proyecto, el tipo y
   el texto completo:

   ```sh
   .venv/bin/python herramientas/historia.py crear <producto> <borrador>
   ```

7. **Crear en Jira**, solo si el usuario lo confirma explícitamente:

   ```sh
   .venv/bin/python herramientas/historia.py crear <producto> <borrador> --confirmar
   ```

   La clave queda en el borrador y, si nació de hallazgos, en cada hallazgo.

## Reglas

- Nunca crear en Jira sin la confirmación explícita del usuario sobre la vista previa.
- No crear historias de tipo Producto u Otros.
- No editar el encabezado YAML del borrador salvo para corregir el Tipo o los repositorios.
- El proyecto de destino es el configurado en las historias del producto (`historias.proyecto` o la consulta
  JQL (Jira Query Language)); si falta, configurarlo con `productos.py historias <producto> ... --proyecto <CLAVE>`.
