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

Cada comando tiene dos partes. Los **scripts** hacen lo repetible, sin IA y sin gastar tokens. **Cursor** aporta el criterio:
lee, compara y redacta. Lo que sale hacia GitLab o Jira siempre muestra una vista previa y pide confirmación.

### /estado

| Comando | Qué hace |
|---|---|
| `/estado` | Muestra el estado general y qué hacer a continuación |
| `/estado semanal` | Escribe el reporte de lo que cambió en la semana |

**Cuándo:** `/estado` al empezar, o si no sabes qué comando usar. `/estado semanal`, cada semana.

**Cómo lo hace:**

- **`/estado`:** el script `make estado` lee los archivos locales, sin usar la red. Revisa fuentes de arquitectura,
  coherencia, repositorios por revisar, hallazgos sin triar, excepciones vencidas, deuda sin Tarea, commits sin subir en los
  harness y más. Cursor muestra el resultado en orden de prioridad y ofrece ejecutar el primer paso.
- **`/estado semanal`:** el script `make semanal` actualiza las copias de los repositorios y compara con el reporte anterior.

**Qué deja:** `/estado` no escribe nada. `/estado semanal` escribe `productos/<producto>/semanal/<AAAA-Wnn>.md`, con commits,
ramas activas y hallazgos nuevos, corregidos, reaparecidos y vencidos. No publica nada.

### /actualizar

| Comando | Qué hace |
|---|---|
| `/actualizar` | Trae las reglas de arquitectura, verifica su coherencia y las publica en cada harness |

**Cuándo:** cada semana, o al saber que hay reglas nuevas.

**Qué te pide:** la primera vez, los repositorios de arquitectura. Al final, confirmar la publicación.

**Cómo lo hace:**

1. **Scripts (`make actualizar`):** descargan los ADR y estándares de arquitectura, traen los ADR propuestos en cada harness,
   buscan pares nuevos de decisión y documento, actualizan repositorios, terceros, historias y páginas de Confluence, y
   regeneran las reglas de cada harness.
2. **Cursor:** evalúa los pares nuevos, si los hay. Primero filtra por tema, con la regla rápida, y lee más solo si tratan lo
   mismo. Cada par queda como `sin_relacion`, `compatible`, `duplica` o `choca`, con citas textuales. Lo que choca queda
   suspendido.
3. **Scripts (`harness.py subir`):** vuelven a generar las reglas con ese resultado, muestran qué cambió y, si confirmas, lo
   suben a GitLab.

**Qué deja:** `arquitectura/INDICE.md`, `equipo/COHERENCIA.md`, reglas al día en cada harness y un resumen de los cambios.

**Se detiene si:** faltan herramientas del entorno. Un harness con coherencia por evaluar queda retenido y no se sube.

### /producto

| Comando | Qué hace |
|---|---|
| `/producto <nombre>` | Crea el producto con su harness y reúne lo que se va a revisar. Si ya existe, permite administrarlo |

**Cuándo:** al recibir o iniciar un producto, y cuando cambian sus repositorios o documentos.

**Qué te pide:**

- **Producto nuevo:** descripción, origen (`heredado` o `nuevo`) y sigla, que queda fija.
- **De una vez, lo que tengas:** repositorios git, páginas o espacios de Confluence, y documentos en otros formatos.
- **Producto existente:** qué hacer: agregar o retirar repositorios, cargar documentos, registrar terceros o configurar historias.

**Cómo lo hace:**

| Qué entra | Scripts | Cursor |
|---|---|---|
| Repositorio git | Lo inspecciona (rama, stack, Sonar, README, C4, contratos), lo registra y lo descarga en solo lectura | Propone la tabla de registro y pide confirmarla |
| Página o espacio de Confluence | Lo lee en solo lectura y lo convierte a markdown | — |
| PDF, Word, PowerPoint, Excel, HTML o texto | Extrae el texto y lo convierte a markdown | — |
| Dibujo o imagen | Crea un markdown por completar | Mira la imagen y escribe qué muestra |
| Conversación | Crea un markdown por completar | Escribe fecha, decisiones y pendientes, sin copiar el chat |
| Documentos de un tercero | Los indexa en `terceros/<id>/docs/` | Ayuda a completar su ficha |

**Qué deja:** `productos/<producto>/producto.yaml`, el harness en `productos/<producto>/harness/`, los repositorios en
`productos/<producto>/repos/` y los documentos en `documentos/` del harness.

**Paso manual:** crear el repositorio `harness-<producto>` en GitLab y hacer el primer push, con los comandos que muestra
el script.

**Se detiene si:** un repositorio ya está en otro producto, no se puede acceder a él o un documento tiene un posible secreto.
Más detalle en [Productos y terceros](04-productos.md).

### /revisar

| Comando | Qué hace |
|---|---|
| `/revisar <producto> [repo]` | Revisa ese repositorio o, sin indicarlo, el primero pendiente. Si todos están al día, consolida el producto |
| `/revisar mr` | Publica las reglas nuevas y revisa los MR abiertos |
| `/revisar mr --producto <producto>` | Muestra solo los MR de ese producto |
| `/revisar mr --mios` | Muestra solo los MR donde eres revisor. Necesita `GITLAB_USUARIO` en `.env` |

