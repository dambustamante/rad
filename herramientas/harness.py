"""Harness de cada producto (harness-<producto>): lo crea y lo mantiene radiografia.

Uso:
  python herramientas/harness.py crear <producto>
  python herramientas/harness.py traer [<producto>]       git pull de la copia local (antes de la coherencia)
  python herramientas/harness.py generar [<producto>]     regenera lo generado y hace commit si cambió
  python herramientas/harness.py guardar <producto> --mensaje TEXTO   commit de los ADR de decisiones/
  python herramientas/harness.py subir [<producto>] [--confirmar]   vista previa o push de lo generado
  python herramientas/harness.py estado [<producto>]

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

La copia de radiografia vive en productos/<producto>/harness/ (fuera de git de radiografia) y es un repositorio
propio. radiografia escribe ahí y hace commit; el push se hace solo con `subir --confirmar`. Dueños de cada parte:

- generado por radiografia (se regenera; no se edita): .cursor/rules/generado/, .cursor/arquitectura/,
  arquitectura.json, repos.json, GENERADO.json,
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
import coherencia as coherencia_decisiones
from coherencia import leer_arquitectura_vigente, leer_decisiones_producto, sigla_de, suspendidos as criterios_suspendidos
from comun import RAIZ, ErrorRadiografia, git, leer_json, normalizar
from revisar import decisiones_con_criterios

PLANTILLA = Path(__file__).resolve().parent / "plantilla_harness"
GENERADOS = ("repos.json", "config.json", "contexto.json", "lenguaje.json", "GENERADO.json", "arquitectura.json",
             ".cursor/rules/generado/", ".cursor/arquitectura/")
MAXIMO_HALLAZGOS = 15
LARGO_RESUMEN = 700
LIMITE_REGLAS_SIEMPRE = 1500  # palabras: decisiones.mdc se paga en cada mensaje
MAXIMO_EXTRACTO = 1500
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

def decisiones_del_producto(raiz: Path, producto: str) -> tuple[list[tuple[str, dict[str, dict]]], list[dict]]:
    todas = leer_decisiones_producto(raiz, producto)
    grupos = [("Equipo", decisiones_con_criterios(raiz)),
              ("Producto", {k: v for k, v in todas.items() if v["tipo"] == "decision" and v["evaluado"]})]
    excepciones = [d for d in todas.values() if d["tipo"] == "excepcion" and normalizar(d["estado"]) == "aprobado"]
    return grupos, excepciones


def texto_decisiones(raiz: Path, producto: str) -> str:
    """Regla que se aplica siempre: la regla rápida de cada documento y decisión, sin sus criterios."""
    lineas = ["---", f"description: Reglas rápidas que {producto} debe cumplir (generado por radiografia; no se edita)",
              "alwaysApply: true", "---", "", f"# Reglas de {producto}", "",
              "Generado por radiografia: no se edita. Las decisiones en `propuesta` todavía se están calibrando: "
              "conviene cumplirlas, pero no bloquean el MR. Los criterios de cada una se cargan al trabajar en `code/` "
              "(`.cursor/rules/generado/criterios.mdc`).", "", "## Arquitectura (obligatorio)", "",
              "/hdu trae los extractos relacionados con la historia. Si una regla toca el cambio y no está en el contexto, "
              "leer `.cursor/arquitectura/<clave>.md` (los `:` de la clave se escriben `--`).", ""]
    lineas += [f"- `{clave}` {PREFIJO_ID.sub('', d['titulo'])}: {d['regla_rapida'] or 'ver el documento'}"
               for clave, d in sorted(leer_arquitectura_vigente(raiz).items())] or ["Sin documentos de arquitectura vigentes."]
    grupos, excepciones = decisiones_del_producto(raiz, producto)
    for titulo, decisiones in grupos:
        lineas += ["", f"## {titulo}", ""]
        lineas += [f"- `{i}` {d['titulo']}" + (" (propuesta)" if normalizar(d["estado"]) == "propuesto" else "") + f": {d['regla_rapida'] or '—'}"
                   for i, d in decisiones.items()] or ["Sin decisiones vigentes."]
    if excepciones:
        lineas += ["", "## Excepciones aprobadas", ""]
        lineas += [f"- {d['id']}: {d['titulo']} (exceptúa {d['campos'].get('criterios exceptuados', '—')}; "
                   f"repositorios {d['campos'].get('repositorios', 'todos')}; vence {d['campos'].get('vence', '—')})" for d in excepciones]
    return "\n".join(lineas).rstrip() + "\n"


def texto_criterios(raiz: Path, producto: str) -> str:
    """Regla que se aplica al trabajar en code/: los criterios que el código debe cumplir."""
    from verificaciones import leer_criterios
    suspendidos = criterios_suspendidos(raiz, producto)
    lineas = ["---", f"description: Criterios que el código de {producto} debe cumplir (generado por radiografia; no se edita)",
              'globs: code/**', "alwaysApply: false", "---", "", "# Criterios que el código debe cumplir"]
    for titulo, decisiones in decisiones_del_producto(raiz, producto)[0]:
        lineas += ["", f"## {titulo}"]
        for id_decision, d in decisiones.items():
            tabla = d.get("tabla") or leer_criterios(d["texto"])
            if any(termino in criterio["como"].lower() for criterio in tabla.values() for termino in FORMA_DE_TRABAJAR):
                continue  # decisiones sobre la forma de trabajar (historias, MR): basta la regla rápida
            criterios = [f"- `{i}` ({c['severidad']}): {c['texto']}" for i, c in tabla.items()
                         if i not in suspendidos.get(id_decision, []) and c["como"] in COMO_CODIGO]
            lineas += ["", f"### {id_decision} {d['titulo']}", *criterios] if criterios else []
    return "\n".join(lineas).rstrip() + "\n"


def seccion_asis(texto: str, nombre: str) -> str:
    coincidencia = re.search(rf"^## {re.escape(nombre)}\s*\n(.*?)(?=^## |\Z)", texto, re.MULTILINE | re.DOTALL)
    resumen = " ".join(coincidencia.group(1).split()) if coincidencia else ""
    return (resumen[:LARGO_RESUMEN] + "…") if len(resumen) > LARGO_RESUMEN else resumen


def archivo_arquitectura(clave: str) -> str:
    return f".cursor/arquitectura/{re.sub(r'[^A-Za-z0-9._-]+', '--', clave)}.md"


def extracto_arquitectura(raiz: Path, clave: str, documento: dict) -> str:
    """Decisión, regla rápida y criterios, con un máximo de caracteres; sin esas secciones, solo los títulos."""
    texto = coherencia_decisiones.extracto(raiz, clave).replace(f" ({documento['archivo']})", "")
    if "(sin secciones" in texto:
        titulos = [l for l in documento["texto"].splitlines() if l.startswith("#")]
        texto = "\n".join([f"# {clave}: {documento['titulo']}", "Sin secciones Decisión, Regla rápida ni Criterios. Títulos:", *titulos])
    if len(texto) > MAXIMO_EXTRACTO:
        texto = texto[:MAXIMO_EXTRACTO].rstrip() + " […]"
    return texto


def indice_arquitectura(raiz: Path, vigentes: dict[str, dict]) -> str:
    """Lo que /hdu cruza con la historia, y los commits de arquitectura con los que se generó."""
    fuentes = leer_json(raiz / "arquitectura" / "estado" / "fuentes.lock")
    return json.dumps({
        "fuentes": {f: {"url": d["url"], "ref": d["ref"], "commit": d["commit"]} for f, d in sorted(fuentes.items())},
        "documentos": [{"clave": c, "titulo": d["titulo"], "regla_rapida": d["regla_rapida"], "archivo": archivo_arquitectura(c),
                        "extracto": extracto_arquitectura(raiz, c, d)} for c, d in sorted(vigentes.items())]},
        indent=2, ensure_ascii=False) + "\n"


def sin_regla_rapida(raiz: Path) -> list[str]:
    return sorted(c for c, d in leer_arquitectura_vigente(raiz).items() if not d["regla_rapida"])


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
        ".cursor/rules/generado/criterios.mdc": texto_criterios(raiz, producto),
    }
    vigentes = leer_arquitectura_vigente(raiz)
    archivos["arquitectura.json"] = indice_arquitectura(raiz, vigentes)
    archivos.update({archivo_arquitectura(c): d["texto"] for c, d in vigentes.items()})
    for repo in activos:
        archivos[f".cursor/rules/generado/repo-{repo['id']}.mdc"] = texto_repo(raiz, producto, repo, registro)
    from jira import config_jira
    jira = config_jira(raiz)
    archivos["config.json"] = json.dumps({
        "producto": producto, "sigla": sigla_de(raiz, producto),
        "jira": {"campo_medicion": jira["campo_medicion"], "medicion_aceptada": jira["medicion_aceptada"],
                 "campo_tipo": jira["campo_tipo"], "campo_equipos": jira["campo_equipos"], "equipos": jira["equipos"],
                 "tipos_incidencia": jira["tipos_incidencia"], "tipo_tarea_desarrollo": jira["tipo_tarea_desarrollo"],
                 **destino_o_nada(raiz, producto)}}, indent=2, ensure_ascii=False) + "\n"
    import lenguaje
    reglas = lenguaje.cargar_reglas(raiz)
    archivos["lenguaje.json"] = json.dumps({"voseo": reglas["voseo"], "expresiones": [e["texto"] for e in reglas["expresiones"]]},
                                           indent=2, ensure_ascii=False) + "\n"
    archivos["contexto.json"] = json.dumps(contexto_estructurado(raiz, producto, activos, registro), indent=2,
                                           ensure_ascii=False, sort_keys=True) + "\n"
    return archivos


def destino_o_nada(raiz: Path, producto: str) -> dict:
    """Espacio y etiqueta de Jira del producto, si está configurado."""
    from jira import destino_jira
    try:
        return destino_jira(raiz, producto)
    except ErrorRadiografia:
        return {}


def contexto_estructurado(raiz: Path, producto: str, activos: list[dict], registro: dict) -> dict:
    """Lo que /hdu cruza con la historia, sin IA: hallazgos abiertos, componentes y terceros de cada repositorio."""
    import revision
    resultado = {}
    for repo in activos:
        id_repo = str(repo["id"])
        codigo = (registro.get("repos", {}).get(id_repo) or {}).get("codigo")
        componentes = revision.leer_trabajo(raiz, producto, codigo["id"], id_repo).get("componentes", []) if codigo else []
        resultado[id_repo] = {
            "hallazgos": [{"id": h["id"], "criterio": h["criterio"] or h["fuente"], "severidad": h["severidad"], "titulo": h["titulo"],
                           "evidencia": [f"{e['archivo']}:{e['linea']}" if e.get("linea") else e["archivo"] for e in h["evidencia"][:2]]}
                          for h in sorted(registro["hallazgos"].values(), key=lambda h: h["id"])
                          if h["repo"] == id_repo and h["rama"] == repo["rama"] and h["estado"] == "abierto"
                          and not h.get("absorbido_por") and (h.get("triaje") or {}).get("decision") != "falso-positivo"],
            "componentes": [{"nombre": c["nombre"], "tipo": c["tipo"], "tecnologia": c["tecnologia"], "tercero": c["tercero"]}
                            for c in componentes],
            "terceros": [{"id": f["id"], "nombre": f.get("nombre"), "p95_ms": (f.get("sla") or {}).get("p95_ms"),
                          "politica_ante_falla": f.get("politica_ante_falla")} for f in terceros.para_repo(raiz, producto, id_repo)],
        }
    return resultado


def huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def escribir_generados(raiz: Path, producto: str, plantilla: dict[str, str] | None = None) -> list[str]:
    """Escribe lo generado; devuelve las rutas que cambiaron (incluidas las que se borraron).

    `plantilla` son las huellas de los archivos del equipo tal como los entregó la plantilla.
    """
    destino = ruta(raiz, producto)
    archivos = contenido_generado(raiz, producto)
    previo = leer_json(destino / "GENERADO.json", {"version": 0, "archivos": {}, "plantilla": {}})
    plantilla = previo.get("plantilla", {}) if plantilla is None else plantilla
    cambiados = sorted(r for r, t in archivos.items() if previo["archivos"].get(r) != huella(t))
    sobrantes = sorted(set(previo["archivos"]) - set(archivos))
    for relativa in sobrantes:
        (destino / relativa).unlink(missing_ok=True)
    for relativa, texto in archivos.items():
        (destino / relativa).parent.mkdir(parents=True, exist_ok=True)
        (destino / relativa).write_text(texto, encoding="utf-8")
    if cambiados or sobrantes or plantilla != previo.get("plantilla", {}) or not (destino / "GENERADO.json").exists():
        try:
            origen = git("rev-parse", "--short", "HEAD", cwd=raiz)
        except ErrorRadiografia:
            origen = "NO DETERMINADO"
        (destino / "GENERADO.json").write_text(json.dumps({
            "version": previo["version"] + 1, "fecha": date.today().isoformat(), "radiografia": origen,
            "archivos": {r: huella(t) for r, t in sorted(archivos.items())},
            "plantilla": dict(sorted(plantilla.items()))}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return cambiados + sobrantes


def indices_decisiones(raiz: Path, producto: str) -> None:
    """INDICE.md y COHERENCIA.md de decisiones/ (los escriben adr.py y coherencia.py)."""
    import adr
    import coherencia
    adr.listar(raiz, producto)
    coherencia.generar(raiz, coherencia.ambito_producto(raiz, producto))


# --- Plantilla (archivos del equipo) -----------------------------------------------------------

def plantilla_adr(raiz: Path, sigla: str) -> str:
    """Plantilla de ADR del producto, con la sigla y sin las notas que solo sirven para elegir el ámbito."""
    texto = (raiz / "equipo" / "plantillas" / "adr.md").read_text(encoding="utf-8")
    texto = re.sub(r"\n> `<ÁMBITO>`:.*\n", "\n", texto, count=1).replace("<ÁMBITO>", sigla)
    texto = texto.replace(f"| `{sigla}-NNN.1` | | `automática` \\| `revisión de código` |", f"| `{sigla}-NNN.1` | | revisión de código |")
    return texto.replace(" (solo ADR de producto; en un ADR-EQ se elimina)", "")


def plantilla_renderizada(raiz: Path, producto: str) -> dict[str, str]:
    """Archivos del equipo tal como los entrega la plantilla (ruta relativa -> contenido)."""
    sigla = sigla_de(raiz, producto) or "XX"
    archivos = {}
    for origen in sorted(PLANTILLA.rglob("*")):
        if origen.is_dir() or "__pycache__" in origen.parts:
            continue
        relativa = origen.relative_to(PLANTILLA).as_posix()
        if origen.name in ("gitignore", "env.example"):  # en la plantilla no llevan punto: no los aplica radiografia
            relativa = relativa[: -len(origen.name)] + "." + origen.name
        archivos[relativa] = origen.read_text(encoding="utf-8").replace("{{producto}}", producto).replace("{{sigla}}", sigla)
    archivos["decisiones/plantilla.md"] = plantilla_adr(raiz, sigla)
    return archivos


def sincronizar_plantilla(raiz: Path, producto: str) -> tuple[dict[str, str], list[str], list[str]]:
    """Agrega los archivos nuevos de la plantilla y detecta los que cambiaron en la plantilla.

    Nunca pisa un archivo del equipo: si la plantilla cambió un archivo que el harness ya tiene, solo avisa
    (una vez) para llevar el cambio por MR. Devuelve (huellas de la plantilla, agregados, avisos).
    """
    destino = ruta(raiz, producto)
    previas = leer_json(destino / "GENERADO.json").get("plantilla", {})
    huellas, agregados, avisos = dict(previas), [], []
    for relativa, texto in plantilla_renderizada(raiz, producto).items():
        archivo = destino / relativa
        if not archivo.exists():
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text(texto, encoding="utf-8")
            agregados.append(relativa)
        elif relativa in previas and previas[relativa] != huella(texto):
            avisos.append(relativa)
        huellas[relativa] = huella(texto)
    return huellas, agregados, avisos


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
    plantilla = plantilla_renderizada(raiz, producto)
    for relativa, texto in plantilla.items():
        (destino / relativa).parent.mkdir(parents=True, exist_ok=True)
        (destino / relativa).write_text(texto, encoding="utf-8")
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
    escribir_generados(raiz, producto, {r: huella(x) for r, x in plantilla.items()})
    indices_decisiones(raiz, producto)
    commit(destino, f"chore: crea el harness de {producto} desde radiografia")
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
    huellas, agregados, avisos = sincronizar_plantilla(raiz, producto)
    cambiados = escribir_generados(raiz, producto, huellas)
    indices_decisiones(raiz, producto)
    rutas = [r for r in (*GENERADOS, *agregados, "decisiones/INDICE.md", "decisiones/COHERENCIA.md") if (destino / r).exists()]
    hecho = commit(destino, "chore: actualiza lo generado desde radiografia", rutas)
    version = leer_json(destino / "GENERADO.json")["version"]
    return {"cambiados": cambiados + agregados, "commit": hecho, "version": version, "avisos": avisos}


def pares_pendientes(raiz: Path, producto: str) -> int:
    return sum(coherencia_decisiones.preparar(ambito)["total_pares"]
               for ambito in (coherencia_decisiones.ambito_equipo(raiz), coherencia_decisiones.ambito_producto(raiz, producto)))


def subir(raiz: Path, producto: str, confirmar: bool) -> dict:
    """Trae, regenera y muestra (o sube, con confirmación) lo que falta. Retiene el harness con coherencia pendiente."""
    destino = ruta(raiz, producto)
    traido = traer(raiz, producto)
    if traido != "actualizado":
        return {"resultado": "bloqueado", "detalle": traido}
    pendientes = pares_pendientes(raiz, producto)
    if pendientes:
        return {"resultado": "retenido", "detalle": f"{pendientes} par(es) de coherencia por evaluar: evaluarlos con /actualizar antes de subir"}
    generar(raiz, producto)
    e = estado(raiz, producto)
    if not e["sin_subir"]:
        return {"resultado": "al dia", "detalle": f"versión {e['version']}"}
    if e["rama"] not in ("main", "master"):
        return {"resultado": "bloqueado", "detalle": f"la copia está en la rama {e['rama']}: se sube solo desde la rama principal"}
    try:
        cambios = git("diff", "--stat", "@{u}..HEAD", cwd=destino)
    except ErrorRadiografia:
        cambios = "primer push: todo el repositorio"
    if not confirmar:
        return {"resultado": "por subir", "detalle": f"versión {e['version']}, {e['sin_subir']} commit(s)\n{cambios}"}
    try:
        git("push", "--quiet", "-u", "origin", "HEAD", cwd=destino)
    except ErrorRadiografia as error:
        return {"resultado": "bloqueado", "detalle": f"el push falló: {error}"}
    return {"resultado": "subido", "detalle": f"versión {e['version']}, {e['sin_subir']} commit(s)"}


def guardar(raiz: Path, producto: str, mensaje: str) -> bool:
    destino = ruta(raiz, producto)
    indices_decisiones(raiz, producto)
    return commit(destino, mensaje, ["decisiones/", *(["documentos/"] if (destino / "documentos").exists() else [])])


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
    p = sub.add_parser("subir")
    p.add_argument("producto", nargs="?")
    p.add_argument("--confirmar", action="store_true", help="hace el push; sin esto solo muestra la vista previa")
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
            distintos = {nombre: r for nombre in con_harness(raiz, o.producto) if (r := traer(raiz, nombre)) != "actualizado"}
            for nombre, r in distintos.items():
                print(f"  harness-{nombre}: {r}")
            if not distintos:
                print("Harness: al día con su remoto.")
        elif o.accion == "generar":
            hubo_cambios = False
            for nombre in con_harness(raiz, o.producto):
                r = generar(raiz, nombre)
                if r["commit"]:
                    hubo_cambios = True
                    cambiados = r["cambiados"]
                    print(f"  harness-{nombre}: versión {r['version']}, commit local: {len(cambiados)} archivo(s)")
                for aviso in r["avisos"]:
                    print(f"    La plantilla cambió {aviso}: revisar si el cambio se lleva al harness (por MR).")
            if not hubo_cambios:
                print("Harness: sin cambios generados.")
            for nombre in con_harness(raiz, o.producto):
                palabras = len(texto_decisiones(raiz, nombre).split())
                if palabras > LIMITE_REGLAS_SIEMPRE:
                    print(f"  harness-{nombre}: decisiones.mdc tiene {palabras} palabras y se carga en cada mensaje: acortar las reglas rápidas.")
            faltantes = sin_regla_rapida(raiz)
            if faltantes:
                print(f"  Documentos de arquitectura vigentes sin regla rápida: {', '.join(faltantes)}")
        elif o.accion == "subir":
            resultados = {nombre: subir(raiz, nombre, o.confirmar) for nombre in con_harness(raiz, o.producto)}
            for nombre, r in resultados.items():
                if r["resultado"] != "al dia":
                    print(f"  harness-{nombre}: {r['resultado']} ({r['detalle']})")
            if all(r["resultado"] == "al dia" for r in resultados.values()):
                print("Harness: nada por subir.")
            if any(r["resultado"] in ("bloqueado", "retenido") for r in resultados.values()):
                return 1
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
