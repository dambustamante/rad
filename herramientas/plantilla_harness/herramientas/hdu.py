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
MAXIMO_DOCUMENTOS = 3
COINCIDENCIAS_MINIMAS = 2
ESPERA_ARQUITECTURA = 15
RAMA_PRINCIPAL = "main"
SECCIONES_SPEC = ("Objetivo", "Criterios de aceptación", "Diseño", "Pruebas", "Reglas que aplican", "Fuera de alcance")
PENDIENTE_SPEC = "<completar"
MAXIMO_LINEAS_SPEC = 80
TIPOS_CAMBIO = ("feat", "fix", "docs", "chore", "test", "refactor")
RAMA_VALIDA = re.compile(rf"^({'|'.join(TIPOS_CAMBIO)})/[A-Za-z0-9][A-Za-z0-9._-]*$")
COMMIT_VALIDO = re.compile(rf"^({'|'.join(TIPOS_CAMBIO)})(\([\w./-]+\))?!?: \S")
TIPO_RAMA = {"error": "fix", "hotfix": "fix", "tarea": "chore"}


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


def arquitectura_relacionada(historia: dict, relacion: dict) -> list[dict]:
    """Hasta MAXIMO_DOCUMENTOS documentos de arquitectura que comparten más palabras con la historia y sus tecnologías."""
    archivo = RAIZ / "arquitectura.json"
    documentos = json.loads(archivo.read_text(encoding="utf-8")).get("documentos", []) if archivo.exists() else []
    tecnologias = [c["tecnologia"] or "" for datos in relacion.values() for c in datos["componentes"]]
    claves = palabras(" ".join([historia["titulo"], historia["descripcion"], *historia["criterios"], *tecnologias]))
    puntajes = [(len(claves & palabras(f"{d['titulo']} {d['regla_rapida'] or ''}")), d["clave"], d) for d in documentos]
    elegidos = sorted((p for p in puntajes if p[0] >= COINCIDENCIAS_MINIMAS), key=lambda p: (-p[0], p[1]))
    return [d for _, _, d in elegidos[:MAXIMO_DOCUMENTOS]]


# --- Espacio de trabajo ------------------------------------------------------------------------

def git(*argumentos: str, cwd: Path) -> tuple[int, str]:
    r = subprocess.run(["git", *argumentos], cwd=cwd, capture_output=True, text=True)
    return r.returncode, (r.stdout or r.stderr).strip()


def actualizar_harness() -> str:
    """Trae las reglas vigentes antes de trabajar; sin ellas no se sigue."""
    if git("remote", "get-url", "origin", cwd=RAIZ)[0] != 0:
        return "sin remoto"
    codigo, salida = git("pull", "--quiet", "--ff-only", cwd=RAIZ)
    if codigo != 0:
        raise ErrorHdu(f"No se pudo actualizar el harness: {salida}. Dejarlo en su rama principal, sin cambios en conflicto, y repetir.")
    return "actualizado"


def version_harness() -> int | str:
    archivo = RAIZ / "GENERADO.json"
    return json.loads(archivo.read_text(encoding="utf-8")).get("version", "NO DETERMINADO") if archivo.exists() else "NO DETERMINADO"


def commit_remoto(url: str, ref: str) -> str | None:
    entorno = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        r = subprocess.run(["git", "ls-remote", url, ref, f"{ref}^{{}}"], capture_output=True, text=True,
                           timeout=ESPERA_ARQUITECTURA, env=entorno, cwd=RAIZ)
    except subprocess.TimeoutExpired:
        return None
    referencias = {l.split("\t")[1]: l.split("\t")[0] for l in r.stdout.splitlines() if "\t" in l} if r.returncode == 0 else {}
    for candidata in (f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}", f"refs/heads/{ref}", ref):
        if candidata in referencias:
            return referencias[candidata]
    return None


def avisos_arquitectura() -> list[str]:
    """Fuentes de arquitectura con commits que todavía no llegaron a este harness."""
    archivo = RAIZ / "arquitectura.json"
    fuentes = json.loads(archivo.read_text(encoding="utf-8")).get("fuentes", {}) if archivo.exists() else {}
    avisos = []
    for nombre, fuente in fuentes.items():
        remoto = commit_remoto(re.sub(r"//[^/@]+@", "//", fuente["url"]), fuente["ref"])
        if remoto is None:
            avisos.append(f"Arquitectura `{nombre}`: NO DETERMINADO - no se pudo consultar la fuente.")
        elif remoto != fuente["commit"]:
            avisos.append(f"Arquitectura `{nombre}` tiene commits que no llegaron a este harness: pueden faltar reglas nuevas.")
    return avisos


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


# --- Spec --------------------------------------------------------------------------------------

