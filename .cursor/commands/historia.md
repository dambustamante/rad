# /historia

Crea una Tarea, un Spike o un Bug del equipo Back con la estructura de ADR-EQ-008, a partir de la
información del producto, y la crea en Jira solo con confirmación del usuario.

Uso:

- `/historia <producto>`: preguntar qué se necesita.
- `/historia <producto> --desde H-0041,H-0052`: una Tarea de Deuda Técnica a partir de hallazgos
  (por ejemplo, los marcados como Deuda en `/triar`).
- `/historia <producto> --spike`: un Spike.

## Tipos

| Tipo de incidencia | Campo Tipo | Cuándo |
|---|---|---|
| Tarea | Deuda Técnica | Corregir o mejorar código o arquitectura |
| Tarea | Deuda Operativa | Eliminar trabajo manual por falta de un backoffice |
| Bug | Bau/Incidentes | Corregir algo que falla en producción |
| Spike | Spike | Investigar para decidir (2 días como máximo) |

## Pasos

1. **Entender el pedido.** Preguntar el tipo, el título, los repositorios involucrados y unas palabras
   clave del tema (sirven para buscar en la documentación y en Jira). Para un Bug, pedir lo que se
   sabe del incidente; para una Deuda Operativa, la frecuencia y el esfuerzo del trabajo manual.

2. **Crear el borrador y el contexto:**

   ```sh
   .venv/bin/python herramientas/historia.py nueva <producto> --tipo <tarea|spike|bug> --titulo "<título>" \
     [--categoria "Deuda Operativa"] [--desde H-0041,H-0052] [--repos <repo1,repo2>] [--tema "<palabras clave>"]
   ```

   El título de una Tarea o un Spike empieza con un verbo en infinitivo ("Agregar…", "Evaluar…").

3. **Leer el contexto** (`…-contexto.md`): hallazgos de origen y relacionados, AS IS de los
   repositorios, decisiones que pueden aplicar, integraciones, documentación del proveedor y de
   terceros, historias parecidas de Jira y Sonar. Si una historia de Jira ya cubre lo mismo,
   avisar al usuario antes de seguir.

4. **Redactar el borrador** (`productos/<producto>/historias/borradores/<NNN>-<título>.md`) con la
   plantilla ya cargada:

   - **Como**: un rol real; nunca "sistema". **Para**: el valor, sin repetir el Quiero.
   - **Criterios de aceptación**: al menos uno propio y medible, más los fijos de su tipo, que ya
     vienen en la plantilla.
   - Las secciones de su tipo, con evidencia del contexto (hallazgos, `archivo:línea`, métricas).
     Lo que no se sepa se marca `NO DETERMINADO`; no se inventa.
   - Solo las decisiones que el trabajo debe respetar, con su regla rápida.
   - Lenguaje técnico y claro, comprensible para cualquier seniority, sin adornos ni muletillas
     (`equipo/lenguaje.yaml`).

5. **Validar:**

   ```sh
   .venv/bin/python herramientas/historia.py validar <producto> <borrador>
   ```

   Corregir hasta que no haya errores.

6. **Vista previa.** Ejecutar sin `--confirmar` y mostrar al usuario el título, el proyecto, el tipo y
   el texto completo:

   ```sh
   .venv/bin/python herramientas/historia.py crear <producto> <borrador>
   ```

7. **Crear en Jira**, solo si el usuario lo confirma explícitamente:

   ```sh
   .venv/bin/python herramientas/historia.py crear <producto> <borrador> --confirmar
   ```

   La clave queda en el borrador y, si nació de hallazgos, en cada hallazgo.

## Reglas

- Nunca crear en Jira sin la confirmación explícita del usuario sobre la vista previa.
- No crear historias de tipo Producto u Otros.
- No editar el encabezado YAML del borrador salvo para corregir el Tipo o los repositorios.
- El proyecto de destino es el configurado en las historias del producto (`historias.proyecto` o la consulta
  JQL (Jira Query Language)); si falta, configurarlo con `productos.py historias <producto> ... --proyecto <CLAVE>`.
