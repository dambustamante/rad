"""Administra los productos y sus repositorios (productos/<producto>/producto.yaml).

Uso:
  python herramientas/productos.py listar
  python herramientas/productos.py inspeccionar <url>
  python herramientas/productos.py agregar --producto P --id ID --url URL --rama RAMA --tipo TIPO
                                           [--sonar CLAVE] [--descripcion TEXTO]
  python herramientas/productos.py retirar --producto P --id ID --motivo TEXTO
  python herramientas/productos.py sincronizar [--producto P]
  python herramientas/productos.py sigla <producto> [--asignar SIGLA]
  python herramientas/productos.py historias <producto> --fuente jira|archivo|ninguna [--jql JQL | --tablero N [--etiqueta E]]
                                             [--campo-tipo NOMBRE] [--archivo export.csv] [--proyecto CLAVE]

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

Todo se resuelve con git: no requiere tokens ni API de GitLab o GitHub. Los repositorios se
clonan en productos/<producto>/repos/<id>/ y nunca se modifican: si una copia tiene cambios
locales, no se toca.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from comun import (RAIZ, ErrorRadiografia, actualizar_clon, carpeta_decisiones_producto, clon_de_inspeccion, escribir_yaml_conservador, git,
                   leer_yaml_conservador, rama_por_defecto, resolver_commit, yaml_conservador)

TIPOS_REPO = ("propio", "proveedor", "config")
PATRON_SIGLA = re.compile(r"[A-Z]{2,5}")
SIGLAS_RESERVADAS = {"EQ"}
PATRON_NOMBRE = re.compile(r"[a-z0-9][a-z0-9-]*")
ORIGENES = ("heredado", "nuevo")
PATRON_CONTRATO = re.compile(r"(^|/)[^/]*(openapi|swagger|asyncapi)[^/]*\.(ya?ml|json)$", re.IGNORECASE)

PLANTILLA_PRODUCTO = """\
# Producto {nombre}. Se administra con el comando /producto: no se edita a mano.

nombre: {nombre}
descripcion: ""
# heredado (se recibe de otro equipo y se toma el control) | nuevo (se construye desde el inicio)
origen: {origen}
# Sigla para numerar los ADR del producto (ADR-{sigla}-001). Se cambia con `productos.py sigla` mientras no haya ADR.
sigla: {sigla}

# Ubicación del C4 del producto (ADR-EQ-006), en formato <id-repo>:<ruta>. null si aún no existe.
c4: null

# Repositorios del producto.
#   tipo: propio (lo desarrolla el banco) | proveedor (código de un tercero) | config (configuración o infraestructura)
#   sonar: clave del proyecto en Sonar (SonarQube o SonarCloud); null si no se conoce
#   estado: activo | retirado
repos: []

# Historias de usuario para proponer ADR (ver herramientas/jira.py).
#   fuente: jira (con jql o tablero, y campo_tipo) | archivo (exportación CSV en historias/) | ninguna
historias:
  fuente: ninguna
"""


# --- Utilidades --------------------------------------------------------------------------------

def validar_nombre(valor: str, que: str) -> None:
    if not PATRON_NOMBRE.fullmatch(valor):
        raise ErrorRadiografia(f"El {que} '{valor}' debe ir en minúsculas, con números y guiones (por ejemplo motor-fraudes).")


def normalizar_url_git(url: str) -> str:
    """Forma comparable de una URL: git@host:grupo/repo.git y https://host/grupo/repo son la misma."""
    texto = url.strip().lower().rstrip("/")
    texto = re.sub(r"\.git$", "", texto)
    texto = re.sub(r"^[a-z+]+://", "", texto)
    texto = re.sub(r"^[^@/]+@", "", texto)
    return texto.replace(":", "/", 1) if ":" in texto.split("/", 1)[0] else texto


def siglas_en_uso(raiz: Path, excepto: str | None = None) -> set[str]:
    return {str(d.get("sigla")) for p, d in leer_productos(raiz).items() if p != excepto and d.get("sigla")} | SIGLAS_RESERVADAS


