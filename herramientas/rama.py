"""Revisión de una rama (o de su MR o PR) y publicación del resultado en la plataforma git.

Uso:
  python herramientas/rama.py preparar <producto> <repo> <rama>
  python herramientas/rama.py registrar <producto> <repo> <rama> [--archivo LOTE.yaml]
  python herramientas/rama.py publicar <producto> <repo> <rama> [--incluir H-0012,H-0015] [--confirmar]
        (registra antes el lote de la rama, si existe)

Opción común: --raiz RUTA (raíz de radiografia, para pruebas).

La revisión de una rama solo mira lo que la rama cambia respecto de su rama de destino (la del MR, o la
rama principal del repositorio si no hay MR):

1. `preparar` trae la rama, la deja en una copia de solo lectura (.cache/ramas/), ejecuta las verificaciones
   automáticas y gitleaks y conserva solo los hallazgos en archivos que la rama cambia. Escribe el paquete
   de revisión con el diff.
2. `registrar` valida el lote de hallazgos de la revisión de código (evidencia en archivos cambiados) y
   lo incorpora al registro: los hallazgos de la rama se triaron y se publican como los demás.
3. `publicar` arma un único comentario con los hallazgos a resolver. Sin --confirmar solo muestra la vista
   previa. Con --confirmar lo publica en el MR o PR y en las siguientes publicaciones edita el mismo
   comentario. Solo se comentan MR o PR: sin MR abierto no se publica.

Sonar no se consulta en ramas: SonarQube Community no las analiza.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


import hallazgos as registro_hallazgos
import lenguaje
import productos
import terceros
import verificaciones
from adr import excepciones_activas
from coherencia import suspendidos as criterios_suspendidos
from comun import RAIZ, ErrorRadiografia, actualizar_clon, cargar_env, git, resolver_commit, slug
from plataforma import ClientePlataforma, ConfigPlataforma, proyecto_de
from revisar import decisiones_con_criterios, veredicto
from revision import hallazgos_del_lote, leer_lote, lista_de_control

MAXIMO_LINEAS_DIFF = 1500
ORDEN_SEVERIDAD = {"bloqueante": 0, "alta": 1, "media": 2, "baja": 3}


# --- Estado ------------------------------------------------------------------------------------

def clave_rama(repo: str, rama: str) -> str:
    return f"{repo}@{rama}"


def repo_del_producto(raiz: Path, producto: str, repo: str) -> dict:
    datos = productos.leer_productos(raiz).get(producto)
    if datos is None:
        raise ErrorRadiografia(f"No existe el producto '{producto}'.")
    for r in productos.repos_de(datos):
        if str(r["id"]) == repo and r.get("estado") == "activo":
            return dict(r)
    raise ErrorRadiografia(f"El producto '{producto}' no tiene un repositorio activo '{repo}'.")


def estado_rama(registro: dict, repo: str, rama: str) -> dict:
    estado = registro.get("ramas", {}).get(clave_rama(repo, rama))
    if not estado:
        raise ErrorRadiografia(f"La rama '{rama}' de '{repo}' no está preparada. Ejecutar: rama.py preparar <producto> {repo} {rama}")
    return estado


def cliente_desde_env(raiz: Path) -> tuple[ClientePlataforma | None, str | None]:
    env = cargar_env(raiz)
    config = ConfigPlataforma.desde_env(env)
    return (ClientePlataforma(config), None) if config else (None, ConfigPlataforma.motivo_sin_config(env))


def copia_de_rama(raiz: Path, producto: str, repo: str, rama: str, clon: Path, commit: str) -> Path:
    """Copia de solo lectura de la rama (git worktree del clon del producto), en el commit indicado."""
    destino = raiz / ".cache" / "ramas" / producto / repo / slug(rama)
    if (destino / ".git").exists():
        git("checkout", "--quiet", "--force", "--detach", commit, cwd=destino)
    else:
        git("worktree", "prune", cwd=clon)
        destino.parent.mkdir(parents=True, exist_ok=True)
        git("worktree", "add", "--quiet", "--force", "--detach", str(destino), commit, cwd=clon)
    return destino


def contexto_rama(raiz: Path, producto: str, repo: str, rama: str, registro: dict) -> dict:
    estado = estado_rama(registro, repo, rama)
    destino = raiz / estado["copia"]
    if not (destino / ".git").exists() or git("rev-parse", "HEAD", cwd=destino) != estado["commit"]:
        clon = raiz / "productos" / producto / "repos" / repo
        destino = copia_de_rama(raiz, producto, repo, rama, clon, estado["commit"])
    return {"destino": destino, "repo": repo, "rama": rama, "producto": producto, "tipo": estado["tipo"],
            "commit": estado["commit"], "estado": estado}


def control_de_rama(raiz: Path, producto: str, repo: str, tipo: str) -> dict[str, dict]:
    """Lo mismo que se evalúa en la revisión de código del repositorio, sin lo exceptuado."""
    return {e["clave"]: e for e in lista_de_control(raiz, tipo, producto, repo) if not e.get("exceptuado")}


# --- Preparar ----------------------------------------------------------------------------------

def preparar(raiz: Path, producto: str, repo: str, rama: str, cliente: ClientePlataforma | None = None) -> dict:
    datos_repo = repo_del_producto(raiz, producto, repo)
    clon = raiz / "productos" / producto / "repos" / repo
    actualizar_clon(str(datos_repo["url"]), clon, raiz)
    try:
        commit = resolver_commit(clon, rama)
    except ErrorRadiografia as error:
        raise ErrorRadiografia(f"La rama '{rama}' no existe en '{repo}'.") from error

    aviso_mr = None
    if cliente is None:
        cliente, aviso_mr = cliente_desde_env(raiz)
    mr = None
    if cliente:
        try:
            mr = cliente.mr_de_rama(proyecto_de(str(datos_repo["url"])), rama)
        except ErrorRadiografia as error:
            aviso_mr = str(error)
    if mr is None:
        raise ErrorRadiografia(f"Solo se revisan MR: la rama '{rama}' de '{repo}' no tiene un MR abierto"
                               + (f" ({aviso_mr})." if aviso_mr else "."))
    destino_rama = mr["destino"]
    base = git("merge-base", resolver_commit(clon, destino_rama), commit, cwd=clon)
    cambiados = sorted(git("diff", "--name-only", "--diff-filter=ACMR", base, commit, cwd=clon).splitlines())
    commits = git("rev-list", f"{base}..{commit}", cwd=clon).splitlines()
    copia = copia_de_rama(raiz, producto, repo, rama, clon, commit)

    gitleaks = verificaciones.ejecutar_gitleaks(copia)
    if gitleaks is not None:
        de_la_rama = {c[:12] for c in commits}
        gitleaks = [s for s in gitleaks if s["commit"] in de_la_rama]
    _, encontrados = verificaciones.verificar_repo(
        copia, repo, rama, str(datos_repo["tipo"]), decisiones_con_criterios(raiz), criterios_suspendidos(raiz, producto),
        gitleaks, excepciones_activas(raiz, producto, repo))
    en_la_rama = set(cambiados)
    encontrados = [h for h in encontrados if any(e["archivo"] in en_la_rama for e in h["evidencia"])]

    hoy = date.today().isoformat()
    id_revision = f"{hoy}-rama-{repo}-{slug(rama, 40)}"
    registro = registro_hallazgos.cargar(raiz, producto)
    origenes = {"verificacion"} | ({"gitleaks"} if gitleaks is not None else set())
    resumen = registro_hallazgos.aplicar(registro, repo, rama, origenes, encontrados, id_revision, hoy, False)
    anterior = registro.get("ramas", {}).get(clave_rama(repo, rama), {})
    estado = {
        "repo": repo, "rama": rama, "tipo": str(datos_repo["tipo"]), "commit": commit, "base": base,
        "destino": destino_rama, "cambiados": cambiados, "commits": len(commits), "mr": mr, "aviso_mr": aviso_mr,
        "id_revision": id_revision, "fecha": hoy, "copia": copia.relative_to(raiz).as_posix(),
        "secretos": None if gitleaks is None else len(gitleaks), "revisada": None,
        "publicacion": anterior.get("publicacion"),
    }
    registro.setdefault("ramas", {})[clave_rama(repo, rama)] = estado
    registro_hallazgos.guardar(raiz, producto, registro)

    carpeta = raiz / "productos" / producto / "revisiones" / id_revision
    carpeta.mkdir(parents=True, exist_ok=True)
    automaticos = [registro["hallazgos"][h["huella"]] for h in encontrados]
    paquete = escribir_paquete(raiz, producto, estado, carpeta, clon, automaticos)
    return {"estado": estado, "resumen": resumen, "paquete": paquete}


def escribir_paquete(raiz: Path, producto: str, estado: dict, carpeta: Path, clon: Path,
                     automaticos: list[dict]) -> Path:
    repo, rama, mr = estado["repo"], estado["rama"], estado["mr"]
    if mr:
        aprobado = [a for a in mr["aprobado_por"] if a != mr.get("autor")]
        linea_mr = (f"[{mr['titulo']}]({mr['url']}) hacia `{mr['destino']}`. "
                    f"Aprobado por otra persona (EQ-008.2): {'sí' if aprobado else 'todavía no'}.")
    else:
        linea_mr = (f"sin MR abierto ({estado['aviso_mr']})" if estado["aviso_mr"] else "sin MR abierto") + \
                   ": se compara con la rama principal. Para publicar el comentario hace falta un MR o PR abierto."
    lineas = [
        f"# Revisión de la rama `{rama}`: {repo} ({producto})", "",
        f"- Commit `{estado['commit'][:12]}` · base `{estado['base'][:12]}` (punto común con `{estado['destino']}`) · "
        f"{estado['commits']} commit(s) · {len(estado['cambiados'])} archivo(s) cambiado(s)",
        f"- MR: {linea_mr}",
        f"- Copia de la rama (solo lectura): `{estado['copia']}/`",
        "- Sonar: no se consulta en ramas (EQ-008.3 queda NO DETERMINADO).",
        f"- Secretos en los commits de la rama (EQ-008.4): "
        + ("NO DETERMINADO (gitleaks no está instalado)" if estado["secretos"] is None else str(estado["secretos"])), "",
        "## Qué hacer", "",
        "Revisar **solo lo que la rama cambia**: el diff y, si hace falta, el contexto en la copia de la rama. Comparar "
        "con lo decidido (ver \"Contra qué comparar\") y registrar únicamente hallazgos introducidos o empeorados por "
        "la rama, con evidencia en un archivo cambiado. No hace falta AS IS, C4 ni evaluar cada elemento.", "",
        "## Archivos cambiados", "",
    ]
    lineas += [f"- `{a}`" for a in estado["cambiados"]] or ["Ninguno."]
    diff = git("diff", "--unified=3", estado["base"], estado["commit"], cwd=clon).splitlines()
    lineas += ["", "## Cambios", "", "```diff", *diff[:MAXIMO_LINEAS_DIFF], "```"]
    if len(diff) > MAXIMO_LINEAS_DIFF:
        lineas.append(f"El diff tiene {len(diff)} líneas; se muestran {MAXIMO_LINEAS_DIFF}. El resto se lee en la copia de la rama.")
    lineas += ["", "## Hallazgos automáticos en los archivos cambiados", ""]
    lineas += [f"- {h['id']} · {h['criterio'] or h['fuente']} · {h['severidad']} · {h['titulo']} · "
               + ", ".join(f"`{e['archivo']}:{e['linea']}`" if e.get("linea") else f"`{e['archivo']}`" for e in h["evidencia"][:2])
               for h in automaticos] or ["Ninguno."]
    fichas = terceros.para_repo(raiz, producto, repo)
    if fichas:
        lineas += ["", "## Terceros del repositorio", ""]
        lineas += [f"- `{f['id']}` {f.get('nombre') or ''}: p95 {(f.get('sla') or {}).get('p95_ms') or '—'} ms, "
                   f"política ante falla {f.get('politica_ante_falla')}" for f in fichas]
    control = control_de_rama(raiz, producto, repo, estado["tipo"])
    lineas += ["", "## Contra qué comparar", "",
               "Documentos de arquitectura vigentes (regla rápida) y criterios de revisión de código de las decisiones. "
               "El texto de cada criterio está en su ADR.", ""]
    por_fuente: dict[str, list[dict]] = {}
    for e in sorted(control.values(), key=lambda e: (e["nivel"], e["clave"])):
        por_fuente.setdefault(e["fuente"], []).append(e)
    for fuente, elementos in por_fuente.items():
        primero = elementos[0]
        if primero["criterio"] is None:
            lineas.append(f"- `{fuente}`: {primero['texto']}")
        else:
            lineas.append(f"- `{fuente}` {primero['titulo']} ({primero['modo']}): " + ", ".join(e["criterio"] for e in elementos))
    if mr:
        lineas += ["", "Descripción del MR:", "", *[f"> {l}" for l in (mr["descripcion"] or "(vacía)").splitlines()]]
    lote = carpeta / "lote.yaml"
    lineas += [
        "", "## Entregables", "",
        f"1. Hallazgos en `{lote.relative_to(raiz)}` (solo la lista `hallazgos:`, con el mismo formato que en `/revisar`).",
        f"2. Registrar y ver la vista previa del comentario: `.venv/bin/python herramientas/rama.py publicar {producto} {repo} {rama} "
        "[--incluir H-NNNN,…]`.",
    ]
    archivo = carpeta / "paquete.md"
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return archivo


# --- Registrar ---------------------------------------------------------------------------------

def registrar(raiz: Path, producto: str, repo: str, rama: str, archivo: Path | None = None) -> dict:
    registro = registro_hallazgos.cargar(raiz, producto)
    ctx = contexto_rama(raiz, producto, repo, rama, registro)
    estado = ctx["estado"]
    datos = leer_lote(archivo or raiz / "productos" / producto / "revisiones" / estado["id_revision"] / "lote.yaml")
    control = control_de_rama(raiz, producto, repo, estado["tipo"])
    errores: list[str] = []
    hallazgos = []
    for hallazgo in hallazgos_del_lote(raiz, ctx, datos, control, errores):
        if hallazgo["evidencia"][0]["archivo"] in estado["cambiados"]:
            hallazgos.append(hallazgo)
        else:
            errores.append(f"{hallazgo['titulo']}: '{hallazgo['evidencia'][0]['archivo']}' no es un archivo que cambia la rama.")
    if errores:
        raise ErrorRadiografia(f"El lote tiene {len(errores)} error(es); no se registró nada:\n  - " + "\n  - ".join(errores))

    hoy = date.today().isoformat()
    resumen = registro_hallazgos.aplicar(registro, repo, rama, {"revision"}, hallazgos, estado["id_revision"], hoy, False)
    estado["revisada"] = {"fecha": hoy, "commit": estado["commit"]}
    registro_hallazgos.guardar(raiz, producto, registro)
    return {"resumen": resumen, "veredicto": veredicto(registro, repo, rama)}


# --- Publicar ----------------------------------------------------------------------------------

def a_publicar(registro: dict, repo: str, rama: str, incluir: list[str]) -> list[dict]:
    """Hallazgos abiertos de la rama marcados Resolver o elegidos ahora, seguridad primero y por severidad."""
    seleccion = [h for h in registro["hallazgos"].values()
                 if h["repo"] == repo and h["rama"] == rama and h["estado"] == "abierto" and not h.get("absorbido_por")
                 and ((h.get("triaje") or {}).get("decision") in ("resolver", "confirmar") or h["id"] in incluir)]
    return sorted(seleccion, key=lambda h: (h["categoria"] != "seguridad", ORDEN_SEVERIDAD.get(h["severidad"], 9), h["id"]))


def armar_comentario(estado: dict, seleccion: list[dict], corregidos: list[dict], enlace) -> str:
    lineas = [f"## Revisión de la rama `{estado['rama']}`", "",
              f"Commit `{estado['commit'][:12]}` · {len(seleccion)} hallazgo(s) por resolver"
              + (f" · {len(corregidos)} corregido(s) desde la publicación anterior" if corregidos else "") + ".", ""]
    if seleccion or corregidos:
        lineas += ["| Estado | Severidad | Hallazgo | Ubicación | Regla |", "|---|---|---|---|---|"]
    for h in seleccion:
        e = h["evidencia"][0] if h["evidencia"] else None
        texto = f"{e['archivo']}:{e['linea']}" if e and e.get("linea") else (e["archivo"] if e else "")
        ubicacion = f"[{texto}]({enlace(e['archivo'], e.get('linea'))})" if e else "—"
        estado_h = "🔁 reapareció" if h.get("reaparecido") else "⏳ pendiente"
        lineas.append(f"| {estado_h} | {h['severidad']} | {h['titulo'].replace('|', '/')} | {ubicacion} | {h['criterio'] or h['fuente']} |")
    for h in corregidos:
        lineas.append(f"| ✅ corregido | {h['severidad']} | {h['titulo'].replace('|', '/')} | — | {h['criterio'] or h['fuente']} |")
    if seleccion:
        lineas += ["", "<details>", "<summary>Detalle</summary>", ""]
        for h in seleccion:
            lineas += [f"**{h['id']} · {h['titulo']}** ({h['severidad']})", "", h["detalle"], ""]
            if h.get("cita_documento"):
                lineas += [f"> {h['cita_documento']}", ""]
        lineas.append("</details>")
    return "\n".join(lineas) + "\n"


def publicar(raiz: Path, producto: str, repo: str, rama: str, incluir: list[str] | None = None, confirmar: bool = False,
             cliente: ClientePlataforma | None = None) -> dict:
    incluir = incluir or []
    datos_repo = repo_del_producto(raiz, producto, repo)
    registro = registro_hallazgos.cargar(raiz, producto)
    estado = estado_rama(registro, repo, rama)
    if (raiz / "productos" / producto / "revisiones" / estado["id_revision"] / "lote.yaml").exists():
        registrar(raiz, producto, repo, rama)
        registro = registro_hallazgos.cargar(raiz, producto)
        estado = estado_rama(registro, repo, rama)
    if not estado.get("revisada") or estado["revisada"]["commit"] != estado["commit"]:
        raise ErrorRadiografia(f"Falta registrar la revisión de código de la rama: rama.py registrar {producto} {repo} {rama}")
    de_la_rama = {h["id"]: h for h in registro["hallazgos"].values() if h["repo"] == repo and h["rama"] == rama}
    desconocidos = [i for i in incluir if i not in de_la_rama or de_la_rama[i]["estado"] != "abierto"]
    if desconocidos:
        raise ErrorRadiografia(f"No son hallazgos abiertos de la rama: {', '.join(desconocidos)}.")

    seleccion = a_publicar(registro, repo, rama, incluir)
    anterior = estado.get("publicacion") or {}
    corregidos = [de_la_rama[i] for i in anterior.get("publicados", []) if i in de_la_rama and de_la_rama[i]["estado"] == "corregido"]
    if not seleccion and not corregidos:
        candidatos = sorted((h for h in de_la_rama.values() if h["estado"] == "abierto"), key=lambda h: h["id"])
        raise ErrorRadiografia(
            f"Nada que publicar: ningún hallazgo de la rama está marcado Resolver. Veredicto de la rama: {veredicto(registro, repo, rama)}. "
            + ("Elegir con --incluir entre:\n  - " + "\n  - ".join(f"{h['id']} · {h['severidad']} · {h['titulo']}" for h in candidatos)
               if candidatos else "La rama no tiene hallazgos abiertos."))

    if cliente is None:
        cliente, motivo = cliente_desde_env(raiz)
    else:
        motivo = None
    proyecto = proyecto_de(str(datos_repo["url"]))
    mr = estado["mr"]
    if cliente:
        mr = cliente.mr_de_rama(proyecto, rama) or None
    enlace = (lambda archivo, linea: cliente.enlace_archivo(proyecto, estado["commit"], archivo, linea)) if cliente \
        else (lambda archivo, linea: f"{archivo}#L{linea}" if linea else archivo)
    cuerpo = armar_comentario(estado, seleccion, corregidos, enlace)
    avisos = lenguaje.formatear(lenguaje.revisar(cuerpo), "comentario")
    destino = f"MR {mr['url']}" if mr else "sin MR o PR abierto: no se puede publicar"
    carpeta = raiz / "productos" / producto / "revisiones" / estado["id_revision"]
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "comentario.md").write_text(cuerpo, encoding="utf-8")
    resultado = {"cuerpo": cuerpo, "destino": destino, "avisos": avisos, "publicado": False,
                 "seleccion": [h["id"] for h in seleccion], "veredicto": veredicto(registro, repo, rama)}
    if not confirmar:
        return resultado
    if avisos:
        raise ErrorRadiografia("El comentario tiene avisos de lenguaje; corregir el título o el detalle de los hallazgos:\n  - "
                               + "\n  - ".join(avisos))
    if cliente is None:
        raise ErrorRadiografia(f"No se puede publicar: {motivo}.")
    if not mr:
        raise ErrorRadiografia(f"La rama '{rama}' no tiene un MR o PR abierto: solo se comentan MR o PR. "
                               f"La vista previa quedó en {(carpeta / 'comentario.md').relative_to(raiz)}.")

    hoy = date.today().isoformat()
    id_previo = anterior.get("id_comentario") if anterior.get("numero") == mr["numero"] else None
    id_comentario = cliente.comentar_mr(proyecto, mr["numero"], cuerpo, id_previo)
    for id_hallazgo in incluir:
        h = de_la_rama[id_hallazgo]
        if (h.get("triaje") or {}).get("decision") != "resolver":
            if h.get("triaje"):
                h.setdefault("historial_triaje", []).append(h["triaje"])
            h["triaje"] = {"decision": "resolver", "motivo": "elegido al publicar la revisión de la rama", "vence": None, "fecha": hoy}
    estado["publicacion"] = {"numero": mr["numero"], "id_comentario": id_comentario, "commit": estado["commit"], "fecha": hoy,
                             "publicados": [h["id"] for h in seleccion]}
    registro_hallazgos.guardar(raiz, producto, registro)
    return {**resultado, "publicado": True}


# --- Programa principal ------------------------------------------------------------------------

def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Revisión de ramas y publicación en el MR o PR.")
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="raíz de radiografia (para pruebas)")
    sub = parser.add_subparsers(dest="accion", required=True)
    for nombre in ("preparar", "registrar", "publicar"):
        p = sub.add_parser(nombre)
        p.add_argument("producto")
        p.add_argument("repo")
        p.add_argument("rama")
        if nombre == "registrar":
            p.add_argument("--archivo", type=Path)
        if nombre == "publicar":
            p.add_argument("--incluir", default="", help="hallazgos a publicar además de los marcados Resolver")
            p.add_argument("--confirmar", action="store_true", help="publicar; sin esta opción solo se muestra la vista previa")
    o = parser.parse_args(argumentos)
    raiz = o.raiz.resolve()
    try:
        if o.accion == "preparar":
            r = preparar(raiz, o.producto, o.repo, o.rama)
            e, s = r["estado"], r["resumen"]
            print(f"Rama '{o.rama}' de '{o.repo}' @ {e['commit'][:12]}: {e['commits']} commit(s), {len(e['cambiados'])} archivo(s) "
                  f"cambiado(s) frente a '{e['destino']}'. MR: {e['mr']['url'] if e['mr'] else 'sin MR abierto'}.")
            if e["aviso_mr"]:
                print(f"  Aviso: no se consultó el MR ({e['aviso_mr']}).")
            print(f"  Hallazgos automáticos en archivos cambiados: nuevos {len(s['nuevos'])}, abiertos {len(s['abiertos'])}, "
                  f"corregidos {len(s['corregidos'])}.")
            print(f"Paquete: {r['paquete'].relative_to(raiz)}")
        elif o.accion == "registrar":
            r = registrar(raiz, o.producto, o.repo, o.rama, o.archivo)
            s = r["resumen"]
            print(f"Revisión de la rama registrada: nuevos {len(s['nuevos'])}, abiertos {len(s['abiertos'])}, "
                  f"corregidos {len(s['corregidos'])}. Veredicto de la rama: {r['veredicto']}")
        elif o.accion == "publicar":
            ids = [i.strip() for i in o.incluir.split(",") if i.strip()]
            r = publicar(raiz, o.producto, o.repo, o.rama, ids, o.confirmar)
            if r["publicado"]:
                print(f"Publicado en {r['destino']}.")
            else:
                print(f"Veredicto de la rama: {r['veredicto']}")
                print(f"Vista previa (destino: {r['destino']}). Para publicar, repetir con --confirmar.\n")
                print(r["cuerpo"])
                for aviso in r["avisos"]:
                    print(f"  Aviso de lenguaje (bloquea la publicación): {aviso}")
    except ErrorRadiografia as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
