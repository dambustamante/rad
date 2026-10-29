# /producto

Crea un producto o administra sus repositorios: agregar repositorios nuevos o retirar uno.
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
     (el producto comprado y las integraciones), configurar las historias de usuario (ver
     `.cursor/partes/crear-historias.md`, "Fuente de historias") o nada.
   - Si no existe, informar que se creará y pedir una descripción de una frase. Al crearse, el
     script le asigna una sigla (por ejemplo `MF` para motor-fraudes) para numerar sus ADR. Mostrarla
     y ofrecer cambiarla mientras el producto no tenga ADR:
     `.venv/bin/python herramientas/productos.py sigla <producto> --asignar <SIGLA>`.

2. **Para agregar**, pedir los repositorios, uno por línea. Se aceptan URL SSH o HTTPS de GitLab
   o GitHub y rutas de carpetas locales con un repositorio git.

3. **Inspeccionar cada repositorio:**

   ```sh
   .venv/bin/python herramientas/productos.py inspeccionar "<url>"
   ```

   Si falla por acceso, informar el error y seguir con los demás.

4. **Proponer el registro** en una tabla:

   | # | id | rama | Último commit | Stack | Sonar | README | C4 | Contratos | Tipo | Aviso |
   |---|---|---|---|---|---|---|---|---|---|---|

   - `id`: el `id_sugerido`.
   - `rama`: la `rama_por_defecto`.
   - `Sonar`: el `sonar_detectado`, o "no detectada".
   - `C4`: contexto y contenedores (✅/❌ cada uno). `Contratos`: cantidad de archivos encontrados.
   - `Tipo`: proponer `propio`; el usuario indica `proveedor` (código de un tercero) o `config`
     (configuración o infraestructura).
   - `Aviso`: si `registrado_en` no es nulo, indicar en qué producto ya está; ese repositorio no
     se puede agregar.

   Pedir al usuario que confirme o corrija cada fila (id, rama, tipo y clave de Sonar). No agregar
   nada sin confirmación.

5. **Agregar los repositorios confirmados**, uno por uno:

   ```sh
   .venv/bin/python herramientas/productos.py agregar --producto <producto> --id <id> --url "<url>" --rama <rama> --tipo <tipo> [--sonar <clave>] [--descripcion "<descripción>"]
   ```

   `--descripcion` se usa solo con el primer repositorio de un producto nuevo. Si el script rechaza
   un repositorio, mostrar el motivo y pedir la corrección.

6. **Para retirar**, pedir el motivo, confirmar y ejecutar:

   ```sh
   .venv/bin/python herramientas/productos.py retirar --producto <producto> --id <id> --motivo "<motivo>"
   ```

   El repositorio queda marcado como retirado, con fecha y motivo; no se borra su historial.

7. **Descargar los repositorios:**

   ```sh
   .venv/bin/python herramientas/productos.py sincronizar --producto <producto>
   ```

8. **Cerrar** con la tabla final del producto y el resultado de la descarga, y sugerir
   `/revisar <producto>` para obtener la línea base AS IS de los repositorios nuevos.

## Terceros

Para registrar o completar el producto comprado y las integraciones, leer y seguir
`.cursor/partes/producto-terceros.md`.

## Reglas

- No inventar repositorios, ramas ni claves de Sonar: solo lo que el usuario indica y la
  inspección confirma.
- El acceso a los repositorios usa la configuración de git del usuario.
