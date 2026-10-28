# ADR-EQ-006: Principios de diseño SOLID y KISS

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `27-10-2026`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** el código crece con clases que concentran demasiadas
  responsabilidades, dependencias rígidas que dificultan las pruebas y, en el extremo opuesto,
  abstracciones innecesarias que complican lo simple. Ambos extremos encarecen el mantenimiento.
- **Alcance:** código de los repositorios de tipo `propio`.
- **Restricciones:** los principios de diseño son interpretables. Para que se puedan revisar sin
  discusiones de opinión, se verifican con señales concretas en el código.

## 5. Decisión

1. Se aplica **SOLID** donde existe variación real o prevista:
   - **S**, responsabilidad única: cada clase o módulo tiene un solo motivo para cambiar.
   - **O**, abierto/cerrado: agregar una variante no exige modificar el código existente.
   - **L**, sustitución de Liskov: una implementación puede reemplazar a su abstracción sin
     romper el comportamiento esperado.
   - **I**, segregación de interfaces: ninguna implementación depende de operaciones que no usa.
   - **D**, inversión de dependencias: el dominio depende de abstracciones, no de la
     infraestructura.
2. Se aplica **KISS** (*Keep It Simple*) en todo lo demás: la solución más simple que cumple el
   requisito.
3. **Si ambos principios chocan, prevalece KISS:** una abstracción con una sola implementación y
   sin variación prevista sobra.

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| Sin principios explícitos | Libertad total | Diseño dispar; discusiones recurrentes en revisión | Sin criterio común |
| SOLID estricto en todo el código | Máxima extensibilidad | Sobreingeniería en lo simple | Costo innecesario |
| SOLID donde hay variación y KISS por defecto | Equilibrio verificable | Requiere criterio para identificar la variación | **Elegida** |

## 7. Consecuencias

### Positivas

- Código más fácil de probar, cambiar y entender.
- Revisiones basadas en señales concretas y no en preferencias.

### Negativas o compromisos

- Las señales de diseño requieren criterio; algunas observaciones serán discutibles.

### Riesgos

- Falsos positivos en la revisión automática. Por eso los hallazgos de este ADR no se publican
  en MR hasta calibrarlos (`publicables` en `harness.yaml`).

## 8. Impacto

Revisión de diseño en todos los repositorios de tipo `propio`. No exige cambios inmediatos: los
hallazgos se gestionan como deuda técnica.

## 9. Acciones requeridas

Cada hallazgo de este ADR describe una **señal concreta** con su ubicación. "La clase no cumple
SOLID" no es un hallazgo válido; "la clase mezcla reglas de negocio, acceso a datos y llamadas
HTTP (`ruta:línea`)" sí lo es.

| Principio | Señal a buscar |
|---|---|
| S | Una clase o servicio mezcla reglas de negocio, acceso a datos y llamadas a sistemas externos; clases de gran tamaño o complejidad (Sonar aporta el dato) |
| O | Cadenas de `if` o `switch` por tipo que crecen con cada variante (por ejemplo, por tipo de transacción o de regla) |
| L | Implementaciones que lanzan "operación no soportada" o ignoran el contrato de su abstracción |
| I | Interfaces grandes con implementaciones vacías o que lanzan excepciones |
| D | El dominio crea su infraestructura directamente (`new` de clientes HTTP, repositorios o SDK) |
| KISS | Capas que solo pasan datos, fábricas con un solo producto, genéricos o patrones sin variación que los justifique |

## 10. Referencias

- Robert C. Martin, *Clean Architecture* (principios SOLID)
- ADR de arquitectura sobre estilos y patrones, si existen

## 11. Regla rápida

> Separar responsabilidades y depender de abstracciones donde algo cambia; donde nada cambia, lo
> más simple que funcione.

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en [COHERENCIA.md](../COHERENCIA.md), junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-006.1` | Responsabilidad única (señal S) | revisión de código | media |
| `EQ-006.2` | Abierto/cerrado (señal O) | revisión de código | baja |
| `EQ-006.3` | Sustitución de Liskov (señal L) | revisión de código | media |
| `EQ-006.4` | Segregación de interfaces (señal I) | revisión de código | baja |
| `EQ-006.5` | Inversión de dependencias (señal D) | revisión de código | media |
| `EQ-006.6` | Simplicidad (señal KISS) | revisión de código | baja |