def proponer_sigla(raiz: Path, producto: str) -> str:
    """Iniciales de las palabras del nombre (motor-fraudes -> MF; pagos -> PAG), única entre productos."""
    palabras = [re.sub(r"[^a-z]", "", p) for p in producto.split("-")]
    palabras = [p for p in palabras if p] or ["producto"]
    letras = "".join(palabras).upper()
    base = "".join(p[0] for p in palabras).upper() if len(palabras) > 1 else palabras[0][:3].upper()
    base = (base + letras[len(base):] + "XX")[:max(2, len(base))][:5]
    usadas = siglas_en_uso(raiz, producto)
    candidata, extra = base, iter(letras[len(base):])
    while candidata in usadas:
        siguiente = next(extra, None)
        if siguiente and len(candidata) < 5:
            candidata += siguiente
        else:
            break
    numero = 0
    while candidata in usadas:
        candidata = base[:4] + chr(ord("A") + numero)
        numero += 1
    return candidata


def asignar_sigla(raiz: Path, producto: str, sigla: str) -> None:
    archivo = archivo_producto(raiz, producto)
    if not archivo.exists():
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    if not PATRON_SIGLA.fullmatch(sigla):
        raise ErrorRadiografia(f"La sigla '{sigla}' debe tener de 2 a 5 letras mayúsculas.")
    if sigla in siglas_en_uso(raiz, producto):
        raise ErrorRadiografia(f"La sigla '{sigla}' ya está en uso o reservada.")
    if any(carpeta_decisiones_producto(raiz, producto).glob("ADR-*.md")):
        raise ErrorRadiografia("El producto ya tiene ADR: su sigla no se puede cambiar.")
    datos = leer_yaml_conservador(archivo)
    datos["sigla"] = sigla
    escribir_yaml_conservador(archivo, datos)


def configurar_historias(raiz: Path, producto: str, fuente: str, jql: str | None, tablero: int | None,
                         etiqueta: str | None, campo_tipo: str | None, archivo_csv: str | None,
                         proyecto: str | None = None) -> None:
    archivo = archivo_producto(raiz, producto)
    if not archivo.exists():
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    if fuente == "jira" and not (jql or tablero):
        raise ErrorRadiografia("Con fuente jira hay que indicar --jql o --tablero.")
    if fuente == "archivo" and not archivo_csv:
        raise ErrorRadiografia("Con fuente archivo hay que indicar --archivo (exportación CSV dentro de historias/).")
    configuracion = CommentedMap(fuente=fuente)
    if fuente == "jira":
        if jql:
            configuracion["jql"] = jql
        if tablero:
            configuracion["tablero"] = tablero
            if etiqueta:
                configuracion["etiqueta"] = etiqueta
    if fuente == "archivo":
        configuracion["archivo"] = archivo_csv
    if campo_tipo and fuente != "ninguna":
        configuracion["campo_tipo"] = campo_tipo
    if proyecto:
        configuracion["proyecto"] = proyecto  # donde se crean Tareas, Spikes, Errores y Hotfix
    datos = leer_yaml_conservador(archivo)
    datos["historias"] = configuracion
    escribir_yaml_conservador(archivo, datos)


def nombre_repositorio(url: str) -> str:
    return re.sub(r"\.git$", "", url.rstrip("/").split("/")[-1].split(":")[-1]).lower()


def archivo_producto(raiz: Path, producto: str) -> Path:
    return raiz / "productos" / producto / "producto.yaml"


def leer_productos(raiz: Path) -> dict[str, CommentedMap]:
    productos = {}
    for archivo in sorted((raiz / "productos").glob("*/producto.yaml")):
        productos[archivo.parent.name] = leer_yaml_conservador(archivo)
    return productos


def repos_de(datos) -> CommentedSeq:
    repos = datos.get("repos")
    if not isinstance(repos, CommentedSeq):
        repos = CommentedSeq(repos or [])
        datos["repos"] = repos
    return repos


# --- Inspección --------------------------------------------------------------------------------

def leer_archivo(clon: Path, commit: str, ruta: str) -> str:
    try:
        return git("show", f"{commit}:{ruta}", cwd=clon)
    except ErrorRadiografia:
        return ""


