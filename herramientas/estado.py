"""Estado general de radiografia y qué hacer a continuación.

Uso: python herramientas/estado.py [--raiz RUTA]

Solo lee archivos locales: no descarga nada ni usa la red. Termina con una lista "Qué sigue",
ordenada por prioridad, con el comando de Cursor que corresponde a cada paso.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from comun import RAIZ, ErrorRadiografia, cargar_config, cargar_env

DIAS_ARQUITECTURA = 7


def dias_desde(fecha_iso: str | None) -> int | None:
    if not fecha_iso:
        return None
    return (date.today() - datetime.fromisoformat(fecha_iso).date()).days


def revisar_estado(raiz: Path) -> dict:
    import adr
    import coherencia
    import hallazgos
    import productos
    import proveedor
    import revision
    import triaje
    import sonar

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
        filas_adr = adr.listar(raiz, nombre) if (raiz / "productos" / nombre / "decisiones").exists() else []
        docs = proveedor.documentos_indexados(raiz, nombre).values()
        al_dia = [r for r in repos if r["situacion"] == "al día"]
        producto_md = raiz / "productos" / nombre / "as-is" / "PRODUCTO.md"
        ultima_revision = max((r["codigo"]["fecha"] for r in al_dia), default=None)
        consolidar = bool(repos) and len(al_dia) == len(repos) and (
            not producto_md.exists() or (ultima_revision and date.fromtimestamp(producto_md.stat().st_mtime).isoformat() < ultima_revision))
        estado_productos.append({
            "nombre": nombre,
            "repos": len(repos),
            "sin_automatica": [r["repo"] for r in repos if r["situacion"] == "falta la parte automática"],
            "sin_revision": [r["repo"] for r in repos if r["situacion"] == "falta la revisión de código"],
            "consolidar": consolidar,
            "triaje": len(triaje.pendientes(registro)),
            "excepciones": [f["id"] for f in filas_adr
                            if f["tipo"] == "excepcion" and (f["efecto"] == "vencida" or str(f["efecto"]).startswith("inactiva"))],
            "sin_indexar": sum(1 for d in docs if d["estado"] != "indexado"),
        })
    env = cargar_env(raiz)
    return {"fuentes": len(fuentes), "edad_arquitectura": edad_arquitectura, "sincronizada": bool(lock),
            "pares": pares, "productos": estado_productos,
            "sonar": sonar.ConfigSonar.motivo_sin_config(env)}


def que_sigue(estado: dict) -> list[str]:
    pasos = []
    if not estado["fuentes"]:
        pasos.append("Registrar los repositorios de arquitectura: `/arquitectura`.")
    elif not estado["sincronizada"]:
        pasos.append("Descargar arquitectura por primera vez: `/actualizar`.")
    elif estado["edad_arquitectura"] is not None and estado["edad_arquitectura"] > DIAS_ARQUITECTURA:
        pasos.append(f"Arquitectura sincronizada hace {estado['edad_arquitectura']} días: `/actualizar`.")
    pendientes_coherencia = {a: n for a, n in estado["pares"].items() if n}
    if pendientes_coherencia and estado["sincronizada"]:
        detalle = ", ".join(f"{a}: {n}" for a, n in pendientes_coherencia.items())
        pasos.append(f"Coherencia con pares sin evaluar ({detalle}): `/actualizar`.")
    if estado["sonar"]:
        pasos.append(f"Configurar Sonar en .env ({estado['sonar']}); sin eso el nivel 4 queda NO DETERMINADO.")
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
            pasos.append(f"{p['nombre']}: excepciones vencidas o inactivas ({', '.join(p['excepciones'])}): `/adr {p['nombre']}`.")
        if p["sin_indexar"]:
            pasos.append(f"{p['nombre']}: {p['sin_indexar']} documento(s) del proveedor sin indexar: ver "
                         f"`productos/{p['nombre']}/proveedor/INDICE.md`.")
    return pasos or ["Todo al día."]


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Estado general y qué sigue.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    o = parser.parse_args(argumentos)
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
