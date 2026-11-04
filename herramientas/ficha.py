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


def donde(g: dict) -> str:
    lineas = sorted(set(g["lineas"]))
    if not lineas:
        return f"`{g['archivo']}`"
    texto = ", ".join(map(str, lineas[:MAXIMO_LINEAS])) + (f" y {len(lineas) - MAXIMO_LINEAS} más" if len(lineas) > MAXIMO_LINEAS else "")
    return f"`{g['archivo']}` (línea{'s' if len(lineas) > 1 else ''} {texto})"


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


SI, NO = "🚫 Sí", "💬 No"
AFECTA = ("**Afecta el veredicto:** 🚫 Sí, si la regla está vigente. 💬 No, si es un ADR en Propuesto, una deuda aceptada o un "
          "falso positivo: se informa, pero no cambia el veredicto.")
ETIQUETAS = ("> Cómo leer la evidencia: **[hecho]** verificado en el código, en el archivo y la línea indicados; **[doc]** lo dice "
             "la documentación del repositorio o del producto; **[inferencia]** deducción sin verificación directa.")


def fila_cumplimiento(nombre: str, conteo: dict) -> str:
    evaluados = sum(conteo.values())
    resultado = ("Sin evaluar" if not evaluados else "🚫 No cumple" if conteo.get("NO CUMPLE") else
                 "🔍 Incompleto" if conteo.get("NO DETERMINADO") else "🔹 No aplica" if not conteo.get("CUMPLE") else "✅ Cumple")
    return (f"| {nombre} | {resultado} | {conteo.get('CUMPLE', 0)} | {conteo.get('NO CUMPLE', 0)} | {conteo.get('NO DETERMINADO', 0)} "
            f"| {conteo.get('NO APLICA', 0)} |")


def tabla_cumplimiento(evaluaciones: dict, verificaciones: list[dict], sonar_estado: dict, sonar_abiertos: int) -> list[str]:
    from collections import Counter
    lineas = ["| Qué se revisó | Resultado | ✅ Cumple | 🚫 No cumple | 🔍 No determinado | 🔹 No aplica |", "|---|---|---|---|---|---|"]
    for nivel in (1, 2, 3, 4):
        lineas.append(fila_cumplimiento(NIVELES[nivel], Counter(e["resultado"] for e in evaluaciones.values() if e["nivel"] == nivel)))
    lineas.append(fila_cumplimiento("Verificaciones automáticas", Counter(v["resultado"] for v in verificaciones)))
    if sonar_estado.get("estado") == "ok":
        compuerta = sonar_estado.get("quality_gate") or "—"
        lineas.append(f"| Sonar | {'✅' if compuerta == 'OK' else '🚫'} Quality gate {compuerta}, {sonar_abiertos} issue(s) | — | — | — | — |")
    else:
        lineas.append("| Sonar | 🔍 No se pudo consultar | — | — | — | — |")
    return lineas


def texto_resumen(raiz: Path, producto: str, repo: str, rama: str, registro: dict, revision: str | None,
                  evaluaciones: dict, verificaciones: list[dict], sonar_estado: dict) -> str:
    lista = abiertos(registro, repo, rama)
    lineas = [f"**Veredicto: {veredicto(registro, repo, rama)}**" + (f" · revisión `{revision}`" if revision else ""), "",
              "## Cumplimiento", "", *tabla_cumplimiento(evaluaciones, verificaciones, sonar_estado, sum(1 for h in lista if h["nivel"] == 5)),
              "", "El detalle de cada regla está al final, en [Detalle del cumplimiento](#detalle-del-cumplimiento).", "",
              "## Qué se incumple", ""]
    nombres = titulos(raiz, producto)
    por_nivel: dict[int, dict[str, list[dict]]] = {}
    for h in lista:
        por_nivel.setdefault(h["nivel"], {}).setdefault(regla_de(h), []).append(h)
    for nivel in [1, 2, 3, *[n for n in (4, 5) if n in por_nivel]]:
        lineas += [f"**{NIVELES[nivel]}**", ""]
        reglas = por_nivel.get(nivel, {})
        if not reglas:
            lineas += ["✅ Ninguno.", ""]
            continue
        if nivel == 5:
            lineas += [f"- {sum(len(v) for v in reglas.values())} issue(s) de Sonar", ""]
            continue
        for regla, hallazgos in sorted(reglas.items()):
            criterios = sorted({h["criterio"] for h in hallazgos if h.get("criterio")})
            afecta = any(cuenta(h) for h in hallazgos)
            lineas.append(f"- {'🚫' if afecta else '💬'} `{regla}` {nombres.get(regla, '')}".rstrip()
                          + f": {len(hallazgos)} hallazgo(s), {'afecta' if afecta else 'no afecta'} el veredicto"
                          + (f" (criterios {', '.join(criterios)})" if criterios else ""))
        lineas.append("")
    lineas += ["## Qué hacer primero", ""]
    acciones = grupos(lista)[:MAXIMO_ACCIONES]
    lineas += [f"{n}. {que(g)} ({', '.join(g['ids'][:3])}{'…' if len(g['ids']) > 3 else ''})"
               for n, g in enumerate(acciones, start=1)] or ["Nada pendiente."]
    if acciones:
        lineas += ["", "Dónde está cada uno: [Hallazgos](#hallazgos)."]
    return "## Resumen\n\n" + "\n".join(lineas)


