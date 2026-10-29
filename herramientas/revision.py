"""Soporte determinista de la revisión de código de /revisar (la parte que hace el agente).

Uso:
  python herramientas/revision.py pendientes <producto>
  python herramientas/revision.py paquete <producto> <repo> [--completa]
  python herramientas/revision.py evaluar <producto> <repo> --fuente F [--criterio C] --resultado R --motivo TEXTO
                                          [--evidencia ruta:línea ...] [--cita-documento TEXTO]
                                          [--documento-tercero RUTA --cita-tercero TEXTO]
  python herramientas/revision.py hallazgo <producto> <repo> --fuente F [--criterio C] --categoria CAT --severidad SEV
                                           --titulo TEXTO --detalle TEXTO --evidencia ruta:línea [--evidencia ...]
                                           --fragmento TEXTO [--cita-documento TEXTO]
                                           [--documento-tercero RUTA --cita-tercero TEXTO]
  python herramientas/revision.py registrar <producto> <repo> [--archivo LOTE.yaml]
  python herramientas/revision.py cerrar <producto> <repo> [--archivos-leidos N]
  python herramientas/revision.py producto <producto> [--narrativa ARCHIVO]

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

Fuentes: documentos vigentes de arquitectura en formato `fuente:ID` (niveles 1 y 2) y decisiones del
equipo `ADR-EQ-NNN` con su `--criterio EQ-NNN.N` (nivel 3). Toda evidencia se valida contra el commit
revisado y toda cita contra el texto del documento: lo que no existe se rechaza.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys

import yaml
from collections import Counter
from datetime import date
from pathlib import Path

import hallazgos as registro_hallazgos
import productos
import terceros
import verificaciones
from adr import excepciones_activas, excepciones_pendientes
from coherencia import (cita_existe, leer_arquitectura_vigente, leer_decisiones_producto, suspendidos as criterios_suspendidos,
                        texto_comparable)
from comun import RAIZ, ErrorRadiografia, git, normalizar
from revisar import MARCA_REVISION, decisiones_con_criterios, leer_json, reemplazar_bloque, veredicto

MARCA_COMPARACION = ("<!-- comparacion:inicio -->", "<!-- comparacion:fin -->")
MARCA_PRODUCTO_AUTOMATICO = ("<!-- producto-automatico:inicio -->", "<!-- producto-automatico:fin -->")
MARCA_PRODUCTO_NARRATIVA = ("<!-- producto-narrativa:inicio -->", "<!-- producto-narrativa:fin -->")
RESULTADOS = ("CUMPLE", "NO CUMPLE", "NO APLICA", "NO DETERMINADO")
CATEGORIAS = ("incumplimiento", "diseño", "error", "seguridad", "deuda", "documentacion")
SEVERIDADES = ("bloqueante", "alta", "media", "baja")
SECCIONES_AS_IS = ("Propósito", "Arquitectura real", "Componentes y contenedores", "Integraciones", "Contratos",
                   "Datos", "Configuración y despliegue", "Observabilidad", "Riesgos y deuda principales")
VENTANA_FRAGMENTO = 3
UMBRAL_INCREMENTAL = 0.4   # si cambió más de esta fracción de archivos, la revisión es completa
MINIMO_ARCHIVOS_UMBRAL = 20  # en repositorios más chicos el umbral no se aplica
SIMBOLOS = {"CUMPLE": "✅", "NO CUMPLE": "❌", "NO APLICA": "➖", "NO DETERMINADO": "❔"}

SENALES = {
    "Clientes de sistemas externos": re.compile(
        r"\b(RestTemplate|WebClient|FeignClient|@FeignClient|HttpClient|OkHttpClient|RestClient)\b"
        r"|\baxios\b|\bfetch\(|\bgot\(|requests\.(get|post|put|delete)|httpx\.|http\.(Get|Post|NewRequest)|grpc\.Dial"),
    "Acceso a datos": re.compile(
        r"\b(JpaRepository|CrudRepository|JdbcTemplate|EntityManager|@Query|@Entity|@Table)\b"
        r"|\b(mongoose|prisma|typeorm|sequelize|knex)\b|\bsqlalchemy\b|database/sql|gorm\."),
    "Resiliencia (timeouts, reintentos, circuit breaker)": re.compile(
        r"(?i)\b(timeout|retry|retries|backoff|circuitbreaker|circuit_breaker|resilience4j|bulkhead|ratelimiter)\b"),
    "Manejo de excepciones sospechoso": re.compile(
        r"catch\s*\([^)]*\)\s*\{\s*\}|except\s*(\w+\s*)?:\s*pass\b|catch\s*\{\s*\}|if err != nil \{\s*\}"),
    "Logs con posibles datos sensibles": re.compile(
        r"(?i)(log|logger|console)\S*\.(info|debug|warn|error|trace|log)\(.*\b(pan|card|tarjeta|cvv|rut|password|"
        r"contrase|token|secret|email|telefono|phone)\b"),
    "Configuración de logs": re.compile(r"(?i)(logback|log4j2?|winston|pino|structlog|zap\.New|slog\.New)"),
}
SENALES["APIs expuestas"] = verificaciones.SENALES_API
SENALES["Mensajería"] = verificaciones.SENALES_EVENTOS
ARCHIVOS_CONFIGURACION = re.compile(
    r"(^|/)(pom\.xml|build\.gradle(\.kts)?|package\.json|go\.mod|pyproject\.toml|requirements\.txt|Dockerfile|"
    r"docker-compose[^/]*\.ya?ml|\.gitlab-ci\.yml|application[^/]*\.(ya?ml|properties)|appsettings[^/]*\.json|"
    r"\.env\.example|values[^/]*\.ya?ml|Chart\.yaml|[^/]*\.csproj)$|(^|/)\.github/workflows/|(^|/)(k8s|helm|deploy|charts)/")
ENTRADAS = re.compile(r"@SpringBootApplication|public static void main\(|if __name__ == ['\"]__main__['\"]|^func main\(\)"
                      r"|NestFactory\.create|app\.listen\(|createServer\(")


# --- Rutas y estado ----------------------------------------------------------------------------

def estado_repo(registro: dict, repo: str) -> dict:
    estado = registro.get("repos", {}).get(repo)
    if not estado or "automatica" not in estado:
        raise ErrorRadiografia(f"El repositorio '{repo}' no tiene parte automática. Ejecutar: make revisar P=<producto> R={repo}")
    return estado


def carpeta_revision(raiz: Path, producto: str, id_revision: str) -> Path:
    return raiz / "productos" / producto / "revisiones" / id_revision


def archivo_trabajo(raiz: Path, producto: str, id_revision: str, repo: str) -> Path:
    return carpeta_revision(raiz, producto, id_revision) / "revision" / f"{repo}.json"


def leer_trabajo(raiz: Path, producto: str, id_revision: str, repo: str) -> dict:
    archivo = archivo_trabajo(raiz, producto, id_revision, repo)
    return json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else {"evaluaciones": {}, "hallazgos": []}


def guardar_trabajo(raiz: Path, producto: str, id_revision: str, repo: str, trabajo: dict) -> None:
    archivo = archivo_trabajo(raiz, producto, id_revision, repo)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(trabajo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def contexto(raiz: Path, producto: str, repo: str) -> dict:
    """Todo lo necesario para trabajar sobre la revisión vigente de un repositorio."""
    registro = registro_hallazgos.cargar(raiz, producto)
    estado = estado_repo(registro, repo)
    destino = raiz / "productos" / producto / "repos" / repo
    if not destino.exists():
        raise ErrorRadiografia(f"No existe la copia de '{repo}'. Ejecutar: make revisar P={producto} R={repo}")
    return {"registro": registro, "estado": estado, "id_revision": estado["automatica"]["id"],
            "commit": estado["automatica"]["commit"], "rama": estado["rama"], "tipo": estado["tipo"], "destino": destino,
            "producto": producto, "repo": repo}


def lista_de_control(raiz: Path, tipo: str, producto: str | None = None, repo: str | None = None) -> list[dict]:
    """Fuentes y criterios que la revisión de código debe evaluar para un repositorio.

    Los elementos exceptuados por un ADR de producto vigente llevan `exceptuado` con el motivo: no se
    evalúan y el cierre los registra como NO APLICA.
    """
    elementos = []
    for clave, doc in sorted(leer_arquitectura_vigente(raiz).items()):
        elementos.append({"clave": clave, "fuente": clave, "criterio": None, "nivel": 1 if doc["tipo"] == "adr" else 2,
                          "titulo": doc["titulo"], "texto": doc["regla_rapida"] or "sin regla rápida: leer el documento",
                          "archivo": doc["archivo"], "modo": "vigente", "severidad": None})
    suspendidos = criterios_suspendidos(raiz, producto)
    if tipo == "propio":
        for id_eq, decision in decisiones_con_criterios(raiz).items():
            modo = "propuesta" if normalizar(decision["estado"]) == "propuesto" else "vigente"
            for id_criterio, criterio in decision["tabla"].items():
                if criterio["como"] != "revisión de código" or id_criterio in suspendidos.get(id_eq, []):
                    continue
                elementos.append({"clave": f"{id_eq}|{id_criterio}", "fuente": id_eq, "criterio": id_criterio, "nivel": 3,
                                  "titulo": decision["titulo"], "texto": criterio["texto"], "archivo": decision["archivo"],
                                  "modo": modo, "severidad": criterio["severidad"]})
        if producto:
            for id_adr, decision in leer_decisiones_producto(raiz, producto).items():
                repos_alcance = [r.strip() for r in decision["campos"].get("repositorios", "todos").split(",")]
                if (decision["tipo"] != "decision" or not decision["evaluado"]
                        or (normalizar(repos_alcance[0]) != "todos" and repo not in repos_alcance)):
                    continue
                modo = "propuesta" if normalizar(decision["estado"]) == "propuesto" else "vigente"
                for id_criterio, criterio in verificaciones.leer_criterios(decision["texto"]).items():
                    if id_criterio in suspendidos.get(id_adr, []):
                        continue
                    elementos.append({"clave": f"{id_adr}|{id_criterio}", "fuente": id_adr, "criterio": id_criterio, "nivel": 3,
                                      "titulo": decision["titulo"], "texto": criterio["texto"], "archivo": decision["archivo"],
                                      "modo": modo, "severidad": criterio["severidad"]})
    exceptuados = excepciones_activas(raiz, producto, repo) if producto and repo else {}
    for elemento in elementos:
        motivo = exceptuados.get(elemento["criterio"] or elemento["fuente"])
        if motivo:
            elemento["exceptuado"] = motivo
    return elementos


def clave_de(fuente: str, criterio: str | None) -> str:
    return f"{fuente}|{criterio}" if criterio else fuente


# --- Pendientes --------------------------------------------------------------------------------

def pendientes(raiz: Path, producto: str) -> list[dict]:
    datos = productos.leer_productos(raiz).get(producto)
    if datos is None:
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    registro = registro_hallazgos.cargar(raiz, producto)
    resultado = []
    for repo in productos.repos_de(datos):
        if repo.get("estado") != "activo":
            continue
        estado = registro.get("repos", {}).get(str(repo["id"]), {})
        automatica, codigo = estado.get("automatica"), estado.get("codigo")
        if not automatica:
            situacion = "falta la parte automática"
        elif not codigo or codigo["commit"] != automatica["commit"]:
            situacion = "falta la revisión de código"
        else:
            situacion = "al día"
        resultado.append({"repo": str(repo["id"]), "tipo": str(repo["tipo"]), "situacion": situacion,
                          "automatica": automatica, "codigo": codigo})
    return resultado


# --- Paquete de revisión -----------------------------------------------------------------------

def arbol(destino: Path, profundidad: int = 3) -> list[str]:
    conteo: Counter = Counter()
    for archivo in destino.rglob("*"):
        relativo = archivo.relative_to(destino)
        if archivo.is_file() and not set(relativo.parts) & verificaciones.CARPETAS_EXCLUIDAS:
            for nivel in range(1, min(len(relativo.parts), profundidad + 1)):
                conteo["/".join(relativo.parts[:nivel])] += 1
    return [f"{'  ' * (c.count('/'))}- {c.split('/')[-1]}/ ({n} archivos)" for c, n in sorted(conteo.items())]


# --- Revisión incremental ---------------------------------------------------------------------

def base_incremental(raiz: Path, producto: str, repo: str, ctx: dict, completa: bool) -> dict | None:
    """Revisión de código anterior contra la cual trabajar de forma incremental, o None para una completa."""
    codigo = ctx["estado"].get("codigo")
    if completa or not codigo or codigo["commit"] == ctx["commit"]:
        return None
    previo = leer_trabajo(raiz, producto, codigo["id"], repo)
    if not previo["evaluaciones"]:
        return None
    try:
        cambiados = sorted(set(git("diff", "--name-only", codigo["commit"], ctx["commit"], cwd=ctx["destino"]).splitlines()))
        total = len(git("ls-tree", "-r", "--name-only", ctx["commit"], cwd=ctx["destino"]).splitlines())
    except ErrorRadiografia:
        return None
    if total >= MINIMO_ARCHIVOS_UMBRAL and len(cambiados) > UMBRAL_INCREMENTAL * total:
        return None
    return {"id": codigo["id"], "commit": codigo["commit"], "cambiados": cambiados}


def heredables(raiz: Path, producto: str, repo: str, base: dict) -> dict[str, dict]:
    """Evaluaciones (y sus hallazgos) de la revisión base que no tocan archivos cambiados."""
    previo = leer_trabajo(raiz, producto, base["id"], repo)
    cambiados = set(base["cambiados"])
    resultado = {}
    for clave, evaluacion in previo["evaluaciones"].items():
        if evaluacion["resultado"] == "NO DETERMINADO":
            continue
        hallazgos_clave = [h for h in previo["hallazgos"] if clave_de(h["fuente"], h["criterio"]) == clave]
        archivos = {e["archivo"] for e in evaluacion.get("evidencia", [])}
        archivos |= {e["archivo"] for h in hallazgos_clave for e in h["evidencia"]}
        if not archivos & cambiados:
            resultado[clave] = {"evaluacion": evaluacion, "hallazgos": hallazgos_clave}
    return resultado


def generar_paquete(raiz: Path, producto: str, repo: str, completa: bool = False) -> Path:
    ctx = contexto(raiz, producto, repo)
    destino, registro = ctx["destino"], ctx["registro"]
    archivos = sorted(p.relative_to(destino).as_posix() for p in destino.rglob("*")
                      if p.is_file() and not set(p.relative_to(destino).parts) & verificaciones.CARPETAS_EXCLUIDAS)
    carpeta = carpeta_revision(raiz, producto, ctx["id_revision"])
    automatico = leer_json(carpeta / f"{repo}.json")
    abiertos = sorted((h for h in registro["hallazgos"].values()
                       if h["repo"] == repo and h["rama"] == ctx["rama"] and h["estado"] == "abierto" and h["origen"] != "revision"),
                      key=lambda h: (h["nivel"], h["id"]))
    lineas = [
        f"# Paquete de revisión: {repo} ({producto})",
        "",
        f"- Revisión: `{ctx['id_revision']}`",
        f"- Tipo: {ctx['tipo']} · Rama: {ctx['rama']} · Commit: `{ctx['commit'][:12]}`",
        f"- Stack detectado: {', '.join(automatico.get('stack', [])) or 'NO DETERMINADO'}",
        f"- Copia de trabajo (solo lectura): `productos/{producto}/repos/{repo}/`",
        "",
        "## Hallazgos automáticos ya registrados (no repetirlos)",
        "",
    ]
    lineas += [f"- {h['id']} · {h['criterio'] or h['fuente']} · {h['severidad']} · {h['titulo']}" for h in abiertos] or ["Ninguno."]
    lineas += ["", "## Mapa del repositorio", ""] + arbol(destino)
    configuracion = [a for a in archivos if ARCHIVOS_CONFIGURACION.search(a)]
    lineas += ["", "## Manifiestos, configuración y despliegue", ""] + ([f"- `{a}`" for a in configuracion] or ["Ninguno detectado."])
    entradas = verificaciones.buscar(destino, ENTRADAS, limite=10)
    lineas += ["", "## Puntos de entrada", ""] + ([f"- `{e['archivo']}:{e['linea']}`" for e in entradas] or ["Ninguno detectado."])
    lineas += ["", "## Señales en el código (archivo:línea)", ""]
    for nombre, patron in SENALES.items():
        coincidencias = verificaciones.buscar(destino, patron, limite=40)
        lineas += [f"### {nombre}", ""]
        lineas += [f"- `{c['archivo']}:{c['linea']}` {c['fragmento'][:100]}" for c in coincidencias] or ["Ninguna."]
        lineas.append("")

    base = base_incremental(raiz, producto, repo, ctx, completa)
    trabajo = leer_trabajo(raiz, producto, ctx["id_revision"], repo)
    trabajo["incremental"] = base
    guardar_trabajo(raiz, producto, ctx["id_revision"], repo, trabajo)
    heredados = heredables(raiz, producto, repo, base) if base else {}
    if base:
        anterior = carpeta_revision(raiz, producto, base["id"])
        for origen, destino_copia in ((anterior / "revision" / f"{repo}-asis.md", carpeta / "revision" / f"{repo}-asis.md"),
                                      (anterior / "borradores" / repo, carpeta / "borradores" / repo)):
            if origen.exists() and not destino_copia.exists():
                destino_copia.parent.mkdir(parents=True, exist_ok=True)
                (shutil.copytree if origen.is_dir() else shutil.copy2)(origen, destino_copia)
        lineas += ["## Revisión incremental", "",
                   f"Base: revisión `{base['id']}` (commit `{base['commit'][:12]}`). Cambiaron {len(base['cambiados'])} archivo(s). "
                   "El AS IS y los borradores C4 se copiaron de la revisión base: actualizar solo lo que cambió. "
                   "Las evaluaciones heredadas se conservan al cerrar; si un archivo cambiado afecta a alguna, incluirla en el lote.",
                   "", "Archivos cambiados:", ""]
        lineas += [f"- `{a}`" for a in base["cambiados"][:200]] + ([f"- … y {len(base['cambiados']) - 200} más"] if len(base["cambiados"]) > 200 else [])
        lineas.append("")

    fichas = terceros.para_repo(raiz, producto, repo)
    if fichas:
        lineas += ["## Terceros", "",
                   "Producto comprado e integraciones que corresponden a este repositorio. Contrastarlos con el código: "
                   "integraciones del código sin ficha (EQ-004.5, EQ-006.6), timeouts frente al p95 del tercero (EQ-002.1), "
                   "política ante falla declarada frente a la implementada (EQ-002.4; la ficha cuenta como documentación de "
                   "la política) y uso de sus contratos, códigos de error y límites. Buscar en su documentación con "
                   f"`.venv/bin/python herramientas/terceros.py buscar {producto} \"<palabras>\"` y citarla como "
                   "`terceros/<id>/docs/<archivo>`.", "",
                   "| Tercero | Rol | Protocolo | Autenticación | p95 (ms) | Límite (rps) | Política ante falla | Contrato | Documentos |",
                   "|---|---|---|---|---|---|---|---|---|"]
        for f in fichas:
            sla, limites = f.get("sla") or {}, f.get("limites") or {}
            documentos = terceros.documentos_indexados(raiz, producto, f["id"])
            lineas.append(f"| `{f['id']}` {f.get('nombre') or ''} | {f.get('rol')} | {f.get('protocolo')} | {f.get('autenticacion')} "
                          f"| {sla.get('p95_ms') if sla.get('p95_ms') is not None else '—'} "
                          f"| {limites.get('rps') if limites.get('rps') is not None else '—'} | {f.get('politica_ante_falla')} "
                          f"| {('terceros/' + f['id'] + '/docs/' + f['contrato']) if f.get('contrato') else '—'} "
                          f"| {sum(1 for d in documentos.values() if d['estado'] == 'indexado')} indexado(s) |")
        lineas.append("")

    control = lista_de_control(raiz, ctx["tipo"], producto, repo)
    exceptuados = [e for e in control if e.get("exceptuado")]
    heredados_control = [e for e in control if not e.get("exceptuado") and e["clave"] in heredados]
    control = [e for e in control if not e.get("exceptuado") and e["clave"] not in heredados]
    lineas += ["## Qué evaluar", "",
               "Cada elemento se evalúa en el lote (CUMPLE, NO CUMPLE, NO APLICA o NO DETERMINADO). "
               "Todo NO CUMPLE requiere al menos un hallazgo con la misma fuente y criterio.", ""]
    for nivel, titulo in ((1, "Nivel 1: ADR de arquitectura vigentes"), (2, "Nivel 2: estándares de arquitectura vigentes"),
                          (3, "Nivel 3: criterios de revisión de código de las decisiones del equipo y del producto")):
        del_nivel = [e for e in control if e["nivel"] == nivel]
        lineas += [f"### {titulo}", ""]
        if not del_nivel:
            lineas += ["Nada que evaluar en este nivel.", ""]
            continue
        lineas += ["| Fuente | Criterio | Título | Regla o criterio | Modo |", "|---|---|---|---|---|"]
        lineas += [f"| `{e['fuente']}` | {e['criterio'] or '—'} | {e['titulo']} | {e['texto'].replace('|', '/')} | {e['modo']} |"
                   for e in del_nivel] + [""]
    if heredados_control:
        lineas += [f"### Heredados de la revisión {base['id']} (no evaluar salvo que un cambio los afecte)", "",
                   "| Fuente | Criterio | Resultado anterior |", "|---|---|---|"]
        lineas += [f"| `{e['fuente']}` | {e['criterio'] or '—'} | {heredados[e['clave']]['evaluacion']['resultado']} |"
                   for e in heredados_control] + [""]
    if exceptuados:
        lineas += ["### No evaluar: exceptuados por un ADR del producto", "",
                   "Se registran solos como NO APLICA al cerrar.", ""]
        lineas += [f"- `{e['criterio'] or e['fuente']}`: {e['exceptuado']}" for e in exceptuados] + [""]
    pendientes_excepcion = excepciones_pendientes(raiz, producto, repo)
    if pendientes_excepcion:
        lineas += ["### Excepciones que no surten efecto (evaluar normalmente)", ""]
        lineas += [f"- `{clave}`: {motivo}" for clave, motivo in sorted(pendientes_excepcion.items())] + [""]
    if ctx["tipo"] != "propio":
        lineas += [f"> Repositorio de tipo `{ctx['tipo']}`: las decisiones del equipo no aplican. "
                   "Describir el AS IS con foco en integraciones, contratos y configuración.", ""]

    lineas += [
        "## Entregables",
        "",
        f"1. AS IS: escribir `productos/{producto}/revisiones/{ctx['id_revision']}/revision/{repo}-asis.md` con estas secciones (`##`): "
        + ", ".join(SECCIONES_AS_IS) + ". Cada afirmación con su etiqueta de evidencia.",
        f"2. C4 inferido: `productos/{producto}/revisiones/{ctx['id_revision']}/borradores/{repo}/c4-contexto.md` y `c4-contenedores.md`, "
        "según las plantillas de `equipo/plantillas/`. Lo que no se pueda deducir, como NO DETERMINADO.",
        f"3. Un único lote con todas las evaluaciones y hallazgos: `productos/{producto}/revisiones/{ctx['id_revision']}/revision/{repo}-lote.yaml`, "
        f"registrado con `.venv/bin/python herramientas/revision.py registrar {producto} {repo}`.",
        f"4. Cerrar: `.venv/bin/python herramientas/revision.py cerrar {producto} {repo} --archivos-leidos <N>`.",
    ]
    archivo = carpeta / "paquetes" / f"{repo}.md"
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return archivo


# --- Validaciones ------------------------------------------------------------------------------

def leer_evidencia(texto: str) -> dict:
    coincidencia = re.fullmatch(r"(.+?):(\d+)", texto.strip())
    if not coincidencia:
        raise ErrorRadiografia(f"Evidencia '{texto}' inválida; formato: ruta:línea (por ejemplo src/main/App.java:42).")
    return {"archivo": coincidencia.group(1).lstrip("./"), "linea": int(coincidencia.group(2))}


def validar_evidencia(destino: Path, evidencia: dict, fragmento: str | None = None) -> None:
    archivo = destino / evidencia["archivo"]
    if not archivo.is_file() or not archivo.resolve().is_relative_to(destino.resolve()):
        raise ErrorRadiografia(f"El archivo '{evidencia['archivo']}' no existe en el commit revisado.")
    lineas = archivo.read_text(encoding="utf-8", errors="replace").splitlines()
    if not 1 <= evidencia["linea"] <= len(lineas):
        raise ErrorRadiografia(f"La línea {evidencia['linea']} no existe en '{evidencia['archivo']}' ({len(lineas)} líneas).")
    if fragmento is not None:
        inicio = max(0, evidencia["linea"] - 1 - VENTANA_FRAGMENTO)
        ventana = " ".join(lineas[inicio:evidencia["linea"] + VENTANA_FRAGMENTO + 2])
        if " ".join(fragmento.split()) not in " ".join(ventana.split()):
            raise ErrorRadiografia(f"El fragmento no aparece cerca de {evidencia['archivo']}:{evidencia['linea']}. "
                                   "Copiarlo tal como está en el código.")


def elemento_de_control(raiz: Path, ctx: dict, fuente: str, criterio: str | None, control: dict | None = None) -> dict:
    if control is None:
        control = {e["clave"]: e for e in lista_de_control(raiz, ctx["tipo"], ctx["producto"], ctx["repo"])}
    clave = clave_de(fuente, criterio)
    if clave not in control:
        if re.match(r"^ADR-[A-Z]{2,5}-\d{3}$", fuente) and not criterio:
            raise ErrorRadiografia("Para una decisión del equipo o del producto, indicar --criterio (por ejemplo EQ-002.1).")
        raise ErrorRadiografia(f"'{clave}' no es una fuente vigente ni un criterio de revisión de código aplicable a este "
                               "repositorio (ver la sección \"Qué evaluar\" del paquete).")
    if control[clave].get("exceptuado"):
        raise ErrorRadiografia(f"'{clave}' no se evalúa: {control[clave]['exceptuado']}.")
    return control[clave]


def texto_fuente(raiz: Path, elemento: dict) -> str:
    return (raiz / elemento["archivo"]).read_text(encoding="utf-8", errors="replace")


def validar_cita_tercero(raiz: Path, producto: str, documento: str | None, cita: str | None) -> dict | None:
    """Valida una cita de la documentación de un tercero y la devuelve normalizada, o None si no hay."""
    if not documento and not cita:
        return None
    if not documento or not cita:
        raise ErrorRadiografia("el documento y la cita del tercero se indican juntos.")
    if not cita_existe(cita, terceros.texto_de(raiz, producto, documento)):
        raise ErrorRadiografia(f"la cita del tercero no aparece textualmente en '{documento}'. Copiarla tal como está escrita.")
    return {"documento": documento, "texto": cita.strip()}


# --- Registro de evaluaciones y hallazgos ------------------------------------------------------

def construir_evaluacion(raiz: Path, ctx: dict, fuente: str, criterio: str | None, resultado: str, motivo: str,
                         evidencias: list[str], cita_documento: str | None, documento_tercero: str | None = None,
                         cita_tercero: str | None = None, control: dict | None = None) -> tuple[str, dict]:
    """Valida una evaluación y la devuelve como (clave, datos). Lanza ErrorRadiografia si algo no es válido."""
    if resultado not in RESULTADOS:
        raise ErrorRadiografia(f"Resultado '{resultado}' inválido; valores válidos: {', '.join(RESULTADOS)}.")
    if not motivo or not str(motivo).strip():
        raise ErrorRadiografia("el motivo es obligatorio.")
    elemento = elemento_de_control(raiz, ctx, fuente, criterio, control)
    lista = [leer_evidencia(e) for e in evidencias]
    for evidencia in lista:
        validar_evidencia(ctx["destino"], evidencia)
    if cita_documento and not cita_existe(cita_documento, texto_fuente(raiz, elemento)):
        raise ErrorRadiografia("la cita del documento no aparece textualmente en el documento. Copiarla tal como está escrita.")
    cita_del_tercero = validar_cita_tercero(raiz, ctx["producto"], documento_tercero, cita_tercero)
    return elemento["clave"], {
        "fuente": fuente, "criterio": criterio, "nivel": elemento["nivel"], "titulo": elemento["titulo"],
        "resultado": resultado, "motivo": str(motivo).strip(), "evidencia": lista, "cita_documento": cita_documento,
        "cita_tercero": cita_del_tercero, "modo": elemento["modo"],
    }


def construir_hallazgo(raiz: Path, ctx: dict, fuente: str, criterio: str | None, categoria: str, severidad: str,
                       titulo: str, detalle: str, evidencias: list[str], fragmento: str, cita_documento: str | None,
                       documento_tercero: str | None = None, cita_tercero: str | None = None,
                       control: dict | None = None) -> dict:
    """Valida un hallazgo y lo devuelve listo para registrar. Lanza ErrorRadiografia si algo no es válido."""
    if categoria not in CATEGORIAS:
        raise ErrorRadiografia(f"Categoría '{categoria}' inválida; valores válidos: {', '.join(CATEGORIAS)}.")
    if severidad not in SEVERIDADES:
        raise ErrorRadiografia(f"Severidad '{severidad}' inválida; valores válidos: {', '.join(SEVERIDADES)}.")
    if not evidencias:
        raise ErrorRadiografia("un hallazgo requiere al menos una evidencia ruta:línea.")
    if not fragmento or len(str(fragmento).strip()) < 5:
        raise ErrorRadiografia("el fragmento es obligatorio: el código citado tal como aparece en la primera evidencia.")
    if not titulo or not detalle:
        raise ErrorRadiografia("un hallazgo requiere título y detalle.")
    elemento = elemento_de_control(raiz, ctx, fuente, criterio, control)
    lista = [leer_evidencia(e) for e in evidencias]
    validar_evidencia(ctx["destino"], lista[0], str(fragmento))
    for evidencia in lista[1:]:
        validar_evidencia(ctx["destino"], evidencia)
    if categoria == "incumplimiento" and not cita_documento:
        raise ErrorRadiografia("un hallazgo de categoría 'incumplimiento' requiere la cita del documento incumplido.")
    if cita_documento and not cita_existe(cita_documento, texto_fuente(raiz, elemento)):
        raise ErrorRadiografia("la cita del documento no aparece textualmente en el documento. Copiarla tal como está escrita.")
    cita_del_tercero = validar_cita_tercero(raiz, ctx["producto"], documento_tercero, cita_tercero)
    return {
        "huella": registro_hallazgos.huella(ctx["repo"], ctx["rama"], fuente, criterio, lista[0]["archivo"],
                                            texto_comparable(str(fragmento))),
        "nivel": elemento["nivel"], "fuente": fuente, "criterio": criterio, "categoria": categoria, "severidad": severidad,
        "titulo": str(titulo).strip(), "detalle": str(detalle).strip(), "evidencia": lista, "fragmento": str(fragmento).strip(),
        "cita_documento": cita_documento, "cita_tercero": cita_del_tercero, "origen": "revision", "modo": elemento["modo"],
    }


def agregar_hallazgo(trabajo: dict, hallazgo: dict) -> None:
    """Agrega un hallazgo al trabajo; si ya hay uno con la misma huella, lo reemplaza."""
    trabajo["hallazgos"] = [h for h in trabajo["hallazgos"] if h["huella"] != hallazgo["huella"]] + [hallazgo]


def evaluar(raiz: Path, producto: str, repo: str, fuente: str, criterio: str | None, resultado: str, motivo: str,
            evidencias: list[str], cita_documento: str | None, documento_tercero: str | None = None,
            cita_tercero: str | None = None) -> None:
    ctx = contexto(raiz, producto, repo)
    clave, datos = construir_evaluacion(raiz, ctx, fuente, criterio, resultado, motivo, evidencias, cita_documento,
                                        documento_tercero, cita_tercero)
    trabajo = leer_trabajo(raiz, producto, ctx["id_revision"], repo)
    trabajo["evaluaciones"][clave] = datos
    guardar_trabajo(raiz, producto, ctx["id_revision"], repo, trabajo)


def registrar_hallazgo(raiz: Path, producto: str, repo: str, fuente: str, criterio: str | None, categoria: str,
                       severidad: str, titulo: str, detalle: str, evidencias: list[str], fragmento: str,
                       cita_documento: str | None, documento_tercero: str | None = None,
                       cita_tercero: str | None = None) -> None:
    ctx = contexto(raiz, producto, repo)
    hallazgo = construir_hallazgo(raiz, ctx, fuente, criterio, categoria, severidad, titulo, detalle, evidencias,
                                  fragmento, cita_documento, documento_tercero, cita_tercero)
    trabajo = leer_trabajo(raiz, producto, ctx["id_revision"], repo)
    agregar_hallazgo(trabajo, hallazgo)
    guardar_trabajo(raiz, producto, ctx["id_revision"], repo, trabajo)


def archivo_lote(raiz: Path, producto: str, id_revision: str, repo: str) -> Path:
    return carpeta_revision(raiz, producto, id_revision) / "revision" / f"{repo}-lote.yaml"


def registrar_lote(raiz: Path, producto: str, repo: str, archivo: Path | None = None) -> dict:
    """Valida y registra de una vez todas las evaluaciones y hallazgos de un archivo YAML o JSON.

    Si algún elemento no es válido, no se registra nada y se informan todos los errores juntos.
    """
    ctx = contexto(raiz, producto, repo)
    archivo = archivo or archivo_lote(raiz, producto, ctx["id_revision"], repo)
    if not archivo.exists():
        raise ErrorRadiografia(f"No existe el archivo de lote {archivo}.")
    try:
        texto = archivo.read_text(encoding="utf-8")
        datos = json.loads(texto) if archivo.suffix == ".json" else yaml.safe_load(texto)
    except (json.JSONDecodeError, yaml.YAMLError) as error:
        raise ErrorRadiografia(f"El lote no es un YAML o JSON válido: {error}") from error
    datos = datos or {}
    control = {e["clave"]: e for e in lista_de_control(raiz, ctx["tipo"], producto, repo)}
    errores, evaluaciones, hallazgos = [], {}, []

    def como_lista(valor) -> list[str]:
        return [str(v) for v in (valor if isinstance(valor, list) else [valor] if valor else [])]

    for indice, e in enumerate(datos.get("evaluaciones") or [], start=1):
        referencia = f"evaluaciones[{indice}] ({clave_de(str(e.get('fuente')), e.get('criterio'))})"
        try:
            clave, evaluacion = construir_evaluacion(
                raiz, ctx, str(e.get("fuente", "")), e.get("criterio"), str(e.get("resultado", "")), e.get("motivo"),
                como_lista(e.get("evidencia")), e.get("cita_documento"), e.get("documento_tercero"),
                e.get("cita_tercero"), control)
            evaluaciones[clave] = evaluacion
        except ErrorRadiografia as error:
            errores.append(f"{referencia}: {error}")
    for indice, h in enumerate(datos.get("hallazgos") or [], start=1):
        referencia = f"hallazgos[{indice}] ({h.get('titulo', 'sin título')})"
        try:
            hallazgos.append(construir_hallazgo(
                raiz, ctx, str(h.get("fuente", "")), h.get("criterio"), str(h.get("categoria", "")),
                str(h.get("severidad", "")), h.get("titulo"), h.get("detalle"), como_lista(h.get("evidencia")),
                h.get("fragmento"), h.get("cita_documento"), h.get("documento_tercero"), h.get("cita_tercero"),
                control))
        except ErrorRadiografia as error:
            errores.append(f"{referencia}: {error}")
    if errores:
        raise ErrorRadiografia(f"El lote tiene {len(errores)} error(es); no se registró nada:\n  - " + "\n  - ".join(errores))

    trabajo = leer_trabajo(raiz, producto, ctx["id_revision"], repo)
    trabajo["evaluaciones"].update(evaluaciones)
    for hallazgo in hallazgos:
        agregar_hallazgo(trabajo, hallazgo)
    guardar_trabajo(raiz, producto, ctx["id_revision"], repo, trabajo)
    pendientes_lote = [c for c, e in control.items() if not e.get("exceptuado") and c not in trabajo["evaluaciones"]]
    return {"evaluaciones": len(evaluaciones), "hallazgos": len(hallazgos), "pendientes": pendientes_lote}


# --- Cierre ------------------------------------------------------------------------------------

def cerrar(raiz: Path, producto: str, repo: str, archivos_leidos: int | None) -> dict:
    ctx = contexto(raiz, producto, repo)
    trabajo = leer_trabajo(raiz, producto, ctx["id_revision"], repo)
    control = lista_de_control(raiz, ctx["tipo"], producto, repo)
    if trabajo.get("incremental"):
        base = trabajo["incremental"]
        for clave, heredado in heredables(raiz, producto, repo, base).items():
            if clave in trabajo["evaluaciones"] or clave not in {e["clave"] for e in control}:
                continue
            trabajo["evaluaciones"][clave] = {**heredado["evaluacion"], "heredada_de": base["id"],
                                              "motivo": f"{heredado['evaluacion']['motivo']} (heredada de {base['id']})"}
            for hallazgo in heredado["hallazgos"]:
                if all(h["huella"] != hallazgo["huella"] for h in trabajo["hallazgos"]):
                    trabajo["hallazgos"].append(hallazgo)
    for e in control:
        if e.get("exceptuado"):
            trabajo["evaluaciones"][e["clave"]] = {
                "fuente": e["fuente"], "criterio": e["criterio"], "nivel": e["nivel"], "titulo": e["titulo"],
                "resultado": "NO APLICA", "motivo": e["exceptuado"], "evidencia": [], "cita_documento": None, "modo": e["modo"]}
    guardar_trabajo(raiz, producto, ctx["id_revision"], repo, trabajo)
    faltantes = [e["clave"] for e in control if e["clave"] not in trabajo["evaluaciones"]]
    if faltantes:
        raise ErrorRadiografia(f"Faltan {len(faltantes)} evaluación(es): {', '.join(faltantes)}.")
    claves_con_hallazgo = {clave_de(h["fuente"], h["criterio"]) for h in trabajo["hallazgos"]}
    sin_hallazgo = [c for c, e in trabajo["evaluaciones"].items() if e["resultado"] == "NO CUMPLE" and c not in claves_con_hallazgo]
    if sin_hallazgo:
        raise ErrorRadiografia(f"Evaluaciones NO CUMPLE sin hallazgo registrado: {', '.join(sin_hallazgo)}.")
    carpeta = carpeta_revision(raiz, producto, ctx["id_revision"])
    asis = carpeta / "revision" / f"{repo}-asis.md"
    if not asis.exists():
        raise ErrorRadiografia(f"Falta el AS IS: {asis.relative_to(raiz)}.")
    texto_asis = asis.read_text(encoding="utf-8")
    encabezados = {normalizar(l.lstrip("#").strip()) for l in texto_asis.splitlines() if l.startswith("## ")}
    sin_seccion = [s for s in SECCIONES_AS_IS if normalizar(s) not in encabezados]
    if sin_seccion:
        raise ErrorRadiografia(f"Al AS IS le faltan secciones: {', '.join(sin_seccion)}.")
    import lenguaje
    avisos = [f"lenguaje: {a}" for a in lenguaje.formatear(lenguaje.revisar(texto_asis), asis.name)]
    for nombre in ("c4-contexto.md", "c4-contenedores.md"):
        if not (carpeta / "borradores" / repo / nombre).exists():
            avisos.append(f"falta el borrador {nombre}")

    registro = ctx["registro"]
    hoy = date.today().isoformat()
    es_linea_base = not any(h["repo"] == repo and h["rama"] == ctx["rama"] and h["origen"] == "revision"
                            for h in registro["hallazgos"].values())
    resumen = registro_hallazgos.aplicar(registro, repo, ctx["rama"], {"revision"}, trabajo["hallazgos"],
                                         ctx["id_revision"], hoy, es_linea_base)
    absorber_sonar(registro, repo, ctx["rama"])
    ctx["estado"]["codigo"] = {"id": ctx["id_revision"], "commit": ctx["commit"], "fecha": hoy,
                               "archivos_leidos": archivos_leidos}
    registro_hallazgos.guardar(raiz, producto, registro)
    escribir_ficha_revision(raiz, producto, repo, ctx, trabajo, texto_asis, registro)
    import indices
    indices.indice_producto(raiz, producto)
    return {"resumen": resumen, "avisos": avisos, "evaluaciones": Counter(e["resultado"] for e in trabajo["evaluaciones"].values())}


def absorber_sonar(registro: dict, repo: str, rama: str) -> None:
    """Un issue de Sonar en la misma ubicación que un hallazgo de nivel superior se reporta una sola vez."""
    revision = [h for h in registro["hallazgos"].values()
                if h["repo"] == repo and h["rama"] == rama and h["estado"] == "abierto" and h["origen"] == "revision"]
    for h in registro["hallazgos"].values():
        if h["repo"] != repo or h["rama"] != rama or h["origen"] != "sonar":
            continue
        h["absorbido_por"] = next((r["id"] for r in revision for e in r["evidencia"] for es in h["evidencia"]
                                   if e["archivo"] == es["archivo"] and es.get("linea") and abs(e["linea"] - es["linea"]) <= 2), None)


def escribir_ficha_revision(raiz: Path, producto: str, repo: str, ctx: dict, trabajo: dict, texto_asis: str, registro: dict) -> None:
    archivo = raiz / "productos" / producto / "as-is" / f"{repo}.md"
    texto = archivo.read_text(encoding="utf-8") if archivo.exists() else f"# {repo}: ficha AS IS\n"
    cuerpo_asis = re.sub(r"^#\s.*\n", "", texto_asis.strip() + "\n", count=1)
    texto = reemplazar_bloque(texto, MARCA_REVISION, f"## Revisión de código\n\n> Revisión `{ctx['id_revision']}` "
                              f"sobre el commit `{ctx['commit'][:12]}`.\n\n" + cuerpo_asis)
    hallazgos_por_clave: dict[str, list[str]] = {}
    for h in registro["hallazgos"].values():
        if h["repo"] == repo and h["rama"] == ctx["rama"] and h["estado"] == "abierto" and h["origen"] == "revision":
            hallazgos_por_clave.setdefault(clave_de(h["fuente"], h["criterio"]), []).append(h["id"])
    lineas = ["## Comparación con lo decidido", "", "> Sección generada al cerrar la revisión de código. No se edita a mano.", ""]
    for nivel, titulo in ((1, "Nivel 1: ADR de arquitectura"), (2, "Nivel 2: estándares de arquitectura"),
                          (3, "Nivel 3: decisiones del equipo y del producto (revisión de código)")):
        evaluaciones = sorted(((c, e) for c, e in trabajo["evaluaciones"].items() if e["nivel"] == nivel), key=lambda x: x[0])
        lineas += [f"### {titulo}", ""]
        if not evaluaciones:
            lineas += ["Nada que evaluar.", ""]
            continue
        lineas += ["| Fuente | Resultado | Modo | Motivo | Hallazgos |", "|---|---|---|---|---|"]
        for clave, e in evaluaciones:
            lineas.append(f"| {e['criterio'] or e['fuente']} | {SIMBOLOS[e['resultado']]} {e['resultado']} | {e['modo']} "
                          f"| {e['motivo'].replace('|', '/')} | {', '.join(hallazgos_por_clave.get(clave, [])) or '—'} |")
        lineas.append("")
    lineas.append(f"Veredicto: **{veredicto(registro, repo, ctx['rama'])}**")
    texto = reemplazar_bloque(texto, MARCA_COMPARACION, "\n".join(lineas))
    archivo.write_text(texto, encoding="utf-8")


# --- Producto ----------------------------------------------------------------------------------

def consolidar_producto(raiz: Path, producto: str, narrativa: Path | None) -> Path:
    estados = pendientes(raiz, producto)
    registro = registro_hallazgos.cargar(raiz, producto)
    matriz: dict[str, dict[str, str]] = {}
    titulos: dict[str, tuple[int, str]] = {}
    for estado in estados:
        codigo = estado["codigo"]
        if not codigo:
            continue
        trabajo = leer_trabajo(raiz, producto, codigo["id"], estado["repo"])
        for clave, e in trabajo["evaluaciones"].items():
            matriz.setdefault(clave, {})[estado["repo"]] = e["resultado"]
            titulos[clave] = (e["nivel"], e["criterio"] or e["fuente"])
    repos = [e["repo"] for e in estados]
    lineas = [
        "## Repositorios", "",
        "> Sección generada por `herramientas/revision.py producto`. No se edita a mano.", "",
        "| Repositorio | Tipo | Revisión de código | Commit | Veredicto |", "|---|---|---|---|---|",
    ]
    for e in estados:
        codigo = e["codigo"]
        rama = registro.get("repos", {}).get(e["repo"], {}).get("rama", "")
        lineas.append(f"| [{e['repo']}]({e['repo']}.md) | {e['tipo']} | {e['situacion']} "
                      f"| {('`' + codigo['commit'][:12] + '`') if codigo else '—'} | {veredicto(registro, e['repo'], rama) if codigo else '—'} |")
    lineas += ["", "## Matriz de cumplimiento", "",
               "✅ cumple · ❌ no cumple · ➖ no aplica · ❔ no determinado · (vacío) sin revisar", "",
               "| Nivel | Fuente | " + " | ".join(repos) + " |", "|---|---|" + "---|" * len(repos)]
    for clave in sorted(matriz, key=lambda c: titulos[c]):
        nivel, nombre = titulos[clave]
        lineas.append(f"| {nivel} | {nombre} | " + " | ".join(SIMBOLOS.get(matriz[clave].get(r, ""), "") for r in repos) + " |")
    abiertos = [h for h in registro["hallazgos"].values() if h["estado"] == "abierto" and not h.get("absorbido_por")]
    por_fuente = Counter((h["nivel"], h["criterio"] or h["fuente"]) for h in abiertos if h["severidad"] in ("bloqueante", "alta"))
    lineas += ["", "## Brechas principales (hallazgos bloqueantes y altos abiertos)", ""]
    lineas += [f"- Nivel {n} · {f}: {c} hallazgo(s)" for (n, f), c in sorted(por_fuente.items(), key=lambda x: (-x[1], x[0]))] or ["Ninguna."]

    archivo = raiz / "productos" / producto / "as-is" / "PRODUCTO.md"
    archivo.parent.mkdir(parents=True, exist_ok=True)
    texto = archivo.read_text(encoding="utf-8") if archivo.exists() else f"# {producto}: AS IS del producto\n"
    texto = reemplazar_bloque(texto, MARCA_PRODUCTO_AUTOMATICO, "\n".join(lineas))
    if narrativa is not None:
        texto = reemplazar_bloque(texto, MARCA_PRODUCTO_NARRATIVA, narrativa.read_text(encoding="utf-8"))
    elif MARCA_PRODUCTO_NARRATIVA[0] not in texto:
        texto = reemplazar_bloque(texto, MARCA_PRODUCTO_NARRATIVA,
                                  "## Visión del producto\n\nPendiente: completar con /revisar cuando todos los repositorios tengan revisión de código.")
    archivo.write_text(texto, encoding="utf-8")
    return archivo


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Revisión de código de /revisar.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("pendientes")
    p.add_argument("producto")
    p = sub.add_parser("paquete")
    p.add_argument("producto")
    p.add_argument("repo")
    p.add_argument("--completa", action="store_true", help="revisión completa aunque haya una revisión anterior")
    p = sub.add_parser("evaluar")
    p.add_argument("producto")
    p.add_argument("repo")
    p.add_argument("--fuente", required=True)
    p.add_argument("--criterio")
    p.add_argument("--resultado", required=True, choices=RESULTADOS)
    p.add_argument("--motivo", required=True)
    p.add_argument("--evidencia", action="append", default=[])
    p.add_argument("--cita-documento")
    p.add_argument("--documento-tercero")
    p.add_argument("--cita-tercero")
    p = sub.add_parser("hallazgo")
    p.add_argument("producto")
    p.add_argument("repo")
    p.add_argument("--fuente", required=True)
    p.add_argument("--criterio")
    p.add_argument("--categoria", required=True, choices=CATEGORIAS)
    p.add_argument("--severidad", required=True, choices=SEVERIDADES)
    p.add_argument("--titulo", required=True)
    p.add_argument("--detalle", required=True)
    p.add_argument("--evidencia", action="append", default=[])
    p.add_argument("--fragmento", required=True)
    p.add_argument("--cita-documento")
    p.add_argument("--documento-tercero")
    p.add_argument("--cita-tercero")
    p = sub.add_parser("registrar")
    p.add_argument("producto")
    p.add_argument("repo")
    p.add_argument("--archivo", type=Path, help="por defecto: revisiones/<revisión>/revision/<repo>-lote.yaml")
    p = sub.add_parser("cerrar")
    p.add_argument("producto")
    p.add_argument("repo")
    p.add_argument("--archivos-leidos", type=int)
    p = sub.add_parser("producto")
    p.add_argument("producto")
    p.add_argument("--narrativa", type=Path)
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()

    try:
        if o.accion == "pendientes":
            for e in pendientes(raiz, o.producto):
                print(f"  {e['repo']} ({e['tipo']}): {e['situacion']}")
        elif o.accion == "paquete":
            print(f"Paquete: {generar_paquete(raiz, o.producto, o.repo, o.completa).relative_to(raiz)}")
        elif o.accion == "evaluar":
            evaluar(raiz, o.producto, o.repo, o.fuente, o.criterio, o.resultado, o.motivo, o.evidencia, o.cita_documento,
                    o.documento_tercero, o.cita_tercero)
            print(f"Evaluado: {clave_de(o.fuente, o.criterio)} = {o.resultado}")
        elif o.accion == "hallazgo":
            registrar_hallazgo(raiz, o.producto, o.repo, o.fuente, o.criterio, o.categoria, o.severidad, o.titulo,
                               o.detalle, o.evidencia, o.fragmento, o.cita_documento, o.documento_tercero, o.cita_tercero)
            print(f"Hallazgo registrado: {clave_de(o.fuente, o.criterio)} · {o.severidad} · {o.titulo}")
        elif o.accion == "registrar":
            r = registrar_lote(raiz, o.producto, o.repo, o.archivo)
            print(f"Lote registrado: {r['evaluaciones']} evaluación(es) y {r['hallazgos']} hallazgo(s).")
            if r["pendientes"]:
                print(f"Faltan {len(r['pendientes'])} elemento(s) por evaluar: {', '.join(r['pendientes'])}")
        elif o.accion == "cerrar":
            r = cerrar(raiz, o.producto, o.repo, o.archivos_leidos)
            s = r["resumen"]
            print(f"Revisión de código de '{o.repo}' cerrada. Evaluaciones: {dict(r['evaluaciones'])}. "
                  f"Hallazgos nuevos {len(s['nuevos'])}, abiertos {len(s['abiertos'])}, corregidos {len(s['corregidos'])}, "
                  f"reaparecidos {len(s['reaparecidos'])}.")
            for aviso in r["avisos"]:
                print(f"  Aviso: {aviso}")
        elif o.accion == "producto":
            print(f"Generado: {consolidar_producto(raiz, o.producto, o.narrativa).relative_to(raiz)}")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
