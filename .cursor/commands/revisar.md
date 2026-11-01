# /revisar

Línea base AS IS de un repositorio, comparada en orden de autoridad, y revisión de MR. Leer solo la parte que corresponde:

| Uso | Leer y seguir |
|---|---|
| `/revisar mr [--producto <producto>] [--mios]` | `.cursor/partes/revisar-mr.md` |
| `/revisar <producto> [repo]`, con todos los repositorios al día | `.cursor/partes/revisar-producto.md` |
| `/revisar <producto> [repo]`, con repositorios pendientes | `.cursor/partes/revisar-repo.md` |

Para saber si están al día: `.venv/bin/python herramientas/revision.py pendientes <producto>`. Un repositorio por conversación:
al terminar, sugerir un chat nuevo para el siguiente.
