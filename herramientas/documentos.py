"""Documentos de un producto, siempre en markdown, en documentos/ de su harness.

Uso:
  python herramientas/documentos.py importar <producto> <archivo> [--titulo TEXTO] [--conversacion]
  python herramientas/documentos.py confluence <producto> <url o id de página> [...]
  python herramientas/documentos.py confluence <producto> --espacio CLAVE
  python herramientas/documentos.py sincronizar [<producto>]     trae las páginas de Confluence que cambiaron
  python herramientas/documentos.py listar <producto>
  python herramientas/documentos.py buscar <producto> <texto>
  python herramientas/documentos.py titulos <producto> <archivo>     títulos de un documento y sus líneas
  python herramientas/documentos.py ver <producto> <archivo> [--seccion TEXTO | --desde N]   una parte, nunca el documento entero

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

PDF, Word, PowerPoint, Excel, HTML y texto se convierten a markdown. Un dibujo o una conversación dejan un markdown
por completar con lo que muestran o lo que se decidió: el original no se copia. Confluence se conecta en solo lectura.
Cada documento indica su origen y su fecha. Un documento con un posible secreto no se guarda.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import requests

import harness
import terceros
from comun import RAIZ, ErrorRadiografia, cargar_env, slug

CARPETA = "documentos"
PENDIENTE = "<completar"
MARCA_CONFLUENCE = re.compile(r"<!-- confluence id=(\d+) version=(\d+) -->")
POR_PAGINA = 50
MAXIMO_LINEAS_VER = 150
ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*)$")
NIVELES = {f"h{n}": "#" * n for n in range(1, 7)}


# --- Confluence a markdown ---------------------------------------------------------------------

class _Markdown(HTMLParser):
    """Formato de almacenamiento de Confluence a markdown: títulos, listas, tablas, enlaces y código."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.listas: list[str] = []
        self.numeros: list[int] = []
        self.enlace: str | None = None
        self.fila: list[str] | None = None
        self.celda: list[str] | None = None
        self.filas_tabla = 0
        self.en_codigo = False

    def escribir(self, texto: str) -> None:
        (self.celda if self.celda is not None else self.partes).append(texto)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in NIVELES:
            self.escribir(f"\n\n{NIVELES[tag]} ")
        elif tag == "p" and self.celda is None:
            self.escribir("\n\n")
        elif tag == "br":
            self.escribir(" " if self.celda is not None else "\n")
        elif tag in ("strong", "b"):
            self.escribir("**")
        elif tag in ("em", "i"):
            self.escribir("*")
        elif tag in ("ul", "ol"):
            self.listas.append(tag)
            self.numeros.append(0)
            if len(self.listas) == 1:
                self.escribir("\n")
        elif tag == "li":
            self.numeros[-1] += 1
            marca = f"{self.numeros[-1]}." if self.listas[-1] == "ol" else "-"
            self.escribir("\n" + "  " * (len(self.listas) - 1) + marca + " ")
        elif tag == "a":
            self.enlace = dict(attrs).get("href")
            if self.enlace:
                self.escribir("[")
        elif tag == "table":
            self.filas_tabla = 0
            self.escribir("\n")
        elif tag == "tr":
            self.fila = []
        elif tag in ("td", "th"):
            self.celda = []
        elif tag == "pre" or tag == "ac:plain-text-body":
            self.en_codigo = True
            self.escribir("\n\n```\n")
        elif tag == "code" and not self.en_codigo:
            self.escribir("`")
        elif tag in ("ac:image", "img"):
            self.escribir("\n\n> Imagen de la página, no importada.\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("strong", "b"):
            self.escribir("**")
        elif tag in ("em", "i"):
            self.escribir("*")
        elif tag in ("ul", "ol"):
            self.listas.pop()
            self.numeros.pop()
            if not self.listas:
                self.escribir("\n")
        elif tag == "a" and self.enlace:
            self.escribir(f"]({self.enlace})")
            self.enlace = None
        elif tag in ("td", "th") and self.celda is not None:
            self.fila.append(re.sub(r"\s+", " ", "".join(self.celda)).strip().replace("|", "\\|"))
            self.celda = None
        elif tag == "tr" and self.fila is not None:
            self.partes.append("\n| " + " | ".join(self.fila) + " |")
            if self.filas_tabla == 0:
                self.partes.append("\n|" + "---|" * len(self.fila))
            self.filas_tabla += 1
            self.fila = None
        elif tag == "table":
            self.partes.append("\n")
        elif tag == "pre" or tag == "ac:plain-text-body":
            self.en_codigo = False
            self.escribir("\n```\n")
        elif tag == "code" and not self.en_codigo:
            self.escribir("`")

    def handle_data(self, data: str) -> None:
        self.escribir(data if self.en_codigo else re.sub(r"\s+", " ", data))

    def unknown_decl(self, data: str) -> None:
        if data.startswith("CDATA["):  # cuerpo de los bloques de código de Confluence
            self.escribir(data[6:])


def html_a_markdown(html: str) -> str:
    conversor = _Markdown()
    conversor.feed(html)
    return re.sub(r"\n{3,}", "\n\n", "".join(conversor.partes)).strip()


class ClienteConfluence:
    """Cliente de solo lectura de Confluence."""

    def __init__(self, env: dict[str, str], sesion: requests.Session | None = None) -> None:
        url, correo = env.get("CONFLUENCE_URL"), env.get("CONFLUENCE_EMAIL") or env.get("JIRA_EMAIL")
        token = env.get("CONFLUENCE_TOKEN") or env.get("JIRA_TOKEN")
        if not (url and correo and token):
            raise ErrorRadiografia("Falta la conexión a Confluence en .env: CONFLUENCE_URL, CONFLUENCE_EMAIL y CONFLUENCE_TOKEN.")
        self.url = url.rstrip("/")
        self.sesion = sesion or requests.Session()
        self.sesion.auth = (correo, token)
        self.sesion.headers["Accept"] = "application/json"

    def _leer(self, ruta: str, parametros: dict) -> dict:
        respuesta = self.sesion.get(f"{self.url}{ruta}", params=parametros, timeout=60)
        if respuesta.status_code in (401, 403):
            raise ErrorRadiografia(f"Confluence rechazó el acceso ({respuesta.status_code}). Verificar el token y sus permisos.")
        if respuesta.status_code == 404:
            raise ErrorRadiografia("Confluence no encontró esa página o el token no tiene acceso a ella.")
        if respuesta.status_code >= 400:
            raise ErrorRadiografia(f"Confluence respondió {respuesta.status_code}.")
        return respuesta.json()

    def pagina(self, id_pagina: str, con_cuerpo: bool = True) -> dict:
        return self._leer(f"/rest/api/content/{id_pagina}", {"expand": "version,_links" + (",body.storage" if con_cuerpo else "")})

    def ids_de_espacio(self, clave: str) -> list[str]:
        ids, inicio = [], 0
        while True:
            datos = self._leer("/rest/api/content", {"spaceKey": clave, "type": "page", "limit": POR_PAGINA, "start": inicio})
            ids += [str(r["id"]) for r in datos.get("results", [])]
            if len(datos.get("results", [])) < POR_PAGINA:
                return ids
            inicio += POR_PAGINA


def id_de_referencia(referencia: str) -> str:
    coincidencia = re.search(r"/pages/(\d+)", referencia) or re.search(r"[?&]pageId=(\d+)", referencia) or re.fullmatch(r"(\d+)", referencia.strip())
    if not coincidencia:
        raise ErrorRadiografia(f"'{referencia}' no es una URL ni un id de página de Confluence.")
    return coincidencia.group(1)


# --- Documentos --------------------------------------------------------------------------------

def carpeta(raiz: Path, producto: str) -> Path:
    if not harness.existe(raiz, producto):
        raise ErrorRadiografia(f"El producto '{producto}' no tiene harness.")
    return harness.ruta(raiz, producto) / CARPETA


def encabezado(titulo: str, tipo: str, origen: str, marca: str = "") -> str:
    lineas = [f"# {titulo}", "", f"- **Tipo:** {tipo}", f"- **Origen:** {origen}", f"- **Importado:** {date.today().isoformat()}"]
    return "\n".join(lineas) + ("\n\n" + marca if marca else "") + "\n\n"


def tiene_secreto(archivo: Path) -> bool:
    if not shutil.which("gitleaks"):
        return False
    return subprocess.run(["gitleaks", "detect", "--no-git", "--no-banner", "--source", str(archivo), "--exit-code", "1"],
                          capture_output=True).returncode == 1


def guardar(destino: Path, contenido: str) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")
    if tiene_secreto(destino):
        destino.unlink()
        raise ErrorRadiografia(f"{destino.name} tiene un posible secreto y no se guardó. El valor no se muestra: quitarlo del original.")


def importar(raiz: Path, producto: str, archivo: Path, titulo: str | None = None, conversacion: bool = False) -> dict:
    if not archivo.is_file():
        raise ErrorRadiografia(f"No existe el archivo {archivo}.")
    titulo = titulo or archivo.stem.replace("-", " ").replace("_", " ")
    destino = carpeta(raiz, producto) / f"{slug(titulo)}.md"
    if destino.exists():
        raise ErrorRadiografia(f"Ya existe {destino.name}: indicar otro título con --titulo.")
    if conversacion:
        tipo, cuerpo = "conversación", ("## Fecha y participantes\n\n<completar: fecha y roles, sin datos personales>\n\n"
                                        "## Qué se decidió\n\n<completar: decisiones y motivos, sin copiar el chat>\n\n"
                                        "## Qué quedó pendiente\n\n<completar: o Nada>\n")
    elif archivo.suffix.lower() in terceros.IMAGENES:
        tipo, cuerpo = "dibujo", "## Qué muestra\n\n<completar: componentes, flujos y datos que se ven en la imagen>\n"
    else:
        texto, motivo = terceros.extraer(archivo)
        if texto is None:
            raise ErrorRadiografia(f"No se pudo convertir {archivo.name}: {motivo}.")
        tipo, cuerpo = archivo.suffix.lower().lstrip(".") or "texto", texto.replace(terceros.SALTO_PAGINA, "\n\n---\n\n").strip() + "\n"
    guardar(destino, encabezado(titulo, tipo, archivo.name) + cuerpo)
    harness.commit(harness.ruta(raiz, producto), f"docs: agrega el documento {destino.stem}", [CARPETA])
    return {"archivo": destino, "pendiente": PENDIENTE in cuerpo}


def _escribir_pagina(destino_carpeta: Path, pagina: dict, base: str) -> Path:
    titulo, version = pagina["title"], pagina["version"]["number"]
    origen = base + (pagina.get("_links") or {}).get("webui", f"/pages/{pagina['id']}")
    destino = destino_carpeta / f"{slug(titulo)}-{pagina['id']}.md"
    marca = f"<!-- confluence id={pagina['id']} version={version} -->"
    guardar(destino, encabezado(titulo, "confluence", origen, marca) + html_a_markdown(pagina["body"]["storage"]["value"]) + "\n")
    return destino


def confluence(raiz: Path, producto: str, referencias: list[str], espacio: str | None = None, sesion=None) -> list[Path]:
    destino = carpeta(raiz, producto)
    cliente = ClienteConfluence(cargar_env(raiz), sesion)
    ids = [id_de_referencia(r) for r in referencias] + (cliente.ids_de_espacio(espacio) if espacio else [])
    if not ids:
        raise ErrorRadiografia("Indicar una página o --espacio.")
    archivos = [_escribir_pagina(destino, cliente.pagina(i), cliente.url) for i in ids]
    harness.commit(harness.ruta(raiz, producto), f"docs: importa {len(archivos)} página(s) de Confluence", [CARPETA])
    return archivos


def sincronizar(raiz: Path, producto: str, sesion=None) -> dict:
    """Vuelve a traer las páginas de Confluence ya importadas que tienen una versión nueva."""
    destino = harness.ruta(raiz, producto) / CARPETA
    importadas = [(a, MARCA_CONFLUENCE.search(a.read_text(encoding="utf-8"))) for a in sorted(destino.glob("*.md"))] if destino.exists() else []
    importadas = [(a, m) for a, m in importadas if m]
    if not importadas:
        return {"actualizadas": [], "errores": []}
    cliente = ClienteConfluence(cargar_env(raiz), sesion)
    actualizadas, errores = [], []
    for archivo, marca in importadas:
        try:
            if cliente.pagina(marca.group(1), False)["version"]["number"] > int(marca.group(2)):
                nuevo = _escribir_pagina(destino, cliente.pagina(marca.group(1)), cliente.url)
                if nuevo != archivo:
                    archivo.unlink()
                actualizadas.append(nuevo)
        except ErrorRadiografia as error:
            errores.append(f"{archivo.name}: {error}")
    if actualizadas:
        harness.commit(harness.ruta(raiz, producto), f"docs: actualiza {len(actualizadas)} página(s) de Confluence", [CARPETA])
    return {"actualizadas": actualizadas, "errores": errores}


def listar(raiz: Path, producto: str) -> list[dict]:
    filas = []
    for archivo in sorted(carpeta(raiz, producto).glob("*.md")):
        texto = archivo.read_text(encoding="utf-8")
        tipo = re.search(r"^- \*\*Tipo:\*\* (.+)$", texto, re.MULTILINE)
        filas.append({"archivo": archivo.name, "tipo": tipo.group(1) if tipo else "—", "pendiente": PENDIENTE in texto,
                      "lineas": len(texto.splitlines())})
    return filas


def buscar(raiz: Path, producto: str, consulta: str, limite: int = 20) -> list[str]:
    palabras = consulta.lower().split()
    resultado = []
    for archivo in sorted(carpeta(raiz, producto).glob("*.md")):
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1):
            if all(p in linea.lower() for p in palabras):
                resultado.append(f"{CARPETA}/{archivo.name}:{numero}: {linea.strip()[:160]}")
    return resultado[:limite]


