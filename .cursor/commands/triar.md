# /triar

Registra la decisión del usuario sobre cada hallazgo y muestra la calibración de las fuentes.
Uso: `/triar <producto> [repo]`.

La parte determinista la hace `herramientas/triaje.py`. Nunca editar `productos/<producto>/estado/hallazgos.json` ni
`harness.yaml` a mano en este comando.

## Decisiones

| Decisión | Significado | Exige | Veredicto |
|---|---|---|---|
| Resolver | se corrige; en una rama, va al comentario del MR o PR | — | cuenta |
| Conversar | se decide con el equipo; va a la agenda | — | cuenta |
| Deuda | se acepta como deuda técnica | motivo; sin fecha, vence a los 90 días | no cuenta hasta que vence |
| Falso positivo | la herramienta o la revisión se equivocó | motivo | no cuenta |

## Pasos

1. **Decisiones en grupo (opcional).** Si el usuario quiere decidir en bloque (por ejemplo, "todo Sonar
   medio y bajo a deuda"), simular primero y mostrar cuántos y cuáles hallazgos se afectan:

   ```sh
   .venv/bin/python herramientas/triaje.py grupo <producto> --decision <resolver|a-conversar|deuda|falso-positivo> \
     [--motivo "<motivo>"] [--vence AAAA-MM-DD] [--repo <repo>] [--nivel 1,2,3,4] [--severidad alta,media] \
     [--fuente <prefijo, por ejemplo sonar: o EQ-005>] --simular
   ```

   Con la confirmación del usuario, ejecutar lo mismo sin `--simular`.

2. **Generar el archivo de triaje** con lo que queda pendiente:

   ```sh
   .venv/bin/python herramientas/triaje.py generar <producto> [--repo <repo>]
   ```

   Abrir el archivo generado e indicar al usuario que marque con `x` una decisión por fila, complete
   el motivo cuando corresponda y guarde. Primero aparecen los hallazgos que requieren atención:
   deudas vencidas y hallazgos que reaparecieron después de corregirse.

   Si el usuario pide ayuda con algún hallazgo, leer su detalle en
   `productos/<producto>/as-is/<repo>.md` y la evidencia en el código, y dar una recomendación. La
   decisión es siempre del usuario: no marcar filas por él.

3. **Aplicar**, cuando el usuario lo pida:

   ```sh
   .venv/bin/python herramientas/triaje.py aplicar <archivo>
   ```

   Se aplica todo o nada. Si el script rechaza una fila, mostrar la línea y el motivo, y pedir la
   corrección. Si hay hallazgos para conversar, el script genera la agenda en
   `productos/<producto>/triaje/agenda-<fecha>.md`. Al final muestra la **calibración** por fuente.

4. **Sugerir lo que sigue:**

   - Para los hallazgos marcados como Deuda, ofrecer crear una Tarea de Deuda Técnica con
     `/crear <producto> tarea --desde <ids>`, agrupando los del mismo tema en una sola Tarea.
   - Para las fuentes "ruidosa: ajustar", revisar los motivos de sus falsos positivos y sugerir el
     ajuste concreto: precisar el texto del criterio en el ADR-EQ, cambiar su severidad o, si es una
     regla de Sonar, desactivarla en el perfil de calidad de Sonar.

## Respuesta final

```markdown
## Triaje de <producto>

**Aplicadas:** <N> decisiones (<detalle por decisión>)
**Pendientes:** <N>
**Agenda:** <ruta, si se generó>

### Calibración
<tabla>

### Sugerencias
<fuentes para ajustar y deuda para llevar a Jira>
```
