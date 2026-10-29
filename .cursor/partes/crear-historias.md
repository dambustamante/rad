# /crear: ADR desde historias de usuario (`--desde-historias`)

La mayoría de las historias no implica una decisión de arquitectura: se usan para **proponer**
decisiones a partir de requisitos no funcionales, restricciones y Spikes.

1. `.venv/bin/python herramientas/jira.py sincronizar <producto>` (solo lectura). Si el producto no
   tiene fuente, configurarla (ver "Fuente de historias", abajo).
2. `.venv/bin/python herramientas/jira.py candidatas <producto>`: el script ya filtró sin IA (Spike,
   Deuda Técnica y las que tienen señales de tiempos, disponibilidad, seguridad, resiliencia…).
3. Clasificar en un solo lote, `productos/<producto>/historias/clasificacion-lote.yaml`, y registrar
   con `.venv/bin/python herramientas/jira.py clasificar <producto>`:

   ```yaml
   historias:
     - clave: FRAUD-123
       clasificacion: candidata          # candidata | sin_impacto | choque
       tema: Latencia de evaluación      # agrupa varias historias en un mismo ADR
       cita: La evaluación responde en menos de 150 ms   # copiada tal cual de la historia
       explicacion: Requisito de latencia verificable en el código.
     - clave: FRAUD-140
       clasificacion: choque             # contradice un ADR o estándar vigente
       documento: decision-records:ADR-010
       cita: Los reintentos se hacen en cada servicio
       cita_documento: Los reintentos se configuran solo en el API Gateway
       explicacion: La historia pide algo que arquitectura prohíbe; conversar antes de implementar.
     - clave: FRAUD-151
       clasificacion: sin_impacto
   ```

   Las citas se validan contra la historia y el documento; si hay errores no se registra nada.
4. Mostrar `jira.py propuestas <producto>` (candidatas por tema) y crear solo los ADR que el usuario
   elija, con `--historias`. Los choques se informan aparte: son temas para conversar, no ADR.

Si una historia de origen cambia o se retira, el ADR aparece en `listar` con "revisar: …". Ver el
antes y después en `historias/INDICE.md`: si el ADR sigue vigente,
`jira.py confirmar <producto> --adr <ADR>`; si no, ajustarlo (Propuesto) o reemplazarlo (Aprobado).

## Fuente de historias

Una sola vez por producto:

```sh
.venv/bin/python herramientas/productos.py historias <producto> --fuente jira --jql "project = FRAUD AND labels = motor-fraudes" --campo-tipo Tipo --proyecto FRAUD
.venv/bin/python herramientas/productos.py historias <producto> --fuente archivo --archivo export.csv --campo-tipo Tipo
.venv/bin/python herramientas/productos.py historias <producto> --fuente ninguna
```

Preferir `--jql` a `--tablero`: sigue funcionando aunque el tablero se elimine. Si el proyecto está
archivado, exportar a CSV y usar `--fuente archivo`. `--proyecto` es el destino de las Tareas,
Spikes, Errores y Hotfix.
