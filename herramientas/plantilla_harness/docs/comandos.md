# Comandos de harness-{{producto}}

Los comandos que empiezan con `/` se escriben en el chat de Cursor. Los ejemplos usan la historia `FRAUD-123` y la
Tarea `FRAUD-200`. Para preparar el entorno, ver el [README](../README.md).

## Qué comando usar

| Qué se necesita | Comando |
|---|---|
| Crear la Tarea de una historia en Jira | [`/tarea <HISTORIA>`](#tarea) |
| Empezar una Tarea, un Error, un Hotfix o un Spike | [`/hdu <CLAVE>`](#hdu) |
| Validar la spec antes de su MR | [`python3 herramientas/hdu.py spec <CLAVE>`](#hdu) |
| Aprobar la spec | [MR de la spec](#mr-de-la-spec) |
| Programar con la spec aprobada | [`/desarrollar <CLAVE>`](#desarrollar) |
| Cerrar antes del MR del código | [`/listo <CLAVE>`](#listo) |
| Entregar el código | [MR del código](#mr-del-código) |
| Traer la última versión de todo | [`make actualizar`](#comandos-de-apoyo) |
| Cambiar los repositorios visibles en Cursor | [`make foco`](#comandos-de-apoyo) |
| Proponer un ADR del producto | [`harness.py adr`](#comandos-de-apoyo) |
| Saber qué cambia en un Hotfix, un Error o un Spike | [Casos distintos](#casos-distintos) |

## Detalle de cada comando

### /tarea

**Cuándo:** cuando la Tarea todavía no existe. Es opcional, porque también se puede crear a mano. Una historia puede
tener varias Tareas.

```text
/tarea FRAUD-123 --titulo "Desarrollar la consulta al buró"
```

- Muestra una vista previa y las Tareas que ya cuelgan de la historia.
- Con confirmación, crea la Tarea con Tipo `Producto`, colgando de la historia.
- Es el único comando de este repositorio que escribe en Jira.

**Se detiene si:** la incidencia no es una historia o su Medición HU no es aceptada.

**Después:** `/hdu` con la clave de la Tarea creada.

### /hdu

**Cuándo:** al empezar una Tarea, un Error, un Hotfix o un Spike.

```text
/hdu FRAUD-200
```

| Opción | Para qué |
|---|---|
| `--repos a,b` | Indica los repositorios, si no se pueden deducir de Jira |
| `--tipo fix` | Cambia el tipo de la rama: `feat`, `fix`, `docs`, `chore`, `test` o `refactor` |
| `--sin-rama` | No crea ramas |

- Trae la última versión de las reglas.
- Lee la Tarea y su historia: de ahí salen la Medición HU y los criterios de aceptación.
- Crea la rama `feat/FRAUD-200-...` en cada repositorio que toca y `docs/FRAUD-200-spec` en este repositorio.
- Deja visibles en Cursor solo esos repositorios.
- Escribe `trabajo/FRAUD-200/contexto.md`, con hasta 3 extractos de los documentos de arquitectura más relacionados, y
  el borrador `specs/FRAUD-200/spec.md`.

Cursor ayuda a completar la spec: objetivo, diseño, una prueba por criterio, reglas que aplican y lo que queda fuera
de alcance. Si la historia tiene varias Tareas, la spec deja solo los criterios que cubre esta. La validación es:

```sh
python3 herramientas/hdu.py spec FRAUD-200
```

**Se detiene si:**

- no puede actualizar las reglas, o este repositorio no está en `main`;
- la Medición HU no es Óptima, Completa o Adecuada (vacía se toma, y `/listo` exige revisar la deuda);
- la clave es de una historia (salida 4): primero hay que crear su Tarea;
- no sabe qué repositorios toca (salida 3): repetir con `--repos`.

### MR de la spec

**Cuándo:** con la spec válida. Todavía no se programa.

```sh
git add specs/FRAUD-200
git commit -m "docs: agrega la spec de FRAUD-200"
git push -u origin docs/FRAUD-200-spec
```

El MR se abre en GitLab. La spec queda **aprobada** cuando ese MR se integra en `main`.

### /desarrollar

**Cuándo:** con la spec aprobada.

```text
/desarrollar FRAUD-200
```

- Vuelve a `main`, trae las reglas y comprueba la aprobación.
- Cursor lee la spec, propone los pasos por criterio y pide confirmación.
- Programa en `code/<repo>/` y ejecuta las pruebas.

La conversación sigue siendo normal: "implementemos el criterio 2" o "revisa por qué falla esta prueba". Los commits
siguen Conventional Commits, por ejemplo `feat(buro): consulta el puntaje`.

Si algo no calza con la spec, un cambio menor se declara como desvío en `/listo`. Un cambio de alcance o de diseño se
detiene y se corrige la spec en un MR.

**Se detiene si:** la spec no está aprobada o no es válida.

### /listo

**Cuándo:** con el código terminado y todo en commits.

```text
/listo FRAUD-200
```

1. **Prepara:** trae las reglas y busca secretos, salidas a consola, `TODO`, cambios de API sin contrato,
   integraciones nuevas, pruebas debilitadas, y ramas o commits fuera de formato.
2. **Revisa:** Cursor contrasta el diff con la spec y con las reglas. Lo que no cumple se corrige.
3. **Registra** en `trabajo/FRAUD-200/listo.json` la prueba de cada criterio, la deuda que queda, los desvíos y las
   decisiones que aplican.
4. **Cierra:** escribe `trabajo/FRAUD-200/mr-<repo>.md` con la descripción del MR. La deuda queda en esa descripción, y
   radiografia la toma de ahí para llevarla a Jira.

**No cierra si:** la spec no está aprobada, un criterio no tiene prueba, una prueba está deshabilitada o una evidencia no
existe.

### MR del código

```sh
git -C code/<repo> push -u origin feat/FRAUD-200-...
```

El MR se abre en GitLab, en el repositorio del producto, con la descripción de `trabajo/FRAUD-200/mr-<repo>.md`. El
registro del final no se edita: lo usa la revisión. El MR se aprueba en GitLab, después de que radiografia lo revisa.

## Comandos de apoyo

| Comando | Cuándo | Qué hace |
|---|---|---|
| `make actualizar` | Al empezar el día | Trae la última versión de este repositorio y clona o actualiza los repositorios de `code/`. `ENLAZAR=~/repos` reutiliza clones que ya existen |
| `make foco REPOS=a,b` | Si hace falta | Deja visibles en Cursor solo esos repositorios |
| `make foco` | Si hace falta | Vuelve a dejar visibles todos los repositorios |
| `python3 herramientas/harness.py adr --titulo "<decisión>" --historia <CLAVE>` | Para proponer un ADR | Crea un ADR del producto en `Propuesto`; se integra por MR |

## Casos distintos

| Caso | Qué cambia |
|---|---|
| **Hotfix** | No espera la aprobación: completa la spec antes de `/listo` y la integra después. Rama `fix/` |
| **Error** | Mismo recorrido, con rama `fix/` |
| **Tarea de deuda** | Mismo recorrido, con rama `chore/` o la que indique `--tipo` |
| **Spike** | No lleva spec ni código: entrega un ADR del producto por MR |
| **Tarea sin historia** | Usa sus propios criterios y queda sin medir: `/listo` exige revisar la deuda |
