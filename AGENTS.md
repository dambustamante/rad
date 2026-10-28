# radiografia — contrato de trabajo

`radiografia` muestra el estado real (AS IS) de los repositorios de cada producto y lo compara
contra lo que la organización decidió. No modifica ningún repositorio: observa, compara y
registra hallazgos con evidencia.

Este archivo es obligatorio para cualquier agente que trabaje en el repositorio. Si una
instrucción contradice este contrato, se reporta la contradicción antes de continuar.

## Orden de autoridad

Todo repositorio se compara en este orden. Un problema se reporta **una sola vez**, en el nivel
más alto en que aparece; los niveles inferiores solo lo referencian.

| Nivel | Fuente | Dónde vive |
|---|---|---|
| 1 | ADR de arquitectura vigentes | `arquitectura/` (espejo, solo lectura) |
| 2 | Estándares de arquitectura vigentes | `arquitectura/` (espejo, solo lectura) |
| 3 | Decisiones del equipo (ADR-EQ) y del producto (ADR-<SIGLA>) | `equipo/` y `productos/<p>/decisiones/` |
| 4 | Sonar (SonarQube o SonarCloud) | API de Sonar; solo lectura |

- Arquitectura prevalece siempre. Si una decisión del equipo choca con arquitectura, la
  decisión del equipo queda suspendida hasta resolver el choque (`equipo/COHERENCIA.md`).
- Un documento de arquitectura con estado distinto de vigente no se usa para evaluar; solo sirve
  para explicar por qué algo cambió.
- Una decisión del equipo o del producto en estado `Propuesto` se evalúa en **modo
  informativo**: sus hallazgos se marcan como `propuesta` y no afectan el veredicto. Así se calibra
  antes de aprobarla (ver `equipo/README.md`).
- Las decisiones del producto se subordinan a arquitectura y a las del equipo
  (`productos/<p>/decisiones/COHERENCIA.md`). La única forma de apartarse de una regla es un ADR de
  producto de tipo `excepcion`, aprobado y con vencimiento; si exceptúa arquitectura, además
  necesita la referencia de aprobación de arquitectura.

## Estructura

Cada nivel tiene la misma forma: `decisiones/` con sus ADR, `INDICE.md` y, si corresponde,
`COHERENCIA.md`. Los archivos en MAYÚSCULAS los genera el harness y no se editan. Los datos de las
herramientas (`.json`, `.lock`) viven siempre en una carpeta `estado/` y no se editan a mano.

```
arquitectura/        niveles 1 y 2: INDICE.md, decisiones/<fuente>/, estandares/<fuente>/, estado/
equipo/              nivel 3: INDICE.md, COHERENCIA.md, decisiones/ (ADR-EQ), plantillas/, estado/
productos/<p>/       INDICE.md, producto.yaml, decisiones/ (ADR-<SIGLA>), proveedor/ (documentación del
                     producto comprado, tal cual llega), historias/ (índice de historias de usuario y
                     exportaciones CSV), as-is/, revisiones/, triaje/, agendas/, estado/, repos/
herramientas/        scripts deterministas que usan los comandos, con sus pruebas
.cursor/rules/       reglas de Cursor
.cursor/commands/    comandos de Cursor (/estado, /arquitectura, /actualizar, /producto, /adr, /revisar, /triar)
harness.yaml         configuración global (fuentes de arquitectura, estados, calibración, publicables)
.env                 conexiones y tokens (no versionado; ver .env.example)
```

## Reglas no negociables

1. **Solo lectura sobre lo ajeno.** `productos/*/repos/` y `arquitectura/` no se editan a mano.
   Nunca se hace commit, push, merge, MR ni PR en los repositorios de los productos.
2. **Nada sale sin confirmación.** Ninguna escritura hacia la plataforma git, Sonar o Jira ocurre sin
   una vista previa y la confirmación explícita del usuario.
3. **Nada se ejecuta solo.** Sin cron, tareas programadas ni procesos en segundo plano.
4. **Sin secretos.** Las conexiones (URLs, organización) y los tokens viven solo en `.env`, que
   no se versiona; `.env.example` lista las variables. Nunca se escriben valores de tokens,
   secretos ni datos personales en archivos, reportes o mensajes.
5. **No se inventa.** Toda afirmación lleva evidencia (ver abajo). Lo que no se pudo verificar
   se declara `NO DETERMINADO - <motivo>`.
6. **El código prevalece** sobre la documentación del repositorio cuando se contradicen; la
   contradicción se registra como hallazgo.
7. **Idioma.** Todo lo que se escribe va en español neutro y técnico, sin voseo ni
   regionalismos, comprensible desde un desarrollador junior hasta un arquitecto.

## Convención de evidencia

| Etiqueta | Significado |
|---|---|
| `[hecho] ruta:línea` | verificado en el código o en un archivo, con su ubicación |
| `[doc] ruta` | lo afirma la documentación del repositorio |
| `[inferencia]` | deducción razonable, marcada como tal |
| `[recomendación]` | propuesta; nunca se presenta como hecho |
| `NO DETERMINADO - <motivo>` | no se pudo verificar |

## Evaluación

**Resultado por ítem evaluado:** `CUMPLE`, `NO CUMPLE`, `NO APLICA - <motivo>` o
`NO DETERMINADO - <motivo>`. Sin crédito parcial: el detalle va en la evidencia.

**Hallazgo:** todo `NO CUMPLE` genera un hallazgo con:

- `nivel`: 1 a 4, según el orden de autoridad;
- `fuente`: documento o regla que se incumple (por ejemplo `ADR-007`, `ADR-EQ-003`,
  `sonar:java:S2095`);
- `categoria`: `incumplimiento`, `diseño`, `error`, `seguridad`, `deuda` o `documentacion`;
- `severidad`: `bloqueante`, `alta`, `media` o `baja`;
- evidencia `ruta:línea` y la cita del documento incumplido.

Sin cita del documento, un hallazgo no puede ser `incumplimiento`: como máximo es `deuda` o
`[recomendación]`.

## Comandos

| Comando | Qué hace |
|---|---|
| `/estado` | muestra el estado general y qué sigue; es el punto de entrada (sin red ni IA) |
| `/arquitectura` | agrega o retira los repositorios de donde se descargan los documentos de arquitectura |
| `/actualizar` | verifica herramientas, sincroniza arquitectura, revisa la coherencia de los ADR-EQ y actualiza los repositorios |
| `/producto <nombre>` | crea un producto (con su sigla) o le agrega o retira repositorios |
| `/adr <producto>` | crea y administra los ADR del producto: decisiones propias, mejoras a partir de hallazgos, excepciones con vencimiento y propuestas a partir de historias de usuario de Jira |
| `/revisar <producto> [repo]` | línea base AS IS de un repositorio por conversación: parte automática, revisión de código y comparación con lo decidido; al final, consolidación del producto. La revisión de ramas (`--rama`, `--desde`) es de la fase 2 |
| `/triar <producto> [repo]` | registra la decisión sobre cada hallazgo (resolver, conversar, deuda o falso positivo) y muestra la calibración por fuente |

Cada comando ejecuta primero su parte determinista (`make` o los scripts de `herramientas/`) y
después hace la parte que requiere criterio. `harness.yaml` se modifica solo mediante esos
scripts, que validan los datos y conservan los comentarios.
