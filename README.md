# radiografia

Muestra el estado real (AS IS) de los repositorios de cada producto y lo compara, en este orden,
contra:

1. los ADR de arquitectura,
2. los estándares de arquitectura,
3. las decisiones del equipo (ADR-EQ),
4. SonarCloud.

El resultado es una ficha por repositorio y por producto, con hallazgos respaldados por
evidencia. `radiografia` no modifica los repositorios que revisa.

## Requisitos

- macOS con Python 3.11 o superior, `git` y `make`.
- [Cursor](https://cursor.com), para los comandos que requieren criterio.
- Acceso de lectura por git (SSH o HTTPS) a los repositorios de arquitectura y de los productos, en GitLab o GitHub.
- Un token de SonarCloud y, para validar repositorios, un token de la plataforma git.

## Inicio rápido

```sh
cp .env.example .env      # completar conexiones y tokens
make venv                 # crea el entorno de Python
make help                 # lista los comandos disponibles
```

Luego, en Cursor:

```
/arquitectura
/actualizar
/producto <nombre>
/revisar <producto>
/triar <producto>
```

## Estructura

| Carpeta | Contenido |
|---|---|
| `arquitectura/` | copia de los documentos publicados por arquitectura; no se edita |
| `equipo/` | decisiones del equipo (ADR-EQ), coherencia con arquitectura y plantillas |
| `productos/<p>/` | configuración, fichas AS IS, reportes y hallazgos de cada producto |
| `herramientas/` | scripts que usan los comandos |
| `.cursor/` | reglas y comandos de Cursor |

El contrato completo está en [AGENTS.md](AGENTS.md).

## Estado

MVP: `/arquitectura`, `/actualizar`, `/producto`, `/revisar` y `/triar`.

Fase 2: revisión de ramas con publicación en el MR o PR (GitLab o GitHub), reporte semanal, historias de deuda en
Jira y pruebas de integración y de carga.
