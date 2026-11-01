"""Pruebas de coherencia: pares pendientes, validación de citas, suspensión y generación."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import coherencia  # noqa: E402
import sync_arquitectura  # noqa: E402
from test_sync_arquitectura import commit, ejecutar  # noqa: E402


def adr_arquitectura(numero: str, titulo: str, decision: str, regla: str) -> str:
    return textwrap.dedent(f"""\
        # ADR-{numero}: {titulo}

        ## 2. Estado

        Aprobado

        ## 5. Decisión

        {decision}

        ## 11. Regla rápida

        > {regla}
        """)


def adr_equipo(numero: str, titulo: str, decision: str, regla: str, criterios: int) -> str:
    filas = "\n".join(f"| `EQ-{numero}.{i}` | Criterio {i} | revisión de código | media |" for i in range(1, criterios + 1))
    return textwrap.dedent(f"""\
        # ADR-EQ-{numero}: {titulo}

        ## 2. Estado

        Propuesto

        ## 3. Fecha

        - Fecha de creación: `27-10-2026`

        ## 5. Decisión

        {decision}

        ## 11. Regla rápida

        > {regla}

        ## 12. Relación con arquitectura

        Ver `equipo/COHERENCIA.md`.

        ## 13. Criterios de verificación

        | Criterio | Qué se verifica | Cómo | Severidad |
        |---|---|---|---|
        """) + filas + "\n"


class PruebaCoherencia(unittest.TestCase):

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        base = Path(self.temporal.name)
        self.origen = base / "origen"
        self.raiz = base / "raiz"

        adrs = self.origen / "adrs"
        adrs.mkdir(parents=True)
        ejecutar("git", "init", "--quiet", "-b", "main", cwd=self.origen)
        (adrs / "0010-reintentos.md").write_text(adr_arquitectura(
            "010", "Reintentos centralizados",
            "Los reintentos se configuran solo en el API Gateway; los servicios no implementan reintentos propios.",
            "Reintentos solo en el API Gateway."), encoding="utf-8")
        (adrs / "0011-logs.md").write_text(adr_arquitectura(
            "011", "Logs estructurados",
            "Todos los servicios emiten logs en formato JSON e incluyen el campo trace_id.",
            "Logs en JSON con trace_id."), encoding="utf-8")
        (adrs / "0012-base-de-datos.md").write_text(adr_arquitectura(
            "012", "Base de datos relacional",
            "La base de datos relacional estándar es PostgreSQL.",
            "PostgreSQL como base relacional."), encoding="utf-8")
        commit(self.origen, "ADR de arquitectura")

        equipo = self.raiz / "equipo" / "decisiones"
        equipo.mkdir(parents=True)
        (equipo / "ADR-EQ-002-resiliencia.md").write_text(adr_equipo(
            "002", "Integraciones resilientes",
            "Los reintentos se aplican solo en operaciones idempotentes, con espera exponencial y un máximo de intentos.",
            "Ninguna integración sin timeout.", 3), encoding="utf-8")
        (equipo / "ADR-EQ-003-logs.md").write_text(adr_equipo(
            "003", "Manejo de logs",
            "Los logs se emiten en JSON, una línea por evento, e incluyen el campo trace_id.",
            "Un log es una línea JSON con su trace_id.", 2), encoding="utf-8")

        (self.raiz / "harness.yaml").write_text(textwrap.dedent(f"""\
            version: 1
            arquitectura:
              fuentes:
                - id: decisiones
                  url: {self.origen}
                  ref: main
                  ruta: adrs
                  tipo: adr
              estados:
                vigente: [Aprobado]
                pendiente: [Propuesto]
                no_vigente: [Reemplazado]
            """), encoding="utf-8")
        self.sincronizar()

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def sincronizar(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sync_arquitectura.main(["--raiz", str(self.raiz)]), 0)

    def ejecutar(self, *argumentos: str) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = coherencia.main(["--raiz", str(self.raiz), *argumentos])
        return codigo, salida.getvalue()

    def plan(self) -> dict:
        codigo, salida = self.ejecutar("preparar", "--json")
        self.assertEqual(codigo, 0, salida)
        return json.loads(salida)

    def registrar_choque(self) -> tuple[int, str]:
        return self.ejecutar(
            "registrar", "--eq", "ADR-EQ-002", "--doc", "decisiones:ADR-010", "--relacion", "choca",
            "--cita-arquitectura", "los servicios no implementan reintentos propios",
            "--cita-equipo", "Los reintentos se aplican solo en operaciones idempotentes",
            "--criterios", "EQ-002.2", "--explicacion", "Arquitectura centraliza los reintentos en el gateway.")

    def registrar_todo(self) -> None:
        self.assertEqual(self.registrar_choque()[0], 0)
        codigo, salida = self.ejecutar(
            "registrar", "--eq", "ADR-EQ-003", "--doc", "decisiones:ADR-011", "--relacion", "duplica",
            "--cita-arquitectura", "emiten logs en formato JSON e incluyen el campo trace_id",
            "--cita-equipo", "Los logs se emiten en JSON, una línea por evento",
            "--explicacion", "Arquitectura ya exige JSON con trace_id.")
        self.assertEqual(codigo, 0, salida)
        for eq, doc in (("ADR-EQ-002", "decisiones:ADR-011"), ("ADR-EQ-002", "decisiones:ADR-012"),
                        ("ADR-EQ-003", "decisiones:ADR-010"), ("ADR-EQ-003", "decisiones:ADR-012")):
            codigo, salida = self.ejecutar("registrar", "--eq", eq, "--doc", doc, "--relacion", "sin_relacion")
            self.assertEqual(codigo, 0, salida)

    def test_preparar_lista_todos_los_pares_la_primera_vez(self) -> None:
        plan = self.plan()
        self.assertEqual(plan["total_pares"], 6)
        self.assertEqual(set(plan["pendientes"]), {"ADR-EQ-002", "ADR-EQ-003"})
        self.assertEqual(plan["documentos"]["decisiones:ADR-010"]["regla_rapida"], "Reintentos solo en el API Gateway.")

    def test_extracto_trae_decision_y_regla(self) -> None:
        codigo, salida = self.ejecutar("extracto", "decisiones:ADR-010")
        self.assertEqual(codigo, 0, salida)
        self.assertIn("API Gateway", salida)
        self.assertIn("## regla rapida", salida)

    def test_rechaza_citas_inventadas_y_criterios_invalidos(self) -> None:
        codigo, salida = self.ejecutar(
            "registrar", "--eq", "ADR-EQ-002", "--doc", "decisiones:ADR-010", "--relacion", "choca",
            "--cita-arquitectura", "los servicios tienen prohibido reintentar cualquier llamada",
            "--cita-equipo", "Los reintentos se aplican solo en operaciones idempotentes",
            "--criterios", "EQ-002.2", "--explicacion", "x")
        self.assertEqual(codigo, 1)
        self.assertIn("no aparece textualmente", salida)

        codigo, salida = self.ejecutar(
            "registrar", "--eq", "ADR-EQ-002", "--doc", "decisiones:ADR-010", "--relacion", "choca",
            "--cita-arquitectura", "los servicios no implementan reintentos propios",
            "--cita-equipo", "Los reintentos se aplican solo en operaciones idempotentes",
            "--criterios", "EQ-002.9", "--explicacion", "x")
        self.assertEqual(codigo, 1)
        self.assertIn("Criterios que no existen en ADR-EQ-002: EQ-002.9", salida)

        codigo, salida = self.ejecutar(
            "registrar", "--eq", "ADR-EQ-002", "--doc", "decisiones:ADR-010", "--relacion", "choca",
            "--cita-arquitectura", "los servicios no implementan reintentos propios",
            "--cita-equipo", "Los reintentos se aplican solo en operaciones idempotentes", "--explicacion", "x")
        self.assertEqual(codigo, 1)
        self.assertIn("exige --criterios", salida)

    def test_lote_por_excepcion(self) -> None:
        lote = self.raiz / "lote.yaml"
        total = coherencia.preparar(coherencia.ambito_equipo(self.raiz))["total_pares"]
        self.assertGreater(total, 1)
        lote.write_text("pares: []\n", encoding="utf-8")
        self.ejecutar("lote", str(lote))
        self.assertEqual(coherencia.preparar(coherencia.ambito_equipo(self.raiz))["total_pares"], total, "sin la marca no se asume nada")
        lote.write_text("resto_sin_relacion: true\npares: []\n", encoding="utf-8")
        self.ejecutar("lote", str(lote))
        self.assertEqual(coherencia.preparar(coherencia.ambito_equipo(self.raiz))["total_pares"], 0)

    def test_lote_todo_o_nada(self) -> None:
        lote = self.raiz / "lote.yaml"
        pares = """\
            ambito: equipo
            pares:
              - decision: ADR-EQ-002
                doc: decisiones:ADR-010
                relacion: choca
                cita_documento: los servicios no implementan reintentos propios
                cita_decision: Los reintentos se aplican solo en operaciones idempotentes
                criterios: [EQ-002.2]
                explicacion: Arquitectura centraliza los reintentos en el gateway.
              - {decision: ADR-EQ-002, doc: decisiones:ADR-011, relacion: sin_relacion}
              - {decision: ADR-EQ-003, doc: decisiones:ADR-010, relacion: sin_relacion}
            """
        lote.write_text(textwrap.dedent(pares).replace("ADR-011, relacion: sin_relacion", "ADR-011, relacion: parecido"),
                        encoding="utf-8")
        codigo, salida = self.ejecutar("lote", str(lote))
        self.assertEqual(codigo, 1)
        self.assertIn("no se registró nada", salida)
        self.assertEqual(self.plan()["total_pares"], 6)
        lote.write_text(textwrap.dedent(pares), encoding="utf-8")
        codigo, salida = self.ejecutar("lote", str(lote))
        self.assertEqual(codigo, 0, salida)
        self.assertIn("3 par(es) registrado(s). Pares pendientes: 3. Criterios suspendidos: 1.", salida)
        self.assertIn("❌ 1 choque(s) · ⏳ 1 par(es) pendiente(s) de evaluar | EQ-002.2", (self.raiz / "equipo" / "COHERENCIA.md").read_text(encoding="utf-8"))

    def test_genera_coherencia_con_choque_y_suspension(self) -> None:
        self.registrar_todo()
        self.assertEqual(self.plan()["total_pares"], 0)

        codigo, salida = self.ejecutar("generar")
        self.assertEqual(codigo, 0, salida)
        texto = (self.raiz / "equipo" / "COHERENCIA.md").read_text(encoding="utf-8")
        self.assertIn("❌ 1 choque(s) | EQ-002.2", texto)
        self.assertIn("⚠️ 1 duplicación(es)", texto)
        self.assertIn("### ADR-EQ-002 × decisiones:ADR-010", texto)
        self.assertIn("decisiones@", texto)
        estado = json.loads((self.raiz / "equipo" / "estado" / "coherencia.json").read_text(encoding="utf-8"))
        self.assertEqual(estado["suspendidos"], {"ADR-EQ-002": ["EQ-002.2"]})

    def test_solo_reevalua_lo_que_cambia(self) -> None:
        self.registrar_todo()
        archivo_eq = self.raiz / "equipo" / "decisiones" / "ADR-EQ-002-resiliencia.md"

        # Cambiar el estado o la fecha no exige volver a evaluar.
        archivo_eq.write_text(archivo_eq.read_text(encoding="utf-8").replace("Propuesto", "Aprobado"), encoding="utf-8")
        self.assertEqual(self.plan()["total_pares"], 0)

        # Cambiar la decisión sí: se reevalúa ese ADR-EQ contra todo.
        archivo_eq.write_text(archivo_eq.read_text(encoding="utf-8").replace("máximo de intentos", "máximo de tres intentos"),
                              encoding="utf-8")
        plan = self.plan()
        self.assertEqual(plan["pendientes"], {"ADR-EQ-002": ["decisiones:ADR-010", "decisiones:ADR-011", "decisiones:ADR-012"]})

    def test_documento_de_arquitectura_modificado_o_retirado(self) -> None:
        self.registrar_todo()
        adr = self.origen / "adrs" / "0012-base-de-datos.md"
        adr.write_text(adr.read_text(encoding="utf-8").replace("PostgreSQL.", "PostgreSQL 16."), encoding="utf-8")
        commit(self.origen, "Cambia ADR-012")
        self.sincronizar()
        self.assertEqual(self.plan()["pendientes"], {"ADR-EQ-002": ["decisiones:ADR-012"], "ADR-EQ-003": ["decisiones:ADR-012"]})

        adr = self.origen / "adrs" / "0010-reintentos.md"
        adr.write_text(adr.read_text(encoding="utf-8").replace("Aprobado", "Reemplazado"), encoding="utf-8")
        commit(self.origen, "Reemplaza ADR-010")
        self.sincronizar()
        self.ejecutar("generar")
        estado = json.loads((self.raiz / "equipo" / "estado" / "coherencia.json").read_text(encoding="utf-8"))
        self.assertEqual(estado["suspendidos"], {}, "el choque con un ADR que dejó de estar vigente se descarta")


if __name__ == "__main__":
    unittest.main()
