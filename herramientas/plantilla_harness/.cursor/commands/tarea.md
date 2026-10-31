# /tarea

Crear en Jira una Tarea de desarrollo que cuelga de una historia. Uso: `/tarea <HISTORIA> [--titulo "<qué parte>"]`.
Una historia puede tener varias Tareas. Es opcional: la Tarea también se puede crear a mano. Es el único comando del harness que escribe en Jira.

1. **Vista previa:**

   ```sh
   python3 herramientas/hdu.py tarea <HISTORIA> [--titulo "<qué parte>"]
   ```

   Se detiene si la incidencia no es una historia o si su Medición HU no es aceptada.

2. Mostrar el título, los campos y las Tareas que ya cuelgan de la historia, para no duplicar trabajo, y pedir
   confirmación.

3. **Crear:**

   ```sh
   python3 herramientas/hdu.py tarea <HISTORIA> [--titulo "<qué parte>"] --confirmar
   ```

   Crea la Tarea con el campo Tipo en `Producto`, Equipos según `config.json`, colgando de la historia.

4. Seguir con `/hdu <TAREA>`.
