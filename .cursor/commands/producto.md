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
     (el producto comprado y las integraciones), configurar las historias de usuario (ver `/crear`,
     sección "Fuente de historias") o nada.
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

El producto comprado y cada sistema externo con el que el producto se integra (buró, red de
tarjetas, listas de sanciones, otro producto…) se registran igual: una ficha y su documentación.

1. Crear la ficha (`--rol producto-comprado` para lo comprado; `integracion` por defecto):

   ```sh
   .venv/bin/python herramientas/terceros.py nuevo <producto> --id <id> --nombre "<nombre>" [--rol producto-comprado]
   ```

2. Pedir al usuario que copie la documentación, tal como viene, en
   `productos/<producto>/terceros/<id>/docs/` (manuales, contratos OpenAPI o AsyncAPI, acuerdos de
   servicio, notas de versión; PDF, Word, PowerPoint, Excel, HTML, markdown o texto), e indexarla:

   ```sh
   .venv/bin/python herramientas/terceros.py indexar <producto>
   ```

   Mostrar los contratos reconocidos y, sobre todo, los documentos **no indexados** con su motivo y
   la acción sugerida (guardar un `.doc` como `.docx`, pedir un PDF con texto en lugar de uno escaneado).
3. Completar `terceros/<id>/ficha.yaml` con el usuario. Proponer valores a partir de la documentación
   (`terceros.py buscar <producto> "<palabras>"`), citando de dónde sale cada uno; lo que no se sepa
   queda `NO DETERMINADO`. La política ante falla (fail-open o fail-closed) y su justificación son
   decisiones de negocio: las define el usuario.
4. Validar:

   ```sh
   .venv/bin/python herramientas/terceros.py validar <producto> --id <id>
   ```

Los originales nunca se modifican; `/actualizar` vuelve a indexar solo lo que cambió. `/revisar` usa
las fichas para contrastar el código: integraciones sin ficha, timeouts frente al tiempo de respuesta
del tercero y política ante falla declarada frente a la implementada.

## Reglas

- No inventar repositorios, ramas ni claves de Sonar: solo lo que el usuario indica y la
  inspección confirma.
- Los repositorios descargados (`productos/<producto>/repos/`) son de solo lectura.
- No mostrar tokens ni credenciales; el acceso usa la configuración de git del usuario.
