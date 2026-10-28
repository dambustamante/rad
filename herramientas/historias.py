"""Historias de usuario de un producto (Jira Cloud o CSV exportado), como insumo para proponer ADR.

Uso:
  python herramientas/historias.py sincronizar [<producto>]
  python herramientas/historias.py candidatas <producto> [--todas]
  python herramientas/historias.py clasificar <producto> [--archivo LOTE.yaml]
  python herramientas/historias.py propuestas <producto>
  python herramientas/historias.py confirmar <producto> --adr ADR-XX-NNN

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

Configuración en producto.yaml (bloque `historias`):
  fuente: jira | archivo | ninguna
  jql: 'project = FRAUD AND labels = motor-fraudes'     (o tablero: 123 y, opcionalmente, etiqueta: x)
  campo_tipo: Tipo                                      (nombre del campo personalizado con el tipo)
  archivo: export.csv                                   (solo con fuente: archivo, dentro de historias/)

Conexión en .env: JIRA_URL, JIRA_EMAIL, JIRA_TOKEN (solo lectura). Nunca se escribe en Jira.
Las historias se guardan en productos/<producto>/estado/historias/ y el índice en historias/INDICE.md.
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

from comun import RAIZ, ErrorRadiografia, cargar_env, normalizar

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


def leer_json(archivo: Path, defecto):
    return json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else defecto


def escribir_json(archivo: Path, datos) -> None:
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(datos, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


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
    lineas = [f"# Historias de {producto}", "", "> Archivo generado por `herramientas/historias.py`. No se edita a mano.", "",
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


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Historias de usuario como insumo para ADR.")
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
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    codigo = 0
    try:
        if o.accion == "sincronizar":
            nombres = [o.producto] if o.producto else sorted(a.parent.name for a in (raiz / "productos").glob("*/producto.yaml"))
            for producto in nombres:
                try:
                    r = sincronizar(raiz, producto)
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


if __name__ == "__main__":
    sys.exit(main())
