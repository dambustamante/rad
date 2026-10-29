"""Pruebas de los ADR de producto: creación, validación, excepciones y coherencia."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import adr  # noqa: E402
import coherencia  # noqa: E402
import hallazgos  # noqa: E402
import productos  # noqa: E402
import revisar  # noqa: E402
import revision  # noqa: E402
import sync_arquitectura  # noqa: E402
from comun import RAIZ  # noqa: E402
from test_productos import crear_repo  # noqa: E402
from test_revisar import CONTROLADOR, README  # noqa: E402
from test_revision import ADR_TIMEOUTS  # noqa: E402

FUTURO = (date.today() + timedelta(days=180)).isoformat()
PASADO = (date.today() - timedelta(days=1)).isoformat()


class PruebaAdrProducto(unittest.TestCase):

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        base = Path(self.temporal.name)
        self.raiz = base / "raiz"
        (self.raiz / "productos").mkdir(parents=True)
        shutil.copytree(RAIZ / "equipo", self.raiz / "equipo", ignore=shutil.ignore_patterns("estado", "COHERENCIA.md", "INDICE.md"))
        arquitectura = base / "arquitectura"
        crear_repo(arquitectura, "main", {"adrs/0010-timeouts.md": ADR_TIMEOUTS})
        (self.raiz / "harness.yaml").write_text(textwrap.dedent(f"""\
            version: 1
            arquitectura:
              fuentes:
                - {{id: decisiones, url: {arquitectura}, ref: main, ruta: adrs, tipo: adr}}
              estados: {{vigente: [Aprobado], pendiente: [Propuesto], no_vigente: [Reemplazado]}}
            """), encoding="utf-8")
        core = base / "fraude-core"
        crear_repo(core, "main", {"README.md": README, "src/main/java/EvaluacionController.java": CONTROLADOR})
        with contextlib.redirect_stdout(io.StringIO()):
            sync_arquitectura.main(["--raiz", str(self.raiz)])
            productos.main(["--raiz", str(self.raiz), "agregar", "--producto", "motor-fraudes", "--id", "fraude-core",
                            "--url", str(core), "--rama", "main", "--tipo", "propio"])

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def ejecutar(self, *argumentos: str) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = adr.main(["--raiz", str(self.raiz), *argumentos])
        return codigo, salida.getvalue()

    def crear(self, tipo: str, titulo: str, reemplazos: dict[str, str], *extra: str) -> Path:
        codigo, salida = self.ejecutar("nuevo", "motor-fraudes", "--tipo", tipo, "--titulo", titulo, *extra)
        self.assertEqual(codigo, 0, salida)
        archivo = self.raiz / salida.split("Creado: ")[1].strip()
        texto = archivo.read_text(encoding="utf-8")
        for a, b in reemplazos.items():
            self.assertIn(a, texto)
            texto = texto.replace(a, b, 1)
        archivo.write_text(texto, encoding="utf-8")
        return archivo

    def decision(self) -> Path:
        return self.crear("decision", "Latencia de evaluación", {
            "> <Una o dos frases que resumen la decisión.>": "> Toda evaluación responde en menos de 150 ms.",
            "| `MF-001.1` | | revisión de código |": "| `MF-001.1` | La evaluación tiene un timeout de 150 ms | revisión de código |",
            "`bloqueante` \\| `alta` \\| `media` \\| `baja` |": "alta |",
            "## 2. Estado\n\nPropuesto": "## 2. Estado\n\nAprobado",
        })

    def excepcion(self, criterios: str, vence: str, referencia: str = "—") -> Path:
        return self.crear("excepcion", "Sin C4 hasta el reemplazo", {
            "## 2. Estado\n\nPropuesto": "## 2. Estado\n\nAprobado",
            "- **Repositorios:** todos": "- **Repositorios:** fraude-core",
            "- **Criterios exceptuados:** —": f"- **Criterios exceptuados:** {criterios}",
            "- **Vence:** —": f"- **Vence:** {vence}",
            "- **Referencia de aprobación de arquitectura:** —": f"- **Referencia de aprobación de arquitectura:** {referencia}",
        })

    def test_sigla_y_numeracion(self) -> None:
        self.assertEqual(self.decision().name, "ADR-MF-001-latencia-de-evaluacion.md")
        archivo = self.crear("decision", "Centralizar clientes", {})
        self.assertTrue(archivo.name.startswith("ADR-MF-002-"))
        texto = archivo.read_text(encoding="utf-8")
        self.assertNotIn("ÁMBITO", texto, "la plantilla común queda sin marcadores de ámbito")
        self.assertIn("`MF-002.1`", texto)
        self.assertIn("## 14. Tipo y alcance\n", texto)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.ejecutar("nuevo", "motor-fraudes", "--tipo", "mejora", "--titulo", "x")

    def test_adr_del_equipo(self) -> None:
        codigo, salida = self.ejecutar("nuevo", "equipo", "--tipo", "decision", "--titulo", "Versionado de APIs")
        self.assertEqual(codigo, 0, salida)
        archivo = self.raiz / salida.split("Creado: ")[1].strip().splitlines()[0]
        self.assertEqual(archivo.name, "ADR-EQ-010-versionado-de-apis.md", "toma el siguiente número libre del equipo")
        texto = archivo.read_text(encoding="utf-8")
        self.assertTrue(texto.startswith("# ADR-EQ-010: Versionado de APIs"))
        self.assertIn("| `EQ-010.1` | | `automática` \\| `revisión de código` |", texto)
        self.assertNotIn("## 14.", texto, "la sección 14 es solo de los productos")
        self.assertNotIn("ÁMBITO", texto)
        self.assertEqual(self.ejecutar("nuevo", "equipo", "--tipo", "excepcion", "--titulo", "x")[0], 1)

    def test_definicion_de_terminado_verificable(self) -> None:
        import jira
        self.decision()
        registro = hallazgos.cargar(self.raiz, "motor-fraudes")
        registro["hallazgos"]["x"] = {"id": "H-0001", "repo": "fraude-core", "rama": "main", "estado": "corregido"}
        hallazgos.guardar(self.raiz, "motor-fraudes", registro)
        borradores = self.raiz / "productos" / "motor-fraudes" / "historias" / "borradores"
        borradores.mkdir(parents=True)
        hace_5_dias = (date.today() - timedelta(days=5)).isoformat()
        (borradores / "001-tarea.md").write_text(f"---\ntipo_incidencia: tarea\nestado: creada\njira: FRAUD-1\n"
                                                 f"hallazgos: [H-0001]\ncreada: '{hace_5_dias}'\n---\n# Agregar timeout\n", encoding="utf-8")
        (borradores / "002-spike.md").write_text(f"---\ntipo_incidencia: spike\nestado: creada\njira: FRAUD-2\n"
                                                 f"creada: '{hace_5_dias}'\n---\n# Evaluar colas\n", encoding="utf-8")
        resultado = {t["criterio"]: t for t in jira.terminado(self.raiz, "motor-fraudes")}
        self.assertTrue(resultado["EQ-008.5"]["cumple"], "todos los hallazgos de origen están corregidos")
        self.assertFalse(resultado["EQ-008.8"]["cumple"])
        self.assertTrue(resultado["EQ-008.8"]["vencido"])
        archivo = next((self.raiz / "productos" / "motor-fraudes" / "decisiones").glob("ADR-MF-001-*.md"))
        archivo.write_text(archivo.read_text(encoding="utf-8").replace("- **Historias de origen:** —", "- **Historias de origen:** FRAUD-2"),
                           encoding="utf-8")
        resultado = {t["criterio"]: t for t in jira.terminado(self.raiz, "motor-fraudes")}
        self.assertTrue(resultado["EQ-008.8"]["cumple"], "un ADR de producto propuesto cita el Spike")

    def test_validar(self) -> None:
        self.decision()
        self.excepcion("EQ-006.1, EQ-099.9", "")
        codigo, salida = self.ejecutar("validar", "motor-fraudes")
        self.assertEqual(codigo, 1)
        self.assertIn("ADR-MF-001: válido", salida)
        self.assertIn("el criterio EQ-099.9 no existe", salida)
        self.assertIn("una excepción necesita fecha de vencimiento", salida)

    def test_excepciones_en_la_revision(self) -> None:
        self.decision()
        self.excepcion("EQ-006.1, EQ-002.1", FUTURO)
        self.excepcion("decisiones:ADR-010", FUTURO)  # sin referencia de arquitectura: inactiva

        filas = {f["id"]: f for f in adr.listar(self.raiz, "motor-fraudes")}
        self.assertEqual(filas["ADR-MF-001"]["efecto"], "se evalúa")
        niveles = {e["clave"]: e["nivel"] for e in revision.lista_de_control(self.raiz, "propio", "motor-fraudes", "fraude-core")}
        self.assertEqual((niveles["ADR-MF-001|MF-001.1"], niveles["ADR-EQ-002|EQ-002.2"]), (4, 3),
                         "las decisiones del producto son el nivel 4, después de las del equipo")
        self.assertEqual(filas["ADR-MF-002"]["efecto"], "activa")
        self.assertEqual(filas["ADR-MF-003"]["efecto"], "inactiva: falta la aprobación de arquitectura")
        self.assertTrue((self.raiz / "productos" / "motor-fraudes" / "decisiones" / "INDICE.md").exists())

        with contextlib.redirect_stdout(io.StringIO()):
            resultado = revisar.revisar(self.raiz, "motor-fraudes", usar_sonar=False)
        verificaciones = {v["criterio"]: v for v in resultado["resultados"][0]["verificaciones"]}
        self.assertEqual(verificaciones["EQ-006.1"]["resultado"], "NO APLICA")
        self.assertIn("excepción ADR-MF-002 vigente hasta", verificaciones["EQ-006.1"]["motivo"])
        self.assertEqual(verificaciones["EQ-006.2"]["resultado"], "NO CUMPLE", "solo se exceptúa lo declarado")

        control = {e["clave"]: e for e in revision.lista_de_control(self.raiz, "propio", "motor-fraudes", "fraude-core")}
        self.assertIn("ADR-MF-001|MF-001.1", control, "los criterios del producto se evalúan en el nivel 3")
        self.assertIn("excepción ADR-MF-002", control["ADR-EQ-002|EQ-002.1"]["exceptuado"])
        self.assertNotIn("exceptuado", control["decisiones:ADR-010"], "la excepción a arquitectura sin aprobación no surte efecto")
        self.assertIn("decisiones:ADR-010", adr.excepciones_pendientes(self.raiz, "motor-fraudes", "fraude-core"))

        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = revision.main(["--raiz", str(self.raiz), "evaluar", "motor-fraudes", "fraude-core", "--fuente", "ADR-EQ-002",
                                    "--criterio", "EQ-002.1", "--resultado", "CUMPLE", "--motivo", "x"])
        self.assertEqual(codigo, 1)
        self.assertIn("no se evalúa: excepción ADR-MF-002", salida.getvalue())

    def test_excepcion_vencida_no_surte_efecto(self) -> None:
        self.excepcion("EQ-006.1", PASADO)
        self.assertEqual(adr.excepciones_activas(self.raiz, "motor-fraudes", "fraude-core"), {})
        self.assertEqual(adr.listar(self.raiz, "motor-fraudes")[0]["efecto"], "vencida")

    def test_coherencia_del_producto_con_arquitectura_y_equipo(self) -> None:
        self.decision()
        self.excepcion("EQ-006.1", FUTURO)
        ambito = coherencia.ambito_producto(self.raiz, "motor-fraudes")
        self.assertEqual(set(ambito.sujetos), {"ADR-MF-001"}, "las excepciones no se verifican por coherencia")
        self.assertIn("decisiones:ADR-010", ambito.referencias)
        self.assertIn("equipo:ADR-EQ-002", ambito.referencias)
        self.assertEqual(coherencia.preparar(ambito)["total_pares"], len(ambito.referencias))

        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = coherencia.main(["--raiz", str(self.raiz), "registrar", "--ambito", "motor-fraudes", "--decision", "ADR-MF-001",
                                      "--doc", "decisiones:ADR-010", "--relacion", "choca",
                                      "--cita-documento", "Ninguna llamada externa sin timeout explícito",
                                      "--cita-decision", "Toda evaluación responde en menos de 150 ms",
                                      "--criterios", "MF-001.1", "--explicacion", "Prueba de choque."])
            self.assertEqual(codigo, 0, salida.getvalue())
            coherencia.main(["--raiz", str(self.raiz), "generar", "--ambito", "motor-fraudes"])
        texto = (self.raiz / "productos" / "motor-fraudes" / "decisiones" / "COHERENCIA.md").read_text(encoding="utf-8")
        self.assertIn("❌ 1 choque(s) · ⏳", texto, "se ven el choque y los pares que faltan")
        self.assertIn("| MF-001.1 |", texto)
        self.assertEqual(coherencia.suspendidos(self.raiz, "motor-fraudes").get("ADR-MF-001"), ["MF-001.1"])
        control = {e["clave"] for e in revision.lista_de_control(self.raiz, "propio", "motor-fraudes", "fraude-core")}
        self.assertNotIn("ADR-MF-001|MF-001.1", control, "un criterio suspendido por coherencia no se evalúa")

    def test_indices(self) -> None:
        import indices
        self.decision()
        indices.regenerar(self.raiz)
        equipo = (self.raiz / "equipo" / "INDICE.md").read_text(encoding="utf-8")
        self.assertIn("| [ADR-EQ-006](decisiones/ADR-EQ-006-documentacion-de-macro-a-micro.md) |", equipo)
        producto = (self.raiz / "productos" / "motor-fraudes" / "INDICE.md").read_text(encoding="utf-8")
        self.assertIn("- **Sigla de sus ADR:** MF", producto)
        self.assertIn("| fraude-core | propio | activo | — | pendiente | 0 | — |", producto)
        self.assertIn("| [ADR-MF-001](decisiones/ADR-MF-001-latencia-de-evaluacion.md) | decision | Aprobado | se evalúa |", producto)


if __name__ == "__main__":
    unittest.main()
