"""Terceros de un producto: el producto comprado y cada sistema externo con el que se integra.

Uso:
  python herramientas/terceros.py nuevo <producto> --id ID --nombre TEXTO [--rol producto-comprado|integracion]
  python herramientas/terceros.py listar <producto>
  python herramientas/terceros.py validar <producto> [--id ID]
  python herramientas/terceros.py indexar [<producto>]
  python herramientas/terceros.py buscar <producto> <texto> [--limite N]

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

Cada tercero vive en productos/<producto>/terceros/<id>/, con una ficha (ficha.yaml) que se completa con
el usuario y una carpeta docs/ donde se copia su documentación tal cual llega (PDF, Word, PowerPoint,
Excel, HTML, markdown, texto, contratos OpenAPI o AsyncAPI). `indexar` extrae el texto de forma
incremental a productos/<producto>/estado/terceros/<id>/ (no versionado) y reconoce los contratos por su
contenido. Los documentos se buscan y se citan como terceros/<id>/docs/<archivo>. Los originales nunca
se modifican.
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

import productos
from comun import RAIZ, ErrorRadiografia, leer_json, normalizar

ROLES = ("producto-comprado", "integracion")
DIRECCIONES = ("saliente", "entrante", "bidireccional")
POLITICAS = ("fail-open", "fail-closed", "no aplica")
NO_DETERMINADO = "NO DETERMINADO"
PREFIJO = "terceros/"

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


# --- Fichas ------------------------------------------------------------------------------------

PLANTILLA = """\
# Ficha del tercero {nombre}. Se completa con /producto; se valida con terceros.py validar.
# Lo que no se sepa se escribe NO DETERMINADO, nunca un valor supuesto.

id: {id}
nombre: {nombre}
rol: {rol}                       # producto-comprado (lo compramos) | integracion (sistema externo que usamos)
proveedor: NO DETERMINADO            # empresa que provee el producto o el servicio
direccion: saliente                   # saliente (lo consumimos) | entrante (nos llama) | bidireccional
protocolo: NO DETERMINADO             # por ejemplo HTTPS/JSON, gRPC, SFTP, Kafka
autenticacion: NO DETERMINADO         # por ejemplo mTLS, OAuth2 client credentials, API key

# Acuerdos de servicio (null si no hay).
sla:
  disponibilidad: null                # por ejemplo 99.9
  p95_ms: null                        # tiempo de respuesta esperado, percentil 95
limites:
  rps: null                           # solicitudes por segundo permitidas
  cuota_diaria: null

datos_sensibles: []                   # por ejemplo [rut, nombre, pan]

# Qué pasa con la operación si el tercero no responde (ADR-EQ-002).
politica_ante_falla: NO DETERMINADO   # fail-open | fail-closed | no aplica
justificacion: NO DETERMINADO         # motivo de negocio de la política

