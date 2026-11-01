"""Pruebas de los documentos del producto: conversión a markdown, Confluence en solo lectura y sincronización."""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import documentos  # noqa: E402
import harness  # noqa: E402
import test_harness  # noqa: E402
from comun import ErrorRadiografia, git  # noqa: E402

CUERPO = ("<h1>Flujo</h1><p>Evalúa <strong>cada</strong> transacción.</p><ul><li>Uno</li><li>Dos</li></ul>"
          "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
          "<ac:structured-macro><ac:plain-text-body><![CDATA[int x = 1;]]></ac:plain-text-body></ac:structured-macro>"
          '<a href="https://x">enlace</a><ac:image></ac:image>')


class Respuesta:
    def __init__(self, datos: dict, estado: int = 200) -> None:
        self.datos, self.status_code = datos, estado

    def json(self) -> dict:
        return self.datos


class Sesion:
    """Confluence simulado. Falla si se intenta escribir."""

    def __init__(self) -> None:
        self.version, self.headers, self.auth, self.estado = 3, {}, None, 200

    def get(self, url, params=None, timeout=None):
        if url.endswith("/rest/api/content"):
            return Respuesta({"results": [{"id": "77"}]})
        return Respuesta({"id": "77", "title": "Flujo de evaluación", "version": {"number": self.version},
                          "_links": {"webui": "/spaces/F/pages/77"}, "body": {"storage": {"value": CUERPO}}}, self.estado)


ENV = {"CONFLUENCE_URL": "https://c.example/wiki", "JIRA_EMAIL": "e", "JIRA_TOKEN": "t"}


class PruebaDocumentos(unittest.TestCase):
    setUp_base = test_harness.PruebaHarness.setUp_base
    setUp_harness = test_harness.PruebaHarness.setUp
    tearDown = test_harness.PruebaHarness.tearDown

    def setUp(self) -> None:
        self.setUp_harness()
        harness.crear(self.raiz, "motor-fraudes")
        self.carpeta = self.destino / "documentos"
        parche = mock.patch.object(documentos, "cargar_env", lambda raiz: ENV)
        parche.start()
        self.addCleanup(parche.stop)

    def test_html_a_markdown(self) -> None:
        texto = documentos.html_a_markdown(CUERPO)
        for esperado in ("# Flujo", "Evalúa **cada** transacción.", "- Uno", "| A | B |", "|---|---|", "| 1 | 2 |",
                         "```\nint x = 1;\n```", "[enlace](https://x)", "Imagen de la página, no importada"):
            self.assertIn(esperado, texto)

    def test_confluence_solo_lee_y_sincroniza_lo_que_cambia(self) -> None:
        sesion = Sesion()
        archivos = documentos.confluence(self.raiz, "motor-fraudes", ["https://c.example/wiki/spaces/F/pages/77/Flujo"], sesion=sesion)
        self.assertEqual(archivos[0].name, "flujo-de-evaluacion-77.md")
        texto = archivos[0].read_text(encoding="utf-8")
        self.assertIn("- **Origen:** https://c.example/wiki/spaces/F/pages/77", texto)
        self.assertIn("<!-- confluence id=77 version=3 -->", texto)
        self.assertEqual(git("status", "--porcelain", cwd=self.destino), "", "queda con commit local")
        self.assertEqual(documentos.sincronizar(self.raiz, "motor-fraudes", sesion)["actualizadas"], [], "sin versión nueva no reescribe")
        sesion.version = 4
        self.assertEqual(len(documentos.sincronizar(self.raiz, "motor-fraudes", sesion)["actualizadas"]), 1)
        self.assertIn("version=4", archivos[0].read_text(encoding="utf-8"))
        self.assertEqual(len(documentos.confluence(self.raiz, "motor-fraudes", [], "F", sesion=sesion)), 1)
        sesion.estado = 403
        with self.assertRaises(ErrorRadiografia):
            documentos.confluence(self.raiz, "motor-fraudes", ["77"], sesion=sesion)
        with self.assertRaises(ErrorRadiografia):
            documentos.id_de_referencia("no-es-una-pagina")

    def test_todo_queda_en_markdown(self) -> None:
        origen = self.raiz / "minuta_de_arquitectura.txt"
        origen.write_text("Se usa Kafka para eventos.\n", encoding="utf-8")
        r = documentos.importar(self.raiz, "motor-fraudes", origen)
        self.assertEqual(r["archivo"].suffix, ".md")
        self.assertIn("- **Tipo:** txt", r["archivo"].read_text(encoding="utf-8"))
        self.assertFalse(r["pendiente"])
        self.assertIn("documentos/minuta-de-arquitectura.md:", documentos.buscar(self.raiz, "motor-fraudes", "kafka eventos")[0])
        with self.assertRaises(ErrorRadiografia):
            documentos.importar(self.raiz, "motor-fraudes", origen)  # no pisa

        imagen = self.raiz / "diagrama.png"
        imagen.write_bytes(b"\x89PNG")
        dibujo = documentos.importar(self.raiz, "motor-fraudes", imagen)
        self.assertTrue(dibujo["pendiente"])
        self.assertIn("## Qué muestra", dibujo["archivo"].read_text(encoding="utf-8"))
        self.assertFalse((self.carpeta / "diagrama.png").exists(), "el original no se copia")

        chat = self.raiz / "chat.txt"
        chat.write_text("Ana: usemos Kafka\n", encoding="utf-8")
        conversacion = documentos.importar(self.raiz, "motor-fraudes", chat, "Decisión de colas", True)
        self.assertNotIn("Ana", conversacion["archivo"].read_text(encoding="utf-8"), "no copia el chat")
        self.assertEqual([f["pendiente"] for f in documentos.listar(self.raiz, "motor-fraudes")], [True, True, False])

        antiguo = self.raiz / "viejo.doc"
        antiguo.write_bytes(b"x")
        with self.assertRaises(ErrorRadiografia):
            documentos.importar(self.raiz, "motor-fraudes", antiguo)

    def test_no_guarda_un_documento_con_secreto(self) -> None:
        origen = self.raiz / "claves.txt"
        origen.write_text("x\n", encoding="utf-8")
        with mock.patch.object(documentos, "tiene_secreto", return_value=True), self.assertRaises(ErrorRadiografia):
            documentos.importar(self.raiz, "motor-fraudes", origen)
        self.assertFalse((self.carpeta / "claves.md").exists())

    def test_el_paquete_de_revision_lista_los_documentos(self) -> None:
        import revision
        origen = self.raiz / "flujo.txt"
        origen.write_text("Se consulta el buró.\n", encoding="utf-8")
        documentos.importar(self.raiz, "motor-fraudes", origen)
        imagen = self.raiz / "diagrama.png"
        imagen.write_bytes(b"x")
        documentos.importar(self.raiz, "motor-fraudes", imagen)
        paquete = revision.generar_paquete(self.raiz, "motor-fraudes", "fraude-core").read_text(encoding="utf-8")
        self.assertIn("## Documentos del producto", paquete)
        self.assertIn("- `flujo.md` · txt", paquete)
        self.assertIn("- `diagrama.md` · dibujo · por completar: no usar como evidencia", paquete)

    def test_cli(self) -> None:
        origen = self.raiz / "nota.md"
        origen.write_text("Texto\n", encoding="utf-8")
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            self.assertEqual(documentos.main(["--raiz", str(self.raiz), "importar", "motor-fraudes", str(origen)]), 0)
            self.assertEqual(documentos.main(["--raiz", str(self.raiz), "sincronizar"]), 0)
        self.assertIn("documentos/nota.md", salida.getvalue())


if __name__ == "__main__":
    unittest.main()
