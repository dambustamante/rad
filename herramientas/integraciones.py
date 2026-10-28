"""Integraciones de un producto con terceros: productos/<producto>/integraciones/<id>/.

Uso:
  python herramientas/integraciones.py nueva <producto> --id ID --nombre TEXTO
  python herramientas/integraciones.py listar <producto>
  python herramientas/integraciones.py validar <producto> [--id ID]

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

Cada integración tiene una ficha (`integracion.yaml`) que se completa con el usuario y una carpeta
`docs/` donde se copia, tal cual, la documentación del tercero (contratos, manuales, SLA). Los
documentos se indexan con `proveedor.py indexar`, igual que los del proveedor, y se buscan y citan
con la ruta `integraciones/<id>/docs/<archivo>`. `listar` escribe integraciones/INDICE.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

import productos
import proveedor
from comun import RAIZ, ErrorRadiografia, normalizar

DIRECCIONES = ("saliente", "entrante", "bidireccional")
POLITICAS = ("fail-open", "fail-closed", "no aplica")
NO_DETERMINADO = "NO DETERMINADO"

PLANTILLA = """\
# Ficha de la integración {nombre}. Se completa con /producto; se valida con integraciones.py validar.
# Lo que no se sepa se escribe NO DETERMINADO, nunca un valor supuesto.

id: {id}
nombre: {nombre}
proveedor: NO DETERMINADO            # empresa que provee el servicio
direccion: saliente                   # saliente (lo consumimos) | entrante (nos llama) | bidireccional
protocolo: NO DETERMINADO             # por ejemplo HTTPS/JSON, gRPC, SFTP, Kafka
autenticacion: NO DETERMINADO         # por ejemplo mTLS, OAuth2 client credentials, API key

# Acuerdos de servicio del tercero (null si no hay).
sla:
  disponibilidad: null                # por ejemplo 99.9
  p95_ms: null                        # tiempo de respuesta esperado, percentil 95
limites:
  rps: null                           # solicitudes por segundo permitidas
  cuota_diaria: null

datos_sensibles: []                   # por ejemplo [rut, nombre, pan]

# Qué pasa con la operación si el tercero no responde (ADR-EQ-003).
politica_ante_falla: NO DETERMINADO   # fail-open | fail-closed | no aplica
justificacion: NO DETERMINADO         # motivo de negocio de la política

