# ADR-<ÁMBITO>-NNN: <Título de la decisión>

> `<ÁMBITO>`: `EQ` para una decisión del equipo o la sigla del producto (por ejemplo `MF`).

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `DD-MM-AAAA`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** <qué pasa hoy y por qué es un problema>
- **Alcance:** <a qué productos o repositorios aplica>
- **Restricciones:** <técnicas, regulatorias u operativas>

## 5. Decisión

<Qué se decide, en términos verificables. En una excepción: qué se deja de cumplir, dónde y hasta
cuándo.>

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

<Cómo se cumple la decisión. En una excepción: qué se hará para dejar de necesitarla antes del
vencimiento.>

## 10. Referencias

- 

## 11. Regla rápida

> <Una o dos frases que resumen la decisión.>

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en el `COHERENCIA.md` de su nivel
(`equipo/` o `productos/<producto>/decisiones/`), junto con los criterios que quedan suspendidos si
hay un choque. Un ADR de producto se compara además con las decisiones del equipo. Las excepciones no
se verifican: se apartan de una regla a propósito.

## 13. Criterios de verificación

Solo para decisiones (no para excepciones). Cada criterio tiene un identificador estable
(`<ÁMBITO>-NNN.N`) que nunca se reutiliza ni se renumera.

Columna **Cómo**:

- `automática`: la verifica una herramienta, siempre con el mismo resultado.
- `revisión de código`: requiere leer y entender el código; se reporta con evidencia `ruta:línea`.
  En los ADR de producto todos los criterios son de este tipo.
- `automática + revisión de código`: una herramienta detecta candidatos y la revisión los confirma.
- `revisión de la historia`, `revisión del MR` o `plataforma git`: para decisiones sobre la forma de
  trabajar (historias, MR); no se evalúan en la revisión del código de un repositorio.

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `<ÁMBITO>-NNN.1` | | `automática` \| `revisión de código` | `bloqueante` \| `alta` \| `media` \| `baja` |

## 14. Tipo y alcance (solo ADR de producto; en un ADR-EQ se elimina)

- **Tipo:** decision
- **Repositorios:** todos
- **Criterios exceptuados:** —
- **Vence:** —
- **Referencia de aprobación de arquitectura:** —
- **Historias de origen:** —

Valores:

- **Tipo:** `decision` (regla propia del producto) o `excepcion` (apartarse formalmente de una regla).
- **Repositorios:** `todos` o una lista separada por comas con los `id` de `producto.yaml`.
- **Criterios exceptuados** (solo `excepcion`): criterios de decisiones del equipo o del producto
  (`EQ-001.1`, `MF-002.1`) o documentos de arquitectura (`fuente:ID`).
- **Vence** (solo `excepcion`): fecha `AAAA-MM-DD`. Al vencer, los criterios se vuelven a evaluar.
- **Referencia de aprobación de arquitectura** (solo si exceptúa un documento de arquitectura):
  ticket, acta o correo. Sin ella, la excepción queda registrada pero inactiva.
- **Historias de origen**: claves de Jira (por ejemplo `FRAUD-123`) de las historias que originan la
  decisión. Si una de ellas cambia o se retira, el ADR queda marcado para revisión.
