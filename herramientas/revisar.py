"""Parte automática de /revisar: línea base AS IS de los repositorios de un producto.

Uso: python herramientas/revisar.py <producto> [--repo ID [--completa]] [--sin-sonar] [--raiz RUTA]

Para cada repositorio activo:
1. lo actualiza en productos/<producto>/repos/<id>/ (solo lectura);
2. detecta su stack y ejecuta gitleaks;
3. verifica los criterios automáticos de las decisiones del equipo;
4. consulta Sonar (quality gate, issues, hotspots, métricas y antigüedad del análisis);
5. actualiza productos/<producto>/estado/hallazgos.json y la sección automática de as-is/<repo>.md.

Deja el reporte en productos/<producto>/revisiones/<fecha>-linea-base[-<repo>]/. Con --repo, además genera
el paquete de revisión para la parte que hace Cursor. La revisión de código
(criterios de "revisión de código" y comparación con arquitectura) la completa el comando /revisar.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import hallazgos as registro_hallazgos
import productos
import sonar
import verificaciones
from adr import excepciones_activas
from coherencia import leer_decisiones_equipo, suspendidos as criterios_suspendidos
from comun import RAIZ, ErrorRadiografia, cargar_env, git, normalizar, leer_json

MARCA_AUTOMATICO = ("<!-- automatico:inicio -->", "<!-- automatico:fin -->")
MARCA_REVISION = ("<!-- revision:inicio -->", "<!-- revision:fin -->")
SEVERIDADES_INDIVIDUALES = ("bloqueante", "alta")


# --- Preparación -------------------------------------------------------------------------------

def decisiones_con_criterios(raiz: Path) -> dict[str, dict]:
    decisiones = leer_decisiones_equipo(raiz)
    for decision in decisiones.values():
        decision["tabla"] = verificaciones.leer_criterios(decision["texto"])
    return {k: v for k, v in decisiones.items() if normalizar(v["estado"]) in ("propuesto", "aprobado")}




def carpeta_reporte(raiz: Path, producto: str, repo: str | None) -> tuple[str, Path]:
    base = f"{date.today().isoformat()}-linea-base" + (f"-{repo}" if repo else "")
    carpeta_reportes = raiz / "productos" / producto / "revisiones"
    id_revision, numero = base, 2
    while (carpeta_reportes / id_revision).exists():
        id_revision, numero = f"{base}-{numero}", numero + 1
    return id_revision, carpeta_reportes / id_revision


# --- Sonar -------------------------------------------------------------------------------------

def hallazgos_sonar(datos: dict, id_repo: str, rama: str) -> list[dict]:
    """Issues bloqueantes y altos uno por uno; medios y bajos agrupados por regla."""
    base = {"nivel": 5, "origen": "sonar", "modo": "vigente"}
    resultado = []
    if datos["quality_gate"]["estado"] == "ERROR":
        condiciones = ", ".join(f"{c['metrica']} = {c['valor']} (umbral {c['umbral']})"
                                for c in datos["quality_gate"]["condiciones_fallidas"])
        resultado.append({**base, "huella": registro_hallazgos.huella(id_repo, rama, "sonar", "quality-gate"),
                          "fuente": "sonar:quality-gate", "criterio": None, "categoria": "deuda", "severidad": "alta",
                          "titulo": "Quality gate de Sonar en rojo", "detalle": f"Condiciones fallidas: {condiciones or 'sin detalle'}.",
                          "evidencia": []})
    grupos: dict[tuple[str, str], list[dict]] = {}
    for issue in datos["issues"]:
        if issue["severidad"] in SEVERIDADES_INDIVIDUALES:
            resultado.append({**base, "huella": registro_hallazgos.huella(id_repo, rama, "sonar", issue["clave"]),
                              "fuente": f"sonar:{issue['regla']}", "criterio": None, "categoria": issue["categoria"],
                              "severidad": issue["severidad"], "titulo": issue["mensaje"][:150],
                              "detalle": f"Regla {issue['regla']}.",
                              "evidencia": [{"archivo": issue["archivo"], "linea": issue["linea"]}] if issue["archivo"] else []})
        else:
            grupos.setdefault((issue["regla"], issue["severidad"]), []).append(issue)
    for (regla, severidad), lista in grupos.items():
        resultado.append({**base, "huella": registro_hallazgos.huella(id_repo, rama, "sonar", regla, severidad),
                          "fuente": f"sonar:{regla}", "criterio": None, "categoria": lista[0]["categoria"],
                          "severidad": severidad, "titulo": f"{len(lista)} issue(s) de la regla {regla}: {lista[0]['mensaje'][:100]}",
                          "detalle": f"{len(lista)} ocurrencia(s) agrupadas; se muestran hasta 5 ubicaciones.",
                          "evidencia": [{"archivo": i["archivo"], "linea": i["linea"]} for i in lista[:5] if i["archivo"]]})
    if datos["hotspots"]:
        resultado.append({**base, "huella": registro_hallazgos.huella(id_repo, rama, "sonar", "hotspots"),
                          "fuente": "sonar:hotspots", "criterio": None, "categoria": "seguridad", "severidad": "media",
                          "titulo": f"{len(datos['hotspots'])} security hotspot(s) sin revisar en Sonar",
                          "detalle": "Puntos sensibles de seguridad que Sonar marca para revisión manual.",
                          "evidencia": [{"archivo": h["archivo"], "linea": h["linea"]} for h in datos["hotspots"][:5] if h["archivo"]]})
    return resultado


def consultar_sonar(cliente: sonar.ClienteSonar | None, motivo_sin_cliente: str | None, clave: str | None,
                    commit: str) -> dict:
    if cliente is None:
        return {"estado": "NO DETERMINADO", "motivo": motivo_sin_cliente}
    if not clave:
        return {"estado": "NO DETERMINADO", "motivo": "el repositorio no tiene clave de Sonar en producto.yaml"}
    try:
        datos = sonar.recolectar(cliente, clave)
    except ErrorRadiografia as error:
        return {"estado": "NO DETERMINADO", "motivo": str(error)}
    analisis = datos["analisis"]
    if analisis is None:
        desfase = "el proyecto no tiene análisis"
    elif not analisis.get("commit"):
        desfase = "Sonar no informa el commit analizado"
    elif analisis["commit"] == commit:
        desfase = None
    else:
        desfase = f"Sonar analizó {analisis['commit'][:12]} ({(analisis.get('fecha') or '')[:10]}); se revisó {commit[:12]}"
    return {"estado": "ok", "datos": datos, "desfase": desfase}


# --- Ficha AS IS -------------------------------------------------------------------------------

def reemplazar_bloque(texto: str, marcas: tuple[str, str], contenido: str) -> str:
    bloque = f"{marcas[0]}\n{contenido.rstrip()}\n{marcas[1]}"
    patron = re.compile(re.escape(marcas[0]) + r".*?" + re.escape(marcas[1]), re.DOTALL)
    return patron.sub(lambda _: bloque, texto) if patron.search(texto) else texto.rstrip() + "\n\n" + bloque + "\n"


def escribir_ficha(raiz: Path, producto: str, repo: dict, revision: dict, registro: dict) -> None:
    archivo = raiz / "productos" / producto / "as-is" / f"{repo['id']}.md"
    archivo.parent.mkdir(parents=True, exist_ok=True)
    texto = archivo.read_text(encoding="utf-8") if archivo.exists() else f"# {repo['id']}: ficha AS IS\n"

    lineas = [
        "## Datos generales",
        "",
        "> Sección generada por la parte automática de /revisar. No se edita a mano.",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Producto | {producto} |",
        f"| Tipo | {repo['tipo']} |",
        f"| Rama | {repo['rama']} |",
        f"| Commit revisado | `{revision['commit'][:12]}` ({revision['fecha_commit']}) |",
        f"| Stack detectado | {', '.join(revision['stack']) or 'NO DETERMINADO'} |",
        f"| Revisión | {revision['id_revision']} |",
        "",
        "## Sonar",
        "",
    ]
    info = revision["sonar"]
    if info["estado"] != "ok":
        lineas.append(f"NO DETERMINADO - {info['motivo']}")
    else:
        datos = info["datos"]
        conteo = {s: sum(1 for i in datos["issues"] if i["severidad"] == s) for s in sonar.ORDEN_SEVERIDAD}
        lineas += [
            f"- Quality gate: **{datos['quality_gate']['estado']}**",
            f"- Último análisis: {info['desfase'] or 'corresponde al commit revisado'}",
            f"- Issues abiertos: {datos['issues_total']} (bloqueantes {conteo['bloqueante']}, altos {conteo['alta']}, "
            f"medios {conteo['media']}, bajos {conteo['baja']})" + (" (lista truncada)" if datos["issues_truncados"] else ""),
            f"- Security hotspots sin revisar: {len(datos['hotspots'])}",
            "",
            "| Métrica | Valor |",
            "|---|---|",
        ] + [f"| {m} | {v} |" for m, v in sorted(datos["metricas"].items())]

    lineas += ["", "## Verificaciones automáticas de las decisiones del equipo", "",
               "| Criterio | Resultado | Motivo |", "|---|---|---|"]
    for r in revision["verificaciones"]:
        lineas.append(f"| {r['criterio']} | {r['resultado']} | {r['motivo'].replace('|', '/')} |")

    abiertos = sorted((h for h in registro["hallazgos"].values()
                       if h["repo"] == repo["id"] and h["rama"] == repo["rama"] and h["estado"] == "abierto"
                       and h["origen"] != "revision"), key=lambda h: (h["nivel"], h["id"]))
    lineas += ["", "## Hallazgos automáticos abiertos", ""]
    if abiertos:
        lineas += ["| ID | Nivel | Fuente | Severidad | Modo | Título | Evidencia |", "|---|---|---|---|---|---|---|"]
        for h in abiertos:
            evidencia = ", ".join(f"`{e['archivo']}:{e['linea']}`" if e.get("linea") else f"`{e['archivo']}`"
                                  for e in h["evidencia"][:3]) or "—"
            lineas.append(f"| {h['id']} | {h['nivel']} | {h['criterio'] or h['fuente']} | {h['severidad']} "
                          f"| {h['modo']} | {h['titulo'].replace('|', '/')} | {evidencia} |")
    else:
        lineas.append("Sin hallazgos automáticos abiertos.")

    texto = reemplazar_bloque(texto, MARCA_AUTOMATICO, "\n".join(lineas))
    if MARCA_REVISION[0] not in texto:
        texto = reemplazar_bloque(texto, MARCA_REVISION,
                                  "## Revisión de código\n\nPendiente: completar con /revisar en Cursor "
                                  "(AS IS y comparación con arquitectura).")
    archivo.write_text(texto, encoding="utf-8")


# --- Revisión ----------------------------------------------------------------------------------

def revisar(raiz: Path, producto: str, solo_repo: str | None = None, usar_sonar: bool = True,
            cliente_sonar: sonar.ClienteSonar | None = None) -> dict:
    datos_producto = productos.leer_productos(raiz).get(producto)
    if datos_producto is None:
        raise ErrorRadiografia(f"No existe el producto '{producto}'. Crearlo con /producto.")
    repos = [dict(r) for r in productos.repos_de(datos_producto) if r.get("estado") == "activo"]
    if solo_repo:
        repos = [r for r in repos if r["id"] == solo_repo]
        if not repos:
            raise ErrorRadiografia(f"El producto '{producto}' no tiene un repositorio activo '{solo_repo}'.")
    if not repos:
        raise ErrorRadiografia(f"El producto '{producto}' no tiene repositorios activos.")

    motivo_sin_sonar = None
    if not usar_sonar:
        motivo_sin_sonar = "revisión ejecutada con --sin-sonar"
    elif cliente_sonar is None:
        env = cargar_env(raiz)
        config = sonar.ConfigSonar.desde_env(env)
        motivo_sin_sonar = sonar.ConfigSonar.motivo_sin_config(env)
        cliente_sonar = sonar.ClienteSonar(config) if config else None
    if not usar_sonar:
        cliente_sonar = None

    decisiones = decisiones_con_criterios(raiz)
    suspendidos = criterios_suspendidos(raiz, producto)
    id_revision, carpeta = carpeta_reporte(raiz, producto, solo_repo)
    carpeta.mkdir(parents=True)
    hoy = date.today().isoformat()

    sincronizados = {r["repo"]: r for r in productos.sincronizar(raiz, producto) if not solo_repo or r["repo"] == solo_repo}
    registro = registro_hallazgos.cargar(raiz, producto)
    resultados = []
    for repo in repos:
        sincronizacion = sincronizados.get(repo["id"], {})
        if sincronizacion.get("resultado") in ("error", "omitido") or "commit" not in sincronizacion:
            resultados.append({"repo": repo["id"], "estado": "NO DETERMINADO",
                               "motivo": sincronizacion.get("detalle", "no se pudo preparar el repositorio")})
            continue
        destino = raiz / "productos" / producto / "repos" / repo["id"]
        commit = sincronizacion["commit"]
        archivos = set(git("ls-tree", "-r", "--name-only", commit, cwd=destino).splitlines())
        gitleaks = verificaciones.ejecutar_gitleaks(destino)
        resultados_criterios, encontrados = verificaciones.verificar_repo(
            destino, repo["id"], repo["rama"], repo["tipo"], decisiones, suspendidos, gitleaks,
            excepciones_activas(raiz, producto, repo["id"]))
        info_sonar = consultar_sonar(cliente_sonar, motivo_sin_sonar, repo.get("sonar"), commit)
        origenes = {"verificacion"} | ({"gitleaks"} if gitleaks is not None else set())
        if info_sonar["estado"] == "ok":
            encontrados += hallazgos_sonar(info_sonar["datos"], repo["id"], repo["rama"])
            origenes.add("sonar")
        es_linea_base = not registro_hallazgos.tiene_revisiones(registro, repo["id"], repo["rama"])
        resumen = registro_hallazgos.aplicar(registro, repo["id"], repo["rama"], origenes, encontrados,
                                             id_revision, hoy, es_linea_base)
        estado_repo = registro.setdefault("repos", {}).setdefault(repo["id"], {})
        estado_repo.update({"rama": repo["rama"], "tipo": repo["tipo"],
                            "automatica": {"id": id_revision, "commit": commit, "fecha": hoy}})
        revision = {
            "repo": repo["id"], "rama": repo["rama"], "estado": "ok", "id_revision": id_revision, "commit": commit,
            "fecha_commit": sincronizacion["fecha"], "stack": productos.detectar_stack(destino, commit, archivos),
            "verificaciones": resultados_criterios, "sonar": info_sonar, "resumen": resumen,
        }
        (carpeta / "crudo").mkdir(exist_ok=True)
        if info_sonar["estado"] == "ok":
            (carpeta / "crudo" / f"{repo['id']}-sonar.json").write_text(
                json.dumps(info_sonar["datos"], indent=2, ensure_ascii=False), encoding="utf-8")
        (carpeta / f"{repo['id']}.json").write_text(json.dumps(
            {k: v for k, v in revision.items() if k != "sonar"} | {"sonar": {k: v for k, v in info_sonar.items() if k != "datos"}},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        escribir_ficha(raiz, producto, repo, revision, registro)
        resultados.append(revision)

    registro_hallazgos.guardar(raiz, producto, registro)
    contexto = {
        "id_revision": id_revision, "producto": producto, "fecha": hoy, "tipo": "linea-base",
        "arquitectura": leer_json(raiz / "arquitectura" / "estado" / "fuentes.lock"),
        "decisiones_equipo": {k: {"estado": v["estado"], "huella": v["huella"]} for k, v in decisiones.items()},
        "criterios_suspendidos": suspendidos,
        "repos": {r["repo"]: {"estado": r["estado"], "commit": r.get("commit")} for r in resultados},
    }
    (carpeta / "contexto.json").write_text(json.dumps(contexto, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    escribir_resumen(carpeta, producto, id_revision, resultados, registro)
    import indices
    indices.indice_producto(raiz, producto)
    return {"id_revision": id_revision, "carpeta": carpeta, "resultados": resultados}


def descontado_por_triaje(hallazgo: dict) -> bool:
    """Falsos positivos y deudas aceptadas no vencidas no cuentan para el veredicto."""
    triaje = hallazgo.get("triaje") or {}
    if triaje.get("decision") == "falso-positivo":
        return True
    return triaje.get("decision") == "deuda" and bool(triaje.get("vence")) and triaje["vence"] >= date.today().isoformat()


def veredicto(registro: dict, repo: str, rama: str) -> str:
    bloqueantes = [h for h in registro["hallazgos"].values()
                   if h["repo"] == repo and h["rama"] == rama and h["estado"] == "abierto" and h["modo"] == "vigente"
                   and h["severidad"] in SEVERIDADES_INDIVIDUALES and not h.get("absorbido_por")
                   and not descontado_por_triaje(h)]
    return f"NO PASA ({len(bloqueantes)} bloqueante(s) o alto(s) vigente(s))" if bloqueantes else "PASA"


def escribir_resumen(carpeta: Path, producto: str, id_revision: str, resultados: list[dict], registro: dict) -> None:
    lineas = [
        f"# Revisión {id_revision}: {producto}",
        "",
        "> Parte automática. El veredicto es preliminar hasta completar la revisión de código con /revisar.",
        "",
        "| Repositorio | Commit | Sonar | Nuevos | Corregidos | Reaparecidos | Abiertos | Veredicto preliminar |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        if r["estado"] != "ok":
            lineas.append(f"| {r['repo']} | — | — | — | — | — | — | NO DETERMINADO - {r['motivo']} |")
            continue
        resumen, info = r["resumen"], r["sonar"]
        estado_sonar = info["datos"]["quality_gate"]["estado"] if info["estado"] == "ok" else "NO DETERMINADO"
        abiertos = sum(1 for h in registro["hallazgos"].values()
                       if h["repo"] == r["repo"] and h["rama"] == r["rama"] and h["estado"] == "abierto")
        lineas.append(f"| {r['repo']} | `{r['commit'][:12]}` | {estado_sonar} | {len(resumen['nuevos'])} "
                      f"| {len(resumen['corregidos'])} | {len(resumen['reaparecidos'])} | {abiertos} "
                      f"| {veredicto(registro, r['repo'], r['rama'])} |")
    lineas += ["", "Hallazgos en modo `propuesta` (decisiones del equipo aún no aprobadas) no afectan el veredicto.",
               "Fichas por repositorio: `as-is/<repo>.md`."]
    (carpeta / "resumen.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parte automática de /revisar (línea base).")
    parser.add_argument("producto")
    parser.add_argument("--repo", help="revisar solo este repositorio")
    parser.add_argument("--sin-sonar", action="store_true", help="no consultar Sonar")
    parser.add_argument("--completa", action="store_true", help="con --repo: paquete de revisión completa aunque haya una anterior")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    opciones = parser.parse_args(argumentos)
    try:
        resultado = revisar(opciones.raiz.resolve(), opciones.producto, opciones.repo, not opciones.sin_sonar)
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    print(f"Revisión {resultado['id_revision']} (parte automática)\n")
    for r in resultado["resultados"]:
        if r["estado"] != "ok":
            print(f"  {r['repo']}: NO DETERMINADO - {r['motivo']}")
            continue
        s = r["resumen"]
        sonar_txt = r["sonar"]["datos"]["quality_gate"]["estado"] if r["sonar"]["estado"] == "ok" else f"NO DETERMINADO ({r['sonar']['motivo']})"
        print(f"  {r['repo']} @ {r['commit'][:12]}: nuevos {len(s['nuevos'])}, abiertos {len(s['abiertos'])}, "
              f"corregidos {len(s['corregidos'])}, reaparecidos {len(s['reaparecidos'])}. Sonar: {sonar_txt}")
        if r["sonar"].get("desfase"):
            print(f"    Aviso Sonar: {r['sonar']['desfase']}")
    print(f"\n  Reporte: {resultado['carpeta'].relative_to(opciones.raiz.resolve())}/resumen.md")
    if opciones.repo and resultado["resultados"][0]["estado"] == "ok":
        import revision
        paquete = revision.generar_paquete(opciones.raiz.resolve(), opciones.producto, opciones.repo, opciones.completa)
        print(f"  Paquete de revisión: {paquete.relative_to(opciones.raiz.resolve())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