repos: []                             # repositorios del producto que lo usan; vacío = no determinado
contrato: null                        # ruta dentro de docs/ del contrato OpenAPI/AsyncAPI
"""


def base_producto(raiz: Path, producto: str) -> Path:
    base = raiz / "productos" / producto
    if not (base / "producto.yaml").exists():
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    return base


def carpeta_terceros(raiz: Path, producto: str) -> Path:
    return base_producto(raiz, producto) / "terceros"


def ids(raiz: Path, producto: str) -> list[str]:
    carpeta = carpeta_terceros(raiz, producto)
    return sorted(c.name for c in carpeta.iterdir() if (c / "ficha.yaml").exists()) if carpeta.exists() else []


def leer_fichas(raiz: Path, producto: str) -> dict[str, dict]:
    fichas = {}
    for id_tercero in ids(raiz, producto):
        archivo = carpeta_terceros(raiz, producto) / id_tercero / "ficha.yaml"
        try:
            fichas[id_tercero] = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as error:
            fichas[id_tercero] = {"_error": f"el YAML no es válido: {error}"}
    return fichas


def nuevo(raiz: Path, producto: str, id_tercero: str, nombre: str, rol: str = "integracion") -> Path:
    productos.validar_nombre(id_tercero, "id de tercero")
    if rol not in ROLES:
        raise ErrorRadiografia(f"Rol '{rol}' inválido; valores válidos: {', '.join(ROLES)}.")
    destino = carpeta_terceros(raiz, producto) / id_tercero
    if destino.exists():
        raise ErrorRadiografia(f"Ya existe el tercero '{id_tercero}' en el producto '{producto}'.")
    (destino / "docs").mkdir(parents=True)
    (destino / "docs" / ".gitkeep").write_text("", encoding="utf-8")
    (destino / "ficha.yaml").write_text(PLANTILLA.format(id=id_tercero, nombre=nombre, rol=rol), encoding="utf-8")
    return destino / "ficha.yaml"


def es_indeterminado(valor) -> bool:
    return valor is None or (isinstance(valor, str) and normalizar(valor) in (normalizar(NO_DETERMINADO), ""))


def validar(raiz: Path, producto: str, id_tercero: str, ficha: dict) -> tuple[list[str], list[str]]:
    """(errores, pendientes). Los pendientes son campos NO DETERMINADO: se informan, no son errores."""
    if "_error" in ficha:
        return [ficha["_error"]], []
    errores, pendientes = [], []
    if ficha.get("id") != id_tercero:
        errores.append(f"el id de la ficha ('{ficha.get('id')}') no coincide con la carpeta ('{id_tercero}')")
    if ficha.get("rol") not in ROLES:
        errores.append(f"rol '{ficha.get('rol')}' inválido; valores válidos: {', '.join(ROLES)}")
    for campo in ("nombre", "proveedor", "protocolo", "autenticacion"):
        if es_indeterminado(ficha.get(campo)):
            pendientes.append(campo)
    if ficha.get("direccion") not in DIRECCIONES:
        errores.append(f"direccion '{ficha.get('direccion')}' inválida; valores válidos: {', '.join(DIRECCIONES)}")
    politica = ficha.get("politica_ante_falla")
    if es_indeterminado(politica):
        pendientes.append("politica_ante_falla")
    elif politica not in POLITICAS:
        errores.append(f"politica_ante_falla '{politica}' inválida; valores válidos: {', '.join(POLITICAS)}")
    elif politica != "no aplica" and es_indeterminado(ficha.get("justificacion")):
        errores.append("una política fail-open o fail-closed necesita su justificación de negocio")
    for grupo, campos in (("sla", ("disponibilidad", "p95_ms")), ("limites", ("rps", "cuota_diaria"))):
        valores = ficha.get(grupo) or {}
        for campo in campos:
            valor = valores.get(campo)
            if valor is not None and not isinstance(valor, (int, float)):
                errores.append(f"{grupo}.{campo} debe ser un número o null")
    if not isinstance(ficha.get("datos_sensibles", []), list):
        errores.append("datos_sensibles debe ser una lista")
    repos_producto = {str(r["id"]) for r in productos.repos_de(productos.leer_productos(raiz)[producto])}
    repos = ficha.get("repos") or []
    desconocidos = [r for r in repos if r not in repos_producto]
    if desconocidos:
        errores.append(f"repositorios que no existen en el producto: {', '.join(desconocidos)}")
    if not repos:
        pendientes.append("repos")
    contrato = ficha.get("contrato")
    if contrato and not (carpeta_terceros(raiz, producto) / id_tercero / "docs" / contrato).is_file():
        errores.append(f"el contrato '{contrato}' no existe en docs/")
    return errores, pendientes


def para_repo(raiz: Path, producto: str, repo: str) -> list[dict]:
    """Fichas de los terceros que declara usar un repositorio (o que no declaran repositorios)."""
    return [{**ficha, "id": id_tercero} for id_tercero, ficha in leer_fichas(raiz, producto).items()
            if not (ficha.get("repos") or []) or repo in (ficha.get("repos") or [])]


# --- Documentación ------------------------------------------------------------------------------

def carpetas(raiz: Path, producto: str, id_tercero: str) -> tuple[Path, Path]:
    """(carpeta de originales, carpeta de estado) de la documentación de un tercero."""
    base = base_producto(raiz, producto)
    return base / "terceros" / id_tercero / "docs", base / "estado" / "terceros" / id_tercero


def indexar_tercero(raiz: Path, producto: str, id_tercero: str) -> dict:
    origen, destino = carpetas(raiz, producto, id_tercero)
    origen.mkdir(parents=True, exist_ok=True)
    destino.mkdir(parents=True, exist_ok=True)
    archivo_indice = destino / "indice.json"
    anterior = leer_json(archivo_indice)
    documentos: dict[str, dict] = {}
    procesados = 0
    for archivo in sorted(p for p in origen.rglob("*") if p.is_file() and p.name not in IGNORADOS | {".gitkeep"}):
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
    escribir_indice_docs(origen, id_tercero, documentos)
    return {"documentos": documentos, "procesados": procesados, "eliminados": sorted(set(anterior) - set(documentos))}


def indexar(raiz: Path, producto: str) -> dict[str, dict]:
    return {id_tercero: indexar_tercero(raiz, producto, id_tercero) for id_tercero in ids(raiz, producto)}


def escribir_indice_docs(origen: Path, id_tercero: str, documentos: dict[str, dict]) -> None:
    contratos = [d for d in documentos.values() if d["contrato"]]
    otros = [d for d in documentos.values() if d["estado"] == "indexado" and not d["contrato"]]
    pendientes = [d for d in documentos.values() if d["estado"] != "indexado"]
    lineas = [f"# Documentación de {id_tercero}", "",
              "> Archivo generado por `herramientas/terceros.py indexar`. No se edita a mano. Los documentos se "
              "copian tal cual en esta carpeta.", "",
              f"Documentos: {len(documentos)} · indexados: {len(documentos) - len(pendientes)} · no indexados: {len(pendientes)}", "",
              "## Contratos", ""]
    lineas += (["| Archivo | Tipo | Título | Versión | Operaciones | Canales |", "|---|---|---|---|---|---|"]
               + [f"| [{d['archivo']}]({d['archivo']}) | {d['contrato']['tipo']} {d['contrato']['version_especificacion']} "
                  f"| {d['contrato']['titulo'] or '—'} | {d['contrato']['version'] or '—'} | {d['contrato']['operaciones']} "
                  f"| {d['contrato']['canales']} |" for d in contratos]) if contratos else ["Ninguno."]
    lineas += ["", "## Documentos", ""]
    lineas += (["| Archivo | Formato | Páginas | Caracteres |", "|---|---|---|---|"]
               + [f"| [{d['archivo']}]({d['archivo']}) | {d['formato']} | {d['paginas'] or '—'} | {d['caracteres']} |" for d in otros]) if otros else ["Ninguno."]
    lineas += ["", "## No indexados (la revisión no los usa)", ""]
    lineas += (["| Archivo | Motivo |", "|---|---|"]
               + [f"| [{d['archivo']}]({d['archivo']}) | {d['motivo']} |" for d in pendientes]) if pendientes else ["Ninguno."]
    (origen / "INDICE.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def documentos_indexados(raiz: Path, producto: str, id_tercero: str) -> dict[str, dict]:
    return leer_json(carpetas(raiz, producto, id_tercero)[1] / "indice.json")


def separar(ruta: str) -> tuple[str, str]:
    """(id del tercero, ruta dentro de docs/) a partir de terceros/<id>/docs/<archivo>."""
    partes = ruta.removeprefix(PREFIJO).split("/", 2)
    if len(partes) < 3 or partes[1] != "docs":
        raise ErrorRadiografia(f"Ruta '{ruta}' inválida; formato: terceros/<id>/docs/<archivo>.")
    return partes[0], partes[2]


def texto_de(raiz: Path, producto: str, ruta: str) -> str:
    id_tercero, relativo = separar(ruta)
    documento = documentos_indexados(raiz, producto, id_tercero).get(relativo)
    if documento is None:
        raise ErrorRadiografia(f"'{ruta}' no está en la documentación de {id_tercero} (ver terceros/{id_tercero}/docs/INDICE.md).")
    if documento["estado"] != "indexado":
        raise ErrorRadiografia(f"'{ruta}' no está indexado: {documento['motivo']}.")
    return (carpetas(raiz, producto, id_tercero)[1] / "texto" / f"{relativo}.txt").read_text(encoding="utf-8")


def buscar(raiz: Path, producto: str, consulta: str, limite: int = 20) -> list[dict]:
    """Coincidencias de todas las palabras en una misma línea, en la documentación de todos los terceros."""
    palabras = [normalizar(p) for p in consulta.split() if p.strip()]
    if not palabras:
        raise ErrorRadiografia("La búsqueda necesita al menos una palabra.")
    resultados = []
    for id_tercero in ids(raiz, producto):
        for relativo, documento in sorted(documentos_indexados(raiz, producto, id_tercero).items()):
            if documento["estado"] != "indexado":
                continue
            ruta = f"{PREFIJO}{id_tercero}/docs/{relativo}"
            pagina = 1
            # split("\n") y no splitlines(): splitlines() descarta el salto de página que marca el cambio de página.
            for numero, linea in enumerate(texto_de(raiz, producto, ruta).split("\n"), start=1):
                pagina += linea.count(SALTO_PAGINA)
                if all(p in normalizar(linea) for p in palabras):
                    resultados.append({"archivo": ruta, "linea": numero, "pagina": pagina if documento["paginas"] else None,
                                       "texto": " ".join(linea.replace(SALTO_PAGINA, " ").split())[:200]})
                    if len(resultados) >= limite:
                        return resultados
    return resultados


# --- Índice y listado --------------------------------------------------------------------------

def listar(raiz: Path, producto: str) -> list[dict]:
    if producto not in productos.leer_productos(raiz):
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    filas = []
    for id_tercero, ficha in leer_fichas(raiz, producto).items():
        errores, pendientes = validar(raiz, producto, id_tercero, ficha)
        documentos = documentos_indexados(raiz, producto, id_tercero)
        sla = ficha.get("sla") or {}
        filas.append({
            "id": id_tercero, "nombre": ficha.get("nombre"), "rol": ficha.get("rol"), "direccion": ficha.get("direccion"),
            "protocolo": ficha.get("protocolo"), "p95_ms": sla.get("p95_ms"), "politica": ficha.get("politica_ante_falla"),
            "repos": ficha.get("repos") or [], "documentos": len(documentos),
            "contratos": sum(1 for d in documentos.values() if d["contrato"]),
            "sin_indexar": sum(1 for d in documentos.values() if d["estado"] != "indexado"),
            "errores": errores, "pendientes": pendientes,
        })
    if filas:
        lineas = [f"# Terceros de {producto}", "", "> Archivo generado por `herramientas/terceros.py listar`. No se edita a "
                  "mano; las fichas (`<id>/ficha.yaml`) sí.", "",
                  "| Tercero | Rol | Dirección | Protocolo | p95 (ms) | Política ante falla | Repositorios | Documentos | Estado de la ficha |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for f in filas:
            estado = ("❌ " + "; ".join(f["errores"])) if f["errores"] else (
                f"⏳ por completar: {', '.join(f['pendientes'])}" if f["pendientes"] else "✅ completa")
            lineas.append(f"| [{f['nombre'] or f['id']}]({f['id']}/ficha.yaml) | {f['rol']} | {f['direccion']} | {f['protocolo']} "
                          f"| {f['p95_ms'] if f['p95_ms'] is not None else '—'} | {f['politica']} | {', '.join(f['repos']) or '—'} "
                          f"| [{f['documentos']}]({f['id']}/docs/INDICE.md) | {estado} |")
        (carpeta_terceros(raiz, producto) / "INDICE.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return filas


def productos_registrados(raiz: Path) -> list[str]:
    return sorted(p.parent.name for p in (raiz / "productos").glob("*/producto.yaml"))


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Terceros del producto: fichas y documentación.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("nuevo")
    p.add_argument("producto")
    p.add_argument("--id", required=True)
    p.add_argument("--nombre", required=True)
    p.add_argument("--rol", default="integracion", choices=ROLES)
    p = sub.add_parser("listar")
    p.add_argument("producto")
    p = sub.add_parser("validar")
    p.add_argument("producto")
    p.add_argument("--id")
    p = sub.add_parser("indexar")
    p.add_argument("producto", nargs="?")
    p = sub.add_parser("buscar")
    p.add_argument("producto")
    p.add_argument("texto")
    p.add_argument("--limite", type=int, default=20)
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    try:
        if o.accion == "nuevo":
            archivo = nuevo(raiz, o.producto, o.id, o.nombre, o.rol)
            print(f"Creado: {archivo.relative_to(raiz)}. Copiar su documentación en {archivo.parent.relative_to(raiz)}/docs/.")
        elif o.accion in ("listar", "validar"):
            filas = [f for f in listar(raiz, o.producto) if not getattr(o, "id", None) or f["id"] == o.id]
            if not filas:
                print(f"El producto '{o.producto}' no tiene terceros registrados.")
            for f in filas:
                print(f"  {f['id']} ({f['rol']}): {'con errores' if f['errores'] else 'válida'}"
                      + (f" · por completar: {', '.join(f['pendientes'])}" if f["pendientes"] else ""))
                for error in f["errores"]:
                    print(f"    ERROR: {error}")
            if o.accion == "validar" and any(f["errores"] for f in filas):
                return 1
        elif o.accion == "indexar":
            for producto in [o.producto] if o.producto else productos_registrados(raiz):
                for id_tercero, r in indexar(raiz, producto).items():
                    docs = r["documentos"].values()
                    no_indexados = [d for d in docs if d["estado"] != "indexado"]
                    print(f"[{producto}] {id_tercero}: {len(r['documentos'])} documento(s), "
                          f"{sum(1 for d in docs if d['contrato'])} contrato(s), {len(no_indexados)} no indexado(s). "
                          f"Procesados ahora: {r['procesados']}.")
                    for d in no_indexados:
                        print(f"  No indexado: {d['archivo']}: {d['motivo']}")
                    if r["eliminados"]:
                        print(f"  Ya no están: {', '.join(r['eliminados'])}")
        elif o.accion == "buscar":
            resultados = buscar(raiz, o.producto, o.texto, o.limite)
            if not resultados:
                print("Sin coincidencias.")
            for r in resultados:
                print(f"  {r['archivo']}" + (f" (página {r['pagina']})" if r["pagina"] else "") + f":{r['linea']}: {r['texto']}")
        if o.accion in ("nuevo", "listar", "validar") or (o.accion == "indexar" and o.producto):
            import indices
            indices.indice_producto(raiz, o.producto)
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
