# /crear: ADR y excepciones

Para una decisión del equipo (`/crear equipo adr`): crearla con
`.venv/bin/python herramientas/adr.py nuevo equipo --tipo decision --titulo "<título>"` y seguir desde el
paso 3; sus criterios pueden ser `automática` o `revisión de código`.

Si el producto tiene harness, sus ADR viven en `productos/<producto>/harness/decisiones/` (la copia local
de `harness-<producto>`): los comandos de abajo escriben ahí. Al terminar, guardar en el harness con
`.venv/bin/python herramientas/harness.py guardar <producto> --mensaje "<ADR y qué cambió>"`; el push y el MR
los hace el usuario. Un ADR de producto lo aprueban un par dev y el TL por MR al harness.

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

Efectos en `/revisar`: los criterios de una `decision` Propuesta o Aprobada se evalúan en el nivel 4
(en modo `propuesta` mientras está Propuesta). Una `excepcion` Aprobada y vigente deja sus criterios
como NO APLICA en su alcance hasta que vence.
