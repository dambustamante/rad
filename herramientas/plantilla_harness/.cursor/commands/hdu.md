# /hdu

Refinar una historia de Jira, proponer sus Tareas y, con confirmación, crearlas. Uso: `/hdu <HISTORIA>`, por ejemplo `/hdu FRAUD-123`. También toma
un Error, un Hotfix, un Spike o una Tarea sin historia. No crea ramas de código ni se programa todavía. Es el único comando del harness que escribe en Jira.

1. **Tomar:**

   ```sh
   python3 herramientas/hdu.py tomar <CLAVE> [--repos a,b]
   ```

   Actualiza primero el harness. Si no puede, se detiene: mostrar el motivo y no seguir con reglas viejas.

   | Salida | Qué significa | Qué hacer |
   |---|---|---|
   | 2 | La Medición HU no es una de las aceptadas | Mostrar el motivo y sugerir qué completar. No seguir |
   | 3 | Sin repositorios (incidencia sin historia) | Preguntar cuáles toca y repetir con `--repos` |
   | 4 | Es una Tarea que cuelga de una historia | Indicar que se refina con `/hdu <HISTORIA>` y se programa con `/desarrollar` |

   Si hay un aviso de arquitectura, mostrarlo al inicio. En una incidencia sin medir, avisar que `/listo` exige revisar la deuda.

2. **Leer** `trabajo/<CLAVE>/contexto.md`: criterios, descripción, extractos de arquitectura y, por repositorio, terceros,
   componentes y hallazgos relacionados. Abrir un texto completo de `.cursor/arquitectura/` solo si el extracto no alcanza
   o si otra regla rápida toca el cambio. Para saber cómo funciona el producto, buscar en `documentos/`; si contradice al
   código, manda el código.

3. **Seguir según lo que sea:**

   | Incidencia | Leer y seguir |
   |---|---|
   | Historia | `.cursor/partes/hdu-historia.md` |
   | Error, Hotfix, Spike o Tarea sin historia | `.cursor/partes/hdu-otras.md` |

No inventar: si no hay criterios reconocibles, decirlo. Lo que no se sabe queda `NO DETERMINADO`, con su pregunta.
