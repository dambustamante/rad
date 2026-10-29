# /actualizar

Deja `radiografia` al día: herramientas, documentos de arquitectura, su índice y la coherencia
de las decisiones del equipo (ADR-EQ) con arquitectura.

Uso: `/actualizar`, o `/actualizar fuentes` para agregar o retirar repositorios de arquitectura (ver
"Fuentes de arquitectura"). Si `harness.yaml` no tiene fuentes, empezar por esa sección.

## Pasos

1. **Parte automática.** Ejecutar:

   ```sh
   make actualizar
   ```

   Si falla en el paso de herramientas (`doctor`), informar qué falta y cómo instalarlo, y
   detenerse. Si la sincronización informa errores, informarlos y continuar con lo disponible.

2. **Coherencia.** La salida tiene una sección por ámbito: `[equipo]` (ADR-EQ frente a arquitectura)
   y `[<producto>]` (ADR de producto frente a arquitectura y a los ADR-EQ, que aparecen como
   `equipo:ADR-EQ-NNN`). Para cada ámbito que liste pares por evaluar, hacer la evaluación en dos
   etapas, siempre con `--ambito <ámbito>` en los comandos. Si todos dicen "Coherencia al día", pasar
   al paso 3.

   **Etapa A: filtro por tema.** Con los títulos y reglas rápidas que muestra la salida, decidir
   para cada par si ambos documentos tratan el mismo tema. Los pares sin relación temática se
   registran sin leer más:

   ```sh
   .venv/bin/python herramientas/coherencia.py registrar --ambito <ámbito> --decision <ADR-XX-NNN> --doc <clave> --relacion sin_relacion
   ```

   Ante la duda, no marcar `sin_relacion`: pasar el par a la etapa B.

   **Etapa B: comparación.** Para cada par relacionado, leer los extractos:

   ```sh
   .venv/bin/python herramientas/coherencia.py extracto <ADR-XX-NNN> --ambito <ámbito>
   .venv/bin/python herramientas/coherencia.py extracto <clave del documento> --ambito <ámbito>
   ```

   Leer el documento completo solo si el extracto no alcanza para decidir. Clasificar:

   - `compatible`: tratan el tema sin contradecirse; el ADR-EQ agrega detalle o exige más.
   - `duplica`: el ADR-EQ repite lo que arquitectura ya decide.
   - `choca`: el ADR-EQ contradice o exige menos que arquitectura.

   Registrar el resultado:

   ```sh
   .venv/bin/python herramientas/coherencia.py registrar --ambito <ámbito> --decision <ADR-XX-NNN> --doc <clave> --relacion <relacion> \
     --cita-documento "<texto copiado tal cual del documento de referencia>" \
     --cita-decision "<texto copiado tal cual de la decisión evaluada>" \
     --explicacion "<por qué>" [--criterios XX-NNN.N,...]
   ```

   - `duplica` y `choca` exigen las dos citas, copiadas textualmente; el script rechaza citas que
     no existen en el documento. Si rechaza una cita, copiarla de nuevo desde el documento, nunca
     reformularla.
   - `choca` exige `--criterios` con los criterios del ADR-EQ que quedan suspendidos: solo los
     afectados, no todos.
   - Para `compatible`, agregar `--explicacion` en una frase.

   Al terminar, ejecutar `make coherencia` para regenerar `equipo/COHERENCIA.md` y
   `productos/<producto>/decisiones/COHERENCIA.md`, y confirmar que no
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

## Fuentes de arquitectura

Los repositorios de donde se descargan los ADR, estándares y referencias. Nunca editar
`harness.yaml` a mano: siempre con `herramientas/fuentes_arquitectura.py`.

1. **Mostrar** `.venv/bin/python herramientas/fuentes_arquitectura.py listar` (`id`, `url`, `ref`,
   `ruta`, `tipo`) y preguntar: agregar, retirar o nada.
2. **Agregar.** Pedir los repositorios, uno por línea (URL SSH o HTTPS de GitLab o GitHub, o ruta de
   una carpeta local con un repositorio git), e inspeccionar cada uno:

   ```sh
   .venv/bin/python herramientas/fuentes_arquitectura.py inspeccionar "<url>"
   ```

   Si falla por acceso, informar y seguir con los demás. Proponer las fuentes en una tabla
   (`#`, `id`, `url`, `ref`, `ruta`, `tipo`, documentos, motivo); un repositorio puede dar varias:
   - `ref`: la `rama_por_defecto` informada.
   - `tipo: adr` con la `ruta_adr_sugerida`, si existe.
   - `tipo: estandar` o `referencia`: carpetas con documentos que no son ADR (`adr: 0`); no la raíz
     si solo tiene un README.
   - `estado_por_defecto: vigente`: solo para estándares o referencias sin sección Estado
     (`con_estado: 0`), explicando que eso los considera vigentes.
   - `id`: minúsculas y guiones (`decision-records`, `estandares-desarrollo`).

   Con la confirmación del usuario, agregar cada fila:

   ```sh
   .venv/bin/python herramientas/fuentes_arquitectura.py agregar --id <id> --url "<url>" --ref <ref> --ruta <ruta> --tipo <tipo> [--estado-por-defecto vigente]
   ```

3. **Retirar**, con confirmación: `.venv/bin/python herramientas/fuentes_arquitectura.py retirar --id <id>`.
4. Mostrar la tabla final y seguir con los pasos de arriba para descargar los documentos.

No inventar repositorios, rutas ni refs: solo los que el usuario indica y la inspección confirma.

## Correcciones del usuario

Si el usuario indica que un resultado es incorrecto, registrar de nuevo el par con la relación que
indica y `--manual "<motivo del usuario>"`. Un choque no se acepta: se resuelve ajustando el ADR-EQ
o con una corrección manual justificada.

## Reglas

- No editar nada en `arquitectura/`, ni los `COHERENCIA.md`, `INDICE.md` o carpetas `estado/`.
- No proponer cambios a los documentos de arquitectura: arquitectura prevalece. Las
  recomendaciones son siempre sobre los ADR-EQ.
