"""Verificaciones automáticas de los criterios de las decisiones del equipo (ADR-EQ).

Cubre los criterios cuya columna "Cómo" es `automática` o `automática + revisión de código`.
Cada verificación devuelve un resultado por criterio (CUMPLE, NO CUMPLE, NO APLICA o
NO DETERMINADO) y los hallazgos con evidencia `ruta:línea`. Los criterios de `revisión de código`
quedan para la parte de criterio de /revisar.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from comun import normalizar
from hallazgos import huella

CUMPLE, NO_CUMPLE, NO_APLICA, NO_DETERMINADO = "CUMPLE", "NO CUMPLE", "NO APLICA", "NO DETERMINADO"

CARPETAS_EXCLUIDAS = {".git", "node_modules", "target", "build", "dist", "vendor", ".venv", "venv",
                      "__pycache__", ".gradle", ".idea", "coverage", ".next", "out"}
CARPETAS_PRUEBA = {"test", "tests", "__tests__", "spec", "e2e", "testing"}
EXTENSIONES_CODIGO = {".java", ".kt", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".py", ".go", ".cs"}
TAMANO_MAXIMO = 1_000_000

CATEGORIAS = {"ADR-EQ-001": "seguridad", "ADR-EQ-003": "diseño", "ADR-EQ-004": "documentacion",
              "ADR-EQ-006": "documentacion", "ADR-EQ-007": "documentacion"}
# Decisiones cuyos criterios automáticos verifican el código de un repositorio. Las demás (por ejemplo,
# ADR-EQ-008 y ADR-EQ-009, sobre historias y MR) no se evalúan en la revisión de un repositorio.
DECISIONES_DE_CODIGO = set(CATEGORIAS)

SECCIONES_README = (
    ("Resumen y propósito", ("resumen", "proposito", "descripcion")),
    ("Contexto de negocio y responsables", ("contexto", "responsable")),
    ("Arquitectura", ("arquitectura",)),
    ("Stack y versiones", ("stack", "tecnologia", "versiones")),
    ("Cómo se ejecuta en local", ("local", "ejecuta", "ejecucion", "instalacion", "como empezar")),
    ("Configuración", ("configuracion", "variables")),
    ("Integraciones", ("integracion",)),
    ("Contratos", ("contrato", "api")),
    ("Entornos y despliegue", ("entorno", "despliegue", "deploy")),
    ("Observabilidad", ("observabilidad", "monitoreo", "logs", "metricas")),
    ("Operación y resolución de problemas", ("operacion", "problemas", "troubleshooting", "soporte")),
    ("Decisiones", ("decisiones", "adr")),
    ("Glosario", ("glosario",)),
)

SENALES_API = re.compile(
    r"@(RestController|Controller|RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\b"
    r"|@(Get|Post|Put|Delete|Patch)\(\s*['\"]?"
    r"|\b(app|router|server)\.(get|post|put|delete|patch)\(\s*['\"]/"
    r"|@(app|router)\.(get|post|put|delete|patch)\("
    r"|\b(r|router|e|g)\.(GET|POST|PUT|DELETE|PATCH)\(\s*\"/"
    r"|\[(HttpGet|HttpPost|HttpPut|HttpDelete|ApiController)\b"
    r"|\bRouterFunctions?\b|\bRequestPredicates\.(GET|POST|PUT|DELETE|PATCH)\("
    r"|\.(GET|POST|PUT|DELETE|PATCH)\(\s*[\"'/]"
)
SENALES_EVENTOS = re.compile(
    r"@(KafkaListener|RabbitListener|JmsListener|SqsListener|EventPattern|MessagePattern)\b"
    r"|\b(KafkaTemplate|RabbitTemplate|JmsTemplate|StreamBridge)\b"
    r"|\b(KafkaReceiver|KafkaSender|ReactiveKafkaConsumerTemplate|ReactiveKafkaProducerTemplate|ReceiverOptions|SenderOptions)\b"
    r"|from ['\"](kafkajs|amqplib)['\"]|require\(['\"](kafkajs|amqplib)['\"]\)"
    r"|\b(confluent_kafka|aiokafka|pika)\b|github\.com/(segmentio/kafka-go|confluentinc|rabbitmq)"
)
SALIDA_DIRECTA = re.compile(
    r"\bSystem\.(out|err)\.print|\.printStackTrace\(\)"
    r"|\bconsole\.(log|error|warn|info|debug)\("
    r"|^\s*print\("
    r"|\bfmt\.Print"
    r"|\bConsole\.Write"
)
PATRON_CONTRATO = re.compile(r"(openapi|swagger|asyncapi)[^/]*\.(ya?ml|json)$", re.IGNORECASE)
PATRON_IMAGEN = re.compile(r"\.(png|jpe?g|svg|drawio|puml)$", re.IGNORECASE)
PATRON_SEMVER = re.compile(r"^\d+\.\d+\.\d+([-+].*)?$")
PATRON_ELEMENTO = re.compile(r"^\s*(Person|System|SystemDb|SystemQueue|Container|ContainerDb|ContainerQueue)(_Ext)?\((.*)\)\s*$")
PATRON_RELACION = re.compile(r"^\s*(Rel|BiRel|Rel_[A-Za-z]+)\((.*)\)\s*$")


# --- Utilidades --------------------------------------------------------------------------------

def leer_criterios(texto_adr: str) -> dict[str, dict]:
    """Tabla de criterios de un ADR del equipo o del producto: {criterio: {texto, como, severidad}}."""
    criterios = {}
    for linea in texto_adr.splitlines():
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if len(celdas) >= 4 and re.fullmatch(r"`[A-Z]{2,5}-\d{3}\.\d+`", celdas[0]):
            criterios[celdas[0].strip("`")] = {"texto": celdas[1], "como": celdas[2], "severidad": celdas[3]}
    return criterios


def archivos_de_codigo(repo: Path, incluir_pruebas: bool = False):
    for archivo in repo.rglob("*"):
        partes = set(archivo.relative_to(repo).parts[:-1])
        if (not archivo.is_file() or archivo.suffix not in EXTENSIONES_CODIGO or partes & CARPETAS_EXCLUIDAS
                or (not incluir_pruebas and {p.lower() for p in partes} & CARPETAS_PRUEBA)
                or archivo.stat().st_size > TAMANO_MAXIMO):
            continue
        yield archivo


def buscar(repo: Path, patron: re.Pattern, limite: int = 20, incluir_pruebas: bool = False) -> list[dict]:
    coincidencias = []
    for archivo in sorted(archivos_de_codigo(repo, incluir_pruebas)):
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if patron.search(linea):
                coincidencias.append({"archivo": archivo.relative_to(repo).as_posix(), "linea": numero,
                                      "fragmento": linea.strip()[:160]})
                if len(coincidencias) >= limite:
                    return coincidencias
    return coincidencias


def argumentos(texto: str) -> list[str]:
    """Argumentos de una llamada Mermaid C4, respetando comillas."""
    resultado, actual, en_comillas = [], "", False
    for caracter in texto:
        if caracter == '"':
            en_comillas = not en_comillas
        elif caracter == "," and not en_comillas:
            resultado.append(actual.strip())
            actual = ""
            continue
        actual += caracter
    resultado.append(actual.strip())
    return [a.strip().strip('"').strip() for a in resultado]


def bloques_mermaid(texto: str) -> list[tuple[int, list[str]]]:
    """(línea de inicio, líneas) de cada bloque ```mermaid."""
    bloques, actual, inicio = [], None, 0
    for numero, linea in enumerate(texto.splitlines(), start=1):
        if actual is None and linea.strip().lower().startswith("```mermaid"):
            actual, inicio = [], numero + 1
        elif actual is not None and linea.strip().startswith("```"):
            bloques.append((inicio, actual))
            actual = None
        elif actual is not None:
            actual.append(linea)
    return bloques