def tipo_historia(tipo_incidencia: str | None) -> str:
    return normalizar(tipo_incidencia or "")


def rama_spec(clave: str) -> str:
    return f"docs/{clave}-spec"


def avisos_convencion(rama: str, mensajes: list[str]) -> list[str]:
    """Rama y commits que no siguen ADR-EQ-010."""
    avisos = [f"La rama `{rama}` no sigue `<tipo>/<CLAVE>-<descripción>` (EQ-010.1)."] if not RAMA_VALIDA.match(rama) else []
    return avisos + [f"El commit «{m}» no sigue Conventional Commits (EQ-010.2)." for m in mensajes if not COMMIT_VALIDO.match(m)]


def ruta_spec(clave: str) -> Path:
    return RAIZ / "specs" / clave / "spec.md"


def texto_spec(historia: dict, repos: list[str]) -> str:
    criterios = [f"{i}. {c}" for i, c in enumerate(historia["criterios"], start=1)] or ["<completar: la historia no trae criterios>"]
    pruebas = [f"| {i} | <completar: nombre> | <completar: qué verifica> |" for i in range(1, len(historia["criterios"]) + 1)]
    lineas = [f"# {historia['clave']}: {historia['titulo']}", "", f"- Jira: {historia['url']}",
              f"- Tipo: {historia['tipo_incidencia'] or 'NO DETERMINADO'}", f"- Repositorios: {', '.join(repos)}", "",
              "## Objetivo", "", "<completar: qué problema resuelve, en una o dos frases>", "",
              "## Criterios de aceptación", "", *criterios, "",
              "## Diseño", "", "<completar: qué cambia en cada repositorio, citando archivo:línea>", "",
              "## Pruebas", "", "| Criterio | Prueba | Qué verifica |", "|---|---|---|", *pruebas, "",
              "## Reglas que aplican", "", "<completar: ID de los documentos y decisiones, con la sección citada>", "",
              "## Fuera de alcance", "", "<completar: lo que este cambio no hace>", ""]
    return "\n".join(lineas)


def seccion_spec(texto: str, nombre: str) -> str | None:
    coincidencia = re.search(rf"^## {re.escape(nombre)}[ \t]*\n(.*?)(?=^## |\Z)", texto, re.MULTILINE | re.DOTALL)
    return coincidencia.group(1) if coincidencia else None


def criterios_spec(texto: str) -> list[str]:
    return re.findall(r"^\d+\.\s+(.+)$", seccion_spec(texto, "Criterios de aceptación") or "", re.MULTILINE)


def errores_spec(clave: str) -> list[str]:
    archivo = ruta_spec(clave)
    if not archivo.exists():
        return [f"no existe specs/{clave}/spec.md"]
    texto = archivo.read_text(encoding="utf-8")
    errores = [f"falta la sección {s}" for s in SECCIONES_SPEC if seccion_spec(texto, s) is None]
    if PENDIENTE_SPEC in texto:
        errores.append("quedan partes por completar")
    criterios = criterios_spec(texto)
    if not criterios:
        errores.append("no tiene criterios de aceptación")
    pruebas = seccion_spec(texto, "Pruebas") or ""
    errores += [f"el criterio {n} no tiene prueba" for n in range(1, len(criterios) + 1)
                if not re.search(rf"^\|\s*{n}\s*\|", pruebas, re.MULTILINE)]
    if len(texto.splitlines()) > MAXIMO_LINEAS_SPEC:
        errores.append(f"supera las {MAXIMO_LINEAS_SPEC} líneas")
    return errores + [f"lenguaje: {a}" for a in avisos_lenguaje(texto)]


def spec_aprobada(clave: str) -> bool:
    """Una spec está aprobada cuando su MR se integró en la rama principal del harness."""
    referencia = RAMA_PRINCIPAL
    if git("remote", "get-url", "origin", cwd=RAIZ)[0] == 0:
        git("fetch", "--quiet", "origin", RAMA_PRINCIPAL, cwd=RAIZ)
        referencia = f"origin/{RAMA_PRINCIPAL}"
    return git("cat-file", "-e", f"{referencia}:specs/{clave}/spec.md", cwd=RAIZ)[0] == 0


