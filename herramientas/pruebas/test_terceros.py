"""Pruebas de los terceros: fichas, documentación (extracción, búsqueda y citas) y uso en la revisión."""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import revision  # noqa: E402
import terceros  # noqa: E402
import test_revision  # noqa: E402

OPENAPI = """\
openapi: 3.0.3
info:
  title: API de evaluación del motor
  version: 2.4.0
paths:
  /evaluaciones:
    post:
      responses:
        "200": {description: ok}
  /evaluaciones/{id}:
    get:
      responses:
        "200": {description: ok}
"""


def pdf(paginas: list[str]) -> bytes:
    """PDF mínimo válido, con una línea de texto por página."""
    objetos = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    hijos = []
    for texto in paginas:
        contenido = f"BT /F1 12 Tf 20 200 Td ({texto}) Tj ET"
        objetos.append(f"<< /Length {len(contenido)} >>\nstream\n{contenido}\nendstream")
        objetos.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents {len(objetos)} 0 R "
                       "/Resources << /Font << /F1 3 0 R >> >> >>")
        hijos.append(f"{len(objetos)} 0 R")
    objetos[1] = f"<< /Type /Pages /Kids [{' '.join(hijos)}] /Count {len(hijos)} >>"
    salida, desplazamientos = b"%PDF-1.4\n", []
    for numero, objeto in enumerate(objetos, start=1):
        desplazamientos.append(len(salida))
        salida += f"{numero} 0 obj\n{objeto}\nendobj\n".encode("latin-1")
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    salida += "".join(f"{d:010d} 00000 n \n" for d in desplazamientos).encode()
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    return salida


def office(archivo: Path, partes: dict[str, str]) -> None:
    with zipfile.ZipFile(archivo, "w") as zip_office:
        for nombre, contenido in partes.items():
            zip_office.writestr(nombre, contenido)


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'



