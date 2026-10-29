# ADR-EQ-001: Documentación de arquitectura C4 en cada repositorio

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `27-10-2026`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** los productos se componen de muchos repositorios y no existe una
  vista común de qué hace cada uno, con qué se comunica ni de qué depende. Entender un
  repositorio exige leer su código, lo que encarece la incorporación de personas y la revisión
  de cambios.
- **Alcance:** repositorios de tipo `propio` y cada producto en su conjunto.
- **Restricciones:** arquitectura no define un formato ni una ubicación para diagramas C4. Los
  diagramas deben poder leerse en GitLab y GitHub sin herramientas adicionales y mantenerse junto al
  código.

## 5. Decisión

Cada repositorio de tipo `propio` documenta su arquitectura con el modelo C4 en dos niveles:

1. **Contexto:** el sistema, las personas que lo usan y los sistemas externos con los que se
   comunica.
2. **Contenedores:** las aplicaciones, bases de datos, colas y servicios que lo componen, con su
   tecnología y sus relaciones.

Los diagramas se escriben como código en Mermaid C4 y viven en el repositorio. Cada producto
tiene además su propio C4 de contexto y de contenedores, que incluye los sistemas comprados y
los terceros.

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| Structurizr DSL (lenguaje propio de Structurizr para describir el modelo) | Modelo único con varias vistas; fiel al modelo C4 | Requiere herramientas para visualizar; GitLab y GitHub no lo muestran | Mayor costo de adopción |
| C4-PlantUML | Notación madura y completa | GitLab y GitHub no lo muestran sin configuración adicional | Mayor costo de adopción |
| Imágenes (PNG, draw.io) | Libertad visual | No se puede verificar ni comparar entre versiones; se desactualiza sin aviso | No es verificable |
| Mermaid C4 | GitLab y GitHub lo muestran dentro del markdown; texto simple y fácil de revisar | Soporte de C4 menos completo que Structurizr | **Elegida** |

## 7. Consecuencias

### Positivas

- Cualquier persona entiende el repositorio y sus dependencias sin leer el código.
- Los diagramas se revisan en el mismo MR que el código que los cambia.
- `radiografia` puede verificar que el diagrama coincide con el código.

### Negativas o compromisos

- Cada cambio estructural (nuevo contenedor, nueva integración) exige actualizar el diagrama.

### Riesgos

- Diagramas que se escriben una vez y no se mantienen. Se mitiga con el criterio `EQ-001.7`.

## 8. Impacto

Todos los repositorios de tipo `propio` necesitan dos archivos nuevos. El esfuerzo inicial es
bajo y `radiografia` entrega un borrador inferido del código como punto de partida.

## 9. Acciones requeridas

**Ubicación en cada repositorio:**

```
docs/arquitectura/c4-contexto.md
docs/arquitectura/c4-contenedores.md
```

**Notación mínima** (plantillas en `equipo/plantillas/`):

- Cada diagrama tiene título.
- Cada elemento tiene nombre y descripción.
- Cada contenedor declara su tecnología (por ejemplo `Java 21, Spring Boot 3`).
- Cada relación declara qué intercambia y con qué protocolo (por ejemplo `Evalúa transacción, HTTPS/JSON`).
- Los sistemas externos se marcan como externos (`System_Ext`, `Container_Ext`).

**Producto:** el C4 del producto se mantiene en la ubicación que indica `producto.yaml`.

## 10. Referencias

- Modelo C4: <https://c4model.com>
- Mermaid C4: <https://mermaid.js.org/syntax/c4.html>
- Plantillas: `equipo/plantillas/c4-contexto.md`, `equipo/plantillas/c4-contenedores.md`

## 11. Regla rápida

> Si no está en el C4, no existe para arquitectura: todo contenedor e integración real aparece
> en el diagrama de contexto o de contenedores del repositorio.

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en [COHERENCIA.md](../COHERENCIA.md), junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-001.1` | Existe `docs/arquitectura/c4-contexto.md` con un diagrama `C4Context` | automática | alta |
| `EQ-001.2` | Existe `docs/arquitectura/c4-contenedores.md` con un diagrama `C4Container` | automática | alta |
| `EQ-001.3` | Notación mínima: título, nombre y descripción en cada elemento, tecnología en cada contenedor, descripción y protocolo en cada relación, externos marcados | automática | media |
| `EQ-001.4` | El diagrama es código Mermaid y no solo una imagen | automática | baja |
| `EQ-001.5` | Los contenedores del diagrama existen en el código o la configuración | revisión de código | media |
| `EQ-001.6` | Toda integración real del código aparece como sistema o contenedor externo | revisión de código | alta |
| `EQ-001.7` | El diagrama refleja los cambios estructurales recientes del código | revisión de código | media |