**Cuándo:** `/revisar <producto>` al recibir un producto y cuando cambia la rama principal de un repositorio, con un chat por
repositorio. `/revisar mr`, una o dos veces al día.

**Cómo revisa un repositorio:**

1. **Scripts:** traen las páginas de Confluence que cambiaron y actualizan la copia del repositorio.
2. **Scripts:** detectan el stack, ejecutan gitleaks y las verificaciones automáticas, y consultan Sonar.
3. **Scripts:** arman un paquete con el mapa del repositorio, señales en el código, terceros, documentos del producto y la lista
   de lo que hay que evaluar. Si cambió menos del 40% de los archivos, la revisión es incremental.
4. **Cursor:** lee el paquete, abre el código y los documentos relacionados, y contrasta. Escribe el estado del repositorio y un
   lote con lo que cumple, lo que no aplica, lo no determinado, los hallazgos y los componentes.
5. **Scripts:** validan el lote, rechazan citas o evidencia que no existan, generan los diagramas C4 y calculan el veredicto.

Lo que un documento afirma y el código contradice queda como hallazgo de `documentacion`: manda el código.

Los documentos no se abren completos: Cursor busca con `documentos.py buscar` y lee solo la parte que sirve con
`documentos.py titulos` y `ver`, hasta 150 líneas por vez.

**Cómo consolida el producto:** cuando todos los repositorios están al día, Cursor escribe la visión y las conclusiones, incluido lo
que los documentos describen y no se encontró en ningún repositorio. Los scripts generan el C4 del producto y los cruces.

**Qué deja:** `as-is/<repo>.md`, `as-is/PRODUCTO.md`, los hallazgos con archivo y línea, y el veredicto.

**Cómo revisa los MR:**

1. **Publica las reglas nuevas:** ejecuta `make harness-al-dia` y `harness.py subir`, y pide confirmación si hay cambios.
2. **Muestra la bandeja:** primero las specs, después los ADR y los MR de código.
3. **Revisa el MR elegido:** los scripts repiten las verificaciones con su propio código, detectan cambios sensibles y contrastan
   el MR con `/listo`, la spec y el formato de ramas y commits. Cursor revisa el diff y escribe los hallazgos.
4. **Publica el comentario:** muestra una vista previa y lo publica solo con confirmación.

| MR de la bandeja | Cómo se atiende |
|---|---|
| Spec | Se revisa y se aprueba en GitLab |
| ADR del producto | Los scripts validan el ADR y Cursor evalúa su coherencia, antes de aprobarlo en GitLab |
| Código | Se revisa como en los pasos 3 y 4 |

radiografia no aprueba ni integra MR: eso se hace en GitLab.

### /triar

| Comando | Qué hace |
|---|---|
| `/triar <producto> [repo]` | Registra tu decisión sobre los hallazgos de ese repositorio o, sin indicarlo, de todo el producto |

**Cuándo:** después de revisar.

**Qué te pide:** una decisión por hallazgo. La decisión siempre es tuya: Cursor recomienda solo si se lo pides.

| Decisión | Significado |
|---|---|
| Resolver | Se corrige |
| Conversar | Se decide con el equipo y va a la agenda |
| Deuda | Se acepta con un motivo. Sin fecha, vence a los 90 días |
| Falso positivo | La herramienta o la revisión se equivocó. Exige un motivo |

**Cómo lo hace:**

1. **Scripts:** generan una planilla con los hallazgos pendientes. Primero, las deudas vencidas y los que reaparecieron.
2. **Tú:** marcas una decisión por fila y guardas. También se puede decidir en grupo, con una simulación previa.
3. **Scripts:** aplican la planilla, todo o nada, y calculan qué fuentes generan demasiados falsos positivos.
4. **Cursor:** sugiere qué sigue: llevar la deuda a Jira o ajustar una fuente con ruido.

**Qué deja:** el registro de decisiones, la agenda en `triaje/agenda-<fecha>.md` si hay temas para conversar, y la calibración.

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

**Cómo crea un ADR o una excepción:**

1. **Scripts:** muestran los que existen y crean el archivo en `Propuesto`, con el siguiente número libre.
2. **Cursor:** lo completa contigo, sección por sección. Lo que no sepas queda `NO DETERMINADO`.
3. **Scripts:** lo validan y `/actualizar` verifica su coherencia.
4. **Tú:** lo apruebas: un ADR de producto, por MR a su harness. Una excepción requiere motivo y vencimiento.

**Cómo crea una incidencia de Jira:**

1. **Cursor:** hace las preguntas de su tipo y busca hallazgos e historias parecidas, para no duplicar.
2. **Scripts:** crean el borrador en `historias/borradores/` y el contexto del producto.
3. **Cursor:** redacta el borrador con evidencia.
4. **Scripts:** validan la estructura de `ADR-EQ-009` y el lenguaje, y muestran la vista previa.
5. **Tú:** confirmas y se crea en Jira. La clave queda en el borrador y en los hallazgos de origen.

Las Tareas de desarrollo de una historia no se crean aquí, sino con `/hdu` en el harness o a mano.

## Comandos de `make`

Los objetivos de `make` están en [Mantenimiento](08-mantenimiento.md#objetivos-de-make).
