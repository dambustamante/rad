# /hdu: otras incidencias

1. **Error, Hotfix o Tarea sin historia: completar `specs/<CLAVE>/<CLAVE>.md`** (una página como máximo): objetivo, diseño por
   repositorio citando `archivo:línea`, una prueba por criterio, reglas que aplican y lo que queda fuera de alcance. Validar con
   `python3 herramientas/hdu.py spec <CLAVE>`, hacer commit en la rama `docs/<CLAVE>-spec`, hacer push y abrir el MR en
   GitLab. **Hotfix:** no espera la aprobación: seguir con `/desarrollar`; la spec se completa antes de `/listo`.

2. **Spike:** el entregable es un ADR del producto en Propuesto. Al cerrar la investigación, crearlo con
   `python3 herramientas/harness.py adr --titulo "<decisión>" --historia <CLAVE>`, completarlo y abrir un MR a este
   repositorio.
