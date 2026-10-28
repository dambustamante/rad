# /revisar

Obtiene la línea base AS IS de los repositorios de un producto y la compara con lo que la
organización decidió, en orden de autoridad: ADR de arquitectura, estándares de arquitectura,
decisiones del equipo (ADR-EQ) y Sonar.

Uso: `/revisar <producto> [repo]`. Se trabaja **un repositorio por conversación**: al terminar uno,
sugerir abrir un chat nuevo para el siguiente (reduce el costo, porque no se reenvía el contexto
acumulado).

## 1. Elegir el repositorio

```sh
.venv/bin/python herramientas/revision.py pendientes <producto>
```

- Si el usuario indicó un repositorio, usar ese. Si no, tomar el primero que no esté "al día".
- Si todos están al día, ir al paso 8 (producto).

## 2. Parte automática

Si el repositorio dice "falta la parte automática", o si el usuario pide revisar de nuevo:

```sh
make revisar P=<producto> R=<repo>
```

## 3. Paquete de revisión

```sh
.venv/bin/python herramientas/revision.py paquete <producto> <repo>
```

Leer el paquete completo antes de abrir cualquier archivo del repositorio. Contiene el mapa del
repositorio, los archivos señalados por patrón, los hallazgos automáticos ya registrados (no
repetirlos) y la lista exacta de lo que hay que evaluar, incluidos los criterios de las decisiones
del producto (`ADR-<SIGLA>-NNN`). Los elementos exceptuados por un ADR del producto vigente aparecen
aparte y no se evalúan: el cierre los registra como NO APLICA.

Leer el código de `productos/<producto>/repos/<repo>/` empezando por los manifiestos, los puntos de
entrada y los archivos señalados. Llevar la cuenta de los archivos leídos: se informa al cerrar.
Nunca modificar nada en esa carpeta. Si se encuentra un secreto, no copiar su valor.

## 4. AS IS

Escribir `productos/<producto>/revisiones/<revisión>/revision/<repo>-asis.md` con estas secciones `##`,
en este orden, cada afirmación con su etiqueta de evidencia (`[hecho] ruta:línea`, `[doc] ruta`,
`[inferencia]`, `NO DETERMINADO - motivo`):

1. **Propósito**: qué hace el repositorio y qué capacidad de negocio soporta.
2. **Arquitectura real**: estilo (por capas, hexagonal, sin estructura clara…), módulos y cómo
   dependen entre sí. Describir lo que hay, no lo que debería haber.
3. **Componentes y contenedores**: aplicaciones, bases de datos, colas y caché, con su tecnología.
4. **Integraciones**: sistemas externos que llama o que lo llaman, con protocolo, timeouts,
   reintentos y qué pasa ante una falla.
5. **Contratos**: APIs y eventos que expone y consume, y dónde están documentados (o que no lo están).
6. **Datos**: qué datos maneja, dónde los guarda y si hay datos sensibles.
7. **Configuración y despliegue**: variables de configuración (solo nombres), empaquetado, CI y
   entornos.
8. **Observabilidad**: logs, métricas, trazas y alertas.
9. **Riesgos y deuda principales**: los tres a cinco puntos más importantes, con su evidencia.

Para un repositorio de tipo `proveedor` o `config`, poner el foco en integraciones, contratos,
configuración y despliegue; el diseño interno se describe solo si es visible y relevante.

## 5. C4 inferido

Escribir los borradores en `productos/<producto>/revisiones/<revisión>/borradores/<repo>/`
(`c4-contexto.md` y `c4-contenedores.md`), con las plantillas de `equipo/plantillas/`. Todo elemento
y relación sale del código; lo que no se pueda deducir se marca como NO DETERMINADO. Es un borrador
para el equipo, no se escribe en el repositorio.

## 6. Evaluar y registrar

Para **cada** elemento de la sección "Qué evaluar" del paquete, en orden de nivel:

1. Si la fuente es un documento de arquitectura y la regla rápida no alcanza para decidir, leer el
   documento (`arquitectura/decisiones/<fuente>/…` o `arquitectura/estandares/<fuente>/…`).
