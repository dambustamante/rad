"""Triaje de hallazgos: decisiones del usuario sobre cada hallazgo y calibración de las fuentes.

Uso:
  python herramientas/triaje.py generar <producto> [--repo R]
  python herramientas/triaje.py aplicar <archivo.md>
  python herramientas/triaje.py grupo <producto> --decision D [--motivo TEXTO] [--vence AAAA-MM-DD]
                                     [--repo R] [--nivel N,...] [--severidad S,...] [--fuente PREFIJO] [--simular]
  python herramientas/triaje.py calibracion [<producto>]
  python herramientas/triaje.py publicables (--agregar FUENTE | --quitar FUENTE)

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

`generar` escribe productos/<producto>/triaje/triaje-<fecha>.md con una fila por hallazgo pendiente y una
columna por decisión; el usuario marca con `x` y `aplicar` registra todo o nada. La fuente de verdad es
hallazgos.json; el archivo de triaje queda como registro de lo decidido.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import hallazgos as registro_hallazgos
import productos
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from comun import RAIZ, ErrorRadiografia, cargar_config, escribir_yaml_conservador, leer_yaml_conservador

DECISIONES = {"Resolver": "resolver", "Confirmar": "confirmar", "Conversar": "a-conversar",
              "Deuda": "deuda", "Falso positivo": "falso-positivo"}
MARCAS = {"x", "✓", "✔", "[x]"}
DIAS_DEUDA = 90
COLUMNAS = ["ID", "Repo", "Nivel", "Sev.", "Modo", "Fuente", "Hallazgo", "Evidencia", "Antes",
            *DECISIONES, "Vence", "Motivo"]
ORDEN_SEVERIDAD = {"bloqueante": 0, "alta": 1, "media": 2, "baja": 3}


# --- Selección ---------------------------------------------------------------------------------

def hoy() -> date:
    return date.today()


def deuda_vencida(hallazgo: dict) -> bool:
    triaje = hallazgo.get("triaje") or {}
    return triaje.get("decision") == "deuda" and bool(triaje.get("vence")) and date.fromisoformat(triaje["vence"]) < hoy()


def motivo_atencion(hallazgo: dict) -> str | None:
    """Por qué un hallazgo ya triado necesita una nueva decisión, o None."""
    triaje = hallazgo.get("triaje")
    if hallazgo["estado"] != "abierto" or hallazgo.get("absorbido_por"):
        return None
    if triaje is None:
        return "sin decisión"
    if deuda_vencida(hallazgo):
        return f"deuda vencida el {triaje['vence']}"
    if hallazgo.get("reaparecido") and triaje.get("decision") == "resolver" and triaje.get("fecha", "") < hallazgo.get("ultima_vez", ""):
        return "reapareció después de corregirse"
    return None


def pendientes(registro: dict, repo: str | None = None) -> list[tuple[dict, str]]:
    seleccion = []
    for hallazgo in registro["hallazgos"].values():
        motivo = motivo_atencion(hallazgo)
        if motivo and (repo is None or hallazgo["repo"] == repo):
            seleccion.append((hallazgo, motivo))
    return sorted(seleccion, key=lambda x: (x[1] == "sin decisión", x[0]["nivel"], ORDEN_SEVERIDAD.get(x[0]["severidad"], 9), x[0]["id"]))


# --- Generar -----------------------------------------------------------------------------------

def celda(texto: object) -> str:
    return str(texto if texto is not None else "").replace("|", "/").replace("\n", " ").strip()


def generar(raiz: Path, producto: str, repo: str | None = None) -> Path | None:
    if producto not in productos.leer_productos(raiz):
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    registro = registro_hallazgos.cargar(raiz, producto)
    seleccion = pendientes(registro, repo)
    if not seleccion:
        return None
    carpeta = raiz / "productos" / producto / "triaje"
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo, numero = carpeta / f"triaje-{hoy().isoformat()}.md", 2
    while archivo.exists():
        archivo, numero = carpeta / f"triaje-{hoy().isoformat()}-{numero}.md", numero + 1

    atencion = sum(1 for _, motivo in seleccion if motivo != "sin decisión")
    lineas = [
        f"# Triaje de {producto}{f' · {repo}' if repo else ''} · {hoy().isoformat()}",
        "",
        "> Marcar con `x` **una** decisión por fila. Falso positivo exige motivo. Deuda sin fecha vence a los "
        f"{DIAS_DEUDA} días. Las filas sin marcar quedan pendientes. Al terminar, guardar y pedir a Cursor "
        "\"aplicar el triaje\". No usar el carácter `|` en el motivo.",
        "",
        f"Pendientes: {len(seleccion)}" + (f" ({atencion} requieren atención: ver columna Antes)" if atencion else ""),
        "",
        "| " + " | ".join(COLUMNAS) + " |",
        "|" + "|".join(":---:" if c in DECISIONES else "---" for c in COLUMNAS) + "|",
    ]
    for hallazgo, motivo in seleccion:
        evidencia = ", ".join(f"{e['archivo']}:{e['linea']}" if e.get("linea") else e["archivo"]
                              for e in hallazgo["evidencia"][:2]) or "—"
        antes = "—" if motivo == "sin decisión" else f"{hallazgo['triaje']['decision']}: {motivo}"
        valores = [hallazgo["id"], hallazgo["repo"], hallazgo["nivel"], hallazgo["severidad"], hallazgo["modo"],
                   hallazgo["criterio"] or hallazgo["fuente"], hallazgo["titulo"], evidencia, antes,
                   *([""] * len(DECISIONES)), "", ""]
        lineas.append("| " + " | ".join(celda(v) for v in valores) + " |")
    lineas += ["", "Detalle de cada hallazgo: `productos/" + producto + "/as-is/<repo>.md`."]
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return archivo


# --- Aplicar -----------------------------------------------------------------------------------

def leer_tabla(texto: str) -> list[tuple[int, dict[str, str]]]:
    encabezado, filas = None, []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        if not linea.strip().startswith("|"):
            continue
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if celdas and celdas[0] == "ID":
            encabezado = celdas
        elif encabezado and re.fullmatch(r"H-\d+", celdas[0] if celdas else ""):
            if len(celdas) != len(encabezado):
                raise ErrorRadiografia(f"Línea {numero}: la fila {celdas[0]} tiene {len(celdas)} columnas y debería tener "
                                       f"{len(encabezado)}. Revisar que el motivo no tenga el carácter |.")
            filas.append((numero, dict(zip(encabezado, celdas))))
    if encabezado is None:
        raise ErrorRadiografia("El archivo no tiene la tabla de triaje.")
    return filas


def nueva_decision(decision: str, motivo: str, vence: str | None, fecha: str) -> dict:
    return {"decision": decision, "motivo": motivo or None, "vence": vence, "fecha": fecha}


def validar(decision: str, motivo: str, vence_texto: str, referencia: str) -> str | None:
    """Valida una decisión y devuelve el vencimiento final (solo para deuda)."""
    if decision == "falso-positivo" and not motivo:
        raise ErrorRadiografia(f"{referencia}: un falso positivo requiere motivo.")
    if decision != "deuda":
        if vence_texto:
            raise ErrorRadiografia(f"{referencia}: la fecha de vencimiento solo corresponde a una deuda.")
        return None
    if not vence_texto:
        return (hoy() + timedelta(days=DIAS_DEUDA)).isoformat()
    try:
        vence = date.fromisoformat(vence_texto)
    except ValueError as error:
        raise ErrorRadiografia(f"{referencia}: la fecha '{vence_texto}' no tiene el formato AAAA-MM-DD.") from error
    if vence <= hoy():
        raise ErrorRadiografia(f"{referencia}: el vencimiento de una deuda debe ser una fecha futura.")
    return vence.isoformat()


def registrar(hallazgo: dict, decision: dict) -> None:
    if hallazgo.get("triaje"):
        hallazgo.setdefault("historial_triaje", []).append(hallazgo["triaje"])
    hallazgo["triaje"] = decision


def aplicar(raiz: Path, archivo: Path) -> dict:
    archivo = archivo.resolve()
    producto = archivo.parent.parent.name
    if archivo.parent.name != "triaje" or not (raiz / "productos" / producto).exists():
        raise ErrorRadiografia("El archivo debe estar en productos/<producto>/triaje/.")
    registro = registro_hallazgos.cargar(raiz, producto)
    por_id = {h["id"]: h for h in registro["hallazgos"].values()}
    fecha = hoy().isoformat()

    decisiones: list[tuple[dict, dict]] = []
    for numero, fila in leer_tabla(archivo.read_text(encoding="utf-8")):
        referencia = f"Línea {numero} ({fila['ID']})"
        marcadas = [nombre for nombre in DECISIONES if fila.get(nombre, "").lower() in MARCAS]
        otras = [nombre for nombre in DECISIONES if fila.get(nombre, "") and fila.get(nombre, "").lower() not in MARCAS]
        if otras:
            raise ErrorRadiografia(f"{referencia}: marca no reconocida en {', '.join(otras)}; usar x.")
        if not marcadas:
            continue
        if len(marcadas) > 1:
            raise ErrorRadiografia(f"{referencia}: hay más de una decisión marcada ({', '.join(marcadas)}).")
        if fila["ID"] not in por_id:
            raise ErrorRadiografia(f"{referencia}: el hallazgo no existe en el registro.")
        decision = DECISIONES[marcadas[0]]
        motivo = fila.get("Motivo", "").strip()
        vence = validar(decision, motivo, fila.get("Vence", "").strip(), referencia)
        decisiones.append((por_id[fila["ID"]], nueva_decision(decision, motivo, vence, fecha)))

    for hallazgo, decision in decisiones:
        registrar(hallazgo, decision)
    registro_hallazgos.guardar(raiz, producto, registro)
    texto = archivo.read_text(encoding="utf-8")
    if decisiones:
        archivo.write_text(re.sub(r"\n", f"\n\n> Aplicado el {fecha}: {len(decisiones)} decisión(es).\n", texto, count=1),
                           encoding="utf-8")
    agenda = escribir_agenda(raiz, producto, registro)
    import indices
    indices.indice_producto(raiz, producto)
    return {"producto": producto, "aplicadas": len(decisiones),
            "por_decision": dict(sorted(_contar(d["decision"] for _, d in decisiones).items())), "agenda": agenda}


def _contar(valores) -> dict[str, int]:
    conteo: dict[str, int] = defaultdict(int)
    for valor in valores:
        conteo[valor] += 1
    return conteo


def escribir_agenda(raiz: Path, producto: str, registro: dict) -> Path | None:
    temas: dict[str, list[dict]] = defaultdict(list)
    for h in registro["hallazgos"].values():
        if h["estado"] == "abierto" and (h.get("triaje") or {}).get("decision") == "a-conversar":
            temas[h["criterio"] or h["fuente"]].append(h)
    if not temas:
        return None
    archivo = raiz / "productos" / producto / "agendas" / f"agenda-{hoy().isoformat()}.md"
    archivo.parent.mkdir(parents=True, exist_ok=True)
    lineas = [f"# Agenda para conversar con el equipo · {producto} · {hoy().isoformat()}", "",
              "> Hallazgos marcados como \"Conversar\", agrupados por tema. Después de la reunión, registrar la "
              "decisión con /triar.", ""]
    for tema, lista in sorted(temas.items(), key=lambda x: (-len(x[1]), x[0])):
        lineas += [f"## {tema} ({len(lista)} hallazgo(s))", ""]
        for h in sorted(lista, key=lambda x: (ORDEN_SEVERIDAD.get(x["severidad"], 9), x["id"])):
            evidencia = ", ".join(f"`{e['archivo']}:{e['linea']}`" if e.get("linea") else f"`{e['archivo']}`" for e in h["evidencia"][:2])
            lineas.append(f"- **{h['id']}** · {h['repo']} · {h['severidad']}: {h['titulo']} {evidencia}")
        lineas += ["", "Decisión propuesta: _(completar en la reunión)_", ""]
    archivo.write_text("\n".join(lineas), encoding="utf-8")
    return archivo


# --- Grupo -------------------------------------------------------------------------------------

def grupo(raiz: Path, producto: str, decision: str, motivo: str, vence: str | None, repo: str | None,
          niveles: list[int], severidades: list[str], fuente: str | None, simular: bool) -> list[str]:
    if decision not in DECISIONES.values():
        raise ErrorRadiografia(f"Decisión '{decision}' inválida; valores válidos: {', '.join(DECISIONES.values())}.")
    vence_final = validar(decision, motivo, vence or "", "Decisión en grupo")
    registro = registro_hallazgos.cargar(raiz, producto)
    seleccion = [h for h, _ in pendientes(registro, repo)
                 if (not niveles or h["nivel"] in niveles) and (not severidades or h["severidad"] in severidades)
                 and (not fuente or (h["criterio"] or h["fuente"]).startswith(fuente) or h["fuente"].startswith(fuente))]
    if not simular:
        fecha = hoy().isoformat()
        for h in seleccion:
            registrar(h, nueva_decision(decision, motivo, vence_final, fecha))
        registro_hallazgos.guardar(raiz, producto, registro)
        escribir_agenda(raiz, producto, registro)
        import indices
        indices.indice_producto(raiz, producto)
    return [h["id"] for h in seleccion]


# --- Calibración -------------------------------------------------------------------------------

def umbrales(raiz: Path) -> tuple[int, float, list[str]]:
    config = cargar_config(raiz)
    calibracion = config.get("calibracion") or {}
    publicables = (config.get("publicacion") or {}).get("publicables") or []
    return int(calibracion.get("minimo_triados", 5)), float(calibracion.get("maximo_falsos_positivos", 0.20)), publicables


def calibracion(raiz: Path, producto: str | None = None) -> list[dict]:
    minimo, maximo, publicables = umbrales(raiz)
    nombres = [producto] if producto else list(productos.leer_productos(raiz))
    por_fuente: dict[str, dict] = defaultdict(lambda: {"triados": 0, "falsos_positivos": 0})
    for nombre in nombres:
        for h in registro_hallazgos.cargar(raiz, nombre)["hallazgos"].values():
            decision = (h.get("triaje") or {}).get("decision")
            if not decision:
                continue
            datos = por_fuente[h["criterio"] or h["fuente"]]
            datos["triados"] += 1
            datos["falsos_positivos"] += int(decision == "falso-positivo")
    resultado = []
    for fuente, datos in sorted(por_fuente.items()):
        tasa = datos["falsos_positivos"] / datos["triados"]
        if datos["triados"] < minimo:
            estado = "pocos datos"
        elif tasa < maximo:
            estado = "lista para publicar"
        else:
            estado = "ruidosa: ajustar"
        resultado.append({"fuente": fuente, **datos, "tasa": tasa, "estado": estado, "publicable": fuente in publicables})
    return resultado


def cambiar_publicables(raiz: Path, agregar: str | None, quitar: str | None) -> list[str]:
    """Agrega o quita una fuente de publicacion.publicables en harness.yaml, conservando los comentarios."""
    archivo = raiz / "harness.yaml"
    datos = leer_yaml_conservador(archivo)
    publicacion = datos.setdefault("publicacion", CommentedMap())
    lista = publicacion.get("publicables")
    if not isinstance(lista, CommentedSeq):
        lista = CommentedSeq(lista or [])
        lista.fa.set_flow_style()
        publicacion["publicables"] = lista
    if agregar:
        if agregar in lista:
            raise ErrorRadiografia(f"'{agregar}' ya es publicable.")
        lista.append(agregar)
    if quitar:
        if quitar not in lista:
            raise ErrorRadiografia(f"'{quitar}' no está en la lista de publicables.")
        lista.remove(quitar)
    lista.fa.set_flow_style()
    escribir_yaml_conservador(archivo, datos)
    return list(lista)


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Triaje de hallazgos y calibración.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("generar")
    p.add_argument("producto")
    p.add_argument("--repo")
    p = sub.add_parser("aplicar")
    p.add_argument("archivo", type=Path)
    p = sub.add_parser("grupo")
    p.add_argument("producto")
    p.add_argument("--decision", required=True, choices=list(DECISIONES.values()))
    p.add_argument("--motivo", default="")
    p.add_argument("--vence")
    p.add_argument("--repo")
    p.add_argument("--nivel", default="")
    p.add_argument("--severidad", default="")
    p.add_argument("--fuente")
    p.add_argument("--simular", action="store_true")
    p = sub.add_parser("calibracion")
    p.add_argument("producto", nargs="?")
    p = sub.add_parser("publicables")
    grupo_publicables = p.add_mutually_exclusive_group(required=True)
    grupo_publicables.add_argument("--agregar")
    grupo_publicables.add_argument("--quitar")
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()

    try:
        if o.accion == "generar":
            archivo = generar(raiz, o.producto, o.repo)
            print(f"Triaje: {archivo.relative_to(raiz)}" if archivo else "No hay hallazgos pendientes de triaje.")
        elif o.accion == "aplicar":
            r = aplicar(raiz, o.archivo if o.archivo.is_absolute() else (Path.cwd() / o.archivo))
            print(f"Triaje aplicado en '{r['producto']}': {r['aplicadas']} decisión(es) {r['por_decision']}.")
            if r["agenda"]:
                print(f"Agenda: {r['agenda'].relative_to(raiz)}")
        elif o.accion == "grupo":
            niveles = [int(n) for n in o.nivel.split(",") if n.strip()]
            severidades = [s.strip() for s in o.severidad.split(",") if s.strip()]
            ids = grupo(raiz, o.producto, o.decision, o.motivo, o.vence, o.repo, niveles, severidades, o.fuente, o.simular)
            accion = "Se aplicaría" if o.simular else "Aplicado"
            print(f"{accion} '{o.decision}' a {len(ids)} hallazgo(s): {', '.join(ids) or 'ninguno'}")
        elif o.accion == "calibracion":
            filas = calibracion(raiz, o.producto)
            if not filas:
                print("Todavía no hay hallazgos triados.")
            else:
                print("| Fuente | Triados | Falsos positivos | Tasa | Estado | Publicable |")
                print("|---|---|---|---|---|---|")
                for f in filas:
                    print(f"| {f['fuente']} | {f['triados']} | {f['falsos_positivos']} | {f['tasa']:.0%} | {f['estado']} "
                          f"| {'sí' if f['publicable'] else 'no'} |")
        elif o.accion == "publicables":
            lista = cambiar_publicables(raiz, o.agregar, o.quitar)
            print(f"Publicables: {', '.join(lista) or 'ninguno'}")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
