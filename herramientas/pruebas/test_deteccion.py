"""Pruebas de lo que mostró la primera revisión real: detectores, secretos repetidos, motivos y certificados."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import comun  # noqa: E402
import revision  # noqa: E402
import verificaciones  # noqa: E402
from comun import normalizar  # noqa: E402


class PruebaDeteccion(unittest.TestCase):
    def test_webflux_funcional_y_kafka_reactivo(self) -> None:
        for linea in ("return RouterFunctions.route()", '.GET("/odin-api/v1/enrollment", handler::listar)',
                      "RequestPredicates.POST(\"/x\")"):
            self.assertTrue(verificaciones.SENALES_API.search(linea), linea)
        for linea in ("private final KafkaSender<String, String> sender;", "ReactiveKafkaConsumerTemplate<String, Evento> consumidor",
                      "ReceiverOptions.create(propiedades)"):
            self.assertTrue(verificaciones.SENALES_EVENTOS.search(linea), linea)
        self.assertFalse(verificaciones.SENALES_API.search("lista.get(0)"))

    def test_un_hallazgo_por_secreto(self) -> None:
        datos = [{"RuleID": "jwt", "File": "a.json", "StartLine": 430, "Commit": "aaa"},
                 {"RuleID": "jwt", "File": "a.json", "StartLine": 430, "Commit": "bbb"},
                 {"RuleID": "jwt", "File": "a.json", "StartLine": 461, "Commit": "aaa"}]
        self.assertEqual(len(verificaciones.secretos_unicos(datos)), 2)

    def test_no_determinado_exige_un_motivo_real(self) -> None:
        for motivo in ("No se revisó cada clase.", "No se contrastó cada operación.", "no se verificó la propagación"):
            self.assertTrue(revision.SIN_REVISAR.search(normalizar(motivo)), motivo)
        self.assertFalse(revision.SIN_REVISAR.search(normalizar("El tier del servicio no está declarado en el repositorio.")))

    def test_la_ficha_agrupa_y_acorta(self) -> None:
        import ficha
        base = {"repo": "r", "rama": "main", "estado": "abierto", "modo": "propuesta", "nivel": 3, "criterio": "EQ-001.1",
                "fuente": "ADR-EQ-001", "severidad": "bloqueante", "titulo": "Posible secreto (jwt) en a.json"}
        lista = [{**base, "id": f"H-{n}", "evidencia": [{"archivo": "a.json", "linea": n}]} for n in (404, 430, 461)]
        grupos = ficha.grupos(lista)
        self.assertEqual((len(grupos), grupos[0]["ids"]), (1, ["H-404", "H-430", "H-461"]), "los repetidos van en una fila")
        self.assertIn("(líneas 404, 430, 461)", ficha.donde(grupos[0]))
        self.assertFalse(grupos[0]["cuenta"], "un ADR en Propuesto informa")
        self.assertEqual(ficha.regla_de(base), "ADR-EQ-001")
        largo = "<!-- automatico:inicio -->\n## Datos generales\n\n## Sonar\n\nNO DETERMINADO - x [SSL: CERTIFICATE_VERIFY_FAILED] y\n" \
                "\n## Hallazgos automáticos abiertos\n\n| ID |\n<!-- automatico:fin -->"
        corto = ficha.limpiar_automatico(largo)
        self.assertIn("configurar `CA_BUNDLE`", corto)
        self.assertNotIn("Hallazgos automáticos abiertos", corto)
        self.assertTrue(corto.endswith("<!-- automatico:fin -->"))

    def test_el_as_is_va_en_tablas(self) -> None:
        tabla = "## Observabilidad\n\n| Aspecto | Qué hay | Evidencia |\n|---|---|---|\n| Trazas | b3 | [hecho] `a.yaml:7` |\n"
        self.assertTrue(revision.tabla_con_evidencia(tabla, "Observabilidad"))
        self.assertFalse(revision.tabla_con_evidencia("## Observabilidad\n\nUsa Actuator ([hecho] `b.gradle:49`).\n", "Observabilidad"))
        self.assertTrue(revision.tabla_con_evidencia("## Riesgos y deuda principales\n\nLos riesgos están en la tabla de hallazgos.\n",
                                                     "Riesgos y deuda principales"))

    def test_certificados_de_la_red(self) -> None:
        with tempfile.TemporaryDirectory() as carpeta, mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REQUESTS_CA_BUNDLE", None)
            (Path(carpeta) / ".env").write_text("CA_BUNDLE=~/certificados.pem\n", encoding="utf-8")
            comun.cargar_env(Path(carpeta))
            self.assertEqual(os.environ["REQUESTS_CA_BUNDLE"], os.path.expanduser("~/certificados.pem"))


if __name__ == "__main__":
    unittest.main()
