"""Todo lo relacionado con Jira: leer historias de usuario y crear Tareas, Spikes, Errores y Hotfix.

Lectura (insumo para proponer ADR de producto):
  python herramientas/jira.py sincronizar [<producto>]
  python herramientas/jira.py candidatas <producto> [--todas]
  python herramientas/jira.py clasificar <producto> [--archivo LOTE.yaml]
  python herramientas/jira.py propuestas <producto>
  python herramientas/jira.py confirmar <producto> --adr ADR-XX-NNN

Creación (ADR-EQ-009):
  python herramientas/jira.py nueva <producto> --tipo tarea|spike|error|hotfix --titulo TEXTO
                                    [--categoria "Deuda Técnica"|"Deuda Operativa"]
                                    [--desde H-0001,H-0002] [--repos a,b] [--tema "palabras clave"]
                                    [--hotfix CLAVE]   (un Error de seguimiento de un Hotfix)
  python herramientas/jira.py validar <producto> <borrador>
  python herramientas/jira.py listar <producto>
  python herramientas/jira.py crear <producto> <borrador> [--confirmar]

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

Configuración de lectura en producto.yaml (bloque `historias`: fuente jira | archivo | ninguna, jql o
tablero, campo_tipo, archivo, proyecto) y de creación en harness.yaml (bloque `jira`). Conexión en
.env: JIRA_URL, JIRA_EMAIL, JIRA_TOKEN. La única escritura hacia Jira es `crear --confirmar`.
Historias leídas: productos/<producto>/estado/historias/; índice: historias/INDICE.md; borradores:
historias/borradores/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests
import yaml

import hallazgos as registro_hallazgos
import lenguaje
import productos
import terceros
from coherencia import leer_arquitectura_vigente, leer_decisiones_equipo, leer_decisiones_producto
from comun import RAIZ, ErrorRadiografia, cargar_config, cargar_env, escribir_json, leer_json, normalizar, slug
from sync_arquitectura import secciones

# ===== Lectura de historias ===================================================================

FUENTES = ("jira", "archivo", "ninguna")
CLASIFICACIONES = ("sin_impacto", "candidata", "choque")
TIPOS_SIEMPRE = {"spike", "deuda tecnica"}
CAMPOS_JIRA = ["summary", "description", "status", "created", "updated", "labels"]
PATRON_SENALES = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:ms|milisegundos?|segundos?|minutos?)\b|\b(?:tps|rps)\b|latencia|tiempo de respuesta|"
    r"disponibilidad|\bsla\b|retencion|conservar|\b\d+\s*anos\b|cifra|encripta|\bpci\b|auditori|trazabilidad|timeout|"
    r"reintent|idempoten|concurren|escalab|rechaz|fail[- ]?(?:open|closed)|degrada|autenticac|autorizac|\bmtls\b|"
    r"datos? sensibles?|enmascar|\blogs?\b|monitoreo|circuit breaker")
# "alerta" no es señal: en un motor de fraudes es un término de negocio (alertas de fraude), no de monitoreo.
PATRON_TITULO_CRITERIOS = re.compile(r"criterios? de aceptacion|acceptance criteria")
PATRON_GHERKIN = re.compile(r"^\s*[-*]?\s*(dado|cuando|entonces|y|given|when|then|and)\b", re.IGNORECASE)


# --- Configuración -----------------------------------------------------------------------------

def leer_config(raiz: Path, producto: str) -> dict:
    archivo = raiz / "productos" / producto / "producto.yaml"
    if not archivo.exists():
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    config = (yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}).get("historias") or {}
    fuente = config.get("fuente", "ninguna")
    if fuente not in FUENTES:
        raise ErrorRadiografia(f"historias.fuente '{fuente}' inválida en {producto}; valores válidos: {', '.join(FUENTES)}.")
    if fuente == "jira" and not (config.get("jql") or config.get("tablero")):
        raise ErrorRadiografia(f"El producto '{producto}' usa historias de Jira: definir historias.jql o historias.tablero.")
    if fuente == "archivo" and not config.get("archivo"):
        raise ErrorRadiografia(f"El producto '{producto}' usa historias desde archivo: definir historias.archivo.")
    return {**config, "fuente": fuente}


def carpetas(raiz: Path, producto: str) -> tuple[Path, Path]:
    base = raiz / "productos" / producto
    return base / "historias", base / "estado" / "historias"


# --- Texto de las historias --------------------------------------------------------------------

def adf_a_texto(nodo) -> str:
    """Convierte el formato de documento de Atlassian (ADF) a texto con títulos y listas."""
    if nodo is None:
        return ""
    if isinstance(nodo, str):
        return nodo
    if isinstance(nodo, list):
        return "".join(adf_a_texto(n) for n in nodo)
    tipo, contenido = nodo.get("type"), nodo.get("content", [])
    atributos = nodo.get("attrs") or {}
    if tipo == "text":
        return nodo.get("text", "")
    if tipo == "hardBreak":
        return "\n"
    if tipo in ("mention", "emoji"):
        return atributos.get("text") or atributos.get("shortName", "")
    if tipo == "inlineCard":
        return atributos.get("url", "")
    if tipo == "heading":
        return "#" * int(atributos.get("level", 2)) + " " + adf_a_texto(contenido).strip() + "\n\n"
    if tipo == "paragraph":
        return adf_a_texto(contenido).strip() + "\n\n"
    if tipo in ("bulletList", "orderedList"):
        lineas = []
        for numero, item in enumerate(contenido, start=1):
            marca = f"{numero}." if tipo == "orderedList" else "-"
            texto = adf_a_texto(item.get("content", [])).strip().replace("\n\n", "\n")
            lineas.append(f"{marca} " + texto.replace("\n", "\n  "))
        return "\n".join(lineas) + "\n\n"
    if tipo == "codeBlock":
        return "```\n" + adf_a_texto(contenido) + "\n```\n\n"
    if tipo == "rule":
        return "---\n\n"
    if tipo == "tableRow":
        return "| " + " | ".join(adf_a_texto(c.get("content", [])).strip() for c in contenido) + " |\n"
    return adf_a_texto(contenido)


def es_titulo(linea: str) -> str | None:
    """Texto del título si la línea es un título markdown, una línea en negrita o termina en dos puntos."""
    limpia = linea.strip()
    if re.match(r"^#{1,6}\s", limpia):
        return limpia.lstrip("#").strip()
    if re.fullmatch(r"\*\*[^*]+\*\*:?|__[^_]+__:?", limpia):
        return limpia.strip("*_: ")
    if re.fullmatch(r"[^\s].{0,60}:", limpia) and not limpia.startswith(("-", "*")):
        return limpia.rstrip(":")
    return None


def extraer_criterios(texto: str) -> str | None:
    """Criterios de aceptación: la sección con ese título; si no hay, los escenarios Dado/Cuando/Entonces."""
    lineas = texto.splitlines()
    for indice, linea in enumerate(lineas):
        titulo = es_titulo(linea)
        if titulo and PATRON_TITULO_CRITERIOS.search(normalizar(re.sub(r"^\d+[.)]\s*", "", titulo))):
            seccion = []
            for siguiente in lineas[indice + 1:]:
                if es_titulo(siguiente) and not PATRON_GHERKIN.match(siguiente):
                    break
                seccion.append(siguiente)
            contenido = "\n".join(seccion).strip()
            return contenido or None
    gherkin = [l.strip() for l in lineas if PATRON_GHERKIN.match(l)]
    return "\n".join(gherkin) if gherkin else None


def valor_tipo(valor) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, list):
        return ", ".join(filter(None, (valor_tipo(v) for v in valor))) or None
    if isinstance(valor, dict):
        return valor.get("value") or valor.get("name")
    return str(valor).strip() or None


def huella_historia(historia: dict) -> str:
    partes = [historia.get("titulo") or "", historia.get("descripcion") or "", historia.get("criterios") or "",
              historia.get("tipo") or ""]
    return hashlib.sha256("\n␞\n".join(partes).encode("utf-8")).hexdigest()


def texto_completo(historia: dict) -> str:
    return "\n".join(filter(None, (historia.get("titulo"), historia.get("descripcion"), historia.get("criterios"))))


# --- Fuentes -----------------------------------------------------------------------------------

class ClienteJira:
    """Cliente de solo lectura de Jira Cloud."""

    def __init__(self, url: str, email: str, token: str, sesion: requests.Session | None = None) -> None:
        self.url = url.rstrip("/")
        self.sesion = sesion or requests.Session()
        self.sesion.auth = (email, token)
        self.sesion.headers["Accept"] = "application/json"

    def _respuesta(self, respuesta) -> dict | list:
        if respuesta.status_code == 401:
            raise ErrorRadiografia("Jira rechazó las credenciales (401). Verificar JIRA_EMAIL y JIRA_TOKEN.")
        if respuesta.status_code == 403:
            raise ErrorRadiografia("El token de Jira no tiene permiso para leer esas historias (403).")
        if respuesta.status_code >= 400:
            raise ErrorRadiografia(f"Jira respondió {respuesta.status_code}: {respuesta.text[:300]}")
        return respuesta.json()

    def id_campo(self, nombre: str) -> str:
        campos = self._respuesta(self.sesion.get(f"{self.url}/rest/api/3/field", timeout=30))
        for campo in campos:
            if normalizar(campo.get("name", "")) == normalizar(nombre):
                return campo["id"]
        personalizados = sorted(c.get("name", "") for c in campos if str(c.get("id", "")).startswith("customfield_"))
        raise ErrorRadiografia(f"No existe el campo '{nombre}' en Jira. Campos personalizados disponibles: "
                               f"{', '.join(personalizados[:40])}.")

    def buscar(self, jql: str, campos: list[str]) -> list[dict]:
        historias, siguiente = [], None
        while True:
            cuerpo = {"jql": jql, "fields": campos, "maxResults": 100}
            if siguiente:
                cuerpo["nextPageToken"] = siguiente
            datos = self._respuesta(self.sesion.post(f"{self.url}/rest/api/3/search/jql", json=cuerpo, timeout=60))
            historias += datos.get("issues", [])
            siguiente = datos.get("nextPageToken")
            if not siguiente or datos.get("isLast"):
                return historias

    def tablero(self, tablero: int, jql: str | None, campos: list[str]) -> list[dict]:
        historias, inicio = [], 0
        while True:
            parametros = {"startAt": inicio, "maxResults": 100, "fields": ",".join(campos)}
            if jql:
                parametros["jql"] = jql
            datos = self._respuesta(self.sesion.get(f"{self.url}/rest/agile/1.0/board/{tablero}/issue", params=parametros, timeout=60))
            lote = datos.get("issues", [])
            historias += lote
            inicio += len(lote)
            if not lote or inicio >= datos.get("total", 0):
                return historias


def desde_jira(config: dict, env: dict[str, str], sesion=None) -> list[dict]:
    faltantes = [v for v in ("JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN") if not env.get(v)]
    if faltantes:
        raise ErrorRadiografia(f"Faltan variables de Jira en .env: {', '.join(faltantes)}.")
    cliente = ClienteJira(env["JIRA_URL"], env["JIRA_EMAIL"], env["JIRA_TOKEN"], sesion)
    campo_tipo = cliente.id_campo(config["campo_tipo"]) if config.get("campo_tipo") else None
    campos = CAMPOS_JIRA + ([campo_tipo] if campo_tipo else [])
    if config.get("tablero"):
        jql = f'labels = "{config["etiqueta"]}"' if config.get("etiqueta") else None
        crudas = cliente.tablero(int(config["tablero"]), jql, campos)
    else:
        crudas = cliente.buscar(config["jql"], campos)
    historias = []
    for cruda in crudas:
        campos_historia = cruda.get("fields", {})
        descripcion = adf_a_texto(campos_historia.get("description")).strip()
        historias.append({
            "clave": cruda["key"],
            "titulo": campos_historia.get("summary") or "",
            "descripcion": descripcion,
            "criterios": extraer_criterios(descripcion),
            "tipo": valor_tipo(campos_historia.get(campo_tipo)) if campo_tipo else None,
            "estado": (campos_historia.get("status") or {}).get("name"),
            "actualizada": campos_historia.get("updated"),
            "url": f"{env['JIRA_URL'].rstrip('/')}/browse/{cruda['key']}",
        })
    return historias


COLUMNAS_CSV = {
    "clave": ("Issue key", "Clave de incidencia", "Clave", "Key"),
    "titulo": ("Summary", "Resumen"),
    "descripcion": ("Description", "Descripción", "Descripcion"),
    "estado": ("Status", "Estado"),
    "actualizada": ("Updated", "Actualizada", "Actualizado"),
}


def desde_archivo(raiz: Path, producto: str, config: dict) -> list[dict]:
    carpeta, _ = carpetas(raiz, producto)
    archivo = carpeta / config["archivo"]
    if not archivo.exists():
        raise ErrorRadiografia(f"No existe {archivo.relative_to(raiz)}. Copiar ahí la exportación CSV de Jira.")
    with archivo.open(encoding="utf-8-sig", newline="") as entrada:
        filas = list(csv.DictReader(entrada))
    if not filas:
        return []
    columnas = filas[0].keys()

    def columna(nombres: tuple[str, ...]) -> str | None:
        return next((c for c in columnas if c.strip() in nombres), None)

    mapa = {campo: columna(nombres) for campo, nombres in COLUMNAS_CSV.items()}
    if not mapa["clave"] or not mapa["titulo"]:
        raise ErrorRadiografia("El CSV no tiene las columnas de clave y resumen de una exportación de Jira.")
    nombre_tipo = config.get("campo_tipo")
    columna_tipo = next((c for c in columnas if nombre_tipo and normalizar(nombre_tipo) in normalizar(c)), None)
    historias = []
    for fila in filas:
        descripcion = (fila.get(mapa["descripcion"]) or "").strip() if mapa["descripcion"] else ""
        historias.append({
            "clave": fila[mapa["clave"]].strip(),
            "titulo": (fila.get(mapa["titulo"]) or "").strip(),
            "descripcion": descripcion,
            "criterios": extraer_criterios(descripcion),
            "tipo": ((fila.get(columna_tipo) or "").strip() or None) if columna_tipo else None,
            "estado": fila.get(mapa["estado"]) if mapa["estado"] else None,
            "actualizada": fila.get(mapa["actualizada"]) if mapa["actualizada"] else None,
            "url": None,
        })
    return historias


# --- Sincronización ----------------------------------------------------------------------------

def sincronizar(raiz: Path, producto: str, sesion=None) -> dict:
    config = leer_config(raiz, producto)
    if config["fuente"] == "ninguna":
        return {"fuente": "ninguna"}
    nuevas_historias = (desde_jira(config, cargar_env(raiz), sesion) if config["fuente"] == "jira"
                        else desde_archivo(raiz, producto, config))
    _, estado = carpetas(raiz, producto)
    archivo = estado / "historias.json"
    guardadas = leer_json(archivo, {})
    hoy = date.today().isoformat()
    resumen = {"fuente": config["fuente"], "nuevas": [], "modificadas": [], "retiradas": [], "reaparecidas": []}
    vistas = set()
    for historia in nuevas_historias:
        historia["huella"] = huella_historia(historia)
        clave = historia["clave"]
        vistas.add(clave)
        previa = guardadas.get(clave)
        if previa is None:
            guardadas[clave] = {**historia, "versiones": [], "en_fuente": True, "retirada": None, "cambio": None}
            resumen["nuevas"].append(clave)
            continue
        if not previa.get("en_fuente", True):
            resumen["reaparecidas"].append(clave)
        if previa["huella"] != historia["huella"]:
            previa["versiones"].append({"fecha": previa.get("cambio") or previa.get("actualizada"), "huella": previa["huella"],
                                        "titulo": previa["titulo"], "criterios": previa["criterios"], "tipo": previa["tipo"]})
            resumen["modificadas"].append(clave)
            historia["cambio"] = hoy
        else:
            historia["cambio"] = previa.get("cambio")
        guardadas[clave] = {**previa, **historia, "en_fuente": True, "retirada": None}
    for clave, historia in guardadas.items():
        if clave not in vistas and historia.get("en_fuente", True):
            historia["en_fuente"] = False
            historia["retirada"] = hoy
            resumen["retiradas"].append(clave)
    escribir_json(archivo, guardadas)
    escribir_json(estado / "ultima_sincronizacion.json", {"fecha": hoy, **resumen})
    escribir_indice(raiz, producto)
    return resumen


def historias_de(raiz: Path, producto: str) -> dict[str, dict]:
    return leer_json(carpetas(raiz, producto)[1] / "historias.json", {})


def analisis_de(raiz: Path, producto: str) -> dict[str, dict]:
    return leer_json(carpetas(raiz, producto)[1] / "analisis.json", {})


def vinculos_de(raiz: Path, producto: str) -> dict[str, dict[str, str]]:
    return leer_json(carpetas(raiz, producto)[1] / "vinculos.json", {})


# --- Candidatas --------------------------------------------------------------------------------

def motivo_candidata(historia: dict) -> str | None:
    tipo = normalizar(historia.get("tipo") or "")
    if tipo in TIPOS_SIEMPRE:
        return f"tipo {historia['tipo']}"
    senales = sorted({m.group(0) for m in PATRON_SENALES.finditer(normalizar(texto_completo(historia)))})
    return f"señales: {', '.join(senales[:6])}" if senales else None


def candidatas(raiz: Path, producto: str, todas: bool = False) -> list[dict]:
    """Historias que conviene analizar: nuevas o modificadas desde su último análisis (o todas con --todas)."""
    analisis = analisis_de(raiz, producto)
    resultado = []
    for clave, historia in sorted(historias_de(raiz, producto).items()):
        if not historia.get("en_fuente", True):
            continue
        motivo = motivo_candidata(historia)
        if not motivo:
            continue
        previo = analisis.get(clave)
        if not todas and previo and previo["huella"] == historia["huella"]:
            continue
        resultado.append({**historia, "motivo": motivo, "analisis_previo": previo})
    return resultado


# --- Clasificación -----------------------------------------------------------------------------

def documentos_de_referencia(raiz: Path, producto: str) -> dict[str, str]:
    from coherencia import leer_arquitectura_vigente, leer_decisiones_equipo, leer_decisiones_producto
    documentos = {clave: d["texto"] for clave, d in leer_arquitectura_vigente(raiz).items()}
    documentos.update({i: d["texto"] for i, d in leer_decisiones_equipo(raiz).items()})
    documentos.update({i: d["texto"] for i, d in leer_decisiones_producto(raiz, producto).items()})
    return documentos


def clasificar(raiz: Path, producto: str, archivo: Path | None = None) -> dict:
    from coherencia import cita_existe
    carpeta, estado = carpetas(raiz, producto)
    archivo = archivo or carpeta / "clasificacion-lote.yaml"
    if not archivo.exists():
        raise ErrorRadiografia(f"No existe el lote {archivo}.")
    try:
        lote = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise ErrorRadiografia(f"El lote no es un YAML válido: {error}") from error
    historias = historias_de(raiz, producto)
    documentos = None
    errores, registros = [], {}
    for indice, item in enumerate(lote.get("historias") or [], start=1):
        clave = str(item.get("clave", ""))
        referencia = f"historias[{indice}] ({clave or 'sin clave'})"
        historia = historias.get(clave)
        clasificacion = item.get("clasificacion")
        if historia is None:
            errores.append(f"{referencia}: la historia no existe (ejecutar sincronizar).")
            continue
        if clasificacion not in CLASIFICACIONES:
            errores.append(f"{referencia}: clasificación '{clasificacion}' inválida; valores válidos: {', '.join(CLASIFICACIONES)}.")
            continue
        if clasificacion != "sin_impacto":
            cita = item.get("cita")
            if not cita or len(str(cita).strip()) < 10 or not cita_existe(str(cita), texto_completo(historia)):
                errores.append(f"{referencia}: falta la cita o no aparece textualmente en la historia.")
                continue
            if not item.get("explicacion"):
                errores.append(f"{referencia}: falta la explicación.")
                continue
        if clasificacion == "candidata" and not item.get("tema"):
            errores.append(f"{referencia}: una candidata necesita un tema para agruparla.")
            continue
        if clasificacion == "choque":
            documentos = documentos if documentos is not None else documentos_de_referencia(raiz, producto)
            documento = item.get("documento")
            if documento not in documentos:
                errores.append(f"{referencia}: el documento '{documento}' no es un ADR o estándar vigente.")
                continue
            if not item.get("cita_documento") or not cita_existe(str(item["cita_documento"]), documentos[documento]):
                errores.append(f"{referencia}: la cita del documento no aparece textualmente en {documento}.")
                continue
        registros[clave] = {
            "huella": historia["huella"], "clasificacion": clasificacion, "tema": item.get("tema"),
            "cita": item.get("cita"), "explicacion": item.get("explicacion"), "documento": item.get("documento"),
            "cita_documento": item.get("cita_documento"), "fecha": date.today().isoformat(),
        }
    if errores:
        raise ErrorRadiografia(f"El lote tiene {len(errores)} error(es); no se registró nada:\n  - " + "\n  - ".join(errores))
    analisis = analisis_de(raiz, producto)
    analisis.update(registros)
    escribir_json(estado / "analisis.json", analisis)
    escribir_indice(raiz, producto)
    return {"registradas": len(registros), "pendientes": len(candidatas(raiz, producto))}


# --- Propuestas, vínculos y atención -----------------------------------------------------------

def propuestas(raiz: Path, producto: str) -> dict[str, list[dict]]:
    """Candidatas analizadas y aún no vinculadas a un ADR, agrupadas por tema."""
    historias, analisis = historias_de(raiz, producto), analisis_de(raiz, producto)
    vinculadas = {clave for vinculo in vinculos_de(raiz, producto).values() for clave in vinculo}
    temas: dict[str, list[dict]] = {}
    for clave, a in analisis.items():
        if a["clasificacion"] == "candidata" and clave not in vinculadas and historias.get(clave, {}).get("en_fuente", True):
            temas.setdefault(a["tema"], []).append({**historias[clave], "cita": a["cita"], "explicacion": a["explicacion"]})
    return dict(sorted(temas.items(), key=lambda x: -len(x[1])))


def vincular(raiz: Path, producto: str, id_adr: str, claves: list[str]) -> None:
    historias = historias_de(raiz, producto)
    vinculos = vinculos_de(raiz, producto)
    vinculos[id_adr] = {clave: historias[clave]["huella"] for clave in claves}
    escribir_json(carpetas(raiz, producto)[1] / "vinculos.json", vinculos)


def atencion(raiz: Path, producto: str) -> dict[str, list[str]]:
    """ADR -> avisos por historias de origen modificadas o retiradas desde que se vincularon."""
    historias = historias_de(raiz, producto)
    avisos: dict[str, list[str]] = {}
    for id_adr, vinculo in vinculos_de(raiz, producto).items():
        for clave, huella in vinculo.items():
            historia = historias.get(clave)
            if historia is None or not historia.get("en_fuente", True):
                avisos.setdefault(id_adr, []).append(f"{clave} retirada de la fuente")
            elif historia["huella"] != huella:
                avisos.setdefault(id_adr, []).append(f"{clave} modificada")
    return avisos


def confirmar(raiz: Path, producto: str, id_adr: str) -> None:
    """El usuario revisó los cambios de las historias de un ADR y el ADR sigue vigente."""
    vinculos = vinculos_de(raiz, producto)
    if id_adr not in vinculos:
        raise ErrorRadiografia(f"{id_adr} no tiene historias de origen.")
    historias = historias_de(raiz, producto)
    vinculos[id_adr] = {c: historias[c]["huella"] for c in vinculos[id_adr] if c in historias and historias[c].get("en_fuente", True)}
    escribir_json(carpetas(raiz, producto)[1] / "vinculos.json", vinculos)
    escribir_indice(raiz, producto)


# --- Índice ------------------------------------------------------------------------------------

def escribir_indice(raiz: Path, producto: str) -> Path | None:
    historias = historias_de(raiz, producto)
    if not historias:
        return None
    carpeta, estado = carpetas(raiz, producto)
    analisis, sincronizacion = analisis_de(raiz, producto), leer_json(estado / "ultima_sincronizacion.json", {})
    activas = [h for h in historias.values() if h.get("en_fuente", True)]
    por_tipo: dict[str, int] = {}
    for h in activas:
        por_tipo[h.get("tipo") or "sin tipo"] = por_tipo.get(h.get("tipo") or "sin tipo", 0) + 1
    pendientes = candidatas(raiz, producto)
    lineas = [f"# Historias de {producto}", "", "> Archivo generado por `herramientas/jira.py`. No se edita a mano.", "",
              f"Última sincronización: {sincronizacion.get('fecha', '—')} · historias: {len(activas)} · "
              f"candidatas por analizar: {len(pendientes)}", "",
              "| Tipo | Historias |", "|---|---|"] + [f"| {t} | {n} |" for t, n in sorted(por_tipo.items())]
    modificadas = [historias[c] for c in sincronizacion.get("modificadas", []) if c in historias]
    lineas += ["", "## Cambios desde la sincronización anterior", ""]
    if modificadas or sincronizacion.get("nuevas") or sincronizacion.get("retiradas"):
        if sincronizacion.get("nuevas"):
            lineas.append(f"- Nuevas: {', '.join(sincronizacion['nuevas'])}")
        if sincronizacion.get("retiradas"):
            lineas.append(f"- Retiradas de la fuente: {', '.join(sincronizacion['retiradas'])}")
        for h in modificadas:
            anterior = h["versiones"][-1] if h["versiones"] else {}
            lineas += ["", f"### {h['clave']}: {h['titulo']}", "",
                       f"- Criterios antes: {(anterior.get('criterios') or 'NO DETERMINADO').replace(chr(10), ' / ')}",
                       f"- Criterios ahora: {(h.get('criterios') or 'NO DETERMINADO').replace(chr(10), ' / ')}"]
    else:
        lineas.append("Sin cambios.")
    choques = [(c, a) for c, a in analisis.items() if a["clasificacion"] == "choque"]
    if choques:
        lineas += ["", "## Historias que chocan con lo decidido (conversar antes de implementar)", ""]
        lineas += [f"- **{c}** ({historias.get(c, {}).get('titulo', '')}) choca con `{a['documento']}`: {a['explicacion']}" for c, a in choques]
    temas = propuestas(raiz, producto)
    if temas:
        lineas += ["", "## Candidatas a ADR (sin ADR todavía)", ""]
        for tema, lista in temas.items():
            lineas.append(f"- **{tema}**: {', '.join(h['clave'] for h in lista)}")
    vinculos, avisos = vinculos_de(raiz, producto), atencion(raiz, producto)
    if vinculos:
        lineas += ["", "## ADR con historias de origen", "", "| ADR | Historias | Atención |", "|---|---|---|"]
        lineas += [f"| {a} | {', '.join(v)} | {'; '.join(avisos.get(a, [])) or '—'} |" for a, v in sorted(vinculos.items())]
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / "INDICE.md"
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return archivo



# ===== Creación de Tareas, Spikes, Errores y Hotfix ===========================================

TIPOS = ("tarea", "spike", "error", "hotfix")
COMBINACIONES = {"tarea": ("Deuda Técnica", "Deuda Operativa"), "error": ("Bau/Incidentes",),
                 "hotfix": ("Bau/Incidentes",), "spike": ("Spike",)}
SECCIONES = {
    "tarea": ("criterios de aceptacion", "contexto", "decisiones que aplican", "fuera de alcance", "trazabilidad"),
    "error": ("criterios de aceptacion", "comportamiento actual", "comportamiento esperado", "como reproducirlo",
              "impacto", "causa", "trazabilidad"),
    "hotfix": ("criterios de aceptacion", "comportamiento actual", "impacto", "correccion", "trazabilidad"),
    "spike": ("criterios de aceptacion", "pregunta", "contexto", "opciones a evaluar", "criterios de decision",
              "restricciones", "duracion maxima", "entregable", "trazabilidad"),
}
CRITERIOS_FIJOS = {   # por tipo de incidencia o, en una Tarea, por su campo Tipo
    "Deuda Técnica": ("ya no reporta",),
    "Deuda Operativa": ("deja de ser necesaria",),
    "error": ("reproduce el error", "causa queda documentada", "evita que el error se repita"),
    "hotfix": ("correccion esta en produccion", "error de seguimiento"),
    "spike": ("pregunta tiene respuesta documentada", "adr de producto en estado propuesto", "duracion maxima"),
}
DURACION_MAXIMA_SPIKE = 2
NOMBRES = {"tarea": "Una Tarea", "spike": "Un Spike", "error": "Un Error", "hotfix": "Un Hotfix"}
PATRON_MEDIBLE = re.compile(r"\d|^\s*[-*]?\s*(dado|cuando|entonces)\b|\b(no reporta|deja de|rechaza|responde|registra|devuelve)\b")
VERBO_INFINITIVO = re.compile(r"^[a-záéíóúñ]+(ar|er|ir)\b", re.IGNORECASE)


# --- Configuración de Jira ---------------------------------------------------------------------

def config_jira(raiz: Path) -> dict:
    jira = cargar_config(raiz).get("jira") or {}
    return {
        "equipos": jira.get("equipos", "Back"),
        "campo_equipos": jira.get("campo_equipos", "Equipos"),
        "campo_tipo": jira.get("campo_tipo", "Tipo"),
        "tipos_incidencia": {"tarea": "Tarea", "spike": "Spike", "error": "Error", "hotfix": "Hotfix",
                             **(jira.get("tipos_incidencia") or {})},
    }


def destino_jira(raiz: Path, producto: str) -> dict:
    """Proyecto y etiqueta donde se crean las incidencias: los mismos de donde se leen las historias."""
    config = leer_config(raiz, producto)
    proyecto = config.get("proyecto")
    if not proyecto and config.get("jql"):
        if coincidencia := re.search(r"project\s*=\s*\"?([A-Z][A-Z0-9_]+)\"?", config["jql"], re.IGNORECASE):
            proyecto = coincidencia.group(1)
    if not proyecto:
        raise ErrorRadiografia(f"No se pudo determinar el proyecto de Jira de '{producto}': agregar historias.proyecto "
                               "(clave del proyecto) o una JQL con 'project = CLAVE'.")
    etiqueta = config.get("etiqueta")
    if not etiqueta and config.get("jql"):
        if coincidencia := re.search(r"labels\s*=\s*\"?([\w-]+)\"?", config["jql"], re.IGNORECASE):
            etiqueta = coincidencia.group(1)
    return {"proyecto": proyecto, "etiqueta": etiqueta}


# --- Borradores --------------------------------------------------------------------------------

def carpeta_borradores(raiz: Path, producto: str) -> Path:
    if not (raiz / "productos" / producto / "producto.yaml").exists():
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    return raiz / "productos" / producto / "historias" / "borradores"


def leer_borrador(archivo: Path) -> tuple[dict, str]:
    texto = archivo.read_text(encoding="utf-8")
    partes = re.match(r"^---\n(.*?)\n---\n(.*)$", texto, re.DOTALL)
    if not partes:
        raise ErrorRadiografia(f"{archivo.name} no tiene el encabezado YAML (entre líneas ---).")
    try:
        datos = yaml.safe_load(partes.group(1)) or {}
    except yaml.YAMLError as error:
        raise ErrorRadiografia(f"El encabezado de {archivo.name} no es un YAML válido: {error}") from error
    return datos, partes.group(2)


def escribir_borrador(archivo: Path, datos: dict, cuerpo: str) -> None:
    encabezado = yaml.safe_dump(datos, allow_unicode=True, sort_keys=False).strip()
    archivo.write_text(f"---\n{encabezado}\n---\n{cuerpo}", encoding="utf-8")


def resolver_borrador(raiz: Path, producto: str, nombre: str) -> Path:
    carpeta = carpeta_borradores(raiz, producto)
    candidatos = [carpeta / nombre, carpeta / f"{nombre}.md", Path(nombre)]
    candidatos += sorted(carpeta.glob(f"{nombre}-*.md")) if carpeta.exists() else []
    for candidato in candidatos:
        if candidato.is_file() and not candidato.name.endswith("-contexto.md"):
            return candidato
    raise ErrorRadiografia(f"No existe el borrador '{nombre}' en {carpeta.relative_to(raiz)}.")


# --- Paquete de contexto -----------------------------------------------------------------------

def palabras_clave(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z0-9áéíóúñ]{4,}", normalizar(texto))}


def contexto(raiz: Path, producto: str, tipo: str, categoria: str, titulo: str, desde: list[str],
             repos: list[str], tema: str | None) -> str:
    registro = registro_hallazgos.cargar(raiz, producto)
    por_id = {h["id"]: h for h in registro["hallazgos"].values()}
    origen = [por_id[i] for i in desde]
    repos = sorted(set(repos) | {h["repo"] for h in origen})
    claves = palabras_clave(" ".join([titulo, tema or ""] + [h["titulo"] for h in origen]))
    fuentes_origen = {h["fuente"] for h in origen} | {h["criterio"] for h in origen if h.get("criterio")}

    lineas = [f"# Contexto para: {titulo}", "",
              f"- Tipo de incidencia: {tipo} · Tipo: {categoria} · Producto: {producto}",
              f"- Repositorios: {', '.join(repos) or 'NO DETERMINADO'}",
              "- Definición de terminado: ADR-EQ-008 · Estructura obligatoria: ADR-EQ-009 · Lenguaje: equipo/lenguaje.yaml",
              "", "## Hallazgos de origen", ""]
    for h in origen:
        evidencia = ", ".join(f"`{e['archivo']}:{e['linea']}`" if e.get("linea") else f"`{e['archivo']}`" for e in h["evidencia"][:5])
        lineas.append(f"- **{h['id']}** · {h['repo']} · {h['criterio'] or h['fuente']} · {h['severidad']}: {h['titulo']}. "
                      f"{h.get('detalle', '')} Evidencia: {evidencia or '—'}"
                      + (f" Triaje: {h['triaje']['decision']} ({h['triaje'].get('motivo') or 'sin motivo'})" if h.get("triaje") else ""))
    if not origen:
        lineas.append("Ninguno indicado.")

    relacionados = [h for h in registro["hallazgos"].values()
                    if h["estado"] == "abierto" and h["id"] not in desde and (not repos or h["repo"] in repos)
                    and ((h.get("criterio") or h["fuente"]) in fuentes_origen or len(claves & palabras_clave(h["titulo"])) >= 2)]
    lineas += ["", "## Otros hallazgos abiertos relacionados", ""]
    lineas += [f"- {h['id']} · {h['repo']} · {h['criterio'] or h['fuente']} · {h['severidad']}: {h['titulo']}" for h in relacionados[:15]] or ["Ninguno."]

    lineas += ["", "## AS IS de los repositorios", ""]
    for repo in repos:
        ficha = raiz / "productos" / producto / "as-is" / f"{repo}.md"
        if not ficha.exists():
            lineas.append(f"- {repo}: sin ficha AS IS (ejecutar /revisar).")
            continue
        _, contenido = secciones(ficha.read_text(encoding="utf-8").splitlines())
        for seccion in ("riesgos y deuda principales", "integraciones", "arquitectura real"):
            texto = "\n".join(l for l in contenido.get(seccion, []) if l.strip()).strip()
            if texto:
                lineas += [f"### {repo}: {seccion}", "", texto[:2500], ""]

    lineas += ["## Decisiones que pueden aplicar", "",
               "Incluir en la historia solo las que el trabajo debe respetar, con su regla rápida.", ""]
    documentos = [(c, d) for c, d in leer_arquitectura_vigente(raiz).items()]
    documentos += [(i, d) for i, d in leer_decisiones_equipo(raiz).items() if d["evaluado"]]
    documentos += [(i, d) for i, d in leer_decisiones_producto(raiz, producto).items() if d["evaluado"]]
    for clave, documento in documentos:
        relacionado = clave in fuentes_origen or any(c.startswith(f"EQ-{clave[7:10]}") for c in fuentes_origen if clave.startswith("ADR-EQ-")) \
            or len(claves & palabras_clave(f"{documento['titulo']} {documento.get('regla_rapida') or ''}")) >= 2
        if relacionado:
            lineas.append(f"- `{clave}` {documento['titulo']}: {documento.get('regla_rapida') or 'sin regla rápida'}")

    fichas = [f for repo in repos for f in terceros.para_repo(raiz, producto, repo)] if repos else []
    if fichas:
        lineas += ["", "## Terceros involucrados", ""]
        for f in {f["id"]: f for f in fichas}.values():
            sla = f.get("sla") or {}
            lineas.append(f"- `{f['id']}` {f.get('nombre')}: {f.get('protocolo')}, p95 {sla.get('p95_ms') or '—'} ms, "
                          f"política ante falla {f.get('politica_ante_falla')} ({f.get('justificacion')})")

    if tema:
        coincidencias = terceros.buscar(raiz, producto, tema, limite=10)
        lineas += ["", f"## Documentación de terceros sobre «{tema}»", ""]
        lineas += [f"- `{c['archivo']}`" + (f" (página {c['pagina']})" if c["pagina"] else "") + f":{c['linea']}: {c['texto']}"
                   for c in coincidencias] or ["Sin coincidencias."]

    similares = [h for h in historias_de(raiz, producto).values()
                 if h.get("en_fuente", True) and len(claves & palabras_clave(h["titulo"])) >= 2]
    lineas += ["", "## Historias de Jira parecidas (revisar si ya existe la misma)", ""]
    lineas += [f"- {h['clave']} · {h.get('tipo') or 'sin tipo'} · {h.get('estado') or '—'}: {h['titulo']}" for h in similares[:10]] or ["Ninguna."]

    lineas += ["", "## Sonar de los repositorios", ""]
    for repo in repos:
        estado = registro.get("repos", {}).get(repo, {}).get("automatica")
        crudo = raiz / "productos" / producto / "revisiones" / estado["id"] / "crudo" / f"{repo}-sonar.json" if estado else None
        if crudo and crudo.exists():
            datos = json.loads(crudo.read_text(encoding="utf-8"))
            metricas = ", ".join(f"{m} {v}" for m, v in sorted(datos.get("metricas", {}).items()))
            lineas.append(f"- {repo}: quality gate {datos['quality_gate']['estado']}; {metricas}")
        else:
            lineas.append(f"- {repo}: NO DETERMINADO (sin datos de Sonar en la última revisión)")
    return "\n".join(lineas) + "\n"


def nueva(raiz: Path, producto: str, tipo: str, categoria: str | None, titulo: str, desde: list[str],
          repos: list[str], tema: str | None, hotfix: str | None = None) -> tuple[Path, Path]:
    if tipo not in TIPOS:
        raise ErrorRadiografia(f"Tipo de incidencia '{tipo}' inválido; valores válidos: {', '.join(TIPOS)}.")
    if hotfix and tipo != "error":
        raise ErrorRadiografia("--hotfix solo se usa al crear el Error de seguimiento de un Hotfix.")
    categoria = categoria or COMBINACIONES[tipo][0]
    if categoria not in COMBINACIONES[tipo]:
        raise ErrorRadiografia(f"{NOMBRES[tipo]} solo admite Tipo {', '.join(COMBINACIONES[tipo])}.")
    datos_producto = productos.leer_productos(raiz).get(producto)
    if datos_producto is None:
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    repos_producto = {str(r["id"]) for r in productos.repos_de(datos_producto)}
    desconocidos = [r for r in repos if r not in repos_producto]
    if desconocidos:
        raise ErrorRadiografia(f"Repositorios que no existen en el producto: {', '.join(desconocidos)}.")
    existentes = {h["id"] for h in registro_hallazgos.cargar(raiz, producto)["hallazgos"].values()}
    inexistentes = [h for h in desde if h not in existentes]
    if inexistentes:
        raise ErrorRadiografia(f"Hallazgos que no existen: {', '.join(inexistentes)}.")

    carpeta = carpeta_borradores(raiz, producto)
    carpeta.mkdir(parents=True, exist_ok=True)
    numeros = [int(m.group(1)) for a in carpeta.glob("*.md") if (m := re.match(r"^(\d{3})-", a.name))]
    base = f"{max(numeros, default=0) + 1:03d}-{slug(titulo, 50)}"
    datos, cuerpo = leer_borrador(raiz / "equipo" / "plantillas" / f"{tipo}.md")
    registro = registro_hallazgos.cargar(raiz, producto)
    datos.update({"tipo": categoria, "equipos": config_jira(raiz)["equipos"], "producto": producto,
                  "repos": sorted(set(repos) | {h["repo"] for h in registro["hallazgos"].values() if h["id"] in desde}),
                  "hallazgos": desde, "estado": "borrador", "jira": None})
    if hotfix:
        datos["historias_relacionadas"] = [hotfix]
    cuerpo = re.sub(r"^# .*$", f"# {titulo}", cuerpo, count=1, flags=re.MULTILINE)
    if hotfix:
        cuerpo = cuerpo.replace("si es el seguimiento de un Hotfix, su clave>", f"seguimiento del Hotfix {hotfix}>", 1)
    if tipo == "tarea":
        fijo = (f"- La revisión ya no reporta los hallazgos de origen ({', '.join(desde)})." if categoria == "Deuda Técnica" and desde
                else "- La revisión ya no reporta los hallazgos de origen." if categoria == "Deuda Técnica"
                else "- La tarea manual deja de ser necesaria; se verifica <cómo se comprueba>.")
        cuerpo = re.sub(r"^- <Deuda Técnica:.*$", fijo, cuerpo, count=1, flags=re.MULTILINE)
    archivo = carpeta / f"{base}.md"
    escribir_borrador(archivo, datos, cuerpo)
    archivo_contexto = carpeta / f"{base}-contexto.md"
    archivo_contexto.write_text(contexto(raiz, producto, tipo, categoria, titulo, desde, repos, tema), encoding="utf-8")
    return archivo, archivo_contexto


# --- Validación --------------------------------------------------------------------------------

def campo_encabezado(cuerpo: str, nombre: str) -> str | None:
    coincidencia = re.search(rf"^\*\*{nombre}\*\*\s*(.+)$", cuerpo, re.MULTILINE)
    return coincidencia.group(1).strip() if coincidencia else None


def validar(raiz: Path, producto: str, archivo: Path) -> list[str]:
    """Errores según ADR-EQ-009 y la regla de lenguaje. Lista vacía si el borrador está listo."""
    datos, cuerpo = leer_borrador(archivo)
    errores = []
    tipo, categoria = datos.get("tipo_incidencia"), datos.get("tipo")
    if tipo not in TIPOS:
        return [f"tipo_incidencia '{tipo}' inválido; valores válidos: {', '.join(TIPOS)}"]
    if categoria not in COMBINACIONES[tipo]:
        errores.append(f"{NOMBRES[tipo].lower()} solo admite Tipo {', '.join(COMBINACIONES[tipo])} (EQ-009.1)")
    if datos.get("equipos") != config_jira(raiz)["equipos"]:
        errores.append(f"Equipos debe ser {config_jira(raiz)['equipos']} (EQ-009.1)")
    if datos.get("producto") != producto:
        errores.append(f"el borrador es del producto '{datos.get('producto')}'")

    titulo = re.search(r"^# (.+)$", cuerpo, re.MULTILINE)
    if not titulo:
        errores.append("falta el título (línea que empieza con '# ')")
    elif tipo in ("tarea", "spike") and not VERBO_INFINITIVO.match(titulo.group(1).strip()):
        errores.append("el título de una Tarea o un Spike empieza con un verbo en infinitivo (por ejemplo «Agregar…», «Evaluar…»)")

    como, quiero, para = (campo_encabezado(cuerpo, n) for n in ("Como", "Quiero", "Para"))
    if not (como and quiero and para):
        errores.append("faltan Como, Quiero o Para (EQ-009.2)")
    else:
        if re.match(r"^(el |un )?sistema\b", normalizar(como)):
            errores.append("«Como» debe ser un rol real (desarrollador, operador, analista…), no «sistema» (EQ-009.2)")
        palabras_quiero, palabras_para = palabras_clave(quiero), palabras_clave(para)
        if palabras_para and len(palabras_para & palabras_quiero) / len(palabras_para) > 0.6:
            errores.append("el «Para» repite el «Quiero»: debe expresar el valor (EQ-009.2)")

    _, contenido = secciones(cuerpo.splitlines())
    for seccion in SECCIONES[tipo]:
        if not "\n".join(contenido.get(seccion, [])).strip():
            errores.append(f"falta la sección «{seccion}» o está vacía (EQ-009.4)")
    criterios = [l.strip() for l in contenido.get("criterios de aceptacion", []) if l.strip().startswith(("-", "*")) or
                 re.match(r"^\s*(dado|cuando|entonces|y)\b", normalizar(l))]
    fijos = CRITERIOS_FIJOS.get(categoria if tipo == "tarea" else tipo, ())
    for fijo in fijos:
        if not any(fijo in normalizar(c) for c in criterios):
            errores.append(f"falta el criterio fijo de {categoria if tipo == 'tarea' else NOMBRES[tipo][3:]}: «…{fijo}…» (ADR-EQ-009)")
    propios = [c for c in criterios if not any(f in normalizar(c) for f in fijos)]
    if tipo != "spike" and not any(PATRON_MEDIBLE.search(normalizar(c)) for c in propios):
        errores.append("se necesita al menos un criterio de aceptación propio y medible (EQ-009.3)")

    if tipo == "spike":
        pregunta = "\n".join(contenido.get("pregunta", []))
        if pregunta.count("?") > 1:
            errores.append("un Spike responde una sola pregunta (EQ-009.5)")
        duracion = "\n".join(contenido.get("duracion maxima", []))
        dias = re.search(r"(\d+)\s*d[ií]as?", duracion)
        if not dias:
            errores.append("la duración máxima se indica en días (EQ-009.5)")
        elif int(dias.group(1)) > DURACION_MAXIMA_SPIKE and "justific" not in normalizar(duracion):
            errores.append(f"la duración máxima de un Spike es {DURACION_MAXIMA_SPIKE} días, salvo justificación (EQ-009.5)")
        if "adr" not in normalizar("\n".join(contenido.get("entregable", []))):
            errores.append("el entregable de un Spike incluye un ADR de producto en estado Propuesto (EQ-009.5)")

    if re.search(r"<[a-záéíóúñ][^>\n]{2,}>", cuerpo, re.IGNORECASE):
        errores.append("quedan textos de la plantilla sin completar (<…>)")
    existentes = {h["id"] for h in registro_hallazgos.cargar(raiz, producto)["hallazgos"].values()}
    inexistentes = [h for h in datos.get("hallazgos") or [] if h not in existentes]
    if inexistentes:
        errores.append(f"hallazgos que no existen: {', '.join(inexistentes)}")
    errores += [f"lenguaje: línea {a['linea']}: «{a['texto']}» ({a['regla']}); {a['sugerencia']}"
                for a in lenguaje.revisar(archivo.read_text(encoding="utf-8"), lenguaje.cargar_reglas(raiz))]
    return errores


def listar(raiz: Path, producto: str) -> list[dict]:
    carpeta = carpeta_borradores(raiz, producto)
    filas = []
    for archivo in sorted(carpeta.glob("*.md")) if carpeta.exists() else []:
        if archivo.name.endswith("-contexto.md"):
            continue
        datos, cuerpo = leer_borrador(archivo)
        titulo = re.search(r"^# (.+)$", cuerpo, re.MULTILINE)
        filas.append({"archivo": archivo.name, "titulo": titulo.group(1) if titulo else archivo.stem,
                      "tipo_incidencia": datos.get("tipo_incidencia"), "tipo": datos.get("tipo"),
                      "estado": datos.get("estado"), "jira": datos.get("jira")})
    return filas


def terminado(raiz: Path, producto: str, hoy: date | None = None) -> list[dict]:
    """Criterios de ADR-EQ-008 que se verifican solos sobre lo ya creado en Jira.

    - EQ-008.5 (Tarea con hallazgos de origen): cumple cuando todos sus hallazgos están corregidos.
    - EQ-008.8 (Spike): cumple cuando un ADR de producto en Propuesto o Aprobado lo cita en "Historias de
      origen". Se informa como pendiente pasada la duración máxima del Spike.
    - EQ-008.9 (Hotfix): cumple cuando hay un Error de seguimiento creado en Jira que lo cita.
    """
    import hallazgos as registro_hallazgos
    from coherencia import leer_decisiones_producto

    hoy = hoy or date.today()
    por_id = {h["id"]: h for h in registro_hallazgos.cargar(raiz, producto)["hallazgos"].values()}
    adrs = leer_decisiones_producto(raiz, producto)
    resultado = []
    carpeta = carpeta_borradores(raiz, producto)
    creados = []
    for archivo in sorted(carpeta.glob("*.md")) if carpeta.exists() else []:
        if not archivo.name.endswith("-contexto.md"):
            datos, _ = leer_borrador(archivo)
            if datos.get("estado") == "creada" and datos.get("jira"):
                creados.append(datos)
    seguimientos = {str(c) for d in creados if d.get("tipo_incidencia") == "error" for c in d.get("historias_relacionadas") or []}
    for datos in creados:
        clave = str(datos["jira"])
        if datos.get("tipo_incidencia") == "hotfix":
            resultado.append({"clave": clave, "criterio": "EQ-008.9", "cumple": clave in seguimientos})
            continue
        if datos.get("tipo_incidencia") == "tarea" and datos.get("hallazgos"):
            abiertos = [i for i in datos["hallazgos"] if por_id.get(i, {}).get("estado") == "abierto"]
            resultado.append({"clave": clave, "criterio": "EQ-008.5", "cumple": not abiertos, "pendientes": abiertos})
        elif datos.get("tipo_incidencia") == "spike":
            con_adr = [i for i, d in adrs.items() if clave in (d["campos"].get("historias de origen") or "")
                       and normalizar(d["estado"]) in ("propuesto", "aprobado")]
            creada = date.fromisoformat(str(datos.get("creada") or hoy.isoformat()))
            resultado.append({"clave": clave, "criterio": "EQ-008.8", "cumple": bool(con_adr), "adr": con_adr,
                              "vencido": (hoy - creada).days > DURACION_MAXIMA_SPIKE})
    return resultado


# --- Jira --------------------------------------------------------------------------------------

def _texto_con_marcas(texto: str) -> list[dict]:
    """Texto ADF con negrita (**x**), código (`x`) y enlaces ([t](u))."""
    nodos = []
    for parte in re.split(r"(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))", texto):
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**"):
            nodos.append({"type": "text", "text": parte[2:-2], "marks": [{"type": "strong"}]})
        elif parte.startswith("`") and parte.endswith("`"):
            nodos.append({"type": "text", "text": parte[1:-1], "marks": [{"type": "code"}]})
        elif enlace := re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", parte):
            nodos.append({"type": "text", "text": enlace.group(1), "marks": [{"type": "link", "attrs": {"href": enlace.group(2)}}]})
        else:
            nodos.append({"type": "text", "text": parte})
    return nodos


def markdown_a_adf(markdown: str) -> dict:
    """Convierte el markdown de un borrador al formato de documento de Atlassian (ADF)."""
    contenido, lista = [], None
    for linea in markdown.split("\n"):
        if not linea.strip():
            lista = None
            continue
        if titulo := re.match(r"^(#{1,6})\s+(.*)$", linea):
            lista = None
            contenido.append({"type": "heading", "attrs": {"level": min(len(titulo.group(1)) + 1, 6)},
                              "content": _texto_con_marcas(titulo.group(2))})
        elif item := re.match(r"^\s*(?:[-*]|(\d+)\.)\s+(.*)$", linea):
            tipo_lista = "orderedList" if item.group(1) else "bulletList"
            if lista is None or lista["type"] != tipo_lista:
                lista = {"type": tipo_lista, "content": []}
                contenido.append(lista)
            lista["content"].append({"type": "listItem", "content": [{"type": "paragraph", "content": _texto_con_marcas(item.group(2))}]})
        else:
            lista = None
            contenido.append({"type": "paragraph", "content": _texto_con_marcas(linea.strip())})
    return {"type": "doc", "version": 1, "content": contenido}


def valor_campo(esquema: dict, valor: str):
    return [{"value": valor}] if (esquema or {}).get("type") == "array" else {"value": valor}


def armar_solicitud(raiz: Path, producto: str, archivo: Path, campos_jira: list[dict]) -> dict:
    datos, cuerpo = leer_borrador(archivo)
    config, destino = config_jira(raiz), destino_jira(raiz, producto)
    por_nombre = {normalizar(c.get("name", "")): c for c in campos_jira}
    faltantes = [n for n in (config["campo_tipo"], config["campo_equipos"]) if normalizar(n) not in por_nombre]
    if faltantes:
        raise ErrorRadiografia(f"No existen en Jira los campos: {', '.join(faltantes)}.")
    campo_tipo, campo_equipos = por_nombre[normalizar(config["campo_tipo"])], por_nombre[normalizar(config["campo_equipos"])]
    titulo = re.search(r"^# (.+)$", cuerpo, re.MULTILINE).group(1).strip()
    descripcion = re.sub(r"^# .+\n+", "", cuerpo, count=1, flags=re.MULTILINE)
    campos = {
        "project": {"key": destino["proyecto"]},
        "issuetype": {"name": config["tipos_incidencia"][datos["tipo_incidencia"]]},
        "summary": titulo,
        "description": markdown_a_adf(descripcion),
        campo_tipo["id"]: valor_campo(campo_tipo.get("schema"), datos["tipo"]),
        campo_equipos["id"]: valor_campo(campo_equipos.get("schema"), datos["equipos"]),
    }
    if destino["etiqueta"]:
        campos["labels"] = [destino["etiqueta"]]
    return {"fields": campos}


def crear(raiz: Path, producto: str, archivo: Path, confirmar: bool, sesion=None) -> dict:
    datos, _ = leer_borrador(archivo)
    if datos.get("estado") == "creada":
        raise ErrorRadiografia(f"El borrador ya se creó en Jira como {datos.get('jira')}.")
    errores = validar(raiz, producto, archivo)
    if errores:
        raise ErrorRadiografia(f"El borrador tiene {len(errores)} error(es); no se puede crear:\n  - " + "\n  - ".join(errores))
    env = cargar_env(raiz)
    faltantes = [v for v in ("JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN") if not env.get(v)]
    if faltantes:
        raise ErrorRadiografia(f"Faltan variables de Jira en .env: {', '.join(faltantes)}.")
    cliente = ClienteJira(env["JIRA_URL"], env["JIRA_EMAIL"], env["JIRA_TOKEN"], sesion)
    campos_jira = cliente._respuesta(cliente.sesion.get(f"{cliente.url}/rest/api/3/field", timeout=30))
    solicitud = armar_solicitud(raiz, producto, archivo, campos_jira)
    vista_previa = archivo.with_name(archivo.stem + "-jira.json")
    vista_previa.write_text(json.dumps(solicitud, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not confirmar:
        return {"creada": False, "solicitud": solicitud, "vista_previa": vista_previa}
    respuesta = cliente._respuesta(cliente.sesion.post(f"{cliente.url}/rest/api/3/issue", json=solicitud, timeout=60))
    clave = respuesta["key"]
    datos_actuales, cuerpo = leer_borrador(archivo)
    datos_actuales.update({"estado": "creada", "jira": clave, "creada": date.today().isoformat()})
    escribir_borrador(archivo, datos_actuales, cuerpo)
    if datos_actuales.get("hallazgos"):
        registro = registro_hallazgos.cargar(raiz, producto)
        for h in registro["hallazgos"].values():
            if h["id"] in datos_actuales["hallazgos"]:
                h["historia_jira"] = clave
        registro_hallazgos.guardar(raiz, producto, registro)
    return {"creada": True, "clave": clave, "url": f"{cliente.url}/browse/{clave}", "solicitud": solicitud}


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None, sesion=None) -> int:
    parser = argparse.ArgumentParser(description="Historias de Jira: lectura y creación de Tareas, Spikes, Errores y Hotfix.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("sincronizar")
    p.add_argument("producto", nargs="?")
    p = sub.add_parser("candidatas")
    p.add_argument("producto")
    p.add_argument("--todas", action="store_true")
    p = sub.add_parser("clasificar")
    p.add_argument("producto")
    p.add_argument("--archivo", type=Path)
    p = sub.add_parser("propuestas")
    p.add_argument("producto")
    p = sub.add_parser("confirmar")
    p.add_argument("producto")
    p.add_argument("--adr", required=True)
    p = sub.add_parser("nueva")
    p.add_argument("producto")
    p.add_argument("--tipo", required=True, choices=TIPOS)
    p.add_argument("--categoria")
    p.add_argument("--titulo", required=True)
    p.add_argument("--desde", default="")
    p.add_argument("--repos", default="")
    p.add_argument("--tema")
    p.add_argument("--hotfix", help="clave del Hotfix del que este Error es el seguimiento")
    p = sub.add_parser("validar")
    p.add_argument("producto")
    p.add_argument("borrador")
    p = sub.add_parser("listar")
    p.add_argument("producto")
    p = sub.add_parser("crear")
    p.add_argument("producto")
    p.add_argument("borrador")
    p.add_argument("--confirmar", action="store_true", help="crea la incidencia en Jira; sin esto solo muestra la vista previa")
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    if o.accion in ("sincronizar", "candidatas", "clasificar", "propuestas", "confirmar"):
        return _main_lectura(o, raiz, sesion)
    return _main_creacion(o, raiz, sesion)


def _main_lectura(o, raiz: Path, sesion) -> int:
    codigo = 0
    try:
        if o.accion == "sincronizar":
            nombres = [o.producto] if o.producto else sorted(a.parent.name for a in (raiz / "productos").glob("*/producto.yaml"))
            for producto in nombres:
                try:
                    r = sincronizar(raiz, producto, sesion)
                except ErrorRadiografia as error:
                    print(f"[{producto}] ERROR: {error}")
                    codigo = 1
                    continue
                if r["fuente"] == "ninguna":
                    continue
                print(f"[{producto}] historias ({r['fuente']}): nuevas {len(r['nuevas'])}, modificadas {len(r['modificadas'])}, "
                      f"retiradas {len(r['retiradas'])}. Candidatas por analizar: {len(candidatas(raiz, producto))}.")
                avisos = atencion(raiz, producto)
                for id_adr, lista in avisos.items():
                    print(f"  Atención {id_adr}: {'; '.join(lista)}")
        elif o.accion == "candidatas":
            lista = candidatas(raiz, o.producto, o.todas)
            if not lista:
                print("No hay historias candidatas por analizar.")
            for h in lista:
                print(f"\n## {h['clave']} · {h.get('tipo') or 'sin tipo'} · {h.get('estado') or '—'} · {h['motivo']}")
                print(f"Título: {h['titulo']}")
                if h.get("analisis_previo"):
                    print(f"Análisis anterior: {h['analisis_previo']['clasificacion']} (la historia cambió desde entonces)")
                print("Criterios de aceptación:" if h.get("criterios") else "Criterios de aceptación: NO DETERMINADO. Descripción:")
                print((h.get("criterios") or h.get("descripcion") or "—")[:1200])
        elif o.accion == "clasificar":
            r = clasificar(raiz, o.producto, o.archivo)
            print(f"Clasificadas: {r['registradas']}. Candidatas aún por analizar: {r['pendientes']}.")
        elif o.accion == "propuestas":
            temas = propuestas(raiz, o.producto)
            if not temas:
                print("No hay candidatas pendientes de convertirse en ADR.")
            for tema, lista in temas.items():
                print(f"\n## {tema} ({len(lista)} historia(s))")
                for h in lista:
                    print(f"- {h['clave']} · {h.get('tipo') or 'sin tipo'}: {h['titulo']} | «{h['cita']}» | {h['explicacion']}")
        elif o.accion == "confirmar":
            confirmar(raiz, o.producto, o.adr)
            print(f"{o.adr}: cambios de sus historias revisados; el ADR sigue vigente.")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return codigo


def _main_creacion(o, raiz: Path, sesion) -> int:
    separar = lambda texto: [v.strip() for v in texto.split(",") if v.strip()]  # noqa: E731
    try:
        if o.accion == "nueva":
            borrador, archivo_contexto = nueva(raiz, o.producto, o.tipo, o.categoria, o.titulo, separar(o.desde),
                                               separar(o.repos), o.tema, o.hotfix)
            print(f"Borrador: {borrador.relative_to(raiz)}\nContexto: {archivo_contexto.relative_to(raiz)}")
        elif o.accion == "validar":
            errores = validar(raiz, o.producto, resolver_borrador(raiz, o.producto, o.borrador))
            if not errores:
                print("El borrador cumple ADR-EQ-009 y la regla de lenguaje.")
            for error in errores:
                print(f"  ERROR: {error}")
            return 1 if errores else 0
        elif o.accion == "listar":
            filas = listar(raiz, o.producto)
            if not filas:
                print("No hay borradores.")
            for f in filas:
                print(f"  {f['archivo']} · {f['tipo_incidencia']} · {f['tipo']} · {f['estado']}"
                      + (f" · {f['jira']}" if f["jira"] else "") + f" · {f['titulo']}")
        elif o.accion == "crear":
            r = crear(raiz, o.producto, resolver_borrador(raiz, o.producto, o.borrador), o.confirmar, sesion)
            campos = r["solicitud"]["fields"]
            print(f"Proyecto: {campos['project']['key']} · Tipo de incidencia: {campos['issuetype']['name']} · "
                  f"Título: {campos['summary']}" + (f" · Etiquetas: {', '.join(campos['labels'])}" if campos.get("labels") else ""))
            if r["creada"]:
                print(f"Creada en Jira: {r['clave']} ({r['url']}).")
            else:
                print(f"Vista previa (no se creó nada): {r['vista_previa'].relative_to(raiz)}. Para crearla: --confirmar.")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