class PruebaTerceros(unittest.TestCase):

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
        terceros.nuevo(self.raiz, "motor-fraudes", "motor", "Motor de fraudes", "producto-comprado")
        self.docs = self.producto / "terceros" / "motor" / "docs"
        (self.docs / "contratos").mkdir()
        (self.docs / "contratos" / "evaluacion.yaml").write_text(OPENAPI, encoding="utf-8")
        (self.docs / "notas.md").write_text("# Notas de versión\n\nLa versión 2.4 agrega el campo canal.\n", encoding="utf-8")
        (self.docs / "portal.html").write_text("<html><script>x()</script><p>Límite de 50 solicitudes por segundo</p></html>",
                                               encoding="utf-8")
        office(self.docs / "guia.docx", {"word/document.xml":
               f'<w:document {W}><w:body><w:p><w:r><w:t>Usar mTLS para </w:t></w:r><w:r><w:t>autenticar</w:t></w:r></w:p>'
               "</w:body></w:document>"})
        office(self.docs / "presentacion.pptx", {"ppt/slides/slide1.xml": f"<p:sld {A} xmlns:p=\"x\"><a:p><a:r><a:t>Arquitectura del motor</a:t></a:r></a:p></p:sld>"})
        (self.docs / "antiguo.doc").write_bytes(b"\xd0\xcf\x11\xe0")
        (self.docs / "diagrama.png").write_bytes(b"\x89PNG")
        if shutil.which("pdftotext"):
            (self.docs / "manual.pdf").write_bytes(pdf(["Manual de integracion", "Timeout recomendado de 800 ms"]))

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def ejecutar(self, *argumentos: str) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = terceros.main(["--raiz", str(self.raiz), *argumentos])
        return codigo, salida.getvalue()

    def ficha(self, id_tercero: str, **cambios) -> None:
        archivo = self.producto / "terceros" / id_tercero / "ficha.yaml"
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        datos.update(cambios)
        archivo.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")

    def test_indexar_por_formato(self) -> None:
        codigo, salida = self.ejecutar("indexar", "motor-fraudes")
        self.assertEqual(codigo, 0, salida)
        docs = terceros.documentos_indexados(self.raiz, "motor-fraudes", "motor")
        contrato = docs["contratos/evaluacion.yaml"]["contrato"]
        self.assertEqual((contrato["tipo"], contrato["titulo"], contrato["version"], contrato["operaciones"]),
                         ("OpenAPI", "API de evaluación del motor", "2.4.0", 2), "el contrato se reconoce por su contenido")
        texto = lambda nombre: terceros.texto_de(self.raiz, "motor-fraudes", f"terceros/motor/docs/{nombre}")  # noqa: E731
        self.assertIn("Usar mTLS para autenticar", texto("guia.docx"))
        self.assertIn("Arquitectura del motor", texto("presentacion.pptx"))
        self.assertIn("Límite de 50 solicitudes", texto("portal.html"))
        self.assertNotIn("x()", texto("portal.html"), "los scripts del HTML no se indexan")
        self.assertIn("guardar como .docx o PDF", docs["antiguo.doc"]["motivo"])
        self.assertIn("imagen", docs["diagrama.png"]["motivo"])
        self.assertNotIn(".gitkeep", docs)
        indice = (self.docs / "INDICE.md").read_text(encoding="utf-8")
        self.assertIn("| [contratos/evaluacion.yaml](contratos/evaluacion.yaml) | OpenAPI 3.0.3 |", indice)
        self.assertIn("No indexado: antiguo.doc", salida)

    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext no está instalado")
    def test_pdf_con_paginas_y_busqueda(self) -> None:
        self.ejecutar("indexar", "motor-fraudes")
        self.assertEqual(terceros.documentos_indexados(self.raiz, "motor-fraudes", "motor")["manual.pdf"]["paginas"], 2)
        codigo, salida = self.ejecutar("buscar", "motor-fraudes", "timeout 800")
        self.assertIn("terceros/motor/docs/manual.pdf (página 2)", salida)

    def test_solo_reprocesa_lo_que_cambia(self) -> None:
        self.ejecutar("indexar", "motor-fraudes")
        self.assertEqual(terceros.indexar(self.raiz, "motor-fraudes")["motor"]["procesados"], 0)
        (self.docs / "notas.md").write_text("# Notas\n\nCambio.\n", encoding="utf-8")
        (self.docs / "portal.html").unlink()
        resultado = terceros.indexar(self.raiz, "motor-fraudes")["motor"]
        self.assertEqual((resultado["procesados"], resultado["eliminados"]), (1, ["portal.html"]))

    def test_citas_y_fichas(self) -> None:
        self.ejecutar("indexar", "motor-fraudes")
        cita = revision.validar_cita_tercero(self.raiz, "motor-fraudes", "terceros/motor/docs/guia.docx", "Usar mTLS para autenticar")
        self.assertEqual(cita["documento"], "terceros/motor/docs/guia.docx")
        for documento, texto, mensaje in (("terceros/motor/docs/guia.docx", "Usar API key", "no aparece textualmente"),
                                          ("terceros/motor/docs/antiguo.doc", "algo", "no está indexado"),
                                          ("terceros/motor/docs/no-existe.pdf", "algo", "no está en la documentación"),
                                          ("guia.docx", "algo", "formato: terceros/<id>/docs/<archivo>"),
                                          ("terceros/motor/docs/guia.docx", None, "se indican juntos")):
            with self.assertRaises(Exception) as contexto:
                revision.validar_cita_tercero(self.raiz, "motor-fraudes", documento, texto)
            self.assertIn(mensaje, str(contexto.exception))

        terceros.nuevo(self.raiz, "motor-fraudes", "buro-credito", "Buró de crédito")
        errores, pendientes = terceros.validar(self.raiz, "motor-fraudes", "buro-credito",
                                               terceros.leer_fichas(self.raiz, "motor-fraudes")["buro-credito"])
        self.assertEqual(errores, [], "la plantilla recién creada es válida, solo incompleta")
        self.assertIn("politica_ante_falla", pendientes)
        self.ficha("buro-credito", politica_ante_falla="fail-closed", repos=["fraude-core", "no-existe"],
                   sla={"p95_ms": "rápido"}, contrato="openapi.yaml", rol="otro")
        errores, _ = terceros.validar(self.raiz, "motor-fraudes", "buro-credito",
                                      terceros.leer_fichas(self.raiz, "motor-fraudes")["buro-credito"])
        for esperado in ("una política fail-open o fail-closed necesita su justificación de negocio",
                         "repositorios que no existen en el producto: no-existe", "sla.p95_ms debe ser un número o null",
                         "el contrato 'openapi.yaml' no existe en docs/", "rol 'otro' inválido; valores válidos: producto-comprado, integracion"):
            self.assertIn(esperado, errores)

        self.ficha("buro-credito", proveedor="Buró S.A.", protocolo="HTTPS/JSON", autenticacion="mTLS", rol="integracion",
                   justificacion="Sin buró no se evalúa el riesgo crediticio", repos=["fraude-core"],
                   sla={"disponibilidad": 99.9, "p95_ms": 800}, contrato=None)
        filas = {f["id"]: f for f in terceros.listar(self.raiz, "motor-fraudes")}
        self.assertEqual((filas["buro-credito"]["errores"], filas["buro-credito"]["pendientes"]), ([], []))
        self.assertIn("✅ completa", (self.producto / "terceros" / "INDICE.md").read_text(encoding="utf-8"))
        self.assertEqual({f["id"] for f in terceros.para_repo(self.raiz, "motor-fraudes", "fraude-backoffice")}, {"motor"},
                         "un tercero sin repositorios declarados se muestra a todos; el buró solo a fraude-core")


class PruebaTercerosEnLaRevision(unittest.TestCase):
    setUp = test_revision.PruebaRevision.setUp
    tearDown = test_revision.PruebaRevision.tearDown

    def test_el_paquete_muestra_los_terceros_del_repo(self) -> None:
        terceros.nuevo(self.raiz, "motor-fraudes", "buro-credito", "Buró de crédito")
        archivo = self.raiz / "productos" / "motor-fraudes" / "terceros" / "buro-credito" / "ficha.yaml"
        archivo.write_text(archivo.read_text(encoding="utf-8").replace("p95_ms: null", "p95_ms: 800"), encoding="utf-8")
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            revision.main(["--raiz", str(self.raiz), "paquete", "motor-fraudes", "fraude-core"])
        paquete = (self.raiz / salida.getvalue().split("Paquete: ")[1].strip()).read_text(encoding="utf-8")
        self.assertIn("## Terceros", paquete)
        self.assertIn("| `buro-credito` Buró de crédito | integracion |", paquete)
        self.assertIn("| 800 |", paquete)


if __name__ == "__main__":
    unittest.main()
