# /arquitectura

Administra los repositorios de donde se descargan los documentos de arquitectura (ADR,
estándares y referencias). Permite agregar fuentes nuevas y retirar las existentes.

La parte determinista la hace `herramientas/fuentes_arquitectura.py`. Nunca editar
`harness.yaml` a mano en este comando: siempre mediante el script.

## Pasos

1. **Mostrar lo que hay.** Ejecutar:

   ```sh
   .venv/bin/python herramientas/fuentes_arquitectura.py listar
   ```

   Mostrar las fuentes en una tabla (`id`, `url`, `ref`, `ruta`, `tipo`). Si no hay, decirlo.

2. **Preguntar qué hacer:** agregar fuentes, retirar una fuente o nada.

3. **Para agregar**, pedir al usuario los repositorios, uno por línea. Se aceptan:

   - URL SSH o HTTPS de GitLab o GitHub (`git@gitlab.com:grupo/proyecto.git`);
   - ruta de una carpeta local con un repositorio git (`~/arquitectura/adrs`).

4. **Inspeccionar cada repositorio:**

   ```sh
   .venv/bin/python herramientas/fuentes_arquitectura.py inspeccionar "<url>"
   ```

   Si falla por acceso, informar el error y seguir con los demás.

5. **Proponer las fuentes** a partir de la inspección. Un mismo repositorio puede generar varias
   fuentes (por ejemplo, una para ADR y otra para estándares). Mostrar una tabla:

   | # | id | url | ref | ruta | tipo | Documentos | Motivo de la propuesta |
   |---|---|---|---|---|---|---|---|

   Criterios para proponer:

   - `ref`: la `rama_por_defecto` informada.
   - `tipo: adr` y `ruta`: la `ruta_adr_sugerida`, si existe.
   - `tipo: estandar` o `referencia`: carpetas con documentos que no son ADR (`adr: 0`). No
     proponer la raíz del repositorio si solo contiene un README.
   - `estado_por_defecto: vigente`: proponerlo solo para fuentes de estándares o referencias cuyos
     documentos no tienen sección Estado (`con_estado: 0`), y explicar que eso los considera
     vigentes.
   - `id`: minúsculas y guiones, derivado del nombre del repositorio y del contenido (por ejemplo
     `decision-records`, `estandares-desarrollo`).

   Pedir al usuario que confirme o corrija cada fila. No agregar nada sin confirmación.

6. **Agregar las fuentes confirmadas**, una por una:

   ```sh
   .venv/bin/python herramientas/fuentes_arquitectura.py agregar --id <id> --url "<url>" --ref <ref> --ruta <ruta> --tipo <tipo> [--estado-por-defecto vigente]
   ```

   Si el script rechaza una fuente, mostrar el motivo y pedir la corrección.

7. **Para retirar**, confirmar con el usuario y ejecutar:

   ```sh
   .venv/bin/python herramientas/fuentes_arquitectura.py retirar --id <id>
   ```

8. **Cerrar** mostrando la tabla final de fuentes y ofreciendo ejecutar `/actualizar` para
   descargar los documentos y generar el índice.

## Reglas

- No inventar repositorios, rutas ni refs: solo los que el usuario indica y la inspección confirma.
- No mostrar tokens ni credenciales; el acceso usa la configuración de git del usuario.
