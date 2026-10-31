# equipo

Decisiones del equipo (ADR-EQ): nivel 3 del orden de autoridad, subordinado a los ADR y estándares
de arquitectura.

| Archivo o carpeta | Contenido |
|---|---|
| [INDICE.md](INDICE.md) | las decisiones con su estado y su coherencia (generado) |
| [COHERENCIA.md](COHERENCIA.md) | comparación de cada ADR-EQ con arquitectura (generado) |
| `decisiones/` | los ADR-EQ: `ADR-EQ-NNN-<titulo>.md` |
| `plantillas/` | plantilla de ADR (del equipo y de producto), Tarea, Spike, Error, Hotfix, README y diagramas C4 |
| `estado/` | datos de las herramientas (no se editan) |

## Orden

Los ADR-EQ están numerados por importancia, según el riesgo que cubren:

| ADR-EQ | Grupo | Tema |
|---|---|---|
| 001 | Seguridad y operación | Datos sensibles |
| 002 | Seguridad y operación | Integraciones resilientes |
| 003 | Seguridad y operación | Logs |
| 004 | Diseño | Contratos como código |
| 005 | Diseño | SOLID y KISS |
| 006 | Documentación | De macro a micro: Confluence, README, C4, docs y contratos |
| 007 | Documentación | README |
| 008 | Forma de trabajar | Definición de terminado |
| 009 | Forma de trabajar | Estructura de Tareas, Spikes, Errores y Hotfix |
| 010 | Forma de trabajar | Nombres de ramas y mensajes de commit |

Una decisión nueva toma el siguiente número libre; la numeración no se cambia después de aprobar.

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
- `revisión del producto`: criterios sobre la documentación del producto completo, por ejemplo su
  página en Confluence (ADR-EQ-006); se evalúan al consolidar el producto, no en cada repositorio.

Quién verifica la definición de terminado (ADR-EQ-008):

| Criterio | Quién lo verifica |
|---|---|
| EQ-008.1 (pruebas de los criterios de aceptación), EQ-008.7 (prueba que reproduce el Error) | la persona que aprueba el MR |
| EQ-008.2 (MR aprobado por otra persona) | la plataforma git; la revisión de la rama lo informa |
| EQ-008.3 (Sonar en verde) | Sonar, en la rama principal |
| EQ-008.4 (sin secretos) | gitleaks, en la revisión de la rama |
| EQ-008.5 (hallazgos de origen corregidos), EQ-008.8 (Spike con ADR propuesto), EQ-008.9 (Hotfix con Error de seguimiento) | `/estado`, sobre lo creado en Jira |
| EQ-008.6 (ADR-EQ que aplican según lo que cambió) | la revisión de la rama |

Un ADR-EQ nuevo se crea con `.venv/bin/python herramientas/adr.py nuevo equipo --tipo decision --titulo "<título>"`.
