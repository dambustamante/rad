# ADR-EQ-005: README estándar en español neutro y técnico

## 2. Estado

Propuesto

## 3. Fecha

- Fecha de creación: `27-10-2026`
- Fecha de aprobación: `—`

## 4. Contexto

- **Problema o necesidad:** cada repositorio documenta de forma distinta o no documenta. Una
  persona nueva depende de que alguien le explique cómo levantar y entender el repositorio, y un
  arquitecto no encuentra las decisiones ni las dependencias sin leer el código.
- **Alcance:** todos los repositorios de tipo `propio`.
- **Restricciones:** arquitectura no define un estándar de documentación. Los lectores van desde
  desarrolladores junior hasta arquitectos.

## 5. Decisión

Cada repositorio de tipo `propio` tiene en su raíz un `README.md` que:

1. sigue las secciones de la plantilla `equipo/plantillas/README.md`;
2. está escrito en español neutro y técnico: sin voseo ni regionalismos, con las siglas
   explicadas la primera vez y frases directas;
3. permite a un desarrollador junior levantar el repositorio sin ayuda;
4. permite a un arquitecto entender el propósito, las dependencias y las decisiones sin leer el
   código.

## 6. Alternativas evaluadas

| Alternativa | Ventajas | Desventajas | Motivo del descarte |
|---|---|---|---|
| Formato libre | Sin esfuerzo de adopción | Calidad dispar; información clave ausente | No es verificable |
| Documentación fuera del repositorio | Herramientas de edición más ricas | Se desactualiza respecto del código | Se separa del código |
| Plantilla común en el repositorio | Consistente y verificable | Exige completar secciones | **Elegida** |

## 7. Consecuencias

### Positivas

- Incorporación más rápida de personas al equipo.
- Menos dependencia de quienes conocen el repositorio.

### Negativas o compromisos

- Mantener el README al día con cada cambio relevante.

### Riesgos

- README completos en forma pero desactualizados. Se mitiga con los criterios `EQ-005.2` y
  `EQ-005.3`.

## 8. Impacto

Todos los repositorios de tipo `propio`. `radiografia` entrega un borrador inferido del código
cuando falta el README o sus secciones.

## 9. Acciones requeridas

**Secciones obligatorias** (en este orden, de lo general a lo operativo):

1. Resumen y propósito
2. Contexto de negocio y responsables
3. Arquitectura (enlace al C4 y patrones usados)
4. Stack y versiones
5. Cómo se ejecuta en local (prerrequisitos y pasos)
6. Configuración (variables de entorno, solo por nombre)
7. Integraciones (con su política de degradación, ADR-EQ-003)
8. Contratos (enlace a `docs/contratos/`, ADR-EQ-002)
9. Entornos y despliegue
10. Observabilidad
11. Operación y resolución de problemas
12. Decisiones (ADR que aplican)
13. Glosario

**Lenguaje:**

- Español neutro: evitar formas como "tenés", "podés" o "hacé", y modismos locales.
- Términos técnicos en inglés solo cuando son el nombre habitual (por ejemplo *circuit breaker*).
- Cada sigla se explica la primera vez que aparece.

## 10. Referencias

- Plantilla: `equipo/plantillas/README.md`
- ADR-EQ-001 (C4), ADR-EQ-002 (contratos), ADR-EQ-003 (integraciones)

## 11. Regla rápida

> Una persona nueva levanta el repositorio solo con el README, y un arquitecto lo entiende sin
> leer el código.

## 12. Relación con arquitectura

Se verifica automáticamente con `/actualizar` y se registra en [COHERENCIA.md](../COHERENCIA.md), junto con los criterios que quedan suspendidos si hay un choque.

## 13. Criterios de verificación

| Criterio | Qué se verifica | Cómo | Severidad |
|---|---|---|---|
| `EQ-005.1` | Existe `README.md` con las secciones obligatorias | automática | media |
| `EQ-005.2` | Los comandos del README existen (Makefile, scripts del gestor de paquetes, wrappers de build) | automática + revisión de código | media |
| `EQ-005.3` | Las variables documentadas coinciden con las que lee el código | revisión de código | media |
| `EQ-005.4` | El texto está en español neutro y técnico, con las siglas explicadas | revisión de código | baja |
| `EQ-005.5` | Los pasos para ejecutar en local son completos y no suponen conocimiento implícito | revisión de código | media |
