"""Administra las fuentes de arquitectura declaradas en harness.yaml.

Uso:
  python herramientas/fuentes_arquitectura.py listar
  python herramientas/fuentes_arquitectura.py inspeccionar <url>
  python herramientas/fuentes_arquitectura.py agregar --id ID --url URL --ref REF --ruta RUTA --tipo TIPO
                                                     [--estado-por-defecto VIGENCIA]
  python herramientas/fuentes_arquitectura.py retirar --id ID

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

`inspeccionar` descarga el repositorio en `.cache/inspeccion/` (solo git) y muestra en JSON su
rama por defecto y las carpetas con documentos, para proponer las fuentes. `agregar` valida que la
ref y la ruta existan antes de escribir harness.yaml. Los comentarios de harness.yaml se conservan.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from comun import (RAIZ, ErrorRadiografia, clon_de_inspeccion, escribir_yaml_conservador, git,
                   leer_yaml_conservador, rama_por_defecto, resolver_commit, ruta_existe)
from sync_arquitectura import PATRON_ID_ADR, TIPOS, VIGENCIAS, leer_fuentes, secciones

CARPETAS_IGNORADAS = {".git", "node_modules", "site", "dist", "build"}
PROFUNDIDAD_MAXIMA = 5


# --- harness.yaml conservando comentarios ------------------------------------------------------

def leer_harness(raiz: Path):
    return leer_yaml_conservador(raiz / "harness.yaml")


def escribir_harness(raiz: Path, datos) -> None:
    escribir_yaml_conservador(raiz / "harness.yaml", datos)


def lista_fuentes(datos) -> CommentedSeq:
    arquitectura = datos.setdefault("arquitectura", CommentedMap())
    fuentes = arquitectura.get("fuentes")
    if not isinstance(fuentes, CommentedSeq):
        fuentes = CommentedSeq(fuentes or [])
        arquitectura["fuentes"] = fuentes
    return fuentes


# --- Inspección --------------------------------------------------------------------------------

def inspeccionar(url: str, raiz: Path) -> dict:
    """Describe el repositorio para proponer fuentes: rama por defecto y carpetas con documentos."""
    cache = clon_de_inspeccion(url, raiz)
    rama = rama_por_defecto(cache)
    commit = resolver_commit(cache, rama)
    archivos = git("ls-tree", "-r", "--name-only", commit, cwd=cache).splitlines()

    carpetas: dict[str, dict[str, int]] = {}
    rutas_adr: list[str] = []
    for ruta in archivos:
        partes = Path(ruta).parts
        if not ruta.lower().endswith(".md") or CARPETAS_IGNORADAS.intersection(partes):
            continue
        texto = git("show", f"{commit}:{ruta}", cwd=cache)
        titulo, contenido = secciones(texto.splitlines())
        es_adr = bool(titulo and PATRON_ID_ADR.search(titulo))
        tiene_estado = "estado" in contenido
        if es_adr:
            rutas_adr.append(ruta)
        for profundidad in range(0, min(len(partes) - 1, PROFUNDIDAD_MAXIMA) + 1):
            carpeta = "/".join(partes[:profundidad]) or "."
            datos = carpetas.setdefault(carpeta, {"documentos": 0, "adr": 0, "con_estado": 0})
            datos["documentos"] += 1
            datos["adr"] += int(es_adr)
            datos["con_estado"] += int(tiene_estado)

    ruta_adr = None
    if rutas_adr:
        comun = Path(rutas_adr[0]).parent
        for ruta in rutas_adr[1:]:
            while comun != Path(".") and comun not in Path(ruta).parents:
                comun = comun.parent
        # Si cada ADR vive en su propia carpeta (0001-titulo/index.md), se sube un nivel.
        if len(rutas_adr) == 1 and re.match(r"^\d{1,4}\b", comun.name):
            comun = comun.parent
        ruta_adr = comun.as_posix()

    nombre = re.sub(r"\.git$", "", url.rstrip("/").split("/")[-1].split(":")[-1])
    return {
        "url": url,
        "nombre_repositorio": nombre,
        "rama_por_defecto": rama,
        "commit": commit,
        "ruta_adr_sugerida": ruta_adr,
        "carpetas": [{"ruta": ruta, **datos} for ruta, datos in sorted(carpetas.items())],
    }


# --- Altas y bajas -----------------------------------------------------------------------------

def agregar(raiz: Path, id_fuente: str, url: str, ref: str, ruta: str, tipo: str,
            estado_por_defecto: str | None) -> None:
    datos = leer_harness(raiz)
    fuentes = lista_fuentes(datos)
    if any(str(f.get("id")) == id_fuente for f in fuentes):
        raise ErrorRadiografia(f"Ya existe una fuente con id '{id_fuente}'.")
    if any(str(f.get("url")) == url and str(f.get("ruta", ".")).strip("/") == ruta.strip("/") for f in fuentes):
        raise ErrorRadiografia(f"La carpeta '{ruta}' de '{url}' ya está declarada como fuente.")
    if tipo not in TIPOS:
        raise ErrorRadiografia(f"Tipo '{tipo}' inválido; valores válidos: {', '.join(TIPOS)}.")
    if estado_por_defecto and estado_por_defecto not in VIGENCIAS:
        raise ErrorRadiografia(f"estado_por_defecto inválido; valores válidos: {', '.join(VIGENCIAS)}.")

    cache = clon_de_inspeccion(url, raiz)
    commit = resolver_commit(cache, ref)
    if not ruta_existe(cache, commit, ruta):
        raise ErrorRadiografia(f"La ruta '{ruta}' no existe en la ref '{ref}' de '{url}'.")

    nueva = CommentedMap(id=id_fuente, url=url, ref=ref, ruta=ruta, tipo=tipo)
    if estado_por_defecto:
        nueva["estado_por_defecto"] = estado_por_defecto
    fuentes.fa.set_block_style()
    fuentes.append(nueva)
    leer_fuentes(datos)  # valida la configuración completa antes de escribir
    escribir_harness(raiz, datos)


def retirar(raiz: Path, id_fuente: str) -> None:
    datos = leer_harness(raiz)
    fuentes = lista_fuentes(datos)
    posiciones = [i for i, f in enumerate(fuentes) if str(f.get("id")) == id_fuente]
    if not posiciones:
        raise ErrorRadiografia(f"No existe una fuente con id '{id_fuente}'.")
    del fuentes[posiciones[0]]
    if not fuentes:
        fuentes.fa.set_flow_style()
    escribir_harness(raiz, datos)


def listar(raiz: Path) -> list[dict]:
    datos = leer_harness(raiz)
    return [dict(f) for f in lista_fuentes(datos)]


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Administra las fuentes de arquitectura.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    sub.add_parser("listar", help="muestra las fuentes configuradas")
    p_inspeccionar = sub.add_parser("inspeccionar", help="describe un repositorio para proponer fuentes")
    p_inspeccionar.add_argument("url")
    p_agregar = sub.add_parser("agregar", help="agrega una fuente validada a harness.yaml")
    p_agregar.add_argument("--id", required=True)
    p_agregar.add_argument("--url", required=True)
    p_agregar.add_argument("--ref", required=True)
    p_agregar.add_argument("--ruta", required=True)
    p_agregar.add_argument("--tipo", required=True, choices=TIPOS)
    p_agregar.add_argument("--estado-por-defecto", choices=VIGENCIAS)
    p_retirar = sub.add_parser("retirar", help="quita una fuente de harness.yaml")
    p_retirar.add_argument("--id", required=True)
    opciones = parser.parse_args(argumentos)
    raiz = opciones.raiz.resolve()

    try:
        if opciones.accion == "listar":
            print(json.dumps(listar(raiz), indent=2, ensure_ascii=False))
        elif opciones.accion == "inspeccionar":
            print(json.dumps(inspeccionar(opciones.url, raiz), indent=2, ensure_ascii=False))
        elif opciones.accion == "agregar":
            agregar(raiz, opciones.id, opciones.url, opciones.ref, opciones.ruta, opciones.tipo,
                    opciones.estado_por_defecto)
            print(f"Fuente '{opciones.id}' agregada a harness.yaml.")
        elif opciones.accion == "retirar":
            retirar(raiz, opciones.id)
            print(f"Fuente '{opciones.id}' retirada de harness.yaml. Su copia se elimina en la próxima sincronización.")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
