"""Verifica que el entorno tenga lo necesario para usar radiografia.

Uso: python herramientas/doctor.py

Nunca muestra valores de variables: solo indica si están definidas.
Termina con código 1 si falta algo obligatorio.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
import sys

from comun import RAIZ, ErrorRadiografia, cargar_config, cargar_env

OK, FALTA, AVISO = "OK", "FALTA", "AVISO"


def revisar() -> list[tuple[str, str, str]]:
    """Devuelve una lista de (estado, elemento, detalle)."""
    resultados: list[tuple[str, str, str]] = []

    version = sys.version_info
    if version >= (3, 11):
        resultados.append((OK, "Python", f"{version.major}.{version.minor}"))
    else:
        resultados.append((FALTA, "Python", "se requiere 3.11 o superior"))

    if shutil.which("git"):
        resultados.append((OK, "git", "instalado"))
    else:
        resultados.append((FALTA, "git", "instalar con: xcode-select --install"))

    try:
        config = cargar_config()
        fuentes = (config.get("arquitectura") or {}).get("fuentes") or []
        detalle = f"{len(fuentes)} fuente(s) de arquitectura"
        resultados.append((OK if fuentes else AVISO, "harness.yaml", detalle))
    except ErrorRadiografia as error:
        resultados.append((FALTA, "harness.yaml", str(error)))

    if (RAIZ / ".env").exists():
        resultados.append((OK, ".env", "existe"))
    else:
        resultados.append((AVISO, ".env", "no existe; copiar .env.example a .env"))

    env = cargar_env()
    plataforma = env.get("GIT_PLATAFORMA", "").strip().lower()
    if plataforma in ("gitlab", "github"):
        resultados.append((OK, "GIT_PLATAFORMA", plataforma))
        resultados.append(_variable(env, f"{plataforma.upper()}_TOKEN", "necesario para revisar ramas con su MR o PR y publicar comentarios"))
    else:
        resultados.append((AVISO, "GIT_PLATAFORMA", "definir gitlab o github en .env; necesario para revisar ramas con su MR o PR"))

    tipo_sonar = env.get("SONAR_TIPO", "").strip().lower()
    if tipo_sonar in ("sonarqube", "sonarcloud"):
        resultados.append((OK, "SONAR_TIPO", tipo_sonar))
    else:
        resultados.append((AVISO, "SONAR_TIPO", "definir sonarqube o sonarcloud en .env; necesario para /revisar"))
    variables_sonar = ["SONAR_URL", "SONAR_TOKEN"] + (["SONAR_ORGANIZACION"] if tipo_sonar == "sonarcloud" else [])
    for variable in variables_sonar:
        resultados.append(_variable(env, variable, "necesario para /revisar"))

    for variable in ("JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN"):
        resultados.append(_variable(env, variable, "necesario solo para productos con historias en Jira"))
    resultados.append(_variable(env, "CONFLUENCE_URL", "necesario solo para importar documentos desde Confluence"))
    if env.get("CA_BUNDLE"):
        existe = Path(os.path.expanduser(env["CA_BUNDLE"])).is_file()
        resultados.append((OK if existe else ERROR, "CA_BUNDLE", "archivo de certificados encontrado" if existe else "el archivo indicado no existe"))

    if shutil.which("pdftotext"):
        resultados.append((OK, "pdftotext", "instalado"))
    else:
        resultados.append((AVISO, "pdftotext", "necesario para leer documentación del proveedor en PDF; instalar con: brew install poppler"))

    if shutil.which("gitleaks"):
        resultados.append((OK, "gitleaks", "instalado"))
    else:
        resultados.append((AVISO, "gitleaks", "necesario para /revisar; instalar con: brew install gitleaks"))

    return resultados


def _variable(env: dict[str, str], nombre: str, uso: str) -> tuple[str, str, str]:
    if env.get(nombre):
        return (OK, nombre, "definida")
    return (AVISO, nombre, f"sin definir en .env; {uso}")


def main() -> int:
    resultados = revisar()
    ancho = max(len(elemento) for _, elemento, _ in resultados)
    print("Estado del entorno de radiografia\n")
    for estado, elemento, detalle in resultados:
        print(f"  [{estado:<5}] {elemento:<{ancho}}  {detalle}")
    faltantes = [elemento for estado, elemento, _ in resultados if estado == FALTA]
    avisos = sum(1 for estado, _, _ in resultados if estado == AVISO)
    print()
    if faltantes:
        print(f"Falta lo obligatorio: {', '.join(faltantes)}.")
        return 1
    print(f"Lo obligatorio está disponible. Avisos: {avisos}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
