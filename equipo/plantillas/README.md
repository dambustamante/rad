# <nombre-del-repositorio>

> Plantilla de ADR-EQ-005. Reemplazar cada `<…>` y eliminar las notas entre corchetes.

## 1. Resumen y propósito

<Qué hace este repositorio, en dos o tres frases, y qué problema resuelve.>

## 2. Contexto de negocio y responsables

- **Producto:** <producto al que pertenece>
- **Capacidad de negocio:** <qué parte del negocio soporta>
- **Equipo responsable:** <equipo>
- **Contacto técnico:** <rol o canal, no datos personales>

## 3. Arquitectura

- Diagrama de contexto: [docs/arquitectura/c4-contexto.md](docs/arquitectura/c4-contexto.md)
- Diagrama de contenedores: [docs/arquitectura/c4-contenedores.md](docs/arquitectura/c4-contenedores.md)
- **Estilo y patrones usados:** <por ejemplo, arquitectura hexagonal, outbox, circuit breaker>

## 4. Stack y versiones

| Componente | Versión |
|---|---|
| <lenguaje> | <versión> |
| <framework> | <versión> |
| <base de datos> | <versión> |

## 5. Cómo se ejecuta en local

**Prerrequisitos:**

- <herramienta y versión>
- <acceso o credencial necesaria y cómo obtenerla>

**Pasos:**

```sh
<comando 1>
<comando 2>
```

**Verificación:** <cómo comprobar que funciona, por ejemplo una URL de salud>

## 6. Configuración

| Variable | Descripción | Obligatoria | Ejemplo |
|---|---|---|---|
| `<NOMBRE_VARIABLE>` | <para qué sirve> | sí/no | <valor de ejemplo no sensible> |

Nunca se documentan valores reales de secretos.

## 7. Integraciones

| Sistema | Tipo | Timeout | Reintentos | Circuit breaker | Política ante falla | Justificación |
|---|---|---|---|---|---|---|
| <sistema> | HTTP/cola/… | <ms> | <n, solo idempotentes> | sí/no | fail-open/fail-closed | <motivo de negocio> |

## 8. Contratos

- API expuesta: [docs/contratos/openapi.yaml](docs/contratos/openapi.yaml)
- Eventos: [docs/contratos/asyncapi.yaml](docs/contratos/asyncapi.yaml)
- APIs consumidas: [docs/contratos/consumidos.md](docs/contratos/consumidos.md)

## 9. Entornos y despliegue

| Entorno | URL o identificador | Cómo se despliega |
|---|---|---|
| <dev/qa/prod> | <…> | <pipeline o procedimiento> |

## 10. Observabilidad

- **Logs:** <dónde se consultan; formato según ADR-EQ-007 (JSON con `trace_id`)>
- **Métricas:** <principales métricas y dónde se ven>
- **Trazas:** <herramienta y cómo se correlacionan>
- **Alertas:** <qué alertas existen>

## 11. Operación y resolución de problemas

| Síntoma | Causa probable | Acción |
|---|---|---|
| <…> | <…> | <…> |

## 12. Decisiones

| Decisión | Aplica porque |
|---|---|
| <ADR de arquitectura o ADR-EQ> | <motivo> |

## 13. Glosario

| Término | Significado |
|---|---|
| <término de negocio o sigla> | <definición> |
