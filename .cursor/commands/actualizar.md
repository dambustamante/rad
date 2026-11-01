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

2. **Coherencia.** Si todos los ámbitos dicen "Coherencia al día", pasar al paso 3. Si no, leer y seguir
   `.cursor/partes/actualizar-coherencia.md`.

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

## Reglas

- No editar nada en `arquitectura/`, ni los `COHERENCIA.md`, `INDICE.md` o carpetas `estado/`.
- No proponer cambios a los documentos de arquitectura: arquitectura prevalece. Las
  recomendaciones son siempre sobre los ADR-EQ.
