"""Ficha de un repositorio (as-is/<repo>.md): lo importante primero.

Orden: resumen (veredicto, qué se incumple y qué hacer primero), hallazgos agrupados, cómo es hoy, componentes y
cumplimiento, y al final los datos técnicos. Se recompone cada vez que cambia una parte, sin repetir la revisión.
"""

from __future__ import annotations

import re
from pathlib import Path

import hallazgos as registro_hallazgos
from comun import leer_json
from coherencia import leer_arquitectura_vigente, leer_decisiones_equipo, leer_decisiones_producto
from revisar import MARCA_AUTOMATICO, MARCA_REVISION, descontado_por_triaje, reemplazar_bloque, veredicto

MARCA_RESUMEN = ("<!-- resumen:inicio -->", "<!-- resumen:fin -->")
MARCA_HALLAZGOS = ("<!-- hallazgos:inicio -->", "<!-- hallazgos:fin -->")
MARCA_COMPARACION = ("<!-- comparacion:inicio -->", "<!-- comparacion:fin -->")
ORDEN = (MARCA_RESUMEN, MARCA_HALLAZGOS, MARCA_REVISION, MARCA_COMPARACION, MARCA_AUTOMATICO)
SEVERIDADES = ("bloqueante", "alta", "media", "baja")
NIVELES = {1: "ADR de arquitectura", 2: "Estándares de arquitectura", 3: "ADR de equipo", 4: "ADR del producto", 5: "Sonar"}
MAXIMO_ACCIONES = 5
MAXIMO_LINEAS = 6


def cuenta(h: dict) -> bool:
    """Si el hallazgo cuenta para el veredicto: regla vigente, no descontado por el triaje ni repetido en otro nivel."""
    return h["modo"] == "vigente" and not h.get("absorbido_por") and not descontado_por_triaje(h)


def abiertos(registro: dict, repo: str, rama: str) -> list[dict]:
    return [h for h in registro["hallazgos"].values()
            if h["repo"] == repo and h["rama"] == rama and h["estado"] == "abierto" and not h.get("absorbido_por")]


def grupos(lista: list[dict]) -> list[dict]:
    """Un grupo por regla y archivo: los repetidos, por ejemplo varios secretos del mismo archivo, van en una fila."""
    por_clave: dict[tuple, dict] = {}
    for h in lista:
        archivo = h["evidencia"][0]["archivo"] if h["evidencia"] else "—"
        g = por_clave.setdefault((h["criterio"] or h["fuente"], archivo, h["titulo"] if not h["evidencia"] else ""), {
            "regla": h["criterio"] or h["fuente"], "nivel": h["nivel"], "severidad": h["severidad"], "cuenta": cuenta(h),
            "titulo": h["titulo"], "archivo": archivo, "lineas": [], "ids": []})
        g["ids"].append(h["id"])
        g["lineas"] += [e["linea"] for e in h["evidencia"] if e.get("linea") and e["archivo"] == archivo]
        g["cuenta"] = g["cuenta"] or cuenta(h)
        if SEVERIDADES.index(h["severidad"]) < SEVERIDADES.index(g["severidad"]):
            g["severidad"] = h["severidad"]
    return sorted(por_clave.values(), key=lambda g: (not g["cuenta"], SEVERIDADES.index(g["severidad"]), g["nivel"], g["ids"][0]))


def url_web(url_git: str, commit: str | None) -> str | None:
    """Dirección web del repositorio en el commit revisado, o None si no es de GitLab ni de GitHub (por ejemplo, una carpeta local)."""
    texto = url_git.strip().removesuffix("/").removesuffix(".git")
    coincidencia = (re.match(r"^[\w.-]+@([\w.-]+):(.+)$", texto)
                    or re.match(r"^(?:https?|ssh)://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", texto))
    if not coincidencia or not commit:
        return None
    servidor, proyecto = coincidencia.groups()
    separador = "/blob/" if "github" in servidor else "/-/blob/"  # GitLab, incluido el propio de la empresa
    return f"https://{servidor}/{proyecto}{separador}{commit}"


