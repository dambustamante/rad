# /tarea

Crear en Jira las Tareas propuestas de una historia y una spec por cada Tarea. Uso: `/tarea <HISTORIA>`, después de `/hdu`.
Es el único comando del harness que escribe en Jira.

1. **Vista previa:**

   ```sh
   python3 herramientas/hdu.py tarea <HISTORIA>
   ```

   Muestra las Tareas por crear y las que ya cuelgan de la historia. Una Tarea creada a mano se reconoce por colgar de la
   historia: si su título coincide con una fila de la propuesta, no se duplica.

2. Si hay Tareas por crear, mostrarlas y pedir confirmación. **Crear:**

   ```sh
   python3 herramientas/hdu.py tarea <HISTORIA> --confirmar
   ```

   Crea cada Tarea con el campo Tipo en `Producto`, Equipos según `config.json`, colgando de la historia, y escribe
   `specs/<HISTORIA>/<TAREA>.md`. Sin Tareas por crear, escribe las specs que falten y no toca Jira.

3. **Completar cada spec** (una página como máximo; todavía no se programa): objetivo, diseño por repositorio citando
   `archivo:línea`, una prueba por criterio, reglas que aplican con la sección citada, y lo que queda fuera de alcance. En una
   Tarea creada a mano, dejar solo los criterios que cubre y sus repositorios.

4. **Validar:**

   ```sh
   python3 herramientas/hdu.py spec <HISTORIA>
   ```

   Exige la propuesta y todas las specs completas, y que entre todas las Tareas se cubran todos los criterios.

5. **MR de las Tareas:** hacer commit en la rama `docs/<HISTORIA>-tareas`, hacer push y abrir el MR en GitLab. Al integrarse,
   las specs quedan aprobadas. Seguir con `/desarrollar <TAREA>`.
