# ADR-EQ-008: Definición de terminado

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `28-10-2026`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** "terminado" significa cosas distintas según quién cierra el trabajo. Se
  mergean cambios sin contrato actualizado, sin diagrama C4 o con hallazgos abiertos, y se detecta
  después, en una revisión o en producción.
- **Alcance:** Tareas, Spikes, Errores y Hotfix del equipo Back.
- **Restricciones:** no duplicar reglas: cada condición remite a la decisión del equipo que la
  define.

## 5. Decisión

Un trabajo está terminado cuando cumple las condiciones base de su tipo y, además, las condiciones
que correspondan según lo que cambió.

**Condiciones base para Tareas y Errores:**

1. Los criterios de aceptación se cumplen y hay pruebas automatizadas que los verifican.
2. El MR fue revisado y aprobado por otra persona del equipo.
3. El quality gate de Sonar está en verde después del merge.
4. No hay secretos ni datos sensibles en el código, los logs ni las pruebas (ADR-EQ-001).
5. Si el trabajo nace de hallazgos de una revisión de código o de arquitectura, la revisión
   siguiente ya no los reporta.

**Condiciones adicionales para Errores:**

1. Hay una prueba automatizada que reproduce el error y que pasa con la corrección.
2. La causa está identificada y documentada en el Error. Si no se pudo determinar, se documenta por
   qué y qué se hizo para mitigarla.
3. Existe al menos una medida que evita que el error se repita sin aviso: una prueba, una alerta o
   un criterio en un ADR.

**Condiciones según lo que cambió (Tareas, Errores y Hotfix):**

| Si el cambio… | Debe cumplir |
|---|---|
| Agrega o modifica una API o un evento | ADR-EQ-004: contrato actualizado y versionado |
| Agrega o modifica un contenedor o una integración | ADR-EQ-002: timeout, reintentos y política ante falla; ADR-EQ-006: C4 actualizado |
| Agrega o modifica logs | ADR-EQ-003: JSON, `trace_id` y nivel correcto |
| Cambia cómo se ejecuta, configura u opera | ADR-EQ-007: README actualizado |
| Cambia el diseño de clases o módulos | ADR-EQ-005: principios SOLID y KISS |
| Toca una decisión del producto (ADR-<SIGLA>) | Los criterios de verificación de esa decisión |

**Condiciones para Hotfix:**

1. La corrección está en producción y el servicio vuelve a funcionar, verificado con el indicador o
   la alerta que detectó la falla.
2. El MR fue revisado y aprobado por otra persona del equipo.
3. No hay secretos ni datos sensibles en el código, los logs ni las pruebas (ADR-EQ-001).
4. Hay un Error de seguimiento creado, que cumple las condiciones de un Error: prueba que reproduce
   la falla, causa documentada y medida que evita que se repita.

**Condiciones para Spikes:**

1. La pregunta tiene respuesta documentada: opciones evaluadas, criterios usados y recomendación.
2. Hay un ADR de producto en estado `Propuesto` con la decisión recomendada.
3. Se respetó la duración máxima de 2 días; si no alcanzó, se documenta qué faltó y por qué.
4. Los riesgos y las dependencias quedaron identificados.

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| Sin definición explícita | Sin esfuerzo | Cada persona decide qué es "terminado" | Criterio dispar |
| Lista completa con todas las reglas escritas | Autocontenida | Duplica los ADR-EQ y se desactualiza | Inconsistencia |
| Condiciones base por tipo + enlace a los ADR-EQ según el cambio | Una sola fuente por regla; corta | Requiere conocer los ADR-EQ | **Elegida** |

## 7. Consecuencias

### Positivas

- Criterio común para cerrar Tareas, Spikes, Errores y Hotfix y para aprobar MR.
- Las condiciones que dependen del código se pueden verificar en la revisión de cada MR.

### Negativas o compromisos

- El trabajo tarda algo más en cerrarse cuando cambian contratos o estructura.

### Riesgos

- Que se trate como trámite. Se mitiga verificando las condiciones en la revisión del MR y no solo
  como una lista.

## 8. Impacto

Todas las Tareas, Spikes, Errores y Hotfix del equipo Back. Las plantillas de Tarea, Spike, Error y Hotfix enlazan a este
ADR en lugar de repetir la lista.

## 9. Acciones requeridas

- Las plantillas de Tarea, Spike, Error y Hotfix (ADR-EQ-009) enlazan a este ADR.
- En la revisión de cada MR se indica qué condiciones se cumplen y cuáles faltan.

## 10. Referencias

- ADR-EQ-001 a ADR-EQ-007, ADR-EQ-009

## 11. Regla rápida

> Terminado es: criterios probados, MR aprobado por otra persona, Sonar en verde, sin secretos y las
> decisiones del equipo que aplican a lo que cambió, cumplidas. Un Error, además, tiene su prueba de
> reproducción y su causa documentada; un Hotfix deja un Error de seguimiento; un Spike termina con un
> ADR propuesto.

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en [COHERENCIA.md](../COHERENCIA.md), junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-008.1` | Los criterios de aceptación tienen pruebas que los verifican | revisión del MR | alta |
| `EQ-008.2` | El MR fue aprobado por otra persona | plataforma git | alta |
| `EQ-008.3` | Quality gate de Sonar en verde | automática | alta |
| `EQ-008.4` | Sin secretos (remite a EQ-001.1) | automática | bloqueante |
| `EQ-008.5` | Los hallazgos de origen ya no se reportan | automática | alta |
| `EQ-008.6` | Se cumplen los ADR-EQ que aplican según lo que cambió | automática + revisión del MR | según el ADR-EQ |
| `EQ-008.7` | Un Error tiene una prueba que reproduce la falla y su causa documentada | revisión del MR | alta |
| `EQ-008.8` | Un Spike deja un ADR de producto en estado Propuesto | automática | alta |
| `EQ-008.9` | Un Hotfix tiene un Error de seguimiento creado | automática | alta |