def donde(g: dict, base: str | None = None) -> str:
    lineas = sorted(set(g["lineas"]))
    archivo = f"[`{g['archivo']}`]({base}/{g['archivo']})" if base and g["archivo"] != "—" else f"`{g['archivo']}`"
    if not lineas:
        return archivo
    numeros = [f"[{n}]({base}/{g['archivo']}#L{n})" if base else str(n) for n in lineas[:MAXIMO_LINEAS]]
    texto = ", ".join(numeros) + (f" y {len(lineas) - MAXIMO_LINEAS} más" if len(lineas) > MAXIMO_LINEAS else "")
    return f"{archivo} (línea{'s' if len(lineas) > 1 else ''} {texto})"


def que(g: dict) -> str:
    """El texto del hallazgo sin la ruta, que ya va en «Dónde»."""
    cantidad = len(g["ids"])
    titulo = g["titulo"].replace(f" en {g['archivo']}", "").replace(f" ({g['archivo']})", "").replace("|", "/")
    return titulo + (f" ({cantidad} casos)" if cantidad > 1 else "")


def titulos(raiz: Path, producto: str) -> dict[str, str]:
    """Título de cada documento o decisión, por su clave (fuente:ID de arquitectura, o ADR-XX-NNN)."""
    nombres = {c: re.sub(r"^[A-Z]+-\d+:\s*", "", d["titulo"]) for c, d in leer_arquitectura_vigente(raiz).items()}
    nombres.update({i: d["titulo"] for i, d in leer_decisiones_equipo(raiz).items()})
    nombres.update({i: d["titulo"] for i, d in leer_decisiones_producto(raiz, producto).items()})
    return nombres


def regla_de(h: dict) -> str:
    """Documento o decisión que se incumple: el criterio EQ-002.3 pertenece a ADR-EQ-002."""
    if h["nivel"] in (3, 4) and h.get("criterio"):
        return "ADR-" + h["criterio"].rsplit(".", 1)[0]
    return h["fuente"]


TEXTO = {"CUMPLE": "Cumple", "NO CUMPLE": "No cumple", "NO APLICA": "No aplica", "NO DETERMINADO": "Sin evidencia suficiente"}
AFECTA = ("«Afecta el veredicto» es «Sí» cuando la regla está vigente. Es «No» cuando la regla es un ADR en Propuesto, una deuda "
          "aceptada o un falso positivo: se informa, pero no cambia el veredicto.")
ETIQUETAS = ("> Cómo leer la evidencia: **[hecho]** verificado en el código, en el archivo y la línea indicados; **[doc]** lo dice "
             "la documentación del repositorio o del producto; **[inferencia]** deducción sin verificación directa.")
ANEXOS = ("Anexos: [A. Hallazgos](#anexo-a-hallazgos) · [B. Cómo es hoy](#anexo-b-cómo-es-hoy) · "
          "[C. Componentes](#anexo-c-componentes) · [D. Cumplimiento regla por regla](#anexo-d-cumplimiento-regla-por-regla) · "
          "[E. Datos técnicos](#anexo-e-datos-técnicos)")


def estado_fuente(conteo: dict, vigente: bool) -> str:
    if not sum(conteo.values()):
        return "Sin evaluar"
    if conteo.get("NO CUMPLE"):
        return "No cumple" if vigente else "Informativo"
    if conteo.get("CUMPLE"):
        return "Cumple" if not conteo.get("NO DETERMINADO") else "Cumple en lo evaluado"
    return "No aplica" if not conteo.get("NO DETERMINADO") else "Sin evidencia suficiente"


def conclusion(repo: str, lista: list[dict], nombres: dict[str, str], sin_evidencia: int) -> str:
    vigentes = sorted({regla_de(h) for h in lista if cuenta(h)})
    if not vigentes:
        texto = f"{repo} cumple las reglas vigentes evaluadas."
    else:
        reglas = [nombres.get(r) or r for r in vigentes]
        texto = (f"{repo} no cumple {len(vigentes)} regla(s) vigente(s): {', '.join(reglas[:-1]) + ' y ' + reglas[-1] if len(reglas) > 1 else reglas[0]}. "
                 f"El riesgo principal: {(lambda s: s[:1].lower() + s[1:])(que(grupos(lista)[0]).rstrip('.'))}.")
    if sin_evidencia:
        texto += f" {sin_evidencia} regla(s) no se pudieron confirmar desde el repositorio."
    return texto


