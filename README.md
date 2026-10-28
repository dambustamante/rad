# radiografia

Muestra el estado real (AS IS) de los repositorios de cada producto y lo compara, en este orden,
contra:

1. los ADR de arquitectura,
2. los estándares de arquitectura,
3. las decisiones del equipo (ADR-EQ),
4. Sonar (SonarQube, incluida la Community Edition, o SonarCloud).

El resultado es una ficha por repositorio y por producto, con hallazgos respaldados por evidencia
(`ruta:línea` y cita del documento incumplido). `radiografia` no modifica los repositorios que
revisa ni escribe en ningún sistema externo.

## Requisitos

- macOS con Python 3.11 o superior, `git` y `make`.
- [Cursor](https://cursor.com), para los comandos que requieren criterio.
- Acceso de lectura por git (SSH o HTTPS) a los repositorios de arquitectura y de los productos,
  en GitLab o GitHub.
- `gitleaks` (`brew install gitleaks`), para buscar secretos.
- Un token de Sonar con permiso de lectura. El token de la plataforma git se necesita recién en la
  fase 2.

## Primer uso

**1. Preparar el entorno**

```sh
cp .env.example .env      # completar SONAR_TIPO, SONAR_URL y SONAR_TOKEN
make venv                 # crea el entorno de Python
make doctor               # verifica herramientas y configuración (no muestra valores)
```

**2. En Cursor, en este orden**

| Paso | Comando | Qué pasa |
|---|---|---|
| 1 | `/arquitectura` | pide los repositorios de arquitectura, los inspecciona y propone las fuentes |
| 2 | `/actualizar` | descarga los documentos, genera `arquitectura/INDICE.md` y verifica que las decisiones del equipo no choquen con arquitectura (`equipo/COHERENCIA.md`) |
| 3 | `/producto <nombre>` | pide los repositorios del producto, los inspecciona y los registra |
| 4 | `/revisar <producto>` | revisa **un repositorio por conversación**: parte automática, AS IS, comparación con lo decidido y C4 inferido. Abrir un chat nuevo para cada repositorio |
| 5 | `/triar <producto>` | genera un archivo para marcar la decisión sobre cada hallazgo y muestra la calibración |

Cuando todos los repositorios de un producto tienen su revisión, `/revisar` consolida el producto en
`productos/<producto>/as-is/PRODUCTO.md`.

**Recomendación para la primera línea base:** revisar primero dos o tres repositorios
representativos, triar sus hallazgos y medir el consumo de Cursor antes de revisar el resto.

## Uso habitual

- `/actualizar` antes de revisar, para trabajar con la última versión de arquitectura.
- `/producto <nombre>` para agregar o retirar repositorios de un producto.
- `/revisar <producto>` toma el siguiente repositorio pendiente; un repositorio queda pendiente
  cuando su código cambió desde la última revisión.
- `/triar <producto>` después de cada revisión.

## Dónde mirar los resultados

| Archivo | Contenido |
|---|---|
| `productos/<p>/as-is/<repo>.md` | ficha del repositorio: datos, Sonar, AS IS, comparación por nivel y veredicto |
| `productos/<p>/as-is/PRODUCTO.md` | matriz de cumplimiento repositorio × documento, brechas y visión del producto |
| `productos/<p>/reportes/<revisión>/` | reporte de cada revisión, paquetes de revisión y borradores C4 |
| `productos/<p>/hallazgos.json` | registro de hallazgos y decisiones (no se edita a mano) |
| `productos/<p>/agendas/` | hallazgos para conversar con el equipo |
| `equipo/COHERENCIA.md` | coherencia de las decisiones del equipo con arquitectura |
| `arquitectura/INDICE.md` | documentos de arquitectura con su estado y su regla rápida |

## Estructura

| Carpeta | Contenido |
|---|---|
| `arquitectura/` | copia de los documentos publicados por arquitectura; no se edita |
| `equipo/` | decisiones del equipo (ADR-EQ), coherencia con arquitectura y plantillas |
| `productos/<p>/` | configuración, fichas AS IS, reportes, hallazgos, triaje y agendas de cada producto |
| `herramientas/` | scripts deterministas que usan los comandos, con sus pruebas (`make test`) |
| `.cursor/` | reglas y comandos de Cursor |

El contrato de trabajo completo está en [AGENTS.md](AGENTS.md).

## Estado

**MVP:** `/arquitectura`, `/actualizar`, `/producto`, `/revisar` y `/triar`.

**Fase 2:** revisión de ramas (`--rama`, `--desde`) con publicación en el MR o PR (GitLab o GitHub),
reporte semanal, historias de deuda en Jira y pruebas de integración y de carga.
