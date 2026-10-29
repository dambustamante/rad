"""Revisión de lenguaje: voseo, expresiones vagas o de relleno y siglas sin explicar.

Uso: python herramientas/lenguaje.py <archivo> [<archivo> ...] [--estricto]

Las reglas viven en equipo/lenguaje.yaml y se pueden editar sin tocar código. Se ignoran los bloques
de código, el código en línea (`así`), las citas textuales («así» o > así) y el frontmatter YAML.
Con --estricto termina con código 1 si encuentra algo.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from comun import RAIZ, normalizar

PATRON_SIGLA = re.compile(r"\b([A-Z][A-Z0-9]{1,5}s?)\b")


def cargar_reglas(raiz: Path = RAIZ) -> dict:
    archivo = raiz / "equipo" / "lenguaje.yaml"
    if not archivo.exists():
        return {"voseo": [], "expresiones": [], "siglas_conocidas": []}
    reglas = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
    return {"voseo": reglas.get("voseo") or [], "expresiones": reglas.get("expresiones") or [],
            "siglas_conocidas": set(reglas.get("siglas_conocidas") or [])}


def lineas_revisables(texto: str) -> list[tuple[int, str]]:
    """Líneas de prosa: sin frontmatter, bloques de código, código en línea ni citas."""
    resultado, en_codigo = [], False
    lineas = texto.split("\n")
    inicio = 0
    if lineas and lineas[0].strip() == "---":
        fin = next((i for i, l in enumerate(lineas[1:], start=1) if l.strip() == "---"), None)
        inicio = (fin + 1) if fin else 0
    for numero, linea in enumerate(lineas[inicio:], start=inicio + 1):
        if linea.strip().startswith("```"):
            en_codigo = not en_codigo
            continue
        if en_codigo or linea.lstrip().startswith(">"):
            continue
        limpia = re.sub(r"`[^`]*`", " ", linea)
        limpia = re.sub(r"«[^»]*»|\"[^\"]*\"|“[^”]*”|<[^>\n]*>", " ", limpia)
        limpia = re.sub(r"\[[^\]]*\]\([^)]*\)", lambda m: m.group(0).split("](")[0][1:], limpia)
        limpia = re.sub(r"https?://\S+", " ", limpia)
        resultado.append((numero, limpia))
    return resultado


def revisar(texto: str, reglas: dict | None = None) -> list[dict]:
    """Avisos: {linea, regla, texto, sugerencia}."""
    reglas = reglas or cargar_reglas()
    avisos = []
    siglas_explicadas: set[str] = set()
    for numero, linea in lineas_revisables(texto):
        normalizada = normalizar(linea)
        # El voseo se distingue por la tilde ("ejecutá" frente a "ejecuta"): se compara sin quitarlas.
        minusculas = linea.lower()
        for palabra in reglas["voseo"]:
            if re.search(rf"(?<![\wáéíóúñ]){re.escape(palabra.lower())}(?![\wáéíóúñ])", minusculas):
                avisos.append({"linea": numero, "regla": "voseo", "texto": palabra,
                               "sugerencia": "usar español neutro (forma impersonal o infinitivo)"})
        for expresion in reglas["expresiones"]:
            if re.search(rf"\b{re.escape(normalizar(expresion['texto']))}\b", normalizada):
                avisos.append({"linea": numero, "regla": "expresión vaga o de relleno", "texto": expresion["texto"],
                               "sugerencia": expresion.get("sugerencia", "")})
        for coincidencia in PATRON_SIGLA.finditer(linea):
            sigla = coincidencia.group(1)
            base = sigla[:-1] if sigla.endswith("s") and sigla[:-1].isupper() else sigla
            if base in reglas["siglas_conocidas"] or sigla in reglas["siglas_conocidas"] or base in siglas_explicadas:
                continue
            if re.match(r"^[A-Z]+-\d", linea[coincidencia.start():]) or base.isdigit():
                continue  # identificadores como ADR-EQ-002, EQ-006.1 o FRAUD-123
            # Una sigla de varias palabras ("PCI DSS (…)") se explica una sola vez, al final.
            resto = re.sub(r"^(\s+[A-Z][A-Z0-9]{1,5})+", "", linea[coincidencia.end():])
            siguiente = resto[:3]
            anterior = linea[max(0, coincidencia.start() - 2):coincidencia.start()]
            if siguiente.lstrip().startswith("(") or anterior.endswith("("):
                siglas_explicadas.add(base)
                continue
            siglas_explicadas.add(base)
            avisos.append({"linea": numero, "regla": "sigla sin explicar", "texto": sigla,
                           "sugerencia": f"explicarla la primera vez: {sigla} (significado)"})
    return avisos


def revisar_archivo(archivo: Path, reglas: dict | None = None) -> list[dict]:
    return revisar(archivo.read_text(encoding="utf-8"), reglas)


def formatear(avisos: list[dict], nombre: str) -> list[str]:
    return [f"{nombre}:{a['linea']}: {a['regla']}: «{a['texto']}». {a['sugerencia']}".rstrip(". ") + "."
            for a in avisos]


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Revisión de lenguaje.")
    parser.add_argument("archivos", nargs="+", type=Path)
    parser.add_argument("--estricto", action="store_true", help="termina con código 1 si hay avisos")
    parser.add_argument("--raiz", type=Path, default=RAIZ)
    o = parser.parse_args(argumentos)
    reglas = cargar_reglas(o.raiz.resolve())
    total = 0
    for archivo in o.archivos:
        avisos = revisar_archivo(archivo, reglas)
        total += len(avisos)
        for linea in formatear(avisos, str(archivo)):
            print(linea)
    print(f"Avisos de lenguaje: {total}.")
    return 1 if o.estricto and total else 0


if __name__ == "__main__":
    sys.exit(main())
