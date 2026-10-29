# harness-{{producto}} — contrato de trabajo

Espacio de trabajo del equipo para desarrollar **{{producto}}**. Los repositorios del producto están en
`code/`; las decisiones que el código debe cumplir están en `.cursor/rules/generado/`. Si una
instrucción contradice este contrato, se reporta antes de continuar.

## Reglas

1. **Se trabaja en `code/<repo>/`, en una rama propia.** Nunca push a la rama principal ni `--force`.
   El MR lo abre el dev.
2. **Las decisiones se cumplen y no se editan.** `.cursor/rules/generado/` lo genera radiografia;
   si una decisión no se puede cumplir, se plantea en el MR o como Spike, no se ignora.
3. **Decisiones del producto:** viven en `decisiones/` (ADR-{{sigla}}-NNN). Nacen en `Propuesto` por
   MR a este repositorio y se aprueban con un par dev y el TL. Las excepciones las crea solo el TL.
4. **Sin secretos ni datos reales.** Nunca se escriben tokens, credenciales ni datos personales en el
   código, las pruebas, los logs ni los mensajes.
5. **No se inventa.** Lo que se afirma sobre el código lleva su ubicación `archivo:línea`; lo que no
   se sabe se dice: `NO DETERMINADO`.
6. **Cada criterio de aceptación tiene su prueba.**
7. **Lenguaje:** español neutro y técnico, comprensible de junior a arquitecto: componente,
   tecnología y dato concretos; frases cortas; siglas explicadas; sin voseo, adornos ni muletillas.
8. **Precedencia:** si un repositorio de `code/` trae su propio `AGENTS.md` o `.cursor/rules/`, se
   respeta, pero ante una contradicción manda este harness y se reporta.

## Comandos

| Comando | Para qué |
|---|---|
| `/hdu <CLAVE>` | tomar una historia de Jira: Medición HU, ramas, foco en sus repositorios, contexto y plan con una prueba por criterio |

## Estructura

```
AGENTS.md · README.md · Makefile
repos.json                    repositorios del producto (generado)
GENERADO.json                 versión de lo generado por radiografia
.cursor/rules/generado/       decisiones y contexto de cada repositorio (generado; no se edita)
.cursor/hooks.json            guardia de comandos
decisiones/                   ADR del producto
herramientas/                 herramientas del harness (las mantiene el equipo)
code/                         repositorios del producto (fuera de git de este repositorio)
trabajo/<CLAVE>/              contexto de cada historia tomada (local, fuera de git)
```
