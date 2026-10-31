# /hdu

Tomar una historia de Jira para desarrollarla. Uso: `/hdu <CLAVE>` (por ejemplo `/hdu FRAUD-123`).

1. **Tomar:**

   ```sh
   python3 herramientas/hdu.py tomar <CLAVE> [--repos a,b] [--sin-rama]
   ```

   - **Actualiza primero el harness.** Si no puede, se detiene (salida 1): mostrar el motivo. No seguir con
     reglas viejas.
   - **Aviso de arquitectura:** si hay commits que no llegaron, mostrarlo al inicio del plan.
   - **No se toma** (salida 2) si la Medición HU no es una de las aceptadas: mostrar el motivo y sugerir
     qué falta completar en la historia. No seguir.
   - **Sin repositorios** (salida 3): preguntar cuáles toca y repetir con `--repos`.
   - **HU sin medir:** se toma, pero avisar que `/listo` va a exigir la revisión de la deuda que deja.
   - Crea la rama `feature/<CLAVE>-…` en cada repositorio (salvo cambios sin commit o `--sin-rama`) y deja
     visibles en Cursor solo esos repositorios.

2. **Leer** `trabajo/<CLAVE>/contexto.md`: criterios de aceptación, descripción, extractos de arquitectura
   relacionados y, por repositorio, terceros, componentes y hallazgos abiertos relacionados. Las decisiones
   que aplican ya están en `.cursor/rules/generado/`. Abrir un texto completo de `.cursor/arquitectura/` solo
   si el extracto no alcanza o si otra regla rápida toca el cambio.

3. **Proponer el plan** y pedir confirmación antes de implementar:
   - versión de las reglas usada (está en el contexto);
   - archivos y cambios por repositorio, citando `archivo:línea` de lo que se lee;
   - **una prueba por criterio de aceptación**, con su nombre y qué verifica;
   - documentos de arquitectura y decisiones que aplican (por su ID), con la sección citada, y hallazgos relacionados que conviene corregir de paso;
   - lo que no se sabe, como `NO DETERMINADO`, con la pregunta por resolver.

   Si no hay criterios de aceptación reconocibles, decirlo y no inventarlos.

4. **Spike:** el entregable es un ADR del producto en Propuesto. Al cerrar la investigación, crearlo
   con `python3 herramientas/harness.py adr --titulo "<decisión>" --historia <CLAVE>`, completarlo y
   abrir un MR a este repositorio.
