"""Pruebas de /estado: qué sigue según el estado de arquitectura y de los productos."""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import estado  # noqa: E402
import test_revision  # noqa: E402


class PruebaEstado(unittest.TestCase):
    """Reutiliza la preparación de la revisión: arquitectura sincronizada y un repositorio con parte automática."""

    setUp = test_revision.PruebaRevision.setUp
    tearDown = test_revision.PruebaRevision.tearDown
    ejecutar = test_revision.PruebaRevision.ejecutar
    hallazgo = test_revision.PruebaRevision.hallazgo
    completar = test_revision.PruebaRevision.completar

    def test_sugiere_revisar_y_despues_triar(self) -> None:
        pasos = estado.que_sigue(estado.revisar_estado(self.raiz))
        self.assertTrue(any("1 repositorio(s) por revisar (fraude-core): `/revisar motor-fraudes`" in p for p in pasos), pasos)
        self.assertTrue(any("`/triar motor-fraudes`" in p for p in pasos), "la parte automática ya dejó hallazgos por triar")
        self.assertTrue(any("Coherencia con pares sin evaluar" in p for p in pasos), "los ADR-EQ todavía no se compararon")

        self.completar()
        self.ejecutar("cerrar", "motor-fraudes", "fraude-core")
        pasos = estado.que_sigue(estado.revisar_estado(self.raiz))
        self.assertTrue(any("consolidar el producto" in p for p in pasos), pasos)

    def test_sin_nada_configurado(self) -> None:
        vacio = self.raiz / "vacio"
        (vacio / "productos").mkdir(parents=True)
        (vacio / "harness.yaml").write_text("version: 1\n", encoding="utf-8")
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            estado.main(["--raiz", str(vacio)])
        self.assertIn("1. Registrar los repositorios de arquitectura: `/actualizar`.", salida.getvalue())


if __name__ == "__main__":
    unittest.main()
