# Comandos de harness-{{producto}}

Los comandos que empiezan con `/` se escriben en el chat de Cursor. Los ejemplos usan la historia `FRAUD-123` y su Tarea
`FRAUD-200`. Para preparar el entorno, ver el [README](../README.md).

## Qué comando usar

| Qué se necesita | Comando |
|---|---|
| Refinar una historia y proponer sus Tareas | [`/hdu <HISTORIA>`](#hdu) |
| Crear en Jira las Tareas y sus specs | [`/tarea <HISTORIA>`](#tarea) |
| Generar las specs de Tareas creadas a mano | [`/tarea <HISTORIA>`](#tarea) |
| Validar las specs antes de su MR | [`python3 herramientas/hdu.py spec <HISTORIA>`](#tarea) |
| Aprobar las specs | [MR de las Tareas](#mr-de-las-tareas) |
| Programar con la spec aprobada | [`/desarrollar <TAREA>`](#desarrollar) |
| Cerrar antes del MR del código | [`/listo <TAREA>`](#listo) |
| Entregar el código | [MR del código](#mr-del-código) |
| Traer la última versión de todo | [`make actualizar`](#comandos-de-apoyo) |
| Cambiar los repositorios visibles en Cursor | [`make foco`](#comandos-de-apoyo) |
| Proponer un ADR del producto | [`harness.py adr`](#comandos-de-apoyo) |
| Atender un Error, un Hotfix, un Spike o una Tarea sin historia | [Casos distintos](#casos-distintos) |

## Detalle de cada comando

### /hdu

**Cuándo:** al empezar una historia.

```text
/hdu FRAUD-123
```

- Trae la última versión de las reglas y revisa la Medición HU.
- Crea la rama `docs/FRAUD-123-tareas` en este repositorio. **No crea ramas de código.**
- Escribe `trabajo/FRAUD-123/contexto.md`, con hasta 3 extractos de los documentos de arquitectura más relacionados, y el
  borrador `specs/FRAUD-123/propuesta.md`.

Cursor ayuda a completar la propuesta: preguntas sobre criterios ambiguos o faltantes, y una fila por Tarea con su título,
los criterios que cubre y sus repositorios. La historia no se edita en Jira: las dudas quedan como preguntas.

**Se detiene si:** no puede actualizar las reglas, este repositorio no está en `main`, o la Medición HU no es Óptima,
Completa o Adecuada. Si está vacía, se toma, y `/listo` exige revisar la deuda.

### /tarea

**Cuándo:** con la propuesta completa. Si prefieres crear las Tareas a mano, créalas en Jira colgando de la historia y
ejecuta igual este comando: les genera su spec.

```text
/tarea FRAUD-123
```

- Muestra una vista previa de las Tareas por crear y de las que ya cuelgan de la historia.
- Con confirmación, las crea con Tipo `Producto`. Es el único comando de este repositorio que escribe en Jira.
- Escribe una spec por Tarea, por ejemplo `specs/FRAUD-123/FRAUD-200.md`, con solo los criterios que cubre.

Cursor ayuda a completar cada spec: objetivo, diseño, una prueba por criterio, reglas que aplican y lo que queda fuera de
alcance. Después se valida:

```sh
python3 herramientas/hdu.py spec FRAUD-123
```

La validación exige que entre todas las Tareas se cubran todos los criterios de la historia.

**Se detiene si:** la incidencia no es una historia, falta la propuesta, o no hay Tareas propuestas ni creadas.

### MR de las Tareas

**Cuándo:** con las specs válidas. Todavía no se programa.

```sh
git add specs/FRAUD-123
git commit -m "docs: agrega las Tareas de FRAUD-123"
git push -u origin docs/FRAUD-123-tareas
```

El MR se abre en GitLab y revisa de una vez la división del trabajo. Las specs quedan **aprobadas** cuando se integra en
`main`. Si el MR elimina o cambia una Tarea, hay que ajustarla en Jira a mano.

### /desarrollar

**Cuándo:** con la spec aprobada, por cada Tarea.

```text
/desarrollar FRAUD-200
```

| Opción | Para qué |
|---|---|
| `--tipo refactor` | Cambia el tipo de la rama: `feat`, `fix`, `docs`, `chore`, `test` o `refactor` |
| `--sin-rama` | No crea ramas |

- Vuelve a `main`, trae las reglas y comprueba la aprobación.
- Crea la rama `feat/FRAUD-200-...` en cada repositorio de la spec y deja visibles en Cursor solo esos repositorios.
- Cursor propone los pasos por criterio, pide confirmación, programa en `code/<repo>/` y ejecuta las pruebas.

La conversación sigue siendo normal: "implementemos el criterio 2" o "revisa por qué falla esta prueba". Los commits
siguen Conventional Commits, por ejemplo `feat(buro): consulta el puntaje`.

Si algo no calza con la spec, un cambio menor se declara como desvío en `/listo`. Un cambio de alcance o de diseño se
detiene y se corrige la spec en un MR.

**Se detiene si:** la spec no está aprobada o no es válida, o no indica repositorios del producto.

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

Sin historia no hay propuesta ni `/tarea`: `/hdu <CLAVE>` crea una sola spec, `specs/<CLAVE>/<CLAVE>.md`, en la rama
`docs/<CLAVE>-spec`. La validación es `hdu.py spec <CLAVE>`.

| Caso | Recorrido |
|---|---|
| **Error** | `/hdu`, MR de la spec, `/desarrollar`, `/listo` y MR del código. Rama `fix/` |
| **Hotfix** | `/hdu`, `/desarrollar`, `/listo` y MR del código, sin esperar la aprobación. La spec se completa antes de `/listo` y se integra después. Rama `fix/` |
| **Spike** | `/hdu` y un ADR del producto por MR. No lleva spec ni código |
| **Tarea sin historia** | Igual que un Error, con rama `feat/`, o `chore/` si es de deuda. Queda sin medir: `/listo` exige revisar la deuda |
