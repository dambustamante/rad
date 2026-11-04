# /revisar: un repositorio

## 1. Elegir y preparar

```sh
.venv/bin/python herramientas/revision.py pendientes <producto>
make revisar P=<producto> R=<repo>        # COMPLETA=1 fuerza una revisión completa
```

Tomar el repositorio indicado o el primero que no esté "al día". `make revisar` ejecuta la parte
automática y genera el paquete. Si la conversación se retoma a mitad de camino, no repetirlo:
regenerar solo el paquete con `revision.py paquete <producto> <repo>`.

## 2. Leer

Leer el paquete completo antes de abrir archivos. Si trae **Documentos del producto**, buscar lo relacionado, leer solo
esa parte y contrastarla con el código: lo que el código contradice es un hallazgo de categoría `documentacion`. Después, el código de `productos/<producto>/repos/<repo>/`
empezando por los manifiestos, los puntos de entrada y los archivos señalados. Contar los archivos
leídos. No modificar nada en esa carpeta ni copiar valores de secretos. Si el paquete es incremental,
revisar solo lo que el cambio afecta: lo demás se hereda.

## 3. AS IS

`revisiones/<revisión>/revision/<repo>-asis.md` con estas secciones `##`. Cada afirmación primero y, al final entre paréntesis,
su etiqueta y su ubicación, para que se lea de corrido: «Usa Spring WebFlux ([hecho] `build.gradle:47`).» Describe cómo es el
servicio: **no repetir lo que ya es un hallazgo** (va en la tabla de hallazgos) ni lo que ya va en `componentes` (bases, colas,
integraciones y APIs).

1. **Propósito**: qué hace y qué capacidad de negocio soporta.
2. **Arquitectura real**: estilo, módulos y cómo dependen entre sí; lo que hay, no lo que debería haber.
3. **Configuración y despliegue**: variables (solo nombres), empaquetado, CI y entornos.
4. **Observabilidad**: logs, métricas, trazas y alertas.
5. **Riesgos y deuda principales**: solo lo que no es un hallazgo, como contexto, decisiones heredadas o riesgos sin una regla que los cubra. Si no hay, escribir «Los riesgos están en la tabla de hallazgos.»

Bases, colas, integraciones, APIs y datos no se describen aquí: van como `componentes` en el lote. El
cierre genera con ellos la tabla de la ficha y los borradores C4.

## 4. Lote

Un único archivo, `revisiones/<revisión>/revision/<repo>-lote.yaml`. Cada clave de "Qué evaluar" va en
`cumple`, `no_aplica` o `no_determinado`; lo que no cumple va **solo** como hallazgo (eso lo registra como
NO CUMPLE). Si la regla rápida no alcanza para decidir, leer el documento.

```yaml
cumple: [EQ-001.2, EQ-002.3, EQ-005.1]
no_aplica: {EQ-003.3: no hace llamadas salientes ni consume mensajes}
no_determinado: {EQ-004.5: los contratos consumidos están en otro repositorio}
hallazgos:
  - fuente: decision-records:ADR-010         # documento (fuente:ID) o decisión (ADR-EQ-002 con su criterio)
    criterio: null                            # EQ-002.1, MF-001.1…; null para documentos de arquitectura
    categoria: incumplimiento                 # incumplimiento|diseño|error|seguridad|deuda|documentacion
    severidad: alta                           # bloqueante|alta|media|baja
    titulo: Llamada al buró sin timeout
    detalle: Una demora del buró bloquea los hilos del servicio. Configurar timeout de conexión y de respuesta.
    evidencia: [src/main/java/BuroClient.java:41]
    fragmento: return restTemplate.getForObject(url, Respuesta.class);
    cita_documento: Ninguna llamada externa sin timeout explícito
    # documento_tercero: documentos/terceros/buro-credito/manual.md    (opcional)
    # cita_tercero: Timeout recomendado de 800 ms
componentes:                                  # todo lo que usa o expone, con evidencia
  - nombre: Buró de crédito
    tipo: integracion                         # base-de-datos|mensajeria|cache|integracion|api-expuesta|almacenamiento|programado
    tecnologia: HTTPS/JSON
    detalle: BURO_URL                         # variable, tópico, tabla o ruta que lo identifica
    direccion: saliente                       # produce|consume|saliente|entrante o null
    tercero: buro-credito                     # id de la ficha en terceros/, o null
    evidencia: [src/main/resources/application.yml:41, src/main/java/BuroClient.java:15]
```

Reglas:

- Copiar fragmentos y citas tal como están en la fuente; el script rechaza lo que no existe. Nunca
  reformular para que pase.
- `incumplimiento` exige `cita_documento`; sin cita, el hallazgo es `diseño`, `error` o `deuda`.
- Severidad de un criterio de ADR-EQ: la de su tabla, salvo motivo en el detalle.
- No repetir hallazgos automáticos ni de Sonar. Si un issue de Sonar incumple además un documento de
  mayor nivel, registrarlo en ese nivel.
- Un hallazgo es una señal concreta en una ubicación concreta ("la clase X mezcla acceso a datos y
  llamadas HTTP"), no "no cumple SOLID".
- Texto de un tercero: buscarlo con `documentos.py buscar <producto> "<palabras>"`.
- Repositorio `proveedor` o `config`: foco en integraciones, contratos y configuración.

## 5. Cerrar

```sh
.venv/bin/python herramientas/revision.py cerrar <producto> <repo> --archivos-leidos <N>
```

Registra el lote (todo o nada: si hay errores, se listan juntos; corregir y repetir), genera los C4
y cierra. Responder:

```markdown
## Revisión de código de <repo> (<producto>)

**Veredicto:** <PASA / NO PASA> · **Archivos leídos:** <N>

| Nivel | Evaluados | ✅ | 🚫 | 🔹 | 🔍 |
|---|---|---|---|---|---|

### Hallazgos principales
<hasta 8, por nivel y severidad: ID, criterio, título, evidencia>

### AS IS en una frase
<resumen>

Siguiente: chat nuevo con `/revisar <producto>`.
```
