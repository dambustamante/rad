# 10. Comandos de radiografia

Los comandos que empiezan con `/` se escriben en el chat de Cursor. Los ejemplos usan el producto `motor-fraudes`.
Los comandos del harness (`/hdu`, `/tarea`, `/desarrollar` y `/listo`) están en
[su propia guía](../herramientas/plantilla_harness/docs/comandos.md). Para preparar el entorno, ver
[Instalación](01-instalacion.md).

## Qué comando usar

Son seis comandos. Si no sabes cuál usar, empieza por `/estado`. Cada uno tiene todas sus opciones en
[Detalle de cada comando](#detalle-de-cada-comando).

| Comando | Para qué sirve |
|---|---|
| [`/estado`](#estado) | Saber qué sigue y qué cambió |
| [`/actualizar`](#actualizar) | Traer y publicar las reglas nuevas |
| [`/producto`](#producto) | Registrar y administrar un producto |
| [`/revisar`](#revisar) | Conocer el estado real de un repositorio y revisar MR |
| [`/triar`](#triar) | Decidir qué hacer con los hallazgos |
| [`/crear`](#crear) | Crear un ADR, una excepción o una incidencia de Jira |

## Orden de uso

```text
/actualizar                     Trae y publica las reglas
     ↓
/producto motor-fraudes         Registra el producto y crea su harness
     ↓
/revisar motor-fraudes          Deja el estado y los hallazgos, un chat por repositorio
     ↓
/triar motor-fraudes            Decide qué hacer con cada hallazgo
     ↓
/crear motor-fraudes <tipo>     Crea un ADR o una incidencia de Jira
```

Después: `/estado` y `/revisar mr` cada día; `/estado semanal` y `/actualizar` cada semana.

## Detalle de cada comando

### /estado

| Comando | Qué hace |
|---|---|
| `/estado` | Muestra un resumen y la lista "Qué sigue", por prioridad. Solo lee archivos locales: no usa la red ni gasta análisis |
| `/estado semanal` | Actualiza las copias de los repositorios y escribe `productos/<producto>/semanal/<AAAA-Wnn>.md` con commits, ramas activas y hallazgos nuevos, corregidos y reaparecidos. No publica nada |

**Cuándo:** `/estado` al empezar, o si no se sabe qué comando usar. `/estado semanal` cada semana.

### /actualizar

| Comando | Qué hace |
|---|---|
| `/actualizar` | Trae y publica las reglas, con los pasos de abajo. La primera vez, pide los repositorios de arquitectura |
| `/actualizar fuentes` | Agrega o retira un repositorio de arquitectura en `harness.yaml` |

**Cuándo:** cada semana, o al saber que hay reglas nuevas.

1. Descarga arquitectura y actualiza su índice.
2. Trae los ADR propuestos en cada harness.
3. Compara las decisiones con arquitectura. Si hay pares nuevos, Cursor los evalúa. Lo que choca queda suspendido.
4. Actualiza repositorios, terceros e historias, y regenera las reglas de cada harness.
5. Muestra qué cambió y, con confirmación, lo sube a GitLab (`harness.py subir --confirmar`).

Un harness con coherencia por evaluar queda retenido y no se sube.

### /producto

| Comando | Qué hace |
|---|---|
| `/producto <nombre>` | Si el producto no existe, lo crea con su harness. Si existe, permite administrar sus repositorios y terceros |

**Cuándo:** al recibir o iniciar un producto, y para agregar o retirar repositorios.

- **Producto nuevo:** pide descripción, origen (`heredado` o `nuevo`) y sigla, y crea el producto **con su harness**.
  La sigla queda fija.
- **Producto existente:** permite agregar o retirar repositorios, registrar terceros y configurar historias.
- **Repositorios:** inspecciona cada uno, propone el registro y los agrega solo con confirmación.

**Paso manual:** crear el repositorio `harness-motor-fraudes` en GitLab y hacer el primer push, con los comandos que
muestra el script.

### /revisar

| Comando | Qué hace |
|---|---|
| `/revisar <producto>` | Revisa el primer repositorio pendiente del producto, o consolida el producto si todos están al día |
| `/revisar <producto> <repo>` | Revisa ese repositorio |
| `/revisar mr` | Publica las reglas nuevas y revisa los MR abiertos |
| `/revisar mr --producto <producto>` | Muestra solo los MR de ese producto |
| `/revisar mr --mios` | Muestra solo los MR donde eres revisor. Necesita `GITLAB_USUARIO` en `.env` |

**Cuándo:** `/revisar <producto>` al recibir un producto y cuando cambia la rama principal de un repositorio, con un chat por repositorio. `/revisar mr` una o dos veces al día.

**Revisión de un repositorio:** Ejecuta las verificaciones automáticas y Sonar, y Cursor revisa el código. Deja el estado del repositorio
(`as-is/<repo>.md`), sus hallazgos y su veredicto. Cuando todos están revisados, consolida el producto en
`as-is/PRODUCTO.md`.

**Revisión de MR:**

1. **Publica las reglas nuevas:** ejecuta `make harness-al-dia` y `harness.py subir`, y pide confirmación si hay cambios.
2. **Muestra la bandeja:** primero las specs, después los ADR y los MR de código.
3. **Revisa el MR elegido:** repite las verificaciones con su propio código, detecta cambios sensibles y contrasta el MR
   con `/listo`, la spec y el formato de ramas y commits.
4. **Publica el comentario:** muestra una vista previa y lo publica solo con confirmación.

| MR de la bandeja | Cómo se atiende |
|---|---|
| Spec | Se revisa y se aprueba en GitLab |
| ADR del producto | `mr.py adr <producto> <número>` verifica su coherencia antes de aprobarlo en GitLab |
| Código | `mr.py revisar <producto> <repo> <número>` y `rama.py publicar` |

radiografia no aprueba ni integra MR: eso se hace en GitLab.

### /triar

| Comando | Qué hace |
|---|---|
| `/triar <producto>` | Decide sobre los hallazgos de todo el producto |
| `/triar <producto> <repo>` | Decide sobre los hallazgos de ese repositorio |

**Cuándo:** después de revisar.

| Decisión | Significado |
|---|---|
| Resolver | Se corrige |
| Conversar | Se decide con el equipo y va a la agenda |
| Deuda | Se acepta con un motivo. Sin fecha, vence a los 90 días |
| Falso positivo | La herramienta o la revisión se equivocó. Exige un motivo |

### /crear

| Comando | Qué hace |
|---|---|
| `/crear <producto>` | Pregunta qué crear. No crea nada todavía |
| `/crear <producto> adr` | ADR del producto, en su harness |
| `/crear <producto> adr --desde-historias` | ADR propuestos a partir de historias |
| `/crear <producto> excepcion` | Excepción a una regla, con vencimiento |
| `/crear equipo adr` | ADR del equipo |
| `/crear <producto> tarea` | Tarea de deuda |
| `/crear <producto> tarea --desde H-0041,H-0052` | Tarea de Deuda Técnica desde hallazgos |
| `/crear <producto> tarea --deuda FRAUD-200` | Tarea desde la deuda declarada en `/listo` |
| `/crear <producto> spike` | Spike |
| `/crear <producto> error` | Error |
| `/crear <producto> error --hotfix FRAUD-300` | Error de seguimiento de un Hotfix |
| `/crear <producto> hotfix` | Hotfix |

**Cuándo:** cuando hace falta.

Todo lo que va a Jira muestra una vista previa y se crea solo con confirmación. Las Tareas de desarrollo no se crean
aquí, sino con `/hdu` en el harness o a mano.

Los objetivos de `make` están en [Mantenimiento](08-mantenimiento.md#objetivos-de-make).
