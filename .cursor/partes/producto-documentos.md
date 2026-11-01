# /producto: documentos del producto

Toda la documentación del producto queda en markdown, en `documentos/` de su harness. Es evidencia de tipo `[doc]`: si
contradice al código, manda el código y la diferencia es un hallazgo. Lo que no sea de un tercero va aquí; lo de un
tercero, en `.cursor/partes/producto-terceros.md`.

| Qué trae el usuario | Qué ejecutar | Qué hace Cursor después |
|---|---|---|
| Página de Confluence | `.venv/bin/python herramientas/documentos.py confluence <producto> <url>` | Nada |
| Espacio de Confluence | `.venv/bin/python herramientas/documentos.py confluence <producto> --espacio <CLAVE>` | Nada |
| PDF, Word, PowerPoint, Excel, HTML o texto | `.venv/bin/python herramientas/documentos.py importar <producto> <archivo> [--titulo "<título>"]` | Nada |
| Dibujo o imagen | Igual que el anterior | Abrir la imagen, completar **Qué muestra** y pedir que lo revise |
| Conversación | Igual, con `--conversacion` | Leer el original y completar fecha, decisiones y pendientes, sin copiar el chat ni datos personales |

Confluence es de solo lectura. Antes de importar un espacio completo, confirmar con el usuario: todos los que usan el
harness verán esas páginas. Ver qué falta completar con `documentos.py listar <producto>`. Al terminar, hacer commit de lo
completado con `.venv/bin/python herramientas/harness.py guardar`, y publicar con `harness.py subir`.
