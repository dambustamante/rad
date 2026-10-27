# ADR-EQ-004: Protección de datos sensibles en código, logs y pruebas

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `27-10-2026`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** los productos procesan datos de tarjetas, de identificación y de
  clientes. Un dato sensible en un log, en un repositorio o en un archivo de prueba es una
  exposición que no se puede deshacer y un incumplimiento regulatorio.
- **Alcance:** todos los repositorios de tipo `propio`.
- **Restricciones:** normativa de protección de datos personales y requisitos PCI DSS para
  datos de tarjetas.

## 5. Decisión

1. **Logs:** nunca se registran datos sensibles completos. El número de tarjeta (PAN) se
   enmascara y el código de seguridad (CVV) nunca se registra ni se almacena.
2. **Repositorio:** ningún secreto (contraseña, token, clave privada, certificado) vive en el
   repositorio. Se inyectan por variables de entorno o un gestor de secretos.
3. **Pruebas:** solo se usan datos sintéticos. Nunca datos reales de clientes ni de producción.
4. **Respuestas y errores:** los mensajes de error hacia clientes o sistemas externos no
   incluyen datos sensibles ni detalles internos.

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| Confiar en la revisión manual de cada MR | Sin herramientas nuevas | Inconsistente; depende de quién revisa | Insuficiente |
| Enmascarar solo en la plataforma de logs | Centralizado | El dato ya salió del servicio y puede quedar en otros destinos | El dato no debe salir |
| Prohibición en el origen, verificada | Elimina la exposición en su causa | Requiere disciplina y revisión | **Elegida** |

## 7. Consecuencias

### Positivas

- Menor superficie de exposición y menor alcance de auditorías.
- Los logs se pueden compartir para diagnóstico sin riesgo.

### Negativas o compromisos

- Diagnosticar un problema con datos enmascarados puede requerir identificadores alternativos
  (por ejemplo, un identificador de transacción).

### Riesgos

- Datos sensibles en campos no evidentes (por ejemplo, el cuerpo completo de una solicitud).
  Se mitiga con el criterio `EQ-004.3`.

## 8. Impacto

Todos los puntos donde se escriben logs, se manejan errores o se preparan datos de prueba.

## 9. Acciones requeridas

**Datos sensibles y tratamiento:**

| Dato | En logs | Almacenamiento |
|---|---|---|
| PAN (número de tarjeta) | Solo los 4 últimos dígitos (o 6 primeros y 4 últimos) | Según PCI DSS |
| CVV | Nunca | Nunca |
| Fecha de vencimiento de tarjeta | Nunca | Según PCI DSS |
| RUT u otro documento de identidad | Enmascarado | Según normativa |
| Nombre, correo, teléfono, dirección | Nunca | Según normativa |
| Tokens, contraseñas, claves | Nunca | Gestor de secretos |

- No registrar cuerpos completos de solicitudes o respuestas que contengan datos sensibles.
- Usar tarjetas de prueba sintéticas (número válido según el algoritmo de Luhn, de rangos de
  prueba) y documentos de identidad ficticios.
- Mantener `.gitignore` con archivos de configuración local y secretos.
- Al reportar un hallazgo de este tipo, indicar solo la ubicación: nunca copiar el valor.

## 10. Referencias

- PCI DSS (requisito 3, protección de datos de tarjeta almacenados)
- ADR-EQ-003 (logs de fallas de integración), ADR-EQ-007 (manejo de logs)

## 11. Regla rápida

> Un dato sensible nunca se escribe en un log, nunca vive en el repositorio y nunca es real en
> una prueba.

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en [COHERENCIA.md](COHERENCIA.md), junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-004.1` | No hay secretos en el repositorio ni en su historial | automática (gitleaks) | bloqueante |
| `EQ-004.2` | Ningún log registra PAN completo, CVV o fecha de vencimiento | revisión de código | bloqueante |
| `EQ-004.3` | Ningún log registra cuerpos completos de solicitudes o respuestas con datos sensibles, ni datos personales sin enmascarar | revisión de código | alta |
| `EQ-004.4` | Las pruebas y archivos de ejemplo no contienen datos reales | revisión de código | alta |
| `EQ-004.5` | Los mensajes de error externos no incluyen datos sensibles ni trazas internas | revisión de código | alta |
