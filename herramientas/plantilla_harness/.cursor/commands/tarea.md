# /tarea

Generar la spec de las Tareas creadas a mano que cuelgan de una historia. Uso: `/tarea <HISTORIA>`. No escribe en Jira. Lo
normal es que `/hdu` proponga y cree las Tareas: este comando es para las que no vinieron de esa propuesta, incluidas las
que se agreguen después.

1. **Generar:**

   ```sh
   python3 herramientas/hdu.py tarea <HISTORIA> [--sin-rama]
   ```

   Lee las Tareas que cuelgan de la historia y escribe `specs/<HISTORIA>/<TAREA>.md` para las que no tienen spec. Se detiene
   si la incidencia no es una historia, si su Medición HU no es aceptada o si no hay Tareas colgando.

2. **Completar cada spec** como en el paso 5 de `/hdu`. En una Tarea sin fila en la propuesta, dejar solo los criterios que
   cubre y sus repositorios.

3. **Validar** con `python3 herramientas/hdu.py spec <HISTORIA>`, hacer commit en la rama `docs/<HISTORIA>-tareas`, hacer
   push y abrir el MR en GitLab.
