"""Revisión de MR: bandeja, revisión de un MR y coherencia de los ADR que se proponen en el harness.

Uso:
  python herramientas/mr.py bandeja [--producto P] [--mios]
  python herramientas/mr.py revisar <producto> <repo> <número>
  python herramientas/mr.py adr <producto> <número>

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

`bandeja` lista los MR abiertos de los repositorios de cada producto y de su harness, con el estado de su
registro de /listo (al día, desactualizado o sin /listo). `revisar` prepara la revisión del MR (la misma de
rama.py: diff, verificaciones con el código de radiografia, gitleaks) y agrega, sin IA, los **cambios
sensibles** y el **contraste con /listo**: lo que se declaró se trata como declaración, nunca como prueba.
También registra la deuda que declaró la historia. `adr` deja la rama del MR del harness en una copia de
solo lectura y prepara la coherencia de sus ADR antes de aprobarlo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

import hallazgos as registro_hallazgos
import harness
import productos
import rama
from comun import RAIZ, ErrorRadiografia, cargar_env, git, slug
from plataforma import proyecto_de

MARCA_REGISTRO = re.compile(r"<!--\s*radiografia:listo\s+(\{.*?\})\s*-->", re.DOTALL)
PRUEBAS = re.compile(r"(^|/)(test|tests|__tests__|spec)(/|$)|(Test|Tests|IT)\.(java|kt)$|\.(test|spec)\.[jt]sx?$|(^|/)test_[^/]+\.py$")
DEBILITADA = re.compile(r"@(Disabled|Ignore)\b|\b(xit|xdescribe|it\.skip|describe\.skip|test\.skip)\(|pytest\.mark\.skip|assert(True)?\(\s*true\s*\)")
ASERCION = re.compile(r"\bassert|\bexpect\(|\bverify\(")
APAGADO = re.compile(r"NOSONAR|sonar\.(coverage\.)?exclusions|@SuppressWarnings|eslint-disable|#\s*noqa|#\s*nosec|istanbul ignore")
UMBRAL = re.compile(r"(?i)(minimum|threshold|coverage|covered)\D{0,30}\d")
CONTROL = re.compile(r"(^|/)(\.gitlab-ci\.yml|\.github/workflows/|\.cursor/|AGENTS\.md$|sonar-project\.properties$|\.gitleaks(\.toml|ignore)$)")
CONFIG_COBERTURA = re.compile(r"(^|/)(pom\.xml|build\.gradle(\.kts)?|jest\.config\.[jt]s|\.nycrc.*|pyproject\.toml|setup\.cfg|\.coveragerc)$")
RUT = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]\b")
TARJETA = re.compile(r"\b\d{15,16}\b")


def registro_listo(descripcion: str) -> dict | None:
    """Registro que /listo deja al final de la descripción del MR, o None."""
    coincidencia = MARCA_REGISTRO.search(descripcion or "")
    if not coincidencia:
        return None
    try:
        return json.loads(coincidencia.group(1))
    except json.JSONDecodeError:
        return {"invalido": True}


def luhn(numero: str) -> bool:
    digitos = [int(d) for d in numero][::-1]
    total = sum(d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2) for i, d in enumerate(digitos))
    return total % 10 == 0


def cliente_o_error(raiz: Path, cliente=None):
    if cliente is not None:
        return cliente
    cliente, motivo = rama.cliente_desde_env(raiz)
    if cliente is None:
        raise ErrorRadiografia(f"La revisión de MR necesita la plataforma git: {motivo}.")
    return cliente


# --- Bandeja -----------------------------------------------------------------------------------

def estado_listo(mr: dict) -> str:
    registro = registro_listo(mr.get("descripcion", ""))
    if registro is None:
        return "sin /listo"
    if registro.get("invalido"):
        return "registro de /listo ilegible"
    return "al día" if mr.get("commit") and registro.get("commit") == mr["commit"] else "desactualizado"


def bandeja(raiz: Path, producto: str | None = None, mios: bool = False, cliente=None) -> list[dict]:
    cliente = cliente_o_error(raiz, cliente)
    usuario = None
    if mios:
        env = cargar_env(raiz)
        usuario = (env.get("GITLAB_USUARIO") or env.get("GITHUB_USUARIO") or "").strip()
        if not usuario:
            raise ErrorRadiografia("--mios necesita GITLAB_USUARIO (o GITHUB_USUARIO) en .env.")
    filas = []
    for nombre, datos in sorted(productos.leer_productos(raiz).items()):
        if producto and nombre != producto:
            continue
        fuentes = [(str(r["id"]), str(r["url"]), "repo") for r in productos.repos_de(datos) if r.get("estado") == "activo"]
        if harness.existe(raiz, nombre):
            try:
                fuentes.append((f"harness-{nombre}", git("remote", "get-url", "origin", cwd=harness.ruta(raiz, nombre)), "harness"))
            except ErrorRadiografia:
                pass
        for id_repo, url, tipo in fuentes:
            try:
                mrs = cliente.mrs_abiertos(proyecto_de(url))
            except ErrorRadiografia as error:
                filas.append({"producto": nombre, "repo": id_repo, "tipo": tipo, "error": str(error)})
                continue
            for mr in mrs:
                if usuario and usuario not in (mr.get("revisores") or []):
                    continue
                filas.append({"producto": nombre, "repo": id_repo, "tipo": tipo, "numero": mr["numero"], "titulo": mr["titulo"],
                              "url": mr["url"], "autor": mr.get("autor"), "rama": mr.get("rama"),
                              "listo": "ADR del producto" if tipo == "harness" else estado_listo(mr)})
    prioridad = {"ADR del producto": 0, "sin /listo": 1, "registro de /listo ilegible": 1, "desactualizado": 2, "al día": 3}
    return sorted(filas, key=lambda f: (prioridad.get(f.get("listo"), 9), f["producto"], f["repo"], f.get("numero", 0)))


# --- Revisión de un MR -------------------------------------------------------------------------

def cambios_sensibles(clon: Path, base: str, commit: str) -> dict[str, list[str]]:
    """Señales típicas de que se debilitó el control: se informan siempre y son foco de la revisión."""
    senales: dict[str, list[str]] = {k: [] for k in ("Pruebas debilitadas", "Pruebas borradas", "Aserciones quitadas",
                                                     "Controles apagados", "Umbral de cobertura", "Cambios al propio control",
                                                     "Datos de prueba sospechosos")}
    estados = [l.split("\t") for l in git("diff", "--name-status", base, commit, cwd=clon).splitlines() if l]
    for partes in estados:
        archivo = partes[-1]
        if partes[0].startswith("D") and PRUEBAS.search(partes[1]):
            senales["Pruebas borradas"].append(partes[1])
        if CONTROL.search(archivo):
            senales["Cambios al propio control"].append(archivo)
    archivo, linea, quitadas = None, 0, {}
    for texto in git("diff", "--unified=0", "--no-color", base, commit, cwd=clon).splitlines():
        if texto.startswith("+++ "):
            archivo = None if texto.endswith("/dev/null") else texto[6:]
        elif texto.startswith("--- "):
            continue
        elif texto.startswith("@@"):
            linea = int(re.search(r"\+(\d+)", texto).group(1))
        elif texto.startswith("-") and archivo and PRUEBAS.search(archivo) and ASERCION.search(texto):
            quitadas[archivo] = quitadas.get(archivo, 0) + 1
        elif texto.startswith("+") and archivo:
            ubicacion, agregado = f"{archivo}:{linea}", texto[1:]
            es_prueba = bool(PRUEBAS.search(archivo))
            if es_prueba and DEBILITADA.search(agregado):
                senales["Pruebas debilitadas"].append(ubicacion)
            if es_prueba and ASERCION.search(agregado):
                quitadas[archivo] = quitadas.get(archivo, 0) - 1
            if APAGADO.search(agregado):
                senales["Controles apagados"].append(ubicacion)
            if CONFIG_COBERTURA.search(archivo) and UMBRAL.search(agregado):
                senales["Umbral de cobertura"].append(ubicacion)
            if es_prueba and (RUT.search(agregado) or any(luhn(n) for n in TARJETA.findall(agregado))):
                senales["Datos de prueba sospechosos"].append(ubicacion)
            linea += 1
    senales["Aserciones quitadas"] = [f"{a} ({n} menos)" for a, n in sorted(quitadas.items()) if n > 0]
    return senales


def contraste(raiz: Path, producto: str, estado: dict, mr: dict, automaticos: list[dict]) -> list[str]:
    """Diferencias entre lo que declaró /listo y lo que verifica radiografia."""
    registro = registro_listo(mr.get("descripcion", ""))
    if registro is None:
        return ["El MR no tiene registro de /listo: revisión completa sin declaración."]
    if registro.get("invalido"):
        return ["El registro de /listo del MR está alterado o mal formado."]
    diferencias = []
    if registro.get("commit") != estado["commit"]:
        diferencias.append(f"/listo se ejecutó sobre `{str(registro.get('commit'))[:12]}` y el MR está en `{estado['commit'][:12]}`: "
                           "hay commits sin verificar.")
    if estado.get("secretos") is not None and registro.get("secretos") is not None and registro["secretos"] != estado["secretos"]:
        diferencias.append(f"/listo declaró {registro['secretos']} secreto(s); gitleaks en radiografia encontró {estado['secretos']}.")
    if (registro.get("senales") or {}).get("consola", 0) == 0 and any(h["criterio"] == "EQ-003.1" for h in automaticos):
        diferencias.append("/listo declaró 0 salidas a consola; radiografia encontró EQ-003.1 en archivos del cambio.")
    copia = raiz / estado["copia"]
    for numero, referencia in sorted((registro.get("criterios") or {}).items()):
        partes = str(referencia).split(":")
        if len(partes) < 3:
            diferencias.append(f"Criterio {numero}: la referencia `{referencia}` no tiene el formato esperado.")
            continue
        archivo, linea = ":".join(partes[1:-1]), int(partes[-1]) if partes[-1].isdigit() else 0
        ruta = copia / archivo
        if archivo not in estado["cambiados"] or not ruta.is_file():
            diferencias.append(f"Criterio {numero}: la prueba `{archivo}` no está en el cambio.")
            continue
        cerca = ruta.read_text(encoding="utf-8", errors="replace").splitlines()[max(0, linea - 4):linea]
        if any(DEBILITADA.search(l) for l in cerca):
            diferencias.append(f"Criterio {numero}: la prueba `{archivo}:{linea}` está deshabilitada.")
    if harness.existe(raiz, producto):
        version = json.loads((harness.ruta(raiz, producto) / "GENERADO.json").read_text(encoding="utf-8")).get("version")
        if registro.get("harness") not in (None, version):
            diferencias.append(f"/listo usó el harness versión {registro.get('harness')}; la vigente es {version}.")
        listo = harness.ruta(raiz, producto) / "herramientas" / "listo.py"
        if listo.exists() and registro.get("verificador") not in (None, hashlib.sha256(listo.read_bytes()).hexdigest()[:16]):
            diferencias.append("El listo.py usado no es el de la rama principal del harness.")
    return diferencias or ["Sin diferencias entre /listo y lo que verifica radiografia."]


def registrar_deuda(raiz: Path, producto: str, repo: str, mr: dict) -> int:
    """Guarda la deuda que declaró la historia, para llevarla a Jira con /crear tarea --deuda."""
    registro_mr = registro_listo(mr.get("descripcion", ""))
    if not registro_mr or registro_mr.get("invalido") or not registro_mr.get("deuda"):
        return 0
    registro = registro_hallazgos.cargar(raiz, producto)
    clave = str(registro_mr.get("clave"))
    anterior = registro.setdefault("deuda_declarada", {}).get(f"{clave}@{repo}", {})
    registro["deuda_declarada"][f"{clave}@{repo}"] = {
        "clave": clave, "repo": repo, "mr": mr["url"], "items": registro_mr["deuda"], "fecha": date.today().isoformat(),
        "tarea": anterior.get("tarea")}
    registro_hallazgos.guardar(raiz, producto, registro)
    return len(registro_mr["deuda"])


def revisar(raiz: Path, producto: str, repo: str, numero: int, cliente=None) -> dict:
    cliente = cliente_o_error(raiz, cliente)
    datos_repo = rama.repo_del_producto(raiz, producto, repo)
    proyecto = proyecto_de(str(datos_repo["url"]))
    mr = next((m for m in cliente.mrs_abiertos(proyecto) if int(m["numero"]) == int(numero)), None)
    if mr is None:
        raise ErrorRadiografia(f"No hay un MR abierto número {numero} en '{repo}'.")
    preparado = rama.preparar(raiz, producto, repo, mr["rama"], cliente)
    estado = preparado["estado"]
    clon = raiz / "productos" / producto / "repos" / repo
    sensibles = cambios_sensibles(clon, estado["base"], estado["commit"])
    registro = registro_hallazgos.cargar(raiz, producto)
    automaticos = [h for h in registro["hallazgos"].values() if h["repo"] == repo and h["rama"] == mr["rama"]
                   and h["estado"] == "abierto" and h["origen"] != "revision"]
    diferencias = contraste(raiz, producto, estado, mr, automaticos)
    deuda = registrar_deuda(raiz, producto, repo, mr)
    lineas = ["", "## Cambios sensibles (foco de la revisión)", ""]
    con_senal = {k: v for k, v in sensibles.items() if v}
    lineas += [f"- **{k}:** {', '.join(f'`{x}`' for x in v[:10])}" + (f" y {len(v) - 10} más" if len(v) > 10 else "")
               for k, v in con_senal.items()] or ["Ninguno."]
    lineas += ["", "## Contraste con /listo", "", "Lo que se declaró se contrasta con lo que verifica radiografia; "
               "no reemplaza la revisión.", ""]
    lineas += [f"- {d}" for d in diferencias]
    if deuda:
        lineas += ["", f"Deuda declarada por la historia: {deuda} punto(s), registrados para `/crear {producto} tarea --deuda`."]
    with preparado["paquete"].open("a", encoding="utf-8") as archivo:
        archivo.write("\n".join(lineas) + "\n")
    registro = registro_hallazgos.cargar(raiz, producto)
    estado_guardado = registro["ramas"][rama.clave_rama(repo, mr["rama"])]
    estado_guardado.update({"sensibles": con_senal, "contraste": diferencias, "numero_mr": mr["numero"]})
    registro_hallazgos.guardar(raiz, producto, registro)
    return {**preparado, "mr": mr, "sensibles": con_senal, "contraste": diferencias, "deuda": deuda}


# --- ADR propuestos en el harness --------------------------------------------------------------

def adr(raiz: Path, producto: str, numero: int, cliente=None) -> dict:
    """Deja la rama del MR del harness en una copia de solo lectura y prepara la coherencia de sus ADR."""
    import adr as modulo_adr
    import coherencia
    cliente = cliente_o_error(raiz, cliente)
    copia_principal = harness.ruta(raiz, producto)
    if not harness.existe(raiz, producto):
        raise ErrorRadiografia(f"El producto '{producto}' no tiene harness.")
    proyecto = proyecto_de(git("remote", "get-url", "origin", cwd=copia_principal))
    mr = next((m for m in cliente.mrs_abiertos(proyecto) if int(m["numero"]) == int(numero)), None)
    if mr is None:
        raise ErrorRadiografia(f"No hay un MR abierto número {numero} en el harness de '{producto}'.")
    git("fetch", "--quiet", "origin", mr["rama"], cwd=copia_principal)
    commit = git("rev-parse", "FETCH_HEAD", cwd=copia_principal)
    destino = raiz / ".cache" / "ramas" / producto / "harness" / slug(mr["rama"])
    if (destino / ".git").exists():
        git("checkout", "--quiet", "--force", "--detach", commit, cwd=destino)
    else:
        git("worktree", "prune", cwd=copia_principal)
        destino.parent.mkdir(parents=True, exist_ok=True)
        git("worktree", "add", "--quiet", "--force", "--detach", str(destino), commit, cwd=copia_principal)
    base = git("merge-base", "HEAD", commit, cwd=copia_principal)
    cambiados = [Path(a).name for a in git("diff", "--name-only", base, commit, "--", "decisiones/", cwd=copia_principal).splitlines()
                 if re.match(r"decisiones/ADR-[A-Z]{2,5}-\d{3}", a)]
    carpeta = destino / "decisiones"
    ambito = coherencia.ambito_producto(raiz, producto, carpeta)
    plan = coherencia.preparar(ambito)
    validacion = {}
    for id_adr, decision in coherencia.leer_decisiones(raiz, carpeta).items():
        if Path(decision["archivo"]).name in cambiados:
            validacion[id_adr] = modulo_adr.validar_adr(raiz, producto, decision)
    return {"mr": mr, "carpeta": carpeta, "cambiados": cambiados, "pares": plan["total_pares"], "validacion": validacion}


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Revisión de MR.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("bandeja")
    p.add_argument("--producto")
    p.add_argument("--mios", action="store_true")
    p = sub.add_parser("revisar")
    p.add_argument("producto")
    p.add_argument("repo")
    p.add_argument("numero", type=int)
    p = sub.add_parser("adr")
    p.add_argument("producto")
    p.add_argument("numero", type=int)
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    try:
        if o.accion == "bandeja":
            filas = bandeja(raiz, o.producto, o.mios)
            if not filas:
                print("No hay MR abiertos.")
            print("| Producto | Repositorio | MR | Autor | /listo |")
            print("|---|---|---|---|---|")
            for f in filas:
                if "error" in f:
                    print(f"| {f['producto']} | {f['repo']} | NO DETERMINADO - {f['error']} | | |")
                else:
                    print(f"| {f['producto']} | {f['repo']} | [!{f['numero']} {f['titulo']}]({f['url']}) | {f['autor']} | {f['listo']} |")
        elif o.accion == "revisar":
            r = revisar(raiz, o.producto, o.repo, o.numero)
            print(f"MR !{r['mr']['numero']} {r['mr']['titulo']} · rama {r['mr']['rama']} · "
                  f"{len(r['estado']['cambiados'])} archivo(s) cambiado(s).")
            print(f"  Cambios sensibles: {', '.join(r['sensibles']) or 'ninguno'}")
            for d in r["contraste"]:
                print(f"  Contraste: {d}")
            print(f"Paquete: {r['paquete'].relative_to(raiz)}")
        elif o.accion == "adr":
            r = adr(raiz, o.producto, o.numero)
            print(f"MR !{r['mr']['numero']} del harness · ADR cambiados: {', '.join(r['cambiados']) or 'ninguno'}")
            for id_adr, (errores, avisos) in r["validacion"].items():
                print(f"  {id_adr}: {'válido' if not errores else 'errores: ' + '; '.join(errores)}"
                      + (f" · avisos: {'; '.join(avisos)}" if avisos else ""))
            relativa = r["carpeta"].relative_to(raiz)
            print(f"  Pares de coherencia por evaluar: {r['pares']}. Evaluarlos con "
                  f"`coherencia.py --decisiones {relativa} preparar --ambito {o.producto}` y registrarlos con "
                  f"`coherencia.py --decisiones {relativa} lote <archivo>`.")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
