# ADR-EQ-006: Documentación de macro a micro

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `27-10-2026`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** los productos se componen de muchos repositorios y su documentación
  está dispersa: no hay un punto de entrada común, los niveles no se enlazan entre sí y la misma
  información se repite en varios lugares hasta que se contradice. Entender un producto o un
  repositorio exige leer su código, lo que encarece la incorporación de personas y la revisión de
  cambios.
- **Alcance:** cada producto en su conjunto y sus repositorios de tipo `propio`.
- **Restricciones:** arquitectura no define un formato ni una ubicación para la documentación ni para
  los diagramas C4. Los diagramas deben poder leerse en GitLab, GitHub y Confluence sin
  herramientas adicionales y mantenerse junto al código.

## 5. Decisión

La documentación se organiza **de lo macro a lo micro**, en cinco niveles. Cada nivel enlaza con el
de arriba y con el de abajo, y cada dato vive en un solo nivel:

| Nivel | Qué contiene | Dónde vive | Para quién |
|---|---|---|---|
| 1. Producto | Visión y capacidades, C4 del producto, repositorios, terceros, decisiones del producto y operación | Confluence: una página por producto, con sus páginas hijas | dueño del producto (PO), negocio, arquitectura, personas nuevas |
| 2. Repositorio | README (ADR-EQ-007) y C4 de contexto y de contenedores del repositorio | el repositorio | desarrollo y arquitectura |
| 3. Detalle técnico | `docs/`: operación, despliegue, configuración y resolución de problemas | el repositorio | desarrollo y operación |
| 4. Contratos | OpenAPI y AsyncAPI, con ejemplos (ADR-EQ-004) | el repositorio | quien integra |
| 5. Código | comentarios solo donde una decisión no es obvia, con referencia a su ADR | el repositorio | desarrollo |

- **Confluence resume y enlaza**; el detalle técnico vive solo en el repositorio. Una página de
  Confluence no copia un README, un contrato ni una configuración: los enlaza.
- **C4 en dos niveles**, en cada repositorio de tipo `propio` y en el producto:
  1. **Contexto:** el sistema, las personas que lo usan y los sistemas externos con los que se
     comunica.
  2. **Contenedores:** las aplicaciones, bases de datos, colas y servicios que lo componen, con su
     tecnología y sus relaciones.

  Los diagramas se escriben como código Mermaid C4. En el repositorio viven junto al código; en
  Confluence se incluyen como bloque de código. El C4 del producto incluye los sistemas comprados y
  los terceros.

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| Todo en Confluence | Un solo lugar para leer | Se desactualiza respecto del código; el cambio no se revisa en el MR | La documentación técnica se separa del código que describe |
| Todo en los repositorios | Siempre junto al código | Sin punto de entrada para quien no lee repositorios (PO, negocio, personas nuevas) | Sin vista de producto |
| Confluence para lo macro, repositorio para lo micro, enlazados | Cada público entra por su nivel; el detalle se revisa en el MR | Exige mantener los enlaces | **Elegida** |
| Structurizr DSL (lenguaje propio de Structurizr) o C4-PlantUML para los diagramas | Notación más completa | GitLab, GitHub y Confluence no los muestran sin configuración | Mayor costo de adopción |
| Diagramas como imagen (PNG, draw.io) | Libertad visual | No se pueden verificar ni comparar entre versiones | No es verificable |
| Mermaid C4 como código | Se lee en GitLab y GitHub; texto simple y fácil de revisar | Soporte de C4 menos completo | **Elegida** para los diagramas |

## 7. Consecuencias

### Positivas

- Cualquier persona entra por el nivel que le corresponde y baja hasta el detalle sin perderse.
- La documentación técnica y los diagramas se revisan en el mismo MR que el código que los cambia.
- Cada dato vive en un solo lugar: no hay dos versiones que se contradicen.
- Los diagramas y los enlaces se pueden verificar contra el código.

### Negativas o compromisos

- Cada cambio estructural (nuevo contenedor, nueva integración) exige actualizar el diagrama.
- Hay que mantener los enlaces entre niveles cuando se crea, mueve o retira un repositorio.

### Riesgos