def preparar_spec(historia: dict, repos: list[str], crear_rama: bool) -> str:
    """Rama docs/<CLAVE>-spec del harness y borrador. Un Spike no lleva spec: su entregable es un ADR."""
    clave = historia["clave"]
    if tipo_historia(historia["tipo_incidencia"]) == "spike":
        return "sin spec: el entregable del Spike es un ADR"
    if spec_aprobada(clave):
        return f"specs/{clave}/spec.md (ya aprobada)"
    if crear_rama:
        nombre, actual = rama_spec(clave), git("branch", "--show-current", cwd=RAIZ)[1]
        if actual not in (RAMA_PRINCIPAL, nombre):
            raise ErrorHdu(f"El harness está en la rama {actual}. Volver a {RAMA_PRINCIPAL} y repetir.")
        if actual == RAMA_PRINCIPAL:
            existe = git("rev-parse", "--verify", "--quiet", nombre, cwd=RAIZ)[0] == 0
            codigo, salida = git("switch", "--quiet", *([nombre] if existe else ["-c", nombre]), cwd=RAIZ)
            if codigo != 0:
                raise ErrorHdu(f"No se pudo crear la rama {nombre}: {salida}")
    archivo = ruta_spec(clave)
    if not archivo.exists():
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(texto_spec(historia, repos), encoding="utf-8")
    return f"specs/{clave}/spec.md (borrador)"


def desarrollar(clave: str) -> dict:
    """Comprueba que se puede programar: spec aprobada y vigente, salvo Hotfix (su spec se completa al cerrar)."""
    archivo = RAIZ / "trabajo" / clave / "hdu.json"
    if not archivo.exists():
        raise ErrorHdu(f"La historia {clave} no se tomó con /hdu.")
    tomada = json.loads(archivo.read_text(encoding="utf-8"))
    tipo = tipo_historia(tomada.get("tipo_incidencia"))
    if tipo == "spike":
        raise ErrorHdu("Un Spike no se desarrolla: su entregable es un ADR del producto.")
    actual = git("branch", "--show-current", cwd=RAIZ)[1]
    if tipo != "hotfix":
        if actual == rama_spec(clave):
            codigo, salida = git("switch", "--quiet", RAMA_PRINCIPAL, cwd=RAIZ)
            if codigo != 0:
                raise ErrorHdu(f"No se pudo volver a {RAMA_PRINCIPAL}: {salida}")
        elif actual != RAMA_PRINCIPAL:
            raise ErrorHdu(f"El harness está en la rama {actual}. Volver a {RAMA_PRINCIPAL} y repetir.")
        actualizar_harness()
        if not spec_aprobada(clave):
            raise ErrorHdu(f"La spec de {clave} no está aprobada: su MR debe integrarse en {RAMA_PRINCIPAL} antes de programar.")
        errores = errores_spec(clave)
        if errores:
            raise ErrorHdu("La spec aprobada no es válida:\n  - " + "\n  - ".join(errores))
    foco(tomada["repos"], [r["id"] for r in leer_json("repos.json")["repos"]])
    return {"spec": ruta_spec(clave), "tipo": tipo, "ramas": tomada["ramas"]}


def avisos_lenguaje(texto: str) -> list[str]:
    archivo = RAIZ / "lenguaje.json"
    if not archivo.exists():
        return []
    reglas = json.loads(archivo.read_text(encoding="utf-8"))
    minusculas, avisos = texto.lower(), []
    for palabra in reglas.get("voseo", []):
        if re.search(rf"(?<![\wáéíóúñ]){re.escape(palabra.lower())}(?![\wáéíóúñ])", minusculas):
            avisos.append(f"voseo: «{palabra}»")
    normal = normalizar(texto)
    for expresion in reglas.get("expresiones", []):
        if re.search(rf"\b{re.escape(normalizar(expresion))}\b", normal):
            avisos.append(f"expresión de relleno: «{expresion}»")
    return avisos


def escribir_contexto(historia: dict, medicion: str, repos: list[str], ramas: dict[str, str], relacion: dict,
                      documentos: list[dict], avisos: list[str], spec: str) -> Path:
    carpeta = RAIZ / "trabajo" / historia["clave"]
    carpeta.mkdir(parents=True, exist_ok=True)
    lineas = [f"# {historia['clave']}: {historia['titulo']}", "",
              f"- [Jira]({historia['url']}) · {historia['tipo_incidencia'] or 'tipo NO DETERMINADO'}"
              + (f" · Tipo: {historia['tipo']}" if historia["tipo"] else "") + f" · Estado: {historia['estado']}",
              f"- Medición HU: {historia['medicion'] or 'vacía'} ({medicion})",
              f"- Repositorios: {', '.join(repos) or 'NO DETERMINADO'}",
              f"- Reglas: harness versión {version_harness()}",
              f"- Spec: {spec}", ""]
    lineas += [*[f"> {a}" for a in avisos], ""] if avisos else []
    if medicion == "sin medir":
        lineas += ["> HU sin medir: al terminar, `/listo` exige revisar la deuda técnica y operativa que deja.", ""]
    lineas += ["## Criterios de aceptación", ""]
    lineas += [f"{i}. {c}" for i, c in enumerate(historia["criterios"], start=1)] or \
        ["NO DETERMINADO: la historia no tiene una sección de criterios de aceptación reconocible."]
    lineas += ["", "## Descripción", "", historia["descripcion"].strip() or "(vacía)", ""]
    lineas += ["## Arquitectura relacionada", "", "Elegida por palabras en común. Las reglas rápidas de todos los documentos "
               "están en `.cursor/rules/generado/decisiones.mdc`.", ""]
    for documento in documentos:
        lineas += [documento["extracto"], "", f"Texto completo: `{documento['archivo']}`", ""]
    if not documentos:
        lineas += ["Ningún documento coincide por palabras: revisar las reglas rápidas.", ""]
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
                                                  "tipo_incidencia": historia["tipo_incidencia"],
                                                  "criterios": historia["criterios"]}, indent=2, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    return archivo


