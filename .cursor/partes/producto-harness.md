# /producto: harness del producto

`harness-<producto>` es el repositorio de trabajo del producto: reúne los repositorios del producto en
`code/`, las decisiones compiladas y los ADR del producto. radiografia lo crea y mantiene en
`productos/<producto>/harness/`; el primer push lo hace el usuario; los siguientes, `harness.py subir --confirmar`.

1. **Antes de crearlo**, conviene que el producto tenga al menos una revisión de código: lo generado lleva
   el AS IS, los componentes y los hallazgos de cada repositorio.
2. **Crear:**

   ```sh
   .venv/bin/python herramientas/harness.py crear <producto>
   ```

   Genera la estructura, mueve los ADR del producto a `decisiones/` del harness, hace `git init` y el
   primer commit. Mostrar qué se movió.
3. **Subirlo** (lo hace el usuario): crear el repositorio `harness-<producto>` en GitLab y ejecutar los
   dos comandos que muestra el script (`remote add` y `push`). Configurar en GitLab que los MR del
   harness necesiten la aprobación de un par dev y del TL.
4. **Después:** `/actualizar` trae el harness, verifica la coherencia de sus ADR y regenera lo generado
   con commit local; `harness.py subir --confirmar` sube todos los harness de una vez. `/estado` avisa
   cuando hay commits sin subir.

Lo generado (`.cursor/rules/generado/`, `.cursor/arquitectura/`, `arquitectura.json`, `repos.json`, `GENERADO.json`, `decisiones/INDICE.md` y
`COHERENCIA.md`) no se edita a mano. El resto (AGENTS.md, README, Makefile, herramientas/ y la guardia)
es del equipo: se crea una vez y se mantiene por MR.
