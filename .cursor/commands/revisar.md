# /revisar

Obtiene la línea base AS IS de los repositorios de un producto y la compara con lo que la
organización decidió.
Uso: `/revisar <producto> [repo]`.

> Estado: por ahora este comando ejecuta solo la **parte automática**. La revisión de código
> (AS IS descriptivo, comparación con ADR y estándares de arquitectura, criterios de revisión de
> código y diagrama C4 inferido) se agrega en el siguiente paso de construcción.

## Pasos

1. Ejecutar:

   ```sh
   make revisar P=<producto> [R=<repo>]
   ```

   Si Sonar no está configurado, la revisión continúa y el nivel 4 queda `NO DETERMINADO`.

2. Leer `productos/<producto>/reportes/<id-revisión>/resumen.md` y, para cada repositorio,
   `productos/<producto>/as-is/<repo>.md`.

3. Responder con este formato:

   ```markdown
   ## Revisión <id> de <producto> (parte automática)

   | Repositorio | Commit | Quality gate | Nuevos | Corregidos | Reaparecidos | Abiertos | Veredicto preliminar |
   |---|---|---|---|---|---|---|---|

   ### Lo más relevante por repositorio
   <para cada repositorio, como máximo 5 hallazgos ordenados por nivel y severidad, con su ID,
   criterio o regla y evidencia `ruta:línea`>

   ### Avisos
   <desfase entre el análisis de Sonar y el commit revisado; repositorios omitidos y su motivo;
   criterios NO DETERMINADO>
   ```

## Reglas

- No modificar nada en `productos/*/repos/`.
- No editar `hallazgos.json` ni la sección automática de las fichas: los escribe el script.
- Los hallazgos en modo `propuesta` vienen de decisiones del equipo no aprobadas: se informan, pero
  no afectan el veredicto.
- Nunca copiar valores de secretos: indicar solo su ubicación.
