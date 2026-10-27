# equipo

Decisiones del equipo (ADR-EQ): nivel 3 del orden de autoridad, subordinado a los ADR y
estándares de arquitectura.

## Decisiones

| ADR | Título | Estado |
|---|---|---|
| [ADR-EQ-001](ADR-EQ-001-documentacion-c4.md) | Documentación de arquitectura C4 en cada repositorio | Propuesto |
| [ADR-EQ-002](ADR-EQ-002-contratos-como-codigo.md) | Contratos como código, versionados en el repositorio | Propuesto |
| [ADR-EQ-003](ADR-EQ-003-integraciones-resilientes.md) | Integraciones resilientes con política de degradación explícita | Propuesto |
| [ADR-EQ-004](ADR-EQ-004-datos-sensibles.md) | Protección de datos sensibles en código, logs y pruebas | Propuesto |
| [ADR-EQ-005](ADR-EQ-005-readme-estandar.md) | README estándar en español neutro y técnico | Propuesto |
| [ADR-EQ-006](ADR-EQ-006-principios-solid-kiss.md) | Principios de diseño SOLID y KISS | Propuesto |
| [ADR-EQ-007](ADR-EQ-007-manejo-de-logs.md) | Manejo de logs estructurados y correlacionados | Propuesto |

## Ciclo de vida

```
Propuesto ──► Aprobado ──► Reemplazado
    └──────► Rechazado
```

- **Propuesto:** se evalúa en modo informativo. Sus hallazgos se marcan como `propuesta` y no
  afectan el veredicto. Sirve para calibrar la decisión antes de presentarla al equipo.
- **Aprobado:** se evalúa con efecto en el veredicto. Requiere que `COHERENCIA.md` no registre
  choques con arquitectura.
- **Reemplazado / Rechazado:** no se evalúa. Un ADR aprobado no se edita: se reemplaza por uno
  nuevo.

## Criterios de verificación

Cada ADR-EQ termina con sus criterios (`EQ-NNN.N`). La columna **Cómo** indica:

- `automática`: la verifica una herramienta, siempre con el mismo resultado.
- `revisión de código`: requiere leer y entender el código; se reporta con evidencia `ruta:línea`.
- `automática + revisión de código`: una herramienta detecta candidatos y la revisión los confirma.

## Archivos

- `ADR-EQ-NNN-<titulo>.md`: cada decisión.
- `COHERENCIA.md`: generado por `/actualizar`; compara cada ADR-EQ con arquitectura.
- `coherencia.json`: resultados de cada par evaluado y criterios suspendidos (lo leen las herramientas).
- `plantillas/`: plantilla de ADR, README y diagramas C4.
