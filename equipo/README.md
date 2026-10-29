# equipo

Decisiones del equipo (ADR-EQ): nivel 3 del orden de autoridad, subordinado a los ADR y estándares
de arquitectura.

| Archivo o carpeta | Contenido |
|---|---|
| [INDICE.md](INDICE.md) | las decisiones con su estado y su coherencia (generado) |
| [COHERENCIA.md](COHERENCIA.md) | comparación de cada ADR-EQ con arquitectura (generado) |
| `decisiones/` | los ADR-EQ: `ADR-EQ-NNN-<titulo>.md` |
| `plantillas/` | plantillas de ADR del equipo y de producto, README y diagramas C4 |
| `estado/` | datos de las herramientas (no se editan) |

## Ciclo de vida

```
Propuesto ──► Aprobado ──► Reemplazado
    └──────► Rechazado
```

- **Propuesto:** se evalúa en modo informativo. Sus hallazgos se marcan como `propuesta` y no
  afectan el veredicto. Sirve para calibrar la decisión antes de presentarla al equipo.
- **Aprobado:** se evalúa con efecto en el veredicto. Requiere que `COHERENCIA.md` no registre
  choques ni pares pendientes.
- **Reemplazado / Rechazado:** no se evalúa. Un ADR aprobado no se edita: se reemplaza por uno
  nuevo.

## Criterios de verificación

Cada ADR-EQ termina con sus criterios (`EQ-NNN.N`). La columna **Cómo** indica:

- `automática`: la verifica una herramienta, siempre con el mismo resultado.
- `revisión de código`: requiere leer y entender el código; se reporta con evidencia `ruta:línea`.
- `automática + revisión de código`: una herramienta detecta candidatos y la revisión los confirma.
- `revisión de la historia`, `revisión del MR` o `plataforma git`: criterios sobre la forma de
  trabajar (ADR-EQ-008 y ADR-EQ-009); no se evalúan en la revisión del código de un repositorio.
