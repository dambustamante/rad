# /crear

Crea un ADR o una excepción, o una Tarea, un Spike, un Error o un Hotfix para Jira.

| Uso | Qué crea | Leer y seguir |
|---|---|---|
| `/crear <producto> adr` o `excepcion` | ADR del producto | `.cursor/partes/crear-adr.md` |
| `/crear equipo adr` | ADR del equipo (ADR-EQ) | `.cursor/partes/crear-adr.md` |
| `/crear <producto> adr --desde-historias` | ADR propuestos desde historias de Jira | `.cursor/partes/crear-historias.md` |
| `/crear <producto> tarea\|spike\|error\|hotfix` | borrador para Jira (ADR-EQ-009), creado solo con confirmación | `.cursor/partes/crear-jira.md` |
| `/crear <producto> tarea --desde H-0041,H-0052` | Tarea de Deuda Técnica desde hallazgos | `.cursor/partes/crear-jira.md` |
| `/crear <producto> error --hotfix FRAUD-300` | Error de seguimiento de un Hotfix | `.cursor/partes/crear-jira.md` |

| Tipo | Campo Tipo | Cuándo |
|---|---|---|
| `tarea` | Deuda Técnica | Corregir o mejorar código o arquitectura |
| `tarea` | Deuda Operativa | Eliminar trabajo manual por falta de un backoffice |
| `error` | Bau/Incidentes | Corregir algo que falla en producción |
| `hotfix` | Bau/Incidentes | Corregir de inmediato algo que no puede esperar; la causa y la prueba van en un Error de seguimiento |
| `spike` | Spike | Investigar para decidir (2 días como máximo) |

Si no se indicó qué crear, preguntarlo primero y leer **solo** la parte que corresponde. No inventar
respuestas: lo que el usuario no sepa queda `NO DETERMINADO`. No se crean historias de tipo Producto u
Otros.
