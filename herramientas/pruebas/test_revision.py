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
from test_sync_arquitectura import commit  # noqa: E402

ADR_TIMEOUTS = """\
# ADR-010: Timeouts obligatorios

## 2. Estado

Aprobado

## 5. Decisión

Toda llamada a un sistema externo define un timeout explícito de conexión y de lectura.

## 11. Regla rápida

> Ninguna llamada externa sin timeout explícito.
"""

AS_IS = ("# AS IS\n\n## Propósito\n\n[inferencia] Contenido de prueba.\n\n" + "\n\n".join(
    f"## {s}\n\n| Aspecto | Qué hay | Evidencia |\n|---|---|---|\n| Prueba | Contenido de prueba | [inferencia] |"
    for s in revision.SECCIONES_AS_IS[1:]) + "\n")


class PruebaRevision(unittest.TestCase):

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
        core = self.core = base / "fraude-core"
        crear_repo(core, "main", {"README.md": README, "src/main/java/EvaluacionController.java": CONTROLADOR})
        with contextlib.redirect_stdout(io.StringIO()):
            sync_arquitectura.main(["--raiz", str(self.raiz)])
            productos.crear(self.raiz, "motor-fraudes", None, "heredado")
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
        """Evalúa todo: NO CUMPLE en ADR-010 y EQ-002.1, NO APLICA en el resto."""
        codigo, salida = self.hallazgo("--fuente", "decisiones:ADR-010", "--evidencia", "src/main/java/EvaluacionController.java:4",
                                       "--fragmento", 'System.out.println("evaluando");',
                                       "--cita-documento", "Ninguna llamada externa sin timeout explícito")
        self.assertEqual(codigo, 0, salida)
        codigo, salida = self.ejecutar("hallazgo", "motor-fraudes", "fraude-core", "--fuente", "ADR-EQ-002", "--criterio", "EQ-002.1",
                                       "--categoria", "diseño", "--severidad", "alta", "--titulo", "Cliente sin timeout",
                                       "--detalle", "Sin timeout.", "--evidencia", "src/main/java/EvaluacionController.java:3",
                                       "--fragmento", "public void evaluar()")
        self.assertEqual(codigo, 0, salida)
        for elemento in revision.lista_de_control(self.raiz, "propio"):
            no_cumple = elemento["clave"] in ("decisiones:ADR-010", "ADR-EQ-002|EQ-002.1")
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
        self.assertIn("- `EQ-002.1` (alta): Cada cliente de un sistema externo tiene timeout", paquete)
        self.assertIn("- `decisiones:ADR-010` Timeouts obligatorios: Ninguna llamada externa sin timeout explícito.", paquete)
        self.assertNotIn("EQ-006.1", paquete.split("## Qué evaluar")[1], "los criterios automáticos no se piden de nuevo")
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
              "--fragmento", 'System.out.println("evaluando");'), "requiere la cita del documento incumplido"),
            (("--fuente", "decisiones:ADR-010", "--evidencia", "src/main/java/EvaluacionController.java:4",
              "--fragmento", 'System.out.println("evaluando");', "--cita-documento", "Los timeouts son opcionales en todos los casos"),
             "no aparece textualmente"),
            (("--fuente", "ADR-EQ-002", "--evidencia", "README.md:1", "--fragmento", "fraude-core"), "indicar --criterio"),
            (("--fuente", "ADR-EQ-006", "--criterio", "EQ-006.1", "--evidencia", "README.md:1", "--fragmento", "fraude-core"),
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
        self.assertIn("### Arquitectura real", ficha)
        self.assertTrue(ficha.startswith("# fraude-core · Revisión de arquitectura"))
        self.assertIn("| motor-fraudes |", ficha)
        self.assertIn("**No aprobado**", ficha)
        self.assertIn("fraude-core no cumple 1 regla(s) vigente(s): Timeouts obligatorios.", ficha, "conclusión automática")
        self.assertIn("| ADR de arquitectura | No cumple | 1 | 0 |", ficha)
        self.assertIn("| ADR de equipo (en Propuesto) | Informativo |", ficha)
        self.assertIn("| Sonar |", ficha)
        self.assertIn("| 1 | Llamada sin timeout | Timeouts obligatorios | Alta |", ficha)
        self.assertIn("## Decisiones pendientes", ficha)
        self.assertIn("| decisiones:ADR-010 | No cumple | Sí | motivo de prueba | [H-0007](#h-0007) |", ficha)
        self.assertIn('<a id="h-0007"></a>H-0007', ficha, "el enlace llega a la fila del hallazgo")
        for icono in ("🚫", "💬", "✅", "🔍", "🔹"):
            self.assertNotIn(icono, ficha, "sin íconos")
        orden = ["## Conclusión", "## Estado por fuente", "## Riesgos principales", "## Decisiones pendientes", "## Anexo A. Hallazgos",
                 "## Anexo B. Cómo es hoy", "## Anexo C. Componentes", "## Anexo D. Cumplimiento regla por regla", "## Anexo E. Datos técnicos"]
        self.assertEqual([ficha.index(s) for s in orden], sorted(ficha.index(s) for s in orden), "de lo ejecutivo a lo técnico")
        self.assertIn("**[hecho]** verificado en el código", ficha)
        self.assertNotIn("## Hallazgos automáticos abiertos", ficha)
        self.assertIn("### Verificaciones automáticas", ficha)
        archivo_ficha = revision.regenerar_fichas(self.raiz, "motor-fraudes", "fraude-core")[0]
        self.assertEqual(archivo_ficha.read_text(encoding="utf-8"), ficha, "recomponer no cambia una ficha al día")
        self.assertNotIn("sobre el commit", ficha)
        self.assertIn("fraude-core (propio): al día", self.ejecutar("pendientes", "motor-fraudes")[1])

        narrativa = self.raiz / "narrativa.md"
        narrativa.write_text("## Visión del producto\n\nTexto del producto.\n", encoding="utf-8")
        codigo, salida = self.ejecutar("producto", "motor-fraudes", "--narrativa", str(narrativa))
        self.assertEqual(codigo, 0, salida)
        producto = (self.raiz / "productos" / "motor-fraudes" / "as-is" / "PRODUCTO.md").read_text(encoding="utf-8")
        self.assertIn("| 1 | decisiones:ADR-010 | 🚫 |", producto)
        self.assertIn("Nivel 1 · decisiones:ADR-010: 1 hallazgo(s)", producto)
        self.assertIn("Texto del producto.", producto)

    def test_registro_en_lote(self) -> None:
        carpeta = self.automatica["carpeta"] / "revision"
        carpeta.mkdir(parents=True, exist_ok=True)
        lote = carpeta / "fraude-core-lote.yaml"
        evaluaciones = [{"fuente": e["fuente"], "criterio": e["criterio"], "resultado": "NO APLICA", "motivo": "prueba"}
                        for e in revision.lista_de_control(self.raiz, "propio", "motor-fraudes", "fraude-core")
                        if e["clave"] != "decisiones:ADR-010"]
        evaluaciones.append({"fuente": "decisiones:ADR-010", "resultado": "NO CUMPLE", "motivo": "sin timeout"})
        hallazgo_valido = {"fuente": "decisiones:ADR-010", "categoria": "incumplimiento", "severidad": "alta",
                           "titulo": "Llamada sin timeout", "detalle": "El cliente no define timeout.",
                           "evidencia": ["src/main/java/EvaluacionController.java:4"],
                           "fragmento": 'System.out.println("evaluando");',
                           "cita_documento": "Ninguna llamada externa sin timeout explícito"}
        invalidos = [{**hallazgo_valido, "fragmento": "new RestTemplate()"},
                     {**hallazgo_valido, "evidencia": ["no-existe.java:1"]}]
        import yaml
        lote.write_text(yaml.safe_dump({"evaluaciones": evaluaciones, "hallazgos": [hallazgo_valido, *invalidos]},
                                       allow_unicode=True), encoding="utf-8")
        codigo, salida = self.ejecutar("registrar", "motor-fraudes", "fraude-core")
        self.assertEqual(codigo, 1)
        self.assertIn("El lote tiene 2 error(es); no se registró nada", salida)
        self.assertIn("hallazgos[2]", salida)
        self.assertIn("hallazgos[3]", salida, "se informan todos los errores juntos")
        self.assertFalse((carpeta / "fraude-core.json").exists(), "nada registrado si hay errores")

        lote.write_text(yaml.safe_dump({"evaluaciones": evaluaciones[:3], "hallazgos": [hallazgo_valido]},
                                       allow_unicode=True), encoding="utf-8")
        codigo, salida = self.ejecutar("registrar", "motor-fraudes", "fraude-core")
        self.assertEqual(codigo, 0, salida)
        self.assertIn("Faltan", salida, "informa lo que queda por evaluar")
        lote.write_text(yaml.safe_dump({"evaluaciones": evaluaciones, "hallazgos": [hallazgo_valido]},
                                       allow_unicode=True), encoding="utf-8")
        codigo, salida = self.ejecutar("registrar", "motor-fraudes", "fraude-core")
        self.assertEqual(codigo, 0, salida)
        self.assertNotIn("Faltan", salida)
        trabajo = json.loads((carpeta / "fraude-core.json").read_text(encoding="utf-8"))
        self.assertEqual(len(trabajo["hallazgos"]), 1, "registrar el mismo lote dos veces no duplica hallazgos")

    def test_cerrar_registra_el_lote(self) -> None:
        carpeta = self.automatica["carpeta"]
        (carpeta / "revision").mkdir(parents=True, exist_ok=True)
        evaluaciones = [{"fuente": e["fuente"], "criterio": e["criterio"], "resultado": "NO APLICA", "motivo": "prueba"}
                        for e in revision.lista_de_control(self.raiz, "propio", "motor-fraudes", "fraude-core")]
        import yaml
        (carpeta / "revision" / "fraude-core-lote.yaml").write_text(yaml.safe_dump({"evaluaciones": evaluaciones}), encoding="utf-8")
        (carpeta / "revision" / "fraude-core-asis.md").write_text(AS_IS, encoding="utf-8")
        codigo, salida = self.ejecutar("cerrar", "motor-fraudes", "fraude-core", "--archivos-leidos", "3")
        self.assertEqual(codigo, 0, salida)
        self.assertIn("cerrada", salida, "un solo comando registra el lote y cierra")

    def test_componentes_validados_y_consolidados(self) -> None:
        import terceros
        import yaml
        terceros.nuevo(self.raiz, "motor-fraudes", "buro-credito", "Buró de crédito")
        terceros.nuevo(self.raiz, "motor-fraudes", "listas-sanciones", "Listas de sanciones")
        carpeta = self.automatica["carpeta"]
        (carpeta / "revision").mkdir(parents=True, exist_ok=True)
        lote = carpeta / "revision" / "fraude-core-lote.yaml"
        evaluaciones = [{"fuente": e["fuente"], "criterio": e["criterio"], "resultado": "NO APLICA", "motivo": "prueba"}
                        for e in revision.lista_de_control(self.raiz, "propio", "motor-fraudes", "fraude-core")]
        evidencia = ["src/main/java/EvaluacionController.java:3"]
        componentes = [
            {"nombre": "Buró de crédito", "tipo": "integracion", "tecnologia": "HTTPS", "detalle": "BURO_URL",
             "direccion": "saliente", "tercero": "buro-credito", "evidencia": evidencia},
            {"nombre": "Core bancario", "tipo": "integracion", "tecnologia": "HTTPS", "direccion": "saliente", "evidencia": evidencia},
            {"nombre": "evaluaciones.resultado", "tipo": "mensajeria", "tecnologia": "Kafka", "direccion": "produce", "evidencia": evidencia},
        ]
        invalidos = [{"nombre": "x", "tipo": "servidor", "evidencia": evidencia},
                     {"nombre": "y", "tipo": "cache", "evidencia": ["no-existe.java:1"]},
                     {"nombre": "z", "tipo": "integracion", "tercero": "no-existe", "evidencia": evidencia},
                     {"nombre": "w", "tipo": "base-de-datos"}]
        lote.write_text(yaml.safe_dump({"evaluaciones": evaluaciones, "componentes": componentes + invalidos},
                                       allow_unicode=True), encoding="utf-8")
        (carpeta / "revision" / "fraude-core-asis.md").write_text(AS_IS, encoding="utf-8")
        codigo, salida = self.ejecutar("cerrar", "motor-fraudes", "fraude-core")
        self.assertEqual(codigo, 1)
        for esperado in ("componentes[4] (x): tipo 'servidor' inválido", "componentes[5] (y)", "componentes[6] (z): el tercero 'no-existe'",
                         "componentes[7] (w): el componente necesita al menos una evidencia"):
            self.assertIn(esperado, salida)

        lote.write_text(yaml.safe_dump({"evaluaciones": evaluaciones, "componentes": componentes}, allow_unicode=True), encoding="utf-8")
        codigo, salida = self.ejecutar("cerrar", "motor-fraudes", "fraude-core")
        self.assertEqual(codigo, 0, salida)
        borradores = carpeta / "borradores" / "fraude-core"
        contexto = (borradores / "c4-contexto.md").read_text(encoding="utf-8")
        self.assertIn('System_Ext(buro_de_credito, "Buró de crédito", "BURO_URL")', contexto)
        self.assertIn('Rel(sistema, buro_de_credito, "BURO_URL", "HTTPS")', contexto)
        contenedores = (borradores / "c4-contenedores.md").read_text(encoding="utf-8")
        self.assertIn('ContainerQueue(evaluaciones_resultado, "evaluaciones.resultado", "Kafka", "")', contenedores)
        self.assertIn('Rel(app, evaluaciones_resultado, "produce", "Kafka")', contenedores)
        ficha = (self.raiz / "productos" / "motor-fraudes" / "as-is" / "fraude-core.md").read_text(encoding="utf-8")
        self.assertIn("## Anexo C. Componentes", ficha)
        self.assertIn("| Buró de crédito | integracion | HTTPS | BURO_URL | saliente | buro-credito | "
                      "`src/main/java/EvaluacionController.java:3` |", ficha)
        self.ejecutar("producto", "motor-fraudes")
        producto = (self.raiz / "productos" / "motor-fraudes" / "as-is" / "PRODUCTO.md").read_text(encoding="utf-8")
        self.assertIn("| evaluaciones.resultado | mensajeria | Kafka | fraude-core (produce) | — |", producto)
        self.assertIn("- Integraciones sin ficha en `terceros/`: Core bancario.", producto)
        self.assertIn("- Fichas de `terceros/` que ningún repositorio usa: listas-sanciones.", producto)
        self.assertIn("- Mensajería que solo se produce o solo se consume dentro del producto: evaluaciones.resultado.", producto)
        self.assertIn("### C4 de contenedores del producto", producto)
        self.assertIn('Rel(fraude_core, c_evaluaciones_resultado, "produce", "Kafka")', producto)

    def test_lote_compacto(self) -> None:
        import yaml
        carpeta = self.automatica["carpeta"]
        (carpeta / "revision").mkdir(parents=True, exist_ok=True)
        claves = [e["criterio"] or e["fuente"] for e in revision.lista_de_control(self.raiz, "propio", "motor-fraudes", "fraude-core")]
        hallazgo = {"fuente": "decisiones:ADR-010", "categoria": "incumplimiento", "severidad": "alta",
                    "titulo": "Llamada sin timeout", "detalle": "El cliente no define timeout.",
                    "evidencia": ["src/main/java/EvaluacionController.java:4"], "fragmento": 'System.out.println("evaluando");',
                    "cita_documento": "Ninguna llamada externa sin timeout explícito"}
        resto = [c for c in claves if c not in ("decisiones:ADR-010", "EQ-003.3")]
        lote = carpeta / "revision" / "fraude-core-lote.yaml"
        lote.write_text(yaml.safe_dump({"cumple": resto + ["decisiones:ADR-010", "EQ-999.9"], "hallazgos": [hallazgo]},
                                       allow_unicode=True), encoding="utf-8")
        codigo, salida = self.ejecutar("registrar", "motor-fraudes", "fraude-core")
        self.assertEqual(codigo, 1)
        self.assertIn("decisiones:ADR-010: tiene hallazgos en el lote", salida)
        self.assertIn("EQ-999.9: no está en", salida)
        lote.write_text(yaml.safe_dump({"cumple": resto, "no_aplica": {"EQ-003.3": "no hace llamadas salientes"},
                                        "hallazgos": [hallazgo]}, allow_unicode=True), encoding="utf-8")
        (carpeta / "revision" / "fraude-core-asis.md").write_text(AS_IS, encoding="utf-8")
        codigo, salida = self.ejecutar("cerrar", "motor-fraudes", "fraude-core")
        self.assertEqual(codigo, 0, salida)
        trabajo = revision.leer_trabajo(self.raiz, "motor-fraudes", self.automatica["id_revision"], "fraude-core")
        self.assertEqual(trabajo["evaluaciones"]["decisiones:ADR-010"]["resultado"], "NO CUMPLE", "el hallazgo implica NO CUMPLE")
        self.assertEqual(trabajo["evaluaciones"]["ADR-EQ-003|EQ-003.3"]["resultado"], "NO APLICA")
        self.assertEqual(trabajo["evaluaciones"]["ADR-EQ-001|EQ-001.2"]["resultado"], "CUMPLE")

        lote.write_text(yaml.safe_dump({"cumple": resto + ["decisiones:ADR-010"], "no_aplica": {"EQ-003.3": "x"}},
                                       allow_unicode=True), encoding="utf-8")
        self.assertEqual(self.ejecutar("cerrar", "motor-fraudes", "fraude-core")[0], 0)
        trabajo = revision.leer_trabajo(self.raiz, "motor-fraudes", self.automatica["id_revision"], "fraude-core")
        self.assertEqual(trabajo["hallazgos"], [], "si ahora cumple, el hallazgo de la carga anterior se descarta")

    def nueva_revision_automatica(self, archivo: str, contenido: str) -> None:
        (self.core / archivo).write_text(contenido, encoding="utf-8")
        commit(self.core, f"Cambia {archivo}")
        with contextlib.redirect_stdout(io.StringIO()):
            self.automatica = revisar.revisar(self.raiz, "motor-fraudes", usar_sonar=False)

    def test_revision_incremental(self) -> None:
        self.completar()
        self.assertEqual(self.ejecutar("cerrar", "motor-fraudes", "fraude-core")[0], 0)

        # Cambio que no toca la evidencia: todo se hereda, incluidos los hallazgos abiertos.
        self.nueva_revision_automatica("README.md", README + "\nCambio menor.\n")
        codigo, salida = self.ejecutar("paquete", "motor-fraudes", "fraude-core")
        paquete = (self.raiz / salida.split("Paquete: ")[1].strip()).read_text(encoding="utf-8")
        self.assertIn("## Revisión incremental", paquete)
        self.assertIn("- `README.md`", paquete)
        self.assertIn("### Heredados de la revisión", paquete)
        self.assertTrue((self.automatica["carpeta"] / "revision" / "fraude-core-asis.md").exists(), "el AS IS se copia")
        codigo, salida = self.ejecutar("cerrar", "motor-fraudes", "fraude-core")
        self.assertEqual(codigo, 0, salida)
        abiertos = [h for h in hallazgos.cargar(self.raiz, "motor-fraudes")["hallazgos"].values()
                    if h["origen"] == "revision" and h["estado"] == "abierto"]
        self.assertEqual(len(abiertos), 2, "los hallazgos heredados siguen abiertos, no se dan por corregidos")
        trabajo = revision.leer_trabajo(self.raiz, "motor-fraudes", self.automatica["id_revision"], "fraude-core")
        self.assertIn("heredada de", trabajo["evaluaciones"]["decisiones:ADR-010"]["motivo"])

        # Cambio en el archivo de la evidencia: esos elementos se vuelven a evaluar.
        self.nueva_revision_automatica("src/main/java/EvaluacionController.java", CONTROLADOR.replace("evaluando", "evaluar"))
        codigo, salida = self.ejecutar("paquete", "motor-fraudes", "fraude-core")
        paquete = (self.raiz / salida.split("Paquete: ")[1].strip()).read_text(encoding="utf-8")
        evaluar = paquete.split("## Qué evaluar")[1].split("### Heredados")[0]
        self.assertIn("`decisiones:ADR-010`", evaluar)
        self.assertIn("EQ-002.1", evaluar)
        codigo, salida = self.ejecutar("cerrar", "motor-fraudes", "fraude-core")
        self.assertEqual(codigo, 1)
        self.assertIn("decisiones:ADR-010", salida)

        codigo, salida = self.ejecutar("paquete", "motor-fraudes", "fraude-core", "--completa")
        paquete = (self.raiz / salida.split("Paquete: ")[1].strip()).read_text(encoding="utf-8")
        self.assertNotIn("## Revisión incremental", paquete, "--completa fuerza la revisión completa")


if __name__ == "__main__":
    unittest.main()
