# Decisiones de {{producto}}

ADR del producto (`ADR-{{sigla}}-NNN-<título>.md`), con la plantilla [plantilla.md](plantilla.md). Son el
nivel 4 del orden de autoridad: aplican a este producto y no pueden relajar ni contradecir la
arquitectura ni las decisiones del equipo.

| Paso | Cómo |
|---|---|
| Nace en `Propuesto` | por MR a este repositorio, con el siguiente número libre (`python3 herramientas/harness.py adr`), o desde radiografia |
| Se verifica su coherencia con arquitectura y con las decisiones del equipo | radiografia, sobre la rama del MR; el resultado queda en [COHERENCIA.md](COHERENCIA.md) |
| Se aprueba (`Aprobado`) | MR que cambia el estado, con las aprobaciones configuradas en este repositorio, solo si no hay choques |

- Las **excepciones** (apartarse de una regla, con vencimiento) se crean y se aprueban solo desde
  radiografia.
- Un ADR `Aprobado` no se edita: se crea uno nuevo que lo reemplaza.
- `INDICE.md` y `COHERENCIA.md` los genera radiografia: no se editan a mano.
