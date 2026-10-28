# ADR-<SIGLA>-NNN: <Título de la decisión>

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `DD-MM-AAAA`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** <qué pasa hoy y por qué es un problema>
- **Alcance:** <a qué repositorios del producto aplica>
- **Restricciones:** <técnicas, regulatorias u operativas>

## 5. Decisión

<Qué se decide, en términos verificables. En una excepción: qué se deja de cumplir, dónde y hasta
cuándo. En una mejora: qué se propone cambiar.>

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

## 12. Relación con arquitectura y con el equipo

Se verifica automáticamente con `/actualizar` y se registra en `decisiones/COHERENCIA.md`, junto con
los criterios que quedan suspendidos si hay un choque. Las excepciones no se verifican: se apartan de
una regla a propósito.

## 13. Criterios de verificación

Solo para el tipo `decision`. Cada criterio tiene un identificador estable que nunca se reutiliza ni se
renumera. En las decisiones del producto todos los criterios son de `revisión de código`.

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `<SIGLA>-NNN.1` | | revisión de código | `bloqueante` \| `alta` \| `media` \| `baja` |

## 14. Tipo y alcance

- **Tipo:** decision
- **Repositorios:** todos
- **Criterios exceptuados:** —
- **Vence:** —
- **Referencia de aprobación de arquitectura:** —
- **Hallazgos de origen:** —
- **Historias de origen:** —

Valores:

- **Tipo:** `decision` (regla propia del producto), `mejora` (propuesta que nace de hallazgos) o
  `excepcion` (apartarse formalmente de una regla).
- **Repositorios:** `todos` o una lista separada por comas con los `id` de `producto.yaml`.
- **Criterios exceptuados** (solo `excepcion`): criterios de decisiones del equipo o del producto
  (`EQ-001.1`, `MF-002.1`) o documentos de arquitectura (`fuente:ID`).
- **Vence** (solo `excepcion`): fecha `AAAA-MM-DD`. Al vencer, los criterios se vuelven a evaluar.
- **Referencia de aprobación de arquitectura** (solo si exceptúa un documento de arquitectura):
  ticket, acta o correo. Sin ella, la excepción queda registrada pero inactiva.
- **Hallazgos de origen** (solo `mejora`): `H-NNNN` separados por comas.
- **Historias de origen**: claves de Jira (por ejemplo `FRAUD-123`) de las historias que originan la
  decisión. Si una de ellas cambia o se retira, el ADR queda marcado para revisión.
