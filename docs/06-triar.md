# 6. Triaje (`/triar`)

```
/triar motor-fraudes [fraude-core]
```

El triaje registra qué se hace con cada hallazgo. La decisión es siempre del usuario: Cursor puede
recomendar, pero no marca filas por su cuenta.

## Las cuatro decisiones

| Decisión | Significado | Exige | Efecto en el veredicto |
|---|---|---|---|
| Resolver | se corrige; en una rama, va al comentario del MR o PR | — | cuenta |
| Conversar | se decide con el equipo; va a la agenda | — | cuenta |
| Deuda | se acepta como deuda técnica | motivo; sin fecha, vence a los 90 días | no cuenta hasta que vence |
| Falso positivo | la herramienta o la revisión se equivocó | motivo | no cuenta; no reaparece mientras el código no cambie |

## Paso 1 (opcional): decidir en grupo

Para decisiones en bloque, por ejemplo "todo Sonar medio y bajo a deuda", primero se simula:

```sh
.venv/bin/python herramientas/triaje.py grupo motor-fraudes --decision deuda \
  --motivo "Se aborda después de la línea base" --fuente sonar: --severidad media,baja --simular
```

Muestra cuántos y cuáles hallazgos se afectan. Con la confirmación, se ejecuta sin `--simular`.
Filtros disponibles: `--repo`, `--nivel`, `--severidad` y `--fuente` (un prefijo, como `sonar:` o
`EQ-005`).

## Paso 2: generar la planilla

```sh
.venv/bin/python herramientas/triaje.py generar motor-fraudes
```

Escribe `triaje/triaje-<fecha>.md` con una fila por hallazgo pendiente. Primero aparecen los que
requieren atención: deudas vencidas y hallazgos que reaparecieron después de corregirse.

El usuario marca con `x` una decisión por fila, completa el motivo cuando corresponde y guarda. Si
pide ayuda, Cursor lee el detalle y la evidencia y da una recomendación.

## Paso 3: aplicar

```sh
.venv/bin/python herramientas/triaje.py aplicar productos/motor-fraudes/triaje/triaje-<fecha>.md
```

- Se aplica **todo o nada**: si una fila tiene un error (dos decisiones, motivo faltante, fecha
  inválida), no se aplica ninguna y se indica la línea.
- Si hay hallazgos para conversar, genera `triaje/agenda-<fecha>.md`, agrupada por tema, para la
  reunión con el equipo. Lo que se decida en la reunión se registra con un nuevo triaje.

## Paso 4: calibración

Al aplicar, el script muestra la calibración del producto (también se puede pedir con
`.venv/bin/python herramientas/triaje.py calibracion`). Por fuente (un ADR, un criterio o una regla de
Sonar) indica cuántos hallazgos tiene triados y qué porcentaje fue falso positivo. Los umbrales están
en `harness.yaml`:

| Estado | Condición | Qué hacer |
|---|---|---|
| confiable | al menos 5 triados y menos de 20% de falsos positivos | nada |
| ruidosa: ajustar | 20% o más de falsos positivos | revisar los motivos y ajustar la fuente |
| pocos datos | menos de 5 triados | seguir triando |

El ajuste de una fuente ruidosa puede ser precisar el texto del criterio en el ADR-EQ, cambiar su
severidad o, si es una regla de Sonar, desactivarla en el perfil de calidad.

## Paso 5: de la deuda a Jira

Para los hallazgos marcados como Deuda, Cursor ofrece crear una Tarea de Deuda Técnica, agrupando
los del mismo tema:

```
/crear motor-fraudes tarea --desde H-0041,H-0052
```

Ver [Crear ADR, Tareas, Spikes, Errores y Hotfix](07-crear.md).