def tomar(clave: str, repos_pedidos: list[str] | None, crear_rama: bool, tipo_rama: str | None = None) -> dict:
    actualizar_harness()
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
    spec = preparar_spec(historia, repos, crear_rama)
    tipo_cambio = tipo_rama or TIPO_RAMA.get(tipo_historia(historia["tipo_incidencia"]), "feat")
    nombre_rama = f"{tipo_cambio}/{clave}-{slug(historia['titulo'])}"
    ramas = {r["id"]: (preparar_rama(r, nombre_rama) if crear_rama else "sin cambio de rama (--sin-rama)")
             for r in repos_config if r["id"] in repos}
    foco(repos, ids)
    contexto = json.loads((RAIZ / "contexto.json").read_text(encoding="utf-8")) if (RAIZ / "contexto.json").exists() else {}
    relacion = relacionado(historia, contexto, repos)
    avisos = avisos_arquitectura()
    archivo = escribir_contexto(historia, medicion, repos, ramas, relacion, arquitectura_relacionada(historia, relacion), avisos, spec)
    return {"historia": historia, "medicion": medicion, "tomada": True, "repos": repos, "ramas": ramas, "contexto": archivo,
            "avisos": avisos, "spec": spec}


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tomar una historia de Jira (/hdu).")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("tomar")
    p.add_argument("clave")
    p.add_argument("--repos", default="")
    p.add_argument("--sin-rama", action="store_true")
    p.add_argument("--tipo", choices=TIPOS_CAMBIO, help="tipo de cambio de la rama (ADR-EQ-010); por defecto, según la historia")
    for nombre in ("spec", "desarrollar"):
        p = sub.add_parser(nombre)
        p.add_argument("clave")
    o = parser.parse_args(argumentos)
    if o.accion == "spec":
        errores = errores_spec(o.clave.upper())
        print("Spec válida: hacer commit, push de la rama y abrir su MR." if not errores else "\n".join(f"  - {e}" for e in errores))
        return 1 if errores else 0
    if o.accion == "desarrollar":
        try:
            r = desarrollar(o.clave.upper())
        except ErrorHdu as error:
            print(f"ERROR: {error}")
            return 1
        print(f"Spec: {r['spec'].relative_to(RAIZ)}" + (" (Hotfix: se completa al cerrar)" if r["tipo"] == "hotfix" else " (aprobada)"))
        for repo, estado in r["ramas"].items():
            print(f"  {repo}: {estado}")
        return 0
    try:
        r = tomar(o.clave.upper(), [x.strip() for x in o.repos.split(",") if x.strip()] or None, not o.sin_rama, o.tipo)
    except ErrorHdu as error:
        print(f"ERROR: {error}")
        return 1
    h = r["historia"]
    print(f"{h['clave']}: {h['titulo']} · Medición HU: {h['medicion'] or 'vacía'} ({r['medicion']})")
    if r["medicion"] == "rechazada":
        print(f"No se toma: la Medición HU debe ser una de las aceptadas. Completar la historia "
              f"(criterios de aceptación medibles, Como/Quiero/Para) y volver a medirla.")
        return 2
    if not h["campo_medicion_existe"]:
        print("Aviso: no se encontró el campo de Medición HU en Jira (revisar config.json).")
    if r.get("faltan_repos") is not None:
        print(f"No se pudo saber qué repositorios toca. Indicarlos con --repos (disponibles: {', '.join(r['faltan_repos'])}).")
        return 3
    for repo, estado in r["ramas"].items():
        print(f"  {repo}: {estado}")
    for aviso in r["avisos"]:
        print(f"Aviso: {aviso}")
    print(f"Reglas: harness versión {version_harness()}. Spec: {r['spec']}.")
    print(f"Criterios de aceptación: {len(h['criterios'])}. Contexto: {r['contexto'].relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