# --- Contexto de una verificación --------------------------------------------------------------

class Verificador:

    def __init__(self, repo: Path, id_repo: str, rama: str, decisiones: dict[str, dict],
                 suspendidos: dict[str, list[str]], exceptuados: dict[str, str] | None = None) -> None:
        self.repo, self.id_repo, self.rama = repo, id_repo, rama
        self.decisiones, self.suspendidos = decisiones, suspendidos
        self.exceptuados = exceptuados or {}
        self.resultados: list[dict] = []
        self.hallazgos: list[dict] = []

    def criterio(self, id_criterio: str) -> tuple[dict, dict] | None:
        """(decisión, criterio) si el criterio está vigente para evaluar; si no, registra por qué."""
        id_eq = "ADR-EQ-" + id_criterio[3:6]
        decision = self.decisiones.get(id_eq)
        if decision is None or id_criterio not in decision["tabla"]:
            return None
        if id_criterio in self.exceptuados:
            self.registrar(id_criterio, NO_APLICA, self.exceptuados[id_criterio])
            return None
        if id_criterio in self.suspendidos.get(id_eq, []):
            self.registrar(id_criterio, NO_APLICA, "suspendido por un choque con arquitectura (equipo/COHERENCIA.md)")
            return None
        return decision, decision["tabla"][id_criterio]

    def registrar(self, id_criterio: str, resultado: str, motivo: str, evidencia: list[dict] | None = None,
                  pendiente_revision: bool = False) -> None:
        self.resultados.append({"criterio": id_criterio, "fuente": "ADR-EQ-" + id_criterio[3:6], "resultado": resultado,
                                "motivo": motivo, "evidencia": evidencia or [], "pendiente_revision": pendiente_revision})

    def hallazgo(self, id_criterio: str, titulo: str, detalle: str, evidencia: list[dict], fragmento: str = "",
                 severidad: str | None = None, origen: str = "verificacion") -> None:
        decision = self.decisiones["ADR-EQ-" + id_criterio[3:6]]
        criterio = decision["tabla"][id_criterio]
        archivo = evidencia[0]["archivo"] if evidencia else ""
        self.hallazgos.append({
            "huella": huella(self.id_repo, self.rama, decision["id"], id_criterio, archivo, fragmento or titulo),
            "nivel": 3,
            "fuente": decision["id"],
            "criterio": id_criterio,
            "categoria": CATEGORIAS.get(decision["id"], "documentacion"),
            "severidad": severidad or criterio["severidad"],
            "titulo": titulo,
            "detalle": detalle,
            "evidencia": [{"archivo": e["archivo"], "linea": e.get("linea")} for e in evidencia],
            "origen": origen,
            "modo": "propuesta" if normalizar(decision["estado"]) == "propuesto" else "vigente",
        })


