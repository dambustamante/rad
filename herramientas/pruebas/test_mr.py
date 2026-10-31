"""Pruebas de la revisión de MR: bandeja, cambios sensibles, contraste con /listo, deuda declarada y ADR del harness."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import estado  # noqa: E402
import hallazgos  # noqa: E402
import harness  # noqa: E402
import jira  # noqa: E402
import mr  # noqa: E402
import test_rama  # noqa: E402
from comun import git  # noqa: E402
from test_harness import GIT_PRUEBA  # noqa: E402
from test_productos import ejecutar  # noqa: E402
from test_sync_arquitectura import commit  # noqa: E402

PRUEBA_DEBILITADA = """\
class BuroClientTest {
    @Disabled
    @Test
    void responde() { }
}
"""


class ClienteMR(test_rama.ClienteFalso):
    def __init__(self, mrs: list[dict]) -> None:
        super().__init__(mrs[0] if mrs else None)
        self.mrs = mrs

    def mr_de_rama(self, proyecto: str, rama_: str) -> dict | None:
        return next((m for m in self.mrs if m["rama"] == rama_), None)

    def mrs_abiertos(self, proyecto: str) -> list[dict]:
        return self.mrs


class PruebaMR(unittest.TestCase):
    setUp_rama = test_rama.PruebaRama.setUp
    setUp_base = test_rama.PruebaRama.setUp_base
    tearDown = test_rama.PruebaRama.tearDown

    def setUp(self) -> None:
        self.setUp_rama()
        parche = mock.patch.dict(os.environ, GIT_PRUEBA)
        parche.start()
        self.addCleanup(parche.stop)
        parche = mock.patch("mr.proyecto_de", return_value="banco/fraude-core")
        parche.start()
        self.addCleanup(parche.stop)
        ejecutar("git", "checkout", "--quiet", "feature/buro", cwd=self.core)
        (self.core / "src/test/java").mkdir(parents=True)
        (self.core / "src/test/java/BuroClientTest.java").write_text(PRUEBA_DEBILITADA, encoding="utf-8")
        (self.core / "src/main/java/BuroClient.java").write_text(
            test_rama.CLIENTE_BURO.replace("return restTemplate", "// NOSONAR\n        return restTemplate"), encoding="utf-8")
        self.cabeza = commit(self.core, "Prueba del cliente")
        ejecutar("git", "checkout", "--quiet", "main", cwd=self.core)

    def mr(self, registro: dict | None) -> dict:
        descripcion = "Agrega el cliente." + (f"\n<!-- radiografia:listo {json.dumps(registro)} -->" if registro else "")
        return {**test_rama.MR, "numero": 7, "rama": "feature/buro", "commit": self.cabeza, "descripcion": descripcion,
                "revisores": ["tl"]}

    def registro(self, **cambios) -> dict:
        return {"clave": "FRAUD-123", "repo": "fraude-core", "commit": self.cabeza, "harness": None, "verificador": None,
                "secretos": 0, "senales": {"consola": 0}, "criterios": {"1": "fraude-core:src/test/java/BuroClientTest.java:4"},
                "deuda": [{"tipo": "operativa", "descripcion": "La carga de listas sigue siendo manual.", "evidencia": None}],
                **cambios}

    def test_bandeja_y_estado_de_listo(self) -> None:
        cliente = ClienteMR([self.mr(self.registro()), {**self.mr(None), "numero": 8},
                             {**self.mr(self.registro(commit="0" * 40)), "numero": 9}])
        filas = mr.bandeja(self.raiz, cliente=cliente)
        self.assertEqual([(f["numero"], f["listo"]) for f in filas], [(8, "sin /listo"), (9, "desactualizado"), (7, "al día")],
                         "primero lo que necesita más atención")

    def test_revisar_detecta_sensibles_contrasta_y_registra_deuda(self) -> None:
        cliente = ClienteMR([self.mr(self.registro())])
        r = mr.revisar(self.raiz, "motor-fraudes", "fraude-core", 7, cliente)
        self.assertEqual(r["sensibles"]["Pruebas debilitadas"], ["src/test/java/BuroClientTest.java:2"])
        self.assertIn("src/main/java/BuroClient.java:4", r["sensibles"]["Controles apagados"])
        self.assertIn("Criterio 1: la prueba `src/test/java/BuroClientTest.java:4` está deshabilitada.", r["contraste"])
        self.assertIn("/listo declaró 0 salidas a consola; radiografia encontró EQ-003.1 en archivos del cambio.", r["contraste"])
        paquete = r["paquete"].read_text(encoding="utf-8")
        self.assertIn("## Cambios sensibles (foco de la revisión)", paquete)
        self.assertIn("## Contraste con /listo", paquete)
        self.assertEqual(r["deuda"], 1)

        pasos = " ".join(estado.que_sigue(estado.revisar_estado(self.raiz)))
        self.assertIn("FRAUD-123 declaró deuda en /listo y no tiene Tarea: `/crear motor-fraudes tarea --deuda FRAUD-123`", pasos)
        borrador, contexto = jira.nueva(self.raiz, "motor-fraudes", "tarea", None, "Automatizar la carga de listas", [], [], None,
                                        deuda="FRAUD-123")
        self.assertIn("Operativa: La carga de listas sigue siendo manual.", contexto.read_text(encoding="utf-8"))
        datos, _ = jira.leer_borrador(borrador)
        self.assertEqual((datos["tipo"], datos["deuda_de"]), ("Deuda Operativa", "FRAUD-123"))

    def test_sin_listo_y_registro_alterado(self) -> None:
        r = mr.revisar(self.raiz, "motor-fraudes", "fraude-core", 7, ClienteMR([self.mr(None)]))
        self.assertEqual(r["contraste"], ["El MR no tiene registro de /listo: revisión completa sin declaración."])
        alterado = {**self.mr(None), "descripcion": "<!-- radiografia:listo {no es json} -->"}
        self.assertEqual(mr.revisar(self.raiz, "motor-fraudes", "fraude-core", 7, ClienteMR([alterado]))["contraste"],
                         ["El registro de /listo del MR está alterado o mal formado."])

    def test_coherencia_del_adr_propuesto_en_el_harness(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        copia = harness.ruta(self.raiz, "motor-fraudes")
        remoto = Path(self.temporal.name) / "harness-remoto.git"
        subprocess.run(["git", "init", "--quiet", "--bare", str(remoto)], check=True)
        git("remote", "add", "origin", str(remoto), cwd=copia)
        git("push", "--quiet", "-u", "origin", "main", cwd=copia)
        trabajo = Path(self.temporal.name) / "harness-dev"
        subprocess.run(["git", "clone", "--quiet", str(remoto), str(trabajo)], check=True)
        git("switch", "--quiet", "-c", "spike/colas", cwd=trabajo)
        subprocess.run([sys.executable, str(trabajo / "herramientas" / "harness.py"), "adr", "--titulo", "Reintentos en cada cliente"],
                       check=True, capture_output=True)
        nuevo = next((trabajo / "decisiones").glob("ADR-MF-001-*.md"))
        nuevo.write_text(nuevo.read_text(encoding="utf-8").replace("> <Una o dos frases que resumen la decisión.>",
                                                                   "> Cada cliente reintenta tres veces."), encoding="utf-8")
        git("add", "-A", cwd=trabajo)
        git("commit", "--quiet", "-m", "Propone ADR-MF-001", cwd=trabajo)
        git("push", "--quiet", "origin", "spike/colas", cwd=trabajo)
        cliente = ClienteMR([{**test_rama.MR, "numero": 3, "rama": "spike/colas", "commit": git("rev-parse", "HEAD", cwd=trabajo)}])
        r = mr.adr(self.raiz, "motor-fraudes", 3, cliente)
        self.assertEqual(r["cambiados"], [nuevo.name])
        self.assertGreater(r["pares"], 0, "el ADR propuesto se compara con arquitectura y con el equipo antes de aprobarlo")
        self.assertIn("ADR-MF-001", r["validacion"])
        self.assertFalse((copia / "decisiones" / nuevo.name).exists(), "la copia principal del harness no se toca")


if __name__ == "__main__":
    unittest.main()
