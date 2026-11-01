"""Cerrar una historia antes de abrir su MR (/listo). Solo biblioteca estándar.

Uso:
  python3 herramientas/listo.py preparar <CLAVE>    verificaciones sobre el diff y paquete para la revisión
  python3 herramientas/listo.py cerrar <CLAVE>      valida trabajo/<CLAVE>/listo.json y escribe la descripción del MR

`preparar` exige que todo esté en commits. Para cada repositorio de la historia (trabajo/<CLAVE>/hdu.json)
compara la rama con su rama principal y verifica, sin IA: secretos (gitleaks), salida a consola, TODO o FIXME
agregados, APIs cambiadas sin contrato, integraciones nuevas y pruebas debilitadas. Escribe
trabajo/<CLAVE>/listo-paquete.md con el diff para la revisión de Cursor.

`cerrar` valida lo que registró Cursor (criterio -> prueba, deuda que deja la historia) y escribe
trabajo/<CLAVE>/mr-<repo>.md con la descripción del MR, que incluye un registro para la revisión.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hdu  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
MAXIMO_LINEAS_DIFF = 1500
PRUEBAS = re.compile(r"(^|/)(test|tests|__tests__|spec)(/|$)|(Test|Tests|IT)\.(java|kt)$|\.(test|spec)\.[jt]sx?$|(^|/)test_[^/]+\.py$")
CONSOLA = re.compile(r"\bSystem\.(out|err)\.print|\bconsole\.(log|debug)\(|^\s*print\(|\bfmt\.Print")
PENDIENTES = re.compile(r"\b(TODO|FIXME|XXX)\b")
API = re.compile(r"@(Get|Post|Put|Delete|Patch|Request)Mapping\b|@(Rest)?Controller\b|\b(app|router)\.(get|post|put|delete|patch)\(")
INTEGRACION = re.compile(r"\b(RestTemplate|WebClient|FeignClient|HttpClient|OkHttpClient|RestClient)\b|\baxios\b|requests\.(get|post)|httpx\.")
DEBILITADA = re.compile(r"@(Disabled|Ignore)\b|\b(xit|xdescribe|it\.skip|describe\.skip|test\.skip)\(|pytest\.mark\.skip|assert(True)?\(\s*true\s*\)")
TIPOS_DEUDA = ("tecnica", "operativa")
MARCA_REGISTRO = "radiografia:listo"


class ErrorListo(Exception):
    pass


def git(*argumentos: str, cwd: Path) -> str:
    r = subprocess.run(["git", *argumentos], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise ErrorListo(f"git {' '.join(argumentos)} falló: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def carpeta_trabajo(clave: str) -> Path:
    carpeta = RAIZ / "trabajo" / clave
    if not (carpeta / "hdu.json").exists():
        raise ErrorListo(f"La incidencia {clave} no se preparó con /desarrollar (falta trabajo/{clave}/hdu.json).")
    return carpeta


def repos_de_la_historia(clave: str) -> tuple[dict, list[dict]]:
    tomada = json.loads((carpeta_trabajo(clave) / "hdu.json").read_text(encoding="utf-8"))
    todos = {r["id"]: r for r in json.loads((RAIZ / "repos.json").read_text(encoding="utf-8"))["repos"]}
    return tomada, [todos[r] for r in tomada["repos"] if r in todos]


def diff_agregado(destino: Path, base: str) -> dict[str, list[tuple[int, str]]]:
    """Líneas agregadas por archivo: {archivo: [(línea, texto)]}."""
    resultado: dict[str, list[tuple[int, str]]] = {}
    archivo, linea = None, 0
    for texto in git("diff", "--unified=0", "--no-color", base, "HEAD", cwd=destino).splitlines():
        if texto.startswith("+++ "):
            archivo = None if texto.endswith("/dev/null") else texto[6:]
        elif texto.startswith("@@"):
            linea = int(re.search(r"\+(\d+)", texto).group(1))
        elif texto.startswith("+") and archivo:
            resultado.setdefault(archivo, []).append((linea, texto[1:]))
            linea += 1
    return resultado


def secretos(destino: Path, base: str) -> int | None:
    if not shutil.which("gitleaks"):
        return None
    with tempfile.TemporaryDirectory() as temporal:
        reporte = Path(temporal) / "gitleaks.json"
        subprocess.run(["gitleaks", "git", "--redact", "--no-banner", "--exit-code", "0", f"--log-opts={base}..HEAD",
                        "--report-format", "json", "--report-path", str(reporte), str(destino)], capture_output=True, check=False)
        return len(json.loads(reporte.read_text(encoding="utf-8") or "[]")) if reporte.exists() else None


def verificar(repo: dict) -> dict:
    destino = RAIZ / "code" / repo["id"]
    if not (destino / ".git").exists():
        raise ErrorListo(f"No existe code/{repo['id']}: ejecutar make actualizar.")
    if git("status", "--porcelain", cwd=destino):
        raise ErrorListo(f"code/{repo['id']} tiene cambios sin commit: hacer commit antes de /listo.")
    base = git("merge-base", f"origin/{repo['rama']}", "HEAD", cwd=destino)
    estados = [l.split("\t") for l in git("diff", "--name-status", base, "HEAD", cwd=destino).splitlines() if l]
    cambiados = sorted(p[-1] for p in estados if not p[0].startswith("D"))
    borrados = sorted(p[1] for p in estados if p[0].startswith("D"))
    agregado = diff_agregado(destino, base)
    senales: dict[str, list[str]] = {"consola": [], "pendientes": [], "integraciones": [], "pruebas debilitadas": []}
    api_cambiada = False
    for archivo, lineas in agregado.items():
        es_prueba = bool(PRUEBAS.search(archivo))
        for numero, texto in lineas:
            ubicacion = f"{archivo}:{numero}"
            if CONSOLA.search(texto) and not es_prueba:
                senales["consola"].append(ubicacion)
            if PENDIENTES.search(texto):
                senales["pendientes"].append(ubicacion)
            if INTEGRACION.search(texto) and not es_prueba:
                senales["integraciones"].append(ubicacion)
            if DEBILITADA.search(texto) and es_prueba:
                senales["pruebas debilitadas"].append(ubicacion)
            api_cambiada = api_cambiada or (bool(API.search(texto)) and not es_prueba)
    senales["pruebas debilitadas"] += [f"{b} (prueba borrada)" for b in borrados if PRUEBAS.search(b)]
    contrato = any(c.startswith("docs/contratos/") for c in cambiados)
    rama = git("branch", "--show-current", cwd=destino)
    mensajes = git("log", "--no-merges", "--format=%s", f"{base}..HEAD", cwd=destino).splitlines()
    return {"id": repo["id"], "rama": rama, "base": base, "convencion": hdu.avisos_convencion(rama, mensajes),
            "commit": git("rev-parse", "HEAD", cwd=destino), "commits": int(git("rev-list", "--count", f"{base}..HEAD", cwd=destino)),
            "cambiados": cambiados, "borrados": borrados, "pruebas": [c for c in cambiados if PRUEBAS.search(c)],
            "secretos": secretos(destino, base), "senales": senales,
            "api_sin_contrato": api_cambiada and not contrato,
            "c4_cambiado": any(c.startswith("docs/arquitectura/") for c in cambiados),
            "diff": git("diff", "--unified=3", "--no-color", base, "HEAD", cwd=destino).splitlines()}


def criterios_de(clave: str, tomada: dict) -> list[str]:
    """Los de la spec, que es lo que se aprobó; sin spec (Spike), los de la historia."""
    archivo = hdu.ruta_spec(clave)
    return hdu.criterios_spec(archivo.read_text(encoding="utf-8")) if archivo.exists() else tomada.get("criterios") or []


def errores_de_spec(clave: str, tomada: dict) -> list[str]:
    tipo = hdu.tipo_historia(tomada.get("tipo_incidencia"))
    if tipo == "spike":
        return []
    errores = [f"spec: {e}" for e in hdu.errores_spec(clave)]
    if tipo != "hotfix" and not hdu.spec_aprobada(clave):
        errores.append(f"spec: no está aprobada (su MR debe integrarse en {hdu.RAMA_PRINCIPAL})")
    return errores


def preparar(clave: str) -> Path:
    tomada, repos = repos_de_la_historia(clave)
    version_previa = hdu.version_harness()
    try:
        hdu.actualizar_harness()
        reglas = f"harness versión {hdu.version_harness()}" + (f" (cambió desde la versión {version_previa}: contrastar con las reglas nuevas)"
                                                               if hdu.version_harness() != version_previa else "")
    except hdu.ErrorHdu as error:
        reglas = f"NO DETERMINADO - {error}"
    resultados = [verificar(r) for r in repos]
    lineas = [f"# /listo de {clave}: {tomada['titulo']}", "",
              f"- Medición HU: {tomada.get('medicion') or 'vacía'} ({tomada.get('evaluacion_medicion')})",
              f"- Reglas: {reglas}", "",
              "## Criterios de aceptación (cada uno necesita su prueba)", ""]
    lineas += [f"{i}. {c}" for i, c in enumerate(criterios_de(clave, tomada), start=1)] or ["NO DETERMINADO: sin criterios."]
    if hdu.ruta_spec(clave).exists():
        lineas += ["", "## Spec (el código debe cumplirla)", "", hdu.ruta_spec(clave).read_text(encoding="utf-8").strip()]
    for r in resultados:
        lineas += ["", f"## {r['id']} · rama `{r['rama']}` · {r['commits']} commit(s) · {len(r['cambiados'])} archivo(s)", ""]
        lineas.append(f"- Secretos (gitleaks): {'NO DETERMINADO (gitleaks no está instalado)' if r['secretos'] is None else r['secretos']}")
        for nombre, ubicaciones in r["senales"].items():
            lineas.append(f"- {nombre.capitalize()}: {', '.join(f'`{u}`' for u in ubicaciones) or 'ninguna'}")
        if r["api_sin_contrato"]:
            lineas.append("- La API cambió y el contrato de `docs/contratos/` no (EQ-004).")
        if r["senales"]["integraciones"] and not r["c4_cambiado"]:
            lineas.append("- Hay integraciones en el cambio y el C4 no se actualizó: revisar timeout (EQ-002.1), ficha del tercero y C4 (EQ-006.6).")
        lineas += [f"- {a}" for a in r["convencion"]]
        lineas.append(f"- Pruebas cambiadas: {', '.join(f'`{p}`' for p in r['pruebas']) or 'ninguna'}")
        lineas += ["", "```diff", *r["diff"][:MAXIMO_LINEAS_DIFF], "```"]
        if len(r["diff"]) > MAXIMO_LINEAS_DIFF:
            lineas.append(f"El diff tiene {len(r['diff'])} líneas; se muestran {MAXIMO_LINEAS_DIFF}.")
    lineas += ["", "## Qué registrar en trabajo/" + clave + "/listo.json", "", "```json", json.dumps({
        "criterios": {"1": "<repo>:<archivo de prueba>:<línea>"},
        "deuda": [{"tipo": "tecnica | operativa", "descripcion": "<qué queda pendiente y por qué>", "evidencia": "<repo>:<archivo>:<línea>"}],
        "sin_deuda": False, "decisiones_aplicadas": ["ADR-EQ-002"], "decision_propuesta": None}, indent=2, ensure_ascii=False), "```"]
    carpeta = carpeta_trabajo(clave)
    (carpeta / "verificaciones.json").write_text(json.dumps([{k: v for k, v in r.items() if k != "diff"} for r in resultados],
                                                            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    archivo = carpeta / "listo-paquete.md"
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return archivo


def ubicacion_valida(referencia: str, repos: dict[str, dict]) -> tuple[str, str, int]:
    coincidencia = re.fullmatch(r"([\w.-]+):(.+?):(\d+)", str(referencia or "").strip())
    if not coincidencia:
        raise ErrorListo(f"'{referencia}' no tiene el formato <repo>:<archivo>:<línea>.")
    repo, archivo, linea = coincidencia.group(1), coincidencia.group(2), int(coincidencia.group(3))
    if repo not in repos:
        raise ErrorListo(f"'{repo}' no es un repositorio de esta historia.")
    ruta = RAIZ / "code" / repo / archivo
    if not ruta.is_file() or not 1 <= linea <= len(ruta.read_text(encoding="utf-8", errors="replace").splitlines()):
        raise ErrorListo(f"'{referencia}' no existe.")
    return repo, archivo, linea


def cerrar(clave: str) -> list[Path]:
    carpeta = carpeta_trabajo(clave)
    tomada, repos = repos_de_la_historia(clave)
    if not (carpeta / "verificaciones.json").exists():
        raise ErrorListo(f"Primero: python3 herramientas/listo.py preparar {clave}")
    verificados = {r["id"]: r for r in json.loads((carpeta / "verificaciones.json").read_text(encoding="utf-8"))}
    for r in repos:
        if git("rev-parse", "HEAD", cwd=RAIZ / "code" / r["id"]) != verificados[r["id"]]["commit"]:
            raise ErrorListo(f"{r['id']} tiene commits nuevos desde preparar: volver a ejecutar preparar.")
    try:
        registro = json.loads((carpeta / "listo.json").read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ErrorListo(f"Falta trabajo/{clave}/listo.json.") from error
    except json.JSONDecodeError as error:
        raise ErrorListo(f"trabajo/{clave}/listo.json no es un JSON válido: {error}") from error
    errores, por_repo = [], {r["id"]: r for r in repos}
    errores += errores_de_spec(clave, tomada)
    criterios = criterios_de(clave, tomada)
    pruebas = registro.get("criterios") or {}
    for numero in range(1, len(criterios) + 1):
        referencia = pruebas.get(str(numero))
        if not referencia:
            errores.append(f"el criterio {numero} no tiene prueba")
            continue
        try:
            repo, archivo, linea = ubicacion_valida(referencia, por_repo)
            if archivo not in verificados[repo]["cambiados"]:
                errores.append(f"criterio {numero}: '{archivo}' no es parte del cambio")
            cerca = (RAIZ / "code" / repo / archivo).read_text(encoding="utf-8", errors="replace").splitlines()[max(0, linea - 4):linea]
            if any(DEBILITADA.search(l) for l in cerca):
                errores.append(f"criterio {numero}: la prueba de '{archivo}:{linea}' está deshabilitada")
        except ErrorListo as error:
            errores.append(f"criterio {numero}: {error}")
    deuda = registro.get("deuda") or []
    for i, d in enumerate(deuda, start=1):
        if d.get("tipo") not in TIPOS_DEUDA:
            errores.append(f"deuda {i}: tipo debe ser tecnica u operativa")
        if not str(d.get("descripcion") or "").strip():
            errores.append(f"deuda {i}: falta la descripción")
        if d.get("evidencia"):
            try:
                ubicacion_valida(d["evidencia"], por_repo)
            except ErrorListo as error:
                errores.append(f"deuda {i}: {error}")
    if tomada.get("evaluacion_medicion") == "sin medir" and not deuda and registro.get("sin_deuda") is not True:
        errores.append("HU sin medir: registrar la deuda que deja o confirmar \"sin_deuda\": true")
    textos = " ".join([*(str(d.get("descripcion") or "") for d in deuda), str(registro.get("decision_propuesta") or ""),
                       *(str(d) for d in registro.get("desvios") or [])])
    errores += [f"lenguaje: {a}" for a in hdu.avisos_lenguaje(textos)]
    if errores:
        raise ErrorListo("No se puede cerrar:\n  - " + "\n  - ".join(errores))

    version = json.loads((RAIZ / "GENERADO.json").read_text(encoding="utf-8")).get("version") if (RAIZ / "GENERADO.json").exists() else None
    verificador = hashlib.sha256((RAIZ / "herramientas" / "listo.py").read_bytes()).hexdigest()[:16]
    archivos = []
    for r in repos:
        v = verificados[r["id"]]
        propios = {n: p for n, p in pruebas.items() if str(p).startswith(f"{r['id']}:")}
        deuda_repo = [d for d in deuda if str(d.get("evidencia") or "").startswith(f"{r['id']}:") or not d.get("evidencia")]
        datos_registro = {"clave": clave, "repo": r["id"], "commit": v["commit"], "harness": version, "verificador": verificador,
                          "medicion": tomada.get("medicion"), "tipo": hdu.tipo_historia(tomada.get("tipo_incidencia")), "secretos": v["secretos"],
                          "senales": {k: len(x) for k, x in v["senales"].items()}, "criterios": propios, "deuda": deuda_repo,
                          "desvios": registro.get("desvios") or [], "decisiones": registro.get("decisiones_aplicadas") or []}
        lineas = [f"## {clave}: {tomada['titulo']}", "", f"Medición HU: {tomada.get('medicion') or 'sin medir'}", "",
                  "### Criterios de aceptación", "", "| # | Criterio | Prueba |", "|---|---|---|"]
        lineas += [f"| {n} | {c} | `{pruebas.get(str(n), '—').split(':', 1)[-1]}` |" for n, c in enumerate(criterios, start=1)
                   if str(pruebas.get(str(n), "")).startswith(f"{r['id']}:")] or ["| — | Sin criterios en este repositorio | — |"]
        if hdu.ruta_spec(clave).exists():
            lineas += ["", f"Spec: `{hdu.ruta_spec(clave).relative_to(RAIZ)}`, en el harness."]
        if registro.get("desvios"):
            lineas += ["", "### Desvíos de la spec", "", *[f"- {d}" for d in registro["desvios"]]]
        lineas += ["", "### Deuda que deja esta HU", ""]
        lineas += [f"- **{'Técnica' if d['tipo'] == 'tecnica' else 'Operativa'}:** {d['descripcion']}"
                   + (f" (`{d['evidencia'].split(':', 1)[-1]}`)" if d.get("evidencia") else "") for d in deuda_repo] or ["Sin deuda."]
        lineas += ["", "### Definición de terminado (ADR-EQ-008)", "",
                   f"- [{'x' if propios or not criterios else ' '}] Criterios de aceptación con su prueba",
                   f"- [{'x' if v['secretos'] == 0 else ' '}] Sin secretos" + (" (gitleaks no disponible)" if v["secretos"] is None else ""),
                   "- [ ] Quality gate de Sonar en verde (lo verifica el pipeline)",
                   "- [ ] Aprobado por otra persona",
                   f"- Decisiones que aplican: {', '.join(registro.get('decisiones_aplicadas') or []) or '—'}"]
        if registro.get("decision_propuesta"):
            lineas += ["", f"**Decisión propuesta:** {registro['decision_propuesta']}"]
        lineas += ["", f"<!-- {MARCA_REGISTRO} {json.dumps(datos_registro, ensure_ascii=False)} -->"]
        archivo = carpeta / f"mr-{r['id']}.md"
        archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        archivos.append(archivo)
    hdu.foco(None, [x["id"] for x in json.loads((RAIZ / "repos.json").read_text(encoding="utf-8"))["repos"]])
    return archivos


def main(argumentos: list[str] | None = None) -> int:
    argumentos = sys.argv[1:] if argumentos is None else argumentos
    if len(argumentos) != 2 or argumentos[0] not in ("preparar", "cerrar"):
        print(__doc__)
        return 2
    accion, clave = argumentos[0], argumentos[1].upper()
    try:
        if accion == "preparar":
            print(f"Paquete: {preparar(clave).relative_to(RAIZ)}")
        else:
            for archivo in cerrar(clave):
                print(f"Descripción del MR: {archivo.relative_to(RAIZ)}")
            print("Foco restaurado. Siguiente: push de la rama y MR con esa descripción.")
    except ErrorListo as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
