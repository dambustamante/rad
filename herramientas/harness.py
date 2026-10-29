"""Harness de cada producto (harness-<producto>): lo crea y lo mantiene radiografia.

Uso:
  python herramientas/harness.py crear <producto>
  python herramientas/harness.py traer [<producto>]       git pull de la copia local (antes de la coherencia)
  python herramientas/harness.py generar [<producto>]     regenera lo generado y hace commit si cambió
  python herramientas/harness.py guardar <producto> --mensaje TEXTO   commit de los ADR de decisiones/
  python herramientas/harness.py estado [<producto>]

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

La copia de radiografia vive en productos/<producto>/harness/ (fuera de git de radiografia) y es un repositorio
propio. radiografia escribe ahí y hace commit; el push lo hace el TL. Dueños de cada parte:

- generado por radiografia (se regenera; no se edita): .cursor/rules/generado/, repos.json, GENERADO.json,
  decisiones/INDICE.md y decisiones/COHERENCIA.md;
- del equipo (se crean una vez desde la plantilla y después se mantienen por MR): AGENTS.md, README.md,
  Makefile, herramientas/, .cursor/hooks.json y los ADR de decisiones/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import hallazgos as registro_hallazgos
import productos
import terceros
from coherencia import leer_arquitectura_vigente, leer_decisiones_producto, sigla_de, suspendidos as criterios_suspendidos
from comun import RAIZ, ErrorRadiografia, git, leer_json, normalizar
from revisar import decisiones_con_criterios

PLANTILLA = Path(__file__).resolve().parent / "plantilla_harness"
GENERADOS = ("repos.json", "GENERADO.json", ".cursor/rules/generado/")
MAXIMO_HALLAZGOS = 15
LARGO_RESUMEN = 700
ORDEN_SEVERIDAD = {"bloqueante": 0, "alta": 1, "media": 2, "baja": 3}
PREFIJO_ID = re.compile(r"^[A-Z]+-[0-9]+:\s*")
COMO_CODIGO = ("automática", "revisión de código", "automática + revisión de código")
FORMA_DE_TRABAJAR = ("historia", "del mr", "plataforma git")


def ruta(raiz: Path, producto: str) -> Path:
    return raiz / "productos" / producto / "harness"


def existe(raiz: Path, producto: str) -> bool:
    return (ruta(raiz, producto) / ".git").exists()


def con_harness(raiz: Path, producto: str | None) -> list[str]:
    nombres = [producto] if producto else list(productos.leer_productos(raiz))
    if producto and not existe(raiz, producto):
        raise ErrorRadiografia(f"El producto '{producto}' no tiene harness. Crearlo con: harness.py crear {producto}")
    return [n for n in nombres if existe(raiz, n)]


# --- Contenido generado ------------------------------------------------------------------------

def texto_decisiones(raiz: Path, producto: str) -> str:
    """Regla que se aplica siempre: lo que el código del producto debe cumplir, en forma compacta."""
    suspendidos = criterios_suspendidos(raiz, producto)
    lineas = ["---", f"description: Decisiones que el código de {producto} debe cumplir (generado por radiografia; no se edita)",
              "alwaysApply: true", "---", "", f"# Decisiones que aplican a {producto}", "",
              "Generado por radiografia: no se edita. Las decisiones en `propuesta` todavía se están calibrando: "
              "conviene cumplirlas, pero no bloquean el MR.", "", "## Arquitectura (obligatorio)", ""]
    lineas += [f"- `{clave}` {PREFIJO_ID.sub('', d['titulo'])}: {d['regla_rapida'] or 'ver el documento'}"
               for clave, d in sorted(leer_arquitectura_vigente(raiz).items())] or ["Sin documentos de arquitectura vigentes."]
    for titulo, decisiones in (("Equipo", decisiones_con_criterios(raiz)),
                               ("Producto", {k: v for k, v in leer_decisiones_producto(raiz, producto).items()
                                             if v["tipo"] == "decision" and v["evaluado"]})):
        lineas += ["", f"## {titulo}", ""]
        if not decisiones:
            lineas.append("Sin decisiones vigentes.")
        for id_decision, d in decisiones.items():
            modo = " (propuesta)" if normalizar(d["estado"]) == "propuesto" else ""
            lineas += [f"### {id_decision} {d['titulo']}{modo}", "", f"Regla: {d['regla_rapida'] or '—'}", ""]
            tabla = d.get("tabla") or {}
            if not tabla:
                from verificaciones import leer_criterios
                tabla = leer_criterios(d["texto"])
            if any(termino in criterio["como"].lower() for criterio in tabla.values() for termino in FORMA_DE_TRABAJAR):
                continue  # decisiones sobre la forma de trabajar (historias, MR): basta la regla rápida
            for id_criterio, criterio in tabla.items():
                if id_criterio not in suspendidos.get(id_decision, []) and criterio["como"] in COMO_CODIGO:
                    lineas.append(f"- `{id_criterio}` ({criterio['severidad']}): {criterio['texto']}")
            lineas.append("")
    excepciones = [d for d in leer_decisiones_producto(raiz, producto).values()
                   if d["tipo"] == "excepcion" and normalizar(d["estado"]) == "aprobado"]
    if excepciones:
        lineas += ["## Excepciones aprobadas", ""]
        lineas += [f"- {d['id']}: {d['titulo']} (exceptúa {d['campos'].get('criterios exceptuados', '—')}; "
                   f"repositorios {d['campos'].get('repositorios', 'todos')}; vence {d['campos'].get('vence', '—')})" for d in excepciones]
    return "\n".join(lineas).rstrip() + "\n"


def seccion_asis(texto: str, nombre: str) -> str:
    coincidencia = re.search(rf"^## {re.escape(nombre)}\s*\n(.*?)(?=^## |\Z)", texto, re.MULTILINE | re.DOTALL)
    resumen = " ".join(coincidencia.group(1).split()) if coincidencia else ""
    return (resumen[:LARGO_RESUMEN] + "…") if len(resumen) > LARGO_RESUMEN else resumen


def texto_repo(raiz: Path, producto: str, repo: dict, registro: dict) -> str:
    """Regla de un repositorio: se carga solo al trabajar en code/<repo>/."""
    import revision
    id_repo = str(repo["id"])
    lineas = ["---", f"description: Contexto del repositorio {id_repo} (generado por radiografia; no se edita)",
              f"globs: code/{id_repo}/**", "alwaysApply: false", "---", "",
              f"# {id_repo} ({repo['tipo']}, rama principal {repo['rama']})", ""]
    ficha = raiz / "productos" / producto / "as-is" / f"{id_repo}.md"
    texto_ficha = ficha.read_text(encoding="utf-8") if ficha.exists() else ""
    for nombre in ("Propósito", "Arquitectura real"):
        resumen = seccion_asis(texto_ficha, nombre)
        lineas += [f"**{nombre}:** {resumen or 'NO DETERMINADO (sin revisión de código)'}", ""]
    codigo = (registro.get("repos", {}).get(id_repo) or {}).get("codigo")
    componentes = revision.leer_trabajo(raiz, producto, codigo["id"], id_repo).get("componentes", []) if codigo else []
    lineas += ["## Componentes", ""]
    lineas += revision.tabla_componentes(componentes) if componentes else ["Sin componentes registrados."]
    fichas = terceros.para_repo(raiz, producto, id_repo)
    if fichas:
        lineas += ["", "## Terceros", ""]
        for f in fichas:
            sla = f.get("sla") or {}
            lineas.append(f"- `{f['id']}` {f.get('nombre') or ''}: {f.get('protocolo')}, p95 {sla.get('p95_ms') or '—'} ms, "
                          f"política ante falla {f.get('politica_ante_falla')} ({f.get('justificacion')})")
    abiertos = sorted((h for h in registro["hallazgos"].values()
                       if h["repo"] == id_repo and h["rama"] == repo["rama"] and h["estado"] == "abierto"
                       and not h.get("absorbido_por") and (h.get("triaje") or {}).get("decision") != "falso-positivo"),
                      key=lambda h: (ORDEN_SEVERIDAD.get(h["severidad"], 9), h["id"]))
    lineas += ["", "## Hallazgos abiertos", "", "Si se toca ese código, corregirlos en el mismo trabajo.", ""]
    for h in abiertos[:MAXIMO_HALLAZGOS]:
        e = h["evidencia"][0] if h["evidencia"] else None
        ubicacion = f" · `{e['archivo']}:{e['linea']}`" if e and e.get("linea") else (f" · `{e['archivo']}`" if e else "")
        lineas.append(f"- {h['id']} · {h['criterio'] or h['fuente']} · {h['severidad']}: {h['titulo']}{ubicacion}")
    if not abiertos:
        lineas.append("Ninguno.")
    elif len(abiertos) > MAXIMO_HALLAZGOS:
        lineas.append(f"- … y {len(abiertos) - MAXIMO_HALLAZGOS} más de menor severidad.")
    return "\n".join(lineas) + "\n"


def contenido_generado(raiz: Path, producto: str) -> dict[str, str]:
    """Archivos generados del harness (ruta relativa -> contenido), salvo GENERADO.json."""
    datos = productos.leer_productos(raiz)[producto]
    activos = [r for r in productos.repos_de(datos) if r.get("estado") == "activo"]
    registro = registro_hallazgos.cargar(raiz, producto)
    archivos = {
        "repos.json": json.dumps({"producto": producto, "repos": [
            {"id": str(r["id"]), "url": str(r["url"]), "rama": str(r["rama"]), "tipo": str(r["tipo"])} for r in activos]},
            indent=2, ensure_ascii=False) + "\n",
        ".cursor/rules/generado/decisiones.mdc": texto_decisiones(raiz, producto),
    }
    for repo in activos:
        archivos[f".cursor/rules/generado/repo-{repo['id']}.mdc"] = texto_repo(raiz, producto, repo, registro)
    return archivos


def huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def escribir_generados(raiz: Path, producto: str) -> list[str]:
    """Escribe lo generado; devuelve las rutas que cambiaron (incluidas las que se borraron)."""
    destino = ruta(raiz, producto)
    archivos = contenido_generado(raiz, producto)
    previo = leer_json(destino / "GENERADO.json", {"version": 0, "archivos": {}})
    cambiados = sorted(r for r, t in archivos.items() if previo["archivos"].get(r) != huella(t))
    sobrantes = sorted(set(previo["archivos"]) - set(archivos))
    for relativa in sobrantes:
        (destino / relativa).unlink(missing_ok=True)
    for relativa, texto in archivos.items():
        (destino / relativa).parent.mkdir(parents=True, exist_ok=True)
        (destino / relativa).write_text(texto, encoding="utf-8")
    if cambiados or sobrantes or not (destino / "GENERADO.json").exists():
        try:
            origen = git("rev-parse", "--short", "HEAD", cwd=raiz)
        except ErrorRadiografia:
            origen = "NO DETERMINADO"
        (destino / "GENERADO.json").write_text(json.dumps({
            "version": previo["version"] + 1, "fecha": date.today().isoformat(), "radiografia": origen,
            "archivos": {r: huella(t) for r, t in sorted(archivos.items())}}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return cambiados + sobrantes


def indices_decisiones(raiz: Path, producto: str) -> None:
    """INDICE.md y COHERENCIA.md de decisiones/ (los escriben adr.py y coherencia.py)."""
    import adr
    import coherencia
    adr.listar(raiz, producto)
    coherencia.generar(raiz, coherencia.ambito_producto(raiz, producto))


# --- Acciones ----------------------------------------------------------------------------------

def commit(destino: Path, mensaje: str, rutas: list[str] | None = None) -> bool:
    git("add", "--all", *(rutas or ["."]), cwd=destino)
    if not git("diff", "--cached", "--name-only", cwd=destino):
        return False
    try:
        git("commit", "--quiet", "-m", mensaje, cwd=destino)
    except ErrorRadiografia as error:
        raise ErrorRadiografia(f"No se pudo hacer commit en {destino}: configurar git (user.name y user.email). Detalle: {error}") from error
    return True


def crear(raiz: Path, producto: str) -> dict:
    datos = productos.leer_productos(raiz).get(producto)
    if datos is None:
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    sigla = sigla_de(raiz, producto)
    if not sigla:
        raise ErrorRadiografia(f"El producto '{producto}' no tiene sigla. Asignarla con: productos.py sigla {producto} --asignar XX")
    destino = ruta(raiz, producto)
    if existe(raiz, producto):
        raise ErrorRadiografia(f"El harness de '{producto}' ya existe en {destino.relative_to(raiz)}.")
    anteriores = raiz / "productos" / producto / "decisiones"
    for origen in sorted(PLANTILLA.rglob("*")):
        if origen.is_dir() or "__pycache__" in origen.parts:
            continue
        relativa = origen.relative_to(PLANTILLA).as_posix()
        if origen.name == "gitignore":  # en la plantilla no lleva punto, para que no la aplique el git de radiografia
            relativa = relativa[: -len("gitignore")] + ".gitignore"
        archivo = destino / relativa
        archivo.parent.mkdir(parents=True, exist_ok=True)
        if origen.suffix in (".md", ".mdc", ".json", "") or origen.name == "Makefile":
            archivo.write_text(origen.read_text(encoding="utf-8").replace("{{producto}}", producto).replace("{{sigla}}", sigla),
                               encoding="utf-8")
        else:
            shutil.copy2(origen, archivo)
    plantilla_adr = (raiz / "equipo" / "plantillas" / "adr.md").read_text(encoding="utf-8")
    (destino / "decisiones" / "plantilla.md").write_text(plantilla_adr.replace("<ÁMBITO>", sigla), encoding="utf-8")
    movidos = []
    if anteriores.exists():
        for adr_anterior in sorted(anteriores.glob("ADR-*.md")):
            shutil.move(str(adr_anterior), destino / "decisiones" / adr_anterior.name)
            movidos.append(adr_anterior.name)
        for generado in ("INDICE.md", "COHERENCIA.md"):
            (anteriores / generado).unlink(missing_ok=True)
        if not any(anteriores.iterdir()):
            anteriores.rmdir()
    git("init", "--quiet", "-b", "main", cwd=destino)
    escribir_generados(raiz, producto)
    indices_decisiones(raiz, producto)
    commit(destino, f"Crea el harness de {producto} desde radiografia")
    return {"ruta": destino, "movidos": movidos}


def traer(raiz: Path, producto: str) -> str:
    destino = ruta(raiz, producto)
    try:
        git("remote", "get-url", "origin", cwd=destino)
    except ErrorRadiografia:
        return "sin remoto: nada que traer"
    if git("status", "--porcelain", cwd=destino):
        return "con cambios sin commit: no se trae nada"
    try:
        git("pull", "--quiet", "--ff-only", cwd=destino)
    except ErrorRadiografia as error:
        return f"NO DETERMINADO - no se pudo traer: {error}"
    return "actualizado"


def generar(raiz: Path, producto: str) -> dict:
    destino = ruta(raiz, producto)
    cambiados = escribir_generados(raiz, producto)
    indices_decisiones(raiz, producto)
    rutas = [r for r in (*GENERADOS, "decisiones/INDICE.md", "decisiones/COHERENCIA.md") if (destino / r).exists()]
    hecho = commit(destino, "Actualiza lo generado desde radiografia", rutas)
    version = leer_json(destino / "GENERADO.json")["version"]
    return {"cambiados": cambiados, "commit": hecho, "version": version}


def guardar(raiz: Path, producto: str, mensaje: str) -> bool:
    destino = ruta(raiz, producto)
    indices_decisiones(raiz, producto)
    return commit(destino, mensaje, ["decisiones/"])


def estado(raiz: Path, producto: str) -> dict:
    destino = ruta(raiz, producto)
    try:
        git("remote", "get-url", "origin", cwd=destino)
        try:
            sin_subir = int(git("rev-list", "--count", "@{u}..HEAD", cwd=destino) or 0)
        except ErrorRadiografia:
            sin_subir = int(git("rev-list", "--count", "HEAD", cwd=destino) or 0)
        remoto = True
    except ErrorRadiografia:
        remoto, sin_subir = False, int(git("rev-list", "--count", "HEAD", cwd=destino) or 0)
    return {"remoto": remoto, "sin_subir": sin_subir, "version": leer_json(destino / "GENERADO.json").get("version"),
            "rama": git("branch", "--show-current", cwd=destino)}


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Harness de cada producto.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("crear")
    p.add_argument("producto")
    for nombre in ("traer", "generar", "estado"):
        p = sub.add_parser(nombre)
        p.add_argument("producto", nargs="?")
    p = sub.add_parser("guardar")
    p.add_argument("producto")
    p.add_argument("--mensaje", required=True)
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    try:
        if o.accion == "crear":
            r = crear(raiz, o.producto)
            relativa = r["ruta"].relative_to(raiz)
            print(f"Harness creado en {relativa} (commit inicial en main).")
            if r["movidos"]:
                print(f"  ADR del producto movidos al harness: {', '.join(r['movidos'])}")
            print(f"  Para subirlo: crear el repositorio harness-{o.producto} en GitLab y ejecutar\n"
                  f"    git -C {relativa} remote add origin <url> && git -C {relativa} push -u origin main")
        elif o.accion == "traer":
            for nombre in con_harness(raiz, o.producto):
                print(f"  harness-{nombre}: {traer(raiz, nombre)}")
        elif o.accion == "generar":
            for nombre in con_harness(raiz, o.producto):
                r = generar(raiz, nombre)
                detalle = f"versión {r['version']}, commit local hecho: {', '.join(r['cambiados']) or 'índices de decisiones'}" \
                    if r["commit"] else "sin cambios"
                print(f"  harness-{nombre}: {detalle}")
        elif o.accion == "guardar":
            print("Commit hecho en decisiones/." if guardar(raiz, o.producto, o.mensaje) else "Sin cambios en decisiones/.")
        elif o.accion == "estado":
            for nombre in con_harness(raiz, o.producto):
                e = estado(raiz, nombre)
                print(f"  harness-{nombre}: versión {e['version']}, rama {e['rama']}, "
                      f"{'remoto configurado' if e['remoto'] else 'sin remoto'}, {e['sin_subir']} commit(s) sin subir")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
