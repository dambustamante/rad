# /estado

Muestra en qué situación está radiografia y qué hacer a continuación. Es el punto de entrada: si no
se sabe qué comando usar, empezar por acá.

## Pasos

1. Ejecutar:

   ```sh
   make estado
   ```

   Solo lee archivos locales: no usa la red ni requiere análisis.

2. Mostrar el resumen y la lista "Qué sigue" tal como la entrega el script, en el mismo orden.

3. Ofrecer ejecutar el primer paso de la lista. Si es `/revisar`, recordar que conviene abrir un
   chat nuevo por repositorio.

## Reglas

- No ejecutar ningún otro comando sin que el usuario lo pida.
- No agregar pasos que el script no sugiere.
