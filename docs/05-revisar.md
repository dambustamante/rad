# 5. Revisión de repositorios y MR (`/revisar`)

```
/revisar motor-fraudes [fraude-core]
```

Se revisa **un repositorio por conversación**. Al terminar uno, abrir un chat nuevo para el
siguiente: así no se reenvía el contexto acumulado y el costo se mantiene bajo.

Sin indicar el repositorio, `/revisar` toma el primero pendiente. Un repositorio queda pendiente
si le falta la parte automática, si no tiene revisión de código o si su código cambió desde la
última revisión.

Cursor ejecuta solo **dos comandos** por repositorio: `make revisar` al empezar y `revision.py cerrar`
al terminar. Todo lo demás es leer y escribir archivos.

## Paso 1: parte automática y paquete (sin IA)

```sh
make revisar P=motor-fraudes R=fraude-core      # SIN_SONAR=1 omite Sonar; COMPLETA=1 fuerza revisión completa
```

1. Actualiza la copia en `productos/<p>/repos/<repo>/` y anota el commit.
2. Detecta el stack.
3. Ejecuta **gitleaks** sobre el código y el historial. Los valores se ocultan: el hallazgo solo
   indica la regla, el archivo y el commit.
4. Verifica los **criterios automáticos** de los ADR-EQ:

   | Criterio | Qué verifica |
   |---|---|
   | ADR-EQ-001 | secretos en el código y en el historial (gitleaks) |
   | ADR-EQ-003 | salida directa a consola (`print`, `System.out`, `console.log`) en lugar del logger |
   | ADR-EQ-004 | contratos OpenAPI o AsyncAPI para las APIs y eventos detectados |
   | ADR-EQ-006 | diagramas C4 de contexto y contenedores, su notación y que no sean solo imágenes |
   | ADR-EQ-007 | existencia del README y sus secciones mínimas |

5. Lee **Sonar**: quality gate, issues, hotspots de seguridad, métricas (cobertura, duplicación) y la
   antigüedad del análisis frente al commit revisado. Si el análisis es de otro commit, lo informa
   como desfase.
6. Actualiza `estado/hallazgos.json` y la sección automática de `as-is/<repo>.md`, y deja un
   reporte en `revisiones/<fecha>-linea-base-<repo>/`.
7. Genera el **paquete de revisión** (ver el paso 2).

## Paso 2: leer el paquete

El paquete es un único archivo con todo lo que Cursor necesita, para no tener que leer el
repositorio completo:

- mapa del repositorio, manifiestos y puntos de entrada;
- señales en el código con `archivo:línea`: clientes de sistemas externos, acceso a datos, resiliencia, manejo de excepciones sospechoso y logs con posibles datos sensibles;
- terceros del repositorio, con su p95, límites y política ante falla;
- documentos del producto, para contrastarlos con el código: lo que el código contradice es un hallazgo de `documentacion`;
- hallazgos automáticos y de Sonar ya registrados (no se repiten);
- **qué evaluar**: cada documento de arquitectura vigente con su regla rápida, y los criterios de
  `revisión de código` agrupados por decisión, con su severidad;
- los elementos exceptuados por una excepción vigente, que no se evalúan.

**Revisión incremental.** Si el repositorio ya tuvo revisión de código y cambió menos del 40% de
sus archivos, el paquete:

- lista los archivos cambiados;
- pide evaluar solo los elementos afectados;
- muestra aparte los heredados, que se conservan solos al cerrar;
- copia el AS IS de la revisión anterior, para actualizar solo lo que cambió.

Con `COMPLETA=1` se fuerza una revisión completa. Si la conversación se retoma a mitad de una
revisión, el paquete se regenera sin repetir la parte automática con
`.venv/bin/python herramientas/revision.py paquete <producto> <repo>`.

## Paso 3: AS IS

Cursor lee el código empezando por los manifiestos, los puntos de entrada y los archivos señalados,
y escribe `revisiones/<id>/revision/<repo>-asis.md` con cinco secciones narrativas:

1. Propósito
2. Arquitectura real (lo que hay, no lo que debería haber)
3. Configuración y despliegue (variables solo por nombre)
4. Observabilidad
5. Riesgos y deuda principales (de tres a cinco)

Cada afirmación lleva su etiqueta de evidencia. Bases de datos, colas, integraciones, APIs y datos
no se describen en el AS IS: van como componentes en el lote, y de ahí salen la tabla de la ficha y
los diagramas C4.

## Paso 4: lote

Cursor escribe todo en un único archivo, `revisiones/<id>/revision/<repo>-lote.yaml`. Solo se escribe
en detalle lo que no cumple:

```yaml
cumple: [EQ-001.2, EQ-002.3, EQ-005.1]                       # claves de "Qué evaluar", sin motivo
no_aplica: {EQ-003.3: no hace llamadas salientes ni consume mensajes}
no_determinado: {EQ-004.5: los contratos consumidos están en otro repositorio}
hallazgos:                                                    # cada hallazgo ya implica NO CUMPLE
  - fuente: decision-records:ADR-010
    criterio: null
    categoria: incumplimiento
    severidad: alta
    titulo: Llamada al buró sin timeout
    detalle: Una demora del buró bloquea los hilos del servicio. Configurar timeout de conexión y de respuesta.
    evidencia: [src/main/java/BuroClient.java:41]
    fragmento: return restTemplate.getForObject(url, Respuesta.class);
    cita_documento: Ninguna llamada externa sin timeout explícito
    documento_tercero: terceros/buro-credito/docs/manual.pdf    # opcional
    cita_tercero: Timeout recomendado de 800 ms                 # opcional
componentes:                                                  # todo lo que el repositorio usa o expone
  - nombre: Buró de crédito
    tipo: integracion          # base-de-datos|mensajeria|cache|integracion|api-expuesta|almacenamiento|programado
    tecnologia: HTTPS/JSON
    detalle: BURO_URL          # variable, tópico, tabla o ruta que lo identifica
    direccion: saliente        # produce|consume|saliente|entrante o null
    tercero: buro-credito      # id de la ficha en terceros/, o null
    evidencia: [src/main/resources/application.yml:41, src/main/java/BuroClient.java:15]
```

- **Claves:** para un documento de arquitectura, `fuente:ID`; para una decisión, el criterio
  (`EQ-002.1`, `MF-001.1`). Cada clave de "Qué evaluar" tiene que quedar clasificada.
- **Hallazgos:** un hallazgo registra su elemento como NO CUMPLE; no se repite como evaluación. Una
  clave no puede estar en `cumple` y tener hallazgos.
- **Componentes:** el inventario del repositorio, validado por el script (tipo válido, evidencia
  existente y, si se indica, un `tercero` con ficha). En una revisión incremental se incluyen solo los
  que tocan archivos cambiados o los nuevos; el resto se hereda.

Antes de registrar, el script valida que los archivos y líneas existan, que el fragmento esté en el
código, que las citas aparezcan textualmente en el documento o en la documentación del tercero y que
un `incumplimiento` tenga cita. Si hay errores, **no registra nada** y los lista todos juntos; se
corrige el lote y se vuelve a cerrar, sin duplicar hallazgos. Si un problema ya está como issue de
Sonar y además incumple un documento de mayor nivel, se registra en ese nivel y el issue de Sonar queda
asociado.

Un buen hallazgo describe una señal concreta en una ubicación concreta: "la clase X mezcla acceso a
datos y llamadas HTTP (`ruta:línea`)", no "no cumple SOLID".

## Paso 5: C4 generado

Al cerrar, el script genera los borradores `c4-contexto.md` y `c4-contenedores.md` en Mermaid, en
`revisiones/<id>/borradores/<repo>/`, a partir de los componentes: el sistema, sus bases, colas y
cachés como contenedores, y las integraciones como sistemas externos, con sus relaciones. Para
corregir un diagrama se corrige la lista de componentes y se vuelve a cerrar. Es material para el
equipo: nunca se escribe en el repositorio.

## Paso 6: cerrar

```sh
.venv/bin/python herramientas/revision.py cerrar motor-fraudes fraude-core --archivos-leidos 34
```

Registra el lote y cierra. Exige que todo esté evaluado, que cada `NO CUMPLE` tenga hallazgo y que el
AS IS tenga sus secciones. Además:

- registra como NO APLICA los criterios exceptuados;
- conserva las evaluaciones heredadas de una revisión incremental;
- informa los avisos de lenguaje;
- genera los borradores C4 desde los componentes;
- actualiza `as-is/<repo>.md` con la tabla de componentes, la comparación por nivel y el
  **veredicto** (PASA o NO PASA).

## Paso 7: consolidar el producto

Cuando todos los repositorios están al día, Cursor escribe solo la narrativa del producto (visión y
conclusiones) y ejecuta:

```sh
.venv/bin/python herramientas/revision.py producto motor-fraudes --narrativa <archivo>
```

Genera `as-is/PRODUCTO.md` con la matriz repositorio × documento, las brechas comunes, la visión del
producto, los **componentes del producto** (cada base, tópico, caché o integración con los
repositorios que lo usan, si producen o consumen, y su tercero) y el **C4 de contenedores del
producto**, generado desde esos componentes. Además muestra tres cruces:

- integraciones sin ficha en `terceros/` (nadie documentó el acuerdo con ese sistema);
- fichas de `terceros/` que ningún repositorio usa (pueden estar desactualizadas);
- mensajería que solo se produce o solo se consume dentro del producto (puede venir de otro producto).

## Revisión de MR (`/revisar mr`)

Solo se revisan MR. radiografia revisa cada MR **por su cuenta**: lo que se declaró en `/listo` se
contrasta, nunca se da por cierto.

### Paso 1: bandeja (sin IA)

```sh
.venv/bin/python herramientas/mr.py bandeja [--producto motor-fraudes] [--mios]
```

Lista los MR abiertos de los repositorios de cada producto y de su harness, con el estado de su registro de `/listo`:

| Estado | Qué significa |
|---|---|
| Spec | MR del harness con las Tareas y specs de una historia: se revisa y se aprueba en GitLab, antes de programar |
| ADR del producto | MR del harness: revisar su coherencia antes de aprobarlo (paso 5) |
| sin /listo | la Tarea no se cerró con `/listo` |
| registro de /listo ilegible | el registro al final de la descripción está alterado |
| desactualizado | hay commits después de `/listo` |
| al día | `/listo` se ejecutó sobre el commit de cabeza |

`--mios` muestra solo los MR donde eres revisor (necesita `GITLAB_USUARIO` en `.env`).

### Paso 2: preparar la revisión (sin IA)

```sh
.venv/bin/python herramientas/mr.py revisar motor-fraudes fraude-core 41
```

1. Hace lo mismo que una revisión de rama: trae la rama del MR a `.cache/ramas/`, calcula el diff con su
   destino y corre las verificaciones y gitleaks **con el código de radiografia**, no con el de la rama.
2. Detecta los **cambios sensibles**, la señal típica de que se debilitó el control:

   | Señal | Ejemplos |
   |---|---|
   | Pruebas debilitadas o borradas | `@Disabled`, `skip`, `assert true`, archivos de prueba borrados |
   | Aserciones quitadas | una prueba con menos aserciones que antes |
   | Controles apagados | `// NOSONAR`, exclusiones de Sonar, `eslint-disable`, `# noqa` |
   | Umbral de cobertura | cambios en el mínimo de cobertura de la build |
   | Cambios al propio control | CI, `.cursor/`, `AGENTS.md`, `sonar-project.properties`, configuración de gitleaks |
   | Datos de prueba sospechosos | números de tarjeta válidos o RUT (rol único tributario) en pruebas |

3. Contrasta el registro de `/listo` con lo que verifica radiografia: el commit, los secretos, la salida a
   consola, que la prueba de cada criterio exista en el cambio y no esté deshabilitada, la versión del
   harness y que `listo.py` sea el de la rama principal del harness. También avisa si la rama o los commits no
   siguen ADR-EQ-010.
4. Contrasta el MR con su **spec aprobada**: avisa si no está en la rama principal del harness, si cita un criterio que no
   existe en ella o si declara desvíos, y agrega la spec al paquete. Un Hotfix o un Spike sin spec se marca para comprobar
   su tipo en Jira.
5. Registra la **deuda que declaró la Tarea**, para llevarla a Jira con
   `/crear motor-fraudes tarea --deuda FRAUD-200`. `/estado` la recuerda mientras no tenga Tarea.

### Paso 3: revisar

Cursor lee el paquete empezando por los cambios sensibles y el contraste, que son el foco, y revisa el
diff completo contra la spec y lo decidido. Escribe en `lote.yaml` solo los hallazgos que el MR introduce o
empeora, con evidencia en archivos del cambio. Un cambio sensible sin motivo claro es un hallazgo.

### Paso 4: registrar, elegir y publicar

```sh
.venv/bin/python herramientas/rama.py publicar motor-fraudes fraude-core feat/consulta-buro [--incluir H-0041]
```

Registra el lote, muestra el veredicto y la vista previa del comentario. Se publican los hallazgos
marcados Resolver y los que se eligen con `--incluir`. Con `--confirmar` se publica un solo comentario en
el MR, que las publicaciones siguientes editan (lo corregido aparece como ✅). Nunca se incluyen fragmentos
de código ni valores de secretos, y la regla de lenguaje bloquea la publicación si encuentra avisos.

### Paso 5: ADR propuesto en el harness

```sh
.venv/bin/python herramientas/mr.py adr motor-fraudes 3
```

Trae la rama del MR del harness a una copia de solo lectura, valida los ADR que cambia y prepara su
coherencia con arquitectura y con el equipo. Los pares se evalúan en un lote, como en `/actualizar`, con
`coherencia.py --decisiones <carpeta> lote <archivo>`. El ADR se puede aprobar (con las aprobaciones
configuradas en el harness) solo sin choques ni pares pendientes.