def detectar_stack(clon: Path, commit: str, archivos: set[str]) -> list[str]:
    stack: list[str] = []
    if "pom.xml" in archivos:
        pom = leer_archivo(clon, commit, "pom.xml")
        stack.append("Java (Maven)")
        if version := re.search(r"<artifactId>spring-boot-starter-parent</artifactId>\s*<version>([^<]+)</version>", pom):
            stack.append(f"Spring Boot {version.group(1)}")
        elif "spring-boot" in pom:
            stack.append("Spring Boot")
    gradle = next((a for a in ("build.gradle.kts", "build.gradle") if a in archivos), None)
    if gradle:
        texto = leer_archivo(clon, commit, gradle)
        stack.append("Kotlin (Gradle)" if gradle.endswith(".kts") else "Java (Gradle)")
        if version := re.search(r"org\.springframework\.boot['\"]?\)?\s*version\s*['\"]([^'\"]+)", texto):
            stack.append(f"Spring Boot {version.group(1)}")
    if "package.json" in archivos:
        try:
            paquete = json.loads(leer_archivo(clon, commit, "package.json") or "{}")
        except json.JSONDecodeError:
            paquete = {}
        dependencias = {**paquete.get("dependencies", {}), **paquete.get("devDependencies", {})}
        stack.append("Node.js")
        marcos = {"typescript": "TypeScript", "@nestjs/core": "NestJS", "next": "Next.js",
                  "react": "React", "express": "Express", "@angular/core": "Angular"}
        stack += [nombre for paquete_npm, nombre in marcos.items() if paquete_npm in dependencias]
    if "go.mod" in archivos:
        version = re.search(r"^go\s+(\S+)", leer_archivo(clon, commit, "go.mod"), re.MULTILINE)
        stack.append(f"Go {version.group(1)}" if version else "Go")
    python = [a for a in ("pyproject.toml", "requirements.txt") if a in archivos]
    if python:
        texto = " ".join(leer_archivo(clon, commit, a) for a in python).lower()
        stack.append("Python")
        stack += [nombre for clave, nombre in (("fastapi", "FastAPI"), ("django", "Django"), ("flask", "Flask")) if clave in texto]
    if any(a.endswith(".csproj") and a.count("/") <= 2 for a in archivos):
        stack.append(".NET")
    return stack


def detectar_sonar(clon: Path, commit: str, archivos: set[str]) -> str | None:
    if "sonar-project.properties" in archivos:
        texto = leer_archivo(clon, commit, "sonar-project.properties")
        if clave := re.search(r"^\s*sonar\.projectKey\s*=\s*(\S+)", texto, re.MULTILINE):
            return clave.group(1)
    if "pom.xml" in archivos:
        if clave := re.search(r"<sonar\.projectKey>([^<]+)</sonar\.projectKey>", leer_archivo(clon, commit, "pom.xml")):
            return clave.group(1).strip()
    for gradle in ("build.gradle.kts", "build.gradle"):
        if gradle in archivos:
            texto = leer_archivo(clon, commit, gradle)
            if clave := re.search(r"sonar\.projectKey['\"]?\s*,\s*['\"]([^'\"]+)", texto):
                return clave.group(1)
    return None


def inspeccionar(url: str, raiz: Path) -> dict:
    """Describe un repositorio para proponer su registro en un producto."""
    clon = clon_de_inspeccion(url, raiz)
    rama = rama_por_defecto(clon)
    commit = resolver_commit(clon, rama)
    archivos = set(git("ls-tree", "-r", "--name-only", commit, cwd=clon).splitlines())
    raiz_archivos = {a.lower() for a in archivos if "/" not in a}

    registrado_en = None
    for producto, datos in leer_productos(raiz).items():
        for repo in repos_de(datos):
            if normalizar_url_git(str(repo.get("url", ""))) == normalizar_url_git(url):
                registrado_en = {"producto": producto, "id": str(repo.get("id")), "estado": str(repo.get("estado"))}

    return {
        "url": url,
        "id_sugerido": nombre_repositorio(url),
        "rama_por_defecto": rama,
        "commit": commit,
        "fecha_ultimo_commit": git("log", "-1", "--format=%cs", commit, cwd=clon),
        "stack": detectar_stack(clon, commit, archivos),
        "sonar_detectado": detectar_sonar(clon, commit, archivos),
        "presencia": {
            "readme": "readme.md" in raiz_archivos,
            "c4_contexto": "docs/arquitectura/c4-contexto.md" in archivos,
            "c4_contenedores": "docs/arquitectura/c4-contenedores.md" in archivos,
            "contratos": sorted(a for a in archivos if PATRON_CONTRATO.search(a))[:10],
            "dockerfile": any(a == "Dockerfile" or a.endswith("/Dockerfile") for a in archivos),
            "ci": ".gitlab-ci.yml" in archivos or any(a.startswith(".github/workflows/") for a in archivos),
        },
        "archivos": len(archivos),
        "registrado_en": registrado_en,
    }


