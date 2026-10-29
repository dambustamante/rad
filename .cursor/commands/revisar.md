# /revisar

Obtiene la línea base AS IS de los repositorios de un producto y la compara con lo que la
organización decidió, en orden de autoridad: ADR de arquitectura, estándares de arquitectura,
decisiones del equipo (ADR-EQ) y Sonar.

Uso: `/revisar <producto> [repo]`, o `/revisar <producto> <repo> --rama <rama>` para revisar solo lo que
cambia una rama o su MR (ver "Revisar una rama"). Se trabaja **un repositorio por conversación**: al
terminar uno, sugerir abrir un chat nuevo para el siguiente (reduce el costo, porque no se reenvía el
contexto acumulado).

## 1. Elegir el repositorio

```sh
.venv/bin/python herramientas/revision.py pendientes <producto>
```

- Si el usuario indicó un repositorio, usar ese. Si no, tomar el primero que no esté "al día".
- Si todos están al día, ir al paso 7 (producto).

## 2. Preparar: parte automática y paquete

```sh
make revisar P=<producto> R=<repo>        # COMPLETA=1 para forzar una revisión completa
```

Actualiza la copia, ejecuta la parte automática (verificaciones, gitleaks y Sonar) y genera el
paquete de revisión. Si la conversación se retoma a mitad de una revisión, no volver a ejecutarlo:
regenerar solo el paquete con `.venv/bin/python herramientas/revision.py paquete <producto> <repo>`.

Si el repositorio ya tuvo una revisión de código y su código cambió, el paquete es **incremental**:
lista los archivos cambiados, pide evaluar solo los elementos afectados y muestra aparte los
heredados, que se conservan solos al cerrar. El AS IS y los borradores C4 se copian de la revisión
anterior: actualizar solo las partes que el cambio afecta.

Leer el paquete completo antes de abrir cualquier archivo del repositorio. Contiene el mapa del
repositorio, los archivos señalados por patrón, los hallazgos automáticos ya registrados (no
repetirlos) y la lista exacta de lo que hay que evaluar, incluidos los criterios de las decisiones
del producto (`ADR-<SIGLA>-NNN`). Los elementos exceptuados por un ADR del producto vigente aparecen
aparte y no se evalúan: el cierre los registra como NO APLICA.

Leer el código de `productos/<producto>/repos/<repo>/` empezando por los manifiestos, los puntos de
entrada y los archivos señalados. Llevar la cuenta de los archivos leídos: se informa al cerrar.
Nunca modificar nada en esa carpeta. Si se encuentra un secreto, no copiar su valor.

## 3. AS IS

Escribir `productos/<producto>/revisiones/<revisión>/revision/<repo>-asis.md` con estas secciones `##`,
en este orden, cada afirmación con su etiqueta de evidencia (`[hecho] ruta:línea`, `[doc] ruta`,
`[inferencia]`, `NO DETERMINADO - motivo`):

1. **Propósito**: qué hace el repositorio y qué capacidad de negocio soporta.
2. **Arquitectura real**: estilo (por capas, hexagonal, sin estructura clara…), módulos y cómo
   dependen entre sí. Describir lo que hay, no lo que debería haber.
3. **Componentes y contenedores**: aplicaciones, bases de datos, colas y caché, con su tecnología. Cada
   componente va además en la lista `componentes:` del lote (ver el paso 5), que se vuelve la tabla de
   la ficha y el inventario del producto.
4. **Integraciones**: sistemas externos que llama o que lo llaman, con protocolo, timeouts,
   reintentos y qué pasa ante una falla.
5. **Contratos**: APIs y eventos que expone y consume, y dónde están documentados (o que no lo están).
6. **Datos**: qué datos maneja, dónde los guarda y si hay datos sensibles.
7. **Configuración y despliegue**: variables de configuración (solo nombres), empaquetado, CI y
   entornos.
8. **Observabilidad**: logs, métricas, trazas y alertas.
9. **Riesgos y deuda principales**: los tres a cinco puntos más importantes, con su evidencia.

Para un repositorio de tipo `proveedor` o `config`, poner el foco en integraciones, contratos,
configuración y despliegue; el diseño interno se describe solo si es visible y relevante.

## 4. C4 inferido

Escribir los borradores en `productos/<producto>/revisiones/<revisión>/borradores/<repo>/`
(`c4-contexto.md` y `c4-contenedores.md`), con las plantillas de `equipo/plantillas/`. Todo elemento
y relación sale del código; lo que no se pueda deducir se marca como NO DETERMINADO. Es un borrador
para el equipo, no se escribe en el repositorio.

