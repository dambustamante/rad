"""Pruebas del harness de producto: creación, contenido generado, regeneración, ADR de producto y herramientas del dev."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import adr  # noqa: E402
import estado  # noqa: E402
import guardia  # noqa: E402
import hallazgos  # noqa: E402
import harness  # noqa: E402
import revision  # noqa: E402
import test_revision  # noqa: E402
from comun import carpeta_decisiones_producto, git  # noqa: E402

GIT_PRUEBA = {"GIT_AUTHOR_NAME": "Prueba", "GIT_AUTHOR_EMAIL": "prueba@example.com",
              "GIT_COMMITTER_NAME": "Prueba", "GIT_COMMITTER_EMAIL": "prueba@example.com"}


def cargar(ruta: Path, nombre: str):
    especificacion = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


class PruebaHarness(unittest.TestCase):
    setUp_base = test_revision.PruebaRevision.setUp
    tearDown = test_revision.PruebaRevision.tearDown

    def setUp(self) -> None:
        self.setUp_base()
        parche = mock.patch.dict(os.environ, GIT_PRUEBA)
        parche.start()
        self.addCleanup(parche.stop)
        import yaml
        carpeta = self.automatica["carpeta"] / "revision"
        carpeta.mkdir(parents=True, exist_ok=True)
        claves = [e["criterio"] or e["fuente"] for e in revision.lista_de_control(self.raiz, "propio", "motor-fraudes", "fraude-core")]
        hallazgo = {"fuente": "decisiones:ADR-010", "categoria": "incumplimiento", "severidad": "alta",
                    "titulo": "Llamada sin timeout", "detalle": "El cliente no define timeout.",
                    "evidencia": ["src/main/java/EvaluacionController.java:4"], "fragmento": 'System.out.println("evaluando");',
                    "cita_documento": "Ninguna llamada externa sin timeout explícito"}
        componente = {"nombre": "Buró de crédito", "tipo": "integracion", "tecnologia": "HTTPS", "detalle": "BURO_URL",
                      "direccion": "saliente", "evidencia": ["src/main/java/EvaluacionController.java:3"]}
        (carpeta / "fraude-core-lote.yaml").write_text(yaml.safe_dump(
            {"cumple": [c for c in claves if c != "decisiones:ADR-010"], "hallazgos": [hallazgo], "componentes": [componente]},
            allow_unicode=True), encoding="utf-8")
        (carpeta / "fraude-core-asis.md").write_text(test_revision.AS_IS.replace(
            "## Propósito\n\n[inferencia] Contenido de prueba.", "## Propósito\n\n[hecho] Evalúa transacciones con riesgo de fraude."),
            encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(revision.main(["--raiz", str(self.raiz), "cerrar", "motor-fraudes", "fraude-core"]), 0)
        self.adr_previo = adr.nuevo(self.raiz, "motor-fraudes", "decision", "Latencia de evaluación")
        self.destino = harness.ruta(self.raiz, "motor-fraudes")

    def commits(self) -> int:
        return int(git("rev-list", "--count", "HEAD", cwd=self.destino))

    def test_crear_genera_estructura_y_mueve_los_adr(self) -> None:
        pasos = " ".join(estado.que_sigue(estado.revisar_estado(self.raiz)))
        self.assertIn("sin harness para el equipo: `/producto motor-fraudes harness`", pasos)
        r = harness.crear(self.raiz, "motor-fraudes")
        self.assertEqual(r["movidos"], [self.adr_previo.name])
        self.assertFalse((self.raiz / "productos" / "motor-fraudes" / "decisiones").exists(), "los ADR dejan radiografia")
        for archivo in ("AGENTS.md", "README.md", "Makefile", ".gitignore", "repos.json", "GENERADO.json", ".cursor/hooks.json",
                        "herramientas/harness.py", "herramientas/guardia.py", "decisiones/README.md", "decisiones/plantilla.md",
                        "decisiones/INDICE.md", f"decisiones/{self.adr_previo.name}"):
            self.assertTrue((self.destino / archivo).exists(), archivo)
        self.assertIn("harness-motor-fraudes — contrato de trabajo", (self.destino / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn("ADR-MF-NNN", (self.destino / "decisiones" / "plantilla.md").read_text(encoding="utf-8"))
        self.assertIn("code/", (self.destino / ".gitignore").read_text(encoding="utf-8"))
        self.assertEqual(self.commits(), 1)
        self.assertEqual(carpeta_decisiones_producto(self.raiz, "motor-fraudes"), self.destino / "decisiones")

        decisiones = (self.destino / ".cursor/rules/generado/decisiones.mdc").read_text(encoding="utf-8")
        self.assertIn("alwaysApply: true", decisiones)
        self.assertIn("- `decisiones:ADR-010` Timeouts obligatorios: Ninguna llamada externa sin timeout explícito.", decisiones)
        self.assertIn("### ADR-EQ-002 Integraciones resilientes con política de degradación explícita (propuesta)", decisiones)
        self.assertIn("- `EQ-002.1` (alta):", decisiones)
        self.assertNotIn("EQ-009.2", decisiones, "los criterios de revisión de la historia no son para el código")
        repo = (self.destino / ".cursor/rules/generado/repo-fraude-core.mdc").read_text(encoding="utf-8")
        self.assertIn("globs: code/fraude-core/**", repo)
        self.assertIn("**Propósito:** [hecho] Evalúa transacciones con riesgo de fraude.", repo)
        self.assertIn("| Buró de crédito | integracion | HTTPS | BURO_URL | saliente |", repo)
        self.assertIn("decisiones:ADR-010 · alta: Llamada sin timeout · `src/main/java/EvaluacionController.java:4`", repo)
        repos = json.loads((self.destino / "repos.json").read_text(encoding="utf-8"))
        self.assertEqual(repos["repos"][0]["id"], "fraude-core")
        with self.assertRaises(Exception):
            harness.crear(self.raiz, "motor-fraudes")

    def test_regenerar_solo_si_cambia_y_adr_en_el_harness(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        self.assertFalse(harness.generar(self.raiz, "motor-fraudes")["commit"], "sin cambios no hay commit")
        registro = hallazgos.cargar(self.raiz, "motor-fraudes")
        for h in registro["hallazgos"].values():
            if h["fuente"] == "decisiones:ADR-010":
                h["triaje"] = {"decision": "falso-positivo", "motivo": "prueba", "vence": None, "fecha": "2026-10-29"}
        hallazgos.guardar(self.raiz, "motor-fraudes", registro)
        r = harness.generar(self.raiz, "motor-fraudes")
        self.assertTrue(r["commit"])
        self.assertEqual(r["cambiados"], [".cursor/rules/generado/repo-fraude-core.mdc"])
        self.assertEqual(r["version"], 2)
        self.assertNotIn("Llamada sin timeout", (self.destino / ".cursor/rules/generado/repo-fraude-core.mdc").read_text(encoding="utf-8"))

        nuevo = adr.nuevo(self.raiz, "motor-fraudes", "decision", "Reintentos del buró")
        self.assertEqual(nuevo.parent, self.destino / "decisiones", "los ADR nuevos nacen en el harness")
        self.assertTrue(nuevo.name.startswith("ADR-MF-002-"))
        self.assertTrue(harness.guardar(self.raiz, "motor-fraudes", "Propone ADR-MF-002"))
        self.assertEqual(self.commits(), 3)
        e = harness.estado(self.raiz, "motor-fraudes")
        self.assertEqual((e["remoto"], e["sin_subir"]), (False, 3))
        self.assertIn("el harness tiene 3 commit(s) sin subir", " ".join(estado.que_sigue(estado.revisar_estado(self.raiz))))
        self.assertEqual(harness.traer(self.raiz, "motor-fraudes"), "sin remoto: nada que traer")

    def test_herramientas_del_dev(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        salida = subprocess.run([sys.executable, str(self.destino / "herramientas" / "harness.py"), "code"],
                                capture_output=True, text=True)
        self.assertEqual(salida.returncode, 0, salida.stdout + salida.stderr)
        self.assertTrue((self.destino / "code" / "fraude-core" / ".git").exists())
        salida = subprocess.run([sys.executable, str(self.destino / "herramientas" / "harness.py"), "code"],
                                capture_output=True, text=True)
        self.assertIn("fraude-core: actualizado · rama main", salida.stdout)
        self.assertEqual(git("status", "--porcelain", cwd=self.destino), "", "code/ queda fuera de git del harness")

        guardia_dev = cargar(self.destino / "herramientas" / "guardia.py", "guardia_dev")
        casos = {"git -C code/fraude-core push origin main": "deny", "git push --force origin feature/x": "deny",
                 "git push origin +feature/x": "deny", "glab mr merge 12": "deny",
                 "git -C code/fraude-core push -u origin feature/FRAUD-123": "allow",
                 "git -C code/fraude-core commit -m 'Agrega timeout'": "allow"}
        for comando, esperado in casos.items():
            self.assertEqual(guardia_dev.evaluar(comando)[0], esperado, comando)
        self.assertEqual(guardia.evaluar("git -C productos/motor-fraudes/harness push origin main")[0], "ask",
                         "en radiografia, el push del harness pide aprobación")
        self.assertEqual(guardia.evaluar("git -C productos/motor-fraudes/harness commit -m x")[0], "allow")


if __name__ == "__main__":
    unittest.main()
