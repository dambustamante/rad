# ADR-EQ-003: Integraciones resilientes con política de degradación explícita

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `27-10-2026`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** los productos dependen de sistemas que pueden fallar o responder
  lento: el motor de fraudes, terceros y servicios de otros productos. Sin protección, una
  dependencia lenta agota los recursos del servicio que la llama y la falla se propaga. Además,
  qué ocurre con una transacción cuando el motor o un tercero no responde es una decisión de
  riesgo de negocio que hoy suele quedar implícita en el código.
- **Alcance:** repositorios de tipo `propio` que llaman a sistemas fuera de su propio proceso:
  APIs HTTP, gRPC, colas y servicios de terceros.
- **Restricciones:** la política ante fallas debe ser comprensible para negocio y para
  auditoría, no solo para quien escribió el código.

## 5. Decisión

Toda llamada a un sistema externo cumple:

1. **Timeout explícito** de conexión y de respuesta, definido por configuración.
2. **Reintentos solo en operaciones idempotentes**, con espera exponencial, variación aleatoria
   (jitter) y un máximo de intentos.
3. **Circuit breaker** en las dependencias críticas, para dejar de llamar a un sistema que está
   fallando y recuperarse cuando vuelve.
4. **Política de degradación declarada** para cada integración:
   - *fail-open*: si la dependencia falla, la operación continúa (por ejemplo, la transacción se
     aprueba sin evaluación);
   - *fail-closed*: si la dependencia falla, la operación se rechaza.

   La política se documenta con su justificación de negocio y quién la aprobó.
5. **Fallas visibles:** cada falla se registra en logs (ADR-EQ-007) y métricas, sin datos
   sensibles (ADR-EQ-004). Nunca se ignora una excepción en silencio.

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| Dejar la resiliencia a criterio de cada equipo | Sin costo inicial | Comportamiento distinto en cada integración; decisiones de riesgo implícitas | Riesgo no gestionado |
| Resolverla solo en la infraestructura (service mesh) | Centralizada | No resuelve la política de negocio ni los reintentos seguros | Insuficiente |
| Reglas mínimas en el código y política declarada | Explícito y verificable | Requiere disciplina en cada integración | **Elegida** |

## 7. Consecuencias

### Positivas

- Una dependencia lenta o caída no arrastra al resto del sistema.
- La decisión de qué pasa con una transacción ante una falla queda explícita y auditable.

### Negativas o compromisos

- Cada integración nueva exige definir timeouts, reintentos y política de degradación.

### Riesgos

- Timeouts mal calibrados que cortan operaciones válidas. Se mitiga calibrándolos con las
  pruebas de carga.

## 8. Impacto

Todos los clientes HTTP, gRPC y de mensajería de los repositorios de tipo `propio`. La política
de degradación requiere una conversación con negocio por cada integración crítica.

## 9. Acciones requeridas

- Configurar timeouts y reintentos en el cliente de cada integración, nunca con los valores
  por defecto de la librería sin revisarlos.
- Usar una librería de resiliencia del stack (por ejemplo Resilience4j en Java) en lugar de
  implementaciones propias.
- Documentar cada integración en el README (sección Integraciones) con: sistema, timeout,
  reintentos, circuit breaker y política de degradación con su justificación.
- Reflejar cada integración en el C4 (ADR-EQ-001).

## 10. Referencias

- ADR-EQ-001 (C4), ADR-EQ-004 (datos sensibles), ADR-EQ-007 (logs)
- Patrones *Timeout*, *Retry*, *Circuit Breaker* y *Bulkhead*

## 11. Regla rápida

> Ninguna integración sin timeout, y ninguna caída de un tercero sin una decisión explícita de
> qué pasa con la transacción.

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en [COHERENCIA.md](COHERENCIA.md), junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-003.1` | Cada cliente de un sistema externo tiene timeout explícito de conexión y de respuesta | revisión de código | alta |
| `EQ-003.2` | Los reintentos se aplican solo a operaciones idempotentes, con espera exponencial y máximo de intentos | revisión de código | alta |
| `EQ-003.3` | Las dependencias críticas tienen circuit breaker | revisión de código | media |
| `EQ-003.4` | Cada integración tiene su política de degradación documentada con justificación | revisión de código | alta |
| `EQ-003.5` | Ninguna falla de integración se ignora en silencio (bloques `catch` vacíos o que solo continúan) | revisión de código | alta |