# --- Verificaciones por decisión ---------------------------------------------------------------

def verificar_c4(v: Verificador) -> None:
    carpeta = v.repo / "docs" / "arquitectura"
    diagramas = {}
    for id_criterio, nombre, tipo in (("EQ-006.1", "c4-contexto.md", "C4Context"),
                                      ("EQ-006.2", "c4-contenedores.md", "C4Container")):
        if not v.criterio(id_criterio):
            continue
        archivo = carpeta / nombre
        ruta = f"docs/arquitectura/{nombre}"
        if not archivo.exists():
            v.registrar(id_criterio, NO_CUMPLE, f"no existe {ruta}")
            v.hallazgo(id_criterio, f"Falta el diagrama {tipo} ({ruta})", f"No existe `{ruta}`.", [{"archivo": ruta}])
            continue
        texto = archivo.read_text(encoding="utf-8", errors="replace")
        bloque = next(((i, b) for i, b in bloques_mermaid(texto) if b and b[0].strip().startswith(tipo)), None)
        if bloque is None:
            v.registrar(id_criterio, NO_CUMPLE, f"{ruta} no contiene un bloque mermaid {tipo}", [{"archivo": ruta}])
            v.hallazgo(id_criterio, f"{ruta} no contiene un diagrama {tipo}",
                       f"El archivo existe pero no tiene un bloque ```mermaid que empiece con `{tipo}`.", [{"archivo": ruta}])
            continue
        diagramas[ruta] = bloque
        v.registrar(id_criterio, CUMPLE, f"{ruta} contiene un diagrama {tipo}", [{"archivo": ruta, "linea": bloque[0]}])

    if v.criterio("EQ-006.3"):
        if not diagramas:
            v.registrar("EQ-006.3", NO_APLICA, "no hay diagramas C4 que evaluar")
        else:
            problemas = []
            for ruta, (inicio, lineas) in diagramas.items():
                if not any(l.strip().startswith("title ") for l in lineas):
                    problemas.append({"archivo": ruta, "linea": inicio, "problema": "el diagrama no tiene título"})
                for desplazamiento, linea in enumerate(lineas):
                    numero = inicio + desplazamiento
                    if m := PATRON_ELEMENTO.match(linea):
                        args, es_contenedor = argumentos(m.group(3)), m.group(1).startswith("Container")
                        minimo = 4 if es_contenedor else 3
                        if len(args) < minimo or not all(args[1:minimo]):
                            falta = "nombre, tecnología o descripción" if es_contenedor else "nombre o descripción"
                            problemas.append({"archivo": ruta, "linea": numero, "problema": f"elemento sin {falta}: `{linea.strip()}`"})
                    elif m := PATRON_RELACION.match(linea):
                        args = argumentos(m.group(2))
                        if len(args) < 4 or not all(args[2:4]):
                            problemas.append({"archivo": ruta, "linea": numero, "problema": f"relación sin descripción o protocolo: `{linea.strip()}`"})
            if problemas:
                v.registrar("EQ-006.3", NO_CUMPLE, f"{len(problemas)} problema(s) de notación", problemas)
                for p in problemas:
                    v.hallazgo("EQ-006.3", f"Notación C4 incompleta en {p['archivo']}", p["problema"], [p], fragmento=p["problema"])
            else:
                v.registrar("EQ-006.3", CUMPLE, "la notación mínima está completa")

    if v.criterio("EQ-006.4"):
        imagenes = sorted(p.relative_to(v.repo).as_posix() for p in (v.repo / "docs").rglob("*")
                          if p.is_file() and PATRON_IMAGEN.search(p.name)) if (v.repo / "docs").exists() else []
        if diagramas:
            v.registrar("EQ-006.4", CUMPLE, "los diagramas están como código Mermaid")
        elif imagenes:
            v.registrar("EQ-006.4", NO_CUMPLE, "hay diagramas como imagen pero no como código", [{"archivo": i} for i in imagenes[:5]])
            v.hallazgo("EQ-006.4", "Diagramas de arquitectura solo como imagen",
                       f"Se encontraron {len(imagenes)} imagen(es) en docs/ y ningún diagrama Mermaid C4.",
                       [{"archivo": i} for i in imagenes[:5]])
        else:
            v.registrar("EQ-006.4", NO_APLICA, "no hay diagramas, ni como imagen ni como código")


