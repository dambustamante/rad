# /tarea

Crear en Jira la Tarea de desarrollo de una historia. Uso: `/tarea <HISTORIA>`. Es opcional: la Tarea también se puede
crear a mano. Es el único comando del harness que escribe en Jira.

1. **Vista previa:**

   ```sh
   python3 herramientas/hdu.py tarea <HISTORIA>
   ```

   Se detiene si la incidencia no es una historia, si su Medición HU no es aceptada o si ya tiene Tarea.

2. Mostrar el título y los campos, y pedir confirmación.

3. **Crear:**

   ```sh
   python3 herramientas/hdu.py tarea <HISTORIA> --confirmar
   ```

   Crea la Tarea con el campo Tipo en `Producto`, Equipos según `config.json`, y la enlaza a la historia. Si el enlace
   falla, indicar la clave creada para enlazarla a mano.

4. Seguir con `/hdu <TAREA>`.
