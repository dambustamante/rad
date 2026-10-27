"""Utilidades compartidas por las herramientas de radiografia."""

from __future__ import annotations

import os
import subprocess
import unicodedata
from pathlib import Path

import yaml

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
