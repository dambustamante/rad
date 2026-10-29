# 3. Arquitectura y coherencia (`/actualizar`)

`/actualizar` deja todo al día: herramientas, documentos de arquitectura, coherencia de las
decisiones, repositorios, documentación de terceros, historias de Jira e índices. Conviene
ejecutarlo antes de cada sesión de revisión. `/estado` avisa cuando la copia de arquitectura tiene
más de 7 días.

## Paso 1: registrar las fuentes (`/actualizar fuentes`)

Se hace una vez, y de nuevo cuando arquitectura publica un repositorio nuevo.

1. Cursor muestra las fuentes registradas y pregunta si agregar o retirar.
2. Se le pasan los repositorios, uno por línea: URL SSH o HTTPS de GitLab o GitHub, o una carpeta
   local con un repositorio git.
3. Para cada uno ejecuta `fuentes_arquitectura.py inspeccionar`, que clona en una carpeta temporal
   y cuenta, por carpeta, cuántos documentos hay, cuántos son ADR y cuántos tienen sección Estado.
4. Propone una tabla de fuentes. Un repositorio puede dar varias, por ejemplo una de ADR y otra de
   estándares:

   | id | ref | ruta | tipo | Motivo |
   |---|---|---|---|---|
   | `decision-records` | `main` | `docs/adrs` | `adr` | 24 ADR con sección Estado |
   | `estandares-desarrollo` | `main` | `estandares` | `estandar` | 9 documentos sin Estado |

   Para documentos sin sección Estado (frecuente en estándares) propone
   `estado_por_defecto: vigente`; sin eso quedarían `NO DETERMINADO`.
5. Con la confirmación, `fuentes_arquitectura.py agregar` guarda cada fuente en `harness.yaml`,
   conservando los comentarios.

## Paso 2: parte automática (`make actualizar`)

Encadena, en este orden:

| Paso | Qué hace |
|---|---|
| `doctor` | verifica el entorno; si falta algo obligatorio, se detiene |
| `sync-arquitectura` | clona o actualiza cada fuente (solo git), copia los documentos en `arquitectura/decisiones/<id>/` o `arquitectura/estandares/<id>/`, fija el commit en `arquitectura/estado/fuentes.lock` y genera `arquitectura/INDICE.md` |
| `coherencia` | regenera los `COHERENCIA.md` y lista los pares por evaluar |
| `repos` | actualiza las copias de los repositorios activos de todos los productos |
| `terceros` | vuelve a indexar la documentación de terceros que cambió |
| `historias` | sincroniza las historias de Jira de los productos que las tienen configuradas |
| `indices` | regenera los `INDICE.md` del equipo y de los productos |

**Cómo se lee cada ADR de arquitectura:**

- **ID y título**, del encabezado (`# ADR-010: …`).
- **Estado**, del primer párrafo de la sección "Estado". Se interpreta con `arquitectura.estados` de
  `harness.yaml`: `Aprobado` es vigente; `Propuesto` y `En revisión` están pendientes; `Reemplazado`,
  `Deprecado`, `Rechazado` y `Obsoleto` no están vigentes. Un valor desconocido queda
  `NO DETERMINADO` y `/actualizar` sugiere agregarlo a la lista.
- **Regla rápida y decisión**, que son lo que se compara en la revisión.

**Cambios:** la salida informa las fuentes con commits nuevos y los documentos nuevos,
modificados, eliminados o con cambio de vigencia.

## Paso 3: coherencia

Verifica que las decisiones propias no contradigan lo que tiene más autoridad. Hay un ámbito por
nivel:

- `[equipo]`: cada ADR-EQ frente a cada documento de arquitectura vigente.
- `[<producto>]`: cada ADR del producto frente a arquitectura y a los ADR-EQ.

Solo se evalúan los pares nuevos o los que cambiaron desde la última vez. Para cada par pendiente,
Cursor trabaja en dos etapas.

**Etapa A, filtro por tema.** Con los títulos y reglas rápidas decide si los dos documentos tratan
el mismo tema. Los que no, se registran como `sin_relacion` sin leer más. Ante la duda, pasan a la
etapa B.

**Etapa B, comparación.** Lee los extractos (decisión, regla rápida y criterios) y clasifica:

| Relación | Significado | Exige |
|---|---|---|
| `compatible` | tratan el tema sin contradecirse; la decisión agrega detalle o exige más | una explicación |
| `duplica` | la decisión repite lo que arquitectura ya decide | las dos citas textuales |
| `choca` | la decisión contradice o exige menos que arquitectura | las dos citas y los criterios afectados |

Ejemplo de registro:

```sh
.venv/bin/python herramientas/coherencia.py registrar --ambito equipo --decision ADR-EQ-002 \
  --doc decision-records:ADR-010 --relacion choca \
  --cita-documento "Los reintentos se configuran solo en el API Gateway" \
  --cita-decision "Los reintentos se aplican en cada cliente HTTP" \
  --criterios EQ-002.2 --explicacion "Arquitectura centraliza los reintentos en el gateway."
```

- Las citas se validan contra el texto real de los dos documentos.
- Un `choca` **suspende** los criterios indicados: `/revisar` no los evalúa hasta resolver el choque.
- Un ADR solo puede pasar a Aprobado si su `COHERENCIA.md` no tiene choques ni pares pendientes.
- Si el usuario no está de acuerdo con un resultado, se registra de nuevo con `--manual "<motivo>"`.

## Resultado

| Archivo | Contenido |
|---|---|
| `arquitectura/INDICE.md` | cada documento con su estado, fuente y regla rápida |
| `equipo/COHERENCIA.md` | resultado por ADR-EQ, criterios suspendidos y detalle de cada choque |
| `productos/<p>/decisiones/COHERENCIA.md` | lo mismo para los ADR del producto |
