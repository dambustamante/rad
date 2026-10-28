"""Registro de hallazgos de un producto: productos/<producto>/hallazgos.json.

Cada hallazgo se identifica por una huella estable (fuente, criterio, archivo y un fragmento
normalizado; nunca el número de línea), de modo que se reconoce entre revisiones aunque el código
se mueva. El registro conserva las decisiones de triaje.

Estados: `abierto` o `corregido`. Un hallazgo corregido que vuelve a aparecer se reabre y se marca
como reaparecido.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from comun import normalizar

VERSION = 1


def huella(*partes: object) -> str:
    texto = "|".join(normalizar(str(p)) for p in partes if p is not None)
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def archivo_registro(raiz: Path, producto: str) -> Path:
    return raiz / "productos" / producto / "hallazgos.json"


def cargar(raiz: Path, producto: str) -> dict:
    archivo = archivo_registro(raiz, producto)
    if not archivo.exists():
        return {"version": VERSION, "siguiente_id": 1, "hallazgos": {}}
    return json.loads(archivo.read_text(encoding="utf-8"))


def guardar(raiz: Path, producto: str, registro: dict) -> None:
    archivo = archivo_registro(raiz, producto)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(registro, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def tiene_revisiones(registro: dict, repo: str, rama: str) -> bool:
    return any(h["repo"] == repo and h["rama"] == rama for h in registro["hallazgos"].values())


def aplicar(registro: dict, repo: str, rama: str, origenes_ejecutados: set[str], encontrados: list[dict],
            id_revision: str, fecha: str, es_linea_base: bool) -> dict:
    """Incorpora los hallazgos de una revisión de `repo`/`rama` y devuelve el resumen de cambios.

    Solo se cierran hallazgos de los orígenes que se ejecutaron bien en esta revisión: si Sonar no
    respondió, sus hallazgos anteriores siguen abiertos.
    """
    resumen = {"nuevos": [], "reaparecidos": [], "corregidos": [], "abiertos": []}
    vistos = set()
    for encontrado in encontrados:
        clave = encontrado["huella"]
        if clave in vistos:
            continue
        vistos.add(clave)
        existente = registro["hallazgos"].get(clave)
        if existente is None:
            id_hallazgo = f"H-{registro['siguiente_id']:04d}"
            registro["siguiente_id"] += 1
            registro["hallazgos"][clave] = {
                **encontrado,
                "id": id_hallazgo, "repo": repo, "rama": rama, "estado": "abierto",
                "primera_vez": fecha, "ultima_vez": fecha, "revisiones": [id_revision],
                "linea_base": es_linea_base, "reaparecido": False, "corregido": None, "triaje": None,
            }
            resumen["nuevos"].append(id_hallazgo)
            continue
        reaparece = existente["estado"] == "corregido"
        existente.update({clave_dato: valor for clave_dato, valor in encontrado.items()})
        existente.update({"estado": "abierto", "ultima_vez": fecha, "corregido": None})
        existente["revisiones"].append(id_revision)
        if reaparece:
            existente["reaparecido"] = True
            resumen["reaparecidos"].append(existente["id"])
        else:
            resumen["abiertos"].append(existente["id"])

    for clave, hallazgo in registro["hallazgos"].items():
        if (hallazgo["repo"] == repo and hallazgo["rama"] == rama and hallazgo["estado"] == "abierto"
                and hallazgo["origen"] in origenes_ejecutados and clave not in vistos):
            hallazgo["estado"] = "corregido"
            hallazgo["corregido"] = fecha
            resumen["corregidos"].append(hallazgo["id"])
    return resumen
