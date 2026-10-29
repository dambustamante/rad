"""ADR de producto: decisiones propias, mejoras y excepciones (productos/<producto>/decisiones/).

Uso:
  python herramientas/adr.py listar <producto>
  python herramientas/adr.py nuevo <producto> --tipo decision|mejora|excepcion --titulo TEXTO [--desde H-0001,H-0002]
                                   [--historias CLAVE-1,CLAVE-2]
  python herramientas/adr.py validar <producto> [--id ADR-XX-NNN]

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

Una excepción aprobada y vigente deja sus criterios como NO APLICA en los repositorios de su alcance.
Si exceptúa un documento de arquitectura, solo se activa con una referencia de aprobación de
arquitectura. `listar` escribe además el índice decisiones/INDICE.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import hallazgos as registro_hallazgos
import productos
from coherencia import leer_arquitectura_vigente, leer_decisiones_equipo, leer_decisiones_producto, sigla_de
from comun import RAIZ, ErrorRadiografia, normalizar, slug

TIPOS = ("decision", "mejora", "excepcion")
ESTADOS = ("propuesto", "aprobado", "reemplazado", "rechazado")
SIN_VALOR = {"", "—", "-", "ninguno", "ninguna", "n/a"}
PATRON_CLAVE_ARQUITECTURA = re.compile(r"^[a-z0-9][a-z0-9-]*:.+$")


# --- Lectura -----------------------------------------------------------------------------------

def lista(valor: str | None) -> list[str]:
    if not valor or normalizar(valor) in SIN_VALOR:
        return []
    return [v.strip().strip("`") for v in valor.split(",") if v.strip().strip("`")]


def valor(campos: dict, nombre: str) -> str | None:
    texto = campos.get(nombre)
    return None if not texto or normalizar(texto) in SIN_VALOR else texto


def alcance(adr: dict) -> list[str] | None:
    """Repositorios del alcance; None significa todos."""
    repos = lista(adr["campos"].get("repositorios"))
    return None if not repos or [normalizar(r) for r in repos] == ["todos"] else repos


def estado_excepcion(adr: dict) -> str:
    """activa, inactiva (sin aprobación de arquitectura), vencida o no aprobada."""
    if normalizar(adr["estado"]) != "aprobado":
        return "no aprobada"
    vence = valor(adr["campos"], "vence")
    if not vence or vence < date.today().isoformat():
        return "vencida"
    exceptuados = lista(adr["campos"].get("criterios exceptuados"))
    toca_arquitectura = any(PATRON_CLAVE_ARQUITECTURA.match(c) for c in exceptuados)
    if toca_arquitectura and not valor(adr["campos"], "referencia de aprobacion de arquitectura"):
        return "inactiva: falta la aprobación de arquitectura"
    return "activa"


def excepciones_activas(raiz: Path, producto: str, repo: str) -> dict[str, str]:
    """Criterio o documento exceptuado -> motivo, para un repositorio."""
    activas = {}
    for adr in leer_decisiones_producto(raiz, producto).values():
        if adr["tipo"] != "excepcion" or estado_excepcion(adr) != "activa":
            continue
        repos = alcance(adr)
        if repos is not None and repo not in repos:
            continue
        for clave in lista(adr["campos"].get("criterios exceptuados")):
            activas[clave] = f"excepción {adr['id']} vigente hasta {adr['campos']['vence']}"
    return activas


def excepciones_pendientes(raiz: Path, producto: str, repo: str) -> dict[str, str]:
    """Excepciones aprobadas que no surten efecto (inactivas o vencidas) para un repositorio."""
    pendientes = {}
    for adr in leer_decisiones_producto(raiz, producto).values():
        estado = estado_excepcion(adr) if adr["tipo"] == "excepcion" else None
        if estado in (None, "activa", "no aprobada"):
            continue
        repos = alcance(adr)
        if repos is None or repo in repos:
            for clave in lista(adr["campos"].get("criterios exceptuados")):
                pendientes[clave] = f"{adr['id']} {estado}"
    return pendientes


# --- Validación --------------------------------------------------------------------------------

def validar_adr(raiz: Path, producto: str, adr: dict) -> tuple[list[str], list[str]]:
    errores, avisos = [], []
    sigla = sigla_de(raiz, producto)
    numero = adr["id"].rsplit("-", 1)[1]
    if normalizar(adr["estado"]) not in ESTADOS:
        errores.append(f"estado '{adr['estado']}' inválido; valores válidos: Propuesto, Aprobado, Reemplazado, Rechazado")
    if adr["tipo"] not in TIPOS:
        errores.append(f"tipo '{adr['tipo']}' inválido; valores válidos: {', '.join(TIPOS)}")
    if re.search(r"<[a-záéíóúñ][^>\n]{3,}>", adr["texto"], re.IGNORECASE):
        avisos.append("la plantilla tiene textos sin completar (<…>)")
    import lenguaje
    avisos += [f"lenguaje: línea {a['linea']}: «{a['texto']}» ({a['regla']}); {a['sugerencia']}"
               for a in lenguaje.revisar(adr["texto"])]
    repos_producto = {str(r["id"]) for r in productos.repos_de(productos.leer_productos(raiz)[producto])}
    desconocidos = [r for r in (alcance(adr) or []) if r not in repos_producto]
    if desconocidos:
        errores.append(f"repositorios que no existen en el producto: {', '.join(desconocidos)}")

    if adr["tipo"] == "decision":
        if not adr["regla_rapida"] or "<" in adr["regla_rapida"]:
            errores.append("falta la regla rápida")
        if not adr["criterios"]:
            avisos.append("no tiene criterios de verificación: no se evaluará en /revisar")
        ajenos = [c for c in adr["criterios"] if not c.startswith(f"{sigla}-{numero}.")]
        if ajenos:
            errores.append(f"criterios con identificador que no corresponde a {adr['id']}: {', '.join(ajenos)}")

    if adr["tipo"] == "excepcion":
        exceptuados = lista(adr["campos"].get("criterios exceptuados"))
        if not exceptuados:
            errores.append("una excepción necesita criterios exceptuados")
        criterios_equipo = {c for d in leer_decisiones_equipo(raiz).values() for c in d["criterios"]}
        criterios_producto = {c for d in leer_decisiones_producto(raiz, producto).values() for c in d["criterios"]}
        arquitectura = leer_arquitectura_vigente(raiz)
        for clave in exceptuados:
            if PATRON_CLAVE_ARQUITECTURA.match(clave):
                if not arquitectura:
                    avisos.append(f"{clave}: arquitectura no sincronizada; no se pudo verificar")
                elif clave not in arquitectura:
                    errores.append(f"{clave} no es un documento vigente de arquitectura")
            elif clave not in criterios_equipo | criterios_producto:
                errores.append(f"el criterio {clave} no existe")
        vence = valor(adr["campos"], "vence")
        if not vence:
            errores.append("una excepción necesita fecha de vencimiento (Vence)")
        else:
            try:
                date.fromisoformat(vence)
            except ValueError:
                errores.append(f"Vence '{vence}' no tiene el formato AAAA-MM-DD")
        if any(PATRON_CLAVE_ARQUITECTURA.match(c) for c in exceptuados) and not valor(adr["campos"], "referencia de aprobacion de arquitectura"):
            avisos.append("exceptúa arquitectura sin referencia de aprobación: quedará inactiva aunque se apruebe")

    if adr["tipo"] == "mejora":
        origen = lista(adr["campos"].get("hallazgos de origen"))
        existentes = {h["id"] for h in registro_hallazgos.cargar(raiz, producto)["hallazgos"].values()}
        inexistentes = [h for h in origen if h not in existentes]
        if inexistentes:
            errores.append(f"hallazgos de origen que no existen: {', '.join(inexistentes)}")
    return errores, avisos


# --- Creación ----------------------------------------------------------------------------------



def nuevo(raiz: Path, producto: str, tipo: str, titulo: str, desde: list[str], historias: list[str] | None = None) -> Path:
    if tipo not in TIPOS:
        raise ErrorRadiografia(f"Tipo '{tipo}' inválido; valores válidos: {', '.join(TIPOS)}.")
    if producto not in productos.leer_productos(raiz):
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    sigla = sigla_de(raiz, producto)
    if not sigla:
        raise ErrorRadiografia(f"El producto '{producto}' no tiene sigla. Asignarla con: productos.py sigla {producto} --asignar XX")
    if desde and tipo != "mejora":
        raise ErrorRadiografia("--desde solo se usa con el tipo mejora.")
    carpeta = raiz / "productos" / producto / "decisiones"
    carpeta.mkdir(parents=True, exist_ok=True)
    numeros = [int(m.group(1)) for a in carpeta.glob(f"ADR-{sigla}-*.md") if (m := re.match(rf"ADR-{sigla}-(\d{{3}})", a.name))]
    numero = f"{max(numeros, default=0) + 1:03d}"
    id_adr = f"ADR-{sigla}-{numero}"

    texto = (raiz / "equipo" / "plantillas" / "adr-producto.md").read_text(encoding="utf-8")
    texto = texto.replace("ADR-<SIGLA>-NNN: <Título de la decisión>", f"{id_adr}: {titulo}")
    texto = texto.replace("<SIGLA>-NNN.1", f"{sigla}-{numero}.1")
    texto = texto.replace("Fecha de creación: `DD-MM-AAAA`", f"Fecha de creación: `{date.today().strftime('%d-%m-%Y')}`")
    texto = texto.replace("- **Tipo:** decision", f"- **Tipo:** {tipo}", 1)

    if desde:
        registro = {h["id"]: h for h in registro_hallazgos.cargar(raiz, producto)["hallazgos"].values()}
        inexistentes = [h for h in desde if h not in registro]
        if inexistentes:
            raise ErrorRadiografia(f"Hallazgos que no existen: {', '.join(inexistentes)}.")
        filas = ["| Hallazgo | Repositorio | Fuente | Severidad | Descripción | Evidencia |", "|---|---|---|---|---|---|"]
        for id_hallazgo in desde:
            h = registro[id_hallazgo]
            evidencia = ", ".join(f"`{e['archivo']}:{e['linea']}`" if e.get("linea") else f"`{e['archivo']}`" for e in h["evidencia"][:3])
            filas.append(f"| {h['id']} | {h['repo']} | {h['criterio'] or h['fuente']} | {h['severidad']} "
                         f"| {h['titulo'].replace('|', '/')} | {evidencia or '—'} |")
        texto = texto.replace("- **Problema o necesidad:** <qué pasa hoy y por qué es un problema>",
                              "- **Problema o necesidad:** <qué pasa hoy y por qué es un problema>\n- **Hallazgos que la originan:**\n\n"
                              + "\n".join(filas) + "\n", 1)
        texto = texto.replace("- **Hallazgos de origen:** —", f"- **Hallazgos de origen:** {', '.join(desde)}", 1)

    if historias:
        import jira as modulo_historias
        guardadas, analisis = modulo_historias.historias_de(raiz, producto), modulo_historias.analisis_de(raiz, producto)
        inexistentes = [c for c in historias if c not in guardadas]
        if inexistentes:
            raise ErrorRadiografia(f"Historias que no existen (ejecutar jira.py sincronizar): {', '.join(inexistentes)}.")
        filas = ["| Historia | Tipo | Título | Requisito citado |", "|---|---|---|---|"]
        for clave in historias:
            h = guardadas[clave]
            enlace = f"[{clave}]({h['url']})" if h.get("url") else clave
            cita = (analisis.get(clave) or {}).get("cita") or (h.get("criterios") or "NO DETERMINADO").split("\n")[0]
            filas.append(f"| {enlace} | {h.get('tipo') or '—'} | {h['titulo'].replace('|', '/')} | {str(cita).replace('|', '/')} |")
        texto = texto.replace("- **Restricciones:** <técnicas, regulatorias u operativas>",
                              "- **Restricciones:** <técnicas, regulatorias u operativas>\n- **Historias que la originan:**\n\n"
                              + "\n".join(filas) + "\n", 1)
        texto = texto.replace("- **Historias de origen:** —", f"- **Historias de origen:** {', '.join(historias)}", 1)

    archivo = carpeta / f"{id_adr}-{slug(titulo)}.md"
    archivo.write_text(texto, encoding="utf-8")
    if historias:
        modulo_historias.vincular(raiz, producto, id_adr, historias)
    return archivo


# --- Listado e índice --------------------------------------------------------------------------

def listar(raiz: Path, producto: str) -> list[dict]:
    if producto not in productos.leer_productos(raiz):
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    import jira as modulo_historias
    avisos = modulo_historias.atencion(raiz, producto)
    filas = []
    for adr in leer_decisiones_producto(raiz, producto).values():
        efecto = estado_excepcion(adr) if adr["tipo"] == "excepcion" else ("se evalúa" if adr["tipo"] == "decision" and adr["evaluado"] else "—")
        if adr["id"] in avisos:
            efecto = f"{efecto} · revisar: {'; '.join(avisos[adr['id']])}"
        filas.append({"id": adr["id"], "titulo": adr["titulo"], "tipo": adr["tipo"], "estado": adr["estado"],
                      "vence": valor(adr["campos"], "vence"), "efecto": efecto, "archivo": Path(adr["archivo"]).name})
    carpeta = raiz / "productos" / producto / "decisiones"
    if filas:
        lineas = [f"# Decisiones de {producto}", "", "> Índice generado por `herramientas/adr.py listar`. No se edita a mano.", "",
                  "| ADR | Título | Tipo | Estado | Vence | Efecto |", "|---|---|---|---|---|---|"]
        lineas += [f"| [{f['id']}]({f['archivo']}) | {f['titulo']} | {f['tipo']} | {f['estado']} | {f['vence'] or '—'} | {f['efecto']} |"
                   for f in filas]
        lineas += ["", "Coherencia con arquitectura y con el equipo: [COHERENCIA.md](COHERENCIA.md)."]
        (carpeta / "INDICE.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return filas


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ADR de producto.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("listar")
    p.add_argument("producto")
    p = sub.add_parser("nuevo")
    p.add_argument("producto")
    p.add_argument("--tipo", required=True, choices=TIPOS)
    p.add_argument("--titulo", required=True)
    p.add_argument("--desde", default="")
    p.add_argument("--historias", default="")
    p = sub.add_parser("validar")
    p.add_argument("producto")
    p.add_argument("--id")
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()

    try:
        if o.accion == "listar":
            filas = listar(raiz, o.producto)
            if not filas:
                print(f"El producto '{o.producto}' no tiene ADR.")
            for f in filas:
                print(f"  {f['id']} [{f['tipo']}, {f['estado']}] {f['titulo']} · efecto: {f['efecto']}"
                      + (f" · vence {f['vence']}" if f["vence"] else ""))
        elif o.accion == "nuevo":
            ids = [i.strip() for i in o.desde.split(",") if i.strip()]
            claves = [c.strip() for c in o.historias.split(",") if c.strip()]
            print(f"Creado: {nuevo(raiz, o.producto, o.tipo, o.titulo, ids, claves).relative_to(raiz)}")
        if o.accion in ("listar", "nuevo"):
            import indices
            indices.indice_producto(raiz, o.producto)
        elif o.accion == "validar":
            adrs = leer_decisiones_producto(raiz, o.producto)
            if o.id and o.id not in adrs:
                raise ErrorRadiografia(f"No existe {o.id} en el producto '{o.producto}'.")
            con_errores = 0
            for id_adr, adr in adrs.items():
                if o.id and id_adr != o.id:
                    continue
                errores, avisos = validar_adr(raiz, o.producto, adr)
                con_errores += bool(errores)
                print(f"  {id_adr}: {'con errores' if errores else 'válido'}")
                for e in errores:
                    print(f"    ERROR: {e}")
                for a in avisos:
                    print(f"    AVISO: {a}")
            return 1 if con_errores else 0
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
