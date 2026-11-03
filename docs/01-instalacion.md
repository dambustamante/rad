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
| `JIRA_URL`, `JIRA_EMAIL`, `JIRA_TOKEN` | no | crear Tareas de deuda, Spikes, Errores y Hotfix |
| `CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_TOKEN` | no | importar documentos del producto desde Confluence, en solo lectura |
| `CA_BUNDLE` | no | archivo de certificados en formato PEM (Privacy-Enhanced Mail), el texto que empieza con `BEGIN CERTIFICATE`, con las autoridades certificadoras, si la red usa una propia y una conexión falla con `CERTIFICATE_VERIFY_FAILED` |
| `GIT_PLATAFORMA`, `GITLAB_*`, `GITHUB_*` | no | revisar MR o PR y publicar el comentario |

Sin Sonar, el nivel 5 queda `NO DETERMINADO` en cada revisión. Sin Jira, no se pueden crear
incidencias. Sin la plataforma git, no se revisan MR ni se publica el
comentario. El resto funciona igual.

Permisos de los tokens de la plataforma: en GitLab, `api`; en GitHub, pull requests de lectura y
escritura (para leer el PR y comentarlo).

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
