"""Pruebas de la revisión de código: paquete, validaciones, cierre y consolidación del producto."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hallazgos  # noqa: E402
import productos  # noqa: E402
import revisar  # noqa: E402
import revision  # noqa: E402
import sync_arquitectura  # noqa: E402
from comun import RAIZ  # noqa: E402
from test_productos import crear_repo  # noqa: E402
from test_revisar import CONTROLADOR, README  # noqa: E402

ADR_TIMEOUTS = """\
# ADR-010: Timeouts obligatorios

## 2. Estado

Aprobado

## 5. Decisión

Toda llamada a un sistema externo define un timeout explícito de conexión y de lectura.

## 11. Regla rápida

> Ninguna llamada externa sin timeout explícito.
"""

AS_IS = "# AS IS\n\n" + "\n\n".join(f"## {s}\n\n[inferencia] Contenido de prueba." for s in revision.SECCIONES_AS_IS) + "\n"


class PruebaRevision(unittest.TestCase):

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        base = Path(self.temporal.name)
        self.raiz = base / "raiz"
        (self.raiz / "productos").mkdir(parents=True)
        shutil.copytree(RAIZ / "equipo", self.raiz / "equipo", ignore=shutil.ignore_patterns("coherencia.json", "COHERENCIA.md"))

        arquitectura = base / "arquitectura"
        crear_repo(arquitectura, "main", {"adrs/0010-timeouts.md": ADR_TIMEOUTS})
        (self.raiz / "harness.yaml").write_text(textwrap.dedent(f"""\
            version: 1
            arquitectura:
              fuentes:
                - id: decisiones
                  url: {arquitectura}
                  ref: main
                  ruta: adrs
                  tipo: adr
              estados:
                vigente: [Aprobado]
                pendiente: [Propuesto]
                no_vigente: [Reemplazado]
            """), encoding="utf-8")
        core = base / "fraude-core"
        crear_repo(core, "main", {"README.md": README, "src/main/java/EvaluacionController.java": CONTROLADOR})
        with contextlib.redirect_stdout(io.StringIO()):
            sync_arquitectura.main(["--raiz", str(self.raiz)])
            productos.main(["--raiz", str(self.raiz), "agregar", "--producto", "motor-fraudes", "--id", "fraude-core",
                            "--url", str(core), "--rama", "main", "--tipo", "propio"])
            self.automatica = revisar.revisar(self.raiz, "motor-fraudes", usar_sonar=False)

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def ejecutar(self, *argumentos: str) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = revision.main(["--raiz", str(self.raiz), *argumentos])
        return codigo, salida.getvalue()

    def hallazgo(self, *extra: str) -> tuple[int, str]:
        return self.ejecutar("hallazgo", "motor-fraudes", "fraude-core", "--categoria", "incumplimiento", "--severidad", "alta",
                             "--titulo", "Llamada sin timeout", "--detalle", "El cliente no define timeout.", *extra)

    def completar(self) -> None:
        """Evalúa todo: NO CUMPLE en ADR-010 y EQ-003.1, NO APLICA en el resto."""
        codigo, salida = self.hallazgo("--fuente", "decisiones:ADR-010", "--evidencia", "src/main/java/EvaluacionController.java:4",
                                       "--fragmento", 'System.out.println("evaluando");',
                                       "--cita-documento", "Ninguna llamada externa sin timeout explícito")
        self.assertEqual(codigo, 0, salida)
        codigo, salida = self.ejecutar("hallazgo", "motor-fraudes", "fraude-core", "--fuente", "ADR-EQ-003", "--criterio", "EQ-003.1",
                                       "--categoria", "diseño", "--severidad", "alta", "--titulo", "Cliente sin timeout",
                                       "--detalle", "Sin timeout.", "--evidencia", "src/main/java/EvaluacionController.java:3",
                                       "--fragmento", "public void evaluar()")
        self.assertEqual(codigo, 0, salida)
        for elemento in revision.lista_de_control(self.raiz, "propio"):
            no_cumple = elemento["clave"] in ("decisiones:ADR-010", "ADR-EQ-003|EQ-003.1")
            argumentos = ["evaluar", "motor-fraudes", "fraude-core", "--fuente", elemento["fuente"],
                          "--resultado", "NO CUMPLE" if no_cumple else "NO APLICA", "--motivo", "motivo de prueba"]
            if elemento["criterio"]:
                argumentos += ["--criterio", elemento["criterio"]]
            codigo, salida = self.ejecutar(*argumentos)
            self.assertEqual(codigo, 0, salida)
        carpeta = self.automatica["carpeta"]
        (carpeta / "revision" / "fraude-core-asis.md").write_text(AS_IS, encoding="utf-8")
        (carpeta / "borradores" / "fraude-core").mkdir(parents=True)
        for nombre in ("c4-contexto.md", "c4-contenedores.md"):
            (carpeta / "borradores" / "fraude-core" / nombre).write_text("# borrador\n", encoding="utf-8")

    def test_pendientes_y_paquete(self) -> None:
        codigo, salida = self.ejecutar("pendientes", "motor-fraudes")
        self.assertIn("fraude-core (propio): falta la revisión de código", salida)
        codigo, salida = self.ejecutar("paquete", "motor-fraudes", "fraude-core")
        self.assertEqual(codigo, 0, salida)
        paquete = (self.raiz / salida.split("Paquete: ")[1].strip()).read_text(encoding="utf-8")
        self.assertIn("`decisiones:ADR-010`", paquete)
        self.assertIn("Ninguna llamada externa sin timeout explícito.", paquete)
        self.assertIn("| `ADR-EQ-003` | EQ-003.1 |", paquete)
        self.assertNotIn("EQ-001.1", paquete.split("## Qué evaluar")[1], "los criterios automáticos no se piden de nuevo")
        self.assertIn("`src/main/java/EvaluacionController.java:1`", paquete, "señal de API expuesta")
        self.assertIn("Hallazgos automáticos ya registrados", paquete)

    def test_rechaza_evidencias_citas_y_fuentes_invalidas(self) -> None:
        casos = [
            (("--fuente", "decisiones:ADR-999", "--evidencia", "README.md:1", "--fragmento", "fraude-core"),
             "no es una fuente vigente"),
            (("--fuente", "decisiones:ADR-010", "--evidencia", "no-existe.java:1", "--fragmento", "algo de codigo",
              "--cita-documento", "Ninguna llamada externa sin timeout explícito"), "no existe en el commit revisado"),
            (("--fuente", "decisiones:ADR-010", "--evidencia", "src/main/java/EvaluacionController.java:99", "--fragmento", "algo de codigo",
              "--cita-documento", "Ninguna llamada externa sin timeout explícito"), "La línea 99 no existe"),
            (("--fuente", "decisiones:ADR-010", "--evidencia", "src/main/java/EvaluacionController.java:4", "--fragmento", "new RestTemplate()",
              "--cita-documento", "Ninguna llamada externa sin timeout explícito"), "El fragmento no aparece"),
            (("--fuente", "decisiones:ADR-010", "--evidencia", "src/main/java/EvaluacionController.java:4",
              "--fragmento", 'System.out.println("evaluando");'), "requiere --cita-documento"),
            (("--fuente", "decisiones:ADR-010", "--evidencia", "src/main/java/EvaluacionController.java:4",
              "--fragmento", 'System.out.println("evaluando");', "--cita-documento", "Los timeouts son opcionales en todos los casos"),
             "no aparece textualmente"),
            (("--fuente", "ADR-EQ-003", "--evidencia", "README.md:1", "--fragmento", "fraude-core"), "indicar --criterio"),
            (("--fuente", "ADR-EQ-001", "--criterio", "EQ-001.1", "--evidencia", "README.md:1", "--fragmento", "fraude-core"),
             "no es una fuente vigente ni un criterio de revisión de código"),
        ]
        for argumentos, mensaje in casos:
            codigo, salida = self.hallazgo(*argumentos)
            self.assertEqual(codigo, 1, argumentos)
            self.assertIn(mensaje, salida, argumentos)

    def test_cierre_exige_revision_completa(self) -> None:
        codigo, salida = self.ejecutar("cerrar", "motor-fraudes", "fraude-core")
        self.assertEqual(codigo, 1)
        self.assertIn("Faltan", salida)
        self.ejecutar("evaluar", "motor-fraudes", "fraude-core", "--fuente", "decisiones:ADR-010", "--resultado", "NO CUMPLE",
                      "--motivo", "sin timeout")
        for elemento in revision.lista_de_control(self.raiz, "propio")[1:]:
            argumentos = ["evaluar", "motor-fraudes", "fraude-core", "--fuente", elemento["fuente"], "--resultado", "NO APLICA", "--motivo", "x"]
            if elemento["criterio"]:
                argumentos += ["--criterio", elemento["criterio"]]
            self.ejecutar(*argumentos)
        codigo, salida = self.ejecutar("cerrar", "motor-fraudes", "fraude-core")
        self.assertIn("NO CUMPLE sin hallazgo registrado: decisiones:ADR-010", salida)

    def test_cierre_actualiza_registro_ficha_y_producto(self) -> None:
        registro = hallazgos.cargar(self.raiz, "motor-fraudes")
        registro["hallazgos"]["sonar-prueba"] = {
            "id": "H-0900", "huella": "sonar-prueba", "repo": "fraude-core", "rama": "main", "estado": "abierto", "origen": "sonar",
            "nivel": 4, "fuente": "sonar:java:S106", "criterio": None, "severidad": "alta", "modo": "vigente", "titulo": "System.out",
            "evidencia": [{"archivo": "src/main/java/EvaluacionController.java", "linea": 4}], "revisiones": [], "triaje": None}
        hallazgos.guardar(self.raiz, "motor-fraudes", registro)

        self.completar()
        codigo, salida = self.ejecutar("cerrar", "motor-fraudes", "fraude-core", "--archivos-leidos", "12")
        self.assertEqual(codigo, 0, salida)

        registro = hallazgos.cargar(self.raiz, "motor-fraudes")
        de_revision = [h for h in registro["hallazgos"].values() if h["origen"] == "revision"]
        self.assertEqual(len(de_revision), 2)
        nivel_1 = next(h for h in de_revision if h["nivel"] == 1)
        self.assertEqual(nivel_1["modo"], "vigente")
        self.assertEqual(registro["hallazgos"]["sonar-prueba"]["absorbido_por"], nivel_1["id"],
                         "el issue de Sonar en la misma línea se reporta una sola vez, en el nivel más alto")
        self.assertEqual(registro["repos"]["fraude-core"]["codigo"]["archivos_leidos"], 12)

        ficha = (self.raiz / "productos" / "motor-fraudes" / "as-is" / "fraude-core.md").read_text(encoding="utf-8")
        self.assertIn("## Arquitectura real", ficha)
        self.assertIn("| decisiones:ADR-010 | ❌ NO CUMPLE | vigente |", ficha)
        self.assertIn("Veredicto: **NO PASA (1 bloqueante(s) o alto(s) vigente(s))**", ficha)
        self.assertIn("fraude-core (propio): al día", self.ejecutar("pendientes", "motor-fraudes")[1])

        narrativa = self.raiz / "narrativa.md"
        narrativa.write_text("## Visión del producto\n\nTexto del producto.\n", encoding="utf-8")
        codigo, salida = self.ejecutar("producto", "motor-fraudes", "--narrativa", str(narrativa))
        self.assertEqual(codigo, 0, salida)
        producto = (self.raiz / "productos" / "motor-fraudes" / "as-is" / "PRODUCTO.md").read_text(encoding="utf-8")
        self.assertIn("| 1 | decisiones:ADR-010 | ❌ |", producto)
        self.assertIn("Nivel 1 · decisiones:ADR-010: 1 hallazgo(s)", producto)
        self.assertIn("Texto del producto.", producto)


if __name__ == "__main__":
    unittest.main()
