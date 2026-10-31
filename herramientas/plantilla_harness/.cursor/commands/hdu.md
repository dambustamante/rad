# /hdu

Tomar una Tarea de Jira para desarrollarla. Uso: `/hdu <CLAVE>` (por ejemplo `/hdu FRAUD-200`). También acepta un
Error, un Hotfix o un Spike. Una historia no se toma directo: se desarrolla en una Tarea.

1. **Tomar:**

   ```sh
   python3 herramientas/hdu.py tomar <CLAVE> [--repos a,b] [--sin-rama] [--tipo feat|fix|docs|chore|test|refactor]
   ```

   - **Actualiza primero el harness.** Si no puede, se detiene (salida 1): mostrar el motivo. No seguir con
     reglas viejas.
   - **Aviso de arquitectura:** si hay commits que no llegaron, mostrarlo al inicio del plan.
   - **Es una historia** (salida 4): indicar que se cree su Tarea con `/tarea` o a mano. No seguir.
   - **No se toma** (salida 2) si la Medición HU no es una de las aceptadas: mostrar el motivo y sugerir
     qué falta completar en la historia. No seguir.
   - **Sin repositorios** (salida 3): preguntar cuáles toca y repetir con `--repos`.
   - **Medición y criterios:** vienen de la historia de la que cuelga la Tarea. Una Tarea sin historia usa sus
     propios criterios y queda sin medir. Si la historia tiene varias Tareas, dejar en la spec solo los criterios que
     cubre esta.
   - **HU sin medir:** se toma, pero avisar que `/listo` va a exigir la revisión de la deuda que deja.
   - Crea la rama `<tipo>/<CLAVE>-…` en cada repositorio (salvo cambios sin commit o `--sin-rama`) y deja visibles
     en Cursor solo esos repositorios. El tipo es `fix` para un Error o un Hotfix, `chore` para una Tarea de deuda y
     `feat` para el resto. Si el cambio es de otro tipo, indicarlo con `--tipo` (ADR-EQ-010).

2. **Leer** `trabajo/<CLAVE>/contexto.md`: criterios de aceptación, descripción, extractos de arquitectura
   relacionados y, por repositorio, terceros, componentes y hallazgos abiertos relacionados. Las decisiones
   que aplican ya están en `.cursor/rules/generado/`. Abrir un texto completo de `.cursor/arquitectura/` solo
   si el extracto no alcanza o si otra regla rápida toca el cambio.

3. **Completar la spec** `specs/<CLAVE>/spec.md` (una página como máximo; todavía no se programa):
   - Objetivo, Diseño (cambios por repositorio, citando `archivo:línea`) y Fuera de alcance;
   - **Pruebas:** una por criterio de aceptación, con su nombre y qué verifica;
   - Reglas que aplican: documentos de arquitectura y decisiones (por su ID), con la sección citada, y la
     versión de las reglas usada;
   - lo que no se sabe, como `NO DETERMINADO`, con la pregunta por resolver.

   Mostrarla y pedir confirmación. Después:

   ```sh
   python3 herramientas/hdu.py spec <CLAVE>
   ```

   Si es válida, hacer commit en la rama `docs/<CLAVE>-spec` del harness y push. El MR de la spec se abre en GitLab.
   Al aprobarse e integrarse, seguir con `/desarrollar <CLAVE>`. **Hotfix:** no espera la aprobación: seguir con
   `/desarrollar`; la spec se completa antes de `/listo` y se integra después.

   Si no hay criterios de aceptación reconocibles, decirlo y no inventarlos.

4. **Spike:** el entregable es un ADR del producto en Propuesto. Al cerrar la investigación, crearlo
   con `python3 herramientas/harness.py adr --titulo "<decisión>" --historia <CLAVE>`, completarlo y
   abrir un MR a este repositorio.
