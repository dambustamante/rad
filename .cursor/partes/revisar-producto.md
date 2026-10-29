# /revisar: consolidar el producto

Cuando todos los repositorios están al día.

1. Leer las fichas `productos/<producto>/as-is/<repo>.md` (AS IS, componentes y comparación).
2. Escribir un archivo temporal con dos secciones:
   - `## Visión del producto`: qué hace y cómo se reparten las responsabilidades entre repositorios.
   - `## Conclusiones`: brechas principales y recomendaciones, con referencias a los hallazgos.

   El C4 del producto y la tabla de componentes los genera el script: no escribirlos.
3. Ejecutar:

   ```sh
   .venv/bin/python herramientas/revision.py producto <producto> --narrativa <archivo>
   ```

4. Mostrar los cruces de `as-is/PRODUCTO.md` (integraciones sin ficha, fichas sin uso, mensajería sin
   par) y sugerir qué hacer: crear la ficha con `/producto`, revisar la ficha o confirmar con el equipo.
