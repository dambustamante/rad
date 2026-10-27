"""Utilidades compartidas por las herramientas de radiografia."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import unicodedata
from pathlib import Path

import yaml
from ruamel.yaml import YAML

RAIZ = Path(__file__).resolve().parent.parent


class ErrorRadiografia(Exception):
    """Error esperado, con un mensaje que se muestra tal cual al usuario."""


def cargar_env(raiz: Path = RAIZ) -> dict[str, str]:
    """Lee `.env` y aplica encima las variables de entorno del proceso.

    Los comentarios en línea (`CLAVE=valor  # comentario`) se descartan.
    """
    valores: dict[str, str] = {}
    archivo = raiz / ".env"
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            linea = linea.split("#", 1)[0].strip()
            if not linea or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip().strip('"').strip("'")
    for clave, valor in os.environ.items():
        if clave in valores or clave.isupper():
            valores[clave] = valor
    return valores


def cargar_config(raiz: Path = RAIZ) -> dict:
    """Lee `harness.yaml`."""
    archivo = raiz / "harness.yaml"
    if not archivo.exists():
        raise ErrorRadiografia(f"No existe {archivo}.")
    try:
        config = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise ErrorRadiografia(f"harness.yaml no es un YAML válido: {error}") from error
    if not isinstance(config, dict):
        raise ErrorRadiografia("harness.yaml debe ser un mapa de claves.")
    return config


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios simples, para comparar textos."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())


def git(*argumentos: str, cwd: Path | None = None) -> str:
    """Ejecuta git y devuelve su salida. Lanza ErrorRadiografia si falla."""
    resultado = subprocess.run(
        ["git", *argumentos],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if resultado.returncode != 0:
        detalle = resultado.stderr.strip() or resultado.stdout.strip()
        raise ErrorRadiografia(f"git {' '.join(argumentos)} falló: {detalle}")
    return resultado.stdout.strip()


def resolver_url(url: str, raiz: Path = RAIZ) -> str:
    """Una ruta local existente se usa como ruta absoluta; cualquier otra cosa es una URL de git."""
    candidata = Path(url).expanduser()
    if not candidata.is_absolute():
        candidata = raiz / candidata
    return str(candidata.resolve()) if candidata.is_dir() else url


def actualizar_clon(url: str, destino: Path, raiz: Path = RAIZ) -> None:
    """Clona el repositorio en `destino` (sin checkout) o trae sus novedades si ya existe."""
    url_resuelta = resolver_url(url, raiz)
    try:
        if (destino / ".git").exists():
            git("remote", "set-url", "origin", url_resuelta, cwd=destino)
            git("fetch", "--quiet", "--prune", "--tags", "--force", "origin", cwd=destino)
        else:
            destino.parent.mkdir(parents=True, exist_ok=True)
            if destino.exists():
                shutil.rmtree(destino)
            git("clone", "--quiet", "--no-checkout", url_resuelta, str(destino))
    except ErrorRadiografia as error:
        raise ErrorRadiografia(
            f"No se pudo acceder a '{url}'. Verifique la URL y sus credenciales de git. Detalle: {error}"
        ) from error


def clon_de_inspeccion(url: str, raiz: Path = RAIZ) -> Path:
    """Clon de trabajo en `.cache/inspeccion/` para examinar un repositorio antes de registrarlo."""
    clave = hashlib.sha1(resolver_url(url, raiz).encode("utf-8")).hexdigest()[:12]
    destino = raiz / ".cache" / "inspeccion" / clave
    actualizar_clon(url, destino, raiz)
    return destino


def rama_por_defecto(clon: Path) -> str:
    try:
        return git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=clon).removeprefix("origin/")
    except ErrorRadiografia:
        ramas = git("branch", "-r", "--format=%(refname:short)", cwd=clon).split()
        for candidata in ("origin/main", "origin/master"):
            if candidata in ramas:
                return candidata.removeprefix("origin/")
        raise ErrorRadiografia("No se pudo determinar la rama por defecto del repositorio.")


def resolver_commit(clon: Path, ref: str) -> str:
    """Commit de una rama remota, un tag o un commit."""
    for candidato in (f"origin/{ref}", f"refs/tags/{ref}", ref):
        try:
            return git("rev-parse", "--verify", "--quiet", f"{candidato}^{{commit}}", cwd=clon)
        except ErrorRadiografia:
            continue
    raise ErrorRadiografia(f"La ref '{ref}' no existe en el repositorio.")


def ruta_existe(clon: Path, commit: str, ruta: str) -> bool:
    ruta = ruta.strip("/")
    if ruta in ("", "."):
        return True
    try:
        return git("cat-file", "-t", f"{commit}:{ruta}", cwd=clon) == "tree"
    except ErrorRadiografia:
        return False


def yaml_conservador() -> YAML:
    """YAML que conserva comentarios y formato al reescribir un archivo."""
    yaml_rt = YAML()
    yaml_rt.preserve_quotes = True
    yaml_rt.indent(mapping=2, sequence=4, offset=2)
    yaml_rt.width = 120
    yaml_rt.representer.add_representer(
        type(None), lambda representer, _: representer.represent_scalar("tag:yaml.org,2002:null", "null")
    )
    return yaml_rt


def leer_yaml_conservador(archivo: Path):
    if not archivo.exists():
        raise ErrorRadiografia(f"No existe {archivo}.")
    return yaml_conservador().load(archivo.read_text(encoding="utf-8"))


def escribir_yaml_conservador(archivo: Path, datos) -> None:
    with archivo.open("w", encoding="utf-8") as salida:
        yaml_conservador().dump(datos, salida)
