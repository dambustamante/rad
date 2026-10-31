"""Herramientas del harness del producto (solo biblioteca estándar).

Uso:
  python3 herramientas/harness.py code [--enlazar CARPETA]   clona o actualiza los repositorios en code/
  python3 herramientas/harness.py doctor                     verifica git, Python, gitleaks y que code/ no esté en git
  python3 herramientas/harness.py foco [--repos a,b]         deja visibles en Cursor solo esos repositorios (sin --repos: todos)
  python3 herramientas/harness.py adr --titulo TEXTO [--historia CLAVE]   ADR del producto en Propuesto

`code` clona lo que falta en la rama principal y, en lo que ya existe, solo trae novedades (`git fetch`):
nunca cambia la rama de trabajo ni descarta cambios. Con --enlazar, si CARPETA/<repo> ya es un clon, crea un
enlace a él en lugar de clonar de nuevo.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def git(*argumentos: str, cwd: Path | None = None) -> tuple[int, str]:
    resultado = subprocess.run(["git", *argumentos], cwd=cwd, capture_output=True, text=True)
    return resultado.returncode, (resultado.stdout or resultado.stderr).strip()


def repos() -> list[dict]:
    return json.loads((RAIZ / "repos.json").read_text(encoding="utf-8"))["repos"]


def code(enlazar: Path | None) -> int:
    errores = 0
    for repo in repos():
        destino = RAIZ / "code" / repo["id"]
        if not (destino / ".git").exists():
            destino.parent.mkdir(parents=True, exist_ok=True)
            existente = (enlazar / repo["id"]).expanduser().resolve() if enlazar else None
            if existente and (existente / ".git").exists():
                destino.symlink_to(existente, target_is_directory=True)
                print(f"  {repo['id']}: enlazado a {existente}")
                continue
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
    _, en_git = git("ls-files", "code", cwd=RAIZ)
    if en_git:
        print("  [FALTA] code/ tiene archivos en git del harness: quitarlos (git rm -r --cached code) y revisar .gitignore")
        faltantes += 1
    else:
        print("  [OK]    code/ fuera de git del harness")
    print(f"  [{'OK' if (RAIZ / '.env').exists() else 'AVISO'}]    .env" + ("" if (RAIZ / ".env").exists() else " (copiar .env.example para usar /hdu)"))
    return 1 if faltantes else 0


def foco(visibles: list[str] | None) -> int:
    sys.path.insert(0, str(RAIZ / "herramientas"))
    import hdu
    ids = [r["id"] for r in repos()]
    desconocidos = [r for r in visibles or [] if r not in ids]
    if desconocidos:
        print(f"ERROR: repositorios que no son del producto: {', '.join(desconocidos)}")
        return 1
    hdu.foco(visibles, ids)
    print(f"Visibles en Cursor: {', '.join(visibles) if visibles else 'todos los repositorios'}")
    return 0


def slug(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes).strip("-")[:60] or "decision"


def adr(titulo: str, historia: str | None) -> int:
    sigla = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))["sigla"]
    carpeta = RAIZ / "decisiones"
    numeros = [int(m.group(1)) for a in carpeta.glob(f"ADR-{sigla}-*.md") if (m := re.match(rf"ADR-{sigla}-(\d{{3}})", a.name))]
    numero = f"{max(numeros, default=0) + 1:03d}"
    texto = (carpeta / "plantilla.md").read_text(encoding="utf-8")
    texto = texto.replace(f"ADR-{sigla}-NNN: <Título de la decisión>", f"ADR-{sigla}-{numero}: {titulo}")
    texto = texto.replace(f"`{sigla}-NNN.1`", f"`{sigla}-{numero}.1`").replace(f"(`{sigla}-NNN.N`)", f"(`{sigla}-{numero}.N`)")
    texto = texto.replace("Fecha de creación: `DD-MM-AAAA`", f"Fecha de creación: `{date.today().strftime('%d-%m-%Y')}`")
    if historia:
        texto = texto.replace("- **Historias de origen:** —", f"- **Historias de origen:** {historia}")
    archivo = carpeta / f"ADR-{sigla}-{numero}-{slug(titulo)}.md"
    archivo.write_text(texto, encoding="utf-8")
    print(f"Creado: {archivo.relative_to(RAIZ)} (Propuesto). Completarlo y abrir un MR a este repositorio: "
          "se aprueba con las aprobaciones configuradas en este repositorio.")
    return 0


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Herramientas del harness.")
    sub = parser.add_subparsers(dest="accion", required=True)
    p = sub.add_parser("code")
    p.add_argument("--enlazar", type=Path)
    sub.add_parser("doctor")
    p = sub.add_parser("foco")
    p.add_argument("--repos", default="")
    p = sub.add_parser("adr")
    p.add_argument("--titulo", required=True)
    p.add_argument("--historia")
    o = parser.parse_args(argumentos)
    if o.accion == "code":
        return code(o.enlazar)
    if o.accion == "doctor":
        return doctor()
    if o.accion == "foco":
        return foco([r.strip() for r in o.repos.split(",") if r.strip()] or None)
    return adr(o.titulo, o.historia)


if __name__ == "__main__":
    sys.exit(main())
