# harness-{{producto}}

Repositorio de trabajo para desarrollar **{{producto}}** con [Cursor](https://cursor.com). Reúne los
repositorios del producto en `code/` y las reglas que el código debe cumplir. Lo genera y lo revisa
**radiografia**.

**Comandos:** [docs/comandos.md](docs/comandos.md) dice cuál usar en cada caso y qué hace.

Usa un chat nuevo por etapa: gasta menos y la spec ya tiene lo necesario.

Una historia se refina y se divide en **Tareas** de Jira, que cuelgan de ella. Cada Tarea tiene su spec: una página que
dice qué se construirá, cómo se probará y qué reglas aplican.

| Paso | Dónde | Qué pasa |
|---|---|---|
| 1. `/hdu <HISTORIA>` | Harness y Jira | Refina la historia, **propone las Tareas** y, si confirmas, las crea en Jira con una spec por cada una. Las Tareas hechas a mano también se reconocen |
| 2. MR de las Tareas | Harness | Se revisan y se aprueban todas las specs, antes de programar |
| 3. `/desarrollar <TAREA>` | `code/<repo>/` | Crea la rama de código y programa contra la spec aprobada |
| 4. `/listo <TAREA>` | Harness | Verifica que el código cumple la spec |
| 5. MR del código | Repositorio del producto | Se revisa y se aprueba como siempre |
| 6. `/revisar mr` | radiografia | Contrasta el MR con la spec y las reglas |

`/hdu` solo toma una historia si su **Medición HU** es Óptima, Completa o Adecuada, o está vacía. Un Error, un Hotfix, un
Spike o una Tarea sin historia tienen [otro recorrido](docs/comandos.md#casos-distintos).

## Empezar

Requisitos: Python 3.11, `git`, `make`, Cursor, `gitleaks` y un token de Jira con lectura. Para que `/hdu` cree las Tareas, también debe poder crear incidencias.

```sh
cp .env.example .env    # JIRA_URL, JIRA_EMAIL y JIRA_TOKEN
make doctor
make actualizar               # clona los repositorios en code/; ENLAZAR=~/repos reutiliza clones existentes
```

Abrir **esta carpeta** en Cursor, no la de un repositorio.

## Qué no se edita a mano

`.cursor/rules/generado/`, `.cursor/arquitectura/`, los `.json` de la raíz y los índices de `decisiones/` los genera radiografia
y llegan con `make actualizar`. El resto se cambia por MR a este repositorio.

`/hdu`, `/desarrollar` y `/listo` traen solos la última versión de las reglas antes de empezar.

La guardia (`.cursor/hooks.json`) bloquea el push a `main`, el `--force` y aprobar o mergear MR desde
Cursor.

## Decisiones del producto

Viven en `decisiones/` (`ADR-{{sigla}}-NNN`) y nacen en `Propuesto` por MR, por ejemplo al cerrar un
Spike: `python3 herramientas/harness.py adr --titulo "<decisión>" --historia <CLAVE>`. radiografia
verifica su coherencia antes de aprobarlas. Ver [decisiones/README.md](decisiones/README.md).
