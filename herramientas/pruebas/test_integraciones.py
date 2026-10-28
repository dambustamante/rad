"""Pruebas de las integraciones con terceros: ficha, validación, documentación y uso en la revisión."""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import integraciones  # noqa: E402
import proveedor  # noqa: E402
import revision  # noqa: E402
import test_revision  # noqa: E402

OPENAPI_BURO = "openapi: 3.0.3\ninfo: {title: API del buró, version: 3.2.0}\npaths: {}\n"


class PruebaIntegraciones(unittest.TestCase):

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporal.name)
        self.producto = self.raiz / "productos" / "motor-fraudes"
        self.producto.mkdir(parents=True)
        (self.producto / "producto.yaml").write_text(textwrap.dedent("""\
            nombre: motor-fraudes
            sigla: MF
            repos:
              - {id: fraude-core, url: x, rama: main, tipo: propio, estado: activo}
              - {id: fraude-backoffice, url: y, rama: main, tipo: propio, estado: activo}
            """), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def ficha(self, id_integracion: str, **cambios) -> Path:
        archivo = self.producto / "integraciones" / id_integracion / "integracion.yaml"
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        datos.update(cambios)
        archivo.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
        return archivo

    def test_nueva_y_validacion(self) -> None:
        integraciones.nueva(self.raiz, "motor-fraudes", "buro-credito", "Buró de crédito")
        with self.assertRaises(Exception):
            integraciones.nueva(self.raiz, "motor-fraudes", "buro-credito", "otra")
        errores, pendientes = integraciones.validar(self.raiz, "motor-fraudes", "buro-credito",
                                                    integraciones.leer_fichas(self.raiz, "motor-fraudes")["buro-credito"])
        self.assertEqual(errores, [], "la plantilla recién creada es válida, solo incompleta")
        self.assertIn("politica_ante_falla", pendientes)
        self.assertIn("repos", pendientes)

        self.ficha("buro-credito", politica_ante_falla="fail-closed", repos=["fraude-core", "no-existe"],
                   sla={"p95_ms": "rápido"}, contrato="openapi.yaml")
        errores, _ = integraciones.validar(self.raiz, "motor-fraudes", "buro-credito",
                                           integraciones.leer_fichas(self.raiz, "motor-fraudes")["buro-credito"])
        self.assertIn("una política fail-open o fail-closed necesita su justificación de negocio", errores)
        self.assertIn("repositorios que no existen en el producto: no-existe", errores)
        self.assertIn("sla.p95_ms debe ser un número o null", errores)
        self.assertIn("el contrato 'openapi.yaml' no existe en docs/", errores)

    def test_documentacion_busqueda_y_cita(self) -> None:
        integraciones.nueva(self.raiz, "motor-fraudes", "buro-credito", "Buró de crédito")
        docs = self.producto / "integraciones" / "buro-credito" / "docs"
        (docs / "openapi.yaml").write_text(OPENAPI_BURO, encoding="utf-8")
        (docs / "sla.md").write_text("# Acuerdo de servicio\n\nTiempo de respuesta p95 de 800 ms.\n", encoding="utf-8")
        resultado = proveedor.indexar(self.raiz, "motor-fraudes")
        documentos = resultado["integraciones"]["integraciones/buro-credito/docs"]["documentos"]
        self.assertEqual(documentos["openapi.yaml"]["contrato"]["titulo"], "API del buró")
        self.assertTrue((docs / "INDICE.md").exists())

        encontrados = proveedor.buscar(self.raiz, "motor-fraudes", "p95 800")
        self.assertEqual(encontrados[0]["archivo"], "integraciones/buro-credito/docs/sla.md")
        cita = revision.validar_cita_proveedor(self.raiz, "motor-fraudes", "integraciones/buro-credito/docs/sla.md",
                                               "Tiempo de respuesta p95 de 800 ms")
        self.assertEqual(cita["documento"], "integraciones/buro-credito/docs/sla.md")

        self.ficha("buro-credito", proveedor="Buró S.A.", protocolo="HTTPS/JSON", autenticacion="mTLS",
                   politica_ante_falla="fail-closed", justificacion="Sin buró no se evalúa el riesgo crediticio",
                   repos=["fraude-core"], sla={"disponibilidad": 99.9, "p95_ms": 800}, contrato="openapi.yaml")
        filas = integraciones.listar(self.raiz, "motor-fraudes")
        self.assertEqual((filas[0]["errores"], filas[0]["pendientes"]), ([], []))
        self.assertIn("✅ completa", (self.producto / "integraciones" / "INDICE.md").read_text(encoding="utf-8"))
        self.assertEqual([f["id"] for f in integraciones.para_repo(self.raiz, "motor-fraudes", "fraude-core")], ["buro-credito"])
        self.assertEqual(integraciones.para_repo(self.raiz, "motor-fraudes", "fraude-backoffice"), [],
                         "solo se muestra a los repositorios que la declaran")


class PruebaIntegracionesEnLaRevision(unittest.TestCase):
    setUp = test_revision.PruebaRevision.setUp
    tearDown = test_revision.PruebaRevision.tearDown
    ejecutar = test_revision.PruebaRevision.ejecutar

    def test_el_paquete_muestra_las_integraciones_del_repo(self) -> None:
        integraciones.nueva(self.raiz, "motor-fraudes", "buro-credito", "Buró de crédito")
        archivo = self.raiz / "productos" / "motor-fraudes" / "integraciones" / "buro-credito" / "integracion.yaml"
        archivo.write_text(archivo.read_text(encoding="utf-8").replace("p95_ms: null", "p95_ms: 800"), encoding="utf-8")
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            revision.main(["--raiz", str(self.raiz), "paquete", "motor-fraudes", "fraude-core"])
        paquete = (self.raiz / salida.getvalue().split("Paquete: ")[1].strip()).read_text(encoding="utf-8")
        self.assertIn("## Integraciones declaradas", paquete)
        self.assertIn("| `buro-credito` Buró de crédito | saliente |", paquete)
        self.assertIn("| 800 |", paquete)


if __name__ == "__main__":
    unittest.main()
