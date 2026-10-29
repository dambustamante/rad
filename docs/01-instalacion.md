# 1. Instalación

## Requisitos

| Herramienta | Para qué | Instalación |
|---|---|---|
| Python 3.11 o superior | scripts de `herramientas/` | `brew install python` |
| `git` y `make` | sincronización y comandos | incluidos en las herramientas de línea de comandos de macOS |
| Cursor | comandos con criterio (`/revisar`, `/crear`…) | [cursor.com](https://cursor.com) |
| `gitleaks` | buscar secretos en el código y el historial | `brew install gitleaks` |
| `pdftotext` | leer documentación de terceros en PDF | `brew install poppler` |

Además se necesita acceso de lectura por git (SSH o HTTPS) a los repositorios de arquitectura y de
los productos. `radiografia` usa las credenciales de git que ya están configuradas: no pide
usuario ni contraseña.

## Paso 1: entorno de Python

```sh
make venv
```

Crea `.venv/` e instala las dependencias de `requirements.txt` (PyYAML, requests y ruamel.yaml).
Se vuelve a ejecutar solo si cambia `requirements.txt`.

## Paso 2: conexiones y tokens

```sh
cp .env.example .env
```

Completar `.env`. Nunca se versiona y ningún comando muestra sus valores.

| Variable | Obligatoria | Uso |
|---|---|---|
| `SONAR_TIPO` | sí | `sonarqube` (incluida la Community Edition) o `sonarcloud` |
| `SONAR_URL` | sí | por ejemplo `https://sonar.empresa.com` o `https://sonarcloud.io` |
| `SONAR_ORGANIZACION` | solo SonarCloud | clave de la organización |
| `SONAR_TOKEN` | sí | token con permiso de lectura (Browse) sobre los proyectos |
| `JIRA_URL`, `JIRA_EMAIL`, `JIRA_TOKEN` | no | leer historias de usuario y crear Tareas, Spikes y Bugs |
| `GIT_PLATAFORMA`, `GITLAB_*`, `GITHUB_*` | no | revisar ramas con su MR o PR, publicar el comentario y contar MR en el reporte semanal |

Sin Sonar, el nivel 4 queda `NO DETERMINADO` en cada revisión. Sin Jira, no se pueden leer
historias ni crear incidencias. Sin la plataforma git, una rama se revisa contra la rama principal y
no se puede publicar el comentario. El resto funciona igual.

Permisos de los tokens de la plataforma: en GitLab, `api`; en GitHub, pull requests y contents de
lectura y escritura (para comentar el MR o PR y el commit).

## Paso 3: verificar

```sh
make doctor
```

Revisa la versión de Python, las herramientas instaladas, `harness.yaml` y las variables de
`.env` (solo si existen, nunca su valor). Si algo falta, indica cómo instalarlo.

## Paso 4: abrir en Cursor

Abrir la carpeta de `radiografia` en Cursor. Cursor lee `AGENTS.md` (el contrato de trabajo) y las
reglas de `.cursor/rules/`. Los comandos aparecen al escribir `/` en el chat.

Primer comando recomendado: `/estado`. Indica qué hacer a continuación.
