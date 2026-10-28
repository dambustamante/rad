# /adr

Crea o administra los ADR de un producto: reglas propias (`decision`), propuestas que nacen de
hallazgos (`mejora`) y apartamientos formales de una regla (`excepcion`).
Uso: `/adr <producto>`, o `/adr <producto> --desde H-0041,H-0052` para una mejora a partir de hallazgos.

La parte determinista la hace `herramientas/adr.py`. Los ADR viven en
`productos/<producto>/decisiones/` y siguen el formato de los ADR de arquitectura.

## Pasos

1. **Mostrar lo que hay:**

   ```sh
   .venv/bin/python herramientas/adr.py listar <producto>
   ```

   Mostrar la tabla (ADR, tipo, estado, vencimiento y efecto) y preguntar qué hacer: crear un ADR,
   completar o aprobar uno existente, o nada. Destacar las excepciones vencidas o inactivas.

2. **Crear un ADR.** Preguntar el tipo y el título y ejecutar:

   ```sh
   .venv/bin/python herramientas/adr.py nuevo <producto> --tipo <decision|mejora|excepcion> --titulo "<título>" [--desde H-0001,H-0002]
   ```

   Si el producto no tiene sigla, el script lo informa: proponer una y asignarla con
   `.venv/bin/python herramientas/productos.py sigla <producto> --asignar <SIGLA>`.

3. **Completar el ADR con el usuario**, sección por sección, en español neutro y técnico:

   - **decision:** contexto, decisión verificable, regla rápida y criterios `XX-NNN.N` con su
     severidad. Todos los criterios son de `revisión de código`.
   - **mejora:** a partir de los hallazgos de origen (ya están en la tabla del contexto), leer su
     evidencia en las fichas y en el código, y proponer la decisión, las alternativas y el impacto.
   - **excepcion:** qué criterios se exceptúan (`EQ-001.1`, `MF-002.1` o `fuente:ID` de
     arquitectura), en qué repositorios, por qué, hasta cuándo y qué se hará para dejar de
     necesitarla. Si exceptúa arquitectura, pedir la referencia de aprobación de arquitectura; sin
     ella, la excepción queda inactiva.

   No inventar datos: lo que el usuario no sepa se marca `NO DETERMINADO - motivo`.

4. **Validar:**

   ```sh
   .venv/bin/python herramientas/adr.py validar <producto> --id <ADR>
   ```

   Corregir los errores. Los avisos se informan al usuario.

5. **Coherencia** (solo `decision`): ejecutar `/actualizar` para comparar la decisión con
   arquitectura y con las decisiones del equipo. Una decisión del producto nunca relaja ni contradice
   lo que tiene más autoridad.

6. **Aprobar**, solo cuando el usuario lo indique: cambiar el estado a `Aprobado` y completar la fecha
   de aprobación. Una `decision` solo se aprueba si `decisiones/COHERENCIA.md` no muestra choques ni
   pares pendientes. Volver a ejecutar `listar` para actualizar el índice.

## Efectos en /revisar

- Los criterios de una `decision` en estado Propuesto o Aprobado se evalúan en el nivel 3 (en modo
  `propuesta` mientras está Propuesto).
- Una `excepcion` Aprobada y vigente deja sus criterios como NO APLICA en los repositorios de su
  alcance. Al vencer, se vuelven a evaluar.
- Una `mejora` no se evalúa: es una propuesta. Si se adopta, se crea una `decision` que la
  materializa.
