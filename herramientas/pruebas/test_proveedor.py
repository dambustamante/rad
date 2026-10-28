"""Pruebas de la documentación del proveedor: extracción por formato, índice, búsqueda y citas."""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import productos  # noqa: E402
import proveedor  # noqa: E402
import revision  # noqa: E402

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


class PruebaProveedor(unittest.TestCase):

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporal.name)
        (self.raiz / "productos" / "motor-fraudes").mkdir(parents=True)
        (self.raiz / "productos" / "motor-fraudes" / "producto.yaml").write_text(
            "nombre: motor-fraudes\nsigla: MF\nrepos: []\n", encoding="utf-8")
        self.docs = self.raiz / "productos" / "motor-fraudes" / "proveedor"
        (self.docs / "contratos").mkdir(parents=True)
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
            codigo = proveedor.main(["--raiz", str(self.raiz), *argumentos])
        return codigo, salida.getvalue()

    def test_indexar_por_formato(self) -> None:
        codigo, salida = self.ejecutar("indexar", "motor-fraudes")
        self.assertEqual(codigo, 0, salida)
        docs = proveedor.documentos_indexados(self.raiz, "motor-fraudes")
        contrato = docs["contratos/evaluacion.yaml"]["contrato"]
        self.assertEqual((contrato["tipo"], contrato["titulo"], contrato["version"], contrato["operaciones"]),
                         ("OpenAPI", "API de evaluación del motor", "2.4.0", 2), "el contrato se reconoce por su contenido")
        self.assertIsNone(docs["notas.md"]["contrato"])
        self.assertIn("Usar mTLS para autenticar", proveedor.texto_de(self.raiz, "motor-fraudes", "guia.docx"))
        self.assertIn("Arquitectura del motor", proveedor.texto_de(self.raiz, "motor-fraudes", "presentacion.pptx"))
        texto_html = proveedor.texto_de(self.raiz, "motor-fraudes", "portal.html")
        self.assertIn("Límite de 50 solicitudes", texto_html)
        self.assertNotIn("x()", texto_html, "los scripts del HTML no se indexan")
        self.assertIn("guardar como .docx o PDF", docs["antiguo.doc"]["motivo"])
        self.assertIn("imagen", docs["diagrama.png"]["motivo"])

        indice = (self.docs / "INDICE.md").read_text(encoding="utf-8")
        self.assertIn("| [contratos/evaluacion.yaml](contratos/evaluacion.yaml) | OpenAPI 3.0.3 |", indice)
        self.assertIn("## No indexados (la revisión no los usa)", indice)
        self.assertIn("No indexado: antiguo.doc", salida)

    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext no está instalado")
    def test_pdf_con_paginas_y_busqueda(self) -> None:
        self.ejecutar("indexar", "motor-fraudes")
        self.assertEqual(proveedor.documentos_indexados(self.raiz, "motor-fraudes")["manual.pdf"]["paginas"], 2)
        codigo, salida = self.ejecutar("buscar", "motor-fraudes", "timeout 800")
        self.assertIn("manual.pdf (página 2)", salida)
        self.assertIn("Timeout recomendado de 800 ms", salida)

    def test_solo_reprocesa_lo_que_cambia(self) -> None:
        self.ejecutar("indexar", "motor-fraudes")
        self.assertEqual(proveedor.indexar(self.raiz, "motor-fraudes")["procesados"], 0)
        (self.docs / "notas.md").write_text("# Notas\n\nCambio.\n", encoding="utf-8")
        (self.docs / "portal.html").unlink()
        resultado = proveedor.indexar(self.raiz, "motor-fraudes")
        self.assertEqual(resultado["procesados"], 1)
        self.assertEqual(resultado["eliminados"], ["portal.html"])
        self.assertFalse((self.raiz / "productos" / "motor-fraudes" / "estado" / "proveedor" / "texto" / "portal.html.txt").exists())

    def test_validar_cita_del_proveedor(self) -> None:
        self.ejecutar("indexar", "motor-fraudes")
        cita = revision.validar_cita_proveedor(self.raiz, "motor-fraudes", "proveedor/guia.docx", "Usar mTLS para autenticar")
        self.assertEqual(cita, {"documento": "guia.docx", "texto": "Usar mTLS para autenticar"})
        for documento, texto, mensaje in (("guia.docx", "Usar API key", "no aparece textualmente"),
                                          ("antiguo.doc", "algo", "no está indexado"),
                                          ("no-existe.pdf", "algo", "no está en la documentación del proveedor"),
                                          ("guia.docx", None, "se usan juntos")):
            with self.assertRaises(Exception) as contexto:
                revision.validar_cita_proveedor(self.raiz, "motor-fraudes", documento, texto)
            self.assertIn(mensaje, str(contexto.exception))


if __name__ == "__main__":
    unittest.main()
