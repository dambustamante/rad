# ADR-EQ-002: Contratos como código, versionados en el repositorio

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `27-10-2026`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** las APIs y los eventos entre repositorios, productos y terceros se
  documentan de forma dispar o no se documentan. Un cambio en un servicio puede romper a sus
  consumidores sin que nadie lo detecte antes de producción.
- **Alcance:** repositorios de tipo `propio` que exponen o consumen APIs HTTP o eventos.
- **Restricciones:** los contratos deben ser legibles por personas y por herramientas, y
  revisarse en el mismo MR que el código.

## 5. Decisión

1. Toda API HTTP que un repositorio expone tiene su especificación **OpenAPI 3** en el
   repositorio.
2. Todo evento que un repositorio publica o consume tiene su especificación **AsyncAPI** en el
   repositorio.
3. Los contratos siguen **versionado semántico**. Un cambio incompatible exige una versión mayor
   y un período en que conviven la versión anterior y la nueva.
4. Las APIs de terceros o de otros repositorios que se consumen se referencian con su versión.

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| Documentación en wiki o Confluence | Fácil de escribir | Se separa del código y se desactualiza; no es verificable | No es verificable |
| Colecciones Postman | Útiles para probar | No describen el contrato completo ni su compatibilidad | Insuficiente como contrato |
| OpenAPI y AsyncAPI en el repositorio | Estándar de la industria; verificable; versionado con el código | Requiere disciplina para mantenerlo | **Elegida** |

## 7. Consecuencias

### Positivas

- Los consumidores conocen el contrato sin leer el código del proveedor.
- Los cambios incompatibles se detectan en revisión y no en producción.
- Los contratos sirven de base para pruebas de integración y simulaciones (mocks).

### Negativas o compromisos

- Cada cambio de API o de evento exige actualizar el contrato.

### Riesgos

- Contrato y código que divergen. Se mitiga con el criterio `EQ-002.4`.

## 8. Impacto

Los repositorios que exponen APIs o eventos sin contrato deben crearlo. `radiografia` entrega
un borrador inferido del código como punto de partida, marcado para validación.

## 9. Acciones requeridas

**Ubicación:**

```
docs/contratos/openapi.yaml            API expuesta (una por servicio)
docs/contratos/asyncapi.yaml           eventos publicados y consumidos
docs/contratos/consumidos.md           APIs consumidas: nombre, proveedor, versión y enlace
```

Si el framework genera el contrato desde el código (por ejemplo springdoc), el archivo generado
se versiona igual en `docs/contratos/`.

**Contenido mínimo de cada contrato:**

- `info.version` con versión semántica.
- Autenticación (`securitySchemes`).
- Respuestas de error con su esquema y sus códigos.
- Al menos un ejemplo de solicitud y de respuesta por operación.
- Límites de uso y tiempos de respuesta esperados, si existen.

**Compatibilidad:** un cambio es incompatible si elimina o renombra un campo, operación o
evento; agrega un campo obligatorio a una solicitud; o cambia un tipo o un código de respuesta.

## 10. Referencias

- OpenAPI: <https://spec.openapis.org/oas/latest.html>
- AsyncAPI: <https://www.asyncapi.com/docs/reference/specification/latest>
- Versionado semántico: <https://semver.org/lang/es/>

## 11. Regla rápida

> Ningún endpoint ni evento existe sin contrato, y ningún contrato se rompe sin versión mayor.

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en [COHERENCIA.md](COHERENCIA.md), junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-002.1` | Si el repositorio expone APIs HTTP, existe su OpenAPI en `docs/contratos/` | automática + revisión de código | alta |
| `EQ-002.2` | Si el repositorio publica o consume eventos, existe su AsyncAPI en `docs/contratos/` | automática + revisión de código | alta |
| `EQ-002.3` | El contrato tiene el contenido mínimo: versión, autenticación, errores y ejemplos | automática | media |
| `EQ-002.4` | Las operaciones, campos y códigos del contrato coinciden con el código | revisión de código | alta |
| `EQ-002.5` | Las APIs consumidas están referenciadas con su versión en `docs/contratos/consumidos.md` | revisión de código | media |
| `EQ-002.6` | Un cambio incompatible viene con versión mayor (solo al revisar una rama) | revisión de código | alta |
