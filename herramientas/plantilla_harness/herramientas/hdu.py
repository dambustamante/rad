"""Tomar una historia de Jira para desarrollarla (/hdu). Solo biblioteca estándar.

Uso:
  python3 herramientas/hdu.py tomar <CLAVE> [--repos a,b] [--sin-rama]

1. Lee la historia de Jira (solo lectura, con JIRA_URL, JIRA_EMAIL y JIRA_TOKEN de .env).
2. Revisa su Medición HU: con un valor aceptado (config.json) se toma; vacía, se toma y queda marcada para
   revisar la deuda que deja; con cualquier otro valor no se toma.
3. Identifica los repositorios que toca (componentes, etiquetas o menciones en la historia, o --repos).
4. Crea la rama de trabajo en cada uno (salvo --sin-rama o cambios sin commit) y deja visibles en Cursor
   solo esos repositorios (.cursorignore).
5. Escribe trabajo/<CLAVE>/contexto.md: historia, criterios de aceptación y lo relacionado de cada
   repositorio (hallazgos abiertos, componentes y terceros, desde contexto.json).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MARCA = ("# hdu:inicio (generado por /hdu; no editar este bloque)", "# hdu:fin")
SEVERIDADES_SIEMPRE = ("bloqueante", "alta")


class ErrorHdu(Exception):
    pass


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin_tildes).strip().lower()


def slug(texto: str, largo: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalizar(texto)).strip("-")[:largo] or "historia"


def leer_json(nombre: str) -> dict:
    return json.loads((RAIZ / nombre).read_text(encoding="utf-8"))


def cargar_env() -> dict[str, str]:
    env = {}
    archivo = RAIZ / ".env"
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                clave, valor = linea.split("=", 1)
                env[clave.strip()] = valor.split(" #")[0].strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith("JIRA_")})
    return env


# --- Jira (solo lectura) -----------------------------------------------------------------------

def pedir(env: dict, ruta: str, parametros: dict | None = None):
    faltantes = [v for v in ("JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN") if not env.get(v)]
    if faltantes:
        raise ErrorHdu(f"Faltan variables de Jira en .env: {', '.join(faltantes)} (ver .env.example).")
    url = env["JIRA_URL"].rstrip("/") + ruta + ("?" + urllib.parse.urlencode(parametros) if parametros else "")
    credencial = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_TOKEN']}".encode()).decode()
    pedido = urllib.request.Request(url, headers={"Authorization": f"Basic {credencial}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=30) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise ErrorHdu("Jira no encontró la historia (o el token no tiene acceso a su proyecto).") from error
        raise ErrorHdu(f"Jira respondió HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise ErrorHdu(f"No se pudo conectar con Jira: {error.reason}") from error


def adf_a_texto(nodo) -> str:
    """Texto de una descripción en formato ADF de Jira, con encabezados y viñetas como líneas."""
    if isinstance(nodo, str):
        return nodo
    if not isinstance(nodo, dict):
        return ""
    tipo, hijos = nodo.get("type"), nodo.get("content") or []
    if tipo == "text":
        return nodo.get("text", "")
    if tipo == "hardBreak":
        return "\n"
    texto = "".join(adf_a_texto(h) for h in hijos)
    if tipo == "listItem":
        return "- " + texto.strip() + "\n"
    if tipo in ("paragraph", "heading", "bulletList", "orderedList", "doc", "blockquote", "codeBlock"):
        return texto.rstrip("\n") + "\n"
    return texto


def valor_campo(valor) -> str | None:
    if valor is None or valor == "" or valor == []:
        return None
    if isinstance(valor, dict):
        return valor.get("value") or valor.get("name") or None
    if isinstance(valor, list):
        return ", ".join(filter(None, (valor_campo(v) for v in valor))) or None
    return str(valor)


def criterios_de(texto: str) -> list[str]:
    """Criterios de aceptación: las líneas que siguen al encabezado 'Criterios de aceptación'."""
    lineas, dentro, criterios = texto.splitlines(), False, []
    for linea in lineas:
        limpia = linea.strip()
        if "criterios de aceptacion" in normalizar(limpia):
            dentro = True
            continue
        if not dentro or not limpia:
            continue
        if limpia.endswith(":") and not limpia.startswith(("-", "*")) and len(limpia) < 60:
            break  # otro encabezado
        if re.match(r"^([-*•]|\d+[.)])\s+", limpia) or re.match(r"^(dado|cuando|entonces|y)\b", normalizar(limpia)):
            criterios.append(re.sub(r"^([-*•]|\d+[.)])\s+", "", limpia))
    return criterios


def leer_historia(clave: str, env: dict, config: dict) -> dict:
    campos = pedir(env, "/rest/api/3/field")
    por_nombre = {normalizar(c.get("name", "")): c["id"] for c in campos}
    id_medicion = por_nombre.get(normalizar(config["jira"]["campo_medicion"]))
    id_tipo = por_nombre.get(normalizar(config["jira"]["campo_tipo"]))
    pedidos = ["summary", "description", "issuetype", "status", "labels", "components", id_medicion, id_tipo]
    datos = pedir(env, f"/rest/api/3/issue/{urllib.parse.quote(clave)}", {"fields": ",".join(filter(None, pedidos))})
    f = datos.get("fields") or {}
    descripcion = adf_a_texto(f.get("description")) if f.get("description") else ""
    return {
        "clave": clave, "titulo": f.get("summary") or "", "descripcion": descripcion,
        "tipo_incidencia": valor_campo(f.get("issuetype")), "tipo": valor_campo(f.get(id_tipo)) if id_tipo else None,
        "estado": valor_campo(f.get("status")),
        "medicion": valor_campo(f.get(id_medicion)) if id_medicion else None, "campo_medicion_existe": bool(id_medicion),
        "etiquetas": f.get("labels") or [], "componentes": [c.get("name", "") for c in f.get("components") or []],
        "criterios": criterios_de(descripcion), "url": env["JIRA_URL"].rstrip("/") + f"/browse/{clave}",
    }


# --- Decisiones sin IA -------------------------------------------------------------------------

def evaluar_medicion(valor: str | None, aceptados: list[str]) -> str:
    if not valor:
        return "sin medir"
    return "aceptada" if normalizar(valor) in {normalizar(a) for a in aceptados} else "rechazada"


def inferir_repos(historia: dict, ids: list[str]) -> list[str]:
    fuentes = " ".join([*historia["componentes"], *historia["etiquetas"], historia["titulo"], historia["descripcion"]])
    texto = " " + re.sub(r"[^a-z0-9]+", " ", normalizar(fuentes)) + " "
    return [i for i in ids if f" {re.sub(r'[^a-z0-9]+', ' ', normalizar(i)).strip()} " in texto]


def palabras(texto: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{4,}", normalizar(texto)))


def relacionado(historia: dict, contexto: dict, repos: list[str]) -> dict[str, dict]:
    """Por repositorio: hallazgos bloqueantes o altos, y los que comparten palabras con la historia; terceros."""
    claves = palabras(" ".join([historia["titulo"], historia["descripcion"], *historia["criterios"]]))
    resultado = {}
    for repo in repos:
        datos = contexto.get(repo, {})
        hallazgos = [h for h in datos.get("hallazgos", [])
                     if h["severidad"] in SEVERIDADES_SIEMPRE or len(claves & palabras(h["titulo"])) >= 1]
        terceros = [t for t in datos.get("terceros", [])
                    if palabras(f"{t['id']} {t.get('nombre') or ''}") & claves] or datos.get("terceros", [])
        resultado[repo] = {"hallazgos": hallazgos, "terceros": terceros, "componentes": datos.get("componentes", [])}
    return resultado


# --- Espacio de trabajo ------------------------------------------------------------------------

def git(*argumentos: str, cwd: Path) -> tuple[int, str]:
    r = subprocess.run(["git", *argumentos], cwd=cwd, capture_output=True, text=True)
    return r.returncode, (r.stdout or r.stderr).strip()


def foco(visibles: list[str] | None, todos: list[str]) -> None:
    """Deja visibles en Cursor solo los repositorios indicados (None: todos)."""
    archivo = RAIZ / ".cursorignore"
    texto = archivo.read_text(encoding="utf-8") if archivo.exists() else ""
    texto = re.sub(rf"{re.escape(MARCA[0])}.*?{re.escape(MARCA[1])}\n?", "", texto, flags=re.DOTALL)
    ocultos = [r for r in todos if visibles is not None and r not in visibles]
    if ocultos:
        texto = texto.rstrip("\n") + ("\n" if texto.strip() else "") + "\n".join([MARCA[0], *[f"code/{r}/" for r in ocultos], MARCA[1]]) + "\n"
    if texto.strip():
        archivo.write_text(texto.lstrip("\n"), encoding="utf-8")
    else:
        archivo.unlink(missing_ok=True)


def preparar_rama(repo: dict, nombre: str) -> str:
    destino = RAIZ / "code" / repo["id"]
    if not (destino / ".git").exists():
        return "sin copia en code/ (ejecutar make code)"
    _, cambios = git("status", "--porcelain", cwd=destino)
    if cambios:
        return "tiene cambios sin commit: no se cambió de rama"
    git("fetch", "--quiet", "origin", cwd=destino)
    if git("rev-parse", "--verify", "--quiet", nombre, cwd=destino)[0] == 0:
        codigo, salida = git("switch", "--quiet", nombre, cwd=destino)
        return f"rama {nombre} (ya existía)" if codigo == 0 else f"ERROR: {salida}"
    codigo, salida = git("switch", "--quiet", "-c", nombre, f"origin/{repo['rama']}", cwd=destino)
    return f"rama {nombre} creada desde origin/{repo['rama']}" if codigo == 0 else f"ERROR: {salida}"


def escribir_contexto(historia: dict, medicion: str, repos: list[str], ramas: dict[str, str], relacion: dict) -> Path:
    carpeta = RAIZ / "trabajo" / historia["clave"]
    carpeta.mkdir(parents=True, exist_ok=True)
    lineas = [f"# {historia['clave']}: {historia['titulo']}", "",
              f"- [Jira]({historia['url']}) · {historia['tipo_incidencia'] or 'tipo NO DETERMINADO'}"
              + (f" · Tipo: {historia['tipo']}" if historia["tipo"] else "") + f" · Estado: {historia['estado']}",
              f"- Medición HU: {historia['medicion'] or 'vacía'} ({medicion})",
              f"- Repositorios: {', '.join(repos) or 'NO DETERMINADO'}", ""]
    if medicion == "sin medir":
        lineas += ["> HU sin medir: al terminar, `/listo` exige revisar la deuda técnica y operativa que deja.", ""]
    lineas += ["## Criterios de aceptación", ""]
    lineas += [f"{i}. {c}" for i, c in enumerate(historia["criterios"], start=1)] or \
        ["NO DETERMINADO: la historia no tiene una sección de criterios de aceptación reconocible."]
    lineas += ["", "## Descripción", "", historia["descripcion"].strip() or "(vacía)", ""]
    for repo in repos:
        datos = relacion.get(repo, {})
        lineas += [f"## {repo}", "", f"- {ramas.get(repo, 'sin rama')}"]
        if datos.get("terceros"):
            lineas += [f"- Tercero `{t['id']}`: p95 {t.get('p95_ms') or '—'} ms, política ante falla {t.get('politica_ante_falla')}"
                       for t in datos["terceros"]]
        if datos.get("componentes"):
            lineas.append("- Componentes: " + ", ".join(f"{c['nombre']} ({c['tipo']}, {c['tecnologia']})" for c in datos["componentes"]))
        lineas += ["", "Hallazgos abiertos relacionados (corregirlos si se toca ese código):", ""]
        lineas += [f"- {h['id']} · {h['criterio']} · {h['severidad']}: {h['titulo']} · {', '.join(h['evidencia'])}"
                   for h in datos.get("hallazgos", [])] or ["Ninguno."]
        lineas.append("")
    if normalizar(historia["tipo_incidencia"] or "") == "spike":
        lineas += ["## Entregable del Spike", "", "Un ADR del producto en estado Propuesto: "
                   "`python3 herramientas/harness.py adr --titulo \"<decisión>\" --historia " + historia["clave"] + "`.", ""]
    archivo = carpeta / "contexto.md"
    archivo.write_text("\n".join(lineas), encoding="utf-8")
    (carpeta / "hdu.json").write_text(json.dumps({"clave": historia["clave"], "titulo": historia["titulo"],
                                                  "medicion": historia["medicion"], "evaluacion_medicion": medicion,
                                                  "repos": repos, "ramas": ramas, "fecha": date.today().isoformat(),
                                                  "criterios": historia["criterios"]}, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    return archivo


def tomar(clave: str, repos_pedidos: list[str] | None, crear_rama: bool) -> dict:
    config, repos_config = leer_json("config.json"), leer_json("repos.json")["repos"]
    ids = [r["id"] for r in repos_config]
    historia = leer_historia(clave, cargar_env(), config)
    medicion = evaluar_medicion(historia["medicion"], config["jira"]["medicion_aceptada"])
    if medicion == "rechazada":
        return {"historia": historia, "medicion": medicion, "tomada": False}
    desconocidos = [r for r in repos_pedidos or [] if r not in ids]
    if desconocidos:
        raise ErrorHdu(f"Repositorios que no son del producto: {', '.join(desconocidos)}. Disponibles: {', '.join(ids)}.")
    repos = repos_pedidos or inferir_repos(historia, ids)
    if not repos:
        return {"historia": historia, "medicion": medicion, "tomada": False, "faltan_repos": ids}
    nombre_rama = f"feature/{clave}-{slug(historia['titulo'])}"
    ramas = {r["id"]: (preparar_rama(r, nombre_rama) if crear_rama else "sin cambio de rama (--sin-rama)")
             for r in repos_config if r["id"] in repos}
    foco(repos, ids)
    contexto = json.loads((RAIZ / "contexto.json").read_text(encoding="utf-8")) if (RAIZ / "contexto.json").exists() else {}
    archivo = escribir_contexto(historia, medicion, repos, ramas, relacionado(historia, contexto, repos))
    return {"historia": historia, "medicion": medicion, "tomada": True, "repos": repos, "ramas": ramas, "contexto": archivo}


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tomar una historia de Jira (/hdu).")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("tomar")
    p.add_argument("clave")
    p.add_argument("--repos", default="")
    p.add_argument("--sin-rama", action="store_true")
    o = parser.parse_args(argumentos)
    try:
        r = tomar(o.clave.upper(), [x.strip() for x in o.repos.split(",") if x.strip()] or None, not o.sin_rama)
    except ErrorHdu as error:
        print(f"ERROR: {error}")
        return 1
    h = r["historia"]
    print(f"{h['clave']}: {h['titulo']} · Medición HU: {h['medicion'] or 'vacía'} ({r['medicion']})")
    if r["medicion"] == "rechazada":
        print(f"No se toma: la Medición HU debe ser una de las aceptadas. Pedir al PO que complete la historia "
              f"(criterios de aceptación medibles, Como/Quiero/Para) y que se vuelva a medir.")
        return 2
    if not h["campo_medicion_existe"]:
        print("Aviso: no se encontró el campo de Medición HU en Jira (revisar config.json).")
    if r.get("faltan_repos") is not None:
        print(f"No se pudo saber qué repositorios toca. Indicarlos con --repos (disponibles: {', '.join(r['faltan_repos'])}).")
        return 3
    for repo, estado in r["ramas"].items():
        print(f"  {repo}: {estado}")
    print(f"Criterios de aceptación: {len(h['criterios'])}. Contexto: {r['contexto'].relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
