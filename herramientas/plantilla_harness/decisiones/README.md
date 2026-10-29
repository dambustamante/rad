# Decisiones de {{producto}}

ADR del producto (`ADR-{{sigla}}-NNN-<título>.md`), con la plantilla [plantilla.md](plantilla.md).

| Paso | Quién | Cómo |
|---|---|---|
| Nace en `Propuesto` | un dev (por ejemplo, como entregable de un Spike) o el TL desde radiografia | MR a este repositorio, con el siguiente número libre |
| Se verifica su coherencia con arquitectura y con las decisiones del equipo | radiografia | el resultado queda en [COHERENCIA.md](COHERENCIA.md) |
| Se aprueba (`Aprobado`) | un par dev y el TL | MR que cambia el estado, solo si COHERENCIA.md no muestra choques |

- Una decisión del producto nunca relaja ni contradice arquitectura ni las decisiones del equipo.
- Las **excepciones** (apartarse de una regla, con vencimiento) las crea y aprueba solo el TL.
- Un ADR `Aprobado` no se edita: se crea uno nuevo que lo reemplaza.
- `INDICE.md` y `COHERENCIA.md` los genera radiografia: no se editan a mano.
