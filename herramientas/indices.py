"""Índices generados: equipo/INDICE.md y productos/<producto>/INDICE.md.

Uso: python herramientas/indices.py [--producto P] [--raiz RUTA]

Sin --producto, regenera el índice del equipo y el de todos los productos. Los comandos los
regeneran solos después de cada acción que los afecta. `arquitectura/INDICE.md` lo escribe
sync_arquitectura.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from comun import RAIZ, ErrorRadiografia

AVISO_GENERADO = "> Archivo generado por radiografia. No se edita a mano."


def _coherencia(archivo: Path, id_decision: str) -> str:
    if not archivo.exists():
        return "sin evaluar"
    estado = json.loads(archivo.read_text(encoding="utf-8"))
    propias = [e for e in estado.get("evaluaciones", {}).values() if e.get("decision") == id_decision]
    choques = sum(1 for e in propias if e["relacion"] == "choca")
    return f"❌ {choques} choque(s)" if choques else ("✅ evaluada" if propias else "sin evaluar")


def indice_equipo(raiz: Path) -> Path:
    from coherencia import leer_decisiones_equipo
    lineas = ["# Decisiones del equipo", "", AVISO_GENERADO, "",
              "| ADR | Título | Estado | Criterios | Coherencia |", "|---|---|---|---|---|"]
    estado = raiz / "equipo" / "estado" / "coherencia.json"
    for id_eq, d in leer_decisiones_equipo(raiz).items():
        lineas.append(f"| [{id_eq}](decisiones/{Path(d['archivo']).name}) | {d['titulo']} | {d['estado']} "
                      f"| {len(d['criterios'])} | {_coherencia(estado, id_eq)} |")
    lineas += ["", "Detalle de la coherencia con arquitectura: [COHERENCIA.md](COHERENCIA.md). "
               "Cómo se crean y aprueban: [README.md](README.md)."]
    archivo = raiz / "equipo" / "INDICE.md"
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return archivo


def indice_producto(raiz: Path, producto: str) -> Path:
    import adr
    import hallazgos
    import productos
    import revisar
    import triaje
    datos = productos.leer_productos(raiz).get(producto)
    if datos is None:
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    carpeta = raiz / "productos" / producto
    registro = hallazgos.cargar(raiz, producto)
    lineas = [f"# {producto}", "", AVISO_GENERADO, "",
              f"- **Descripción:** {datos.get('descripcion') or 'sin descripción'}",
              f"- **Sigla de sus ADR:** {datos.get('sigla') or 'sin asignar'}", ""]

    lineas += ["## Repositorios", "",
               "| Repositorio | Tipo | Estado | Parte automática | Revisión de código | Abiertos | Veredicto |",
               "|---|---|---|---|---|---|---|"]
    for repo in productos.repos_de(datos):
        id_repo = str(repo["id"])
        estado = registro.get("repos", {}).get(id_repo, {})
        automatica, codigo = estado.get("automatica"), estado.get("codigo")
        abiertos = sum(1 for h in registro["hallazgos"].values()
                       if h.get("repo") == id_repo and h.get("estado") == "abierto" and not h.get("absorbido_por")
                       and not revisar.descontado_por_triaje(h))
        ficha = f"[{id_repo}](as-is/{id_repo}.md)" if (carpeta / "as-is" / f"{id_repo}.md").exists() else id_repo
        al_dia = codigo and automatica and codigo["commit"] == automatica["commit"]
        lineas.append(f"| {ficha} | {repo.get('tipo')} | {repo.get('estado')} "
                      f"| {automatica['fecha'] if automatica else '—'} "
                      f"| {(codigo['fecha'] + ('' if al_dia else ' (desactualizada)')) if codigo else 'pendiente'} "
                      f"| {abiertos} | {revisar.veredicto(registro, id_repo, str(repo.get('rama'))) if automatica else '—'} |")

    lineas += ["", "## Decisiones del producto", ""]
    filas = adr.listar(raiz, producto) if (carpeta / "decisiones").exists() else []
    if filas:
        lineas += ["| ADR | Tipo | Estado | Efecto |", "|---|---|---|---|"]
        lineas += [f"| [{f['id']}](decisiones/{f['archivo']}) | {f['tipo']} | {f['estado']} | {f['efecto']} |" for f in filas]
        lineas += ["", "Índice completo: [decisiones/INDICE.md](decisiones/INDICE.md) · "
                   "Coherencia: [decisiones/COHERENCIA.md](decisiones/COHERENCIA.md)"]
    else:
        lineas.append("Sin ADR. Se crean con `/adr`.")

    if (carpeta / "proveedor" / "INDICE.md").exists():
        import proveedor
        docs = proveedor.documentos_indexados(raiz, producto).values()
        lineas_proveedor = (f"- Documentación del proveedor: [proveedor/INDICE.md](proveedor/INDICE.md) "
                            f"({sum(1 for d in docs if d['contrato'])} contrato(s), "
                            f"{sum(1 for d in docs if d['estado'] != 'indexado')} sin indexar)")
    else:
        lineas_proveedor = None
    revisiones = sorted(p.name for p in (carpeta / "revisiones").iterdir() if p.is_dir()) if (carpeta / "revisiones").exists() else []
    agendas = sorted(p.name for p in (carpeta / "agendas").glob("*.md")) if (carpeta / "agendas").exists() else []
    pendientes_triaje = len(triaje.pendientes(registro))
    lineas += ["", "## Accesos", ""]
    if lineas_proveedor:
        lineas.append(lineas_proveedor)
    if (carpeta / "integraciones").exists():
        import integraciones
        fichas = integraciones.listar(raiz, producto)
        if fichas:
            incompletas = sum(1 for f in fichas if f["errores"] or f["pendientes"])
            lineas.append(f"- Integraciones con terceros: [integraciones/INDICE.md](integraciones/INDICE.md) "
                          f"({len(fichas)} ficha(s), {incompletas} por completar)")
    import historia
    borradores = historia.listar(raiz, producto)
    if borradores:
        pendientes_jira = sum(1 for b in borradores if b["estado"] != "creada")
        lineas.append(f"- Tareas, Spikes y Bugs: {len(borradores)} borrador(es) en `historias/borradores/` "
                      f"({pendientes_jira} sin crear en Jira)")
    if (carpeta / "historias" / "INDICE.md").exists():
        import historias
        lineas.append(f"- Historias de usuario: [historias/INDICE.md](historias/INDICE.md) "
                      f"({len(historias.candidatas(raiz, producto))} candidata(s) por analizar)")
    if (carpeta / "as-is" / "PRODUCTO.md").exists():
        lineas.append("- AS IS del producto: [as-is/PRODUCTO.md](as-is/PRODUCTO.md)")
    if revisiones:
        lineas.append(f"- Última revisión: [revisiones/{revisiones[-1]}/resumen.md](revisiones/{revisiones[-1]}/resumen.md)")
    lineas.append(f"- Hallazgos pendientes de triaje: {pendientes_triaje}" + (" (ejecutar `/triar`)" if pendientes_triaje else ""))
    if agendas:
        lineas.append(f"- Última agenda: [agendas/{agendas[-1]}](agendas/{agendas[-1]})")

    archivo = carpeta / "INDICE.md"
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return archivo


def regenerar(raiz: Path, producto: str | None = None) -> list[Path]:
    """Regenera el índice de un producto, o el del equipo y los de todos los productos."""
    if producto:
        return [indice_producto(raiz, producto)]
    generados = [indice_equipo(raiz)]
    for archivo in sorted((raiz / "productos").glob("*/producto.yaml")):
        generados.append(indice_producto(raiz, archivo.parent.name))
    return generados


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenera los índices del equipo y de los productos.")
    parser.add_argument("--producto")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    try:
        for archivo in regenerar(raiz, o.producto):
            print(f"Generado: {archivo.relative_to(raiz)}")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
