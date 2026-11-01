# Guía de radiografia

Explicación paso a paso de cómo funciona cada etapa. Para empezar, ver el [README principal](../README.md). Para
consultar un comando, ver [Comandos](10-comandos.md).

| # | Guía | Comando | Qué se aprende |
|---|---|---|---|
| 10 | [Comandos](10-comandos.md) | todos | cada comando de principio a fin: cuándo se usa, qué hace y qué se obtiene |
| 1 | [Instalación](01-instalacion.md) | `make venv`, `make doctor` | preparar el entorno, `.env` y las herramientas |
| 2 | [Conceptos](02-conceptos.md) | — | orden de autoridad, evidencia, hallazgos, veredicto y estructura de carpetas |
| 3 | [Arquitectura y coherencia](03-arquitectura.md) | `/actualizar` | registrar fuentes, sincronizar y verificar la coherencia de las decisiones |
| 4 | [Productos y terceros](04-productos.md) | `/producto` | registrar un producto, sus repositorios, el producto comprado y las integraciones |
| 5 | [Revisión de repositorios y MR](05-revisar.md) | `/revisar` | parte automática, paquete, AS IS, C4, lote, cierre, y bandeja y revisión de MR con cambios sensibles y contraste con /listo |
| 6 | [Triaje](06-triar.md) | `/triar` | decidir qué hacer con cada hallazgo y calibrar las fuentes |
| 7 | [Crear ADR, Tareas, Spikes, Errores y Hotfix](07-crear.md) | `/crear` | decisiones del producto, excepciones, historias de usuario y Jira |
| 8 | [Mantenimiento](08-mantenimiento.md) | `/estado`, `make` | el reporte semanal, el ciclo de uso habitual, los objetivos de `make` y las pruebas |
| 9 | [Harness del producto](09-harness.md) | `/producto` | el repositorio de trabajo de cada producto: estructura, lo generado, cómo se crea y se mantiene. Su uso está en [su guía de comandos](../herramientas/plantilla_harness/docs/comandos.md) |

Cada comando ejecuta primero su parte determinista (scripts de `herramientas/`, sin IA) y después
la parte que requiere criterio, que hace Cursor. Así se gasta IA solo donde aporta.
