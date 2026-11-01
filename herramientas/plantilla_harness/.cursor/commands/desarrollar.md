# /desarrollar

Programar una Tarea contra su spec aprobada. Uso: `/desarrollar <TAREA>`. También para un Error o un Hotfix.

1. **Preparar** (sin IA):

   ```sh
   python3 herramientas/hdu.py desarrollar <CLAVE> [--tipo feat|fix|docs|chore|test|refactor]
   ```

   Comprueba la aprobación, crea la rama `<tipo>/<CLAVE>-…` en cada repositorio de la spec y deja visibles en Cursor solo
   esos repositorios. El tipo es `fix` para un Error o un Hotfix, `chore` para una Tarea de deuda y `feat` para el resto. Si
   el cambio es de otro tipo, indicarlo con `--tipo` (ADR-EQ-010). Si se detiene, mostrar el motivo y no programar.

2. **Leer** la spec y `trabajo/<CLAVE>/contexto.md`. No releer las reglas: `.cursor/rules/generado/` se carga solo. Un chat por Tarea.

3. **Proponer los pasos**, cada uno ligado a un criterio de aceptación y a su prueba, y pedir confirmación. Volver a
   pedirla en los cambios delicados.

4. **Implementar** en `code/<repo>/`, en la rama de la Tarea, y ejecutar las pruebas. Los commits siguen Conventional
   Commits (ADR-EQ-010).

5. **Si algo no calza con la spec:** no cambiar el alcance. Un cambio menor se anota para `desvios` de `/listo`. Un
   cambio de alcance o de diseño se detiene y se propone corregir la spec en un MR.

Al terminar, sugerir un chat nuevo para `/listo <CLAVE>`.