# --- Altas y bajas -----------------------------------------------------------------------------

def datos_nuevos(raiz: Path, producto: str, descripcion: str | None, origen: str, sigla: str | None = None):
    validar_nombre(producto, "nombre de producto")
    if producto == "equipo":
        raise ErrorRadiografia("'equipo' está reservado para las decisiones del equipo; elegir otro nombre de producto.")
    if origen not in ORIGENES:
        raise ErrorRadiografia(f"Origen '{origen}' inválido; valores válidos: {', '.join(ORIGENES)}.")
    if sigla is not None:
        if not PATRON_SIGLA.fullmatch(sigla):
            raise ErrorRadiografia(f"La sigla '{sigla}' debe tener de 2 a 5 letras mayúsculas.")
        if sigla in siglas_en_uso(raiz, producto):
            raise ErrorRadiografia(f"La sigla '{sigla}' ya está en uso o reservada.")
    datos = yaml_conservador().load(PLANTILLA_PRODUCTO.format(nombre=producto, sigla=sigla or proponer_sigla(raiz, producto),
                                                              origen=origen))
    datos["descripcion"] = descripcion or ""
    return datos


def crear(raiz: Path, producto: str, descripcion: str | None, origen: str, sigla: str | None = None) -> None:
    """Crea un producto sin repositorios (por ejemplo, uno nuevo que todavía no tiene código)."""
    archivo = archivo_producto(raiz, producto)
    if archivo.exists():
        raise ErrorRadiografia(f"El producto '{producto}' ya existe.")
    datos = datos_nuevos(raiz, producto, descripcion, origen, sigla)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    escribir_yaml_conservador(archivo, datos)


def agregar(raiz: Path, producto: str, id_repo: str, url: str, rama: str, tipo: str,
            sonar: str | None, descripcion: str | None, origen: str = "heredado") -> bool:
    """Registra un repositorio. Devuelve True si además se creó el producto."""
    validar_nombre(producto, "nombre de producto")
    if producto == "equipo":
        raise ErrorRadiografia("'equipo' está reservado para las decisiones del equipo; elegir otro nombre de producto.")
    validar_nombre(id_repo, "id de repositorio")
    if tipo not in TIPOS_REPO:
        raise ErrorRadiografia(f"Tipo '{tipo}' inválido; valores válidos: {', '.join(TIPOS_REPO)}.")

    for otro, datos in leer_productos(raiz).items():
        for repo in repos_de(datos):
            if normalizar_url_git(str(repo.get("url", ""))) == normalizar_url_git(url):
                raise ErrorRadiografia(
                    f"El repositorio ya está registrado en el producto '{otro}' como '{repo.get('id')}' "
                    f"(estado {repo.get('estado')})."
                )

    clon = clon_de_inspeccion(url, raiz)
    resolver_commit(clon, rama)

    archivo = archivo_producto(raiz, producto)
    creado = not archivo.exists()
    if creado:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        datos = datos_nuevos(raiz, producto, descripcion, origen)
    else:
        datos = leer_yaml_conservador(archivo)
    repos = repos_de(datos)
    if any(str(r.get("id")) == id_repo for r in repos):
        raise ErrorRadiografia(f"Ya existe un repositorio con id '{id_repo}' en el producto '{producto}'.")

    repos.fa.set_block_style()
    repos.append(CommentedMap(id=id_repo, url=url, rama=rama, tipo=tipo, sonar=sonar or None,
                              estado="activo", agregado=date.today().isoformat()))
    escribir_yaml_conservador(archivo, datos)
    return creado