def texto_resumen(raiz: Path, producto: str, repo: str, rama: str, registro: dict, estado: dict,
                  evaluaciones: dict, verificaciones: list[dict], sonar_estado: dict) -> str:
    from collections import Counter
    lista = abiertos(registro, repo, rama)
    nombres = titulos(raiz, producto)
    codigo = estado.get("codigo") or estado.get("automatica") or {}
    dictamen = veredicto(registro, repo, rama)
    conteos = {n: Counter(e["resultado"] for e in evaluaciones.values() if e["nivel"] == n) for n in (1, 2, 3, 4)}
    conteos[3] += Counter(v["resultado"] for v in verificaciones)
    vigencia = {n: any(e["modo"] == "vigente" for e in evaluaciones.values() if e["nivel"] == n) for n in (1, 2, 3, 4)}
    sin_evidencia = sum(c.get("NO DETERMINADO", 0) for c in conteos.values())
    lineas = ["| Producto | Commit revisado | Fecha | Veredicto |", "|---|---|---|---|",
              f"| {producto} | {str(codigo.get('commit', '—'))[:7]} | {codigo.get('fecha', '—')} | "
              f"**{'Aprobado' if dictamen == 'PASA' else 'No aprobado'}** |", "",
              "## Conclusión", "", conclusion(repo, lista, nombres, sin_evidencia), "",
              "## Estado por fuente", "", "| Fuente | Estado | Incumplimientos | Sin evidencia suficiente |", "|---|---|---|---|"]
    for n in (1, 2, 3, 4):
        nombre = NIVELES[n] + (" (en Propuesto)" if n == 3 and not vigencia[3] and sum(conteos[3].values()) else "")
        lineas.append(f"| {nombre} | {estado_fuente(conteos[n], vigencia[n] or n in (1, 2))} | {conteos[n].get('NO CUMPLE', 0)} "
                      f"| {conteos[n].get('NO DETERMINADO', 0)} |")
    if sonar_estado.get("estado") == "ok":
        lineas.append(f"| Sonar | Quality gate {sonar_estado.get('quality_gate') or '—'} | {sum(1 for h in lista if h['nivel'] == 5)} | — |")
    else:
        lineas.append("| Sonar | No disponible | — | — |")
    lineas += ["", "## Riesgos principales", ""]
    principales = grupos(lista)[:MAXIMO_ACCIONES]
    if principales:
        lineas += ["| Prioridad | Riesgo | Regla incumplida | Severidad |", "|---|---|---|---|"]
        for n, g in enumerate(principales, start=1):
            regla = regla_de({"nivel": g["nivel"], "criterio": g["regla"] if g["nivel"] in (3, 4) else None, "fuente": g["regla"]})
            lineas.append(f"| {n} | {que(g)} | {nombres.get(regla) or regla}{'' if g['cuenta'] else ' (no afecta el veredicto)'} "
                          f"| {g['severidad'].capitalize()} |")
    else:
        lineas.append("Sin riesgos abiertos.")
    pendientes = []
    informativos = sum(1 for h in lista if not cuenta(h))
    if informativos:
        pendientes.append(f"**Reglas en Propuesto:** {informativos} hallazgo(s) no afectan el veredicto mientras sus ADR no se aprueben.")
    if sin_evidencia:
        pendientes.append(f"**Sin evidencia suficiente:** {sin_evidencia} regla(s) necesitan información que no está en el repositorio, "
                          "por ejemplo el tier del servicio, sus alertas o Sonar.")
    if sonar_estado.get("estado") != "ok":
        pendientes.append("**Sonar:** no se pudo consultar; su calidad de código queda sin evaluar.")
    lineas += ["", "## Decisiones pendientes", "", *([f"- {p}" for p in pendientes] or ["Ninguna."]), "", "---", "", ANEXOS]
    return "\n".join(lineas)