## 5. Evaluar en un solo lote

Para **cada** elemento de la sección "Qué evaluar" del paquete, en orden de nivel, decidir
`CUMPLE`, `NO CUMPLE`, `NO APLICA` (no corresponde a este repositorio) o `NO DETERMINADO` (no se
pudo verificar con el código disponible). Si la regla rápida no alcanza para decidir, leer el
documento (`arquitectura/decisiones/<fuente>/…` o `arquitectura/estandares/<fuente>/…`).

Escribir **todo** en un único archivo,
`productos/<producto>/revisiones/<revisión>/revision/<repo>-lote.yaml`. El cierre lo registra: no usar un
comando por evaluación, porque cada comando reenvía la conversación y multiplica el costo.

```yaml
evaluaciones:
  - fuente: decision-records:ADR-010          # o ADR-EQ-002 / ADR-MF-001 con su criterio
    criterio: null                             # EQ-002.1, MF-001.1…; null para documentos de arquitectura
    resultado: NO CUMPLE
    motivo: El cliente del buró no define timeout.
    evidencia: [src/main/java/BuroClient.java:41]
  - fuente: ADR-EQ-003
    criterio: EQ-003.3
    resultado: NO APLICA
    motivo: El repositorio no hace llamadas salientes ni consume mensajes.
hallazgos:
  - fuente: decision-records:ADR-010
    criterio: null
    categoria: incumplimiento                  # incumplimiento|diseño|error|seguridad|deuda|documentacion
    severidad: alta                            # bloqueante|alta|media|baja
    titulo: Llamada al buró sin timeout
    detalle: Una demora del buró bloquea los hilos del servicio. Configurar timeout de conexión y de respuesta.
    evidencia: [src/main/java/BuroClient.java:41]
    fragmento: |
      return restTemplate.getForObject(url, Respuesta.class);
    cita_documento: Ninguna llamada externa sin timeout explícito
    # opcional, si la evidencia viene de la documentación de un tercero:
    # documento_tercero: terceros/motor/docs/manual.pdf
    # cita_tercero: Timeout recomendado de 800 ms
componentes:                                 # todo lo que el repositorio usa o expone, con evidencia
  - nombre: Buró de crédito
    tipo: integracion                          # base-de-datos|mensajeria|cache|integracion|api-expuesta|almacenamiento|programado
    tecnologia: HTTPS/JSON
    detalle: BURO_URL, timeout no configurado  # variable, tópico, tabla, ruta…: lo que identifica al componente
    direccion: saliente                        # produce|consume|saliente|entrante o null
    tercero: buro-credito                      # id de la ficha en terceros/, o null
    evidencia: [src/main/resources/application.yml:41, src/main/java/BuroClient.java:15]
  - nombre: evaluaciones.resultado
    tipo: mensajeria
    tecnologia: Kafka
    direccion: produce
    evidencia: [src/main/java/Publicador.java:22]
```

Componentes: registrar **todo** lo que el repositorio usa o expone (bases de datos, tópicos y colas,
cachés, integraciones salientes y entrantes, APIs, almacenamiento y procesos programados), cada uno con
evidencia de configuración y, si se puede, de uso en el código. Si una integración corresponde a un
tercero con ficha, indicar su `tercero`; si no tiene ficha, dejar `null` (el producto lo informa como
integración sin ficha).

Reglas del lote:

- El script rechaza archivos o líneas que no existen, fragmentos que no están en el código y citas
  que no están en el documento. Si rechaza algo, volver a copiar el texto desde la fuente: nunca
  reformular para que pase.
- `incumplimiento` exige `cita_documento`. Sin cita, el hallazgo es `diseño`, `error` o `deuda`.
- Si la evidencia viene de la documentación de un tercero (un contrato, un código de error, un tiempo
  o un límite que el código no respeta), agregar `documento_tercero` (`terceros/<id>/docs/<archivo>`)
  y `cita_tercero` (texto copiado tal cual). Para encontrar el texto:
  `.venv/bin/python herramientas/terceros.py buscar <producto> "<palabras>"`.
- Severidad de un criterio de un ADR-EQ: la de su tabla, salvo motivo explícito en el detalle.
- No repetir los hallazgos automáticos ni los de Sonar del paquete. Si un problema ya está como
  issue de Sonar y además incumple un documento de mayor nivel, registrarlo en ese nivel: el script
  asocia el issue de Sonar al hallazgo.
