# ADR-EQ-009: Estructura de Tareas, Spikes, Errores y Hotfix

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `28-10-2026`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** las Tareas, Spikes, Errores y Hotfix del equipo se escriben con estructuras
  distintas. Falta la evidencia del problema, el alcance no queda claro y cuesta estimar y revisar.
- **Alcance:** Tareas, Spikes, Errores y Hotfix del equipo Back.
- **Restricciones:** mantener el formato que el equipo ya usa (Como, Quiero, Para y Criterios de
  aceptación) y que se entienda sin importar el seniority de quien lo lea.

## 5. Decisión

Toda Tarea, Spike, Error o Hotfix tiene:

1. **Campos de Jira:** Equipos = Back; Tipo según la tabla de combinaciones válidas.
2. **Encabezado común:** Como / Quiero / Para y Criterios de aceptación.
3. **Secciones propias de su tipo de incidencia** (ver Acciones requeridas).
4. **Enlace a la definición de terminado** (ADR-EQ-008), sin repetirla.

| Tipo de incidencia | Campo "Tipo" permitido |
|---|---|
| Tarea | Deuda Técnica, Deuda Operativa, Producto |
| Error | Bau/Incidentes |
| Hotfix | Bau/Incidentes |
| Spike | Spike |

Una **Tarea de Producto** es una parte del desarrollo de una historia y cuelga de ella. Una historia puede tener varias.
Su contenido ya está en la historia y en la spec, así que lleva solo un resumen y la ubicación de la spec. No aplican los puntos 2 y 3.

Un **Hotfix** es la corrección urgente de algo que falla en producción y no puede esperar: se
escribe con lo mínimo para actuar ya, y la causa y la prueba que reproduce la falla se documentan
después en un **Error de seguimiento**.

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| Formato libre | Sin esfuerzo | Información dispar; difícil de estimar | Sin criterio común |
| Una plantilla nueva, distinta del formato del equipo | Más campos | El equipo ya usa Como/Quiero/Para | Costo de adopción |
| Como/Quiero/Para + criterios + secciones por tipo | Conserva el formato conocido y agrega la evidencia necesaria | Algo más de texto | **Elegida** |

## 7. Consecuencias

### Positivas

- Todo el trabajo técnico se lee igual y se estima con la misma información.
- La evidencia del problema queda en la historia y no en la memoria de quien la escribió.

### Negativas o compromisos

- Escribir una historia toma unos minutos más.

### Riesgos

- Secciones completadas con texto genérico. Se mitiga con las reglas de lenguaje.

## 8. Impacto

Todas las Tareas, Spikes, Errores y Hotfix que crea el equipo Back.

## 9. Acciones requeridas

**Encabezado común**

- **Como** <rol real: desarrollador, operador, analista de fraude, cliente…>; nunca "como sistema".
- **Quiero** <qué se necesita, en términos concretos>.
- **Para** <el valor: reducir un riesgo, cumplir una decisión, evitar un incidente, eliminar un
  trabajo manual, desbloquear otra historia>. No repite el "Quiero".
- **Criterios de aceptación:** verificables, en formato Dado/Cuando/Entonces o como lista. Al menos
  uno medible.

**Tarea (Deuda Técnica o Deuda Operativa)**

| Sección | Contenido |
|---|---|
| Contexto | El problema actual con evidencia: archivo y línea, métricas, incidentes, frecuencia y esfuerzo del trabajo manual |
| Decisiones que aplican | ADR de arquitectura, del equipo y del producto, con su regla rápida |
| Fuera de alcance | Qué no incluye |
| Trazabilidad | Hallazgos, ADR e historias relacionadas |

Criterio fijo: en Deuda Técnica, "la revisión ya no reporta los hallazgos de origen"; en Deuda
Operativa, "la tarea manual deja de ser necesaria", indicando cómo se verifica.

**Tarea (Producto)**

| Sección | Contenido |
|---|---|
| Resumen | Qué parte de la historia desarrolla |
| Trazabilidad | Historia de la que cuelga y ubicación de la spec |