def ancla(id_hallazgo: str) -> str:
    """Destino de un enlace a un hallazgo, en su fila del Anexo A."""
    return f'<a id="{id_hallazgo.lower()}"></a>{id_hallazgo}'


def enlace(id_hallazgo: str) -> str:
    return f"[{id_hallazgo}](#{id_hallazgo.lower()})"


def texto_hallazgos(registro: dict, repo: str, rama: str, base: str | None = None) -> str:
    lista = grupos(abiertos(registro, repo, rama))
    lineas = ["## Anexo A. Hallazgos", "", AFECTA, "", "De lo más grave a lo menos. Los repetidos en el mismo archivo van en una fila.", ""]
    if not lista:
        return "\n".join(lineas + ["Sin hallazgos abiertos."])
    lineas += ["| Severidad | Afecta el veredicto | Regla | Qué | Dónde | IDs |", "|---|---|---|---|---|---|"]
    for g in lista:
        lineas.append(f"| {g['severidad'].capitalize()} | {'Sí' if g['cuenta'] else 'No'} | {g['regla']} | {que(g)} | {donde(g, base)} "
                      f"| {', '.join(ancla(i) for i in g['ids'])} |")
    return "\n".join(lineas)


VERIFICACIONES = re.compile(r"\n## Verificaciones automáticas de las decisiones del equipo\n.*?(?=\n## |\n<!-- )", re.S)


def verificaciones_en_cumplimiento(texto: str, verificaciones: list[dict]) -> str:
    """Las verificaciones automáticas van con el cumplimiento; las que no cumplen ya están en Hallazgos."""
    automatico, comparacion = bloque(texto, MARCA_AUTOMATICO), bloque(texto, MARCA_COMPARACION)
    if not automatico or not comparacion or not verificaciones:
        return texto
    no_cumplen = [v["criterio"] for v in verificaciones if v["resultado"] == "NO CUMPLE"]
    lineas = ["", "### Verificaciones automáticas", "",
              *([f"No cumplen, y están en el [Anexo A](#anexo-a-hallazgos): {', '.join(no_cumplen)}.", ""] if no_cumplen else []),
              "| Regla | Resultado | Motivo |", "|---|---|---|",
              *(f"| {v['criterio']} | {TEXTO[v['resultado']]} | {v['motivo'].replace('|', '/')} |"
                for v in verificaciones if v["resultado"] != "NO CUMPLE")]
    nueva = re.sub(r"\n### Verificaciones automáticas\n.*?(?=\n### |\n<!-- )", "", comparacion, flags=re.S)
    nueva = nueva.replace(MARCA_COMPARACION[1], "").rstrip() + "\n" + "\n".join(lineas).rstrip() + "\n" + MARCA_COMPARACION[1]
    return texto.replace(comparacion, nueva).replace(automatico, VERIFICACIONES.sub("", automatico))


def limpiar_automatico(texto: str) -> str:
    """Datos técnicos al final: sin la tabla de hallazgos (ya está arriba) y con el error de Sonar en una línea."""
    texto = re.sub(r"\n## Hallazgos automáticos abiertos\n.*?(?=\n## |\n<!-- )", "", texto, flags=re.S)
    texto = re.sub(r"^## (Datos generales|Datos técnicos)$", "## Anexo E. Datos técnicos", texto, flags=re.M)
    texto = re.sub(r"^## Sonar$", "### Sonar", texto, flags=re.M).replace("| Revisión |", "| Revisión automática |")
    def sonar_breve(m: re.Match) -> str:
        motivo = m.group(1)
        if "CERTIFICATE_VERIFY_FAILED" in motivo:
            return "NO DETERMINADO - el certificado TLS de Sonar no se reconoce: configurar `CA_BUNDLE` en `.env`."
        return "NO DETERMINADO - " + (motivo[:200] + "…" if len(motivo) > 200 else motivo)
    return re.sub(r"^NO DETERMINADO - (.*)$", sonar_breve, texto, count=1, flags=re.M)