- Un hallazgo describe una señal concreta en una ubicación concreta. "No cumple SOLID" no es un
  hallazgo; "la clase X mezcla acceso a datos y llamadas HTTP (`ruta:línea`)" sí lo es.

## 6. Cerrar

```sh
.venv/bin/python herramientas/revision.py cerrar <producto> <repo> --archivos-leidos <N>
```

Registra el lote y cierra. Si el lote tiene errores, **no se registra nada** y se listan todos juntos:
corregir esas entradas en el mismo archivo y volver a cerrar (no duplica hallazgos). El cierre exige
además que todo esté evaluado, que cada `NO CUMPLE` tenga hallazgo y que el AS IS tenga sus secciones.

Responder con:

```markdown
## Revisión de código de <repo> (<producto>)

**Veredicto:** <PASA / NO PASA, de la ficha>
**Archivos leídos:** <N>

| Nivel | Evaluados | ✅ | ❌ | ➖ | ❔ |
|---|---|---|---|---|---|

### Hallazgos principales
<hasta 8, ordenados por nivel y severidad: ID, fuente o criterio, título, evidencia>

### AS IS en una frase
<resumen>

Siguiente: abrir un chat nuevo y ejecutar `/revisar <producto>` para el próximo repositorio.
```

## 7. Producto

Cuando todos los repositorios están al día:

1. Leer las fichas `productos/<producto>/as-is/<repo>.md` y los borradores C4 de cada repositorio.
2. Escribir un archivo temporal con la narrativa del producto: `## Visión del producto` (qué hace,
   cómo se reparten las responsabilidades entre repositorios), `## C4 del producto (inferido)` con
   los diagramas de contexto y contenedores en Mermaid, y `## Conclusiones` (brechas principales y
   recomendaciones, con referencias a los hallazgos).
3. Ejecutar:

   ```sh
   .venv/bin/python herramientas/revision.py producto <producto> --narrativa <archivo>
   ```

## Revisar una rama (`--rama`)

Solo se revisa lo que la rama cambia respecto de su destino: la rama del MR o PR abierto, o la rama
principal si no hay MR. No hace falta AS IS, C4 ni evaluar cada elemento.

1. **Preparar:**

   ```sh
   make revisar P=<producto> R=<repo> RAMA=<rama>
   ```

   Trae la rama a una copia de solo lectura (`.cache/ramas/`), busca su MR, ejecuta las verificaciones
   automáticas y gitleaks, conserva solo los hallazgos en archivos cambiados y escribe el paquete.
2. **Leer el paquete** (`revisiones/<fecha>-rama-<repo>-<rama>/paquete.md`): archivos cambiados, diff,
   hallazgos automáticos, terceros, contra qué comparar y, si hay MR, su descripción y si ya lo aprobó
   otra persona. Abrir archivos de la copia de la rama solo si el diff no alcanza.
3. **Escribir los hallazgos** que introduce o empeora la rama en `lote.yaml` (solo `hallazgos:`, mismo
   formato que arriba). La evidencia debe estar en un archivo que la rama cambia.
4. **Registrar y elegir qué publicar:**

   ```sh
   .venv/bin/python herramientas/rama.py publicar <producto> <repo> <rama>
   ```

   Registra el lote y muestra el veredicto de la rama. Si ningún hallazgo está marcado Resolver,
   lista los hallazgos abiertos: preguntar al usuario cuáles se piden resolver y repetir con
   `--incluir H-0012,H-0015`. Si el lote tiene errores, no se registra nada: corregirlo y repetir.
5. **Vista previa.** Mostrar el destino (el MR o PR) y el comentario completo. Si hay avisos de
   lenguaje, corregir el título o el detalle de esos hallazgos en el lote y repetir.
6. **Publicar**, solo si el usuario lo confirma explícitamente sobre la vista previa: repetir con
   `--confirmar`. En el MR se crea un solo comentario y las publicaciones siguientes lo editan (los
   corregidos aparecen como ✅). Solo se comentan MR o PR: si la rama no tiene uno abierto, no se
   publica y la vista previa queda en `comentario.md` hasta que exista el MR.

Responder con el veredicto de la rama, los hallazgos principales y dónde se publicó.

## Reglas generales

- No modificar las secciones generadas de las fichas ni la copia de la rama (`.cache/ramas/`).
- Los hallazgos en modo `propuesta` (decisiones del equipo no aprobadas) se informan, pero no
  afectan el veredicto.