**Error (Bau/Incidentes)**

| Sección | Contenido |
|---|---|
| Comportamiento actual | Qué pasa, con evidencia: logs, `trace_id`, fecha y entorno |
| Comportamiento esperado | Qué debería pasar |
| Cómo reproducirlo | Pasos o datos de entrada; NO DETERMINADO si no se pudo reproducir |
| Impacto | Transacciones, clientes o procesos afectados |
| Causa | Si se conoce; si no, NO DETERMINADO y la hipótesis |
| Trazabilidad | Incidente, hallazgos e integraciones involucradas |

Criterios fijos: prueba que reproduce el error, causa documentada y medida que evita que se
repita sin aviso. Si es el seguimiento de un Hotfix, la Trazabilidad incluye la clave del Hotfix.

**Hotfix (Bau/Incidentes)**

| Sección | Contenido |
|---|---|
| Comportamiento actual | Qué falla en producción, con evidencia: logs, `trace_id`, alertas, desde cuándo |
| Impacto | Transacciones, clientes o procesos afectados, con cantidades si se conocen |
| Corrección | Qué se cambia para recuperar el servicio y cómo se vuelve atrás si falla |
| Trazabilidad | Incidente, alertas y repositorios involucrados |

Criterios fijos: la corrección está en producción y el servicio vuelve a funcionar, verificado
con el indicador o la alerta que detectó la falla; y hay un Error de seguimiento creado para la
causa y la prueba.

**Spike**

| Sección | Contenido |
|---|---|
| Pregunta | Una sola, concreta |
| Contexto | Por qué hay que decidirlo ahora, con evidencia |
| Opciones a evaluar | Las conocidas al empezar |
| Criterios de decisión | Ordenados por importancia: cumplimiento de ADR, latencia, costo, operación, soporte |
| Restricciones | ADR vigentes, condiciones del proveedor, integraciones |
| Duración máxima | 2 días, salvo justificación |
| Entregable | Recomendación documentada y ADR de producto en estado Propuesto |

**Lenguaje**

- Técnico y preciso: se nombra el componente, la tecnología y el dato concreto.
- Claro para cualquier seniority: frases cortas, siglas explicadas la primera vez.
- Voz activa y sujeto claro.
- Español neutro, sin voseo ni regionalismos.
- Sin adornos ni muletillas ("robusto", "potenciar", "integral", "Es importante destacar"): cada
  frase dice algo verificable. Lo que no se sabe se marca NO DETERMINADO.

Plantillas: `equipo/plantillas/tarea.md`, `equipo/plantillas/spike.md`, `equipo/plantillas/error.md` y
`equipo/plantillas/hotfix.md`.

## 10. Referencias

- ADR-EQ-008 (definición de terminado), ADR-EQ-001 a ADR-EQ-007
- Lista de expresiones a evitar: `equipo/lenguaje.yaml`

## 11. Regla rápida

> Toda Tarea de deuda, Spike, Error o Hotfix tiene Como/Quiero/Para, criterios de aceptación verificables, la
> evidencia del problema y las secciones de su tipo, en lenguaje técnico y claro. Una Tarea de Producto cuelga de su
> historia y lleva un resumen y la ubicación de su spec.

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en [COHERENCIA.md](../COHERENCIA.md), junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-009.1` | Equipos = Back y combinación válida de tipo de incidencia y campo Tipo | automática | alta |
| `EQ-009.2` | Tiene Como, Quiero y Para, y el Para no repite el Quiero (salvo una Tarea de Producto) | automática + revisión de la historia | media |
| `EQ-009.3` | Tiene al menos un criterio de aceptación medible (en una Tarea de Producto, en su historia) | automática + revisión de la historia | alta |
| `EQ-009.4` | Tiene las secciones obligatorias de su tipo de incidencia | automática | media |
| `EQ-009.5` | Un Spike tiene una sola pregunta, duración máxima y ADR como entregable | automática | alta |
| `EQ-009.6` | Cumple las reglas de lenguaje | automática + revisión de la historia | baja |
