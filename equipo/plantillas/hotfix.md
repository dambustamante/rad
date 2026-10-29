---
tipo_incidencia: hotfix
tipo: Bau/Incidentes
equipos: Back
producto: <producto>
repos: []
hallazgos: []
historias_relacionadas: []
estado: borrador
jira: null
---
# <Título: qué falla en producción + dónde>

**Como** <rol afectado: operador, analista de fraude, cliente…>
**Quiero** <recuperar el comportamiento correcto, en términos concretos>
**Para** <el valor: detener el impacto que hoy causa la falla>

## Criterios de aceptación

- <criterio medible de la recuperación: por ejemplo, la tasa de error vuelve a menos de 1%>
- La corrección está en producción y el servicio vuelve a funcionar, verificado con el indicador o la alerta que detectó la falla.
- Hay un Error de seguimiento creado para documentar la causa y agregar la prueba que reproduce la falla.

## Comportamiento actual

<Qué falla en producción, con evidencia: logs, `trace_id`, alertas, desde cuándo.>

## Impacto

<Transacciones, clientes o procesos afectados, con cantidades si se conocen.>

## Corrección

<Qué se cambia para recuperar el servicio y cómo se vuelve atrás si falla.>

## Trazabilidad

- <Incidente, alertas y repositorios involucrados>

## Definición de terminado

Según ADR-EQ-008 (Definición de terminado) del equipo Back.
