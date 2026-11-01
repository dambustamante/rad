# /hdu: historia

1. **Proponer las Tareas.** Si `tomar` mostró Tareas que ya cuelgan de la historia y se quieren usar esas, dejar la propuesta sin
   filas propias y pasar al paso 2. Si no, leer la historia y el código relacionado, y escribir la propuesta en
   `specs/<HISTORIA>/propuesta.md`, sin esperar a que la pidan:
   - **Preguntas para refinar:** criterios ambiguos o faltantes. La historia no se edita en Jira: se preguntan. Si no hay,
     escribir `Ninguna`.
   - **Tareas propuestas:** una fila por Tarea, con título en infinitivo, números de los criterios que cubre y repositorios.
     Entre todas deben cubrir todos los criterios.

   Si la historia implica una decisión de diseño duradera, proponer también un ADR con
   `python3 herramientas/harness.py adr --titulo "<decisión>" --historia <HISTORIA>`.

   Mostrarla y aceptar cambios.

2. **Crear las Tareas.**

   ```sh
   python3 herramientas/hdu.py crear-tareas <HISTORIA>
   ```

   Muestra la vista previa de las Tareas por crear y de las que ya cuelgan de la historia. Una Tarea que ya existe con el
   mismo título no se duplica. Pedir confirmación y crearlas:

   ```sh
   python3 herramientas/hdu.py crear-tareas <HISTORIA> --confirmar
   ```

   Crea cada Tarea con el campo Tipo en `Producto`, Equipos según `config.json`, colgando de la historia, y escribe
   `specs/<HISTORIA>/<TAREA>.md`. Si se rechaza la propuesta o el token no puede crear incidencias, no crear nada: las
   Tareas se crean a mano en Jira, colgando de la historia.

3. **Completar cada spec** (una página como máximo; todavía no se programa): objetivo, diseño por repositorio
   citando `archivo:línea`, una prueba por criterio, reglas que aplican con la sección citada, y lo que queda fuera de
   alcance. Validar:

   ```sh
   python3 herramientas/hdu.py spec <HISTORIA>
   ```

   Exige la propuesta y todas las specs completas, y que entre todas las Tareas se cubran todos los criterios. Si es válido,
   hacer commit en la rama `docs/<HISTORIA>-tareas`, hacer push y abrir el MR en GitLab. Al integrarse, las specs quedan
   aprobadas. Seguir con `/desarrollar <TAREA>`.

Al terminar, sugerir un chat nuevo para `/desarrollar`: la spec ya tiene lo necesario.
