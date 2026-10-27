"""Pruebas de fuentes_arquitectura: inspección, alta y baja de fuentes en harness.yaml."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fuentes_arquitectura  # noqa: E402
import sync_arquitectura  # noqa: E402
from test_sync_arquitectura import ADR_ESTADO_DESCONOCIDO, ADR_VIGENTE, commit, ejecutar  # noqa: E402

HARNESS = """\
# Comentario de cabecera que debe conservarse.
version: 1

arquitectura:
  # Comentario de las fuentes que debe conservarse.
  fuentes: []

  estados:
    vigente: [Aprobado]
    pendiente: [Propuesto]
    no_vigente: [Reemplazado]
"""

ESTANDAR = """\
# Estándar de APIs REST

## 1. Objetivo

Definir cómo se diseñan las APIs.
"""


class PruebaFuentesArquitectura(unittest.TestCase):

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        base = Path(self.temporal.name)
        self.origen = base / "arquitectura-docs"
        self.raiz = base / "raiz"
        # ADR en formato carpeta (0003-titulo/index.md) y en formato archivo, más un estándar.
        (self.origen / "docs" / "adrs" / "0003-adopcion-cursor").mkdir(parents=True)
        (self.origen / "docs" / "estandares").mkdir(parents=True)
        ejecutar("git", "init", "--quiet", "-b", "main", cwd=self.origen)
        (self.origen / "docs" / "adrs" / "index.md").write_text("# Decision records\n", encoding="utf-8")
        (self.origen / "docs" / "adrs" / "0003-adopcion-cursor" / "index.md").write_text(ADR_VIGENTE, encoding="utf-8")
        (self.origen / "docs" / "adrs" / "0002-baseline-java.md").write_text(ADR_ESTADO_DESCONOCIDO, encoding="utf-8")
        (self.origen / "docs" / "estandares" / "api-rest.md").write_text(ESTANDAR, encoding="utf-8")
        (self.origen / "README.md").write_text("# Arquitectura\n", encoding="utf-8")
        commit(self.origen, "Documentos de arquitectura")

        self.raiz.mkdir()
        (self.raiz / "harness.yaml").write_text(HARNESS, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def ejecutar(self, *argumentos: str) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = fuentes_arquitectura.main(["--raiz", str(self.raiz), *argumentos])
        return codigo, salida.getvalue()

    def test_inspeccionar_propone_rama_y_carpetas(self) -> None:
        codigo, salida = self.ejecutar("inspeccionar", str(self.origen))
        self.assertEqual(codigo, 0, salida)
        resultado = json.loads(salida)
        self.assertEqual(resultado["rama_por_defecto"], "main")
        self.assertEqual(resultado["nombre_repositorio"], "arquitectura-docs")
        self.assertEqual(resultado["ruta_adr_sugerida"], "docs/adrs")
        carpetas = {c["ruta"]: c for c in resultado["carpetas"]}
        self.assertEqual(carpetas["docs/adrs"]["adr"], 2)
        self.assertEqual(carpetas["docs/estandares"]["documentos"], 1)
        self.assertEqual(carpetas["docs/estandares"]["adr"], 0)

    def test_agregar_conserva_comentarios_y_permite_sincronizar(self) -> None:
        codigo, salida = self.ejecutar("agregar", "--id", "decisiones", "--url", str(self.origen),
                                       "--ref", "main", "--ruta", "docs/adrs", "--tipo", "adr")
        self.assertEqual(codigo, 0, salida)
        codigo, salida = self.ejecutar("agregar", "--id", "estandares", "--url", str(self.origen),
                                       "--ref", "main", "--ruta", "docs/estandares", "--tipo", "estandar",
                                       "--estado-por-defecto", "vigente")
        self.assertEqual(codigo, 0, salida)

        texto = (self.raiz / "harness.yaml").read_text(encoding="utf-8")
        self.assertIn("# Comentario de cabecera que debe conservarse.", texto)
        self.assertIn("# Comentario de las fuentes que debe conservarse.", texto)
        self.assertIn("estado_por_defecto: vigente", texto)

        salida_sync = io.StringIO()
        with contextlib.redirect_stdout(salida_sync):
            codigo = sync_arquitectura.main(["--raiz", str(self.raiz)])
        self.assertEqual(codigo, 0, salida_sync.getvalue())
        indice = json.loads((self.raiz / "arquitectura" / "indice.json").read_text(encoding="utf-8"))
        documentos = {d["id"]: d for d in indice["documentos"]}
        self.assertEqual(set(documentos), {"ADR-002", "ADR-003", "api-rest"}, "la portada index.md no se indexa")
        self.assertEqual(documentos["ADR-003"]["vigencia"], "vigente", "ADR en formato carpeta con index.md")
        self.assertEqual(documentos["api-rest"]["vigencia"], "vigente", "estándar sin Estado con estado_por_defecto")

    def test_agregar_rechaza_ruta_inexistente_y_duplicados(self) -> None:
        codigo, salida = self.ejecutar("agregar", "--id", "x", "--url", str(self.origen),
                                       "--ref", "main", "--ruta", "no-existe", "--tipo", "adr")
        self.assertEqual(codigo, 1)
        self.assertIn("La ruta 'no-existe' no existe", salida)

        codigo, salida = self.ejecutar("agregar", "--id", "x", "--url", str(self.origen),
                                       "--ref", "rama-inexistente", "--ruta", "docs/adrs", "--tipo", "adr")
        self.assertEqual(codigo, 1)
        self.assertIn("La ref 'rama-inexistente' no existe", salida)

        self.ejecutar("agregar", "--id", "x", "--url", str(self.origen), "--ref", "main", "--ruta", "docs/adrs", "--tipo", "adr")
        codigo, salida = self.ejecutar("agregar", "--id", "x", "--url", str(self.origen),
                                       "--ref", "main", "--ruta", "docs/estandares", "--tipo", "estandar")
        self.assertEqual(codigo, 1)
        self.assertIn("Ya existe una fuente con id 'x'", salida)

        codigo, salida = self.ejecutar("agregar", "--id", "y", "--url", str(self.origen),
                                       "--ref", "main", "--ruta", "docs/adrs", "--tipo", "adr")
        self.assertEqual(codigo, 1)
        self.assertIn("ya está declarada como fuente", salida)

    def test_url_inaccesible(self) -> None:
        codigo, salida = self.ejecutar("inspeccionar", str(self.raiz / "no-existe"))
        self.assertEqual(codigo, 1)
        self.assertIn("No se pudo acceder", salida)

    def test_retirar_y_listar(self) -> None:
        self.ejecutar("agregar", "--id", "decisiones", "--url", str(self.origen), "--ref", "main",
                      "--ruta", "docs/adrs", "--tipo", "adr")
        codigo, salida = self.ejecutar("listar")
        self.assertEqual([f["id"] for f in json.loads(salida)], ["decisiones"])

        codigo, salida = self.ejecutar("retirar", "--id", "decisiones")
        self.assertEqual(codigo, 0, salida)
        codigo, salida = self.ejecutar("listar")
        self.assertEqual(json.loads(salida), [])
        self.assertIn("fuentes: []", (self.raiz / "harness.yaml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
