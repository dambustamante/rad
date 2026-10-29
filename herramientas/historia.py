"""Tareas, Spikes y Bugs del equipo (ADR-EQ-008): borrador, contexto del producto, validación y Jira.

Uso:
  python herramientas/historia.py nueva <producto> --tipo tarea|spike|bug --titulo TEXTO
                                        [--categoria "Deuda Técnica"|"Deuda Operativa"]
                                        [--desde H-0001,H-0002] [--repos a,b] [--tema "palabras clave"]
  python herramientas/historia.py validar <producto> <borrador>
  python herramientas/historia.py listar <producto>
  python herramientas/historia.py crear <producto> <borrador> [--confirmar]

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

Los borradores viven en productos/<producto>/historias/borradores/. `nueva` escribe el borrador desde la
plantilla y un paquete de contexto con la información del producto. `crear` sin --confirmar solo muestra
la vista previa; con --confirmar crea la incidencia en Jira (la única escritura hacia Jira) y deja la
clave en el borrador.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

import hallazgos as registro_hallazgos
import historias as modulo_historias
import integraciones
import lenguaje
import productos
import proveedor
from coherencia import leer_arquitectura_vigente, leer_decisiones_equipo, leer_decisiones_producto
from comun import RAIZ, ErrorRadiografia, cargar_config, cargar_env, normalizar
from sync_arquitectura import secciones

TIPOS = ("tarea", "spike", "bug")
COMBINACIONES = {"tarea": ("Deuda Técnica", "Deuda Operativa"), "bug": ("Bau/Incidentes",), "spike": ("Spike",)}
SECCIONES = {
    "tarea": ("criterios de aceptacion", "contexto", "decisiones que aplican", "fuera de alcance", "trazabilidad"),
    "bug": ("criterios de aceptacion", "comportamiento actual", "comportamiento esperado", "como reproducirlo",
            "impacto", "causa", "trazabilidad"),
    "spike": ("criterios de aceptacion", "pregunta", "contexto", "opciones a evaluar", "criterios de decision",
              "restricciones", "duracion maxima", "entregable", "trazabilidad"),
}
CRITERIOS_FIJOS = {
    "Deuda Técnica": ("ya no reporta",),
    "Deuda Operativa": ("deja de ser necesaria",),
    "Bau/Incidentes": ("reproduce el error", "causa queda documentada", "evita que el error se repita"),
    "Spike": ("pregunta tiene respuesta documentada", "adr de producto en estado propuesto", "duracion maxima"),
}
DURACION_MAXIMA_SPIKE = 2
NOMBRES = {"tarea": "Una Tarea", "spike": "Un Spike", "bug": "Un Bug"}
PATRON_MEDIBLE = re.compile(r"\d|^\s*[-*]?\s*(dado|cuando|entonces)\b|\b(no reporta|deja de|rechaza|responde|registra|devuelve)\b")
VERBO_INFINITIVO = re.compile(r"^[a-záéíóúñ]+(ar|er|ir)\b", re.IGNORECASE)


# --- Configuración de Jira ---------------------------------------------------------------------

def config_jira(raiz: Path) -> dict:
    jira = cargar_config(raiz).get("jira") or {}
    return {
        "equipos": jira.get("equipos", "Back"),
        "campo_equipos": jira.get("campo_equipos", "Equipos"),
        "campo_tipo": jira.get("campo_tipo", "Tipo"),
        "tipos_incidencia": {"tarea": "Tarea", "spike": "Spike", "bug": "Bug", **(jira.get("tipos_incidencia") or {})},
    }


def destino_jira(raiz: Path, producto: str) -> dict:
    """Proyecto y etiqueta donde se crean las incidencias: los mismos de donde se leen las historias."""
    config = modulo_historias.leer_config(raiz, producto)
    proyecto = config.get("proyecto")
    if not proyecto and config.get("jql"):
        if coincidencia := re.search(r"project\s*=\s*\"?([A-Z][A-Z0-9_]+)\"?", config["jql"], re.IGNORECASE):
            proyecto = coincidencia.group(1)
    if not proyecto:
        raise ErrorRadiografia(f"No se pudo determinar el proyecto de Jira de '{producto}': agregar historias.proyecto "
                               "(clave del proyecto) o una JQL con 'project = CLAVE'.")
    etiqueta = config.get("etiqueta")
    if not etiqueta and config.get("jql"):
        if coincidencia := re.search(r"labels\s*=\s*\"?([\w-]+)\"?", config["jql"], re.IGNORECASE):
            etiqueta = coincidencia.group(1)
    return {"proyecto": proyecto, "etiqueta": etiqueta}


# --- Borradores --------------------------------------------------------------------------------

def carpeta_borradores(raiz: Path, producto: str) -> Path:
    if not (raiz / "productos" / producto / "producto.yaml").exists():
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    return raiz / "productos" / producto / "historias" / "borradores"


def leer_borrador(archivo: Path) -> tuple[dict, str]:
    texto = archivo.read_text(encoding="utf-8")
    partes = re.match(r"^---\n(.*?)\n---\n(.*)$", texto, re.DOTALL)
    if not partes:
        raise ErrorRadiografia(f"{archivo.name} no tiene el encabezado YAML (entre líneas ---).")
    try:
        datos = yaml.safe_load(partes.group(1)) or {}
    except yaml.YAMLError as error:
        raise ErrorRadiografia(f"El encabezado de {archivo.name} no es un YAML válido: {error}") from error
    return datos, partes.group(2)


def escribir_borrador(archivo: Path, datos: dict, cuerpo: str) -> None:
    encabezado = yaml.safe_dump(datos, allow_unicode=True, sort_keys=False).strip()
    archivo.write_text(f"---\n{encabezado}\n---\n{cuerpo}", encoding="utf-8")


def resolver_borrador(raiz: Path, producto: str, nombre: str) -> Path:
    carpeta = carpeta_borradores(raiz, producto)
    candidatos = [carpeta / nombre, carpeta / f"{nombre}.md", Path(nombre)]
    candidatos += sorted(carpeta.glob(f"{nombre}-*.md")) if carpeta.exists() else []
    for candidato in candidatos:
        if candidato.is_file() and not candidato.name.endswith("-contexto.md"):
            return candidato
    raise ErrorRadiografia(f"No existe el borrador '{nombre}' en {carpeta.relative_to(raiz)}.")


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalizar(texto)).strip("-")[:50] or "historia"


# --- Paquete de contexto -----------------------------------------------------------------------

def palabras_clave(texto: str) -> set[str]:
    return {p for p in re.findall(r"[a-z0-9áéíóúñ]{4,}", normalizar(texto))}


def contexto(raiz: Path, producto: str, tipo: str, categoria: str, titulo: str, desde: list[str],
             repos: list[str], tema: str | None) -> str:
    registro = registro_hallazgos.cargar(raiz, producto)
    por_id = {h["id"]: h for h in registro["hallazgos"].values()}
    origen = [por_id[i] for i in desde]
    repos = sorted(set(repos) | {h["repo"] for h in origen})
    claves = palabras_clave(" ".join([titulo, tema or ""] + [h["titulo"] for h in origen]))
    fuentes_origen = {h["fuente"] for h in origen} | {h["criterio"] for h in origen if h.get("criterio")}

    lineas = [f"# Contexto para: {titulo}", "",
              f"- Tipo de incidencia: {tipo} · Tipo: {categoria} · Producto: {producto}",
              f"- Repositorios: {', '.join(repos) or 'NO DETERMINADO'}",
              "- Estructura obligatoria: ADR-EQ-008 · Definición de terminado: ADR-EQ-009 · Lenguaje: equipo/lenguaje.yaml",
              "", "## Hallazgos de origen", ""]
    for h in origen:
        evidencia = ", ".join(f"`{e['archivo']}:{e['linea']}`" if e.get("linea") else f"`{e['archivo']}`" for e in h["evidencia"][:5])
        lineas.append(f"- **{h['id']}** · {h['repo']} · {h['criterio'] or h['fuente']} · {h['severidad']}: {h['titulo']}. "
                      f"{h.get('detalle', '')} Evidencia: {evidencia or '—'}"
                      + (f" Triaje: {h['triaje']['decision']} ({h['triaje'].get('motivo') or 'sin motivo'})" if h.get("triaje") else ""))
    if not origen:
        lineas.append("Ninguno indicado.")

    relacionados = [h for h in registro["hallazgos"].values()
                    if h["estado"] == "abierto" and h["id"] not in desde and (not repos or h["repo"] in repos)
                    and ((h.get("criterio") or h["fuente"]) in fuentes_origen or len(claves & palabras_clave(h["titulo"])) >= 2)]
    lineas += ["", "## Otros hallazgos abiertos relacionados", ""]
    lineas += [f"- {h['id']} · {h['repo']} · {h['criterio'] or h['fuente']} · {h['severidad']}: {h['titulo']}" for h in relacionados[:15]] or ["Ninguno."]

    lineas += ["", "## AS IS de los repositorios", ""]
    for repo in repos:
        ficha = raiz / "productos" / producto / "as-is" / f"{repo}.md"
        if not ficha.exists():
            lineas.append(f"- {repo}: sin ficha AS IS (ejecutar /revisar).")
            continue
        _, contenido = secciones(ficha.read_text(encoding="utf-8").splitlines())
        for seccion in ("riesgos y deuda principales", "integraciones", "arquitectura real"):
            texto = "\n".join(l for l in contenido.get(seccion, []) if l.strip()).strip()
            if texto:
                lineas += [f"### {repo}: {seccion}", "", texto[:2500], ""]

    lineas += ["## Decisiones que pueden aplicar", "",
               "Incluir en la historia solo las que el trabajo debe respetar, con su regla rápida.", ""]
    documentos = [(c, d) for c, d in leer_arquitectura_vigente(raiz).items()]
    documentos += [(i, d) for i, d in leer_decisiones_equipo(raiz).items() if d["evaluado"]]
    documentos += [(i, d) for i, d in leer_decisiones_producto(raiz, producto).items() if d["evaluado"]]
    for clave, documento in documentos:
        relacionado = clave in fuentes_origen or any(c.startswith(f"EQ-{clave[7:10]}") for c in fuentes_origen if clave.startswith("ADR-EQ-")) \
            or len(claves & palabras_clave(f"{documento['titulo']} {documento.get('regla_rapida') or ''}")) >= 2
        if relacionado:
            lineas.append(f"- `{clave}` {documento['titulo']}: {documento.get('regla_rapida') or 'sin regla rápida'}")

    fichas = [f for repo in repos for f in integraciones.para_repo(raiz, producto, repo)] if repos else []
    if fichas:
        lineas += ["", "## Integraciones involucradas", ""]
        for f in {f["id"]: f for f in fichas}.values():
            sla = f.get("sla") or {}
            lineas.append(f"- `{f['id']}` {f.get('nombre')}: {f.get('protocolo')}, p95 {sla.get('p95_ms') or '—'} ms, "
                          f"política ante falla {f.get('politica_ante_falla')} ({f.get('justificacion')})")

    if tema:
        coincidencias = proveedor.buscar(raiz, producto, tema, limite=10)
        lineas += ["", f"## Documentación del proveedor y de terceros sobre «{tema}»", ""]
        lineas += [f"- `{c['archivo']}`" + (f" (página {c['pagina']})" if c["pagina"] else "") + f":{c['linea']}: {c['texto']}"
                   for c in coincidencias] or ["Sin coincidencias."]

    similares = [h for h in modulo_historias.historias_de(raiz, producto).values()
                 if h.get("en_fuente", True) and len(claves & palabras_clave(h["titulo"])) >= 2]
    lineas += ["", "## Historias de Jira parecidas (revisar si ya existe la misma)", ""]
    lineas += [f"- {h['clave']} · {h.get('tipo') or 'sin tipo'} · {h.get('estado') or '—'}: {h['titulo']}" for h in similares[:10]] or ["Ninguna."]

    lineas += ["", "## Sonar de los repositorios", ""]
    for repo in repos:
        estado = registro.get("repos", {}).get(repo, {}).get("automatica")
        crudo = raiz / "productos" / producto / "revisiones" / estado["id"] / "crudo" / f"{repo}-sonar.json" if estado else None
        if crudo and crudo.exists():
            datos = json.loads(crudo.read_text(encoding="utf-8"))
            metricas = ", ".join(f"{m} {v}" for m, v in sorted(datos.get("metricas", {}).items()))
            lineas.append(f"- {repo}: quality gate {datos['quality_gate']['estado']}; {metricas}")
        else:
            lineas.append(f"- {repo}: NO DETERMINADO (sin datos de Sonar en la última revisión)")
    return "\n".join(lineas) + "\n"


def nueva(raiz: Path, producto: str, tipo: str, categoria: str | None, titulo: str, desde: list[str],
          repos: list[str], tema: str | None) -> tuple[Path, Path]:
    if tipo not in TIPOS:
        raise ErrorRadiografia(f"Tipo de incidencia '{tipo}' inválido; valores válidos: {', '.join(TIPOS)}.")
    categoria = categoria or COMBINACIONES[tipo][0]
    if categoria not in COMBINACIONES[tipo]:
        raise ErrorRadiografia(f"{NOMBRES[tipo]} solo admite Tipo {', '.join(COMBINACIONES[tipo])}.")
    datos_producto = productos.leer_productos(raiz).get(producto)
    if datos_producto is None:
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    repos_producto = {str(r["id"]) for r in productos.repos_de(datos_producto)}
    desconocidos = [r for r in repos if r not in repos_producto]
    if desconocidos:
        raise ErrorRadiografia(f"Repositorios que no existen en el producto: {', '.join(desconocidos)}.")
    existentes = {h["id"] for h in registro_hallazgos.cargar(raiz, producto)["hallazgos"].values()}
    inexistentes = [h for h in desde if h not in existentes]
    if inexistentes:
        raise ErrorRadiografia(f"Hallazgos que no existen: {', '.join(inexistentes)}.")

    carpeta = carpeta_borradores(raiz, producto)
    carpeta.mkdir(parents=True, exist_ok=True)
    numeros = [int(m.group(1)) for a in carpeta.glob("*.md") if (m := re.match(r"^(\d{3})-", a.name))]
    base = f"{max(numeros, default=0) + 1:03d}-{slug(titulo)}"
    datos, cuerpo = leer_borrador(raiz / "equipo" / "plantillas" / f"{tipo}.md")
    registro = registro_hallazgos.cargar(raiz, producto)
    datos.update({"tipo": categoria, "equipos": config_jira(raiz)["equipos"], "producto": producto,
                  "repos": sorted(set(repos) | {h["repo"] for h in registro["hallazgos"].values() if h["id"] in desde}),
                  "hallazgos": desde, "estado": "borrador", "jira": None})
    cuerpo = re.sub(r"^# .*$", f"# {titulo}", cuerpo, count=1, flags=re.MULTILINE)
    if tipo == "tarea":
        fijo = (f"- La revisión ya no reporta los hallazgos de origen ({', '.join(desde)})." if categoria == "Deuda Técnica" and desde
                else "- La revisión ya no reporta los hallazgos de origen." if categoria == "Deuda Técnica"
                else "- La tarea manual deja de ser necesaria; se verifica <cómo se comprueba>.")
        cuerpo = re.sub(r"^- <Deuda Técnica:.*$", fijo, cuerpo, count=1, flags=re.MULTILINE)
    archivo = carpeta / f"{base}.md"
    escribir_borrador(archivo, datos, cuerpo)
    archivo_contexto = carpeta / f"{base}-contexto.md"
    archivo_contexto.write_text(contexto(raiz, producto, tipo, categoria, titulo, desde, repos, tema), encoding="utf-8")
    return archivo, archivo_contexto


# --- Validación --------------------------------------------------------------------------------

def campo_encabezado(cuerpo: str, nombre: str) -> str | None:
    coincidencia = re.search(rf"^\*\*{nombre}\*\*\s*(.+)$", cuerpo, re.MULTILINE)
    return coincidencia.group(1).strip() if coincidencia else None


def validar(raiz: Path, producto: str, archivo: Path) -> list[str]:
    """Errores según ADR-EQ-008 y la regla de lenguaje. Lista vacía si el borrador está listo."""
    datos, cuerpo = leer_borrador(archivo)
    errores = []
    tipo, categoria = datos.get("tipo_incidencia"), datos.get("tipo")
    if tipo not in TIPOS:
        return [f"tipo_incidencia '{tipo}' inválido; valores válidos: {', '.join(TIPOS)}"]
    if categoria not in COMBINACIONES[tipo]:
        errores.append(f"{NOMBRES[tipo].lower()} solo admite Tipo {', '.join(COMBINACIONES[tipo])} (EQ-008.1)")
    if datos.get("equipos") != config_jira(raiz)["equipos"]:
        errores.append(f"Equipos debe ser {config_jira(raiz)['equipos']} (EQ-008.1)")
    if datos.get("producto") != producto:
        errores.append(f"el borrador es del producto '{datos.get('producto')}'")

    titulo = re.search(r"^# (.+)$", cuerpo, re.MULTILINE)
    if not titulo:
        errores.append("falta el título (línea que empieza con '# ')")
    elif tipo != "bug" and not VERBO_INFINITIVO.match(titulo.group(1).strip()):
        errores.append("el título de una Tarea o un Spike empieza con un verbo en infinitivo (por ejemplo «Agregar…», «Evaluar…»)")

    como, quiero, para = (campo_encabezado(cuerpo, n) for n in ("Como", "Quiero", "Para"))
    if not (como and quiero and para):
        errores.append("faltan Como, Quiero o Para (EQ-008.2)")
    else:
        if re.match(r"^(el |un )?sistema\b", normalizar(como)):
            errores.append("«Como» debe ser un rol real (desarrollador, operador, analista…), no «sistema» (EQ-008.2)")
        palabras_quiero, palabras_para = palabras_clave(quiero), palabras_clave(para)
        if palabras_para and len(palabras_para & palabras_quiero) / len(palabras_para) > 0.6:
            errores.append("el «Para» repite el «Quiero»: debe expresar el valor (EQ-008.2)")

    _, contenido = secciones(cuerpo.splitlines())
    for seccion in SECCIONES[tipo]:
        if not "\n".join(contenido.get(seccion, [])).strip():
            errores.append(f"falta la sección «{seccion}» o está vacía (EQ-008.4)")
    criterios = [l.strip() for l in contenido.get("criterios de aceptacion", []) if l.strip().startswith(("-", "*")) or
                 re.match(r"^\s*(dado|cuando|entonces|y)\b", normalizar(l))]
    fijos = CRITERIOS_FIJOS.get(categoria, ())
    for fijo in fijos:
        if not any(fijo in normalizar(c) for c in criterios):
            errores.append(f"falta el criterio fijo de {categoria}: «…{fijo}…» (ADR-EQ-008)")
    propios = [c for c in criterios if not any(f in normalizar(c) for f in fijos)]
    if tipo != "spike" and not any(PATRON_MEDIBLE.search(normalizar(c)) for c in propios):
        errores.append("se necesita al menos un criterio de aceptación propio y medible (EQ-008.3)")

    if tipo == "spike":
        pregunta = "\n".join(contenido.get("pregunta", []))
        if pregunta.count("?") > 1:
            errores.append("un Spike responde una sola pregunta (EQ-008.5)")
        duracion = "\n".join(contenido.get("duracion maxima", []))
        dias = re.search(r"(\d+)\s*d[ií]as?", duracion)
        if not dias:
            errores.append("la duración máxima se indica en días (EQ-008.5)")
        elif int(dias.group(1)) > DURACION_MAXIMA_SPIKE and "justific" not in normalizar(duracion):
            errores.append(f"la duración máxima de un Spike es {DURACION_MAXIMA_SPIKE} días, salvo justificación (EQ-008.5)")
        if "adr" not in normalizar("\n".join(contenido.get("entregable", []))):
            errores.append("el entregable de un Spike incluye un ADR de producto en estado Propuesto (EQ-008.5)")

    if re.search(r"<[a-záéíóúñ][^>\n]{2,}>", cuerpo, re.IGNORECASE):
        errores.append("quedan textos de la plantilla sin completar (<…>)")
    existentes = {h["id"] for h in registro_hallazgos.cargar(raiz, producto)["hallazgos"].values()}
    inexistentes = [h for h in datos.get("hallazgos") or [] if h not in existentes]
    if inexistentes:
        errores.append(f"hallazgos que no existen: {', '.join(inexistentes)}")
    errores += [f"lenguaje: línea {a['linea']}: «{a['texto']}» ({a['regla']}); {a['sugerencia']}"
                for a in lenguaje.revisar(archivo.read_text(encoding="utf-8"), lenguaje.cargar_reglas(raiz))]
    return errores


def listar(raiz: Path, producto: str) -> list[dict]:
    carpeta = carpeta_borradores(raiz, producto)
    filas = []
    for archivo in sorted(carpeta.glob("*.md")) if carpeta.exists() else []:
        if archivo.name.endswith("-contexto.md"):
            continue
        datos, cuerpo = leer_borrador(archivo)
        titulo = re.search(r"^# (.+)$", cuerpo, re.MULTILINE)
        filas.append({"archivo": archivo.name, "titulo": titulo.group(1) if titulo else archivo.stem,
                      "tipo_incidencia": datos.get("tipo_incidencia"), "tipo": datos.get("tipo"),
                      "estado": datos.get("estado"), "jira": datos.get("jira")})
    return filas


# --- Jira --------------------------------------------------------------------------------------

def _texto_con_marcas(texto: str) -> list[dict]:
    """Texto ADF con negrita (**x**), código (`x`) y enlaces ([t](u))."""
    nodos = []
    for parte in re.split(r"(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))", texto):
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**"):
            nodos.append({"type": "text", "text": parte[2:-2], "marks": [{"type": "strong"}]})
        elif parte.startswith("`") and parte.endswith("`"):
            nodos.append({"type": "text", "text": parte[1:-1], "marks": [{"type": "code"}]})
        elif enlace := re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", parte):
            nodos.append({"type": "text", "text": enlace.group(1), "marks": [{"type": "link", "attrs": {"href": enlace.group(2)}}]})
        else:
            nodos.append({"type": "text", "text": parte})
    return nodos


def markdown_a_adf(markdown: str) -> dict:
    """Convierte el markdown de un borrador al formato de documento de Atlassian (ADF)."""
    contenido, lista = [], None
    for linea in markdown.split("\n"):
        if not linea.strip():
            lista = None
            continue
        if titulo := re.match(r"^(#{1,6})\s+(.*)$", linea):
            lista = None
            contenido.append({"type": "heading", "attrs": {"level": min(len(titulo.group(1)) + 1, 6)},
                              "content": _texto_con_marcas(titulo.group(2))})
        elif item := re.match(r"^\s*(?:[-*]|(\d+)\.)\s+(.*)$", linea):
            tipo_lista = "orderedList" if item.group(1) else "bulletList"
            if lista is None or lista["type"] != tipo_lista:
                lista = {"type": tipo_lista, "content": []}
                contenido.append(lista)
            lista["content"].append({"type": "listItem", "content": [{"type": "paragraph", "content": _texto_con_marcas(item.group(2))}]})
        else:
            lista = None
            contenido.append({"type": "paragraph", "content": _texto_con_marcas(linea.strip())})
    return {"type": "doc", "version": 1, "content": contenido}


def valor_campo(esquema: dict, valor: str):
    return [{"value": valor}] if (esquema or {}).get("type") == "array" else {"value": valor}


def armar_solicitud(raiz: Path, producto: str, archivo: Path, campos_jira: list[dict]) -> dict:
    datos, cuerpo = leer_borrador(archivo)
    config, destino = config_jira(raiz), destino_jira(raiz, producto)
    por_nombre = {normalizar(c.get("name", "")): c for c in campos_jira}
    faltantes = [n for n in (config["campo_tipo"], config["campo_equipos"]) if normalizar(n) not in por_nombre]
    if faltantes:
        raise ErrorRadiografia(f"No existen en Jira los campos: {', '.join(faltantes)}.")
    campo_tipo, campo_equipos = por_nombre[normalizar(config["campo_tipo"])], por_nombre[normalizar(config["campo_equipos"])]
    titulo = re.search(r"^# (.+)$", cuerpo, re.MULTILINE).group(1).strip()
    descripcion = re.sub(r"^# .+\n+", "", cuerpo, count=1, flags=re.MULTILINE)
    campos = {
        "project": {"key": destino["proyecto"]},
        "issuetype": {"name": config["tipos_incidencia"][datos["tipo_incidencia"]]},
        "summary": titulo,
        "description": markdown_a_adf(descripcion),
        campo_tipo["id"]: valor_campo(campo_tipo.get("schema"), datos["tipo"]),
        campo_equipos["id"]: valor_campo(campo_equipos.get("schema"), datos["equipos"]),
    }
    if destino["etiqueta"]:
        campos["labels"] = [destino["etiqueta"]]
    return {"fields": campos}


def crear(raiz: Path, producto: str, archivo: Path, confirmar: bool, sesion=None) -> dict:
    datos, _ = leer_borrador(archivo)
    if datos.get("estado") == "creada":
        raise ErrorRadiografia(f"El borrador ya se creó en Jira como {datos.get('jira')}.")
    errores = validar(raiz, producto, archivo)
    if errores:
        raise ErrorRadiografia(f"El borrador tiene {len(errores)} error(es); no se puede crear:\n  - " + "\n  - ".join(errores))
    env = cargar_env(raiz)
    faltantes = [v for v in ("JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN") if not env.get(v)]
    if faltantes:
        raise ErrorRadiografia(f"Faltan variables de Jira en .env: {', '.join(faltantes)}.")
    cliente = modulo_historias.ClienteJira(env["JIRA_URL"], env["JIRA_EMAIL"], env["JIRA_TOKEN"], sesion)
    campos_jira = cliente._respuesta(cliente.sesion.get(f"{cliente.url}/rest/api/3/field", timeout=30))
    solicitud = armar_solicitud(raiz, producto, archivo, campos_jira)
    vista_previa = archivo.with_name(archivo.stem + "-jira.json")
    vista_previa.write_text(json.dumps(solicitud, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not confirmar:
        return {"creada": False, "solicitud": solicitud, "vista_previa": vista_previa}
    respuesta = cliente._respuesta(cliente.sesion.post(f"{cliente.url}/rest/api/3/issue", json=solicitud, timeout=60))
    clave = respuesta["key"]
    datos_actuales, cuerpo = leer_borrador(archivo)
    datos_actuales.update({"estado": "creada", "jira": clave, "creada": date.today().isoformat()})
    escribir_borrador(archivo, datos_actuales, cuerpo)
    if datos_actuales.get("hallazgos"):
        registro = registro_hallazgos.cargar(raiz, producto)
        for h in registro["hallazgos"].values():
            if h["id"] in datos_actuales["hallazgos"]:
                h["historia_jira"] = clave
        registro_hallazgos.guardar(raiz, producto, registro)
    return {"creada": True, "clave": clave, "url": f"{cliente.url}/browse/{clave}", "solicitud": solicitud}


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None, sesion=None) -> int:
    parser = argparse.ArgumentParser(description="Tareas, Spikes y Bugs del equipo.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("nueva")
    p.add_argument("producto")
    p.add_argument("--tipo", required=True, choices=TIPOS)
    p.add_argument("--categoria")
    p.add_argument("--titulo", required=True)
    p.add_argument("--desde", default="")
    p.add_argument("--repos", default="")
    p.add_argument("--tema")
    p = sub.add_parser("validar")
    p.add_argument("producto")
    p.add_argument("borrador")
    p = sub.add_parser("listar")
    p.add_argument("producto")
    p = sub.add_parser("crear")
    p.add_argument("producto")
    p.add_argument("borrador")
    p.add_argument("--confirmar", action="store_true", help="crea la incidencia en Jira; sin esto solo muestra la vista previa")
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    separar = lambda texto: [v.strip() for v in texto.split(",") if v.strip()]  # noqa: E731
    try:
        if o.accion == "nueva":
            borrador, archivo_contexto = nueva(raiz, o.producto, o.tipo, o.categoria, o.titulo, separar(o.desde),
                                               separar(o.repos), o.tema)
            print(f"Borrador: {borrador.relative_to(raiz)}\nContexto: {archivo_contexto.relative_to(raiz)}")
        elif o.accion == "validar":
            errores = validar(raiz, o.producto, resolver_borrador(raiz, o.producto, o.borrador))
            if not errores:
                print("El borrador cumple ADR-EQ-008 y la regla de lenguaje.")
            for error in errores:
                print(f"  ERROR: {error}")
            return 1 if errores else 0
        elif o.accion == "listar":
            filas = listar(raiz, o.producto)
            if not filas:
                print("No hay borradores.")
            for f in filas:
                print(f"  {f['archivo']} · {f['tipo_incidencia']} · {f['tipo']} · {f['estado']}"
                      + (f" · {f['jira']}" if f["jira"] else "") + f" · {f['titulo']}")
        elif o.accion == "crear":
            r = crear(raiz, o.producto, resolver_borrador(raiz, o.producto, o.borrador), o.confirmar, sesion)
            campos = r["solicitud"]["fields"]
            print(f"Proyecto: {campos['project']['key']} · Tipo de incidencia: {campos['issuetype']['name']} · "
                  f"Título: {campos['summary']}" + (f" · Etiquetas: {', '.join(campos['labels'])}" if campos.get("labels") else ""))
            if r["creada"]:
                print(f"Creada en Jira: {r['clave']} ({r['url']}).")
            else:
                print(f"Vista previa (no se creó nada): {r['vista_previa'].relative_to(raiz)}. Para crearla: --confirmar.")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
