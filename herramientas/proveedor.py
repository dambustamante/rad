"""Documentación del proveedor de un producto comprado: productos/<producto>/proveedor/.

Uso:
  python herramientas/proveedor.py indexar [<producto>]
  python herramientas/proveedor.py buscar <producto> <texto> [--limite N]

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

Los archivos se copian tal cual en proveedor/, con la organización que se quiera. `indexar` extrae su
texto a productos/<producto>/estado/proveedor/ (no versionado), reconoce los contratos OpenAPI y
AsyncAPI por su contenido y escribe proveedor/INDICE.md con lo indexado y lo que no se pudo indexar.
Solo vuelve a procesar los archivos que cambiaron. Los originales nunca se modifican.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

import yaml

from comun import RAIZ, ErrorRadiografia, normalizar

TEXTO = {".md", ".markdown", ".txt", ".rst", ".adoc", ".csv"}
ESTRUCTURADO = {".yaml", ".yml", ".json"}
HTML = {".html", ".htm"}
OFFICE = {".docx": "word/document.xml", ".pptx": "ppt/slides/", ".xlsx": "xl/sharedStrings.xml"}
NO_SOPORTADOS = {".doc": "formato Word antiguo: guardar como .docx o PDF",
                 ".ppt": "formato PowerPoint antiguo: guardar como .pptx o PDF",
                 ".xls": "formato Excel antiguo: guardar como .xlsx o CSV"}
IMAGENES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".tiff", ".webp"}
IGNORADOS = {"INDICE.md", ".DS_Store"}
SALTO_PAGINA = "\f"


# --- Extracción --------------------------------------------------------------------------------

class _ExtractorHtml(HTMLParser):
    BLOQUES = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "pre"}

    def __init__(self) -> None:
        super().__init__()
        self.partes: list[str] = []
        self._omitir = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._omitir += 1
        elif tag in self.BLOQUES:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._omitir:
            self._omitir -= 1

    def handle_data(self, data):
        if not self._omitir:
            self.partes.append(data)


def _texto_xml(contenido: bytes, etiqueta_parrafo: str) -> str:
    """Texto de un XML de Office, con un salto por párrafo (w:p, a:p) o celda compartida (si)."""
    raiz = ElementTree.fromstring(contenido)
    parrafos = []
    for elemento in raiz.iter():
        if elemento.tag.endswith("}" + etiqueta_parrafo):
            texto = "".join(t.text or "" for t in elemento.iter() if t.tag.endswith("}t"))
            if texto.strip():
                parrafos.append(texto)
    return "\n".join(parrafos)


def extraer(archivo: Path) -> tuple[str | None, str | None]:
    """(texto, motivo). Si no se puede extraer, el texto es None y el motivo dice por qué."""
    extension = archivo.suffix.lower()
    try:
        if extension in TEXTO | ESTRUCTURADO:
            return archivo.read_text(encoding="utf-8", errors="replace"), None
        if extension in HTML:
            extractor = _ExtractorHtml()
            extractor.feed(archivo.read_text(encoding="utf-8", errors="replace"))
            return re.sub(r"\n\s*\n+", "\n\n", "".join(extractor.partes)).strip(), None
        if extension == ".pdf":
            if not shutil.which("pdftotext"):
                return None, "falta pdftotext: instalar con brew install poppler"
            resultado = subprocess.run(["pdftotext", "-layout", str(archivo), "-"], capture_output=True, text=True)
            if resultado.returncode != 0:
                return None, f"pdftotext no pudo leerlo: {resultado.stderr.strip()[:200]}"
            if not resultado.stdout.replace(SALTO_PAGINA, "").strip():
                return None, "el PDF no tiene texto extraíble (posiblemente escaneado como imagen)"
            return resultado.stdout, None
        if extension in OFFICE:
            with zipfile.ZipFile(archivo) as zip_office:
                if extension == ".docx":
                    return _texto_xml(zip_office.read(OFFICE[extension]), "p"), None
                if extension == ".xlsx":
                    nombres = zip_office.namelist()
                    if OFFICE[extension] not in nombres:
                        return None, "la planilla no tiene texto"
                    return _texto_xml(zip_office.read(OFFICE[extension]), "si"), None
                diapositivas = sorted((n for n in zip_office.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                                      key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
                return SALTO_PAGINA.join(_texto_xml(zip_office.read(n), "p") for n in diapositivas), None
        if extension in NO_SOPORTADOS:
            return None, NO_SOPORTADOS[extension]
        if extension in IMAGENES:
            return None, "imagen: no se puede leer como texto"
        return None, f"formato {extension or 'sin extensión'} no soportado"
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError, OSError) as error:
        return None, f"no se pudo leer el archivo: {error}"


def contar_paginas(texto: str) -> int | None:
    """Páginas de un texto con saltos de página; pdftotext también cierra la última con uno."""
    if SALTO_PAGINA not in texto:
        return None
    saltos = texto.count(SALTO_PAGINA)
    return saltos if texto.rstrip(" \n").endswith(SALTO_PAGINA) else saltos + 1


def clasificar_contrato(archivo: Path, texto: str) -> dict | None:
    """Datos del contrato si el archivo es un OpenAPI, Swagger o AsyncAPI."""
    if archivo.suffix.lower() not in ESTRUCTURADO:
        return None
    try:
        datos = json.loads(texto) if archivo.suffix.lower() == ".json" else yaml.safe_load(texto)
    except (json.JSONDecodeError, yaml.YAMLError):
        return None
    if not isinstance(datos, dict):
        return None
    tipo = "OpenAPI" if "openapi" in datos or "swagger" in datos else ("AsyncAPI" if "asyncapi" in datos else None)
    if tipo is None:
        return None
    info = datos.get("info") or {}
    operaciones = sum(1 for camino in (datos.get("paths") or {}).values() if isinstance(camino, dict)
                      for metodo in camino if metodo.lower() in ("get", "post", "put", "patch", "delete"))
    canales = len(datos.get("channels") or {})
    return {"tipo": tipo, "version_especificacion": str(datos.get("openapi") or datos.get("swagger") or datos.get("asyncapi")),
            "titulo": info.get("title"), "version": str(info.get("version", "")), "operaciones": operaciones, "canales": canales}


# --- Índice ------------------------------------------------------------------------------------

def carpetas(raiz: Path, producto: str) -> tuple[Path, Path]:
    base = raiz / "productos" / producto
    if not (base / "producto.yaml").exists():
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    return base / "proveedor", base / "estado" / "proveedor"


def indexar(raiz: Path, producto: str) -> dict:
    origen, destino = carpetas(raiz, producto)
    origen.mkdir(parents=True, exist_ok=True)
    destino.mkdir(parents=True, exist_ok=True)
    archivo_indice = destino / "indice.json"
    anterior = json.loads(archivo_indice.read_text(encoding="utf-8")) if archivo_indice.exists() else {}
    documentos: dict[str, dict] = {}
    procesados = 0
    for archivo in sorted(p for p in origen.rglob("*") if p.is_file() and p.name not in IGNORADOS):
        relativo = archivo.relative_to(origen).as_posix()
        huella = hashlib.sha256(archivo.read_bytes()).hexdigest()
        texto_extraido = destino / "texto" / f"{relativo}.txt"
        previo = anterior.get(relativo)
        if previo and previo["sha256"] == huella and (previo["estado"] != "indexado" or texto_extraido.exists()):
            documentos[relativo] = previo
            continue
        procesados += 1
        texto, motivo = extraer(archivo)
        registro = {"archivo": relativo, "formato": archivo.suffix.lower().lstrip(".") or "—", "sha256": huella,
                    "bytes": archivo.stat().st_size, "estado": "indexado" if texto is not None else "no indexado",
                    "motivo": motivo, "contrato": None, "paginas": None, "caracteres": 0}
        if texto is not None:
            texto_extraido.parent.mkdir(parents=True, exist_ok=True)
            texto_extraido.write_text(texto, encoding="utf-8")
            registro["caracteres"] = len(texto)
            registro["paginas"] = contar_paginas(texto)
            registro["contrato"] = clasificar_contrato(archivo, texto)
        documentos[relativo] = registro

    for relativo in set(anterior) - set(documentos):
        (destino / "texto" / f"{relativo}.txt").unlink(missing_ok=True)
    archivo_indice.write_text(json.dumps(documentos, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    escribir_indice_md(origen, producto, documentos)
    return {"documentos": documentos, "procesados": procesados,
            "eliminados": sorted(set(anterior) - set(documentos))}


def escribir_indice_md(origen: Path, producto: str, documentos: dict[str, dict]) -> None:
    contratos = [d for d in documentos.values() if d["contrato"]]
    otros = [d for d in documentos.values() if d["estado"] == "indexado" and not d["contrato"]]
    pendientes = [d for d in documentos.values() if d["estado"] != "indexado"]
    lineas = [f"# Documentación del proveedor de {producto}", "",
              "> Archivo generado por `herramientas/proveedor.py indexar`. No se edita a mano. Los documentos se "
              "copian tal cual en esta carpeta.", "",
              f"Documentos: {len(documentos)} · indexados: {len(documentos) - len(pendientes)} · no indexados: {len(pendientes)}", ""]
    lineas += ["## Contratos", ""]
    if contratos:
        lineas += ["| Archivo | Tipo | Título | Versión | Operaciones | Canales |", "|---|---|---|---|---|---|"]
        lineas += [f"| [{d['archivo']}]({d['archivo']}) | {d['contrato']['tipo']} {d['contrato']['version_especificacion']} "
                   f"| {d['contrato']['titulo'] or '—'} | {d['contrato']['version'] or '—'} | {d['contrato']['operaciones']} "
                   f"| {d['contrato']['canales']} |" for d in contratos]
    else:
        lineas.append("Ninguno.")
    lineas += ["", "## Documentos", ""]
    if otros:
        lineas += ["| Archivo | Formato | Páginas | Caracteres |", "|---|---|---|---|"]
        lineas += [f"| [{d['archivo']}]({d['archivo']}) | {d['formato']} | {d['paginas'] or '—'} | {d['caracteres']} |" for d in otros]
    else:
        lineas.append("Ninguno.")
    lineas += ["", "## No indexados (la revisión no los usa)", ""]
    if pendientes:
        lineas += ["| Archivo | Motivo |", "|---|---|"]
        lineas += [f"| [{d['archivo']}]({d['archivo']}) | {d['motivo']} |" for d in pendientes]
    else:
        lineas.append("Ninguno.")
    (origen / "INDICE.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def documentos_indexados(raiz: Path, producto: str) -> dict[str, dict]:
    _, destino = carpetas(raiz, producto)
    archivo = destino / "indice.json"
    return json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {}


def texto_de(raiz: Path, producto: str, relativo: str) -> str:
    _, destino = carpetas(raiz, producto)
    documento = documentos_indexados(raiz, producto).get(relativo)
    if documento is None:
        raise ErrorRadiografia(f"'{relativo}' no está en la documentación del proveedor (ver proveedor/INDICE.md).")
    if documento["estado"] != "indexado":
        raise ErrorRadiografia(f"'{relativo}' no está indexado: {documento['motivo']}.")
    return (destino / "texto" / f"{relativo}.txt").read_text(encoding="utf-8")


# --- Búsqueda ----------------------------------------------------------------------------------

def buscar(raiz: Path, producto: str, consulta: str, limite: int = 20) -> list[dict]:
    """Coincidencias de todas las palabras de la consulta en una misma línea, con página si la hay."""
    palabras = [normalizar(p) for p in consulta.split() if p.strip()]
    if not palabras:
        raise ErrorRadiografia("La búsqueda necesita al menos una palabra.")
    resultados = []
    for relativo, documento in sorted(documentos_indexados(raiz, producto).items()):
        if documento["estado"] != "indexado":
            continue
        pagina = 1
        # split("\n") y no splitlines(): splitlines() descarta el salto de página que marca el cambio de página.
        for numero, linea in enumerate(texto_de(raiz, producto, relativo).split("\n"), start=1):
            pagina += linea.count(SALTO_PAGINA)
            if all(p in normalizar(linea) for p in palabras):
                resultados.append({"archivo": relativo, "linea": numero,
                                   "pagina": pagina if documento["paginas"] else None,
                                   "texto": " ".join(linea.replace(SALTO_PAGINA, " ").split())[:200]})
                if len(resultados) >= limite:
                    return resultados
    return resultados


def productos_con_proveedor(raiz: Path) -> list[str]:
    return sorted(p.parent.name for p in (raiz / "productos").glob("*/producto.yaml"))


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Documentación del proveedor.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("indexar")
    p.add_argument("producto", nargs="?")
    p = sub.add_parser("buscar")
    p.add_argument("producto")
    p.add_argument("texto")
    p.add_argument("--limite", type=int, default=20)
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    try:
        if o.accion == "indexar":
            for producto in [o.producto] if o.producto else productos_con_proveedor(raiz):
                r = indexar(raiz, producto)
                docs = r["documentos"].values()
                no_indexados = [d for d in docs if d["estado"] != "indexado"]
                if not r["documentos"]:
                    print(f"[{producto}] Sin documentación del proveedor (copiar los archivos en productos/{producto}/proveedor/).")
                    continue
                print(f"[{producto}] {len(r['documentos'])} documento(s), {sum(1 for d in docs if d['contrato'])} contrato(s), "
                      f"{len(no_indexados)} no indexado(s). Procesados ahora: {r['procesados']}.")
                for d in no_indexados:
                    print(f"  No indexado: {d['archivo']}: {d['motivo']}")
                if r["eliminados"]:
                    print(f"  Ya no están: {', '.join(r['eliminados'])}")
                import indices
                indices.indice_producto(raiz, producto)
        elif o.accion == "buscar":
            resultados = buscar(raiz, o.producto, o.texto, o.limite)
            if not resultados:
                print("Sin coincidencias.")
            for r in resultados:
                ubicacion = f"{r['archivo']}" + (f" (página {r['pagina']})" if r["pagina"] else "") + f":{r['linea']}"
                print(f"  {ubicacion}: {r['texto']}")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