def cargar_contrato(archivo: Path) -> dict | None:
    try:
        texto = archivo.read_text(encoding="utf-8", errors="replace")
        datos = json.loads(texto) if archivo.suffix == ".json" else yaml.safe_load(texto)
        return datos if isinstance(datos, dict) else None
    except (yaml.YAMLError, json.JSONDecodeError):
        return None


def verificar_contratos(v: Verificador) -> None:
    carpeta = v.repo / "docs" / "contratos"
    contratos = sorted(p for p in carpeta.rglob("*") if p.is_file() and PATRON_CONTRATO.search(p.name)) if carpeta.exists() else []
    openapi = [c for c in contratos if "asyncapi" not in c.name.lower()]
    asyncapi = [c for c in contratos if "asyncapi" in c.name.lower()]
    otros = sorted(p.relative_to(v.repo).as_posix() for p in v.repo.rglob("*")
                   if p.is_file() and PATRON_CONTRATO.search(p.name) and not set(p.relative_to(v.repo).parts) & CARPETAS_EXCLUIDAS
                   and not p.is_relative_to(carpeta))

    for id_criterio, encontrados, senales, que in (("EQ-004.1", openapi, SENALES_API, "APIs HTTP"),
                                                    ("EQ-004.2", asyncapi, SENALES_EVENTOS, "eventos")):
        if not v.criterio(id_criterio):
            continue
        if encontrados:
            v.registrar(id_criterio, CUMPLE, f"contrato en docs/contratos/", [{"archivo": c.relative_to(v.repo).as_posix()} for c in encontrados])
            continue
        coincidencias = buscar(v.repo, senales, limite=10)
        if coincidencias:
            ubicacion = f" Hay contratos fuera de docs/contratos/: {', '.join(otros)}." if otros else ""
            v.registrar(id_criterio, NO_CUMPLE, f"el código expone o usa {que} y no hay contrato en docs/contratos/", coincidencias)
            v.hallazgo(id_criterio, f"Sin contrato para {que} en docs/contratos/",
                       f"El código tiene señales de {que} y no existe el contrato en `docs/contratos/`.{ubicacion}",
                       coincidencias[:5])
        elif que == "eventos":
            v.registrar(id_criterio, NO_APLICA, "[inferencia] no se detectaron productores ni consumidores de eventos",
                        pendiente_revision=True)
        else:
            v.registrar(id_criterio, NO_DETERMINADO, "no se detectaron señales de APIs HTTP; confirmar en la revisión de código",
                        pendiente_revision=True)

    if v.criterio("EQ-004.3"):
        if not openapi:
            v.registrar("EQ-004.3", NO_APLICA, "no hay contratos OpenAPI que evaluar")
        else:
            problemas = []
            for contrato in openapi:
                ruta = contrato.relative_to(v.repo).as_posix()
                datos = cargar_contrato(contrato)
                if datos is None:
                    problemas.append((ruta, "el archivo no es un YAML o JSON válido"))
                    continue
                version = str((datos.get("info") or {}).get("version", ""))
                if not PATRON_SEMVER.match(version):
                    problemas.append((ruta, f"info.version '{version}' no sigue versionado semántico"))
                if not (datos.get("components") or {}).get("securitySchemes") and "securityDefinitions" not in datos:
                    problemas.append((ruta, "no declara autenticación (securitySchemes)"))
                operaciones = [op for camino in (datos.get("paths") or {}).values() if isinstance(camino, dict)
                               for metodo, op in camino.items() if isinstance(op, dict) and metodo.lower() in
                               ("get", "post", "put", "patch", "delete")]
                if operaciones and not any(str(c).startswith(("4", "5")) for op in operaciones for c in (op.get("responses") or {})):
                    problemas.append((ruta, "ninguna operación declara respuestas de error (4xx o 5xx)"))
                if operaciones and not re.search(r"\bexamples?\b", json.dumps(datos)):
                    problemas.append((ruta, "no tiene ejemplos de solicitud o respuesta"))
            if problemas:
                v.registrar("EQ-004.3", NO_CUMPLE, f"{len(problemas)} carencia(s) de contenido", [{"archivo": r, "problema": p} for r, p in problemas])
                for ruta, problema in problemas:
                    v.hallazgo("EQ-004.3", f"Contrato incompleto: {ruta}", problema, [{"archivo": ruta}], fragmento=problema)
            else:
                v.registrar("EQ-004.3", CUMPLE, "los contratos tienen el contenido mínimo")


