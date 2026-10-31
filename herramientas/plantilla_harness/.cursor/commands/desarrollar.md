# /desarrollar

Programar una historia contra su spec aprobada. Uso: `/desarrollar <CLAVE>`.

1. **Comprobar** (sin IA):

   ```sh
   python3 herramientas/hdu.py desarrollar <CLAVE>
   ```

   Si se detiene porque la spec no está aprobada, mostrar el motivo y no programar.

2. **Leer** `specs/<CLAVE>/spec.md` y lo que cita. No releer las reglas: ya están en `.cursor/rules/generado/`.

3. **Proponer los pasos**, cada uno ligado a un criterio de aceptación y a su prueba, y pedir confirmación. Volver a
   pedirla en los cambios delicados.

4. **Implementar** en `code/<repo>/`, en la rama de la historia, y ejecutar las pruebas.

5. **Si algo no calza con la spec:** no cambiar el alcance. Un cambio menor se anota para `desvios` de `/listo`. Un
   cambio de alcance o de diseño se detiene y se propone corregir la spec en un MR.

Al terminar, seguir con `/listo <CLAVE>`.
