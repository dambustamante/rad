# harness-{{producto}}

Repositorio de trabajo para desarrollar **{{producto}}** con [Cursor](https://cursor.com). Reúne los
repositorios del producto en `code/` y las reglas que el código debe cumplir. Lo genera y lo revisa
**radiografia**.

Una historia se desarrolla en una **Tarea** de Jira, que lleva la spec, el código y las pruebas. Las Tareas cuelgan de
la historia, que puede tener varias, y se crean con `/tarea <HISTORIA>` o a mano. `<CLAVE>` es la clave de la Tarea.

| Paso | Dónde | Qué pasa |
|---|---|---|
| 1. `/hdu <CLAVE>` | Harness | Crea la rama y el borrador de la spec |
| 2. MR de la spec | Harness | Se revisa y se aprueba antes de programar |
| 3. `/desarrollar <CLAVE>` | `code/<repo>/` | Se trabaja contra la spec aprobada |
| 4. `/listo <CLAVE>` | Harness | Verifica que el código cumple la spec |
| 5. MR del código | Repositorio del producto | Se revisa y se aprueba como siempre |
| 6. `/revisar mr` | radiografia | Contrasta el MR con la spec y las reglas |

Una **spec** es una página que dice qué se construirá, cómo se probará y qué reglas aplican. Vive en
`specs/<CLAVE>/spec.md`. `/hdu` solo toma una Tarea si la **Medición HU** de su historia es Óptima, Completa o
Adecuada, o está vacía.

Un Hotfix no espera la aprobación: su spec se completa antes de `/listo`. Un Spike no lleva spec: entrega un ADR.

## Empezar

Requisitos: Python 3.11, `git`, `make`, Cursor, `gitleaks` y un token de Jira con lectura. `/tarea` también necesita permiso para crear incidencias.

```sh
cp .env.example .env    # JIRA_URL, JIRA_EMAIL y JIRA_TOKEN
make doctor
make code               # clona los repositorios en code/; ENLAZAR=~/repos reutiliza clones existentes
```

Abrir **esta carpeta** en Cursor, no la de un repositorio.

## Comandos

| Comando | Cuándo | Qué hace |
|---|---|---|
| `/tarea <HISTORIA>` | si la Tarea no existe | crea en Jira una Tarea que cuelga de la historia, con vista previa y confirmación |
| `/hdu <CLAVE>` | al empezar una Tarea | Medición HU, ramas, foco, contexto y borrador de la spec |
| `/desarrollar <CLAVE>` | con la spec aprobada | comprueba la aprobación y desarrolla contra la spec |
| `/listo <CLAVE>` | antes del MR | verificaciones, pruebas por criterio, deuda y descripción del MR |
| `make actualizar` | al empezar el día | trae la última versión del harness y de los repositorios |
| `make foco [REPOS=a,b]` | si hace falta | repositorios visibles en Cursor; sin `REPOS`, todos |

## Qué no se edita a mano

`.cursor/rules/generado/`, `.cursor/arquitectura/`, los `.json` de la raíz y los índices de `decisiones/` los genera radiografia
y llegan con `make actualizar`. El resto se cambia por MR a este repositorio.

`/hdu`, `/desarrollar` y `/listo` traen solas la última versión de las reglas antes de empezar.

La guardia (`.cursor/hooks.json`) bloquea el push a `main`, el `--force` y aprobar o mergear MR desde
Cursor.

## Decisiones del producto

Viven en `decisiones/` (`ADR-{{sigla}}-NNN`) y nacen en `Propuesto` por MR, por ejemplo al cerrar un
Spike: `python3 herramientas/harness.py adr --titulo "<decisión>" --historia <CLAVE>`. radiografia
verifica su coherencia antes de aprobarlas. Ver [decisiones/README.md](decisiones/README.md).