def ejecutar_gitleaks(repo: Path) -> list[dict] | None:
    """Secretos en el repositorio y su historial, con los valores ocultos. None si gitleaks no está."""
    if not shutil.which("gitleaks"):
        return None
    with tempfile.TemporaryDirectory() as temporal:
        reporte = Path(temporal) / "gitleaks.json"
        subprocess.run(["gitleaks", "git", "--redact", "--no-banner", "--exit-code", "0",
                        "--report-format", "json", "--report-path", str(reporte), str(repo)],
                       capture_output=True, text=True, check=False)
        if not reporte.exists():
            return None
        datos = json.loads(reporte.read_text(encoding="utf-8") or "[]")
    return secretos_unicos(datos)


def secretos_unicos(datos: list[dict]) -> list[dict]:
    """Un hallazgo por secreto: gitleaks lo informa una vez por cada commit del historial que lo contiene."""
    unicos: dict[tuple, dict] = {}
    for d in datos:
        unicos.setdefault((d.get("RuleID"), d.get("File"), d.get("StartLine")), {
            "regla": d.get("RuleID"), "archivo": d.get("File"), "linea": d.get("StartLine"), "commit": (d.get("Commit") or "")[:12]})
    return list(unicos.values())


def verificar_secretos(v: Verificador, gitleaks: list[dict] | None) -> None:
    if not v.criterio("EQ-001.1"):
        return
    if gitleaks is None:
        v.registrar("EQ-001.1", NO_DETERMINADO, "gitleaks no está instalado o no pudo ejecutarse")
        return
    if not gitleaks:
        v.registrar("EQ-001.1", CUMPLE, "gitleaks no encontró secretos en el repositorio ni en su historial")
        return
    v.registrar("EQ-001.1", NO_CUMPLE, f"gitleaks encontró {len(gitleaks)} posible(s) secreto(s)", gitleaks)
    vistos: dict[tuple[str, str], int] = {}
    for secreto in gitleaks:
        clave = (secreto["regla"], secreto["archivo"])
        vistos[clave] = vistos.get(clave, 0) + 1
        v.hallazgo("EQ-001.1", f"Posible secreto ({secreto['regla']}) en {secreto['archivo']}",
                   f"Detectado por gitleaks en el commit {secreto['commit']}. El valor no se muestra. "
                   "Si el secreto es real, rotarlo: borrarlo del código no lo invalida.",
                   [secreto], fragmento=f"{secreto['regla']}#{vistos[clave]}", origen="gitleaks")