def retirar(raiz: Path, producto: str, id_repo: str, motivo: str) -> None:
    archivo = archivo_producto(raiz, producto)
    if not archivo.exists():
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    datos = leer_yaml_conservador(archivo)
    repo = next((r for r in repos_de(datos) if str(r.get("id")) == id_repo), None)
    if repo is None:
        raise ErrorRadiografia(f"No existe el repositorio '{id_repo}' en el producto '{producto}'.")
    if repo.get("estado") == "retirado":
        raise ErrorRadiografia(f"El repositorio '{id_repo}' ya está retirado.")
    repo["estado"] = "retirado"
    repo["retirado"] = date.today().isoformat()
    repo["motivo_retiro"] = motivo
    escribir_yaml_conservador(archivo, datos)


def listar(raiz: Path) -> list[dict]:
    resultado = []
    for producto, datos in leer_productos(raiz).items():
        resultado.append({
            "producto": producto,
            "descripcion": str(datos.get("descripcion") or ""),
            "repos": [
                {clave: (None if valor is None else str(valor)) for clave, valor in repo.items()}
                for repo in repos_de(datos)
            ],
        })
    return resultado


# --- Sincronización ----------------------------------------------------------------------------

def sincronizar(raiz: Path, producto: str | None = None) -> list[dict]:
    """Clona o actualiza los repositorios activos en productos/<producto>/repos/<id>/."""
    productos = leer_productos(raiz)
    if producto is not None and producto not in productos:
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    resultados = []
    for nombre, datos in productos.items():
        if producto is not None and nombre != producto:
            continue
        for repo in repos_de(datos):
            if repo.get("estado") != "activo":
                continue
            id_repo, url, rama = str(repo["id"]), str(repo["url"]), str(repo["rama"])
            destino = raiz / "productos" / nombre / "repos" / id_repo
            registro = {"producto": nombre, "repo": id_repo, "rama": rama}
            try:
                anterior = None
                if (destino / ".git").exists():
                    if git("status", "--porcelain", cwd=destino):
                        resultados.append({**registro, "resultado": "omitido",
                                           "detalle": "la copia tiene cambios locales; no se modifica"})
                        continue
                    anterior = git("rev-parse", "HEAD", cwd=destino)
                actualizar_clon(url, destino, raiz)
                commit = resolver_commit(destino, rama)
                git("checkout", "--quiet", "--force", "--detach", commit, cwd=destino)
                resultados.append({**registro, "resultado": "sin cambios" if commit == anterior else "actualizado",
                                   "commit": commit,
                                   "fecha": git("log", "-1", "--format=%cs", commit, cwd=destino)})
            except ErrorRadiografia as error:
                resultados.append({**registro, "resultado": "error", "detalle": str(error)})
    return resultados


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Administra los productos y sus repositorios.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    sub.add_parser("listar", help="muestra los productos y sus repositorios")
    p_inspeccionar = sub.add_parser("inspeccionar", help="describe un repositorio antes de registrarlo")
    p_inspeccionar.add_argument("url")
    p_agregar = sub.add_parser("agregar", help="registra un repositorio en un producto")
    p_agregar.add_argument("--producto", required=True)
    p_agregar.add_argument("--id", required=True)
    p_agregar.add_argument("--url", required=True)
    p_agregar.add_argument("--rama", required=True)
    p_agregar.add_argument("--tipo", required=True, choices=TIPOS_REPO)
    p_agregar.add_argument("--sonar")
    p_agregar.add_argument("--descripcion", help="descripción del producto; se usa solo al crearlo")
    p_agregar.add_argument("--origen", default="heredado", choices=ORIGENES, help="se usa solo al crear el producto")
    p_crear = sub.add_parser("crear", help="crea un producto sin repositorios")
    p_crear.add_argument("--producto", required=True)
    p_crear.add_argument("--origen", required=True, choices=ORIGENES)
    p_crear.add_argument("--descripcion", required=True)
    p_crear.add_argument("--sigla")
    p_retirar = sub.add_parser("retirar", help="marca un repositorio como retirado")
    p_retirar.add_argument("--producto", required=True)
    p_retirar.add_argument("--id", required=True)
    p_retirar.add_argument("--motivo", required=True)
    p_sincronizar = sub.add_parser("sincronizar", help="clona o actualiza los repositorios activos")
    p_sincronizar.add_argument("--producto")
    p_historias = sub.add_parser("historias", help="configura la fuente de historias de usuario del producto")
    p_historias.add_argument("producto")
    p_historias.add_argument("--fuente", required=True, choices=("jira", "archivo", "ninguna"))
    p_historias.add_argument("--jql")
    p_historias.add_argument("--tablero", type=int)
    p_historias.add_argument("--etiqueta")
    p_historias.add_argument("--campo-tipo")
    p_historias.add_argument("--archivo")
    p_historias.add_argument("--proyecto", help="clave del proyecto de Jira donde se crean Tareas, Spikes, Errores y Hotfix")
    p_sigla = sub.add_parser("sigla", help="muestra o cambia la sigla de un producto")
    p_sigla.add_argument("producto")
    p_sigla.add_argument("--asignar")
    opciones = parser.parse_args(argumentos)
    raiz = opciones.raiz.resolve()

    try:
        if opciones.accion == "listar":
            print(json.dumps(listar(raiz), indent=2, ensure_ascii=False))
        elif opciones.accion == "inspeccionar":
            print(json.dumps(inspeccionar(opciones.url, raiz), indent=2, ensure_ascii=False))
        elif opciones.accion == "agregar":
            creado = agregar(raiz, opciones.producto, opciones.id, opciones.url, opciones.rama, opciones.tipo,
                             opciones.sonar, opciones.descripcion, opciones.origen)
            if creado:
                sigla = leer_productos(raiz)[opciones.producto].get("sigla")
                print(f"Producto '{opciones.producto}' creado con la sigla {sigla} (se puede cambiar mientras no tenga ADR).")
            print(f"Repositorio '{opciones.id}' agregado al producto '{opciones.producto}'.")
        elif opciones.accion == "crear":
            crear(raiz, opciones.producto, opciones.descripcion, opciones.origen, opciones.sigla)
            sigla = leer_productos(raiz)[opciones.producto].get("sigla")
            print(f"Producto '{opciones.producto}' ({opciones.origen}) creado con la sigla {sigla}, sin repositorios.")
        elif opciones.accion == "retirar":
            retirar(raiz, opciones.producto, opciones.id, opciones.motivo)
            print(f"Repositorio '{opciones.id}' retirado del producto '{opciones.producto}'.")
        elif opciones.accion == "sincronizar":
            resultados = sincronizar(raiz, opciones.producto)
            if not resultados:
                print("No hay repositorios activos que sincronizar.")
            for r in resultados:
                detalle = f"{r['commit'][:12]} ({r['fecha']})" if "commit" in r else r["detalle"]
                print(f"  [{r['resultado']}] {r['producto']}/{r['repo']} ({r['rama']}): {detalle}")
            return 1 if any(r["resultado"] == "error" for r in resultados) else 0
        elif opciones.accion == "historias":
            configurar_historias(raiz, opciones.producto, opciones.fuente, opciones.jql, opciones.tablero,
                                 opciones.etiqueta, opciones.campo_tipo, opciones.archivo, opciones.proyecto)
            print(f"Historias de '{opciones.producto}': fuente {opciones.fuente}.")
        elif opciones.accion == "sigla":
            if opciones.asignar:
                asignar_sigla(raiz, opciones.producto, opciones.asignar)
            datos = leer_productos(raiz).get(opciones.producto)
            if datos is None:
                raise ErrorRadiografia(f"No existe el producto '{opciones.producto}'.")
            print(f"Sigla de '{opciones.producto}': {datos.get('sigla') or 'sin asignar'}")
        if opciones.accion in ("agregar", "crear", "retirar", "sigla"):
            import indices
            indices.indice_producto(raiz, opciones.producto)
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
