# harness-{{producto}}

Espacio de trabajo para desarrollar **{{producto}}** con Cursor. Reúne los repositorios del producto
en `code/` y las decisiones que el código debe cumplir, para que cada historia se desarrolle con el
mismo contexto.

## Empezar

```sh
cp .env.example .env    # completar JIRA_URL, JIRA_EMAIL y JIRA_TOKEN (solo lectura) para /hdu
make doctor             # verifica git, Python, gitleaks y que code/ quede fuera de git
make code               # clona los repositorios del producto en code/; ENLAZAR=~/repos reutiliza clones existentes
```

Abrir esta carpeta en Cursor. Cursor lee `AGENTS.md`, las decisiones de
`.cursor/rules/generado/decisiones.mdc` y, al trabajar en `code/<repo>/`, el contexto de ese
repositorio.

## Uso habitual

- `/hdu <CLAVE>` en Cursor para tomar una historia: revisa su Medición HU, crea la rama en cada
  repositorio que toca, deja visibles solo esos repositorios y arma el contexto y el plan.
- Trabajar en `code/<repo>/`, en una rama propia, con el flujo normal de git. El push a la rama
  principal y el `--force` están bloqueados.
- `make foco REPOS=a,b` cambia los repositorios visibles en Cursor; `make foco` vuelve a mostrar todos.
- `make actualizar` trae la última versión de este harness y las novedades de los repositorios, sin
  tocar las ramas de trabajo.

## Qué viene de radiografia

`.cursor/rules/generado/`, `repos.json`, `GENERADO.json` y los índices de `decisiones/` los genera
radiografia, la herramienta del TL. No se editan a mano: los cambios llegan con `make actualizar`.

## Decisiones del producto

Ver [decisiones/README.md](decisiones/README.md).
