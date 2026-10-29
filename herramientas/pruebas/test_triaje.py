"""Pruebas del triaje: archivo editable, validaciones, decisiones en grupo, agenda y calibración."""

from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hallazgos  # noqa: E402
import revisar  # noqa: E402
import triaje  # noqa: E402


def hallazgo(numero: int, **cambios) -> dict:
    datos = {"id": f"H-{numero:04d}", "huella": f"h{numero}", "repo": "fraude-core", "rama": "main", "estado": "abierto",
             "origen": "verificacion", "nivel": 3, "fuente": "ADR-EQ-007", "criterio": "EQ-007.1", "severidad": "alta",
             "modo": "vigente", "titulo": f"Hallazgo {numero}", "evidencia": [{"archivo": "App.java", "linea": numero}],
             "revisiones": [], "triaje": None, "reaparecido": False, "ultima_vez": "2026-10-01"}
    datos.update(cambios)
    return datos


class PruebaTriaje(unittest.TestCase):

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporal.name)
        producto = self.raiz / "productos" / "motor-fraudes"
        producto.mkdir(parents=True)
        (producto / "producto.yaml").write_text("nombre: motor-fraudes\nrepos: []\n", encoding="utf-8")
        (self.raiz / "harness.yaml").write_text("version: 1\ncalibracion:\n  minimo_triados: 2\n  maximo_falsos_positivos: 0.2\n"
                                                "publicacion:\n  publicables: [EQ-002.1]\n", encoding="utf-8")
        vencida = (date.today() - timedelta(days=1)).isoformat()
        registro = {"version": 1, "siguiente_id": 10, "hallazgos": {
            "h1": hallazgo(1),
            "h2": hallazgo(2, severidad="media", origen="sonar", nivel=4, fuente="sonar:java:S1128", criterio=None),
            "h3": hallazgo(3, severidad="baja", origen="sonar", nivel=4, fuente="sonar:java:S1128", criterio=None),
            "h4": hallazgo(4, triaje={"decision": "deuda", "motivo": "x", "vence": vencida, "fecha": "2026-01-01"}),
            "h5": hallazgo(5, triaje={"decision": "confirmar", "motivo": None, "vence": None, "fecha": "2026-01-01"}),  # decisión antigua
            "h6": hallazgo(6, estado="corregido"),
            "h7": hallazgo(7, reaparecido=True, ultima_vez="2026-10-20",
                           triaje={"decision": "resolver", "motivo": None, "vence": None, "fecha": "2026-09-01"}),
        }}
        hallazgos.guardar(self.raiz, "motor-fraudes", registro)

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def ejecutar(self, *argumentos: str) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = triaje.main(["--raiz", str(self.raiz), *argumentos])
        return codigo, salida.getvalue()

    def generar(self) -> Path:
        codigo, salida = self.ejecutar("generar", "motor-fraudes")
        self.assertEqual(codigo, 0, salida)
        return self.raiz / salida.split("Triaje: ")[1].strip()

    def marcar(self, archivo: Path, id_hallazgo: str, columna: str, vence: str = "", motivo: str = "") -> None:
        lineas = archivo.read_text(encoding="utf-8").splitlines()
        encabezado = next(l for l in lineas if l.startswith("| ID "))
        columnas = [c.strip() for c in encabezado.strip().strip("|").split("|")]
        for i, linea in enumerate(lineas):
            if linea.startswith(f"| {id_hallazgo} "):
                celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
                celdas[columnas.index(columna)] = "x"
                celdas[columnas.index("Vence")] = vence
                celdas[columnas.index("Motivo")] = motivo
                lineas[i] = "| " + " | ".join(celdas) + " |"
        archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    def registro(self) -> dict[str, dict]:
        return {h["id"]: h for h in hallazgos.cargar(self.raiz, "motor-fraudes")["hallazgos"].values()}

    def test_genera_solo_lo_que_requiere_decision(self) -> None:
        texto = self.generar().read_text(encoding="utf-8")
        ids = re.findall(r"^\| (H-\d+) ", texto, re.MULTILINE)
        self.assertEqual(ids, ["H-0004", "H-0007", "H-0001", "H-0002", "H-0003"],
                         "primero lo que requiere atención; sin los ya decididos ni los corregidos")
        self.assertIn("deuda: deuda vencida el", texto)
        self.assertIn("resolver: reapareció después de corregirse", texto)
        self.assertIn("| Resolver | Conversar | Deuda | Falso positivo |", texto)

    def test_aplicar_registra_y_genera_agenda(self) -> None:
        archivo = self.generar()
        self.marcar(archivo, "H-0001", "Falso positivo", motivo="Es una herramienta de consola")
        self.marcar(archivo, "H-0002", "Deuda")
        self.marcar(archivo, "H-0003", "Conversar")
        codigo, salida = self.ejecutar("aplicar", str(archivo))
        self.assertEqual(codigo, 0, salida)
        self.assertIn("3 decisión(es)", salida)
        registro = self.registro()
        self.assertEqual(registro["H-0001"]["triaje"]["decision"], "falso-positivo")
        self.assertEqual(registro["H-0002"]["triaje"]["vence"], (date.today() + timedelta(days=90)).isoformat(),
                         "una deuda sin fecha vence a los 90 días")
        self.assertEqual(registro["H-0004"]["triaje"]["decision"], "deuda", "las filas sin marcar no cambian")
        self.assertNotIn("historial_triaje", registro["H-0004"])
        agenda = next((self.raiz / "productos" / "motor-fraudes" / "triaje").glob("agenda-*.md")).read_text(encoding="utf-8")
        self.assertIn("## sonar:java:S1128 (1 hallazgo(s))", agenda)
        self.assertIn("> Aplicado el", archivo.read_text(encoding="utf-8"))

    def test_aplicar_es_todo_o_nada(self) -> None:
        casos = [
            (("H-0001", "Falso positivo", "", ""), "un falso positivo requiere motivo"),
            (("H-0001", "Deuda", "2020-01-01", ""), "debe ser una fecha futura"),
            (("H-0001", "Deuda", "31-12-2027", ""), "no tiene el formato AAAA-MM-DD"),
            (("H-0001", "Resolver", "2027-01-01", ""), "solo corresponde a una deuda"),
        ]
        for (id_hallazgo, columna, vence, motivo), mensaje in casos:
            archivo = self.generar()
            self.marcar(archivo, "H-0002", "Resolver")
            self.marcar(archivo, id_hallazgo, columna, vence, motivo)
            codigo, salida = self.ejecutar("aplicar", str(archivo))
            self.assertEqual(codigo, 1, mensaje)
            self.assertIn(mensaje, salida)
            self.assertIsNone(self.registro()["H-0002"]["triaje"], "si una fila falla, no se aplica ninguna")

        archivo = self.generar()
        self.marcar(archivo, "H-0001", "Resolver")
        self.marcar(archivo, "H-0001", "Conversar")
        codigo, salida = self.ejecutar("aplicar", str(archivo))
        self.assertIn("más de una decisión marcada", salida)

    def test_decision_en_grupo_y_veredicto(self) -> None:
        codigo, salida = self.ejecutar("grupo", "motor-fraudes", "--decision", "deuda", "--fuente", "sonar:",
                                       "--severidad", "media,baja", "--motivo", "Limpieza gradual", "--simular")
        self.assertIn("Se aplicaría 'deuda' a 2 hallazgo(s): H-0002, H-0003", salida)
        self.assertIsNone(self.registro()["H-0002"]["triaje"])
        self.ejecutar("grupo", "motor-fraudes", "--decision", "deuda", "--fuente", "sonar:", "--severidad", "media,baja",
                      "--motivo", "Limpieza gradual")
        self.assertEqual(self.registro()["H-0003"]["triaje"]["motivo"], "Limpieza gradual")

        registro = hallazgos.cargar(self.raiz, "motor-fraudes")
        self.assertTrue(revisar.veredicto(registro, "fraude-core", "main").startswith("NO PASA (4"),
                        "cuentan H-0001 (sin decisión), H-0004 (deuda vencida), H-0005 (confirmado) y H-0007 (resolver)")
        self.ejecutar("grupo", "motor-fraudes", "--decision", "falso-positivo", "--motivo", "prueba")
        registro = hallazgos.cargar(self.raiz, "motor-fraudes")
        self.assertEqual(revisar.veredicto(registro, "fraude-core", "main"), "NO PASA (1 bloqueante(s) o alto(s) vigente(s))",
                         "solo queda H-0005, confirmado")

    def test_calibracion(self) -> None:
        self.ejecutar("grupo", "motor-fraudes", "--decision", "falso-positivo", "--fuente", "sonar:", "--motivo", "regla ruidosa")
        codigo, salida = self.ejecutar("calibracion")
        self.assertIn("| sonar:java:S1128 | 2 | 2 | 100% | ruidosa: ajustar | no |", salida)
        self.assertIn("| EQ-007.1 | 3 | 0 | 0% | lista para publicar | no |", salida, "H-0004, H-0005 y H-0007 tienen decisión")

    def test_publicables_conserva_comentarios(self) -> None:
        (self.raiz / "harness.yaml").write_text("# cabecera\nversion: 1\npublicacion:\n  # comentario\n  publicables: []\n",
                                                encoding="utf-8")
        codigo, salida = self.ejecutar("publicables", "--agregar", "EQ-002.1")
        self.assertEqual(codigo, 0, salida)
        texto = (self.raiz / "harness.yaml").read_text(encoding="utf-8")
        self.assertIn("publicables: [EQ-002.1]", texto)
        self.assertIn("# comentario", texto)
        self.assertEqual(self.ejecutar("publicables", "--agregar", "EQ-002.1")[0], 1)
        self.ejecutar("publicables", "--quitar", "EQ-002.1")
        self.assertIn("publicables: []", (self.raiz / "harness.yaml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
