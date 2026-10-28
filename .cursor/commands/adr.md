# /adr

Crea o administra los ADR de un producto: reglas propias (`decision`), propuestas que nacen de
hallazgos (`mejora`) y apartamientos formales de una regla (`excepcion`).
Uso: `/adr <producto>`, `/adr <producto> --desde H-0041,H-0052` para una mejora a partir de hallazgos,
o `/adr <producto> --desde-historias` para proponer ADR a partir de las historias de usuario.

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

## Desde historias de usuario (`--desde-historias`)

Las historias no generan un ADR cada una: la mayoría no implica una decisión de arquitectura. Se
usan para **proponer** decisiones a partir de requisitos no funcionales, restricciones y Spikes.

1. **Sincronizar** (solo lectura; si el producto no tiene fuente, ofrecer configurarla, ver abajo):

   ```sh
   .venv/bin/python herramientas/historias.py sincronizar <producto>
   ```

2. **Candidatas.** El script ya filtró sin IA: todas las de tipo Spike y Deuda Técnica, y las demás
   solo si tienen señales (tiempos, disponibilidad, retención, seguridad, resiliencia…):

   ```sh
   .venv/bin/python herramientas/historias.py candidatas <producto>
   ```

3. **Clasificar en un solo lote**, `productos/<producto>/historias/clasificacion-lote.yaml`:

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

   ```sh
   .venv/bin/python herramientas/historias.py clasificar <producto>
   ```

   Las citas se validan contra el texto de la historia y del documento. Si hay errores no se
   registra nada. Una historia analizada no se vuelve a pedir mientras no cambie.

4. **Proponer.** Mostrar `historias.py propuestas <producto>` (candidatas agrupadas por tema) y, para
   cada tema, proponer un ADR de tipo `decision`. Crear solo los que el usuario elija:

   ```sh
   .venv/bin/python herramientas/adr.py nuevo <producto> --tipo decision --titulo "<título>" --historias FRAUD-123,FRAUD-130
   ```

   Completar el ADR con el usuario (paso 3 de arriba). Los choques se informan aparte: son temas
   para conversar, no ADR.

**Configurar la fuente** (una sola vez por producto):

```sh
.venv/bin/python herramientas/productos.py historias <producto> --fuente jira --jql "project = FRAUD AND labels = motor-fraudes" --campo-tipo Tipo
.venv/bin/python herramientas/productos.py historias <producto> --fuente archivo --archivo export.csv --campo-tipo Tipo
.venv/bin/python herramientas/productos.py historias <producto> --fuente ninguna
```

Preferir `--jql` a `--tablero`: sigue funcionando aunque el tablero se haya eliminado. Si el proyecto
está archivado en Jira, exportar sus historias a CSV y usar `--fuente archivo`.

**Cuando una historia de origen cambia o se retira**, el ADR aparece en `listar` con
"revisar: …". Ver el antes y después en `historias/INDICE.md` y decidir con el usuario: si el ADR
sigue vigente, `historias.py confirmar <producto> --adr <ADR>`; si no, ajustarlo (si está Propuesto)
o reemplazarlo por uno nuevo (si está Aprobado).

## Efectos en /revisar

- Los criterios de una `decision` en estado Propuesto o Aprobado se evalúan en el nivel 3 (en modo
  `propuesta` mientras está Propuesto).
- Una `excepcion` Aprobada y vigente deja sus criterios como NO APLICA en los repositorios de su
  alcance. Al vencer, se vuelven a evaluar.
- Una `mejora` no se evalúa: es una propuesta. Si se adopta, se crea una `decision` que la
  materializa.
