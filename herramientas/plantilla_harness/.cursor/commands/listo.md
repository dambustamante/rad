# /listo

Cerrar una historia antes de abrir su MR. Uso: `/listo <CLAVE>`.

1. **Preparar** (sin IA; exige todo en commits; primero trae la última versión de las reglas):

   ```sh
   python3 herramientas/listo.py preparar <CLAVE>
   ```

2. **Revisar** `trabajo/<CLAVE>/listo-paquete.md`: el diff de cada repositorio y lo que encontraron las
   verificaciones (secretos, salida a consola, TODO, APIs sin contrato, integraciones, pruebas
   debilitadas). Contrastar el diff con las decisiones de `.cursor/rules/generado/`: lo que no cumple se
   corrige antes del MR. Si se corrige algo, hacer commit y volver al paso 1.

3. **Registrar** `trabajo/<CLAVE>/listo.json`:
   - `criterios`: la prueba de cada criterio de aceptación, como `<repo>:<archivo>:<línea>`;
   - `deuda`: lo que la historia deja pendiente, con `tipo` (`tecnica` u `operativa`), descripción y
     evidencia. Proponerla desde las verificaciones y el diff (criterios sin prueba, atajos, TODO,
     pasos manuales que quedan) y pedir que se confirme, corrija o descarte. Sin deuda, `"sin_deuda": true`;
     en una HU sin medir es obligatorio decidirlo;
   - `decisiones_aplicadas`: los ID de las decisiones que aplican al cambio;
   - `decision_propuesta`: si apareció una decisión de diseño que conviene volver ADR, o `null`.

4. **Cerrar:**

   ```sh
   python3 herramientas/listo.py cerrar <CLAVE>
   ```

   Si hay errores (criterio sin prueba, prueba deshabilitada, evidencia inexistente, lenguaje), corregir
   y repetir. Escribe `trabajo/<CLAVE>/mr-<repo>.md` y restaura el foco.

5. Se hace push de la rama y se abre el MR con esa descripción. No editar el registro del final de la
   descripción: lo usa la revisión.
