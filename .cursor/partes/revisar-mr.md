# /revisar mr

Revisión de los MR abiertos. Solo se revisan MR; lo que se declaró en `/listo` se contrasta, nunca se
da por cierto.

0. **Reglas al día** (sin IA, salvo coherencia pendiente):

   ```sh
   make harness-al-dia
   .venv/bin/python herramientas/harness.py subir
   ```

   Si hay un harness `retenido`, evaluar los pares con el paso 2 de `.cursor/commands/actualizar.md` y repetir
   `subir`. Si hay alguno `por subir`, mostrar la vista previa y, con la confirmación del usuario, ejecutar
   `harness.py subir --confirmar`. Sin cambios, seguir sin comentarios.

1. **Bandeja** (sin IA):

   ```sh
   .venv/bin/python herramientas/mr.py bandeja [--producto <producto>] [--mios]
   ```

   Muestra los MR abiertos de cada producto y de su harness, con el estado de `/listo`: primero los ADR
   del producto, después los MR sin `/listo`, los desactualizados y los al día. Preguntar cuál revisar.

2. **MR de un repositorio:**

   ```sh
   .venv/bin/python herramientas/mr.py revisar <producto> <repo> <número>
   ```

   Prepara la revisión con el código de radiografia sobre el commit de cabeza (diff, verificaciones,
   gitleaks), detecta los **cambios sensibles** (pruebas debilitadas o borradas, aserciones quitadas,
   controles apagados, umbrales de cobertura, cambios al propio control, datos de prueba sospechosos) y
   el **contraste con /listo**, y registra la deuda que declaró la historia.

   Leer el paquete (`revisiones/<fecha>-rama-<repo>-<rama>/paquete.md`) empezando por los cambios
   sensibles y el contraste: son el foco. Revisar el diff completo contra lo decidido y escribir en
   `lote.yaml` solo `hallazgos:` (mismo formato que en `/revisar`), con evidencia en archivos del cambio.
   Un cambio sensible sin motivo claro es un hallazgo.

3. **Registrar y ver la vista previa del comentario:**

   ```sh
   .venv/bin/python herramientas/rama.py publicar <producto> <repo> <rama> [--incluir H-0012,H-0015]
   ```

   Muestra el veredicto. Si nada está marcado Resolver, lista los hallazgos: preguntar cuáles se piden
   resolver y repetir con `--incluir`. Publicar solo si el usuario confirma la vista previa: repetir con
   `--confirmar` (un solo comentario en el MR, que se edita en las publicaciones siguientes).

4. **MR del harness con ADR del producto** (se aprueba con las aprobaciones configuradas en el harness):

   ```sh
   .venv/bin/python herramientas/mr.py adr <producto> <número>
   ```

   Deja la rama del MR en una copia de solo lectura, valida los ADR cambiados y muestra los pares de
   coherencia por evaluar. Evaluarlos como en `/actualizar` (un lote) con
   `.venv/bin/python herramientas/coherencia.py --decisiones <carpeta> lote <archivo>`. Responder si el ADR
   se puede aprobar: solo sin choques ni pares pendientes. La aprobación se hace en GitLab.

Responder con el veredicto, los cambios sensibles, las diferencias con `/listo`, los hallazgos principales
y, si se publicó, dónde.