def verificar_readme(v: Verificador) -> None:
    readme = next((p for p in v.repo.iterdir() if p.is_file() and p.name.lower() == "readme.md"), None)
    if v.criterio("EQ-007.1"):
        if readme is None:
            v.registrar("EQ-007.1", NO_CUMPLE, "no existe README.md")
            v.hallazgo("EQ-007.1", "Falta README.md", "El repositorio no tiene README.md en la raíz.", [{"archivo": "README.md"}])
        else:
            encabezados = [normalizar(re.sub(r"^#+\s*(\d+(\.\d+)*\.?\s*)?", "", l)) for l in
                           readme.read_text(encoding="utf-8", errors="replace").splitlines() if l.startswith("#")]
            faltantes = [nombre for nombre, claves in SECCIONES_README
                         if not any(clave in encabezado for encabezado in encabezados for clave in claves)]
            if faltantes:
                v.registrar("EQ-007.1", NO_CUMPLE, f"faltan {len(faltantes)} sección(es): {', '.join(faltantes)}", [{"archivo": readme.name}])
                v.hallazgo("EQ-007.1", f"README sin {len(faltantes)} sección(es) obligatoria(s)",
                           f"Faltan: {', '.join(faltantes)}.", [{"archivo": readme.name}])
            else:
                v.registrar("EQ-007.1", CUMPLE, "el README tiene las secciones obligatorias", [{"archivo": readme.name}])

    if v.criterio("EQ-007.2"):
        if readme is None:
            v.registrar("EQ-007.2", NO_APLICA, "no existe README.md")
            return
        comandos = []
        en_bloque = False
        for numero, linea in enumerate(readme.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if linea.strip().startswith("```"):
                en_bloque = not en_bloque
            elif en_bloque and linea.strip():
                comandos.append((numero, linea.strip().lstrip("$ ").strip()))
        makefile = v.repo / "Makefile"
        objetivos = set(re.findall(r"^([A-Za-z0-9_.-]+):", makefile.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)) if makefile.exists() else set()
        paquete = v.repo / "package.json"
        try:
            scripts = set((json.loads(paquete.read_text(encoding="utf-8")) or {}).get("scripts", {})) if paquete.exists() else set()
        except json.JSONDecodeError:
            scripts = set()
        revisados, inexistentes = 0, []
        for numero, comando in comandos:
            if m := re.match(r"make\s+([A-Za-z0-9_.-]+)", comando):
                revisados += 1
                if m.group(1) not in objetivos:
                    inexistentes.append((numero, comando, f"el Makefile no tiene el objetivo '{m.group(1)}'"))
            elif m := re.match(r"(npm run|pnpm run|yarn run|pnpm|yarn)\s+([A-Za-z0-9:_.-]+)", comando):
                if m.group(1) in ("pnpm", "yarn") and m.group(2) in ("install", "add", "dlx", "exec", "test"):
                    continue
                revisados += 1
                if m.group(2) not in scripts:
                    inexistentes.append((numero, comando, f"package.json no tiene el script '{m.group(2)}'"))
            elif m := re.match(r"\./(mvnw|gradlew)\b", comando):
                revisados += 1
                if not (v.repo / m.group(1)).exists():
                    inexistentes.append((numero, comando, f"no existe el wrapper {m.group(1)}"))
        if inexistentes:
            evidencia = [{"archivo": readme.name, "linea": n, "problema": p} for n, _, p in inexistentes]
            v.registrar("EQ-007.2", NO_CUMPLE, f"{len(inexistentes)} comando(s) del README no existen", evidencia)
            for numero, comando, problema in inexistentes:
                v.hallazgo("EQ-007.2", f"Comando del README inexistente: `{comando}`", problema,
                           [{"archivo": readme.name, "linea": numero}], fragmento=comando)
        elif revisados:
            v.registrar("EQ-007.2", CUMPLE, f"los {revisados} comando(s) verificables del README existen")
        else:
            v.registrar("EQ-007.2", NO_DETERMINADO, "el README no tiene comandos verificables automáticamente", pendiente_revision=True)


def verificar_logs(v: Verificador) -> None:
    if not v.criterio("EQ-003.1"):
        return
    coincidencias = buscar(v.repo, SALIDA_DIRECTA, limite=30)
    if not coincidencias:
        v.registrar("EQ-003.1", CUMPLE, "no se encontró salida directa a consola fuera de las pruebas", pendiente_revision=True)
        return
    v.registrar("EQ-003.1", NO_CUMPLE, f"{len(coincidencias)} uso(s) de salida directa a consola fuera de las pruebas", coincidencias)
    por_archivo: dict[str, list[dict]] = {}
    for c in coincidencias:
        por_archivo.setdefault(c["archivo"], []).append(c)
    for archivo, lista in por_archivo.items():
        v.hallazgo("EQ-003.1", f"Salida directa a consola en {archivo}",
                   f"{len(lista)} uso(s) de print/console en lugar del logger del framework.", lista[:5])


# --- Punto de entrada --------------------------------------------------------------------------

def verificar_repo(repo: Path, id_repo: str, rama: str, tipo: str, decisiones: dict[str, dict],
                   suspendidos: dict[str, list[str]], gitleaks: list[dict] | None,
                   exceptuados: dict[str, str] | None = None) -> tuple[list[dict], list[dict]]:
    """Devuelve (resultados por criterio, hallazgos)."""
    v = Verificador(repo, id_repo, rama, decisiones, suspendidos, exceptuados)
    if tipo != "propio":
        # En repositorios de configuración solo se buscan secretos (ADR-EQ-001); el resto aplica a repositorios propios.
        if tipo == "config":
            verificar_secretos(v, gitleaks)
        evaluados = {r["criterio"] for r in v.resultados}
        for decision in decisiones.values():
            if decision["id"] not in DECISIONES_DE_CODIGO:
                continue
            for id_criterio, criterio in decision["tabla"].items():
                if criterio["como"].startswith("automática") and id_criterio not in evaluados:
                    v.registrar(id_criterio, NO_APLICA, f"no aplica a repositorios de tipo {tipo}")
        return v.resultados, v.hallazgos
    verificar_c4(v)
    verificar_contratos(v)
    verificar_secretos(v, gitleaks)
    verificar_readme(v)
    verificar_logs(v)
    return v.resultados, v.hallazgos
