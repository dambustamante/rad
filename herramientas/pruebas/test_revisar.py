"""Pruebas de la parte automática de /revisar, con un Sonar simulado."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hallazgos  # noqa: E402
import productos  # noqa: E402
import revisar  # noqa: E402
import sonar  # noqa: E402
from comun import RAIZ  # noqa: E402
from test_productos import crear_repo  # noqa: E402
from test_sync_arquitectura import commit  # noqa: E402

SECRETO_FALSO = "AKIAQYLPMN5HHHFPZAM2"

README = """\
# fraude-core

## Resumen y propósito

Servicio de evaluación.

## Cómo se ejecuta en local

```sh
make build
```
"""

CONTROLADOR = """\
@RestController
public class EvaluacionController {
    public void evaluar() {
        System.out.println("evaluando");
    }
}
"""

C4_CONTEXTO = """\
# Contexto

```mermaid
C4Context
    title Contexto de fraude-core
    Person(analista, "Analista", "Revisa alertas")
    System(core, "fraude-core", "Evalúa transacciones")
    Rel(analista, core, "Consulta alertas", "HTTPS")
```
"""

C4_CONTENEDORES = """\
# Contenedores

```mermaid
C4Container
    title Contenedores de fraude-core
    Container(api, "API", "Java 21, Spring Boot 3", "Expone la evaluación")
    ContainerDb(bd, "Base de datos", "", "Guarda evaluaciones")
    Rel(api, bd, "Lee y escribe")
```
"""


class RespuestaFalsa:
    def __init__(self, estado: int, datos: dict) -> None:
        self.status_code, self._datos, self.text = estado, datos, json.dumps(datos)

    def json(self) -> dict:
        return self._datos


class SesionSonarFalsa:
    """Responde como SonarQube reciente para el proyecto banco_fraude-core."""

    def __init__(self) -> None:
        self.headers: dict = {}
        self.llamadas: list[tuple[str, dict]] = []

    def get(self, url: str, params: dict, timeout: int) -> RespuestaFalsa:
        ruta = url.removeprefix("http://sonar")
        self.llamadas.append((ruta, params))
        if "banco_fraude-core" not in params.values():
            return RespuestaFalsa(404, {"errors": [{"msg": "Component not found"}]})
        if ruta == "/api/project_analyses/search":
            return RespuestaFalsa(200, {"analyses": [{"date": "2026-10-10T10:00:00+0000", "revision": "0" * 40}]})
        if ruta == "/api/qualitygates/project_status":
            return RespuestaFalsa(200, {"projectStatus": {"status": "ERROR", "conditions": [
                {"status": "ERROR", "metricKey": "new_coverage", "actualValue": "40.0", "errorThreshold": "80"}]}})
        if ruta == "/api/measures/component":
            return RespuestaFalsa(200, {"component": {"measures": [{"metric": "coverage", "value": "52.3"},
                                                                    {"metric": "ncloc", "value": "1200"}]}})
        if ruta == "/api/issues/search":
            return RespuestaFalsa(200, {"paging": {"total": 3}, "issues": [
                {"key": "AX-1", "rule": "java:S2095", "message": "Cerrar el recurso", "component": "banco_fraude-core:src/main/java/Evaluacion.java",
                 "line": 10, "impacts": [{"softwareQuality": "RELIABILITY", "severity": "HIGH"}]},
                {"key": "AX-2", "rule": "java:S1128", "message": "Quitar import sin uso", "component": "banco_fraude-core:src/main/java/A.java",
                 "line": 1, "type": "CODE_SMELL", "severity": "MINOR"},
                {"key": "AX-3", "rule": "java:S1128", "message": "Quitar import sin uso", "component": "banco_fraude-core:src/main/java/B.java",
                 "line": 2, "type": "CODE_SMELL", "severity": "MINOR"},
            ]})
        if ruta == "/api/hotspots/search":
            return RespuestaFalsa(200, {"hotspots": [{"key": "H1", "ruleKey": "java:S5332", "message": "HTTP sin TLS",
                                                       "component": "banco_fraude-core:src/main/java/Cliente.java", "line": 5}]})
        return RespuestaFalsa(404, {})


class PruebaRevisar(unittest.TestCase):

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        base = Path(self.temporal.name)
        self.raiz = base / "raiz"
        (self.raiz / "productos").mkdir(parents=True)
        shutil.copytree(RAIZ / "equipo", self.raiz / "equipo", ignore=shutil.ignore_patterns("estado", "COHERENCIA.md", "INDICE.md"))

        self.core = base / "fraude-core"
        crear_repo(self.core, "main", {
            "README.md": README,
            "pom.xml": "<project></project>\n",
            "src/main/java/EvaluacionController.java": CONTROLADOR,
            "src/test/java/EvaluacionTest.java": "class EvaluacionTest { void t() { System.out.println(1); } }\n",
            "docs/arquitectura/diagrama.png": "imagen",
        })
        self.config = base / "fraude-config"
        crear_repo(self.config, "main", {"application-prod.properties": f"aws.key={SECRETO_FALSO}\n"})

        with contextlib.redirect_stdout(io.StringIO()):
            productos.crear(self.raiz, "motor-fraudes", None, "heredado")
            productos.main(["--raiz", str(self.raiz), "agregar", "--producto", "motor-fraudes", "--id", "fraude-core",
                            "--url", str(self.core), "--rama", "main", "--tipo", "propio", "--sonar", "banco_fraude-core"])
            productos.main(["--raiz", str(self.raiz), "agregar", "--producto", "motor-fraudes", "--id", "fraude-config",
                            "--url", str(self.config), "--rama", "main", "--tipo", "config"])
        self.sesion = SesionSonarFalsa()

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def revisar(self, con_sonar: bool = True) -> dict:
        cliente = sonar.ClienteSonar(sonar.ConfigSonar("sonarqube", "http://sonar", "token"), sesion=self.sesion)
        with contextlib.redirect_stdout(io.StringIO()):
            return revisar.revisar(self.raiz, "motor-fraudes", usar_sonar=con_sonar,
                                   cliente_sonar=cliente if con_sonar else None)

    def registro(self) -> dict:
        return hallazgos.cargar(self.raiz, "motor-fraudes")["hallazgos"]

    def abiertos(self, repo: str) -> dict[str, dict]:
        return {(h["criterio"] or h["fuente"]): h for h in self.registro().values() if h["repo"] == repo and h["estado"] == "abierto"}

    def test_linea_base_detecta_incumplimientos_y_sonar(self) -> None:
        resultado = self.revisar()
        core = self.abiertos("fraude-core")
        for criterio in ("EQ-006.1", "EQ-006.2", "EQ-006.4", "EQ-004.1", "EQ-007.1", "EQ-007.2", "EQ-003.1"):
            self.assertIn(criterio, core)
            self.assertEqual(core[criterio]["modo"], "propuesta", "los ADR-EQ en Propuesto no afectan el veredicto")
            self.assertTrue(core[criterio]["linea_base"])
        self.assertEqual(core["EQ-003.1"]["evidencia"][0]["archivo"], "src/main/java/EvaluacionController.java",
                         "la salida a consola en pruebas no cuenta")
        self.assertEqual(core["EQ-007.2"]["evidencia"][0]["linea"], 10)
        self.assertIn("Contexto de negocio y responsables", core["EQ-007.1"]["detalle"])

        self.assertEqual(core["sonar:quality-gate"]["severidad"], "alta")
        self.assertEqual(core["sonar:quality-gate"]["nivel"], 5, "Sonar es el nivel 5")
        self.assertEqual(core["EQ-006.1"]["nivel"], 3, "las decisiones del equipo son el nivel 3")
        self.assertEqual(core["sonar:java:S2095"]["evidencia"], [{"archivo": "src/main/java/Evaluacion.java", "linea": 10}])
        self.assertIn("2 issue(s) de la regla java:S1128", core["sonar:java:S1128"]["titulo"], "los issues menores se agrupan")
        self.assertIn("sonar:hotspots", core)

        revision = next(r for r in resultado["resultados"] if r["repo"] == "fraude-core")
        self.assertIn("Sonar analizó 000000000000", revision["sonar"]["desfase"])
        self.assertTrue((resultado["carpeta"] / "resumen.md").exists())
        self.assertTrue((resultado["carpeta"] / "crudo" / "fraude-core-sonar.json").exists())

        ficha = (self.raiz / "productos" / "motor-fraudes" / "as-is" / "fraude-core.md").read_text(encoding="utf-8")
        self.assertIn(revisar.MARCA_AUTOMATICO[0], ficha)
        self.assertIn("Quality gate: **ERROR**", ficha)
        self.assertIn("## Revisión de código", ficha)

    @unittest.skipUnless(shutil.which("gitleaks"), "gitleaks no está instalado")
    def test_secretos_tambien_en_repos_de_configuracion(self) -> None:
        self.revisar()
        config = self.abiertos("fraude-config")
        self.assertIn("EQ-001.1", config)
        self.assertEqual(config["EQ-001.1"]["origen"], "gitleaks")
        self.assertNotIn(SECRETO_FALSO, json.dumps(self.registro()), "el valor del secreto nunca se guarda")
        self.assertEqual(set(config), {"EQ-001.1"}, "a un repo de configuración solo se le aplican los secretos")

    def test_reconoce_corregidos_reaparecidos_y_conserva_la_revision(self) -> None:
        self.revisar()
        ficha = self.raiz / "productos" / "motor-fraudes" / "as-is" / "fraude-core.md"
        ficha.write_text(revisar.reemplazar_bloque(ficha.read_text(encoding="utf-8"), revisar.MARCA_REVISION,
                                                   "## Revisión de código\n\nTexto de la revisión."), encoding="utf-8")

        segunda = self.revisar()
        resumen = next(r for r in segunda["resultados"] if r["repo"] == "fraude-core")["resumen"]
        self.assertEqual(resumen["nuevos"], [], "una segunda revisión sin cambios no duplica hallazgos")
        self.assertIn("Texto de la revisión.", ficha.read_text(encoding="utf-8"), "la sección de revisión se conserva")

        (self.core / "docs" / "arquitectura" / "c4-contexto.md").write_text(C4_CONTEXTO, encoding="utf-8")
        (self.core / "docs" / "arquitectura" / "c4-contenedores.md").write_text(C4_CONTENEDORES, encoding="utf-8")
        commit(self.core, "Agrega C4")
        self.revisar()
        core = self.abiertos("fraude-core")
        self.assertNotIn("EQ-006.1", core)
        self.assertNotIn("EQ-006.2", core)
        problemas = [h["detalle"] for h in self.registro().values() if h["criterio"] == "EQ-006.3" and h["estado"] == "abierto"]
        self.assertEqual(len(problemas), 2, "contenedor sin tecnología y relación sin protocolo")

        (self.core / "docs" / "arquitectura" / "c4-contexto.md").unlink()
        commit(self.core, "Borra el contexto")
        self.revisar()
        reabierto = self.abiertos("fraude-core")["EQ-006.1"]
        self.assertTrue(reabierto["reaparecido"])

    def test_sin_sonar_no_cierra_hallazgos_de_sonar(self) -> None:
        self.revisar()
        resultado = self.revisar(con_sonar=False)
        revision = next(r for r in resultado["resultados"] if r["repo"] == "fraude-core")
        self.assertEqual(revision["sonar"]["estado"], "NO DETERMINADO")
        self.assertIn("sonar:quality-gate", self.abiertos("fraude-core"), "si Sonar no corre, sus hallazgos siguen abiertos")

    def test_criterio_suspendido_por_coherencia(self) -> None:
        (self.raiz / "equipo" / "estado").mkdir(parents=True, exist_ok=True)
        (self.raiz / "equipo" / "estado" / "coherencia.json").write_text(json.dumps({"suspendidos": {"ADR-EQ-006": ["EQ-006.1"]}}), encoding="utf-8")
        resultado = self.revisar()
        self.assertNotIn("EQ-006.1", self.abiertos("fraude-core"))
        revision = next(r for r in resultado["resultados"] if r["repo"] == "fraude-core")
        estado = next(v for v in revision["verificaciones"] if v["criterio"] == "EQ-006.1")
        self.assertEqual(estado["resultado"], "NO APLICA")
        self.assertIn("suspendido", estado["motivo"])


if __name__ == "__main__":
    unittest.main()
