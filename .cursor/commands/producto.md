# /producto

Crea un producto con su harness y reúne lo que `/revisar` va a revisar: repositorios git, páginas de Confluence y
documentación en cualquier formato. También administra un producto existente.
Uso: `/producto <nombre>` (por ejemplo `/producto motor-fraudes`).

La parte determinista la hace `herramientas/productos.py`. Nunca editar `producto.yaml` a mano en
este comando: siempre mediante el script.

## Pasos

1. **Identificar el producto.** Si el usuario no indicó el nombre, pedirlo (minúsculas y guiones).
   Ejecutar:

   ```sh
   .venv/bin/python herramientas/productos.py listar
   ```

   - Si el producto existe, mostrar sus repositorios en una tabla (`id`, `tipo`, `rama`, `sonar`,
     `estado`) y preguntar: agregar repositorios, retirar uno, registrar o completar terceros
     (el producto comprado y las integraciones), cargar documentos, indicar su proyecto de Jira
     (`productos.py jira <producto> --proyecto <CLAVE>`) o nada.
   - Si no existe, pedir una descripción de una frase, el **origen** (`heredado`: se recibe de otro
     equipo y se toma el control; `nuevo`: se construye desde el inicio) y la sigla para numerar sus
     ADR (proponer una: `MF` para motor-fraude). Crearlo:

     ```sh
     .venv/bin/python herramientas/productos.py crear --producto <producto> --origen <heredado|nuevo> --descripcion "<frase>" [--sigla <SIGLA>]
     ```

     El script crea también el harness: seguir `.cursor/partes/producto-harness.md` para subirlo. Un producto
     nuevo puede quedar sin repositorios hasta que tenga código. La sigla queda fija al crearlo.
   - Después de crearlo, pedir **de una vez** los tres insumos. Lo que el usuario todavía no tenga se puede agregar después:
     1. **Repositorios git**, uno por línea (paso 2).
     2. **Páginas o espacios de Confluence** (paso 3).
     3. **Documentación en otros formatos:** PDF, Word, PowerPoint, Excel, texto, dibujos y conversaciones (paso 3).

2. **Repositorios:** para agregar o retirar, leer y seguir `.cursor/partes/producto-repos.md`.

3. **Cargar los documentos:** leer y seguir `.cursor/partes/producto-documentos.md`.

4. **Actualizar el harness:** `.venv/bin/python herramientas/harness.py generar <producto>`, para que reciba
   los repositorios nuevos o retirados.

5. **Cerrar** con la tabla final de repositorios, los documentos cargados y lo que quedó por completar, y sugerir
   `/revisar <producto>` (un repositorio por chat), que revisa el código contra las reglas y contra estos documentos.

## Terceros

Para registrar o completar el producto comprado y las integraciones, leer y seguir
`.cursor/partes/producto-terceros.md`.

## Reglas

- No inventar repositorios, ramas ni claves de Sonar: solo lo que el usuario indica y la
  inspección confirma.
- El acceso a los repositorios usa la configuración de git del usuario.
