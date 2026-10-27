# ADR-EQ-007: Manejo de logs estructurados y correlacionados

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `27-10-2026`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** cada repositorio registra logs con formato, niveles y contenido
  distintos. Seguir una transacción entre varios servicios exige buscar a mano en cada uno, los
  errores aparecen duplicados o sin contexto, y el volumen innecesario encarece el
  almacenamiento y oculta lo importante.
- **Alcance:** repositorios de tipo `propio`.
- **Restricciones:** los logs se consultan con herramientas de observabilidad que requieren
  formato estructurado. Los datos sensibles se rigen por ADR-EQ-004.

## 5. Decisión

1. **Formato estructurado:** los logs se emiten en JSON, una línea por evento, mediante el
   logger del framework. Nunca con `print`, `System.out`, `console.log` o equivalentes.
2. **Campos obligatorios** en cada evento (ver Acciones requeridas).
3. **Correlación:** cada solicitud o mensaje tiene un identificador de correlación que se
   registra en todos sus logs y se propaga a las llamadas y mensajes salientes.
4. **Niveles con significado único:**
   - `ERROR`: falla que requiere acción de una persona.
   - `WARN`: situación anómala que el sistema resolvió (por ejemplo, un reintento exitoso o una
     degradación aplicada).
   - `INFO`: hitos del negocio o del ciclo de vida (inicio, fin de una operación relevante).
   - `DEBUG`: detalle para diagnóstico; desactivado por defecto en producción.
5. **Excepciones:** una excepción se registra una sola vez, con su traza, en el punto donde se
   maneja. No se registra y se relanza en cada capa.
6. **Datos sensibles:** se aplica ADR-EQ-004 sin excepciones.
7. **Logs técnicos y auditoría son cosas distintas:** los logs sirven para operar y diagnosticar.
   Los registros que exige negocio o auditoría (por ejemplo, la decisión tomada sobre una
   transacción) se guardan en un mecanismo propio y no dependen de los logs.

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| Texto libre | Simple de escribir | No se puede filtrar ni correlacionar de forma confiable | No es consultable |
| Formato definido por cada equipo | Flexibilidad | Imposible seguir una transacción entre servicios | Sin correlación común |
| JSON con campos comunes y correlación | Consultable y correlacionable entre servicios | Requiere configurar el logger en cada repositorio | **Elegida** |

## 7. Consecuencias

### Positivas

- Una transacción se sigue de punta a punta con un solo identificador.
- Las alertas se basan en niveles con significado común.
- Menos volumen y menos costo de almacenamiento.

### Negativas o compromisos

- Configuración inicial del logger y de la propagación de la correlación en cada repositorio.

### Riesgos

- Usar los logs como registro de auditoría. Se mitiga con el punto 7 de la decisión.

## 8. Impacto

Configuración del logger en todos los repositorios de tipo `propio`, propagación de la
correlación en clientes HTTP y de mensajería, y revisión de los niveles usados.

## 9. Acciones requeridas

**Campos obligatorios** (nombres en inglés, compatibles con OpenTelemetry y las herramientas de
observabilidad habituales):

| Campo | Contenido |
|---|---|
| `timestamp` | fecha y hora en ISO 8601, UTC |
| `level` | `ERROR`, `WARN`, `INFO` o `DEBUG` |
| `service` | nombre del servicio |
| `version` | versión desplegada |
| `environment` | entorno (`dev`, `qa`, `prod`) |
| `trace_id` | identificador de correlación de la solicitud o del mensaje |
| `message` | descripción del evento, en español neutro |

Campos recomendados: `span_id`, `operation` (operación de negocio), `duration_ms` y
`error.type` / `error.stack` en los errores.

**Correlación:** se usa el encabezado estándar `traceparent` (W3C Trace Context) cuando el stack
lo soporta. Si no, `X-Correlation-ID`. Si una solicitud llega sin identificador, el servicio
genera uno.

**Volumen:** no se registra en ciclos por elemento con nivel `INFO`, no se registran los
health checks y no se registran cuerpos completos de solicitudes o respuestas.

## 10. Referencias

- W3C Trace Context: <https://www.w3.org/TR/trace-context/>
- OpenTelemetry Logs: <https://opentelemetry.io/docs/specs/otel/logs/>
- ADR-EQ-003 (fallas de integración visibles), ADR-EQ-004 (datos sensibles)

## 11. Regla rápida

> Un log es una línea JSON con su `trace_id`, en el nivel que corresponde, sin datos sensibles,
> y cada error se registra una sola vez.

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en [COHERENCIA.md](COHERENCIA.md), junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-007.1` | Los logs se emiten en JSON con el logger del framework; no hay `print`, `System.out`, `console.log` o equivalentes | automática + revisión de código | media |
| `EQ-007.2` | Los logs incluyen los campos obligatorios | revisión de código | media |
| `EQ-007.3` | El identificador de correlación se registra y se propaga a llamadas y mensajes salientes | revisión de código | media |
| `EQ-007.4` | Los niveles se usan según su significado y `DEBUG` está desactivado por defecto en producción | revisión de código | baja |
| `EQ-007.5` | Cada excepción se registra una sola vez, con su traza, donde se maneja | revisión de código | media |
| `EQ-007.6` | No hay logs de alto volumen innecesarios: ciclos por elemento, health checks o cuerpos completos | revisión de código | baja |
| `EQ-007.7` | Las decisiones sobre transacciones (aprobación, rechazo, revisión manual) y sus motivos se registran en un almacenamiento de auditoría propio, no solo en logs técnicos. `NO APLICA` si otro sistema (por ejemplo, el motor del proveedor) las guarda y está documentado dónde y por cuánto tiempo | revisión de código | alta |