2. Decidir: `CUMPLE`, `NO CUMPLE`, `NO APLICA` (no corresponde a este repositorio) o
   `NO DETERMINADO` (no se pudo verificar con el código disponible).
3. Si es `NO CUMPLE`, registrar primero cada hallazgo:

   ```sh
   .venv/bin/python herramientas/revision.py hallazgo <producto> <repo> \
     --fuente <fuente:ID o ADR-EQ-NNN> [--criterio EQ-NNN.N] \
     --categoria <incumplimiento|diseño|error|seguridad|deuda|documentacion> --severidad <bloqueante|alta|media|baja> \
     --titulo "<qué pasa, en una línea>" --detalle "<por qué importa y qué se sugiere>" \
     --evidencia <ruta:línea> [--evidencia <ruta:línea> ...] \
     --fragmento "<código copiado tal cual de la primera evidencia>" \
     [--cita-documento "<texto copiado tal cual del documento incumplido>"]
   ```

4. Registrar la evaluación:

   ```sh
   .venv/bin/python herramientas/revision.py evaluar <producto> <repo> \
     --fuente <fuente> [--criterio <criterio>] --resultado "<resultado>" --motivo "<una o dos frases>" \
     [--evidencia <ruta:línea> ...] [--cita-documento "<texto>"]
   ```

Reglas del registro:

- El script rechaza archivos o líneas que no existen, fragmentos que no están en el código y citas
  que no están en el documento. Si rechaza algo, volver a copiar el texto desde la fuente: nunca
  reformular para que pase.
- `incumplimiento` exige `--cita-documento`. Sin cita, el hallazgo es `diseño`, `error` o `deuda`.
- Severidad de un criterio de un ADR-EQ: la de su tabla, salvo motivo explícito en el detalle.
- No repetir los hallazgos automáticos ni los de Sonar del paquete. Si un problema ya está como
  issue de Sonar y además incumple un documento de mayor nivel, registrarlo en ese nivel: el script
  asocia el issue de Sonar al hallazgo.
- Un hallazgo describe una señal concreta en una ubicación concreta. "No cumple SOLID" no es un
  hallazgo; "la clase X mezcla acceso a datos y llamadas HTTP (`ruta:línea`)" sí lo es.

## 7. Cerrar

```sh
.venv/bin/python herramientas/revision.py cerrar <producto> <repo> --archivos-leidos <N>
```

El cierre exige que todo esté evaluado, que cada `NO CUMPLE` tenga hallazgo y que el AS IS tenga
sus secciones. Si falta algo, completarlo y volver a cerrar.

Responder con:

```markdown
## Revisión de código de <repo> (<producto>)

**Veredicto:** <PASA / NO PASA, de la ficha>
**Archivos leídos:** <N>

| Nivel | Evaluados | ✅ | ❌ | ➖ | ❔ |
|---|---|---|---|---|---|

### Hallazgos principales
<hasta 8, ordenados por nivel y severidad: ID, fuente o criterio, título, evidencia>

### AS IS en una frase
<resumen>

Siguiente: abrir un chat nuevo y ejecutar `/revisar <producto>` para el próximo repositorio.
```

## 8. Producto

Cuando todos los repositorios están al día:

1. Leer las fichas `productos/<producto>/as-is/<repo>.md` y los borradores C4 de cada repositorio.
2. Escribir un archivo temporal con la narrativa del producto: `## Visión del producto` (qué hace,
   cómo se reparten las responsabilidades entre repositorios), `## C4 del producto (inferido)` con
   los diagramas de contexto y contenedores en Mermaid, y `## Conclusiones` (brechas principales y
   recomendaciones, con referencias a los hallazgos).
3. Ejecutar:

   ```sh
   .venv/bin/python herramientas/revision.py producto <producto> --narrativa <archivo>
   ```

## Reglas generales

- Nunca modificar `productos/*/repos/`, `productos/*/estado/` ni las secciones generadas de las fichas.
- Los hallazgos en modo `propuesta` (decisiones del equipo no aprobadas) se informan, pero no
  afectan el veredicto.
- Todo en español neutro y técnico.
