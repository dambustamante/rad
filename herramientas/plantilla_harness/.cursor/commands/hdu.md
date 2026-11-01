# /hdu

Refinar una historia de Jira, proponer sus Tareas y, con confirmación, crearlas. Uso: `/hdu <HISTORIA>`, por ejemplo `/hdu FRAUD-123`. También toma
un Error, un Hotfix, un Spike o una Tarea sin historia. No crea ramas de código ni se programa todavía. Es el único comando del harness que escribe en Jira.

1. **Tomar:**

   ```sh
   python3 herramientas/hdu.py tomar <CLAVE> [--repos a,b]
   ```

   Actualiza primero el harness. Si no puede, se detiene: mostrar el motivo y no seguir con reglas viejas.

   | Salida | Qué significa | Qué hacer |
   |---|---|---|
   | 2 | La Medición HU no es una de las aceptadas | Mostrar el motivo y sugerir qué completar. No seguir |
   | 3 | Sin repositorios (incidencia sin historia) | Preguntar cuáles toca y repetir con `--repos` |
   | 4 | Es una Tarea que cuelga de una historia | Indicar que se refina con `/hdu <HISTORIA>` y se programa con `/desarrollar` |

   Si hay un aviso de arquitectura, mostrarlo al inicio. En una incidencia sin medir, avisar que `/listo` exige revisar la deuda.

2. **Leer** `trabajo/<CLAVE>/contexto.md`: criterios, descripción, extractos de arquitectura y, por repositorio, terceros,
   componentes y hallazgos relacionados. Abrir un texto completo de `.cursor/arquitectura/` solo si el extracto no alcanza
   o si otra regla rápida toca el cambio.

3. **Historia: proponer las Tareas.** Leer la historia y el código relacionado, y escribir la propuesta en
   `specs/<HISTORIA>/propuesta.md`, sin esperar a que la pidan:
   - **Preguntas para refinar:** criterios ambiguos o faltantes. La historia no se edita en Jira: se preguntan. Si no hay,
     escribir `Ninguna`.
   - **Tareas propuestas:** una fila por Tarea, con título en infinitivo, números de los criterios que cubre y repositorios.
     Entre todas deben cubrir todos los criterios.

   Mostrarla y aceptar cambios.

4. **Historia: crear las Tareas.**

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
   Tareas se crean a mano en Jira y se sigue con `/tarea <HISTORIA>`.

5. **Historia: completar cada spec** (una página como máximo; todavía no se programa): objetivo, diseño por repositorio
   citando `archivo:línea`, una prueba por criterio, reglas que aplican con la sección citada, y lo que queda fuera de
   alcance. Validar:

   ```sh
   python3 herramientas/hdu.py spec <HISTORIA>
   ```

   Exige la propuesta y todas las specs completas, y que entre todas las Tareas se cubran todos los criterios. Si es válido,
   hacer commit en la rama `docs/<HISTORIA>-tareas`, hacer push y abrir el MR en GitLab. Al integrarse, las specs quedan
   aprobadas. Seguir con `/desarrollar <TAREA>`.

6. **Error, Hotfix o Tarea sin historia: completar `specs/<CLAVE>/<CLAVE>.md`**, igual que en el paso 5. Validar con
   `python3 herramientas/hdu.py spec <CLAVE>`, hacer commit en la rama `docs/<CLAVE>-spec`, hacer push y abrir el MR en
   GitLab. **Hotfix:** no espera la aprobación: seguir con `/desarrollar`; la spec se completa antes de `/listo`.

7. **Spike:** el entregable es un ADR del producto en Propuesto. Al cerrar la investigación, crearlo con
   `python3 herramientas/harness.py adr --titulo "<decisión>" --historia <CLAVE>`, completarlo y abrir un MR a este
   repositorio.

No inventar: si no hay criterios reconocibles, decirlo. Lo que no se sabe queda `NO DETERMINADO`, con su pregunta.
