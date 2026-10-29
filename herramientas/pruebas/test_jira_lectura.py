"""Pruebas de las historias de usuario: Jira simulado, CSV, candidatas, clasificación, ADR y cambios."""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import adr  # noqa: E402
import jira as historias  # noqa: E402
from comun import RAIZ  # noqa: E402


def texto(t: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": t}]}


def titulo(t: str) -> dict:
    return {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": t}]}


def lista(*items: str) -> dict:
    return {"type": "bulletList", "content": [{"type": "listItem", "content": [texto(i)]} for i in items]}


def descripcion_latencia(milisegundos: int) -> dict:
    return {"type": "doc", "content": [
        texto("Como cliente quiero que mi compra se evalúe sin demoras."),
        titulo("Criterios de aceptación"),
        lista(f"La evaluación responde en menos de {milisegundos} ms", "Si el motor no responde, la transacción se rechaza"),
        titulo("Notas"),
        texto("Sin notas."),
    ]}


def historia(clave: str, resumen: str, tipo: str, descripcion: dict) -> dict:
    return {"key": clave, "fields": {"summary": resumen, "description": descripcion, "status": {"name": "Terminada"},
                                     "updated": "2026-10-01T10:00:00.000-0300", "customfield_10050": {"value": tipo}}}


class Respuesta:
    def __init__(self, datos, estado: int = 200) -> None:
        self.status_code, self._datos, self.text = estado, datos, str(datos)

    def json(self):
        return self._datos


class JiraFalso:
    """Responde como Jira Cloud: campos, y búsqueda JQL paginada con nextPageToken."""

    def __init__(self) -> None:
        self.headers: dict = {}
        self.auth = None
        self.historias = [
            historia("FRAUD-1", "Evaluar la compra en tiempo real", "Producto", descripcion_latencia(150)),
            historia("FRAUD-2", "Elegir el broker de mensajería", "Spike", {"type": "doc", "content": [texto("Comparar opciones.")]}),
            historia("FRAUD-3", "Filtrar alertas por fecha", "Producto", {"type": "doc", "content": [texto("Filtro en la pantalla.")]}),
        ]

    def get(self, url, timeout=None, params=None):
        assert url.endswith("/rest/api/3/field")
        return Respuesta([{"id": "summary", "name": "Summary"}, {"id": "customfield_10050", "name": "Tipo"}])

    def post(self, url, json=None, timeout=None):
        assert url.endswith("/rest/api/3/search/jql")
        assert "customfield_10050" in json["fields"]
        if json.get("nextPageToken") == "p2":
            return Respuesta({"issues": self.historias[2:], "isLast": True})
        return Respuesta({"issues": self.historias[:2], "nextPageToken": "p2"})


class PruebaHistorias(unittest.TestCase):

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporal.name)
        shutil.copytree(RAIZ / "equipo" / "plantillas", self.raiz / "equipo" / "plantillas")
        (self.raiz / "equipo" / "decisiones").mkdir()
        self.producto = self.raiz / "productos" / "motor-fraudes"
        self.producto.mkdir(parents=True)
        (self.producto / "producto.yaml").write_text(textwrap.dedent("""\
            nombre: motor-fraudes
            sigla: MF
            repos: []
            historias:
              fuente: jira
              jql: 'project = FRAUD'
              campo_tipo: Tipo
            """), encoding="utf-8")
        (self.raiz / ".env").write_text("JIRA_URL=https://ejemplo.atlassian.net\nJIRA_EMAIL=a@b.c\nJIRA_TOKEN=x\n", encoding="utf-8")
        self.jira = JiraFalso()

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def sincronizar(self) -> dict:
        return historias.sincronizar(self.raiz, "motor-fraudes", sesion=self.jira)

    def clasificar(self, lote: str) -> tuple[int, str]:
        (self.producto / "historias").mkdir(exist_ok=True)
        (self.producto / "historias" / "clasificacion-lote.yaml").write_text(textwrap.dedent(lote), encoding="utf-8")
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = historias.main(["--raiz", str(self.raiz), "clasificar", "motor-fraudes"])
        return codigo, salida.getvalue()

    def test_sincroniza_jira_con_tipo_y_criterios(self) -> None:
        resumen = self.sincronizar()
        self.assertEqual(sorted(resumen["nuevas"]), ["FRAUD-1", "FRAUD-2", "FRAUD-3"], "las dos páginas")
        guardadas = historias.historias_de(self.raiz, "motor-fraudes")
        self.assertEqual(guardadas["FRAUD-2"]["tipo"], "Spike", "el tipo sale del campo personalizado")
        criterios = guardadas["FRAUD-1"]["criterios"]
        self.assertIn("- La evaluación responde en menos de 150 ms", criterios)
        self.assertNotIn("Sin notas", criterios, "los criterios terminan en el título siguiente")
        self.assertEqual(guardadas["FRAUD-1"]["url"], "https://ejemplo.atlassian.net/browse/FRAUD-1")
        self.assertTrue((self.producto / "historias" / "INDICE.md").exists())

    def test_candidatas_por_tipo_y_senales(self) -> None:
        self.sincronizar()
        motivos = {h["clave"]: h["motivo"] for h in historias.candidatas(self.raiz, "motor-fraudes")}
        self.assertEqual(set(motivos), {"FRAUD-1", "FRAUD-2"}, "FRAUD-3 no tiene señales ni es Spike o Deuda Técnica")
        self.assertEqual(motivos["FRAUD-2"], "tipo Spike")
        self.assertIn("150 ms", motivos["FRAUD-1"])

    def test_clasificacion_validada_y_adr_desde_historias(self) -> None:
        self.sincronizar()
        codigo, salida = self.clasificar("""\
            historias:
              - {clave: FRAUD-1, clasificacion: candidata, tema: Latencia, cita: "responde en menos de 200 ms", explicacion: x}
              - {clave: FRAUD-2, clasificacion: choque, documento: ADR-EQ-099, cita: "Comparar opciones.", explicacion: x}
            """)
        self.assertEqual(codigo, 1)
        self.assertIn("2 error(es); no se registró nada", salida)
        self.assertIn("no aparece textualmente en la historia", salida)
        self.assertIn("no es un ADR o estándar vigente", salida)

        codigo, salida = self.clasificar("""\
            historias:
              - {clave: FRAUD-1, clasificacion: candidata, tema: Latencia de evaluación,
                 cita: "La evaluación responde en menos de 150 ms", explicacion: Requisito de latencia verificable.}
              - {clave: FRAUD-2, clasificacion: sin_impacto}
            """)
        self.assertEqual(codigo, 0, salida)
        self.assertEqual(historias.candidatas(self.raiz, "motor-fraudes"), [], "lo analizado no se vuelve a pedir")
        self.assertEqual(list(historias.propuestas(self.raiz, "motor-fraudes")), ["Latencia de evaluación"])

        archivo = adr.nuevo(self.raiz, "motor-fraudes", "decision", "Latencia de evaluación", [], ["FRAUD-1"])
        texto_adr = archivo.read_text(encoding="utf-8")
        self.assertIn("| [FRAUD-1](https://ejemplo.atlassian.net/browse/FRAUD-1) | Producto |", texto_adr)
        self.assertIn("La evaluación responde en menos de 150 ms", texto_adr)
        self.assertIn("- **Historias de origen:** FRAUD-1", texto_adr)
        self.assertEqual(historias.propuestas(self.raiz, "motor-fraudes"), {}, "una candidata con ADR deja de proponerse")

    def test_cambios_y_retiro_de_historias(self) -> None:
        self.sincronizar()
        self.clasificar("""\
            historias:
              - {clave: FRAUD-1, clasificacion: candidata, tema: Latencia, cita: "responde en menos de 150 ms", explicacion: x}
            """)
        adr.nuevo(self.raiz, "motor-fraudes", "decision", "Latencia", [], ["FRAUD-1"])

        self.jira.historias[0] = historia("FRAUD-1", "Evaluar la compra en tiempo real", "Producto", descripcion_latencia(300))
        del self.jira.historias[2]
        resumen = self.sincronizar()
        self.assertEqual(resumen["modificadas"], ["FRAUD-1"])
        self.assertEqual(resumen["retiradas"], ["FRAUD-3"])
        guardada = historias.historias_de(self.raiz, "motor-fraudes")["FRAUD-1"]
        self.assertIn("150 ms", guardada["versiones"][-1]["criterios"], "se conserva la versión anterior")
        self.assertIn("FRAUD-1", {h["clave"] for h in historias.candidatas(self.raiz, "motor-fraudes")},
                      "una historia modificada se vuelve a analizar")
        self.assertEqual(historias.atencion(self.raiz, "motor-fraudes"), {"ADR-MF-001": ["FRAUD-1 modificada"]})
        self.assertIn("revisar: FRAUD-1 modificada", adr.listar(self.raiz, "motor-fraudes")[0]["efecto"])
        indice = (self.producto / "historias" / "INDICE.md").read_text(encoding="utf-8")
        self.assertIn("Criterios antes: - La evaluación responde en menos de 150 ms", indice)
        self.assertIn("Criterios ahora: - La evaluación responde en menos de 300 ms", indice)

        historias.confirmar(self.raiz, "motor-fraudes", "ADR-MF-001")
        self.assertEqual(historias.atencion(self.raiz, "motor-fraudes"), {})

    def test_csv_exportado_de_jira(self) -> None:
        (self.producto / "producto.yaml").write_text(textwrap.dedent("""\
            nombre: motor-fraudes
            sigla: MF
            repos: []
            historias: {fuente: archivo, archivo: export.csv, campo_tipo: Tipo}
            """), encoding="utf-8")
        (self.producto / "historias").mkdir()
        (self.producto / "historias" / "export.csv").write_text(
            'Clave de incidencia,Resumen,Descripción,Estado,Campo personalizado (Tipo)\n'
            'OLD-7,Conservar decisiones,"**Criterios de aceptación**\n- Las decisiones se conservan 5 años",Cerrada,Deuda Técnica\n',
            encoding="utf-8")
        resumen = historias.sincronizar(self.raiz, "motor-fraudes")
        self.assertEqual(resumen["nuevas"], ["OLD-7"])
        guardada = historias.historias_de(self.raiz, "motor-fraudes")["OLD-7"]
        self.assertEqual(guardada["tipo"], "Deuda Técnica")
        self.assertEqual(guardada["criterios"], "- Las decisiones se conservan 5 años")

    def test_criterios_en_formato_gherkin(self) -> None:
        self.assertEqual(historias.extraer_criterios("Contexto.\nDado un cliente\nCuando paga\nEntonces se evalúa"),
                         "Dado un cliente\nCuando paga\nEntonces se evalúa")
        self.assertIsNone(historias.extraer_criterios("Solo una descripción."))


if __name__ == "__main__":
    unittest.main()
