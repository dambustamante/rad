"""Estado general de radiografia y qué hacer a continuación.

Uso:
  python herramientas/estado.py [--raiz RUTA]
  python herramientas/estado.py semanal [--raiz RUTA]

Sin argumentos solo lee archivos locales: no descarga nada ni usa la red. Termina con una lista "Qué
sigue", ordenada por prioridad, con el comando de Cursor que corresponde a cada paso.

`semanal` escribe productos/<producto>/semanal/<AAAA-Wnn>.md con lo que cambió desde la ejecución anterior
(o desde hace 7 días la primera vez): commits y ramas activas con su revisión y su MR, hallazgos nuevos,
corregidos y reaparecidos, y deuda vencida. Mide repositorios y ramas, no personas. Usa solo las copias
locales y el registro (sin API): `make semanal` actualiza antes las copias.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from datetime import timedelta

from comun import RAIZ, ErrorRadiografia, cargar_config, cargar_env, carpeta_decisiones_producto, escribir_json, git, leer_json

DIAS_ARQUITECTURA = 7
DIAS_SEMANAL = 7


def dias_desde(fecha_iso: str | None) -> int | None:
    if not fecha_iso:
        return None
    return (date.today() - datetime.fromisoformat(fecha_iso).date()).days


def revisar_estado(raiz: Path) -> dict:
    import adr
    import coherencia
    import jira
    import hallazgos
    import productos
    import terceros
    import revision
    import triaje
    import sonar
    import harness

    config = cargar_config(raiz)
    fuentes = (config.get("arquitectura") or {}).get("fuentes") or []
    lock_archivo = raiz / "arquitectura" / "estado" / "fuentes.lock"
    lock = json.loads(lock_archivo.read_text(encoding="utf-8")) if lock_archivo.exists() else {}
    edades = [dias_desde(d.get("sincronizado")) for d in lock.values()]
    edad_arquitectura = max((e for e in edades if e is not None), default=None)
    pares = {a.nombre: coherencia.preparar(a)["total_pares"] for a in coherencia.todos_los_ambitos(raiz)}

    estado_productos = []
    for nombre in productos.leer_productos(raiz):
        repos = revision.pendientes(raiz, nombre)
        registro = hallazgos.cargar(raiz, nombre)
        filas_adr = adr.listar(raiz, nombre) if carpeta_decisiones_producto(raiz, nombre).exists() else []
        fichas_terceros = terceros.listar(raiz, nombre)
        al_dia = [r for r in repos if r["situacion"] == "al día"]
        producto_md = raiz / "productos" / nombre / "as-is" / "PRODUCTO.md"
        ultima_revision = max((r["codigo"]["fecha"] for r in al_dia), default=None)
        consolidar = bool(repos) and len(al_dia) == len(repos) and (
            not producto_md.exists() or (ultima_revision and date.fromtimestamp(producto_md.stat().st_mtime).isoformat() < ultima_revision))
        try:
            fuente_historias = jira.leer_config(raiz, nombre)["fuente"]
        except ErrorRadiografia:
            fuente_historias = "ninguna"
        estado_productos.append({
            "borradores": [b["archivo"] for b in jira.listar(raiz, nombre) if b["estado"] != "creada"],
            "terminado": jira.terminado(raiz, nombre),
            "terceros_incompletos": [f["id"] for f in fichas_terceros if f["errores"] or f["pendientes"]],
            "historias_fuente": fuente_historias,
            "historias_pendientes": len(jira.candidatas(raiz, nombre)),
            "historias_atencion": sorted(jira.atencion(raiz, nombre)),
            "nombre": nombre,
            "repos": len(repos),
            "sin_automatica": [r["repo"] for r in repos if r["situacion"] == "falta la parte automática"],
            "sin_revision": [r["repo"] for r in repos if r["situacion"] == "falta la revisión de código"],
            "consolidar": consolidar,
            "triaje": len(triaje.pendientes(registro)),
            "excepciones": [f["id"] for f in filas_adr
                            if f["tipo"] == "excepcion" and (f["efecto"] == "vencida" or str(f["efecto"]).startswith("inactiva"))],
            "sin_indexar": sum(f["sin_indexar"] for f in fichas_terceros),
            "dias_semanal": dias_desde(leer_json(archivo_semanal(raiz, nombre)).get("ultima")),
            "harness": harness.estado(raiz, nombre) if harness.existe(raiz, nombre) else None,
            "con_revision": len(al_dia),
            "deuda_sin_tarea": sorted({d["clave"] for d in registro.get("deuda_declarada", {}).values() if not d.get("tarea")}),
        })
    env = cargar_env(raiz)
    return {"fuentes": len(fuentes), "edad_arquitectura": edad_arquitectura, "sincronizada": bool(lock),
            "pares": pares, "productos": estado_productos,
            "sonar": sonar.ConfigSonar.motivo_sin_config(env)}


def que_sigue(estado: dict) -> list[str]:
    pasos = []
    if not estado["fuentes"]:
        pasos.append("Registrar los repositorios de arquitectura: `/actualizar fuentes`.")
    elif not estado["sincronizada"]:
        pasos.append("Descargar arquitectura por primera vez: `/actualizar`.")
    elif estado["edad_arquitectura"] is not None and estado["edad_arquitectura"] > DIAS_ARQUITECTURA:
        pasos.append(f"Arquitectura sincronizada hace {estado['edad_arquitectura']} días: `/actualizar`.")
    pendientes_coherencia = {a: n for a, n in estado["pares"].items() if n}
    if pendientes_coherencia and estado["sincronizada"]:
        detalle = ", ".join(f"{a}: {n}" for a, n in pendientes_coherencia.items())
        pasos.append(f"Coherencia con pares sin evaluar ({detalle}): `/actualizar`.")
    if estado["sonar"]:
        pasos.append(f"Configurar Sonar en .env ({estado['sonar']}); sin eso el nivel 5 (Sonar) queda NO DETERMINADO.")
    if not estado["productos"]:
        pasos.append("Crear el primer producto: `/producto <nombre>`.")
    for p in estado["productos"]:
        if not p["repos"]:
            pasos.append(f"{p['nombre']}: agregar repositorios con `/producto {p['nombre']}`.")
            continue
        pendientes = p["sin_automatica"] + p["sin_revision"]
        if pendientes:
            pasos.append(f"{p['nombre']}: {len(pendientes)} repositorio(s) por revisar ({', '.join(pendientes[:5])}"
                         f"{'…' if len(pendientes) > 5 else ''}): `/revisar {p['nombre']}`, un chat por repositorio.")
        elif p["consolidar"]:
            pasos.append(f"{p['nombre']}: todos los repositorios revisados; consolidar el producto: `/revisar {p['nombre']}`.")
        if p["triaje"]:
            pasos.append(f"{p['nombre']}: {p['triaje']} hallazgo(s) esperando decisión: `/triar {p['nombre']}`.")
        if p["excepciones"]:
            pasos.append(f"{p['nombre']}: excepciones vencidas o inactivas ({', '.join(p['excepciones'])}): `/crear {p['nombre']} adr`.")
        if p["borradores"]:
            pasos.append(f"{p['nombre']}: {len(p['borradores'])} borrador(es) de Tarea, Spike, Error o Hotfix sin crear en Jira: "
                         f"`/crear {p['nombre']}`.")
        for t in p["terminado"]:
            if t["criterio"] == "EQ-008.5" and t["cumple"]:
                pasos.append(f"{p['nombre']}: {t['clave']} tiene todos sus hallazgos de origen corregidos (EQ-008.5): "
                             "se puede cerrar en Jira.")
            elif t["criterio"] == "EQ-008.9" and not t["cumple"]:
                pasos.append(f"{p['nombre']}: el Hotfix {t['clave']} no tiene su Error de seguimiento (EQ-008.9): "
                             f"`/crear {p['nombre']} error --hotfix {t['clave']}`.")
            elif t["criterio"] == "EQ-008.8" and not t["cumple"] and t["vencido"]:
                pasos.append(f"{p['nombre']}: el Spike {t['clave']} superó su duración y no tiene un ADR de producto propuesto "
                             f"(EQ-008.8): `/crear {p['nombre']} adr` con {t['clave']} en Historias de origen.")
        for clave in p["deuda_sin_tarea"]:
            pasos.append(f"{p['nombre']}: {clave} declaró deuda en /listo y no tiene Tarea: `/crear {p['nombre']} tarea --deuda {clave}`.")
        if p["harness"] is None and p["con_revision"]:
            pasos.append(f"{p['nombre']}: sin harness para el equipo: `/producto {p['nombre']} harness`.")
        elif p["harness"] and p["harness"]["sin_subir"]:
            pasos.append(f"{p['nombre']}: el harness tiene {p['harness']['sin_subir']} commit(s) sin subir: "
                         f"`git -C productos/{p['nombre']}/harness push`" + ("" if p["harness"]["remoto"] else " (falta configurar el remoto)") + ".")
        if p["terceros_incompletos"]:
            pasos.append(f"{p['nombre']}: fichas de terceros por completar ({', '.join(p['terceros_incompletos'])}): "
                         f"`/producto {p['nombre']}` → terceros.")
        if p["historias_atencion"]:
            pasos.append(f"{p['nombre']}: ADR con historias de origen modificadas o retiradas ({', '.join(p['historias_atencion'])}): "
                         f"`/crear {p['nombre']} adr`.")
        if p["historias_pendientes"]:
            pasos.append(f"{p['nombre']}: {p['historias_pendientes']} historia(s) candidata(s) a ADR por analizar: "
                         f"`/crear {p['nombre']} adr --desde-historias`.")
        if p["repos"] and (p["dias_semanal"] is None or p["dias_semanal"] > DIAS_SEMANAL):
            cuando = "sin reporte semanal" if p["dias_semanal"] is None else f"último reporte semanal hace {p['dias_semanal']} días"
            pasos.append(f"{p['nombre']}: {cuando}: `/estado semanal`.")
        if p["sin_indexar"]:
            pasos.append(f"{p['nombre']}: {p['sin_indexar']} documento(s) de terceros sin indexar: ver "
                         f"`productos/{p['nombre']}/terceros/INDICE.md`.")
    return pasos or ["Todo al día."]


# --- Reporte semanal ---------------------------------------------------------------------------

def archivo_semanal(raiz: Path, producto: str) -> Path:
    return raiz / "productos" / producto / "estado" / "semanal.json"


def actividad_git(clon: Path, rama: str, desde: str) -> dict:
    """Commits en la rama principal y ramas con commits desde `desde`, según la copia local."""
    principal = f"origin/{rama}"
    commits = int(git("rev-list", "--count", f"--since={desde}T00:00:00", principal, cwd=clon) or 0)
    ramas = []
    for linea in git("for-each-ref", "--format=%(refname:short)|%(committerdate:short)", "refs/remotes/origin", cwd=clon).splitlines():
        nombre, fecha = linea.rsplit("|", 1)
        if nombre in (principal, "origin/HEAD", "origin") or fecha < desde:
            continue
        adelante = int(git("rev-list", "--count", f"{principal}..{nombre}", cwd=clon) or 0)
        ramas.append({"rama": nombre.removeprefix("origin/"), "fecha": fecha, "commits": adelante})
    return {"commits": commits, "ramas": sorted(ramas, key=lambda r: r["fecha"], reverse=True)}


def semanal(raiz: Path, producto: str, hoy: date | None = None) -> Path:
    import hallazgos
    import productos
    from revisar import veredicto
    from triaje import deuda_vencida

    hoy = hoy or date.today()
    datos = productos.leer_productos(raiz).get(producto)
    if datos is None:
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    desde = leer_json(archivo_semanal(raiz, producto)).get("ultima") or (hoy - timedelta(days=DIAS_SEMANAL)).isoformat()
    registro = hallazgos.cargar(raiz, producto)
    anio, semana, _ = hoy.isocalendar()
    lineas = [f"# Reporte semanal de {producto}: {anio}-W{semana:02d}", "",
              f"Cambios desde el {desde} hasta el {hoy.isoformat()}. Se miden repositorios y ramas, no personas.", "",
              "## Repositorios", "", "| Repositorio | Commits en la rama principal | Ramas activas | Ramas revisadas |", "|---|---|---|---|"]
    detalle = []
    for repo in productos.repos_de(datos):
        if repo.get("estado") != "activo":
            continue
        id_repo = str(repo["id"])
        clon = raiz / "productos" / producto / "repos" / id_repo
        if not (clon / ".git").exists():
            lineas.append(f"| {id_repo} | NO DETERMINADO - sin copia local | — | — |")
            continue
        try:
            actividad = actividad_git(clon, str(repo["rama"]), desde)
        except ErrorRadiografia as error:
            lineas.append(f"| {id_repo} | NO DETERMINADO - {error} | — | — |")
            continue
        revisadas = {e["rama"]: e for e in registro.get("ramas", {}).values() if e["repo"] == id_repo and e.get("revisada")}
        activas_revisadas = sum(1 for r in actividad["ramas"] if r["rama"] in revisadas)
        lineas.append(f"| {id_repo} | {actividad['commits']} | {len(actividad['ramas'])} | {activas_revisadas} |")
        if actividad["ramas"]:
            detalle += [f"### {id_repo}", "", "| Rama | Último commit | Commits adelante | MR | Revisión de la rama |", "|---|---|---|---|---|"]
            for r in actividad["ramas"]:
                revisada = revisadas.get(r["rama"])
                mr = (revisada or {}).get("mr")
                enlace_mr = f"[{mr['titulo']}]({mr['url']})" if mr else "—"
                texto_revision = f"{revisada['revisada']['fecha']}: {veredicto(registro, id_repo, r['rama'])}" if revisada else "sin revisar"
                if revisada and revisada["revisada"]["commit"] != git("rev-parse", f"origin/{r['rama']}", cwd=clon):
                    texto_revision += " (hay commits nuevos)"
                detalle.append(f"| `{r['rama']}` | {r['fecha']} | {r['commits']} | {enlace_mr} | {texto_revision} |")
            detalle.append("")

    del_periodo = lambda campo: [h for h in registro["hallazgos"].values() if (h.get(campo) or "") >= desde]  # noqa: E731
    nuevos = del_periodo("primera_vez")
    corregidos = [h for h in del_periodo("corregido") if h["estado"] == "corregido"]
    reaparecidos = [h for h in del_periodo("ultima_vez") if h.get("reaparecido") and h["estado"] == "abierto"]
    vencidas = [h for h in registro["hallazgos"].values() if h["estado"] == "abierto" and deuda_vencida(h)]
    lineas += ["", "## Ramas activas", ""] + (detalle or ["Ninguna rama con commits en el período.", ""])
    lineas += ["## Hallazgos", "", "| | Cantidad | Bloqueantes o altos |", "|---|---|---|"]
    for nombre, lista in (("Nuevos", nuevos), ("Corregidos", corregidos), ("Reaparecidos", reaparecidos), ("Deuda vencida", vencidas)):
        lineas.append(f"| {nombre} | {len(lista)} | {sum(1 for h in lista if h['severidad'] in ('bloqueante', 'alta'))} |")
    importantes = sorted((h for h in reaparecidos + vencidas + [h for h in nuevos if h["estado"] == "abierto"]
                          if h["severidad"] in ("bloqueante", "alta")), key=lambda h: h["id"])
    if importantes:
        lineas += ["", "Bloqueantes o altos que requieren atención:", ""]
        for h in {h["id"]: h for h in importantes}.values():
            principal = registro.get("repos", {}).get(h["repo"], {}).get("rama", h["rama"])
            donde = h["repo"] if h["rama"] == principal else f"{h['repo']} @{h['rama']}"
            lineas.append(f"- {h['id']} · {donde} · {h['criterio'] or h['fuente']} · {h['titulo']}")
    lineas += ["", "Qué hacer con esto: `/triar` para lo nuevo y lo reaparecido, `/revisar mr` para los MR abiertos "
               "y `/crear tarea --desde` para la deuda que se lleva a Jira."]

    archivo = raiz / "productos" / producto / "semanal" / f"{anio}-W{semana:02d}.md"
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    escribir_json(archivo_semanal(raiz, producto), {"ultima": hoy.isoformat(), "reporte": archivo.relative_to(raiz).as_posix()})
    return archivo


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Estado general y qué sigue.")
    parser.add_argument("accion", nargs="?", choices=["semanal"])
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    o = parser.parse_args(argumentos)
    if o.accion == "semanal":
        import productos
        try:
            for nombre in productos.leer_productos(o.raiz.resolve()):
                print(f"Reporte semanal: {semanal(o.raiz.resolve(), nombre).relative_to(o.raiz.resolve())}")
        except ErrorRadiografia as error:
            print(f"ERROR: {error}")
            return 1
        return 0
    try:
        estado = revisar_estado(o.raiz.resolve())
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    edad = estado["edad_arquitectura"]
    print("Estado de radiografia\n")
    print(f"  Arquitectura: {estado['fuentes']} fuente(s)"
          + (f", sincronizada hace {edad} día(s)" if edad is not None else ", sin sincronizar"))
    for ambito, pares in estado["pares"].items():
        print(f"  Coherencia [{ambito}]: {'al día' if not pares else f'{pares} par(es) por evaluar'}")
    for p in estado["productos"]:
        revisados = p["repos"] - len(p["sin_automatica"]) - len(p["sin_revision"])
        print(f"  {p['nombre']}: {revisados}/{p['repos']} repositorio(s) revisado(s) · {p['triaje']} hallazgo(s) por triar")
    print("\nQué sigue:")
    for numero, paso in enumerate(que_sigue(estado), start=1):
        print(f"  {numero}. {paso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