def bloque(texto: str, marcas: tuple[str, str]) -> str | None:
    coincidencia = re.search(re.escape(marcas[0]) + r".*?" + re.escape(marcas[1]), texto, re.DOTALL)
    return coincidencia.group(0) if coincidencia else None


def componer(raiz: Path, producto: str, repo: str) -> Path:
    archivo = raiz / "productos" / producto / "as-is" / f"{repo}.md"
    texto = archivo.read_text(encoding="utf-8") if archivo.exists() else ""
    registro = registro_hallazgos.cargar(raiz, producto)
    estado = (registro.get("repos") or {}).get(repo) or {}
    rama = estado.get("rama", "main")
    revision = (estado.get("codigo") or estado.get("automatica") or {}).get("id")
    automatica, codigo = estado.get("automatica") or {}, estado.get("codigo") or {}
    carpeta = raiz / "productos" / producto / "revisiones"
    datos = leer_json(carpeta / str(automatica.get("id")) / f"{repo}.json") if automatica else {}
    sonar_estado = dict(datos.get("sonar") or {})
    if sonar_estado.get("estado") == "ok":
        sonar_estado["quality_gate"] = (leer_json(carpeta / str(automatica.get("id")) / "crudo" / f"{repo}-sonar.json")
                                        .get("quality_gate") or {}).get("estado")
    evaluaciones = leer_json(carpeta / str(codigo.get("id")) / "revision" / f"{repo}.json").get("evaluaciones", {}) if codigo else {}
    verificaciones = datos.get("verificaciones") or []
    texto = reemplazar_bloque(texto, MARCA_RESUMEN, texto_resumen(raiz, producto, repo, rama, registro, estado, evaluaciones,
                                                                  verificaciones, sonar_estado))
    import productos
    datos_repo = next((r for r in productos.repos_de(productos.leer_productos(raiz).get(producto) or {}) if str(r["id"]) == repo), {})
    base = url_web(str(datos_repo.get("url") or ""), (estado.get("codigo") or estado.get("automatica") or {}).get("commit"))
    texto = reemplazar_bloque(texto, MARCA_HALLAZGOS, texto_hallazgos(registro, repo, rama, base))
    automatico = bloque(texto, MARCA_AUTOMATICO)
    if automatico:
        texto = texto.replace(automatico, limpiar_automatico(automatico))
    texto = verificaciones_en_cumplimiento(texto, verificaciones)
    revision_codigo = bloque(texto, MARCA_REVISION)
    if revision_codigo:
        nuevo_bloque = re.sub(r"^## (Revisión de código|Cómo es hoy \(revisión de código\))\n(\n> Cómo leer la evidencia:.*\n)?",
                              "## Anexo B. Cómo es hoy\n\n" + ETIQUETAS + "\n", revision_codigo, count=1, flags=re.M)
        nuevo_bloque = re.sub(r"(> Cómo leer la evidencia:.*\n)\n+", r"\1\n", nuevo_bloque)
        nuevo_bloque = re.sub(r"^## (?!Anexo )", "### ", nuevo_bloque, flags=re.M)
        texto = texto.replace(revision_codigo, nuevo_bloque)
    comparacion = bloque(texto, MARCA_COMPARACION)
    if comparacion:
        texto = texto.replace(comparacion, comparacion.replace("## Componentes\n", "## Anexo C. Componentes\n").replace(
            "## Detalle del cumplimiento\n", "## Anexo D. Cumplimiento regla por regla\n"))
    texto = re.sub(r"^> Revisión `[^`]+` sobre el commit `[^`]+`\.\n\n?", "", texto, flags=re.M)  # el commit ya está en Datos técnicos
    partes = [b for marcas in ORDEN if (b := bloque(texto, marcas))]
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(f"# {repo} · Revisión de arquitectura\n\n" + "\n\n".join(partes) + "\n", encoding="utf-8")
    return archivo
