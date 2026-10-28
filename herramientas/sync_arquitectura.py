"""Sincroniza los documentos de arquitectura y genera su índice.

Uso: python herramientas/sync_arquitectura.py [--raiz RUTA]

Para cada fuente de `harness.yaml` (arquitectura.fuentes):
1. clona o actualiza el repositorio en `.cache/arquitectura/<id>/` (solo git);
2. copia la carpeta indicada a `arquitectura/decisiones/<id>/` (fuentes de tipo adr) o a
   `arquitectura/estandares/<id>/` (estándares y referencias);
3. lee cada documento (título, estado, fechas, regla rápida, relaciones).

Luego escribe `arquitectura/estado/fuentes.lock`, `arquitectura/estado/indice.json` y
`arquitectura/INDICE.md`, e informa los cambios respecto de la sincronización anterior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from comun import RAIZ, ErrorRadiografia, actualizar_clon, cargar_config, git, normalizar, resolver_commit

TIPOS = ("adr", "estandar", "referencia")
VIGENCIAS = ("vigente", "pendiente", "no_vigente")
NO_DETERMINADO = "NO DETERMINADO"
ARCHIVOS_OMITIDOS = {"readme.md", "index.md", "_index.md"}
SUBCARPETAS = ("decisiones", "estandares")


def carpeta_fuente(raiz: Path, fuente: dict) -> Path:
    """arquitectura/decisiones/<id> para ADR; arquitectura/estandares/<id> para estándares y referencias."""
    return raiz / "arquitectura" / ("decisiones" if fuente["tipo"] == "adr" else "estandares") / fuente["id"]


def carpeta_estado(raiz: Path) -> Path:
    return raiz / "arquitectura" / "estado"

PATRON_ID_ADR = re.compile(r"\bADR[-_ ]?(\d+)\b", re.IGNORECASE)
PATRON_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
PATRON_NUMERACION = re.compile(r"^\d+(\.\d+)*\.?\s*")
PATRON_FECHA_DMA = re.compile(r"\b(\d{2})[-/](\d{2})[-/](\d{4})\b")
PATRON_FECHA_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
PATRON_REEMPLAZA = re.compile(r"\breemplaza\b(?:\s+a)?\s*:?\s*((?:ADR[-_ ]?\d+[\s,y]*)+)", re.IGNORECASE)
PATRON_REEMPLAZADO_POR = re.compile(r"\breemplazad[oa]\s+por\s*:?\s*(ADR[-_ ]?\d+)", re.IGNORECASE)


# --- Configuración -----------------------------------------------------------------------------

def leer_fuentes(config: dict) -> tuple[list[dict], dict[str, list[str]]]:
    """Valida y normaliza las fuentes y la configuración de estados."""
    arquitectura = config.get("arquitectura") or {}
    estados = arquitectura.get("estados") or {}
    for vigencia in VIGENCIAS:
        if not isinstance(estados.get(vigencia, []), list):
            raise ErrorRadiografia(f"arquitectura.estados.{vigencia} debe ser una lista.")

    fuentes = []
    vistos = set()
    for indice, fuente in enumerate(arquitectura.get("fuentes") or [], start=1):
        if not isinstance(fuente, dict):
            raise ErrorRadiografia(f"La fuente {indice} de harness.yaml no es un mapa de claves.")
        id_fuente = str(fuente.get("id", "")).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", id_fuente):
            raise ErrorRadiografia(f"La fuente {indice} necesita un id en minúsculas y guiones (por ejemplo decision-records).")
        if id_fuente in vistos:
            raise ErrorRadiografia(f"El id de fuente '{id_fuente}' está repetido.")
        vistos.add(id_fuente)
        if not fuente.get("url"):
            raise ErrorRadiografia(f"La fuente '{id_fuente}' necesita url.")
        tipo = fuente.get("tipo", "adr")
        if tipo not in TIPOS:
            raise ErrorRadiografia(f"La fuente '{id_fuente}' tiene tipo '{tipo}'; valores válidos: {', '.join(TIPOS)}.")
        estado_por_defecto = fuente.get("estado_por_defecto")
        if estado_por_defecto is not None and estado_por_defecto not in VIGENCIAS:
            raise ErrorRadiografia(f"La fuente '{id_fuente}' tiene estado_por_defecto inválido; valores válidos: {', '.join(VIGENCIAS)}.")
        fuentes.append({
            "id": id_fuente,
            "url": str(fuente["url"]),
            "ref": str(fuente.get("ref", "main")),
            "ruta": str(fuente.get("ruta", ".")),
            "tipo": tipo,
            "estado_por_defecto": estado_por_defecto,
        })
    return fuentes, {v: [str(e) for e in estados.get(v, [])] for v in VIGENCIAS}


# --- Sincronización ----------------------------------------------------------------------------

def sincronizar_fuente(fuente: dict, raiz: Path) -> str:
    """Deja la copia de la fuente en el commit de su ref y devuelve ese commit."""
    cache = raiz / ".cache" / "arquitectura" / fuente["id"]
    actualizar_clon(fuente["url"], cache, raiz)
    try:
        commit = resolver_commit(cache, fuente["ref"])
    except ErrorRadiografia as error:
        raise ErrorRadiografia(f"La ref '{fuente['ref']}' no existe en la fuente '{fuente['id']}'.") from error
    git("checkout", "--quiet", "--force", "--detach", commit, cwd=cache)

    origen = (cache / fuente["ruta"]).resolve()
    if not origen.is_dir() or cache.resolve() not in (origen, *origen.parents):
        raise ErrorRadiografia(f"La ruta '{fuente['ruta']}' no existe en la fuente '{fuente['id']}'.")
    destino = carpeta_fuente(raiz, fuente)
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(origen, destino, ignore=shutil.ignore_patterns(".git"))
    return commit


# --- Lectura de documentos ---------------------------------------------------------------------

def secciones(lineas: list[str]) -> tuple[str | None, dict[str, list[str]]]:
    """Devuelve el título (primer encabezado de nivel 1) y el contenido de cada sección.

    El nombre de cada sección se normaliza: sin numeración ("2. Estado" -> "estado"),
    en minúsculas y sin tildes. Una sección termina en el siguiente encabezado de igual o
    mayor nivel.
    """
    titulo = None
    contenido: dict[str, list[str]] = {}
    abiertas: list[tuple[int, str]] = []
    en_bloque_codigo = False
    for linea in lineas:
        if linea.lstrip().startswith("```"):
            en_bloque_codigo = not en_bloque_codigo
        coincidencia = None if en_bloque_codigo else PATRON_ENCABEZADO.match(linea)
        if coincidencia:
            nivel = len(coincidencia.group(1))
            texto = coincidencia.group(2)
            if nivel == 1 and titulo is None:
                titulo = texto
            abiertas = [(n, s) for n, s in abiertas if n < nivel]
            nombre = normalizar(PATRON_NUMERACION.sub("", texto))
            contenido.setdefault(nombre, [])
            abiertas.append((nivel, nombre))
            continue
        for _, nombre in abiertas:
            contenido[nombre].append(linea)
    return titulo, contenido


def limpiar(texto: str) -> str:
    """Quita marcas de markdown simples y espacios sobrantes."""
    texto = re.sub(r"^\s*(>|[-*+](?=\s)|\d+\.(?=\s))\s*", "", texto)
    texto = texto.replace("**", "").replace("__", "").replace("`", "")
    return " ".join(texto.split()).strip("*_ ")


def primer_parrafo(lineas: list[str]) -> str | None:
    for linea in lineas:
        if linea.strip():
            return limpiar(linea)
    return None


def a_iso(texto: str) -> str | None:
    if coincidencia := PATRON_FECHA_ISO.search(texto):
        return "-".join(coincidencia.groups())
    if coincidencia := PATRON_FECHA_DMA.search(texto):
        dia, mes, anio = coincidencia.groups()
        return f"{anio}-{mes}-{dia}"
    return None


def normalizar_id_adr(texto: str) -> str:
    coincidencia = PATRON_ID_ADR.search(texto)
    return f"ADR-{coincidencia.group(1)}" if coincidencia else texto


def clasificar_estado(estado: str | None, estados: dict[str, list[str]], por_defecto: str | None) -> tuple[str, str | None]:
    """Devuelve (vigencia, motivo). La vigencia es una de VIGENCIAS o NO_DETERMINADO."""
    if not estado:
        if por_defecto:
            return por_defecto, None
        return NO_DETERMINADO, "el documento no tiene sección Estado"
    estado_normalizado = normalizar(estado)
    for vigencia in VIGENCIAS:
        for valor in estados.get(vigencia, []):
            valor_normalizado = normalizar(valor)
            if re.match(rf"{re.escape(valor_normalizado)}\b", estado_normalizado):
                return vigencia, None
    return NO_DETERMINADO, f"el estado '{estado}' no está en arquitectura.estados de harness.yaml"


def analizar_documento(archivo: Path, carpeta_fuente: Path, fuente: dict, estados: dict[str, list[str]],
                       raiz: Path) -> dict | None:
    """Lee un documento. Devuelve None si no corresponde indexarlo.

    Un `README.md` o `index.md` en la raíz de la fuente es una portada y no se indexa. Más
    adentro, representa al documento de su carpeta (formato `0001-titulo/index.md`).
    """
    es_portada = archivo.name.lower() in ARCHIVOS_OMITIDOS
    if es_portada and archivo.parent == carpeta_fuente:
        return None
    nombre_base = archivo.parent.name if es_portada else archivo.stem
    texto = archivo.read_text(encoding="utf-8", errors="replace")
    titulo, contenido = secciones(texto.splitlines())

    if fuente["tipo"] == "adr":
        origen_id = titulo or ""
        if not PATRON_ID_ADR.search(origen_id):
            numero = re.match(r"^(\d{1,4})\b", nombre_base)
            origen_id = f"ADR-{numero.group(1)}" if numero else ""
        if not PATRON_ID_ADR.search(origen_id):
            return None
        id_documento = normalizar_id_adr(origen_id)
    else:
        id_documento = nombre_base

    estado = primer_parrafo(contenido.get("estado", []))
    vigencia, motivo = clasificar_estado(estado, estados, fuente["estado_por_defecto"])

    fecha_creacion = fecha_aprobacion = None
    for linea in contenido.get("fecha", []) + contenido.get("fechas", []):
        linea_normalizada = normalizar(linea)
        if "creacion" in linea_normalizada and not fecha_creacion:
            fecha_creacion = a_iso(linea)
        elif "aprobacion" in linea_normalizada and not fecha_aprobacion:
            fecha_aprobacion = a_iso(linea)

    regla_rapida = " ".join(limpiar(linea) for linea in contenido.get("regla rapida", []) if linea.strip()) or None

    reemplaza = sorted({
        normalizar_id_adr(id_adr)
        for coincidencia in PATRON_REEMPLAZA.finditer(texto)
        for id_adr in re.findall(r"ADR[-_ ]?\d+", coincidencia.group(1), re.IGNORECASE)
    })
    reemplazado_por = sorted({normalizar_id_adr(m.group(1)) for m in PATRON_REEMPLAZADO_POR.finditer(texto)})

    return {
        "id": id_documento,
        "fuente": fuente["id"],
        "tipo": fuente["tipo"],
        "titulo": limpiar(titulo) if titulo else archivo.stem,
        "estado": estado,
        "vigencia": vigencia,
        "motivo": motivo,
        "fecha_creacion": fecha_creacion,
        "fecha_aprobacion": fecha_aprobacion,
        "regla_rapida": regla_rapida,
        "reemplaza": reemplaza,
        "reemplazado_por": reemplazado_por,
        "archivo": archivo.relative_to(raiz).as_posix(),
        "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
    }


def analizar_fuente(fuente: dict, estados: dict[str, list[str]], raiz: Path) -> list[dict]:
    carpeta = carpeta_fuente(raiz, fuente)
    documentos = []
    for archivo in sorted(carpeta.rglob("*.md")):
        documento = analizar_documento(archivo, carpeta, fuente, estados, raiz)
        if documento:
            documentos.append(documento)
    return documentos


# --- Salidas -----------------------------------------------------------------------------------

def leer_json(archivo: Path) -> dict:
    if not archivo.exists():
        return {}
    try:
        return json.loads(archivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def calcular_cambios(anterior: dict, documentos: list[dict], lock_anterior: dict, lock: dict) -> dict:
    previos = {d["archivo"]: d for d in anterior.get("documentos", [])}
    actuales = {d["archivo"]: d for d in documentos}
    return {
        "fuentes_actualizadas": sorted(f for f in lock if f in lock_anterior and lock[f]["commit"] != lock_anterior[f]["commit"]),
        "fuentes_nuevas": sorted(f for f in lock if f not in lock_anterior),
        "fuentes_retiradas": sorted(f for f in lock_anterior if f not in lock),
        "nuevos": sorted(a for a in actuales if a not in previos),
        "eliminados": sorted(a for a in previos if a not in actuales),
        "modificados": sorted(a for a in actuales if a in previos and actuales[a]["sha256"] != previos[a]["sha256"]),
        "cambios_de_vigencia": sorted(
            (a, previos[a]["vigencia"], actuales[a]["vigencia"])
            for a in actuales
            if a in previos and actuales[a]["vigencia"] != previos[a]["vigencia"]
        ),
    }


def escribir_indice_md(archivo: Path, documentos: list[dict], lock: dict, generado: str) -> None:
    def celda(valor) -> str:
        if not valor:
            return "—"
        texto = ", ".join(valor) if isinstance(valor, list) else str(valor)
        return texto.replace("|", "\\|")

    lineas = [
        "# Índice de arquitectura",
        "",
        "> Archivo generado por `/actualizar` (`make sync-arquitectura`). No se edita a mano.",
        "",
        f"Generado: {generado}",
        "",
        "## Fuentes",
        "",
        "| Fuente | Tipo | Ref | Commit |",
        "|---|---|---|---|",
    ]
    for id_fuente, datos in sorted(lock.items()):
        lineas.append(f"| {id_fuente} | {datos['tipo']} | {datos['ref']} | `{datos['commit'][:12]}` |")

    conteo = {v: sum(1 for d in documentos if d["vigencia"] == v) for v in (*VIGENCIAS, NO_DETERMINADO)}
    lineas += [
        "",
        "## Resumen",
        "",
        f"- Vigentes: {conteo['vigente']}",
        f"- Pendientes: {conteo['pendiente']}",
        f"- No vigentes: {conteo['no_vigente']}",
        f"- NO DETERMINADO: {conteo[NO_DETERMINADO]}",
    ]

    for id_fuente in sorted(lock):
        lineas += [
            "",
            f"## Documentos de {id_fuente}",
            "",
            "| ID | Título | Estado | Vigencia | Aprobación | Reemplaza | Reemplazado por | Archivo |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for d in (d for d in documentos if d["fuente"] == id_fuente):
            lineas.append(
                f"| {celda(d['id'])} | {celda(d['titulo'])} | {celda(d['estado'])} | {celda(d['vigencia'])} "
                f"| {celda(d['fecha_aprobacion'])} | {celda(d['reemplaza'])} | {celda(d['reemplazado_por'])} "
                f"| [{Path(d['archivo']).name}]({Path(d['archivo']).relative_to('arquitectura').as_posix()}) |"
            )

    vigentes = [d for d in documentos if d["vigencia"] == "vigente"]
    lineas += ["", "## Reglas rápidas de los documentos vigentes", ""]
    if vigentes:
        for d in vigentes:
            lineas.append(f"- **{d['id']}** ({d['titulo']}): {d['regla_rapida'] or 'NO DETERMINADO - el documento no tiene sección Regla rápida'}")
    else:
        lineas.append("No hay documentos vigentes.")

    indeterminados = [d for d in documentos if d["vigencia"] == NO_DETERMINADO]
    if indeterminados:
        lineas += ["", "## Documentos con vigencia NO DETERMINADO", ""]
        for d in indeterminados:
            lineas.append(f"- **{d['id']}** (`{d['archivo']}`): {d['motivo']}")

    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def imprimir_resumen(documentos: list[dict], cambios: dict, errores: list[str]) -> None:
    print("Sincronización de arquitectura\n")
    conteo = {v: sum(1 for d in documentos if d["vigencia"] == v) for v in (*VIGENCIAS, NO_DETERMINADO)}
    print(f"  Documentos: {len(documentos)} (vigentes {conteo['vigente']}, pendientes {conteo['pendiente']}, "
          f"no vigentes {conteo['no_vigente']}, NO DETERMINADO {conteo[NO_DETERMINADO]})")
    etiquetas = {
        "fuentes_nuevas": "Fuentes nuevas",
        "fuentes_actualizadas": "Fuentes con commits nuevos",
        "fuentes_retiradas": "Fuentes retiradas",
        "nuevos": "Documentos nuevos",
        "modificados": "Documentos modificados",
        "eliminados": "Documentos eliminados",
    }
    hubo_cambios = False
    for clave, etiqueta in etiquetas.items():
        if cambios[clave]:
            hubo_cambios = True
            print(f"  {etiqueta}: {', '.join(cambios[clave])}")
    for archivo, antes, despues in cambios["cambios_de_vigencia"]:
        hubo_cambios = True
        print(f"  Cambio de vigencia: {archivo}: {antes} -> {despues}")
    if not hubo_cambios:
        print("  Sin cambios respecto de la sincronización anterior.")
    for d in documentos:
        if d["vigencia"] == NO_DETERMINADO:
            print(f"  NO DETERMINADO: {d['id']} ({d['archivo']}): {d['motivo']}")
    for error in errores:
        print(f"  ERROR: {error}")
    print("\n  Índice: arquitectura/INDICE.md")


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sincroniza los documentos de arquitectura.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    opciones = parser.parse_args(argumentos)
    raiz = opciones.raiz.resolve()

    try:
        fuentes, estados = leer_fuentes(cargar_config(raiz))
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    if not fuentes:
        print("No hay fuentes de arquitectura en harness.yaml (arquitectura.fuentes). Nada que sincronizar.")
        return 0

    carpeta = raiz / "arquitectura"
    estado = carpeta_estado(raiz)
    estado.mkdir(parents=True, exist_ok=True)
    lock_anterior = leer_json(estado / "fuentes.lock")
    indice_anterior = leer_json(estado / "indice.json")
    documentos_previos = indice_anterior.get("documentos", [])
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")

    lock: dict[str, dict] = {}
    documentos: list[dict] = []
    errores: list[str] = []
    for fuente in fuentes:
        try:
            commit = sincronizar_fuente(fuente, raiz)
            lock[fuente["id"]] = {"url": fuente["url"], "ref": fuente["ref"], "ruta": fuente["ruta"],
                                  "tipo": fuente["tipo"], "commit": commit, "sincronizado": ahora}
            documentos += analizar_fuente(fuente, estados, raiz)
        except ErrorRadiografia as error:
            errores.append(str(error))
            if fuente["id"] in lock_anterior:
                # Se conserva la copia y los datos de la sincronización anterior de esta fuente.
                lock[fuente["id"]] = lock_anterior[fuente["id"]]
                documentos += [d for d in documentos_previos if d["fuente"] == fuente["id"]]

    configuradas = {carpeta_fuente(raiz, f) for f in fuentes}
    for nombre in SUBCARPETAS:
        if (carpeta / nombre).exists():
            for subcarpeta in (carpeta / nombre).iterdir():
                if subcarpeta.is_dir() and subcarpeta not in configuradas:
                    shutil.rmtree(subcarpeta)

    cambios = calcular_cambios(indice_anterior, documentos, lock_anterior, lock)
    (estado / "fuentes.lock").write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (estado / "indice.json").write_text(
        json.dumps({"generado": ahora, "documentos": documentos}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    escribir_indice_md(carpeta / "INDICE.md", documentos, lock, ahora)
    imprimir_resumen(documentos, cambios, errores)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
