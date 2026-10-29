# /revisar --rama

Solo se revisa lo que la rama cambia respecto de su destino (la rama del MR o PR, o la principal si
no hay MR). Sin AS IS, sin C4 y sin evaluar cada elemento.

1. **Preparar:** `make revisar P=<producto> R=<repo> RAMA=<rama>`. Trae la rama a `.cache/ramas/` (solo
   lectura), busca su MR, ejecuta las verificaciones y gitleaks sobre lo que cambió y escribe el
   paquete.
2. **Leer el paquete** (`revisiones/<fecha>-rama-<repo>-<rama>/paquete.md`): diff, hallazgos automáticos,
   terceros, contra qué comparar y el MR. Abrir archivos de la copia solo si el diff no alcanza.
3. **Escribir** en `lote.yaml` solo `hallazgos:` (mismo formato que en `/revisar`), los que la rama
   introduce o empeora, con evidencia en un archivo cambiado.
4. **Registrar y ver la vista previa:**

   ```sh
   .venv/bin/python herramientas/rama.py publicar <producto> <repo> <rama> [--incluir H-0012,H-0015]
   ```

   Muestra el veredicto. Si nada está marcado Resolver, lista los hallazgos abiertos: preguntar cuáles
   se piden resolver y repetir con `--incluir`. Si hay avisos de lenguaje, corregir el lote y repetir.
5. **Publicar** solo si el usuario confirma la vista previa: repetir con `--confirmar`. Un solo
   comentario en el MR o PR, que se edita en las publicaciones siguientes. Sin MR abierto no se publica.

Responder con el veredicto de la rama, los hallazgos principales y dónde se publicó.