def _lineas(raiz: Path, producto: str, archivo: str) -> list[str]:
    ruta = carpeta(raiz, producto) / Path(archivo).name
    if not ruta.is_file():
        raise ErrorRadiografia(f"No existe el documento '{archivo}'. Verlos con: documentos.py listar {producto}")
    return ruta.read_text(encoding="utf-8").splitlines()


def titulos(raiz: Path, producto: str, archivo: str) -> list[str]:
    return [f"{numero}: {linea}" for numero, linea in enumerate(_lineas(raiz, producto, archivo), start=1) if ENCABEZADO.match(linea)]


def ver(raiz: Path, producto: str, archivo: str, seccion: str | None = None, desde: int = 1) -> str:
    """Una sección, o un tramo desde una línea. Siempre con un máximo de líneas, para no gastar tokens en el documento completo."""
    lineas = _lineas(raiz, producto, archivo)
    inicio, fin = max(desde, 1) - 1, len(lineas)
    if seccion:
        inicio = next((i for i, l in enumerate(lineas) if ENCABEZADO.match(l) and seccion.lower() in l.lower()), None)
        if inicio is None:
            raise ErrorRadiografia(f"'{archivo}' no tiene una sección con '{seccion}'. Ver sus títulos con: documentos.py titulos")
        nivel = len(ENCABEZADO.match(lineas[inicio]).group(1))
        fin = next((i for i in range(inicio + 1, len(lineas)) if (m := ENCABEZADO.match(lineas[i])) and len(m.group(1)) <= nivel), len(lineas))
    tramo = lineas[inicio:min(fin, inicio + MAXIMO_LINEAS_VER)]
    resto = fin - inicio - len(tramo)
    return "\n".join(f"{inicio + n}: {l}" for n, l in enumerate(tramo, start=1)) + (f"\n… {resto} línea(s) más: seguir con --desde {inicio + len(tramo) + 1}" if resto > 0 else "")


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Documentos del producto, en markdown.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("importar")
    p.add_argument("producto")
    p.add_argument("archivo", type=Path)
    p.add_argument("--titulo")
    p.add_argument("--conversacion", action="store_true")
    p = sub.add_parser("confluence")
    p.add_argument("producto")
    p.add_argument("paginas", nargs="*")
    p.add_argument("--espacio")
    p = sub.add_parser("sincronizar")
    p.add_argument("producto", nargs="?")
    p = sub.add_parser("listar")
    p.add_argument("producto")
    p = sub.add_parser("buscar")
    p.add_argument("producto")
    p.add_argument("texto")
    p = sub.add_parser("titulos")
    p.add_argument("producto")
    p.add_argument("archivo")
    p = sub.add_parser("ver")
    p.add_argument("producto")
    p.add_argument("archivo")
    p.add_argument("--seccion")
    p.add_argument("--desde", type=int, default=1)
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    try:
        if o.accion == "importar":
            r = importar(raiz, o.producto, o.archivo, o.titulo, o.conversacion)
            print(f"Documento: {r['archivo'].relative_to(raiz)}" + (" (por completar)" if r["pendiente"] else ""))
        elif o.accion == "confluence":
            for archivo in confluence(raiz, o.producto, o.paginas, o.espacio):
                print(f"Documento: {archivo.relative_to(raiz)}")
        elif o.accion == "sincronizar":
            for nombre in harness.con_harness(raiz, o.producto):
                try:
                    r = sincronizar(raiz, nombre)
                except ErrorRadiografia as error:
                    print(f"  harness-{nombre}: NO DETERMINADO - {error}")
                    continue
                print(f"  harness-{nombre}: {len(r['actualizadas'])} página(s) de Confluence actualizada(s)")
                for error in r["errores"]:
                    print(f"    NO DETERMINADO - {error}")
        elif o.accion == "listar":
            for fila in listar(raiz, o.producto):
                print(f"  {fila['archivo']} · {fila['tipo']} · {fila['lineas']} líneas" + (" · por completar" if fila["pendiente"] else ""))
        elif o.accion == "titulos":
            print("\n".join(titulos(raiz, o.producto, o.archivo)) or "Sin títulos: usar buscar o ver --desde.")
        elif o.accion == "ver":
            print(ver(raiz, o.producto, o.archivo, o.seccion, o.desde))
        else:
            for linea in buscar(raiz, o.producto, o.texto):
                print(f"  {linea}")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
