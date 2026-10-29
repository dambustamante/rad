# 5. Revisión de un repositorio (`/revisar`)

```
/revisar motor-fraudes [fraude-core]
```

Se revisa **un repositorio por conversación**. Al terminar uno, abrir un chat nuevo para el
siguiente: así no se reenvía el contexto acumulado y el costo se mantiene bajo.

Sin indicar el repositorio, `/revisar` toma el primero pendiente. Un repositorio queda pendiente
si le falta la parte automática, si no tiene revisión de código o si su código cambió desde la
última revisión.

## Paso 1: parte automática (sin IA)

```sh
make revisar P=motor-fraudes R=fraude-core      # SIN_SONAR=1 para omitir Sonar
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

## Paso 2: paquete de revisión

```sh
.venv/bin/python herramientas/revision.py paquete motor-fraudes fraude-core
```

Genera un único archivo con todo lo que Cursor necesita, para no tener que leer el repositorio
completo:

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

Con `--completa` se fuerza una revisión completa.

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

## Paso 5: evaluar y registrar en un solo lote

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
```

```sh
.venv/bin/python herramientas/revision.py registrar motor-fraudes fraude-core
```

Un solo comando para todo el lote, porque cada comando reenvía la conversación y multiplica el
costo. El script valida antes de registrar:

- que los archivos y líneas existan y que el fragmento esté en el código;
- que `cita_documento` aparezca textualmente en el documento, y `cita_tercero` en la documentación
  indexada;
- que un `incumplimiento` tenga cita;
- que todo `NO CUMPLE` tenga al menos un hallazgo de la misma fuente y criterio.

Si hay errores, **no registra nada** y los lista todos juntos. Registrar de nuevo no duplica
hallazgos. Si un problema ya está como issue de Sonar y además incumple un documento de mayor nivel,
se registra en ese nivel y el issue de Sonar queda asociado.

Un buen hallazgo describe una señal concreta en una ubicación concreta: "la clase X mezcla acceso a
datos y llamadas HTTP (`ruta:línea`)", no "no cumple SOLID".

## Paso 6: cerrar

```sh
.venv/bin/python herramientas/revision.py cerrar motor-fraudes fraude-core --archivos-leidos 34
```

El cierre exige que todo esté evaluado, que cada `NO CUMPLE` tenga hallazgo y que el AS IS tenga sus
secciones. Además:

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

Genera `as-is/PRODUCTO.md` con la matriz repositorio × documento, las brechas comunes y la visión
del producto.
