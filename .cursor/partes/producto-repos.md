# /producto: repositorios

1. **Para agregar**, pedir los repositorios, uno por línea. Se aceptan URL SSH o HTTPS de GitLab
   o GitHub y rutas de carpetas locales con un repositorio git.

2. **Inspeccionar cada repositorio:**

   ```sh
   .venv/bin/python herramientas/productos.py inspeccionar "<url>"
   ```

   Si falla por acceso, informar el error y seguir con los demás.

3. **Proponer el registro** en una tabla:

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

4. **Agregar los repositorios confirmados**, uno por uno:

   ```sh
   .venv/bin/python herramientas/productos.py agregar --producto <producto> --id <id> --url "<url>" --rama <rama> --tipo <tipo> [--sonar <clave>]
   ```

   Si el script rechaza
   un repositorio, mostrar el motivo y pedir la corrección.

5. **Para retirar**, pedir el motivo, confirmar y ejecutar:

   ```sh
   .venv/bin/python herramientas/productos.py retirar --producto <producto> --id <id> --motivo "<motivo>"
   ```

   El repositorio queda marcado como retirado, con fecha y motivo; no se borra su historial.

6. **Descargar los repositorios:**

   ```sh
   .venv/bin/python herramientas/productos.py sincronizar --producto <producto>
   ```
