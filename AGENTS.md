# radiografia — contrato de trabajo

`radiografia` muestra el estado real (AS IS) de los repositorios de cada producto y lo compara con lo
que se decidió. No modifica ningún repositorio: observa, compara y registra hallazgos con evidencia.
Si una instrucción contradice este contrato, se reporta antes de continuar. Estructura, comandos y
guía paso a paso: [README.md](README.md) y [docs/](docs/README.md).

## Orden de autoridad

| Nivel | Fuente |
|---|---|
| 1 | ADR de arquitectura vigentes (`arquitectura/`, solo lectura) |
| 2 | Estándares de arquitectura vigentes (`arquitectura/`, solo lectura) |
| 3 | Decisiones del equipo (ADR-EQ) y del producto (ADR-<SIGLA>) |
| 4 | Sonar (solo lectura) |

- Un problema se reporta **una sola vez**, en el nivel más alto en que aparece.
- Arquitectura prevalece siempre: una decisión que choca con ella queda suspendida (`COHERENCIA.md`).
- Un documento de arquitectura no vigente no se usa para evaluar.
- Una decisión en `Propuesto` se evalúa en modo `propuesta`: informa, no afecta el veredicto.
- La única forma de apartarse de una regla es un ADR de producto `excepcion`, aprobado y con
  vencimiento (y, si exceptúa arquitectura, con su referencia de aprobación).

## Reglas no negociables

1. **Solo lectura sobre lo ajeno.** `productos/*/repos/`, `.cache/ramas/` y `arquitectura/` no se editan.
   La copia del harness de cada producto (`productos/*/harness/`) sí se escribe, con commit local: el
   push lo hace el usuario.
   Nunca commit, push, merge, MR ni PR en los repositorios de los productos. Lo único que se escribe en
   la plataforma git es el comentario de una revisión de rama en su MR o PR.
2. **Nada sale sin confirmación.** Nada hacia la plataforma git, Sonar o Jira sin vista previa y
   confirmación explícita. La guardia de `.cursor/hooks.json` bloquea las escrituras de git en las
   copias, `glab` o `gh` sobre MR y las escrituras HTTP directas, y pide aprobación para `--confirmar`.
3. **Nada se ejecuta solo.** Sin cron, tareas programadas ni procesos en segundo plano.
4. **Sin secretos.** Conexiones y tokens solo en `.env`. Nunca se escriben valores de tokens,
   secretos ni datos personales.
5. **No se inventa.** Toda afirmación lleva evidencia; lo no verificado es `NO DETERMINADO - <motivo>`.
6. **El código prevalece** sobre la documentación del repositorio; la contradicción es un hallazgo.
7. **Lo determinista lo hacen los scripts** (`make`, `herramientas/`); el agente aporta el criterio.
   Los archivos en MAYÚSCULAS y las carpetas `estado/` los generan los scripts: no se editan a mano.
8. **Lenguaje.** Español neutro y técnico, comprensible de junior a arquitecto: componente, tecnología
   y dato concretos; frases cortas; siglas explicadas; sin voseo, adornos ni muletillas
   (`equipo/lenguaje.yaml`). Lo que va a Jira o a un MR no sale con avisos de lenguaje.

## Evidencia

`[hecho] ruta:línea` (verificado) · `[doc] ruta` (lo dice la documentación) · `[inferencia]` ·
`[recomendación]` (nunca como hecho) · `NO DETERMINADO - <motivo>`.

## Evaluación

- Resultado por elemento: `CUMPLE`, `NO CUMPLE`, `NO APLICA - <motivo>` o `NO DETERMINADO - <motivo>`.
- Todo `NO CUMPLE` es un hallazgo con nivel, fuente y criterio, categoría (`incumplimiento`, `diseño`,
  `error`, `seguridad`, `deuda`, `documentacion`), severidad (`bloqueante`, `alta`, `media`, `baja`) y
  evidencia `ruta:línea`.
- Sin cita del documento incumplido, un hallazgo no puede ser `incumplimiento`.
