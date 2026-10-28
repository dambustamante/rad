# arquitectura

Copia de los documentos que publica arquitectura (ADR, estándares y referencias). La escribe
`/actualizar` a partir de las fuentes declaradas en `harness.yaml`.

**No se edita a mano.** Cualquier cambio se pierde en la siguiente sincronización. Para proponer
un cambio a un documento de arquitectura, se gestiona directamente con el equipo de arquitectura.

Archivos generados:

- `INDICE.md`: documentos con su tipo, estado, vigencia, fechas, relaciones y regla rápida.
- `decisiones/<fuente>/`: ADR de las fuentes de tipo `adr` (nivel 1).
- `estandares/<fuente>/`: documentos de las fuentes de tipo `estandar` o `referencia` (nivel 2).
- `estado/indice.json`: el índice en formato legible por las herramientas.
- `estado/fuentes.lock`: commit exacto de cada fuente en la última sincronización.

Las fuentes se descargan solo con `git`, en `.cache/arquitectura/` (no versionado), por lo que
funcionan con GitLab, GitHub o una carpeta local.
