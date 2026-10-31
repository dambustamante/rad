# ADR-EQ-010: Nombres de ramas y mensajes de commit

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `31-10-2026`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** cada persona nombra ramas y commits a su manera. Por eso, cuesta saber qué tipo de
  cambio trae una rama y qué cambió en el historial sin abrir el diff.
- **Alcance:** todos los repositorios de los productos y sus repositorios de trabajo.
- **Restricciones:** usar un estándar conocido y verificable, sin depender de la plataforma git.

## 5. Decisión

Toda rama y todo commit declaran un tipo de cambio. Los tipos válidos son los mismos para ambos:

| Tipo | Cuándo se usa |
|---|---|
| `feat` | Funcionalidad nueva |
| `fix` | Corrección de un error |
| `docs` | Solo documentación |
| `chore` | Mantenimiento que no cambia el comportamiento: dependencias, configuración, construcción |
| `test` | Solo pruebas |
| `refactor` | Cambio interno de código, sin cambiar el comportamiento |

**Ramas:** `<tipo>/<CLAVE>-<descripción-corta>`, en minúsculas y con guiones, salvo la clave de Jira. El tipo es el
mismo del commit que la rama va a llevar. Sin historia de Jira: `<tipo>/<descripción-corta>`.

- `feat/FRAUD-123-consulta-buro`
- `fix/FRAUD-140-timeout-buro`

**Commits:** siguen [Conventional Commits 1.0.0](https://www.conventionalcommits.org/es/v1.0.0/), con la lista de
tipos de esta decisión:

```text
<tipo>[alcance opcional][!]: <descripción>

[cuerpo opcional]

[notas al pie opcionales]
```

- `feat(buro): consulta el puntaje antes de evaluar`
- `fix: define el timeout del cliente del buró`
- `refactor!: cambia el contrato interno de evaluación`

La descripción va en español neutro, en presente y dice qué cambia. El signo `!` marca un cambio incompatible. Una
rama con commits de varios tipos toma el de su objetivo principal.

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| Formato libre | Sin esfuerzo | Historial difícil de leer | Sin criterio común |
| Prefijos `feature/`, `bugfix/` y mensajes libres | Conocido | La rama y el commit usan vocabularios distintos | Dos convenciones que mantener |
| Conventional Commits, con el mismo tipo en la rama | Estándar público y verificable | Requiere aprender seis tipos | **Elegida** |

## 7. Consecuencias

### Positivas

- La rama y el mensaje indican el tipo de cambio sin abrir el diff.
- El formato se puede verificar con una herramienta.

### Negativas o compromisos

- Hay que elegir un tipo en cada commit.
- La lista es más corta que la habitual en Conventional Commits: `build`, `ci`, `perf`, `style` y `revert` no se usan.

### Riesgos

- Elegir un tipo que no corresponde al cambio. El formato se verifica de forma automática; el tipo correcto, en la
  revisión del MR.

## 8. Impacto

Todas las ramas y commits nuevos. El historial anterior no se reescribe.

## 9. Acciones requeridas

- Nombrar las ramas y escribir los commits según esta decisión.
- Corregir el mensaje de los commits de la rama antes de abrir el MR, si no cumplen.

## 10. Referencias

- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/es/v1.0.0/)
- ADR-EQ-008 (definición de terminado)

## 11. Regla rápida

> Las ramas se llaman `<tipo>/<CLAVE>-<descripción-corta>` y los commits siguen Conventional Commits, con el mismo tipo
> en ambos: `feat`, `fix`, `docs`, `chore`, `test` o `refactor`.

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en [COHERENCIA.md](../COHERENCIA.md), junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-010.1` | El nombre de la rama del MR empieza con un tipo válido y sigue el formato | automática + revisión del MR | media |
| `EQ-010.2` | Los mensajes de los commits del MR siguen Conventional Commits con un tipo válido | automática + revisión del MR | media |
| `EQ-010.3` | El tipo de la rama y de los commits corresponde al cambio | revisión del MR | baja |
