# /estado

Muestra en qué situación está radiografia y qué hacer a continuación. Es el punto de entrada: si no
se sabe qué comando usar, empezar por aquí.
Uso: `/estado` o `/estado semanal` (reporte semanal).

## Pasos

1. Ejecutar:

   ```sh
   make estado
   ```

   Solo lee archivos locales: no usa la red ni requiere análisis.

2. Mostrar el resumen y la lista "Qué sigue" tal como la entrega el script, en el mismo orden.

3. Ofrecer ejecutar el primer paso de la lista. Si es `/revisar`, recordar que conviene abrir un
   chat nuevo por repositorio.

## Reporte semanal (`/estado semanal`)

```sh
make semanal
```

Actualiza las copias de los repositorios y escribe `productos/<producto>/semanal/<AAAA-Wnn>.md` con lo
que cambió desde el reporte anterior: commits y ramas activas, MR o PR (si la plataforma está
configurada), ramas revisadas con su veredicto, hallazgos nuevos, corregidos y reaparecidos, y deuda
vencida. Mide repositorios, ramas y MR, no personas.

Mostrar el resumen y sugerir los siguientes pasos: `/revisar <producto> <repo> --rama <rama>` para las
ramas sin revisar, `/triar` para lo nuevo y lo reaparecido. No publica nada.

## Reglas

- No ejecutar ningún otro comando sin que el usuario lo pida.
- No agregar pasos que el script no sugiere.
