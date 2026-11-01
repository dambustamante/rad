# /actualizar

Deja `radiografia` al día: herramientas, documentos de arquitectura, su índice y la coherencia
de las decisiones del equipo (ADR-EQ) con arquitectura.

Uso: `/actualizar`. Si `harness.yaml` no tiene fuentes, o si se pide agregar o retirar un repositorio de
arquitectura, leer y seguir primero `.cursor/partes/actualizar-fuentes.md`.

## Pasos

1. **Parte automática.** Ejecutar:

   ```sh
   make actualizar
   ```

   Si falla en el paso de herramientas (`doctor`), informar qué falta y cómo instalarlo, y
   detenerse. Si la sincronización informa errores, informarlos y continuar con lo disponible.
   Si algún harness de producto tuvo cambios generados, el commit es local: se suben en el paso 3.

2. **Coherencia.** La salida tiene una sección por ámbito: `[equipo]` (ADR-EQ frente a arquitectura)
   y `[<producto>]` (ADR de producto frente a arquitectura y a los ADR-EQ, que aparecen como
   `equipo:ADR-EQ-NNN`). Si todos dicen "Coherencia al día", pasar al paso 3. Si no, para cada ámbito
   con pares por evaluar, escribir **un solo lote** en `.cache/coherencia-<ámbito>.yaml` y registrarlo
   con un comando:

   ```yaml
   ambito: equipo                       # o el nombre del producto
   pares:
     - {decision: ADR-EQ-002, doc: decision-records:ADR-011, relacion: sin_relacion}
     - decision: ADR-EQ-003
       doc: decision-records:ADR-012
       relacion: compatible
       explicacion: El ADR-EQ agrega los campos obligatorios que arquitectura no detalla.
     - decision: ADR-EQ-002
       doc: decision-records:ADR-010
       relacion: choca
       cita_documento: Los reintentos se configuran solo en el API Gateway
       cita_decision: Los reintentos se aplican en cada cliente HTTP
       criterios: [EQ-002.2]
       explicacion: Arquitectura centraliza los reintentos en el gateway.
   ```

   ```sh
   .venv/bin/python herramientas/coherencia.py lote .cache/coherencia-<ámbito>.yaml
   ```

   Cómo decidir cada par, en dos etapas:

   - **Etapa A, filtro por tema.** Con los títulos y reglas rápidas que muestra la salida, decidir si
     ambos documentos tratan el mismo tema. Los que no, van como `sin_relacion` sin leer más. Ante la
     duda, pasar a la etapa B.
   - **Etapa B, comparación.** Leer los extractos con
     `.venv/bin/python herramientas/coherencia.py extracto <ID> --ambito <ámbito>` (decisión y
     documento), y el documento completo solo si no alcanza. Clasificar:
     - `compatible`: tratan el tema sin contradecirse; la decisión agrega detalle o exige más. Lleva
       una explicación en una frase.
     - `duplica`: la decisión repite lo que arquitectura ya decide.
     - `choca`: la decisión contradice o exige menos que arquitectura. Lleva `criterios`: solo los
       criterios afectados, que quedan suspendidos.

     `duplica` y `choca` exigen las dos citas, copiadas textualmente, y la explicación.

   El lote se registra todo o nada: si una cita no aparece en el documento, no se registra nada y se
   listan todos los errores. Copiar la cita de nuevo desde el documento, nunca reformularla. Al
   registrar, el script regenera el `COHERENCIA.md` del ámbito e informa los pares que quedan.

3. **Subir los harness.** Ejecutar `.venv/bin/python herramientas/harness.py subir` (vista previa). Con la
   confirmación del usuario, repetir con `--confirmar`. Un harness con coherencia pendiente queda retenido.

4. **Responder** con este formato:

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
   <documentos NO DETERMINADO con su motivo y la acción sugerida; documentos vigentes sin regla rápida;
   errores de sincronización>
   ```

5. Para cada documento `NO DETERMINADO` por un estado desconocido, sugerir agregar ese valor a la
   lista que corresponda en `arquitectura.estados` de `harness.yaml`. No modificar `harness.yaml`
   sin confirmación del usuario.

## Correcciones del usuario

Si el usuario indica que un resultado es incorrecto, registrar de nuevo el par (en un lote o con
`coherencia.py registrar`) con la relación que indica y `manual: "<motivo del usuario>"`. Un choque
no se acepta: se resuelve ajustando el ADR-EQ o con una corrección manual justificada.

## Reglas

- No editar nada en `arquitectura/`, ni los `COHERENCIA.md`, `INDICE.md` o carpetas `estado/`.
- No proponer cambios a los documentos de arquitectura: arquitectura prevalece. Las
  recomendaciones son siempre sobre los ADR-EQ.
