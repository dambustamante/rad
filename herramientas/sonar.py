"""Cliente de solo lectura para SonarQube (incluida la Community Edition) y SonarCloud.

Usa solo las APIs comunes a ambos. Nunca ejecuta análisis ni modifica nada en el servidor.
Configuración en .env: SONAR_TIPO (sonarqube | sonarcloud), SONAR_URL, SONAR_TOKEN y, solo para
SonarCloud, SONAR_ORGANIZACION.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from comun import ErrorRadiografia

METRICAS = (
    "ncloc", "coverage", "duplicated_lines_density", "bugs", "vulnerabilities", "code_smells",
    "security_hotspots", "sqale_index", "reliability_rating", "security_rating", "sqale_rating",
)
LIMITE_ISSUES = 2000
TAMANO_PAGINA = 500

# Severidad del formato nuevo (impacts) y del formato anterior (severity), llevadas a la escala del harness.
SEVERIDADES = {
    "BLOCKER": "bloqueante", "HIGH": "alta", "CRITICAL": "alta",
    "MEDIUM": "media", "MAJOR": "media", "LOW": "baja", "MINOR": "baja", "INFO": "baja",
}
ORDEN_SEVERIDAD = ("bloqueante", "alta", "media", "baja")
CATEGORIAS = {
    "BUG": "error", "RELIABILITY": "error", "VULNERABILITY": "seguridad", "SECURITY": "seguridad",
    "CODE_SMELL": "deuda", "MAINTAINABILITY": "deuda",
}


@dataclass
class ConfigSonar:
    tipo: str
    url: str
    token: str
    organizacion: str | None = None

    @classmethod
    def desde_env(cls, env: dict[str, str]) -> "ConfigSonar | None":
        """Devuelve None si falta configuración; el motivo lo informa `motivo_sin_config`."""
        if cls.motivo_sin_config(env):
            return None
        return cls(tipo=env["SONAR_TIPO"].strip().lower(), url=env["SONAR_URL"].rstrip("/"),
                   token=env["SONAR_TOKEN"], organizacion=env.get("SONAR_ORGANIZACION") or None)

    @staticmethod
    def motivo_sin_config(env: dict[str, str]) -> str | None:
        tipo = env.get("SONAR_TIPO", "").strip().lower()
        if tipo not in ("sonarqube", "sonarcloud"):
            return "SONAR_TIPO no está definido en .env (sonarqube o sonarcloud)"
        faltantes = [v for v in ("SONAR_URL", "SONAR_TOKEN") if not env.get(v)]
        if tipo == "sonarcloud" and not env.get("SONAR_ORGANIZACION"):
            faltantes.append("SONAR_ORGANIZACION")
        return f"faltan variables en .env: {', '.join(faltantes)}" if faltantes else None


class ClienteSonar:

    def __init__(self, config: ConfigSonar, sesion: requests.Session | None = None) -> None:
        self.config = config
        self.sesion = sesion or requests.Session()
        self.sesion.headers["Authorization"] = f"Bearer {config.token}"

    def _get(self, ruta: str, parametros: dict) -> dict:
        if self.config.tipo == "sonarcloud":
            parametros = {**parametros, "organization": self.config.organizacion}
        try:
            respuesta = self.sesion.get(f"{self.config.url}{ruta}", params=parametros, timeout=30)
        except requests.RequestException as error:
            raise ErrorRadiografia(f"No se pudo conectar con Sonar ({self.config.url}): {error}") from error
        if respuesta.status_code == 401:
            raise ErrorRadiografia("Sonar rechazó el token (401). Verificar SONAR_TOKEN.")
        if respuesta.status_code == 403:
            raise ErrorRadiografia("El token de Sonar no tiene permiso de lectura sobre el proyecto (403).")
        if respuesta.status_code == 404:
            clave = next((parametros[p] for p in ("component", "projectKey", "project", "components", "componentKeys")
                          if p in parametros), "")
            raise ProyectoNoEncontrado(clave)
        if respuesta.status_code >= 400:
            raise ErrorRadiografia(f"Sonar respondió {respuesta.status_code} en {ruta}: {respuesta.text[:300]}")
        return respuesta.json()

    # --- Consultas ---------------------------------------------------------------------------

    def ultimo_analisis(self, proyecto: str) -> dict | None:
        datos = self._get("/api/project_analyses/search", {"project": proyecto, "ps": 1})
        analisis = datos.get("analyses") or []
        if not analisis:
            return None
        return {"fecha": analisis[0].get("date"), "commit": analisis[0].get("revision")}

    def quality_gate(self, proyecto: str) -> dict:
        estado = self._get("/api/qualitygates/project_status", {"projectKey": proyecto}).get("projectStatus", {})
        return {
            "estado": estado.get("status", "NONE"),
            "condiciones_fallidas": [
                {"metrica": c.get("metricKey"), "valor": c.get("actualValue"), "umbral": c.get("errorThreshold")}
                for c in estado.get("conditions", []) if c.get("status") == "ERROR"
            ],
        }

    def metricas(self, proyecto: str) -> dict[str, str]:
        datos = self._get("/api/measures/component", {"component": proyecto, "metricKeys": ",".join(METRICAS)})
        return {m["metric"]: m.get("value") for m in datos.get("component", {}).get("measures", [])}

    def issues(self, proyecto: str) -> tuple[list[dict], int]:
        """Issues abiertos, normalizados. Devuelve (issues, total en el servidor)."""
        issues: list[dict] = []
        pagina, total = 1, 0
        while len(issues) < LIMITE_ISSUES:
            # SonarQube reciente usa `components`; SonarCloud mantiene `componentKeys`.
            parametro = "componentKeys" if self.config.tipo == "sonarcloud" else "components"
            datos = self._get("/api/issues/search", {
                parametro: proyecto, "resolved": "false", "ps": TAMANO_PAGINA, "p": pagina,
            })
            total = datos.get("paging", {}).get("total", datos.get("total", 0))
            lote = datos.get("issues", [])
            issues += [normalizar_issue(i, proyecto) for i in lote]
            if not lote or len(issues) >= total:
                break
            pagina += 1
        return issues, total

    def hotspots(self, proyecto: str) -> list[dict]:
        parametro = "projectKey" if self.config.tipo == "sonarcloud" else "project"
        datos = self._get("/api/hotspots/search", {parametro: proyecto, "status": "TO_REVIEW", "ps": TAMANO_PAGINA})
        return [
            {
                "clave": h.get("key"),
                "regla": h.get("ruleKey"),
                "mensaje": h.get("message", ""),
                "archivo": _archivo(h.get("component", ""), proyecto),
                "linea": h.get("line"),
                "probabilidad": h.get("vulnerabilityProbability"),
            }
            for h in datos.get("hotspots", [])
        ]


class ProyectoNoEncontrado(ErrorRadiografia):
    def __init__(self, proyecto: str) -> None:
        super().__init__(f"El proyecto '{proyecto}' no existe en Sonar o el token no puede verlo.")


def _archivo(componente: str, proyecto: str) -> str | None:
    prefijo = f"{proyecto}:"
    return componente[len(prefijo):] if componente.startswith(prefijo) else None


def normalizar_issue(issue: dict, proyecto: str) -> dict:
    """Unifica el formato nuevo (impacts) y el anterior (type y severity)."""
    impactos = issue.get("impacts") or []
    if impactos:
        principal = min(impactos, key=lambda i: ORDEN_SEVERIDAD.index(SEVERIDADES.get(i.get("severity"), "baja")))
        severidad = SEVERIDADES.get(principal.get("severity"), "baja")
        categoria = CATEGORIAS.get(principal.get("softwareQuality"), "deuda")
    else:
        severidad = SEVERIDADES.get(issue.get("severity"), "baja")
        categoria = CATEGORIAS.get(issue.get("type"), "deuda")
    return {
        "clave": issue.get("key"),
        "regla": issue.get("rule"),
        "mensaje": issue.get("message", ""),
        "archivo": _archivo(issue.get("component", ""), proyecto),
        "linea": issue.get("line"),
        "severidad": severidad,
        "categoria": categoria,
    }


def recolectar(cliente: ClienteSonar, proyecto: str) -> dict:
    """Todo lo que el harness usa de un proyecto. Lanza ProyectoNoEncontrado si no existe."""
    issues, total = cliente.issues(proyecto)
    return {
        "proyecto": proyecto,
        "analisis": cliente.ultimo_analisis(proyecto),
        "quality_gate": cliente.quality_gate(proyecto),
        "metricas": cliente.metricas(proyecto),
        "issues": issues,
        "issues_total": total,
        "issues_truncados": total > len(issues),
        "hotspots": cliente.hotspots(proyecto),
    }
