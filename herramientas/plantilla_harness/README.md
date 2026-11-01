# harness-{{producto}}

Repositorio de trabajo para desarrollar **{{producto}}** con [Cursor](https://cursor.com). Reúne los
repositorios del producto en `code/` y las reglas que el código debe cumplir. Lo genera y lo revisa
**radiografia**.

**Comandos:** [docs/comandos.md](docs/comandos.md) dice cuál usar en cada caso y qué hace.

Una historia se refina y se divide en **Tareas** de Jira, que cuelgan de ella. Cada Tarea tiene su spec: una página que
dice qué se construirá, cómo se probará y qué reglas aplican.

| Paso | Dónde | Qué pasa |
|---|---|---|
| 1. `/hdu <HISTORIA>` | Harness | Trae la historia, ayuda a refinarla y **propone las Tareas**: título, criterios que cubre y repositorios |
| 2. `/tarea <HISTORIA>` | Harness y Jira | Crea las Tareas propuestas y una spec por cada una. También se pueden crear a mano |
| 3. MR de las Tareas | Harness | Se revisan y se aprueban todas las specs, antes de programar |
| 4. `/desarrollar <TAREA>` | `code/<repo>/` | Crea la rama de código y programa contra la spec aprobada |
| 5. `/listo <TAREA>` | Harness | Verifica que el código cumple la spec |
| 6. MR del código | Repositorio del producto | Se revisa y se aprueba como siempre |
| 7. `/revisar mr` | radiografia | Contrasta el MR con la spec y las reglas |

`/hdu` solo toma una historia si su **Medición HU** es Óptima, Completa o Adecuada, o está vacía. Un Error, un Hotfix, un
Spike o una Tarea sin historia tienen [otro recorrido](docs/comandos.md#casos-distintos).

## Empezar

Requisitos: Python 3.11, `git`, `make`, Cursor, `gitleaks` y un token de Jira con lectura. `/tarea` también necesita permiso para crear incidencias.

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
