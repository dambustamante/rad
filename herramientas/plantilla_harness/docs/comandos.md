# Comandos de harness-{{producto}}

Los comandos que empiezan con `/` se escriben en el chat de Cursor. Los ejemplos usan la historia `FRAUD-123` y su Tarea
`FRAUD-200`. Para preparar el entorno, ver el [README](../README.md).

## Qué comando usar

| Qué se necesita | Comando |
|---|---|
| Refinar una historia, y que te proponga y cree sus Tareas | [`/hdu <HISTORIA>`](#hdu) |
| Generar la spec de Tareas creadas a mano | [`/tarea <HISTORIA>`](#tarea) |
| Validar las specs antes de su MR | [`python3 herramientas/hdu.py spec <HISTORIA>`](#hdu) |
| Aprobar las specs | [MR de las Tareas](#mr-de-las-tareas) |
| Programar con la spec aprobada | [`/desarrollar <TAREA>`](#desarrollar) |
| Cerrar antes del MR del código | [`/listo <TAREA>`](#listo) |
| Entregar el código | [MR del código](#mr-del-código) |
| Traer la última versión de todo | [`make actualizar`](#comandos-de-apoyo) |
| Cambiar los repositorios visibles en Cursor | [`make foco`](#comandos-de-apoyo) |
| Proponer un ADR del producto | [`harness.py adr`](#comandos-de-apoyo) |
| Atender un Error, un Hotfix, un Spike o una Tarea sin historia | [Casos distintos](#casos-distintos) |

## Detalle de cada comando

Cada comando tiene dos partes. Los **scripts** hacen lo repetible, sin IA y sin gastar tokens. **Cursor** aporta el criterio: lee,
propone y escribe. Tú confirmas antes de lo importante.

### /hdu

| Comando | Qué hace |
|---|---|
| `/hdu <CLAVE>` | Con una historia: la refina, propone sus Tareas y, si confirmas, las crea. Con otra incidencia: ver [Casos distintos](#casos-distintos) |
| `/hdu <CLAVE> --repos a,b` | Indica los repositorios, si no se pueden deducir de Jira |

**Cuándo:** al empezar una historia. Ejemplo: `/hdu FRAUD-123`.

**Qué te pide:** revisar la propuesta y confirmar la creación de las Tareas. Después, revisar cada spec.

**Cómo lo hace:**

1. **Scripts:** traen la última versión de las reglas y leen la historia en Jira. Revisan la Medición HU.
2. **Scripts:** crean la rama `docs/FRAUD-123-tareas` en este repositorio y `trabajo/FRAUD-123/contexto.md`, con los criterios,
   hasta 3 extractos de arquitectura y los hallazgos relacionados. **No crean ramas de código.**
3. **Cursor te propone las Tareas:** lee el contexto, el código y los documentos relacionados, y escribe
   `specs/FRAUD-123/propuesta.md`, con una fila por Tarea: título, criterios que cubre y repositorios. Deja como preguntas los
   criterios ambiguos o faltantes, porque la historia no se edita en Jira. Puedes cambiar la propuesta.
4. **Scripts:** muestran una vista previa y, si confirmas, crean las Tareas en Jira con Tipo `Producto`, colgando de la historia.
   Es el único comando de este repositorio que escribe en Jira. Si no confirmas, no crean nada.
5. **Scripts:** escriben una spec por Tarea, por ejemplo `specs/FRAUD-123/FRAUD-200.md`, con solo los criterios que cubre.
6. **Cursor:** completa cada spec: objetivo, diseño, una prueba por criterio, reglas que aplican y lo que queda fuera de alcance.
7. **Scripts:** validan con `python3 herramientas/hdu.py spec FRAUD-123`. Exigen que entre todas las Tareas se cubran todos los
   criterios de la historia.

**Qué deja:** la propuesta y las specs en la rama, listas para el [MR de las Tareas](#mr-de-las-tareas), y las Tareas en Jira.

**Se detiene si:** no puede actualizar las reglas, este repositorio no está en `main`, o la Medición HU no es Óptima,
Completa o Adecuada. Si está vacía, se toma, y `/listo` exige revisar la deuda.

### /tarea

| Comando | Qué hace |
|---|---|
| `/tarea <HISTORIA>` | Crea la rama y la spec de las Tareas hechas a mano |

**Cuándo:** solo si creaste Tareas a mano en Jira, colgando de la historia, en lugar de usar las que propone `/hdu`, o si
agregaste una después.

**Cómo lo hace:** los scripts leen las Tareas que cuelgan de la historia y escriben la spec de las que no la tienen. No escriben en
Jira. Cursor ayuda a completar cada spec y a dejar solo los criterios que cubre y sus repositorios. Se valida igual que en `/hdu`.

**Se detiene si:** la incidencia no es una historia, su Medición HU no es aceptada o no hay Tareas colgando de ella.

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

| Comando | Qué hace |
|---|---|
| `/desarrollar <CLAVE>` | Comprueba la aprobación, crea las ramas de código y programa contra la spec |
| `/desarrollar <CLAVE> --tipo refactor` | Cambia el tipo de la rama: `feat`, `fix`, `docs`, `chore`, `test` o `refactor` |

**Cuándo:** con la spec aprobada, por cada Tarea.

**Qué te pide:** confirmar los pasos propuestos y los cambios delicados.

**Cómo lo hace:**

1. **Scripts:** vuelven a `main`, traen las reglas y comprueban que la spec esté aprobada y sea válida.
2. **Scripts:** crean `feat/FRAUD-200-...` en cada repositorio de la spec, dejan visibles en Cursor solo esos repositorios y
   escriben el contexto de la Tarea. No cambian de rama un repositorio con cambios sin commit.
3. **Cursor:** lee la spec, propone los pasos por criterio, programa en `code/<repo>/` y ejecuta las pruebas.

La conversación sigue siendo normal: "implementemos el criterio 2" o "revisa por qué falla esta prueba". Los commits
siguen Conventional Commits, por ejemplo `feat(buro): consulta el puntaje`.

Si algo no calza con la spec, un cambio menor se declara como desvío en `/listo`. Un cambio de alcance o de diseño se
detiene y se corrige la spec en un MR.

**Se detiene si:** la spec no está aprobada o no es válida, o no indica repositorios del producto.

### /listo

| Comando | Qué hace |
|---|---|
| `/listo <CLAVE>` | Verifica el código contra su spec y escribe la descripción del MR |

**Cuándo:** con el código terminado y todo en commits.

**Qué te pide:** confirmar, corregir o descartar la deuda propuesta.

**Cómo lo hace:**

1. **Scripts:** traen las reglas y buscan secretos, salidas a consola, `TODO`, cambios de API sin contrato, integraciones nuevas,
   pruebas debilitadas, y ramas o commits fuera de formato.
2. **Cursor:** contrasta el diff con la spec y con las reglas. Lo que no cumple se corrige.
3. **Cursor:** registra en `trabajo/FRAUD-200/listo.json` la prueba de cada criterio, la deuda que queda, los desvíos y las
   decisiones que aplican.
4. **Scripts:** validan ese registro y escriben `trabajo/FRAUD-200/mr-<repo>.md` con la descripción del MR. La deuda queda en esa
   descripción, y radiografia la toma de ahí para llevarla a Jira.

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
| `make foco [REPOS=a,b]` | Si hace falta | Deja visibles en Cursor solo esos repositorios o, sin indicarlos, todos |
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