def texto_hallazgos(registro: dict, repo: str, rama: str) -> str:
    lista = grupos(abiertos(registro, repo, rama))
    todos = abiertos(registro, repo, rama)
    lineas = ["## Hallazgos", "", "| Severidad | 🚫 Afectan el veredicto | 💬 No afectan |", "|---|---|---|",
              *(f"| {s.capitalize()} | {sum(1 for h in todos if h['severidad'] == s and cuenta(h))} "
                f"| {sum(1 for h in todos if h['severidad'] == s and not cuenta(h))} |" for s in SEVERIDADES),
              "", AFECTA, "", "De lo más grave a lo menos. Los repetidos en el mismo archivo van en una fila.", ""]
    if not lista:
        return "\n".join(lineas + ["Sin hallazgos abiertos."])
    lineas += ["| Severidad | Afecta el veredicto | Regla | Qué | Dónde | IDs |", "|---|---|---|---|---|---|"]
    for g in lista:
        lineas.append(f"| {g['severidad']} | {SI if g['cuenta'] else NO} | {g['regla']} | {que(g)} | {donde(g)} "
                      f"| {', '.join(g['ids'])} |")
    return "\n".join(lineas)


VERIFICACIONES = re.compile(r"\n## Verificaciones automáticas de las decisiones del equipo\n.*?(?=\n## |\n<!-- )", re.S)
SIMBOLOS = {"CUMPLE": "✅", "NO CUMPLE": "🚫", "NO APLICA": "🔹", "NO DETERMINADO": "🔍"}


def verificaciones_en_cumplimiento(texto: str, verificaciones: list[dict]) -> str:
    """Las verificaciones automáticas van con el cumplimiento; las que no cumplen ya están en Hallazgos."""
    automatico, comparacion = bloque(texto, MARCA_AUTOMATICO), bloque(texto, MARCA_COMPARACION)
    if not automatico or not comparacion or not verificaciones:
        return texto
    no_cumplen = [v["criterio"] for v in verificaciones if v["resultado"] == "NO CUMPLE"]
    lineas = ["", "### Verificaciones automáticas", "",
              *([f"No cumplen, y están en [Hallazgos](#hallazgos): {', '.join(no_cumplen)}.", ""] if no_cumplen else []),
              "| Regla | Resultado | Motivo |", "|---|---|---|",
              *(f"| {v['criterio']} | {SIMBOLOS[v['resultado']]} {v['resultado']} | {v['motivo'].replace('|', '/')} |"
                for v in verificaciones if v["resultado"] != "NO CUMPLE")]
    nueva = re.sub(r"\n### Verificaciones automáticas\n.*?(?=\n### |\n<!-- )", "", comparacion, flags=re.S)
    nueva = nueva.replace(MARCA_COMPARACION[1], "").rstrip() + "\n" + "\n".join(lineas).rstrip() + "\n" + MARCA_COMPARACION[1]
    return texto.replace(comparacion, nueva).replace(automatico, VERIFICACIONES.sub("", automatico))


def limpiar_automatico(texto: str) -> str:
    """Datos técnicos al final: sin la tabla de hallazgos (ya está arriba) y con el error de Sonar en una línea."""
    texto = re.sub(r"\n## Hallazgos automáticos abiertos\n.*?(?=\n## |\n<!-- )", "", texto, flags=re.S)
    texto = texto.replace("## Datos generales", "## Datos técnicos").replace("| Revisión |", "| Revisión automática |")
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
    texto = reemplazar_bloque(texto, MARCA_RESUMEN, texto_resumen(raiz, producto, repo, rama, registro, revision, evaluaciones,
                                                                  verificaciones, sonar_estado))
    texto = reemplazar_bloque(texto, MARCA_HALLAZGOS, texto_hallazgos(registro, repo, rama))
    automatico = bloque(texto, MARCA_AUTOMATICO)
    if automatico:
        texto = texto.replace(automatico, limpiar_automatico(automatico))
    texto = verificaciones_en_cumplimiento(texto, verificaciones)
    revision_codigo = bloque(texto, MARCA_REVISION)
    if revision_codigo and ETIQUETAS not in revision_codigo:
        nuevo_bloque = revision_codigo.replace("## Revisión de código\n", "## Cómo es hoy (revisión de código)\n\n" + ETIQUETAS + "\n", 1)
        texto = texto.replace(revision_codigo, nuevo_bloque)
    texto = re.sub(r"^> Revisión `[^`]+` sobre el commit `[^`]+`\.\n\n?", "", texto, flags=re.M)  # el commit ya está en Datos técnicos
    partes = [b for marcas in ORDEN if (b := bloque(texto, marcas))]
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(f"# {repo}\n\n" + "\n\n".join(partes) + "\n", encoding="utf-8")
    return archivo
