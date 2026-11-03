"""Ficha de un repositorio (as-is/<repo>.md): lo importante primero.

Orden: resumen (veredicto, qué se incumple y qué hacer primero), hallazgos agrupados, cómo es hoy, componentes y
cumplimiento, y al final los datos técnicos. Se recompone cada vez que cambia una parte, sin repetir la revisión.
"""

from __future__ import annotations

import re
from pathlib import Path

import hallazgos as registro_hallazgos
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
    cantidad = len(g["ids"])
    return g["titulo"].replace("|", "/") + (f" ({cantidad} casos)" if cantidad > 1 else "")


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


def texto_resumen(raiz: Path, producto: str, repo: str, rama: str, registro: dict, revision: str | None) -> str:
    lista = abiertos(registro, repo, rama)
    lineas = [f"**Veredicto: {veredicto(registro, repo, rama)}**" + (f" · revisión `{revision}`" if revision else ""), "",
              "| Severidad | Cuentan para el veredicto | Informativos |", "|---|---|---|"]
    for s in SEVERIDADES:
        lineas.append(f"| {s.capitalize()} | {sum(1 for h in lista if h['severidad'] == s and cuenta(h))} "
                      f"| {sum(1 for h in lista if h['severidad'] == s and not cuenta(h))} |")
    lineas += ["", "Informativos: hallazgos de ADR en Propuesto, aceptados como deuda o marcados como falso positivo. No cambian el "
               "veredicto.", "", "## Qué se incumple"]
    nombres = titulos(raiz, producto)
    por_nivel: dict[int, dict[str, list[dict]]] = {}
    for h in lista:
        por_nivel.setdefault(h["nivel"], {}).setdefault(regla_de(h), []).append(h)
    if not por_nivel:
        lineas.append("Nada: no hay hallazgos abiertos.")
    for nivel in sorted(por_nivel):
        lineas += ["", f"**{NIVELES.get(nivel, f'Nivel {nivel}')}**", ""]
        if nivel == 5:
            lineas.append(f"- {len(por_nivel[nivel].get('sonar', [])) or sum(len(v) for v in por_nivel[nivel].values())} issue(s) de Sonar")
            continue
        for regla, hallazgos in sorted(por_nivel[nivel].items()):
            criterios = sorted({h["criterio"] for h in hallazgos if h.get("criterio")})
            estado = "cuenta" if any(cuenta(h) for h in hallazgos) else "informativo"
            lineas.append(f"- `{regla}` {nombres.get(regla, '')}".rstrip() + f": {len(hallazgos)} hallazgo(s), {estado}"
                          + (f" (criterios {', '.join(criterios)})" if criterios else ""))
    lineas += ["", "## Qué hacer primero", ""]
    acciones = grupos(lista)[:MAXIMO_ACCIONES]
    lineas += [f"{n}. {que(g)}: {donde(g)} ({', '.join(g['ids'][:3])}{'…' if len(g['ids']) > 3 else ''})"
               for n, g in enumerate(acciones, start=1)] or ["Nada pendiente."]
    return "## Resumen\n\n" + "\n".join(lineas)


def texto_hallazgos(registro: dict, repo: str, rama: str) -> str:
    lista = grupos(abiertos(registro, repo, rama))
    lineas = ["## Hallazgos", "", "> De lo más grave a lo menos. Los repetidos en el mismo archivo van en una fila.", ""]
    if not lista:
        return "\n".join(lineas + ["Sin hallazgos abiertos."])
    lineas += ["| Severidad | Cuenta | Regla | Qué | Dónde | IDs |", "|---|---|---|---|---|---|"]
    for g in lista:
        lineas.append(f"| {g['severidad']} | {'sí' if g['cuenta'] else 'no'} | {g['regla']} | {que(g)} | {donde(g)} "
                      f"| {', '.join(g['ids'])} |")
    return "\n".join(lineas)


def limpiar_automatico(texto: str) -> str:
    """Datos técnicos al final: sin la tabla de hallazgos (ya está arriba) y con el error de Sonar en una línea."""
    texto = re.sub(r"\n## Hallazgos automáticos abiertos\n.*?(?=\n## |\n<!-- )", "", texto, flags=re.S)
    texto = texto.replace("## Datos generales", "## Datos técnicos")
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
    texto = reemplazar_bloque(texto, MARCA_RESUMEN, texto_resumen(raiz, producto, repo, rama, registro, revision))
    texto = reemplazar_bloque(texto, MARCA_HALLAZGOS, texto_hallazgos(registro, repo, rama))
    automatico = bloque(texto, MARCA_AUTOMATICO)
    if automatico:
        texto = texto.replace(automatico, limpiar_automatico(automatico))
    partes = [b for marcas in ORDEN if (b := bloque(texto, marcas))]
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(f"# {repo}\n\n" + "\n\n".join(partes) + "\n", encoding="utf-8")
    return archivo
