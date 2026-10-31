# /producto: harness del producto

`harness-<producto>` es el repositorio de trabajo del producto: reúne los repositorios del producto en
`code/`, las decisiones compiladas y los ADR del producto. radiografia lo crea y mantiene en
`productos/<producto>/harness/`; el primer push lo hace el usuario; los siguientes, `harness.py subir --confirmar`.

1. **Se crea con el producto:** `productos.py crear` genera la estructura, hace `git init` y el primer commit.
2. **Contenido:** lleva las reglas desde el inicio. El AS IS, los componentes y los hallazgos llegan después de
   `/revisar`, con la siguiente publicación.
3. **Subirlo** (lo hace el usuario): crear el repositorio `harness-<producto>` en GitLab y ejecutar los
   dos comandos que muestra el script (`remote add` y `push`). Configurar en GitLab que los MR del
   harness necesiten la aprobación de un par dev y del TL.
4. **Después:** `/actualizar` trae el harness, verifica la coherencia de sus ADR y regenera lo generado
   con commit local; `harness.py subir --confirmar` sube todos los harness de una vez. `/estado` avisa
   cuando hay commits sin subir.

Lo generado (`.cursor/rules/generado/`, `.cursor/arquitectura/`, `arquitectura.json`, `repos.json`, `GENERADO.json`, `decisiones/INDICE.md` y
`COHERENCIA.md`) no se edita a mano. El resto (AGENTS.md, README, Makefile, herramientas/ y la guardia)
es del equipo: se crea una vez y se mantiene por MR.
