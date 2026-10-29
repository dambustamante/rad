# Guía de radiografia

Explicación paso a paso de cómo funciona cada etapa. Para empezar rápido, ver el
[README principal](../README.md).

| # | Guía | Comando | Qué se aprende |
|---|---|---|---|
| 1 | [Instalación](01-instalacion.md) | `make venv`, `make doctor` | preparar el entorno, `.env` y las herramientas |
| 2 | [Conceptos](02-conceptos.md) | — | orden de autoridad, evidencia, hallazgos, veredicto y estructura de carpetas |
| 3 | [Arquitectura y coherencia](03-arquitectura.md) | `/actualizar` | registrar fuentes, sincronizar y verificar la coherencia de las decisiones |
| 4 | [Productos y terceros](04-productos.md) | `/producto` | registrar un producto, sus repositorios, el producto comprado y las integraciones |
| 5 | [Revisión de repositorios y ramas](05-revisar.md) | `/revisar` | parte automática, paquete, AS IS, C4, registro en lote, cierre, y revisión de ramas con comentario en el MR |
| 6 | [Triaje](06-triar.md) | `/triar` | decidir qué hacer con cada hallazgo y calibrar las fuentes |
| 7 | [Crear ADR, Tareas, Spikes y Bugs](07-crear.md) | `/crear` | decisiones del producto, excepciones, historias de usuario y Jira |
| 8 | [Mantenimiento](08-mantenimiento.md) | `/estado`, `make` | el reporte semanal, el ciclo de uso habitual, los objetivos de `make` y las pruebas |

## El ciclo completo

```
/actualizar fuentes ─► /actualizar ─► /producto ─► /revisar (un chat por repo) ─► /triar ─► /crear
        ▲                                                                                     │
        └──────────────────────────── /estado indica qué sigue ◄──────────────────────────────┘
```

Cada comando ejecuta primero su parte determinista (scripts de `herramientas/`, sin IA) y después
la parte que requiere criterio, que hace Cursor. Así se gasta IA solo donde aporta.
