"""Coherencia de las decisiones del equipo y de los productos con lo que tiene más autoridad.

Hay dos tipos de ámbito:
- `equipo`: cada ADR-EQ frente a los documentos vigentes de arquitectura;
- `<producto>`: cada ADR de producto de tipo decisión frente a arquitectura y a los ADR-EQ.

Uso:
  python herramientas/coherencia.py preparar [--ambito equipo|<producto>] [--json]
  python herramientas/coherencia.py extracto <ID> [--ambito <producto>]
        ID: ADR-EQ-002, equipo:ADR-EQ-002, ADR-MF-001 o fuente:ID (por ejemplo decision-records:ADR-007)
  python herramientas/coherencia.py registrar [--ambito equipo|<producto>] --decision ADR-XX-NNN --doc CLAVE
        --relacion RELACION [--cita-documento TEXTO --cita-decision TEXTO] [--criterios XX-NNN.N,...]
        [--explicacion TEXTO] [--manual MOTIVO]
  python herramientas/coherencia.py lote <archivo.yaml>
  python herramientas/coherencia.py generar [--ambito equipo|<producto>]

Sin --ambito, `preparar` y `generar` recorren el equipo y todos los productos. Opción común: --raiz RUTA.

`lote` registra de una vez todos los pares de un ámbito (todo o nada) y regenera su COHERENCIA.md:

  ambito: equipo
  pares:
    - {decision: ADR-EQ-002, doc: decisiones:ADR-011, relacion: sin_relacion}
    - decision: ADR-EQ-002
      doc: decisiones:ADR-010
      relacion: choca
      cita_documento: <texto copiado del documento>
      cita_decision: <texto copiado de la decisión>
      criterios: [EQ-002.2]
      explicacion: <por qué>

La comparación la hace el agente; este script decide qué pares hay que evaluar, valida cada resultado
(incluido que las citas existan textualmente en los documentos) y genera `equipo/COHERENCIA.md` y
`productos/<producto>/decisiones/COHERENCIA.md`. El estado vive en `equipo/estado/coherencia.json` y en
`productos/<producto>/estado/coherencia.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from comun import RAIZ, ErrorRadiografia, carpeta_decisiones_producto, normalizar
from sync_arquitectura import primer_parrafo, secciones

RELACIONES = ("sin_relacion", "compatible", "duplica", "choca")
SECCIONES_HUELLA = ("decision", "acciones requeridas", "regla rapida", "criterios de verificacion")
SECCIONES_EXTRACTO = ("decision", "regla rapida", "criterios de verificacion")
ESTADOS_EVALUADOS = ("propuesto", "aprobado")
LARGO_MINIMO_CITA = 15
PATRON_ARCHIVO_ADR = re.compile(r"^(ADR-([A-Z]{2,5})-\d{3})-.*\.md$")
PATRON_CRITERIO = re.compile(r"`([A-Z]{2,5}-\d{3}\.\d+)`")
PATRON_CAMPO = re.compile(r"^\s*[-*]\s*\**([^:*]+?)\**\s*:\s*\**\s*(.*?)\s*$")
EQUIPO = "equipo"


# --- Lectura de decisiones ---------------------------------------------------------------------

def huella(contenido: dict[str, list[str]], claves: tuple[str, ...] | None = None) -> str:
    partes = []
    for clave in sorted(contenido) if claves is None else claves:
        partes.append(clave + "\n" + "\n".join(contenido.get(clave, [])).strip())
    return hashlib.sha256("\n\n".join(partes).encode("utf-8")).hexdigest()


def leer_campos(lineas: list[str]) -> dict[str, str]:
    """Campos `- **Nombre:** valor` de una sección, con el nombre normalizado. Vale la primera aparición."""
    campos = {}
    for linea in lineas:
        if coincidencia := PATRON_CAMPO.match(linea):
            campos.setdefault(normalizar(coincidencia.group(1)), coincidencia.group(2).strip().strip("`").strip())
    return campos


def leer_decisiones(raiz: Path, carpeta: Path, prefijo: str | None = None) -> dict[str, dict]:
    """ADR de una carpeta (`ADR-XX-NNN-titulo.md`). Con `prefijo`, solo los de esa sigla."""
    decisiones = {}
    if not carpeta.exists():
        return decisiones
    for archivo in sorted(carpeta.glob("ADR-*.md")):
        coincidencia = PATRON_ARCHIVO_ADR.match(archivo.name)
        if not coincidencia or (prefijo and coincidencia.group(2) != prefijo):
            continue
        id_adr = coincidencia.group(1)
        texto = archivo.read_text(encoding="utf-8")
        titulo, contenido = secciones(texto.splitlines())
        estado = primer_parrafo(contenido.get("estado", [])) or "NO DETERMINADO"
        campos = leer_campos(contenido.get("tipo y alcance", []))
        decisiones[id_adr] = {
            "id": id_adr,
            "titulo": re.sub(r"^ADR-[A-Z]{2,5}-\d{3}:\s*", "", titulo or archivo.stem),
            "estado": estado,
            "evaluado": normalizar(estado) in ESTADOS_EVALUADOS,
            "tipo": normalizar(campos.get("tipo", "decision")) or "decision",
            "campos": campos,
            "regla_rapida": " ".join(l.strip(" >") for l in contenido.get("regla rapida", []) if l.strip()),
            "criterios": PATRON_CRITERIO.findall("\n".join(contenido.get("criterios de verificacion", []))),
            "huella": huella(contenido, SECCIONES_HUELLA),
            "archivo": archivo.relative_to(raiz).as_posix(),
            "texto": texto,
            "contenido": contenido,
        }
    return decisiones


def leer_decisiones_equipo(raiz: Path) -> dict[str, dict]:
    return leer_decisiones(raiz, raiz / "equipo" / "decisiones", "EQ")


def sigla_de(raiz: Path, producto: str) -> str | None:
    archivo = raiz / "productos" / producto / "producto.yaml"
    if not archivo.exists():
        return None
    from ruamel.yaml import YAML  # import local: evita la dependencia circular con productos.py
    datos = YAML(typ="safe").load(archivo.read_text(encoding="utf-8")) or {}
    return datos.get("sigla")


def leer_decisiones_producto(raiz: Path, producto: str) -> dict[str, dict]:
    sigla = sigla_de(raiz, producto)
    if not sigla:
        return {}
    return leer_decisiones(raiz, carpeta_decisiones_producto(raiz, producto), sigla)


def leer_arquitectura_vigente(raiz: Path) -> dict[str, dict]:
    indice = raiz / "arquitectura" / "estado" / "indice.json"
    if not indice.exists():
        return {}
    vigentes = {}
    for documento in json.loads(indice.read_text(encoding="utf-8")).get("documentos", []):
        if documento["vigencia"] != "vigente":
            continue
        archivo = raiz / documento["archivo"]
        texto = archivo.read_text(encoding="utf-8") if archivo.exists() else ""
        vigentes[f"{documento['fuente']}:{documento['id']}"] = {**documento, "texto": texto, "huella": documento["sha256"]}
    return vigentes


# --- Ámbitos -----------------------------------------------------------------------------------

@dataclass
class Ambito:
    nombre: str
    titulo: str
    sujetos: dict[str, dict]        # decisiones que se evalúan
    referencias: dict[str, dict]    # documentos con más autoridad: clave -> {titulo, regla_rapida, texto, huella, archivo}
    carpeta: Path                   # donde vive COHERENCIA.md
    archivo_estado: Path            # coherencia.json


def ambito_equipo(raiz: Path) -> Ambito:
    return Ambito(EQUIPO, "Coherencia de las decisiones del equipo con arquitectura",
                  leer_decisiones_equipo(raiz), leer_arquitectura_vigente(raiz), raiz / "equipo",
                  raiz / "equipo" / "estado" / "coherencia.json")


def ambito_producto(raiz: Path, producto: str, carpeta: Path | None = None) -> Ambito:
    """Ámbito de un producto. Con `carpeta`, los ADR se leen de ahí (por ejemplo, la rama de un MR del harness)."""
    if not (raiz / "productos" / producto / "producto.yaml").exists():
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    referencias = leer_arquitectura_vigente(raiz)
    for id_eq, eq in leer_decisiones_equipo(raiz).items():
        if eq["evaluado"]:
            referencias[f"{EQUIPO}:{id_eq}"] = {**eq, "tipo": "decision-equipo"}
    decisiones = (leer_decisiones(raiz, carpeta, sigla_de(raiz, producto)) if carpeta
                  else leer_decisiones_producto(raiz, producto))
    sujetos = {k: v for k, v in decisiones.items() if v["tipo"] == "decision"}
    return Ambito(producto, f"Coherencia de las decisiones de {producto} con arquitectura y con el equipo",
                  sujetos, referencias, carpeta or carpeta_decisiones_producto(raiz, producto),
                  raiz / "productos" / producto / "estado" / "coherencia.json")


CARPETA_DECISIONES: Path | None = None   # --decisiones: ADR del producto desde otra carpeta (rama de un MR del harness)


def obtener_ambito(raiz: Path, nombre: str) -> Ambito:
    return ambito_equipo(raiz) if nombre == EQUIPO else ambito_producto(raiz, nombre, CARPETA_DECISIONES)


def todos_los_ambitos(raiz: Path) -> list[Ambito]:
    ambitos = [ambito_equipo(raiz)]
    for archivo in sorted((raiz / "productos").glob("*/producto.yaml")):
        ambito = ambito_producto(raiz, archivo.parent.name)
        if ambito.sujetos:
            ambitos.append(ambito)
    return ambitos


def leer_estado(ambito: Ambito) -> dict:
    archivo = ambito.archivo_estado
    if not archivo.exists():
        return {"evaluaciones": {}, "suspendidos": {}}
    return json.loads(archivo.read_text(encoding="utf-8"))


def escribir_estado(ambito: Ambito, estado: dict) -> None:
    ambito.archivo_estado.parent.mkdir(parents=True, exist_ok=True)
    ambito.archivo_estado.write_text(
        json.dumps(estado, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def suspendidos(raiz: Path, producto: str | None = None) -> dict[str, list[str]]:
    """Criterios suspendidos por choques: los del equipo y, si se indica, los del producto."""
    resultado = dict(leer_estado(ambito_equipo(raiz)).get("suspendidos", {}))
    if producto:
        archivo = raiz / "productos" / producto / "estado" / "coherencia.json"
        if archivo.exists():
            resultado.update(json.loads(archivo.read_text(encoding="utf-8")).get("suspendidos", {}))
    return resultado


def clave_par(id_decision: str, clave_doc: str) -> str:
    return f"{id_decision}|{clave_doc}"


# --- Preparar ----------------------------------------------------------------------------------

def preparar(ambito: Ambito) -> dict:
    """Pares (decisión, documento) que hay que evaluar porque son nuevos o cambiaron."""
    evaluaciones = leer_estado(ambito)["evaluaciones"]
    pendientes: dict[str, list[str]] = {}
    for id_decision, decision in ambito.sujetos.items():
        if not decision["evaluado"]:
            continue
        for clave_doc, doc in ambito.referencias.items():
            previa = evaluaciones.get(clave_par(id_decision, clave_doc))
            if previa and previa["huella_decision"] == decision["huella"] and previa["huella_documento"] == doc["huella"]:
                continue
            pendientes.setdefault(id_decision, []).append(clave_doc)
    return {
        "ambito": ambito.nombre,
        "referencias_disponibles": bool(ambito.referencias),
        "total_pares": sum(len(v) for v in pendientes.values()),
        "decisiones": {i: {"titulo": ambito.sujetos[i]["titulo"], "regla_rapida": ambito.sujetos[i]["regla_rapida"]}
                       for i in pendientes},
        "documentos": {c: {"titulo": ambito.referencias[c]["titulo"], "regla_rapida": ambito.referencias[c]["regla_rapida"]}
                       for c in sorted({c for lista in pendientes.values() for c in lista})},
        "pendientes": pendientes,
    }


def imprimir_preparacion(plan: dict) -> None:
    encabezado = f"[{plan['ambito']}]"
    if not plan["referencias_disponibles"]:
        print(f"{encabezado} No hay documentos vigentes contra los cuales comparar (ejecutar /actualizar).")
        return
    if not plan["total_pares"]:
        print(f"{encabezado} Coherencia al día: no hay pares nuevos ni modificados que evaluar.")
        return
    print(f"{encabezado} Coherencia: {plan['total_pares']} par(es) por evaluar.\n")
    print("Documentos de referencia involucrados (título y regla rápida):")
    for clave, doc in plan["documentos"].items():
        print(f"  - {clave}: {doc['titulo']} | {doc['regla_rapida'] or 'sin regla rápida'}")
    print("\nPares pendientes por decisión:")
    for id_decision, documentos in plan["pendientes"].items():
        decision = plan["decisiones"][id_decision]
        print(f"  - {id_decision} ({decision['titulo']}) | {decision['regla_rapida']}")
        print(f"      contra: {', '.join(documentos)}")
    print()


# --- Extracto ----------------------------------------------------------------------------------

def extracto(raiz: Path, identificador: str, producto: str | None = None) -> str:
    """Decisión, regla rápida y criterios de un documento; si no tiene esas secciones, el texto completo."""
    identificador_eq = identificador.removeprefix(f"{EQUIPO}:")
    if identificador_eq.startswith("ADR-EQ-"):
        documentos = leer_decisiones_equipo(raiz)
        identificador = identificador_eq
    elif re.match(r"^ADR-[A-Z]{2,5}-\d{3}$", identificador):
        if not producto:
            raise ErrorRadiografia("Para un ADR de producto, indicar --ambito <producto>.")
        documentos = (leer_decisiones(raiz, CARPETA_DECISIONES, sigla_de(raiz, producto)) if CARPETA_DECISIONES
                      else leer_decisiones_producto(raiz, producto))
    else:
        documentos = leer_arquitectura_vigente(raiz)
    if identificador not in documentos:
        raise ErrorRadiografia(f"No existe el documento '{identificador}'.")
    documento = documentos[identificador]
    contenido = documento.get("contenido") or secciones(documento["texto"].splitlines())[1]
    partes = [f"# {identificador}: {documento['titulo']} ({documento['archivo']})"]
    for clave in SECCIONES_EXTRACTO:
        lineas = [l for l in contenido.get(clave, []) if l.strip()]
        if lineas:
            partes.append(f"## {clave}\n" + "\n".join(lineas))
    if len(partes) == 1:
        partes.append("(sin secciones Decisión, Regla rápida ni Criterios: texto completo)\n" + documento["texto"])
    return "\n\n".join(partes)


# --- Registrar ---------------------------------------------------------------------------------

def texto_comparable(texto: str) -> str:
    texto = re.sub(r"[*_`>|#]", " ", texto)
    texto = re.sub(r"^\s*([-+]|\d+\.)\s+", " ", texto, flags=re.MULTILINE)
    return normalizar(texto)


def cita_existe(cita: str, texto: str) -> bool:
    return texto_comparable(cita) in texto_comparable(texto)


def evaluacion_valida(ambito: Ambito, id_decision: str, clave_doc: str, relacion: str, cita_documento: str | None,
                      cita_decision: str | None, criterios: list[str], explicacion: str | None, manual: str | None) -> dict:
    """Valida el resultado de un par y lo devuelve listo para guardar. Lanza ErrorRadiografia si no es válido."""
    if id_decision not in ambito.sujetos:
        raise ErrorRadiografia(f"No existe la decisión {id_decision} en el ámbito '{ambito.nombre}'.")
    if clave_doc not in ambito.referencias:
        raise ErrorRadiografia(f"No existe el documento vigente '{clave_doc}' en el ámbito '{ambito.nombre}'.")
    if relacion not in RELACIONES:
        raise ErrorRadiografia(f"Relación '{relacion}' inválida; valores válidos: {', '.join(RELACIONES)}.")
    decision, doc = ambito.sujetos[id_decision], ambito.referencias[clave_doc]

    if relacion in ("duplica", "choca"):
        for nombre, cita, texto in (("cita-documento", cita_documento, doc["texto"]),
                                    ("cita-decision", cita_decision, decision["texto"])):
            if not cita or len(cita.strip()) < LARGO_MINIMO_CITA:
                raise ErrorRadiografia(f"La relación '{relacion}' exige --{nombre} con al menos {LARGO_MINIMO_CITA} caracteres.")
            if not cita_existe(cita, texto):
                raise ErrorRadiografia(f"La --{nombre} no aparece textualmente en el documento. Copiarla tal como está escrita.")
        if not explicacion:
            raise ErrorRadiografia(f"La relación '{relacion}' exige --explicacion.")
    if relacion == "choca":
        if not criterios:
            raise ErrorRadiografia("La relación 'choca' exige --criterios con los criterios afectados (por ejemplo EQ-002.2).")
        desconocidos = [c for c in criterios if c not in decision["criterios"]]
        if desconocidos:
            raise ErrorRadiografia(f"Criterios que no existen en {id_decision}: {', '.join(desconocidos)}.")
    elif criterios:
        raise ErrorRadiografia("--criterios solo se usa con la relación 'choca'.")

    return {
        "decision": id_decision, "documento": clave_doc, "relacion": relacion,
        "cita_documento": cita_documento, "cita_decision": cita_decision, "criterios_suspendidos": criterios,
        "explicacion": explicacion, "manual": manual,
        "huella_decision": decision["huella"], "huella_documento": doc["huella"],
        "evaluado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def registrar(ambito: Ambito, id_decision: str, clave_doc: str, relacion: str, cita_documento: str | None,
              cita_decision: str | None, criterios: list[str], explicacion: str | None, manual: str | None) -> None:
    evaluacion = evaluacion_valida(ambito, id_decision, clave_doc, relacion, cita_documento, cita_decision,
                                   criterios, explicacion, manual)
    estado = leer_estado(ambito)
    estado["evaluaciones"][clave_par(id_decision, clave_doc)] = evaluacion
    escribir_estado(ambito, estado)


def registrar_lote(raiz: Path, archivo: Path) -> dict:
    """Registra todos los pares de un archivo YAML (todo o nada) y regenera el COHERENCIA.md del ámbito."""
    import yaml
    if not archivo.exists():
        raise ErrorRadiografia(f"No existe el archivo de lote {archivo}.")
    try:
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise ErrorRadiografia(f"El lote no es un YAML válido: {error}") from error
    ambito = obtener_ambito(raiz, str(datos.get("ambito") or EQUIPO))
    errores, evaluaciones = [], {}
    for indice, par in enumerate(datos.get("pares") or [], start=1):
        decision, doc = str(par.get("decision", "")), str(par.get("doc", ""))
        criterios = par.get("criterios") or []
        criterios = [c.strip() for c in (criterios.split(",") if isinstance(criterios, str) else criterios) if str(c).strip()]
        try:
            evaluaciones[clave_par(decision, doc)] = evaluacion_valida(
                ambito, decision, doc, str(par.get("relacion", "")), par.get("cita_documento"), par.get("cita_decision"),
                criterios, par.get("explicacion"), par.get("manual"))
        except ErrorRadiografia as error:
            errores.append(f"pares[{indice}] ({decision} × {doc}): {error}")
    if errores:
        raise ErrorRadiografia(f"El lote tiene {len(errores)} error(es); no se registró nada:\n  - " + "\n  - ".join(errores))
    estado = leer_estado(ambito)
    estado["evaluaciones"].update(evaluaciones)
    escribir_estado(ambito, estado)
    return {"registrados": len(evaluaciones), **generar(raiz, ambito)}


# --- Generar -----------------------------------------------------------------------------------

def generar(raiz: Path, ambito: Ambito) -> dict:
    """Depura evaluaciones obsoletas, calcula suspensiones y escribe COHERENCIA.md del ámbito."""
    estado = leer_estado(ambito)
    vigentes = {clave: e for clave, e in estado["evaluaciones"].items()
                if e["decision"] in ambito.sujetos and e["documento"] in ambito.referencias}
    plan = preparar(ambito)
    pendientes = plan["pendientes"]

    suspension: dict[str, list[str]] = {}
    for e in vigentes.values():
        if e["relacion"] == "choca":
            suspension[e["decision"]] = sorted(set(suspension.get(e["decision"], [])) | set(e["criterios_suspendidos"]))
    escribir_estado(ambito, {"evaluaciones": vigentes, "suspendidos": suspension})

    lock_archivo = raiz / "arquitectura" / "estado" / "fuentes.lock"
    lock = json.loads(lock_archivo.read_text(encoding="utf-8")) if lock_archivo.exists() else {}
    referencia = ", ".join(f"{f}@{d['commit'][:7]}" for f, d in sorted(lock.items())) or "sin fuentes sincronizadas"
    lineas = [
        f"# {ambito.titulo}",
        "",
        "> Archivo generado por `/actualizar` (`herramientas/coherencia.py generar`). No se edita a mano.",
        "",
        f"Evaluado contra: {referencia}" + (" y las decisiones del equipo" if ambito.nombre != EQUIPO else ""),
        "",
        "| Decisión | Estado | Resultado | Criterios suspendidos |",
        "|---|---|---|---|",
    ]
    for id_decision, decision in ambito.sujetos.items():
        propias = [e for e in vigentes.values() if e["decision"] == id_decision]
        choques = sum(1 for e in propias if e["relacion"] == "choca")
        duplicados = sum(1 for e in propias if e["relacion"] == "duplica")
        if not decision["evaluado"]:
            resultado = "no se evalúa (estado no vigente)"
        elif not ambito.referencias:
            resultado = "NO DETERMINADO - no hay documentos de referencia sincronizados"
        else:
            partes = []
            if choques:
                partes.append(f"❌ {choques} choque(s)")
            if duplicados:
                partes.append(f"⚠️ {duplicados} duplicación(es)")
            if id_decision in pendientes:
                partes.append(f"⏳ {len(pendientes[id_decision])} par(es) pendiente(s) de evaluar")
            resultado = " · ".join(partes) or "✅ sin choques"
        enlace = Path(os.path.relpath(raiz / decision["archivo"], ambito.carpeta)).as_posix()
        lineas.append(f"| [{id_decision}]({enlace}) {decision['titulo']} | {decision['estado']} "
                      f"| {resultado} | {', '.join(suspension.get(id_decision, [])) or '—'} |")

    for relacion, titulo in (("choca", "Choques"), ("duplica", "Duplicaciones")):
        casos = sorted((e for e in vigentes.values() if e["relacion"] == relacion), key=lambda x: (x["decision"], x["documento"]))
        if not casos:
            continue
        lineas += ["", f"## {titulo}"]
        for e in casos:
            lineas += ["", f"### {e['decision']} × {e['documento']}", "",
                       f"- **{e['documento']}:** «{e['cita_documento']}»",
                       f"- **{e['decision']}:** «{e['cita_decision']}»",
                       f"- **Explicación:** {e['explicacion']}"]
            if e["criterios_suspendidos"]:
                lineas.append(f"- **Criterios suspendidos:** {', '.join(e['criterios_suspendidos'])}")
            if e["manual"]:
                lineas.append(f"- **Corrección manual:** {e['manual']}")

    compatibles = sorted((e for e in vigentes.values() if e["relacion"] == "compatible"), key=lambda x: (x["decision"], x["documento"]))
    if compatibles:
        lineas += ["", "## Relaciones compatibles", "", "| Decisión | Documento | Explicación |", "|---|---|---|"]
        lineas += [f"| {e['decision']} | {e['documento']} | {e['explicacion'] or '—'} |" for e in compatibles]

    ambito.carpeta.mkdir(parents=True, exist_ok=True)
    (ambito.carpeta / "COHERENCIA.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return {"ambito": ambito.nombre, "pendientes": plan["total_pares"], "suspendidos": suspension}


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coherencia de las decisiones del equipo y de los productos.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    parser.add_argument("--decisiones", type=Path, help="carpeta con los ADR del producto (por ejemplo, la rama de un MR)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("preparar", help="lista los pares que hay que evaluar")
    p.add_argument("--ambito")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("extracto", help="muestra el extracto de un documento")
    p.add_argument("identificador")
    p.add_argument("--ambito")
    p = sub.add_parser("registrar", help="registra el resultado de un par, con validación")
    p.add_argument("--ambito", default=EQUIPO)
    p.add_argument("--decision", "--eq", dest="decision", required=True)
    p.add_argument("--doc", required=True)
    p.add_argument("--relacion", required=True, choices=RELACIONES)
    p.add_argument("--cita-documento", "--cita-arquitectura", dest="cita_documento")
    p.add_argument("--cita-decision", "--cita-equipo", dest="cita_decision")
    p.add_argument("--criterios", default="")
    p.add_argument("--explicacion")
    p.add_argument("--manual", help="motivo de una corrección hecha por el usuario")
    p = sub.add_parser("lote", help="registra todos los pares de un archivo YAML y regenera COHERENCIA.md")
    p.add_argument("archivo", type=Path)
    p = sub.add_parser("generar", help="escribe COHERENCIA.md")
    p.add_argument("--ambito")
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    global CARPETA_DECISIONES
    CARPETA_DECISIONES = o.decisiones.resolve() if o.decisiones else None

    try:
        if o.accion in ("preparar", "generar"):
            ambitos = [obtener_ambito(raiz, o.ambito)] if o.ambito else todos_los_ambitos(raiz)
            for ambito in ambitos:
                if o.accion == "preparar":
                    plan = preparar(ambito)
                    print(json.dumps(plan, indent=2, ensure_ascii=False)) if o.json else imprimir_preparacion(plan)
                else:
                    r = generar(raiz, ambito)
                    print(f"[{r['ambito']}] COHERENCIA.md generado. Pares pendientes: {r['pendientes']}. "
                          f"Criterios suspendidos: {sum(len(v) for v in r['suspendidos'].values())}.")
        elif o.accion == "extracto":
            print(extracto(raiz, o.identificador, o.ambito if o.ambito != EQUIPO else None))
        elif o.accion == "lote":
            r = registrar_lote(raiz, o.archivo.resolve())
            print(f"[{r['ambito']}] {r['registrados']} par(es) registrado(s). Pares pendientes: {r['pendientes']}. "
                  f"Criterios suspendidos: {sum(len(v) for v in r['suspendidos'].values())}.")
        elif o.accion == "registrar":
            criterios = [c.strip() for c in o.criterios.split(",") if c.strip()]
            registrar(obtener_ambito(raiz, o.ambito), o.decision, o.doc, o.relacion, o.cita_documento,
                      o.cita_decision, criterios, o.explicacion, o.manual)
            print(f"Registrado: {o.decision} × {o.doc} = {o.relacion}")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
