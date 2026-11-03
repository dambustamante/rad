# 4. Productos y terceros (`/producto`)

> Qué hace este comando y cuándo se usa: [Comandos](10-comandos.md). Aquí está solo el detalle.

## Crear un producto

```
/producto motor-fraudes
```

1. Si el producto no existe, Cursor pide una descripción de una frase, el **origen** y la **sigla**,
   y lo crea en `productos/motor-fraudes/producto.yaml`, junto con su harness:

   ```sh
   .venv/bin/python herramientas/productos.py crear --producto motor-fraude --origen nuevo \
     --descripcion "Motor de fraude propio" --sigla MF
   ```

   | Origen | Qué es | Cómo sigue |
   |---|---|---|
   | `heredado` | se recibe de otro equipo | toma de control: repositorios, terceros y línea base con `/revisar` |
   | `nuevo` | se construye desde el inicio | puede quedar sin repositorios hasta tener código |

2. La **sigla** numera sus ADR (`MF` → `ADR-MF-001`). Si no se indica, el script propone una. Queda fija al
   crear el producto, porque el harness la usa.

3. Todos los productos aparecen en **`productos/INDICE.md`**, el portafolio generado: origen, sigla,
   repositorios, línea base, harness, veredicto y hallazgos bloqueantes o altos abiertos.

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

Un tercero es todo sistema del que depende el producto y que el equipo no construye: el producto
comprado (rol `producto-comprado`) y cada sistema externo con el que se integra (rol `integracion`):
buró, red de tarjetas, listas de sanciones o un sistema del banco de otro equipo.

La ficha registra lo **acordado o documentado** con ese sistema (protocolo, p95, límites, política
ante falla). Lo que el código **usa de verdad** lo registra `/revisar` como componentes, con
evidencia. El inventario del producto cruza ambos: integraciones del código sin ficha y fichas que
ningún repositorio usa.

La ficha se registra en `productos/<p>/terceros/<id>/`. Su documentación queda en markdown, en
`documentos/terceros/<id>/` del harness:

```
terceros/
├── INDICE.md                 estado de cada ficha (generado)
└── buro-credito/
    └── ficha.yaml            datos del tercero
```

### Paso 1: crear la ficha

```sh
.venv/bin/python herramientas/terceros.py nuevo motor-fraudes --id motor --nombre "Motor de fraudes" --rol producto-comprado
.venv/bin/python herramientas/terceros.py nuevo motor-fraudes --id buro-credito --nombre "Buró de crédito"
```

El rol es `producto-comprado` o `integracion` (por defecto).

### Paso 2: importar la documentación

Se convierte a markdown, igual que los [documentos del producto](#documentos-del-producto):

```sh
.venv/bin/python herramientas/documentos.py importar motor-fraudes manual.pdf --tercero buro-credito
.venv/bin/python herramientas/documentos.py confluence motor-fraudes <url> --tercero buro-credito
```

Un PDF conserva sus páginas, para poder citarlas. Los contratos OpenAPI y AsyncAPI se reconocen por su contenido, y el
documento indica su tipo, título, versión y cantidad de operaciones.

### Paso 3: completar la ficha

Cursor propone los valores buscando en la documentación indexada y citando de dónde sale cada uno:

```sh
.venv/bin/python herramientas/documentos.py buscar motor-fraudes "timeout 800"
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
contrato: openapi-buro.md      # archivo en documentos/terceros/<id>/
```

La política ante falla (`fail-open` o `fail-closed`) y su justificación son decisiones de negocio:
las define el usuario. Lo que no se sepa queda `NO DETERMINADO`.

### Paso 4: validar

```sh
.venv/bin/python herramientas/terceros.py validar motor-fraudes --id buro-credito
```

Distingue **errores** (un valor inválido, un repositorio inexistente, un contrato que no está en
`documentos/terceros/<id>/`) de **pendientes** (campos sin completar).

### Para qué sirve en la revisión

El paquete de `/revisar` muestra los terceros de cada repositorio. La revisión los contrasta con el
código:

- integraciones que el código usa y no tienen ficha;
- timeouts del cliente frente al p95 del tercero;
- política ante falla declarada frente a la implementada;
- uso de sus contratos, códigos de error y límites.

Un hallazgo puede citar la documentación del tercero (`documentos/terceros/<id>/<archivo>.md`); la cita se
valida contra el texto indexado.

## Documentos del producto

Toda la documentación del producto, salvo la de un tercero, queda **en markdown** en `documentos/` de su harness, con su
tipo, origen y fecha.

| Qué se trae | Comando | Resultado |
|---|---|---|
| Página de Confluence | `documentos.py confluence motor-fraudes <url>` | Se convierte a markdown |
| Espacio de Confluence | `documentos.py confluence motor-fraudes --espacio FRAUDE` | Una página de markdown por cada página del espacio |
| PDF, Word, PowerPoint, Excel, HTML, texto | `documentos.py importar motor-fraudes <archivo>` | Se convierte a markdown |
| Dibujo o imagen | `documentos.py importar motor-fraudes <imagen>` | Markdown por completar: Cursor mira la imagen y escribe qué muestra |
| Conversación | `documentos.py importar motor-fraudes <archivo> --conversacion` | Markdown por completar: fecha, decisiones y pendientes, sin copiar el chat |

- **Confluence es de solo lectura.** Se configura en `.env`: `CONFLUENCE_URL` y, si difieren de los de Jira,
  `CONFLUENCE_EMAIL` y `CONFLUENCE_TOKEN`. `/actualizar` trae las páginas importadas que cambiaron.
- **Lo que no se importa:** las imágenes dentro de una página de Confluence, los formatos antiguos (`.doc`, `.ppt`, `.xls`),
  que hay que guardar como `.docx`, `.pptx` o `.xlsx`, y los PDF escaneados, para los que hay que pedir una versión con texto.
- **Lectura:** `documentos.py buscar`, `titulos` y `ver` leen solo la parte necesaria, hasta 150 líneas por vez.
- **Secretos:** un documento con un posible secreto no se guarda. Necesita `gitleaks`. Los datos personales no se detectan.
- **Evidencia:** se cita como `[doc]`. Si contradice al código, manda el código y la diferencia es un hallazgo.
- **Acceso:** todos los que usan el harness ven estos documentos. Lo confidencial no se importa.

## Espacio de Jira

Cada producto se asocia a un espacio de Jira, por ejemplo `SYF`. `/producto` lo pide al crear el producto. Las incidencias que
crean `/crear` y `/hdu` van a ese espacio, con el nombre del producto como etiqueta, para filtrarlas en un tablero.

Para cambiarlo después, o usar otra etiqueta:

```sh
.venv/bin/python herramientas/productos.py jira motor-fraudes --proyecto SYF [--etiqueta otra]
```

Las historias no se guardan en radiografia: cada harness las lee de Jira cuando se ejecuta `/hdu`.