repos: []                             # repositorios del producto que la usan; vacío = no determinado
contrato: null                        # ruta dentro de docs/ del contrato OpenAPI/AsyncAPI del tercero
"""


def carpeta(raiz: Path, producto: str) -> Path:
    return proveedor.base_producto(raiz, producto) / "integraciones"


def leer_fichas(raiz: Path, producto: str) -> dict[str, dict]:
    fichas = {}
    base = carpeta(raiz, producto)
    if not base.exists():
        return fichas
    for archivo in sorted(base.glob("*/integracion.yaml")):
        try:
            datos = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as error:
            datos = {"_error": f"el YAML no es válido: {error}"}
        fichas[archivo.parent.name] = datos
    return fichas


def nueva(raiz: Path, producto: str, id_integracion: str, nombre: str) -> Path:
    productos.validar_nombre(id_integracion, "id de integración")
    destino = carpeta(raiz, producto) / id_integracion
    if destino.exists():
        raise ErrorRadiografia(f"Ya existe la integración '{id_integracion}' en el producto '{producto}'.")
    (destino / "docs").mkdir(parents=True)
    (destino / "docs" / ".gitkeep").write_text("", encoding="utf-8")
    (destino / "integracion.yaml").write_text(PLANTILLA.format(id=id_integracion, nombre=nombre), encoding="utf-8")
    return destino / "integracion.yaml"


def es_indeterminado(valor) -> bool:
    return valor is None or (isinstance(valor, str) and normalizar(valor) in (normalizar(NO_DETERMINADO), ""))


def validar(raiz: Path, producto: str, id_integracion: str, ficha: dict) -> tuple[list[str], list[str]]:
    """(errores, pendientes). Los pendientes son campos NO DETERMINADO: se informan, no son errores."""
    if "_error" in ficha:
        return [ficha["_error"]], []
    errores, pendientes = [], []
    if ficha.get("id") != id_integracion:
        errores.append(f"el id de la ficha ('{ficha.get('id')}') no coincide con la carpeta ('{id_integracion}')")
    for campo in ("nombre", "proveedor", "protocolo", "autenticacion"):
        if es_indeterminado(ficha.get(campo)):
            pendientes.append(campo)
    if ficha.get("direccion") not in DIRECCIONES:
        errores.append(f"direccion '{ficha.get('direccion')}' inválida; valores válidos: {', '.join(DIRECCIONES)}")
    politica = ficha.get("politica_ante_falla")
    if es_indeterminado(politica):
        pendientes.append("politica_ante_falla")
    elif politica not in POLITICAS:
        errores.append(f"politica_ante_falla '{politica}' inválida; valores válidos: {', '.join(POLITICAS)}")
    elif politica != "no aplica" and es_indeterminado(ficha.get("justificacion")):
        errores.append("una política fail-open o fail-closed necesita su justificación de negocio")
    for grupo, campos in (("sla", ("disponibilidad", "p95_ms")), ("limites", ("rps", "cuota_diaria"))):
        valores = ficha.get(grupo) or {}
        for campo in campos:
            valor = valores.get(campo)
            if valor is not None and not isinstance(valor, (int, float)):
                errores.append(f"{grupo}.{campo} debe ser un número o null")
    if not isinstance(ficha.get("datos_sensibles", []), list):
        errores.append("datos_sensibles debe ser una lista")
    repos_producto = {str(r["id"]) for r in productos.repos_de(productos.leer_productos(raiz)[producto])}
    repos = ficha.get("repos") or []
    desconocidos = [r for r in repos if r not in repos_producto]
    if desconocidos:
        errores.append(f"repositorios que no existen en el producto: {', '.join(desconocidos)}")
    if not repos:
        pendientes.append("repos")
    contrato = ficha.get("contrato")
    if contrato and not (carpeta(raiz, producto) / id_integracion / "docs" / contrato).is_file():
        errores.append(f"el contrato '{contrato}' no existe en docs/")
    return errores, pendientes


def para_repo(raiz: Path, producto: str, repo: str) -> list[dict]:
    """Fichas de las integraciones que declara usar un repositorio (o que no declaran repositorios)."""
    resultado = []
    for id_integracion, ficha in leer_fichas(raiz, producto).items():
        repos = ficha.get("repos") or []
        if not repos or repo in repos:
            resultado.append({**ficha, "id": id_integracion})
    return resultado


def listar(raiz: Path, producto: str) -> list[dict]:
    if producto not in productos.leer_productos(raiz):
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    filas = []
    for id_integracion, ficha in leer_fichas(raiz, producto).items():
        errores, pendientes = validar(raiz, producto, id_integracion, ficha)
        documentos = proveedor.documentos_indexados(raiz, producto, f"integraciones/{id_integracion}/docs")
        sla = ficha.get("sla") or {}
        filas.append({
            "id": id_integracion, "nombre": ficha.get("nombre"), "direccion": ficha.get("direccion"),
            "protocolo": ficha.get("protocolo"), "p95_ms": sla.get("p95_ms"),
            "politica": ficha.get("politica_ante_falla"), "repos": ficha.get("repos") or [],
            "documentos": len(documentos), "errores": errores, "pendientes": pendientes,
        })
    base = carpeta(raiz, producto)
    if filas:
        lineas = [f"# Integraciones de {producto}", "", "> Archivo generado por `herramientas/integraciones.py listar`. No se "
                  "edita a mano; las fichas (`<id>/integracion.yaml`) sí.", "",
                  "| Integración | Dirección | Protocolo | p95 (ms) | Política ante falla | Repositorios | Documentos | Estado de la ficha |",
                  "|---|---|---|---|---|---|---|---|"]
        for f in filas:
            estado = ("❌ " + "; ".join(f["errores"])) if f["errores"] else (
                f"⏳ por completar: {', '.join(f['pendientes'])}" if f["pendientes"] else "✅ completa")
            lineas.append(f"| [{f['nombre'] or f['id']}]({f['id']}/integracion.yaml) | {f['direccion']} | {f['protocolo']} "
                          f"| {f['p95_ms'] if f['p95_ms'] is not None else '—'} | {f['politica']} | {', '.join(f['repos']) or '—'} "
                          f"| [{f['documentos']}]({f['id']}/docs/INDICE.md) | {estado} |")
        (base / "INDICE.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return filas


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Integraciones con terceros.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("nueva")
    p.add_argument("producto")
    p.add_argument("--id", required=True)
    p.add_argument("--nombre", required=True)
    p = sub.add_parser("listar")
    p.add_argument("producto")
    p = sub.add_parser("validar")
    p.add_argument("producto")
    p.add_argument("--id")
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    try:
        if o.accion == "nueva":
            archivo = nueva(raiz, o.producto, o.id, o.nombre)
            print(f"Creada: {archivo.relative_to(raiz)}. Copiar la documentación del tercero en {archivo.parent.relative_to(raiz)}/docs/.")
        elif o.accion in ("listar", "validar"):
            filas = [f for f in listar(raiz, o.producto) if not getattr(o, "id", None) or f["id"] == o.id]
            if not filas:
                print(f"El producto '{o.producto}' no tiene integraciones registradas.")
            for f in filas:
                print(f"  {f['id']}: {'con errores' if f['errores'] else 'válida'}"
                      + (f" · por completar: {', '.join(f['pendientes'])}" if f["pendientes"] else ""))
                for error in f["errores"]:
                    print(f"    ERROR: {error}")
            if o.accion == "validar" and any(f["errores"] for f in filas):
                return 1
        if o.accion in ("nueva", "listar", "validar"):
            import indices
            indices.indice_producto(raiz, o.producto)
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
