# /actualizar: coherencia

La salida tiene una sección por ámbito: `[equipo]` (ADR-EQ frente a arquitectura)
y `[<producto>]` (ADR de producto frente a arquitectura y a los ADR-EQ, que aparecen como
`equipo:ADR-EQ-NNN`). Para cada ámbito con pares por evaluar, escribir **un solo lote** en `.cache/coherencia-<ámbito>.yaml` y registrarlo
con un comando:

```yaml
ambito: equipo                       # o el nombre del producto
resto_sin_relacion: true             # los pares que no se escriben quedan como sin_relacion
pares:
  - decision: ADR-EQ-003
    doc: decision-records:ADR-012
    relacion: compatible
    explicacion: El ADR-EQ agrega los campos obligatorios que arquitectura no detalla.
  - decision: ADR-EQ-002
    doc: decision-records:ADR-010
    relacion: choca
    cita_documento: Los reintentos se configuran solo en el API Gateway
    cita_decision: Los reintentos se aplican en cada cliente HTTP
    criterios: [EQ-002.2]
    explicacion: Arquitectura centraliza los reintentos en el gateway.
```

```sh
.venv/bin/python herramientas/coherencia.py lote .cache/coherencia-<ámbito>.yaml
```

Cómo decidir cada par, en dos etapas:

- **Etapa A, filtro por tema.** Con los títulos y reglas rápidas que muestra la salida, decidir si
  ambos documentos tratan el mismo tema. Los que no, no se escriben: quedan como `sin_relacion`, porque el lote lleva `resto_sin_relacion: true`. Ante la
  duda, pasar a la etapa B.
- **Etapa B, comparación.** Leer los extractos con
  `.venv/bin/python herramientas/coherencia.py extracto <ID> --ambito <ámbito>` (decisión y
  documento), y el documento completo solo si no alcanza. Clasificar:
  - `compatible`: tratan el tema sin contradecirse; la decisión agrega detalle o exige más. Lleva
    una explicación en una frase.
  - `duplica`: la decisión repite lo que arquitectura ya decide.
  - `choca`: la decisión contradice o exige menos que arquitectura. Lleva `criterios`: solo los
    criterios afectados, que quedan suspendidos.

  `duplica` y `choca` exigen las dos citas, copiadas textualmente, y la explicación.

El lote se registra todo o nada: si una cita no aparece en el documento, no se registra nada y se
listan todos los errores. Copiar la cita de nuevo desde el documento, nunca reformularla. Al
registrar, el script regenera el `COHERENCIA.md` del ámbito e informa los pares que quedan.

## Correcciones del usuario

Si el usuario indica que un resultado es incorrecto, registrar de nuevo el par (en un lote o con
`coherencia.py registrar`) con la relación que indica y `manual: "<motivo del usuario>"`. Un choque
no se acepta: se resuelve ajustando el ADR-EQ o con una corrección manual justificada.
