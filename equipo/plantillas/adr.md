# ADR-EQ-NNN: <Título de la decisión>

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `DD-MM-AAAA`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** <qué pasa hoy y por qué es un problema>
- **Alcance:** <a qué repositorios o productos aplica>
- **Restricciones:** <técnicas, regulatorias u operativas>

## 5. Decisión

<Qué se decide, en términos verificables.>

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| | | | |

## 7. Consecuencias

### Positivas

- 

### Negativas o compromisos

- 

### Riesgos

- 

## 8. Impacto

<Qué repositorios, equipos o procesos cambian y cuánto esfuerzo implica.>

## 9. Acciones requeridas

<Detalle técnico de cómo se cumple la decisión: ubicaciones, formatos, ejemplos.>

## 10. Referencias

- 

## 11. Regla rápida

> <Una o dos frases que resumen la decisión y se pueden recordar sin leer el resto.>

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en `equipo/COHERENCIA.md`, junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

Cada criterio tiene un identificador estable que nunca se reutiliza ni se renumera.

Columna **Cómo**:

- `automática`: la verifica una herramienta, siempre con el mismo resultado.
- `revisión de código`: requiere leer y entender el código; se reporta con evidencia `ruta:línea`.
- `automática + revisión de código`: una herramienta detecta candidatos y la revisión los confirma.

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-NNN.1` | | `automática` \| `revisión de código` | `bloqueante` \| `alta` \| `media` \| `baja` |
