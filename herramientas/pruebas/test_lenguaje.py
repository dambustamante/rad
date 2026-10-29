"""Pruebas de la revisión de lenguaje."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lenguaje  # noqa: E402
import revision  # noqa: E402
from comun import RAIZ  # noqa: E402


def reglas_encontradas(texto: str) -> list[tuple[str, str]]:
    return [(a["regla"], a["texto"]) for a in lenguaje.revisar(texto, lenguaje.cargar_reglas(RAIZ))]


class PruebaLenguaje(unittest.TestCase):

    def test_detecta_voseo_relleno_y_siglas(self) -> None:
        avisos = reglas_encontradas("Tenés que ejecutar esto.\nEs importante destacar que el servicio es robusto.\nEl SLA es bajo.")
        self.assertIn(("voseo", "tenés"), avisos)
        self.assertIn(("expresión vaga o de relleno", "es importante destacar"), avisos)
        self.assertIn(("expresión vaga o de relleno", "robusto"), avisos)
        self.assertIn(("sigla sin explicar", "SLA"), avisos)

    def test_evita_falsos_positivos(self) -> None:
        texto = "\n".join([
            "El servicio ejecuta la evaluación y hace el registro.",          # "ejecuta" no es voseo
            "Se evita escribir \"robusto\" o «potenciar».",                    # ejemplos entre comillas
            "El `HttpClient` usa timeout; ver ADR-EQ-003 y FRAUD-123.",        # código e identificadores
            "El p95 del SLA (acuerdo de nivel de servicio) es 800 ms; el SLA se mide por mes.",
            "Requisitos PCI DSS (estándar de seguridad de datos de tarjetas).",
            "Resultado: NO APLICA o NO DETERMINADO.",
            "```",
            "es importante destacar dentro de un bloque de código",
            "```",
            "> Cita textual: es robusto.",
        ])
        self.assertEqual(reglas_encontradas(texto), [])

    def test_decisiones_sobre_la_forma_de_trabajar_no_se_evaluan_en_el_codigo(self) -> None:
        claves = {e["clave"] for e in revision.lista_de_control(RAIZ, "propio")}
        self.assertFalse(any(c.startswith(("ADR-EQ-008", "ADR-EQ-009")) for c in claves))
        self.assertTrue(any(c.startswith("ADR-EQ-003") for c in claves))


if __name__ == "__main__":
    unittest.main()
