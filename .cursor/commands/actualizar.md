# /actualizar

Deja `radiografia` al día: herramientas, documentos de arquitectura, su índice y la coherencia
de las decisiones del equipo (ADR-EQ) con arquitectura.

## Pasos

1. **Parte automática.** Ejecutar:

   ```sh
   make actualizar
   ```

   Si falla en el paso de herramientas (`doctor`), informar qué falta y cómo instalarlo, y
   detenerse. Si la sincronización informa errores, informarlos y continuar con lo disponible.

2. **Coherencia.** Si la salida dice "Coherencia al día" o que no hay documentos vigentes, pasar
   al paso 3. Si lista pares por evaluar, hacer la evaluación en dos etapas.

   **Etapa A: filtro por tema.** Con los títulos y reglas rápidas que muestra la salida, decidir
   para cada par si ambos documentos tratan el mismo tema. Los pares sin relación temática se
   registran sin leer más:

   ```sh
   .venv/bin/python herramientas/coherencia.py registrar --eq <ADR-EQ-NNN> --doc <fuente:ID> --relacion sin_relacion
   ```

   Ante la duda, no marcar `sin_relacion`: pasar el par a la etapa B.

   **Etapa B: comparación.** Para cada par relacionado, leer los extractos:

   ```sh
   .venv/bin/python herramientas/coherencia.py extracto <ADR-EQ-NNN>
   .venv/bin/python herramientas/coherencia.py extracto <fuente:ID>
   ```

   Leer el documento completo solo si el extracto no alcanza para decidir. Clasificar:

   - `compatible`: tratan el tema sin contradecirse; el ADR-EQ agrega detalle o exige más.
   - `duplica`: el ADR-EQ repite lo que arquitectura ya decide.
   - `choca`: el ADR-EQ contradice o exige menos que arquitectura.

   Registrar el resultado:

   ```sh
   .venv/bin/python herramientas/coherencia.py registrar --eq <ADR-EQ-NNN> --doc <fuente:ID> --relacion <relacion> \
     --cita-arquitectura "<texto copiado tal cual>" --cita-equipo "<texto copiado tal cual>" \
     --explicacion "<por qué>" [--criterios EQ-NNN.N,...]
   ```

   - `duplica` y `choca` exigen las dos citas, copiadas textualmente; el script rechaza citas que
     no existen en el documento. Si rechaza una cita, copiarla de nuevo desde el documento, nunca
     reformularla.
   - `choca` exige `--criterios` con los criterios del ADR-EQ que quedan suspendidos: solo los
     afectados, no todos.
   - Para `compatible`, agregar `--explicacion` en una frase.

   Al terminar, ejecutar `make coherencia` para regenerar `equipo/COHERENCIA.md` y confirmar que no
   quedan pares pendientes.

3. **Responder** con este formato:

   ```markdown
   ## Resultado de /actualizar

   **Entorno:** <OK, o lista de avisos relevantes>
   **Arquitectura:** <N documentos: X vigentes, Y pendientes, Z no vigentes, W NO DETERMINADO>

   ### Cambios desde la sincronización anterior
   <fuentes con commits nuevos, documentos nuevos, modificados, eliminados y cambios de vigencia;
   o "Sin cambios">

   ### Coherencia de las decisiones del equipo
   <tabla de COHERENCIA.md: ADR-EQ, resultado y criterios suspendidos; detalle de cada choque y
   duplicación con su recomendación>

   ### Requiere atención
   <documentos NO DETERMINADO con su motivo y la acción sugerida; errores de sincronización>
   ```

4. Para cada documento `NO DETERMINADO` por un estado desconocido, sugerir agregar ese valor a la
   lista que corresponda en `arquitectura.estados` de `harness.yaml`. No modificar `harness.yaml`
   sin confirmación del usuario.

## Correcciones del usuario

Si el usuario indica que un resultado es incorrecto, registrar de nuevo el par con la relación que
indica y `--manual "<motivo del usuario>"`. Un choque no se acepta: se resuelve ajustando el ADR-EQ
o con una corrección manual justificada.

## Reglas

- No editar nada en `arquitectura/`, ni `equipo/COHERENCIA.md` ni `equipo/coherencia.json`.
- No proponer cambios a los documentos de arquitectura: arquitectura prevalece. Las
  recomendaciones son siempre sobre los ADR-EQ.
- Si `harness.yaml` no tiene fuentes, sugerir ejecutar `/arquitectura`.
