# /actualizar fuentes

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
