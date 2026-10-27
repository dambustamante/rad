"""Coherencia entre las decisiones del equipo (ADR-EQ) y los documentos vigentes de arquitectura.

Uso:
  python herramientas/coherencia.py preparar [--json]
  python herramientas/coherencia.py extracto <ID>            (ADR-EQ-003 o fuente:ID, por ejemplo decision-records:ADR-007)
  python herramientas/coherencia.py registrar --eq ADR-EQ-NNN --doc fuente:ID --relacion RELACION
                                              [--cita-arquitectura TEXTO --cita-equipo TEXTO]
                                              [--criterios EQ-NNN.N,...] [--explicacion TEXTO] [--manual MOTIVO]
  python herramientas/coherencia.py generar

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

La comparación la hace el agente; este script decide qué pares hay que evaluar, valida cada
resultado (incluido que las citas existan textualmente en los documentos) y genera
`equipo/COHERENCIA.md`. El estado vive en `equipo/coherencia.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from comun import RAIZ, ErrorRadiografia, normalizar
from sync_arquitectura import primer_parrafo, secciones

RELACIONES = ("sin_relacion", "compatible", "duplica", "choca")
SECCIONES_HUELLA = ("decision", "acciones requeridas", "regla rapida", "criterios de verificacion")
SECCIONES_EXTRACTO = ("decision", "regla rapida", "criterios de verificacion")
ESTADOS_EQ_EVALUADOS = ("propuesto", "aprobado")
LARGO_MINIMO_CITA = 15
PATRON_ARCHIVO_EQ = re.compile(r"^(ADR-EQ-\d{3})-.*\.md$")
PATRON_CRITERIO = re.compile(r"`(EQ-\d{3}\.\d+)`")


# --- Lectura de documentos ---------------------------------------------------------------------

def huella(contenido: dict[str, list[str]], claves: tuple[str, ...] | None = None) -> str:
    partes = []
    for clave in sorted(contenido) if claves is None else claves:
        partes.append(clave + "\n" + "\n".join(contenido.get(clave, [])).strip())
    return hashlib.sha256("\n\n".join(partes).encode("utf-8")).hexdigest()


def leer_decisiones_equipo(raiz: Path) -> dict[str, dict]:
    decisiones = {}
    for archivo in sorted((raiz / "equipo").glob("ADR-EQ-*.md")):
        coincidencia = PATRON_ARCHIVO_EQ.match(archivo.name)
        if not coincidencia:
            continue
        texto = archivo.read_text(encoding="utf-8")
        titulo, contenido = secciones(texto.splitlines())
        estado = primer_parrafo(contenido.get("estado", [])) or "NO DETERMINADO"
        decisiones[coincidencia.group(1)] = {
            "id": coincidencia.group(1),
            "titulo": re.sub(r"^ADR-EQ-\d{3}:\s*", "", titulo or archivo.stem),
            "estado": estado,
            "evaluado": normalizar(estado) in ESTADOS_EQ_EVALUADOS,
            "regla_rapida": " ".join(l.strip(" >") for l in contenido.get("regla rapida", []) if l.strip()),
            "criterios": PATRON_CRITERIO.findall("\n".join(contenido.get("criterios de verificacion", []))),
            "huella": huella(contenido, SECCIONES_HUELLA),
            "archivo": archivo.relative_to(raiz).as_posix(),
            "texto": texto,
            "contenido": contenido,
        }
    return decisiones


def leer_arquitectura_vigente(raiz: Path) -> dict[str, dict]:
    indice = raiz / "arquitectura" / "indice.json"
    if not indice.exists():
        return {}
    documentos = json.loads(indice.read_text(encoding="utf-8")).get("documentos", [])
    vigentes = {}
    for documento in documentos:
        if documento["vigencia"] != "vigente":
            continue
        archivo = raiz / documento["archivo"]
        texto = archivo.read_text(encoding="utf-8") if archivo.exists() else ""
        vigentes[f"{documento['fuente']}:{documento['id']}"] = {**documento, "texto": texto}
    return vigentes


def leer_estado(raiz: Path) -> dict:
    archivo = raiz / "equipo" / "coherencia.json"
    if not archivo.exists():
        return {"evaluaciones": {}}
    return json.loads(archivo.read_text(encoding="utf-8"))


def escribir_estado(raiz: Path, estado: dict) -> None:
    archivo = raiz / "equipo" / "coherencia.json"
    archivo.write_text(json.dumps(estado, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def clave_par(id_eq: str, clave_doc: str) -> str:
    return f"{id_eq}|{clave_doc}"


# --- Preparar ----------------------------------------------------------------------------------

def preparar(raiz: Path) -> dict:
    """Pares (ADR-EQ, documento vigente) que hay que evaluar porque son nuevos o cambiaron."""
    decisiones = leer_decisiones_equipo(raiz)
    arquitectura = leer_arquitectura_vigente(raiz)
    evaluaciones = leer_estado(raiz)["evaluaciones"]

    pendientes: dict[str, list[str]] = {}
    for id_eq, eq in decisiones.items():
        if not eq["evaluado"]:
            continue
        for clave_doc, doc in arquitectura.items():
            previa = evaluaciones.get(clave_par(id_eq, clave_doc))
            if previa and previa["huella_equipo"] == eq["huella"] and previa["huella_arquitectura"] == doc["sha256"]:
                continue
            pendientes.setdefault(id_eq, []).append(clave_doc)

    return {
        "arquitectura_disponible": bool(arquitectura),
        "total_pares": sum(len(v) for v in pendientes.values()),
        "decisiones": {
            id_eq: {"titulo": decisiones[id_eq]["titulo"], "regla_rapida": decisiones[id_eq]["regla_rapida"]}
            for id_eq in pendientes
        },
        "documentos": {
            clave: {"titulo": arquitectura[clave]["titulo"], "regla_rapida": arquitectura[clave]["regla_rapida"]}
            for clave in sorted({c for lista in pendientes.values() for c in lista})
        },
        "pendientes": pendientes,
    }


def imprimir_preparacion(plan: dict) -> None:
    if not plan["arquitectura_disponible"]:
        print("No hay documentos de arquitectura vigentes (ejecutar /arquitectura y /actualizar). Nada que evaluar.")
        return
    if not plan["total_pares"]:
        print("Coherencia al día: no hay pares nuevos ni modificados que evaluar.")
        return
    print(f"Coherencia: {plan['total_pares']} par(es) por evaluar.\n")
    print("Documentos de arquitectura involucrados (título y regla rápida):")
    for clave, doc in plan["documentos"].items():
        print(f"  - {clave}: {doc['titulo']} | {doc['regla_rapida'] or 'sin regla rápida'}")
    print("\nPares pendientes por decisión del equipo:")
    for id_eq, documentos in plan["pendientes"].items():
        eq = plan["decisiones"][id_eq]
        print(f"  - {id_eq} ({eq['titulo']}) | {eq['regla_rapida']}")
        print(f"      contra: {', '.join(documentos)}")


# --- Extracto ----------------------------------------------------------------------------------

def extracto(raiz: Path, identificador: str) -> str:
    """Decisión, regla rápida y criterios de un documento; si no tiene esas secciones, el texto completo."""
    if identificador.startswith("ADR-EQ-"):
        decisiones = leer_decisiones_equipo(raiz)
        if identificador not in decisiones:
            raise ErrorRadiografia(f"No existe {identificador} en equipo/.")
        documento = decisiones[identificador]
        contenido, texto, encabezado = documento["contenido"], documento["texto"], f"{identificador}: {documento['titulo']}"
    else:
        arquitectura = leer_arquitectura_vigente(raiz)
        if identificador not in arquitectura:
            raise ErrorRadiografia(f"No existe el documento vigente '{identificador}' (formato fuente:ID).")
        documento = arquitectura[identificador]
        texto = documento["texto"]
        _, contenido = secciones(texto.splitlines())
        encabezado = f"{identificador}: {documento['titulo']} ({documento['archivo']})"

    partes = [f"# {encabezado}"]
    for clave in SECCIONES_EXTRACTO:
        lineas = [l for l in contenido.get(clave, []) if l.strip()]
        if lineas:
            partes.append(f"## {clave}\n" + "\n".join(lineas))
    if len(partes) == 1:
        partes.append("(sin secciones Decisión, Regla rápida ni Criterios: texto completo)\n" + texto)
    return "\n\n".join(partes)


# --- Registrar ---------------------------------------------------------------------------------

def texto_comparable(texto: str) -> str:
    texto = re.sub(r"[*_`>|#]", " ", texto)
    texto = re.sub(r"^\s*([-+]|\d+\.)\s+", " ", texto, flags=re.MULTILINE)
    return normalizar(texto)


def cita_existe(cita: str, texto: str) -> bool:
    return texto_comparable(cita) in texto_comparable(texto)


def registrar(raiz: Path, id_eq: str, clave_doc: str, relacion: str, cita_arquitectura: str | None,
              cita_equipo: str | None, criterios: list[str], explicacion: str | None, manual: str | None) -> None:
    decisiones = leer_decisiones_equipo(raiz)
    arquitectura = leer_arquitectura_vigente(raiz)
    if id_eq not in decisiones:
        raise ErrorRadiografia(f"No existe {id_eq} en equipo/.")
    if clave_doc not in arquitectura:
        raise ErrorRadiografia(f"No existe el documento vigente '{clave_doc}' (formato fuente:ID).")
    if relacion not in RELACIONES:
        raise ErrorRadiografia(f"Relación '{relacion}' inválida; valores válidos: {', '.join(RELACIONES)}.")
    eq, doc = decisiones[id_eq], arquitectura[clave_doc]

    if relacion in ("duplica", "choca"):
        for nombre, cita, texto in (("cita-arquitectura", cita_arquitectura, doc["texto"]),
                                    ("cita-equipo", cita_equipo, eq["texto"])):
            if not cita or len(cita.strip()) < LARGO_MINIMO_CITA:
                raise ErrorRadiografia(f"La relación '{relacion}' exige --{nombre} con al menos {LARGO_MINIMO_CITA} caracteres.")
            if not cita_existe(cita, texto):
                raise ErrorRadiografia(f"La --{nombre} no aparece textualmente en el documento. Copiarla tal como está escrita.")
        if not explicacion:
            raise ErrorRadiografia(f"La relación '{relacion}' exige --explicacion.")
    if relacion == "choca":
        if not criterios:
            raise ErrorRadiografia("La relación 'choca' exige --criterios con los criterios afectados (por ejemplo EQ-003.2).")
        desconocidos = [c for c in criterios if c not in eq["criterios"]]
        if desconocidos:
            raise ErrorRadiografia(f"Criterios que no existen en {id_eq}: {', '.join(desconocidos)}.")
    elif criterios:
        raise ErrorRadiografia("--criterios solo se usa con la relación 'choca'.")

    estado = leer_estado(raiz)
    estado["evaluaciones"][clave_par(id_eq, clave_doc)] = {
        "equipo": id_eq,
        "documento": clave_doc,
        "relacion": relacion,
        "cita_arquitectura": cita_arquitectura,
        "cita_equipo": cita_equipo,
        "criterios_suspendidos": criterios,
        "explicacion": explicacion,
        "manual": manual,
        "huella_equipo": eq["huella"],
        "huella_arquitectura": doc["sha256"],
        "evaluado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    escribir_estado(raiz, estado)


# --- Generar -----------------------------------------------------------------------------------

def generar(raiz: Path) -> dict:
    """Depura evaluaciones obsoletas, calcula suspensiones y escribe COHERENCIA.md."""
    decisiones = leer_decisiones_equipo(raiz)
    arquitectura = leer_arquitectura_vigente(raiz)
    estado = leer_estado(raiz)
    vigentes = {
        clave: e for clave, e in estado["evaluaciones"].items()
        if e["equipo"] in decisiones and e["documento"] in arquitectura
    }
    plan = preparar(raiz)
    pendientes = plan["pendientes"]

    suspendidos: dict[str, list[str]] = {}
    for e in vigentes.values():
        if e["relacion"] == "choca":
            suspendidos.setdefault(e["equipo"], [])
            suspendidos[e["equipo"]] = sorted(set(suspendidos[e["equipo"]]) | set(e["criterios_suspendidos"]))

    lock = {}
    archivo_lock = raiz / "arquitectura" / "fuentes.lock"
    if archivo_lock.exists():
        lock = json.loads(archivo_lock.read_text(encoding="utf-8"))
    estado = {"evaluaciones": vigentes, "suspendidos": suspendidos}
    escribir_estado(raiz, estado)

    referencia = ", ".join(f"{f}@{d['commit'][:7]}" for f, d in sorted(lock.items())) or "sin fuentes sincronizadas"
    lineas = [
        "# Coherencia de las decisiones del equipo con arquitectura",
        "",
        "> Archivo generado por `/actualizar` (`herramientas/coherencia.py generar`). No se edita a mano.",
        "",
        f"Evaluado contra: {referencia}",
        "",
        "| ADR-EQ | Estado | Resultado | Criterios suspendidos |",
        "|---|---|---|---|",
    ]
    for id_eq, eq in decisiones.items():
        de_eq = [e for e in vigentes.values() if e["equipo"] == id_eq]
        choques = sum(1 for e in de_eq if e["relacion"] == "choca")
        duplicados = sum(1 for e in de_eq if e["relacion"] == "duplica")
        if not eq["evaluado"]:
            resultado = "no se evalúa (estado no vigente)"
        elif not arquitectura:
            resultado = "NO DETERMINADO - arquitectura no sincronizada"
        elif id_eq in pendientes:
            resultado = f"⏳ {len(pendientes[id_eq])} par(es) pendiente(s) de evaluar"
        elif choques:
            resultado = f"❌ {choques} choque(s)"
        elif duplicados:
            resultado = f"⚠️ {duplicados} duplicación(es)"
        else:
            resultado = "✅ sin choques"
        lineas.append(f"| [{id_eq}]({Path(eq['archivo']).name}) {eq['titulo']} | {eq['estado']} | {resultado} "
                      f"| {', '.join(suspendidos.get(id_eq, [])) or '—'} |")

    for relacion, titulo in (("choca", "Choques"), ("duplica", "Duplicaciones")):
        casos = [e for e in vigentes.values() if e["relacion"] == relacion]
        if not casos:
            continue
        lineas += ["", f"## {titulo}"]
        for e in sorted(casos, key=lambda x: (x["equipo"], x["documento"])):
            lineas += [
                "",
                f"### {e['equipo']} × {e['documento']}",
                "",
                f"- **Arquitectura:** «{e['cita_arquitectura']}»",
                f"- **{e['equipo']}:** «{e['cita_equipo']}»",
                f"- **Explicación:** {e['explicacion']}",
            ]
            if e["criterios_suspendidos"]:
                lineas.append(f"- **Criterios suspendidos:** {', '.join(e['criterios_suspendidos'])}")
            if e["manual"]:
                lineas.append(f"- **Corrección manual:** {e['manual']}")

    relacionados = [e for e in vigentes.values() if e["relacion"] == "compatible"]
    if relacionados:
        lineas += ["", "## Relaciones compatibles", "", "| ADR-EQ | Documento de arquitectura | Explicación |", "|---|---|---|"]
        for e in sorted(relacionados, key=lambda x: (x["equipo"], x["documento"])):
            lineas.append(f"| {e['equipo']} | {e['documento']} | {e['explicacion'] or '—'} |")

    (raiz / "equipo" / "COHERENCIA.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return {"pendientes": plan["total_pares"], "suspendidos": suspendidos}


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coherencia de los ADR-EQ con arquitectura.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p_preparar = sub.add_parser("preparar", help="lista los pares que hay que evaluar")
    p_preparar.add_argument("--json", action="store_true")
    p_extracto = sub.add_parser("extracto", help="muestra el extracto de un documento")
    p_extracto.add_argument("identificador")
    p_registrar = sub.add_parser("registrar", help="registra el resultado de un par, con validación")
    p_registrar.add_argument("--eq", required=True)
    p_registrar.add_argument("--doc", required=True)
    p_registrar.add_argument("--relacion", required=True, choices=RELACIONES)
    p_registrar.add_argument("--cita-arquitectura")
    p_registrar.add_argument("--cita-equipo")
    p_registrar.add_argument("--criterios", default="")
    p_registrar.add_argument("--explicacion")
    p_registrar.add_argument("--manual", help="motivo de una corrección hecha por el usuario")
    sub.add_parser("generar", help="escribe equipo/COHERENCIA.md")
    opciones = parser.parse_args(argumentos)
    raiz = opciones.raiz.resolve()

    try:
        if opciones.accion == "preparar":
            plan = preparar(raiz)
            if opciones.json:
                print(json.dumps(plan, indent=2, ensure_ascii=False))
            else:
                imprimir_preparacion(plan)
        elif opciones.accion == "extracto":
            print(extracto(raiz, opciones.identificador))
        elif opciones.accion == "registrar":
            criterios = [c.strip() for c in opciones.criterios.split(",") if c.strip()]
            registrar(raiz, opciones.eq, opciones.doc, opciones.relacion, opciones.cita_arquitectura,
                      opciones.cita_equipo, criterios, opciones.explicacion, opciones.manual)
            print(f"Registrado: {opciones.eq} × {opciones.doc} = {opciones.relacion}")
        elif opciones.accion == "generar":
            resultado = generar(raiz)
            print(f"equipo/COHERENCIA.md generado. Pares pendientes: {resultado['pendientes']}. "
                  f"Criterios suspendidos: {sum(len(v) for v in resultado['suspendidos'].values())}.")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
