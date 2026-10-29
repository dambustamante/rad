# 5. Revisión de repositorios y ramas (`/revisar`)

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
- hallazgos automáticos y de Sonar ya registrados (no se repiten);
- **qué evaluar**, por nivel: documentos de arquitectura vigentes, estándares y criterios de
  `revisión de código` de las decisiones del equipo y del producto;
- los elementos exceptuados por una excepción vigente, que no se evalúan.

**Revisión incremental.** Si el repositorio ya tuvo revisión de código y cambió menos del 40% de
sus archivos, el paquete:

- lista los archivos cambiados;
- pide evaluar solo los elementos afectados;
- muestra aparte los heredados, que se conservan solos al cerrar;
- copia el AS IS y los borradores C4 de la revisión anterior, para actualizar solo lo que cambió.

Con `COMPLETA=1` se fuerza una revisión completa. Si la conversación se retoma a mitad de una
revisión, el paquete se regenera sin repetir la parte automática con
`.venv/bin/python herramientas/revision.py paquete <producto> <repo>`.

## Paso 3: AS IS

Cursor lee el código empezando por los manifiestos, los puntos de entrada y los archivos señalados,
y escribe `revisiones/<id>/revision/<repo>-asis.md` con nueve secciones:

1. Propósito
2. Arquitectura real (lo que hay, no lo que debería haber)
3. Componentes y contenedores
4. Integraciones (protocolo, timeouts, reintentos, qué pasa ante una falla)
5. Contratos expuestos y consumidos
6. Datos y datos sensibles
7. Configuración y despliegue (variables solo por nombre)
8. Observabilidad
9. Riesgos y deuda principales (de tres a cinco)

Cada afirmación lleva su etiqueta de evidencia. Para repositorios `proveedor` o `config`, el foco
está en integraciones, contratos y configuración.

## Paso 4: C4 inferido

Borradores de `c4-contexto.md` y `c4-contenedores.md` en Mermaid, en
`revisiones/<id>/borradores/<repo>/`, con las plantillas de `equipo/plantillas/`. Todo sale del
código; lo que no se puede deducir queda `NO DETERMINADO`. Es material para el equipo: nunca se
escribe en el repositorio.

## Paso 5: evaluar en un solo lote

Cursor evalúa cada elemento de "Qué evaluar" y escribe todo en un único archivo,
`revisiones/<id>/revision/<repo>-lote.yaml`:

```yaml
evaluaciones:
  - fuente: decision-records:ADR-010
    criterio: null
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
    categoria: incumplimiento
    severidad: alta
    titulo: Llamada al buró sin timeout
    detalle: Una demora del buró bloquea los hilos del servicio. Configurar timeout de conexión y de respuesta.
    evidencia: [src/main/java/BuroClient.java:41]
    fragmento: |
      return restTemplate.getForObject(url, Respuesta.class);
    cita_documento: Ninguna llamada externa sin timeout explícito
    documento_tercero: terceros/buro-credito/docs/manual.pdf    # opcional
    cita_tercero: Timeout recomendado de 800 ms                 # opcional
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

**Componentes.** La lista `componentes:` es el inventario del repositorio: todo lo que usa o expone,
armado por Cursor y validado por el script (tipo válido, evidencia existente y, si se indica, un
`tercero` con ficha). Queda como tabla en `as-is/<repo>.md` y se consolida en el producto. En una
revisión incremental se incluyen solo los componentes que tocan archivos cambiados o los nuevos; el
resto se hereda.

El lote se registra al cerrar (paso 6), con un solo comando: cada comando reenvía la conversación y
multiplica el costo. Antes de registrar, el script valida:

- que los archivos y líneas existan y que el fragmento esté en el código;
- que `cita_documento` aparezca textualmente en el documento, y `cita_tercero` en la documentación
  indexada;
- que un `incumplimiento` tenga cita;
- que todo `NO CUMPLE` tenga al menos un hallazgo de la misma fuente y criterio.

Si hay errores, **no registra nada** y los lista todos juntos; se corrige el lote y se vuelve a
cerrar, sin duplicar hallazgos. Si un problema ya está como issue de Sonar y además incumple un documento de mayor nivel,
se registra en ese nivel y el issue de Sonar queda asociado.

Un buen hallazgo describe una señal concreta en una ubicación concreta: "la clase X mezcla acceso a
datos y llamadas HTTP (`ruta:línea`)", no "no cumple SOLID".

## Paso 6: cerrar

```sh
.venv/bin/python herramientas/revision.py cerrar motor-fraudes fraude-core --archivos-leidos 34
```

Registra el lote y cierra. Exige que todo esté evaluado, que cada `NO CUMPLE` tenga hallazgo y que el
AS IS tenga sus secciones. Además:

- registra como NO APLICA los criterios exceptuados;
- conserva las evaluaciones heredadas de una revisión incremental;
- informa los avisos de lenguaje;
- actualiza `as-is/<repo>.md` con la comparación por nivel y el **veredicto** (PASA o NO PASA).

## Paso 7: consolidar el producto

Cuando todos los repositorios están al día, `/revisar <producto>` escribe la narrativa del producto
(visión, C4 del producto en Mermaid y conclusiones) y ejecuta:

```sh
.venv/bin/python herramientas/revision.py producto motor-fraudes --narrativa <archivo>
```

Genera `as-is/PRODUCTO.md` con la matriz repositorio × documento, las brechas comunes, la visión del
producto y los **componentes del producto**: cada base, tópico, caché o integración con los
repositorios que lo usan (y si producen o consumen) y su tercero. Además muestra tres cruces:

- integraciones sin ficha en `terceros/` (nadie documentó el acuerdo con ese sistema);
- fichas de `terceros/` que ningún repositorio usa (pueden estar desactualizadas);
- mensajería que solo se produce o solo se consume dentro del producto (puede venir de otro producto).

## Revisión de una rama (`--rama`)

```
/revisar motor-fraudes fraude-core --rama feature/consulta-buro
```

Revisa **solo lo que la rama cambia** y publica el resultado en su MR o PR. Es mucho más barata que
una revisión completa: no hay AS IS ni C4, y no se evalúa cada elemento.

### Paso 1: preparar (sin IA)

```sh
make revisar P=motor-fraudes R=fraude-core RAMA=feature/consulta-buro
```

1. Trae las novedades del repositorio y busca el MR o PR abierto de la rama (si la plataforma git
   está configurada).
2. Calcula el punto común con la rama de destino: la del MR, o la rama principal si no hay MR. Desde
   ahí obtiene los commits y los archivos que la rama cambia.
3. Deja la rama en una copia de solo lectura, `.cache/ramas/<producto>/<repo>/<rama>/`, sin tocar la
   copia de la rama principal.
4. Ejecuta las verificaciones automáticas y gitleaks, y conserva **solo** los hallazgos en archivos
   que la rama cambia y los secretos de sus propios commits. Lo que ya estaba en la rama principal no
   se atribuye a la rama.
5. Escribe el paquete, `revisiones/<fecha>-rama-<repo>-<rama>/paquete.md`, con:
   - commit, base, cantidad de commits y archivos cambiados;
   - el MR: título, destino, descripción y si ya lo aprobó otra persona (EQ-008.2);
   - secretos en los commits de la rama (EQ-008.4);
   - el diff completo (hasta 1500 líneas);
   - hallazgos automáticos en los archivos cambiados;
   - terceros del repositorio;
   - contra qué comparar: la regla rápida de cada documento de arquitectura vigente y los criterios de
     revisión de código agrupados por decisión (el texto de cada criterio está en su ADR).

Sonar no se consulta en ramas, porque SonarQube Community no las analiza: EQ-008.3 queda
`NO DETERMINADO`.

### Paso 2: revisar

Cursor lee el diff (y la copia de la rama solo si hace falta) y escribe en `lote.yaml` los hallazgos
que la rama **introduce o empeora**, con el mismo formato del paso 5. La evidencia debe estar en un
archivo que la rama cambia.

### Paso 3: registrar, elegir qué publicar y ver la vista previa

```sh
.venv/bin/python herramientas/rama.py publicar motor-fraudes fraude-core feature/consulta-buro [--incluir H-0041]
```

Un solo comando registra el lote (con las validaciones habituales; si hay errores no se registra
nada), muestra el veredicto de la rama y arma el comentario. Se publican:

- los hallazgos de la rama marcados **Resolver** en el triaje;
- los que el usuario elija en ese momento, con `--incluir` (quedan triados como Resolver al publicar).

Si ninguno está elegido, el comando lista los hallazgos abiertos de la rama para elegir.

Sin `--confirmar` solo muestra el destino y el comentario completo:

```markdown
## Revisión de la rama `feature/consulta-buro`

Commit `3f2a9c1d8e7b` · 1 hallazgo(s) por resolver.

| Estado | Severidad | Hallazgo | Ubicación | Regla |
|---|---|---|---|---|
| ⏳ pendiente | alta | Llamada al buró sin timeout | [src/main/java/BuroClient.java:41](…) | decision-records:ADR-010 |

<details>
<summary>Detalle</summary>
…
</details>
```

- Los hallazgos de seguridad van primero; después, por severidad.
- Cada ubicación enlaza a la línea en ese commit exacto.
- Nunca se incluyen fragmentos de código ni valores de secretos: solo título, detalle y ubicación.
- La regla de lenguaje **bloquea** la publicación si encuentra avisos: se corrige el título o el
  detalle en el lote y se registra de nuevo.

### Paso 4: publicar

Solo si el usuario lo confirma explícitamente sobre la vista previa, se repite con `--confirmar`.

- Se publica un comentario en el MR o PR. Las publicaciones siguientes **editan el mismo
  comentario**, y lo que se corrigió aparece como ✅.
- **Solo se comentan MR o PR.** Si la rama no tiene uno abierto, no se publica: la revisión queda
  registrada y la vista previa queda en `revisiones/<id>/comentario.md`. Se publica cuando exista el MR.

Para seguir la rama después de nuevos commits, se repiten los pasos: preparar, actualizar el lote y
publicar. Los hallazgos que ya no aparecen quedan corregidos.
