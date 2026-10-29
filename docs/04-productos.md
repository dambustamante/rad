# 4. Productos y terceros (`/producto`)

## Crear un producto

```
/producto motor-fraudes
```

1. Si el producto no existe, Cursor pide una descripción de una frase y lo crea en
   `productos/motor-fraudes/producto.yaml`.
2. El script le asigna una **sigla** para numerar sus ADR (`MF` → `ADR-MF-001`). Se puede cambiar
   mientras el producto no tenga ADR:

   ```sh
   .venv/bin/python herramientas/productos.py sigla motor-fraudes --asignar MFR
   ```

## Agregar repositorios

1. Se pasan los repositorios, uno por línea (URL SSH o HTTPS, o carpeta local).
2. `productos.py inspeccionar` clona cada uno en una carpeta temporal y detecta: rama por defecto,
   último commit, stack, clave de Sonar (de `sonar-project.properties`, `pom.xml` o similares),
   README, diagramas C4 y contratos.
3. Cursor propone una tabla para confirmar:

   | id | rama | Stack | Sonar | README | C4 | Contratos | Tipo |
   |---|---|---|---|---|---|---|---|
   | `fraude-core` | `main` | Java 21, Spring Boot | `fraude-core` | ✅ | ❌/❌ | 1 | propio |

   | Tipo | Cuándo | Qué se le exige |
   |---|---|---|
   | `propio` | código del equipo | todas las decisiones |
   | `proveedor` | código de un tercero | foco en integraciones, contratos y configuración; no se le exige C4 |
   | `config` | configuración o infraestructura | foco en configuración y despliegue |

4. Con la confirmación, `productos.py agregar` registra cada repositorio y `productos.py
   sincronizar` lo descarga en `productos/<p>/repos/<id>/`. Esa carpeta es de solo lectura y está
   fuera de git.

Un repositorio solo puede estar en un producto. Para **retirarlo** se indica el motivo: queda
marcado como retirado, con fecha, y se conserva su historial de hallazgos.

## Terceros: producto comprado e integraciones

El producto comprado y cada sistema externo (buró, red de tarjetas, listas de sanciones, otro
producto…) se registran igual, en `productos/<p>/terceros/<id>/`:

```
terceros/
├── INDICE.md                 estado de cada ficha y documentos sin indexar (generado)
└── buro-credito/
    ├── ficha.yaml            datos del tercero
    └── docs/                 documentación tal como llega, en subcarpetas si se quiere
        └── INDICE.md         documentos indexados y contratos reconocidos (generado)
```

### Paso 1: crear la ficha

```sh
.venv/bin/python herramientas/terceros.py nuevo motor-fraudes --id motor --nombre "Motor de fraudes" --rol producto-comprado
.venv/bin/python herramientas/terceros.py nuevo motor-fraudes --id buro-credito --nombre "Buró de crédito"
```

El rol es `producto-comprado` o `integracion` (por defecto).

### Paso 2: copiar e indexar la documentación

Se copian los archivos tal como llegan en `terceros/<id>/docs/` y se indexan:

```sh
.venv/bin/python herramientas/terceros.py indexar motor-fraudes
```

| Formato | Cómo se lee |
|---|---|
| PDF | `pdftotext`, con número de página para citar |
| Word, PowerPoint, Excel (`.docx`, `.pptx`, `.xlsx`) | texto interno del archivo |
| HTML | texto visible, sin scripts ni estilos |
| markdown, texto, YAML, JSON | tal cual |
| OpenAPI y AsyncAPI | se reconocen por su contenido: título, versión y cantidad de operaciones |
| `.doc`, `.ppt`, `.xls` antiguos | no se leen: guardarlos como `.docx`, `.pptx` o `.xlsx`, o como PDF |
| imágenes y PDF escaneados | no tienen texto: pedir una versión con texto |

- Los originales nunca se modifican.
- Solo se vuelve a procesar lo que cambió; los archivos borrados salen del índice.

### Paso 3: completar la ficha

Cursor propone los valores buscando en la documentación indexada y citando de dónde sale cada uno:

```sh
.venv/bin/python herramientas/terceros.py buscar motor-fraudes "timeout 800"
```

```yaml
id: buro-credito
nombre: Buró de crédito
rol: integracion               # producto-comprado | integracion
proveedor: Buró S.A.
direccion: saliente            # saliente | entrante | bidireccional
protocolo: HTTPS/JSON
autenticacion: mTLS
sla:
  disponibilidad: 99.9
  p95_ms: 800
limites:
  rps: 50
  cuota_diaria: null
datos_sensibles: [rut]
politica_ante_falla: fail-closed   # fail-open | fail-closed | no aplica
justificacion: Sin buró no se evalúa el riesgo crediticio
repos: [fraude-core]           # vacío: se muestra en la revisión de todos los repositorios
contrato: contratos/buro.yaml  # ruta dentro de docs/
```

La política ante falla (`fail-open` o `fail-closed`) y su justificación son decisiones de negocio:
las define el usuario. Lo que no se sepa queda `NO DETERMINADO`.

### Paso 4: validar

```sh
.venv/bin/python herramientas/terceros.py validar motor-fraudes --id buro-credito
```

Distingue **errores** (un valor inválido, un repositorio inexistente, un contrato que no está en
`docs/`) de **pendientes** (campos sin completar).

### Para qué sirve en la revisión

El paquete de `/revisar` muestra los terceros de cada repositorio. La revisión los contrasta con el
código:

- integraciones que el código usa y no tienen ficha;
- timeouts del cliente frente al p95 del tercero;
- política ante falla declarada frente a la implementada;
- uso de sus contratos, códigos de error y límites.

Un hallazgo puede citar la documentación del tercero (`terceros/<id>/docs/<archivo>`); la cita se
valida contra el texto indexado.

## Fuente de historias de usuario

Opcional. Permite proponer ADR a partir de historias de Jira y crear Tareas, Spikes, Errores y Hotfix. Se
configura una vez por producto:

```sh
.venv/bin/python herramientas/productos.py historias motor-fraudes --fuente jira \
  --jql "project = FRAUD AND labels = motor-fraudes" --campo-tipo Tipo --proyecto FRAUD
```

- Conviene `--jql` antes que `--tablero`: sigue funcionando aunque el tablero se elimine.
- `--campo-tipo` es el campo personalizado que clasifica la historia (Bau/Incidentes, Deuda
  Operativa, Deuda Técnica, Spike…).
- `--proyecto` es el proyecto donde se crean las Tareas, Spikes, Errores y Hotfix.
- Para un proyecto archivado, exportar a CSV y usar `--fuente archivo --archivo export.csv`.
