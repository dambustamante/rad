"""Herramientas del harness del producto (solo biblioteca estándar).

Uso:
  python3 herramientas/harness.py code      clona o actualiza los repositorios de repos.json en code/
  python3 herramientas/harness.py doctor    verifica git, Python y gitleaks

`code` clona lo que falta en la rama principal y, en lo que ya existe, solo trae novedades (`git fetch`):
nunca cambia la rama de trabajo ni descarta cambios.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def git(*argumentos: str, cwd: Path | None = None) -> tuple[int, str]:
    resultado = subprocess.run(["git", *argumentos], cwd=cwd, capture_output=True, text=True)
    return resultado.returncode, (resultado.stdout or resultado.stderr).strip()


def repos() -> list[dict]:
    return json.loads((RAIZ / "repos.json").read_text(encoding="utf-8"))["repos"]


def code() -> int:
    errores = 0
    for repo in repos():
        destino = RAIZ / "code" / repo["id"]
        if not (destino / ".git").exists():
            destino.parent.mkdir(parents=True, exist_ok=True)
            codigo, salida = git("clone", "--quiet", "--branch", repo["rama"], repo["url"], str(destino))
            print(f"  {repo['id']}: {'clonado' if codigo == 0 else 'ERROR - ' + salida}")
            errores += codigo != 0
            continue
        codigo, salida = git("fetch", "--quiet", "--prune", cwd=destino)
        _, rama = git("branch", "--show-current", cwd=destino)
        _, cambios = git("status", "--porcelain", cwd=destino)
        estado = "actualizado" if codigo == 0 else "ERROR - " + salida
        print(f"  {repo['id']}: {estado} · rama {rama or '(sin rama)'}" + (" · con cambios sin commit" if cambios else ""))
        errores += codigo != 0
    return 1 if errores else 0


def doctor() -> int:
    faltantes = 0
    for nombre, obligatorio in (("git", True), ("gitleaks", False)):
        if shutil.which(nombre):
            print(f"  [OK]    {nombre}")
        else:
            print(f"  [{'FALTA' if obligatorio else 'AVISO'}] {nombre}" + ("" if obligatorio else " (brew install gitleaks)"))
            faltantes += obligatorio
    version = sys.version_info
    print(f"  [{'OK' if version >= (3, 11) else 'FALTA'}]    Python {version.major}.{version.minor}")
    faltantes += version < (3, 11)
    return 1 if faltantes else 0


if __name__ == "__main__":
    acciones = {"code": code, "doctor": doctor}
    if len(sys.argv) != 2 or sys.argv[1] not in acciones:
        print(__doc__)
        sys.exit(2)
    sys.exit(acciones[sys.argv[1]]())
