# /producto: terceros

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
