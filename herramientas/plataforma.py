"""Cliente mínimo de la plataforma git (GitLab o GitHub) para la revisión de ramas.

Solo hace lo necesario:
- buscar el MR o PR abierto de una rama, con sus aprobaciones;
- crear o editar un comentario en un MR o PR (no se comentan commits).

La conexión se lee de .env (GIT_PLATAFORMA, GITLAB_URL/GITLAB_TOKEN o GITHUB_URL/GITHUB_TOKEN). Este módulo
no decide qué publicar ni pide confirmación: eso lo hace rama.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

import requests

from comun import ErrorRadiografia

PLATAFORMAS = ("gitlab", "github")
TIEMPO_ESPERA = 30


def proyecto_de(url: str) -> str:
    """Ruta del proyecto (grupo/subgrupo/proyecto u owner/repo) a partir de la URL de git."""
    texto = url.strip().removesuffix("/").removesuffix(".git")
    coincidencia = re.match(r"^[\w.-]+@[\w.-]+:(.+)$", texto) or re.match(r"^(?:https?|ssh)://(?:[^@/]+@)?[^/]+(?::\d+)?/(.+)$", texto)
    if not coincidencia:
        raise ErrorRadiografia(f"No se pudo obtener el proyecto de la URL '{url}': se necesita una URL de GitLab o GitHub.")
    return coincidencia.group(1)


@dataclass
class ConfigPlataforma:
    tipo: str
    url: str
    token: str

    @classmethod
    def desde_env(cls, env: dict[str, str]) -> "ConfigPlataforma | None":
        tipo = (env.get("GIT_PLATAFORMA") or "").strip().lower()
        if tipo not in PLATAFORMAS:
            return None
        prefijo = tipo.upper()
        token = (env.get(f"{prefijo}_TOKEN") or "").strip()
        url = (env.get(f"{prefijo}_URL") or ("https://gitlab.com" if tipo == "gitlab" else "https://github.com")).strip().rstrip("/")
        return cls(tipo, url, token) if token else None

    @staticmethod
    def motivo_sin_config(env: dict[str, str]) -> str | None:
        tipo = (env.get("GIT_PLATAFORMA") or "").strip().lower()
        if tipo not in PLATAFORMAS:
            return "GIT_PLATAFORMA no está definida en .env (gitlab o github)"
        if not (env.get(f"{tipo.upper()}_TOKEN") or "").strip():
            return f"{tipo.upper()}_TOKEN no está definido en .env"
        return None


class ClientePlataforma:
    def __init__(self, config: ConfigPlataforma, sesion: requests.Session | None = None) -> None:
        self.config = config
        self.sesion = sesion or requests.Session()
        if config.tipo == "gitlab":
            self.api = f"{config.url}/api/v4"
            self.sesion.headers.update({"PRIVATE-TOKEN": config.token})
        else:
            self.api = "https://api.github.com" if config.url == "https://github.com" else f"{config.url}/api/v3"
            self.sesion.headers.update({"Authorization": f"Bearer {config.token}", "Accept": "application/vnd.github+json"})

    # --- HTTP ---

    def _pedir(self, metodo: str, ruta: str, **opciones) -> dict | list:
        try:
            respuesta = self.sesion.request(metodo, f"{self.api}{ruta}", timeout=TIEMPO_ESPERA, **opciones)
        except requests.RequestException as error:
            raise ErrorRadiografia(f"No se pudo conectar con {self.config.tipo}: {error}") from error
        if respuesta.status_code in (401, 403):
            raise ErrorRadiografia(f"{self.config.tipo} rechazó el token (HTTP {respuesta.status_code}). Revisar sus permisos.")
        if respuesta.status_code == 404:
            raise ErrorRadiografia(f"{self.config.tipo} no encontró {ruta} (HTTP 404). Revisar la URL del repositorio y el acceso del token.")
        if respuesta.status_code >= 400:
            raise ErrorRadiografia(f"{self.config.tipo} respondió HTTP {respuesta.status_code}: {respuesta.text[:200]}")
        return respuesta.json() if respuesta.content else {}

    def _proyecto(self, proyecto: str) -> str:
        return f"/projects/{quote(proyecto, safe='')}" if self.config.tipo == "gitlab" else f"/repos/{proyecto}"

    # --- Enlaces ---

    def enlace_archivo(self, proyecto: str, commit: str, archivo: str, linea: int | None) -> str:
        separador = "/-/blob/" if self.config.tipo == "gitlab" else "/blob/"
        return f"{self.config.url}/{proyecto}{separador}{commit}/{archivo}" + (f"#L{linea}" if linea else "")

    # --- MR o PR ---

    def _mr_gitlab(self, proyecto: str, datos: dict) -> dict:
        aprobaciones = self._pedir("GET", f"{self._proyecto(proyecto)}/merge_requests/{datos['iid']}/approvals")
        return {**self._resumen_gitlab(datos),
                "aprobado_por": [a["user"]["username"] for a in aprobaciones.get("approved_by", [])]}

    @staticmethod
    def _resumen_gitlab(datos: dict) -> dict:
        return {"numero": datos["iid"], "url": datos["web_url"], "titulo": datos["title"],
                "descripcion": datos.get("description") or "", "destino": datos["target_branch"],
                "rama": datos.get("source_branch"), "commit": datos.get("sha"),
                "autor": (datos.get("author") or {}).get("username"),
                "revisores": [r.get("username") for r in datos.get("reviewers") or []]}

    def _mr_github(self, proyecto: str, datos: dict) -> dict:
        revisiones = self._pedir("GET", f"{self._proyecto(proyecto)}/pulls/{datos['number']}/reviews")
        return {**self._resumen_github(datos),
                "aprobado_por": sorted({r["user"]["login"] for r in revisiones if r.get("state") == "APPROVED"})}

    @staticmethod
    def _resumen_github(datos: dict) -> dict:
        return {"numero": datos["number"], "url": datos["html_url"], "titulo": datos["title"],
                "descripcion": datos.get("body") or "", "destino": datos["base"]["ref"],
                "rama": (datos.get("head") or {}).get("ref"), "commit": (datos.get("head") or {}).get("sha"),
                "autor": (datos.get("user") or {}).get("login"),
                "revisores": [r.get("login") for r in datos.get("requested_reviewers") or []]}

    def mrs_abiertos(self, proyecto: str) -> list[dict]:
        """MR o PR abiertos del proyecto, sin aprobaciones (para la bandeja)."""
        if self.config.tipo == "gitlab":
            lista = self._pedir("GET", f"{self._proyecto(proyecto)}/merge_requests", params={"state": "opened", "per_page": 100})
            return [self._resumen_gitlab(m) for m in lista]
        lista = self._pedir("GET", f"{self._proyecto(proyecto)}/pulls", params={"state": "open", "per_page": 100})
        return [self._resumen_github(p) for p in lista]

    def mr_de_rama(self, proyecto: str, rama: str) -> dict | None:
        """MR o PR abierto cuya rama de origen es `rama`, o None."""
        if self.config.tipo == "gitlab":
            lista = self._pedir("GET", f"{self._proyecto(proyecto)}/merge_requests",
                                params={"source_branch": rama, "state": "opened"})
            return self._mr_gitlab(proyecto, lista[0]) if lista else None
        propietario = proyecto.split("/")[0]
        lista = self._pedir("GET", f"{self._proyecto(proyecto)}/pulls", params={"head": f"{propietario}:{rama}", "state": "open"})
        return self._mr_github(proyecto, lista[0]) if lista else None

    # --- Comentarios ---

    def comentar_mr(self, proyecto: str, numero: int, cuerpo: str, id_comentario: int | None = None) -> int:
        """Crea el comentario o, si se indica `id_comentario`, lo edita. Devuelve su id."""
        if self.config.tipo == "gitlab":
            base = f"{self._proyecto(proyecto)}/merge_requests/{numero}/notes"
            datos = (self._pedir("PUT", f"{base}/{id_comentario}", json={"body": cuerpo}) if id_comentario
                     else self._pedir("POST", base, json={"body": cuerpo}))
        else:
            datos = (self._pedir("PATCH", f"{self._proyecto(proyecto)}/issues/comments/{id_comentario}", json={"body": cuerpo})
                     if id_comentario else self._pedir("POST", f"{self._proyecto(proyecto)}/issues/{numero}/comments", json={"body": cuerpo}))
        return int(datos["id"])