- Documentación que se escribe una vez y no se mantiene. Se mitiga con los criterios `EQ-006.7` y
  `EQ-006.11`.
- Páginas de Confluence que vuelven a copiar el detalle técnico. Se mitiga con el criterio `EQ-006.10`.

## 8. Impacto

Cada repositorio de tipo `propio` necesita sus dos diagramas C4 y los enlaces de su README y de sus
contratos. Cada producto necesita su página de Confluence. Se parte de borradores inferidos del
código y del inventario de componentes de cada repositorio.

## 9. Acciones requeridas

**Página del producto en Confluence** (nivel 1):

```
<Producto>                     visión y capacidades
├── Arquitectura               C4 de contexto y de contenedores del producto (Mermaid como código)
├── Repositorios               una fila por repositorio: propósito, stack y enlace a su README
├── Integraciones y terceros   protocolo, tiempo de respuesta (p95), política ante falla y enlace a su documentación
├── Decisiones                 ADR del producto vigentes, con su regla rápida
└── Operación                  enlaces a los docs/ de operación de cada repositorio
```

**En cada repositorio** (niveles 2 a 4):

```
README.md                          enlaza a la página del producto, a docs/ y a los contratos
docs/arquitectura/c4-contexto.md
docs/arquitectura/c4-contenedores.md
docs/                              operación, despliegue, configuración y resolución de problemas
docs/contratos/                    OpenAPI y AsyncAPI; cada contrato enlaza al README
```

En OpenAPI, el enlace al README va en `externalDocs`; en AsyncAPI, en `externalDocs` o en
`info.description`.

**Notación mínima de los diagramas** (plantillas en `equipo/plantillas/`):

- Cada diagrama tiene título.
- Cada elemento tiene nombre y descripción.
- Cada contenedor declara su tecnología (por ejemplo `Java 21, Spring Boot 3`).
- Cada relación declara qué intercambia y con qué protocolo (por ejemplo `Evalúa transacción, HTTPS/JSON`).
- Los sistemas externos se marcan como externos (`System_Ext`, `Container_Ext`).

## 10. Referencias

- ADR-EQ-004 (contratos como código), ADR-EQ-007 (README estándar)
- Modelo C4: <https://c4model.com>
- Mermaid C4: <https://mermaid.js.org/syntax/c4.html>
- Plantillas: `equipo/plantillas/c4-contexto.md`, `equipo/plantillas/c4-contenedores.md`, `equipo/plantillas/README.md`

## 11. Regla rápida

> La documentación va de lo macro a lo micro: Confluence resume el producto y enlaza; cada
> repositorio tiene su README, su C4 y sus contratos, enlazados entre sí. Si no está en el C4, no
> existe para arquitectura.

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en [COHERENCIA.md](../COHERENCIA.md), junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-006.1` | Existe `docs/arquitectura/c4-contexto.md` con un diagrama `C4Context` | automática | alta |
| `EQ-006.2` | Existe `docs/arquitectura/c4-contenedores.md` con un diagrama `C4Container` | automática | alta |
| `EQ-006.3` | Notación mínima: título, nombre y descripción en cada elemento, tecnología en cada contenedor, descripción y protocolo en cada relación, externos marcados | automática | media |
| `EQ-006.4` | El diagrama es código Mermaid y no solo una imagen | automática | baja |
| `EQ-006.5` | Los contenedores del diagrama existen en el código o la configuración | revisión de código | media |
| `EQ-006.6` | Toda integración real del código aparece como sistema o contenedor externo | revisión de código | alta |
| `EQ-006.7` | El diagrama refleja los cambios estructurales recientes del código | revisión de código | media |
| `EQ-006.8` | El README enlaza a la página del producto, a `docs/` y a los contratos | revisión de código | media |
| `EQ-006.9` | Cada contrato OpenAPI o AsyncAPI enlaza al README del repositorio | revisión de código | baja |
| `EQ-006.10` | La página del producto en Confluence tiene visión, C4 del producto, repositorios, terceros, decisiones y operación, y resume y enlaza en lugar de copiar el detalle técnico | revisión del producto | alta |
| `EQ-006.11` | Un MR que cambia la estructura (contenedores, integraciones, contratos) actualiza el nivel de documentación que corresponde | revisión del MR | media |
