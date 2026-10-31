"""Pruebas del harness de producto: creación, contenido generado, regeneración, ADR de producto y herramientas del dev."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import adr  # noqa: E402
import estado  # noqa: E402
import guardia  # noqa: E402
import hallazgos  # noqa: E402
import harness  # noqa: E402
import revision  # noqa: E402
import test_revision  # noqa: E402
from comun import carpeta_decisiones_producto, git  # noqa: E402

GIT_PRUEBA = {"GIT_AUTHOR_NAME": "Prueba", "GIT_AUTHOR_EMAIL": "prueba@example.com",
              "GIT_COMMITTER_NAME": "Prueba", "GIT_COMMITTER_EMAIL": "prueba@example.com"}


def cargar(ruta: Path, nombre: str):
    sys.modules.pop("hdu", None)  # listo.py importa hdu: que sea el del harness de esta prueba
    especificacion = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


class PruebaHarness(unittest.TestCase):
    setUp_base = test_revision.PruebaRevision.setUp
    tearDown = test_revision.PruebaRevision.tearDown

    def setUp(self) -> None:
        self.setUp_base()
        parche = mock.patch.dict(os.environ, GIT_PRUEBA)
        parche.start()
        self.addCleanup(parche.stop)
        import yaml
        carpeta = self.automatica["carpeta"] / "revision"
        carpeta.mkdir(parents=True, exist_ok=True)
        claves = [e["criterio"] or e["fuente"] for e in revision.lista_de_control(self.raiz, "propio", "motor-fraudes", "fraude-core")]
        hallazgo = {"fuente": "decisiones:ADR-010", "categoria": "incumplimiento", "severidad": "alta",
                    "titulo": "Llamada sin timeout", "detalle": "El cliente no define timeout.",
                    "evidencia": ["src/main/java/EvaluacionController.java:4"], "fragmento": 'System.out.println("evaluando");',
                    "cita_documento": "Ninguna llamada externa sin timeout explícito"}
        componente = {"nombre": "Buró de crédito", "tipo": "integracion", "tecnologia": "HTTPS", "detalle": "BURO_URL",
                      "direccion": "saliente", "evidencia": ["src/main/java/EvaluacionController.java:3"]}
        (carpeta / "fraude-core-lote.yaml").write_text(yaml.safe_dump(
            {"cumple": [c for c in claves if c != "decisiones:ADR-010"], "hallazgos": [hallazgo], "componentes": [componente]},
            allow_unicode=True), encoding="utf-8")
        (carpeta / "fraude-core-asis.md").write_text(test_revision.AS_IS.replace(
            "## Propósito\n\n[inferencia] Contenido de prueba.", "## Propósito\n\n[hecho] Evalúa transacciones con riesgo de fraude."),
            encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(revision.main(["--raiz", str(self.raiz), "cerrar", "motor-fraudes", "fraude-core"]), 0)
        self.adr_previo = adr.nuevo(self.raiz, "motor-fraudes", "decision", "Latencia de evaluación")
        self.destino = harness.ruta(self.raiz, "motor-fraudes")

    def commits(self) -> int:
        return int(git("rev-list", "--count", "HEAD", cwd=self.destino))

    def test_crear_genera_estructura_y_mueve_los_adr(self) -> None:
        pasos = " ".join(estado.que_sigue(estado.revisar_estado(self.raiz)))
        self.assertIn("sin harness: `harness.py crear motor-fraudes`", pasos)
        r = harness.crear(self.raiz, "motor-fraudes")
        self.assertEqual(r["movidos"], [self.adr_previo.name])
        self.assertFalse((self.raiz / "productos" / "motor-fraudes" / "decisiones").exists(), "los ADR dejan radiografia")
        for archivo in ("AGENTS.md", "README.md", "Makefile", ".gitignore", "repos.json", "GENERADO.json", ".cursor/hooks.json",
                        "herramientas/harness.py", "herramientas/guardia.py", "decisiones/README.md", "decisiones/plantilla.md",
                        "decisiones/INDICE.md", f"decisiones/{self.adr_previo.name}"):
            self.assertTrue((self.destino / archivo).exists(), archivo)
        self.assertIn("harness-motor-fraudes — contrato de trabajo", (self.destino / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn("ADR-MF-NNN", (self.destino / "decisiones" / "plantilla.md").read_text(encoding="utf-8"))
        self.assertIn("code/", (self.destino / ".gitignore").read_text(encoding="utf-8"))
        self.assertEqual(self.commits(), 1)
        self.assertEqual(carpeta_decisiones_producto(self.raiz, "motor-fraudes"), self.destino / "decisiones")

        decisiones = (self.destino / ".cursor/rules/generado/decisiones.mdc").read_text(encoding="utf-8")
        self.assertIn("alwaysApply: true", decisiones)
        self.assertIn("- `decisiones:ADR-010` Timeouts obligatorios: Ninguna llamada externa sin timeout explícito.", decisiones)
        self.assertIn("### ADR-EQ-002 Integraciones resilientes con política de degradación explícita (propuesta)", decisiones)
        self.assertIn("- `EQ-002.1` (alta):", decisiones)
        self.assertNotIn("EQ-009.2", decisiones, "los criterios de revisión de la historia no son para el código")
        repo = (self.destino / ".cursor/rules/generado/repo-fraude-core.mdc").read_text(encoding="utf-8")
        self.assertIn("globs: code/fraude-core/**", repo)
        self.assertIn("**Propósito:** [hecho] Evalúa transacciones con riesgo de fraude.", repo)
        self.assertIn("| Buró de crédito | integracion | HTTPS | BURO_URL | saliente |", repo)
        self.assertIn("decisiones:ADR-010 · alta: Llamada sin timeout · `src/main/java/EvaluacionController.java:4`", repo)
        repos = json.loads((self.destino / "repos.json").read_text(encoding="utf-8"))
        self.assertEqual(repos["repos"][0]["id"], "fraude-core")
        with self.assertRaises(Exception):
            harness.crear(self.raiz, "motor-fraudes")

    def test_regenerar_solo_si_cambia_y_adr_en_el_harness(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        self.assertFalse(harness.generar(self.raiz, "motor-fraudes")["commit"], "sin cambios no hay commit")
        registro = hallazgos.cargar(self.raiz, "motor-fraudes")
        for h in registro["hallazgos"].values():
            if h["fuente"] == "decisiones:ADR-010":
                h["triaje"] = {"decision": "falso-positivo", "motivo": "prueba", "vence": None, "fecha": "2026-10-29"}
        hallazgos.guardar(self.raiz, "motor-fraudes", registro)
        r = harness.generar(self.raiz, "motor-fraudes")
        self.assertTrue(r["commit"])
        self.assertEqual(r["cambiados"], [".cursor/rules/generado/repo-fraude-core.mdc", "contexto.json"])
        self.assertEqual(r["version"], 2)
        self.assertNotIn("Llamada sin timeout", (self.destino / ".cursor/rules/generado/repo-fraude-core.mdc").read_text(encoding="utf-8"))

        nuevo = adr.nuevo(self.raiz, "motor-fraudes", "decision", "Reintentos del buró")
        self.assertEqual(nuevo.parent, self.destino / "decisiones", "los ADR nuevos nacen en el harness")
        self.assertTrue(nuevo.name.startswith("ADR-MF-002-"))
        self.assertTrue(harness.guardar(self.raiz, "motor-fraudes", "Propone ADR-MF-002"))
        self.assertEqual(self.commits(), 3)
        e = harness.estado(self.raiz, "motor-fraudes")
        self.assertEqual((e["remoto"], e["sin_subir"]), (False, 3))
        self.assertIn("el harness tiene 3 commit(s) sin subir", " ".join(estado.que_sigue(estado.revisar_estado(self.raiz))))
        self.assertEqual(harness.traer(self.raiz, "motor-fraudes"), "sin remoto: nada que traer")

    def test_herramientas_del_dev(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        salida = subprocess.run([sys.executable, str(self.destino / "herramientas" / "harness.py"), "code"],
                                capture_output=True, text=True)
        self.assertEqual(salida.returncode, 0, salida.stdout + salida.stderr)
        self.assertTrue((self.destino / "code" / "fraude-core" / ".git").exists())
        salida = subprocess.run([sys.executable, str(self.destino / "herramientas" / "harness.py"), "code"],
                                capture_output=True, text=True)
        self.assertIn("fraude-core: actualizado · rama main", salida.stdout)
        self.assertEqual(git("status", "--porcelain", cwd=self.destino), "", "code/ queda fuera de git del harness")

        guardia_dev = cargar(self.destino / "herramientas" / "guardia.py", "guardia_dev")
        casos = {"git -C code/fraude-core push origin main": "deny", "git push --force origin feature/x": "deny",
                 "git push origin +feature/x": "deny", "glab mr merge 12": "deny",
                 "git -C code/fraude-core push -u origin feature/FRAUD-123": "allow",
                 "git -C code/fraude-core commit -m 'Agrega timeout'": "allow"}
        for comando, esperado in casos.items():
            self.assertEqual(guardia_dev.evaluar(comando)[0], esperado, comando)
        self.assertEqual(guardia.evaluar("git -C productos/motor-fraudes/harness push origin main")[0], "ask",
                         "en radiografia, el push del harness pide aprobación")
        self.assertEqual(guardia.evaluar("git -C productos/motor-fraudes/harness commit -m x")[0], "allow")

    def test_plantilla_agrega_lo_nuevo_y_avisa_sin_pisar(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        (self.destino / "herramientas" / "hdu.py").unlink()
        agents = self.destino / "AGENTS.md"
        agents.write_text(agents.read_text(encoding="utf-8") + "\nRegla propia del equipo.\n", encoding="utf-8")
        generado = json.loads((self.destino / "GENERADO.json").read_text(encoding="utf-8"))
        generado["plantilla"]["README.md"] = "huella-de-una-plantilla-anterior"
        del generado["plantilla"]["herramientas/hdu.py"]
        (self.destino / "GENERADO.json").write_text(json.dumps(generado), encoding="utf-8")
        r = harness.generar(self.raiz, "motor-fraudes")
        self.assertIn("herramientas/hdu.py", r["cambiados"], "un archivo nuevo de la plantilla se agrega")
        self.assertTrue((self.destino / "herramientas" / "hdu.py").exists())
        self.assertEqual(r["avisos"], ["README.md"], "la plantilla cambió el README: se avisa, no se pisa")
        self.assertIn("Regla propia del equipo.", agents.read_text(encoding="utf-8"), "lo que cambió el equipo se conserva")
        self.assertEqual(harness.generar(self.raiz, "motor-fraudes")["avisos"], [], "el aviso se da una vez")
        config = json.loads((self.destino / "config.json").read_text(encoding="utf-8"))
        self.assertEqual((config["sigla"], config["jira"]["medicion_aceptada"]), ("MF", ["Óptima", "Completa", "Adecuada"]))
        contexto = json.loads((self.destino / "contexto.json").read_text(encoding="utf-8"))
        self.assertIn("decisiones:ADR-010", [h["criterio"] for h in contexto["fraude-core"]["hallazgos"]])
        self.assertTrue((self.destino / ".env.example").exists())

    def historia(self, medicion: str | None, tipo: str = "Historia") -> dict:
        descripcion = {"type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Como analista quiero que la evaluación consulte el buró."}]},
            {"type": "heading", "content": [{"type": "text", "text": "Criterios de aceptación"}]},
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "La consulta responde en menos de 800 ms."}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Si el buró falla, la transacción queda en revisión."}]}]}]}]}
        campos = {"summary": "Consultar el buró en la evaluación", "description": descripcion, "issuetype": {"name": tipo},
                  "status": {"name": "Por hacer"}, "labels": [], "components": [{"name": "fraude-core"}],
                  "customfield_1": {"value": medicion} if medicion else None, "customfield_2": {"value": "Producto"}}
        return {"fields": campos}

    def hdu(self, medicion: str | None, tipo: str = "Historia"):
        modulo = cargar(self.destino / "herramientas" / "hdu.py", "hdu_prueba")
        def pedir(env, ruta, parametros=None):
            if ruta.endswith("/field"):
                return [{"id": "customfield_1", "name": "Medición HU"}, {"id": "customfield_2", "name": "Tipo"}]
            return self.historia(medicion, tipo)
        modulo.pedir = pedir
        modulo.cargar_env = lambda: {"JIRA_URL": "https://jira.example", "JIRA_EMAIL": "e", "JIRA_TOKEN": "t"}
        return modulo

    def test_hdu_toma_segun_medicion_y_prepara_el_trabajo(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        subprocess.run([sys.executable, str(self.destino / "herramientas" / "harness.py"), "code"], capture_output=True, check=True)
        r = self.hdu("Completa").tomar("FRAUD-123", None, True)
        self.assertTrue(r["tomada"])
        self.assertEqual(r["repos"], ["fraude-core"], "el repositorio sale del componente de Jira")
        self.assertEqual(r["historia"]["criterios"], ["La consulta responde en menos de 800 ms.",
                                                      "Si el buró falla, la transacción queda en revisión."])
        self.assertEqual(git("branch", "--show-current", cwd=self.destino / "code" / "fraude-core"),
                         "feat/FRAUD-123-consultar-el-buro-en-la-evaluacion")
        contexto = r["contexto"].read_text(encoding="utf-8")
        self.assertIn("1. La consulta responde en menos de 800 ms.", contexto)
        self.assertIn("decisiones:ADR-010 · alta: Llamada sin timeout", contexto, "los hallazgos altos del repo siempre se muestran")

        self.assertFalse(self.hdu("Incompleta").tomar("FRAUD-124", None, False)["tomada"], "una medición no aceptada no se toma")
        sin_medir = self.hdu(None).tomar("FRAUD-125", None, False)
        self.assertEqual(sin_medir["medicion"], "sin medir")
        self.assertIn("`/listo` exige revisar la deuda", sin_medir["contexto"].read_text(encoding="utf-8"))
        spike = self.hdu("Óptima", "Spike").tomar("FRAUD-126", None, False)
        self.assertIn("## Entregable del Spike", spike["contexto"].read_text(encoding="utf-8"))
        self.assertEqual({l[3:].split("/")[0] for l in git("status", "--porcelain", cwd=self.destino).splitlines()}, {"specs"},
                         "trabajo/ y .cursorignore quedan fuera de git")

        modulo = self.hdu("Completa")
        modulo.foco(["fraude-core"], ["fraude-core", "fraude-backoffice"])
        self.assertIn("code/fraude-backoffice/", (self.destino / ".cursorignore").read_text(encoding="utf-8"))
        modulo.foco(None, ["fraude-core", "fraude-backoffice"])
        self.assertFalse((self.destino / ".cursorignore").exists(), "sin foco no queda nada oculto")

    def aprobar_spec(self, clave: str) -> None:
        """Completa la spec e integra su rama en main, como lo haría su MR."""
        archivo = self.destino / "specs" / clave / "spec.md"
        archivo.write_text(re.sub(r"<completar[^>]*>", "Definido", archivo.read_text(encoding="utf-8")), encoding="utf-8")
        git("add", "-A", cwd=self.destino)
        git("commit", "--quiet", "-m", f"Spec de {clave}", cwd=self.destino)
        git("switch", "--quiet", "main", cwd=self.destino)
        git("merge", "--quiet", "--no-ff", "-m", f"Integra spec de {clave}", f"docs/{clave}-spec", cwd=self.destino)

    def test_no_se_programa_sin_spec_aprobada(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        subprocess.run([sys.executable, str(self.destino / "herramientas" / "harness.py"), "code"], capture_output=True, check=True)
        modulo = self.hdu("Completa")
        self.assertIn("borrador", modulo.tomar("FRAUD-123", None, True)["spec"])
        self.assertEqual(git("branch", "--show-current", cwd=self.destino), "docs/FRAUD-123-spec")
        self.assertIn("quedan partes por completar", modulo.errores_spec("FRAUD-123"))
        self.assertIn("1. La consulta responde en menos de 800 ms.", modulo.ruta_spec("FRAUD-123").read_text(encoding="utf-8"))
        with self.assertRaises(modulo.ErrorHdu) as error:
            modulo.desarrollar("FRAUD-123")
        self.assertIn("no está aprobada", str(error.exception))

        git("switch", "--quiet", "docs/FRAUD-123-spec", cwd=self.destino)
        self.aprobar_spec("FRAUD-123")
        self.assertEqual(modulo.errores_spec("FRAUD-123"), [])
        self.assertEqual(modulo.desarrollar("FRAUD-123")["tipo"], "historia")
        self.assertIn("ya aprobada", modulo.tomar("FRAUD-123", None, False)["spec"])

        archivo = modulo.ruta_spec("FRAUD-123")
        original = archivo.read_text(encoding="utf-8")
        archivo.write_text(original.replace("| 2 |", "| x |"), encoding="utf-8")
        self.assertIn("el criterio 2 no tiene prueba", modulo.errores_spec("FRAUD-123"))
        archivo.write_text(original + "\n" * 100, encoding="utf-8")
        self.assertIn("supera las 80 líneas", modulo.errores_spec("FRAUD-123"))
        archivo.write_text(original, encoding="utf-8")

        hotfix = self.hdu("Completa", "Hotfix")
        self.assertIn("borrador", hotfix.tomar("FRAUD-127", None, False)["spec"])
        self.assertEqual(hotfix.desarrollar("FRAUD-127")["tipo"], "hotfix", "un Hotfix no espera la aprobación")
        spike = self.hdu("Completa", "Spike")
        self.assertIn("sin spec", spike.tomar("FRAUD-128", None, False)["spec"])
        with self.assertRaises(spike.ErrorHdu):
            spike.desarrollar("FRAUD-128")

    def test_todo_producto_nace_con_su_harness(self) -> None:
        import productos
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = productos.main(["--raiz", str(self.raiz), "crear", "--producto", "motor-nuevo", "--origen", "nuevo",
                                     "--descripcion", "Producto nuevo", "--sigla", "MN"])
            self.assertEqual(codigo, 0, salida.getvalue())
            self.assertTrue(harness.existe(self.raiz, "motor-nuevo"))
            self.assertIn("Para subirlo", salida.getvalue())
            self.assertEqual(productos.main(["--raiz", str(self.raiz), "sigla", "motor-nuevo", "--asignar", "MNX"]), 1,
                             "con harness, la sigla queda fija")

    def test_arquitectura_llega_a_hdu_con_poco_contexto(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        indice = json.loads((self.destino / "arquitectura.json").read_text(encoding="utf-8"))
        documento = next(d for d in indice["documentos"] if d["clave"] == "decisiones:ADR-010")
        self.assertTrue((self.destino / documento["archivo"]).exists(), "el texto completo queda en el harness")
        self.assertLessEqual(len(documento["extracto"]), harness.MAXIMO_EXTRACTO + 4)
        self.assertNotIn(documento["extracto"], (self.destino / ".cursor/rules/generado/decisiones.mdc").read_text(encoding="utf-8"))

        modulo = self.hdu("Completa")
        historia = {"titulo": "Llamada externa", "descripcion": "Definir el timeout obligatorio", "criterios": []}
        self.assertEqual([d["clave"] for d in modulo.arquitectura_relacionada(historia, {})], ["decisiones:ADR-010"])
        self.assertEqual(modulo.arquitectura_relacionada({**historia, "titulo": "Otro", "descripcion": "Reporte mensual"}, {}), [])
        self.assertEqual(modulo.avisos_arquitectura(), [], "el harness tiene el último commit de arquitectura")

        fuentes = indice["fuentes"]
        fuentes["decisiones"]["commit"] = "0" * 40
        (self.destino / "arquitectura.json").write_text(json.dumps({**indice, "fuentes": fuentes}), encoding="utf-8")
        self.assertIn("no llegaron", modulo.avisos_arquitectura()[0])
        fuentes["decisiones"]["url"] = str(self.raiz / "no-existe")
        (self.destino / "arquitectura.json").write_text(json.dumps({**indice, "fuentes": fuentes}), encoding="utf-8")
        self.assertIn("NO DETERMINADO", modulo.avisos_arquitectura()[0])

    def test_subir_retiene_sin_coherencia_y_hdu_trae_lo_nuevo(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        remoto = Path(self.temporal.name) / "harness-remoto.git"
        subprocess.run(["git", "init", "--quiet", "--bare", "-b", "main", str(remoto)], check=True)
        git("remote", "add", "origin", str(remoto), cwd=self.destino)
        git("push", "--quiet", "-u", "origin", "main", cwd=self.destino)
        copia = Path(self.temporal.name) / "harness-persona"
        subprocess.run(["git", "clone", "--quiet", str(remoto), str(copia)], check=True)

        with mock.patch.object(harness, "pares_pendientes", return_value=2):
            r = harness.subir(self.raiz, "motor-fraudes", True)
        self.assertEqual(r["resultado"], "retenido")
        with mock.patch.object(harness, "pares_pendientes", return_value=0):
            self.assertEqual(harness.subir(self.raiz, "motor-fraudes", False)["resultado"], "al dia")
            (self.destino / "repos.json").write_text("{}\n", encoding="utf-8")
            git("commit", "--quiet", "-am", "Cambio local", cwd=self.destino)
            self.assertEqual(harness.subir(self.raiz, "motor-fraudes", False)["resultado"], "por subir")
            self.assertEqual(git("rev-parse", "main", cwd=remoto) == git("rev-parse", "HEAD", cwd=self.destino), False,
                             "la vista previa no sube nada")
            self.assertEqual(harness.subir(self.raiz, "motor-fraudes", True)["resultado"], "subido")
        self.assertEqual(git("rev-parse", "main", cwd=remoto), git("rev-parse", "HEAD", cwd=self.destino))

        modulo = cargar(copia / "herramientas" / "hdu.py", "hdu_copia")
        self.assertEqual(modulo.actualizar_harness(), "actualizado")
        self.assertEqual(git("rev-parse", "HEAD", cwd=copia), git("rev-parse", "main", cwd=remoto), "/hdu llega con lo último")
        git("switch", "--quiet", "-c", "propuesta", cwd=copia)
        with self.assertRaises(modulo.ErrorHdu):
            modulo.actualizar_harness()

    def test_adr_desde_el_harness_y_enlazar_clones(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        herramienta = str(self.destino / "herramientas" / "harness.py")
        salida = subprocess.run([sys.executable, herramienta, "adr", "--titulo", "Cola para eventos de evaluación",
                                 "--historia", "FRAUD-126"], capture_output=True, text=True)
        self.assertEqual(salida.returncode, 0, salida.stderr)
        nuevo = next((self.destino / "decisiones").glob("ADR-MF-002-*.md")).read_text(encoding="utf-8")
        self.assertTrue(nuevo.startswith("# ADR-MF-002: Cola para eventos de evaluación"))
        self.assertIn("- **Historias de origen:** FRAUD-126", nuevo)
        self.assertIn("| `MF-002.1` | | revisión de código |", nuevo)
        self.assertNotIn("ÁMBITO", nuevo)
        errores, _ = adr.validar_adr(self.raiz, "motor-fraudes", adr.leer_decisiones_producto(self.raiz, "motor-fraudes")["ADR-MF-002"])
        self.assertEqual(errores, ["falta la regla rápida"], "radiografia lo lee como ADR del producto; solo falta completarlo")

        clones = Path(self.temporal.name) / "mis-repos"
        clones.mkdir()
        subprocess.run(["git", "clone", "--quiet", str(self.core), str(clones / "fraude-core")], check=True)
        salida = subprocess.run([sys.executable, herramienta, "code", "--enlazar", str(clones)], capture_output=True, text=True)
        self.assertIn("fraude-core: enlazado a", salida.stdout)
        self.assertTrue((self.destino / "code" / "fraude-core").is_symlink())
        doctor = subprocess.run([sys.executable, herramienta, "doctor"], capture_output=True, text=True)
        self.assertIn("code/ fuera de git del harness", doctor.stdout)

    def test_listo_verifica_registra_criterios_y_deuda(self) -> None:
        harness.crear(self.raiz, "motor-fraudes")
        subprocess.run([sys.executable, str(self.destino / "herramientas" / "harness.py"), "code"], capture_output=True, check=True)
        self.hdu("Completa").tomar("FRAUD-123", None, True)
        codigo_repo = self.destino / "code" / "fraude-core"
        (codigo_repo / "src/main/java/BuroClient.java").write_text(
            "class BuroClient {\n  String consultar() {\n    // TODO timeout\n    System.out.println(\"x\");\n    return null;\n  }\n}\n",
            encoding="utf-8")
        (codigo_repo / "src/test/java").mkdir(parents=True)
        (codigo_repo / "src/test/java/BuroClientTest.java").write_text(
            "class BuroClientTest {\n  @Test\n  void respondeEnMenosDe800ms() {}\n  @Test\n  void quedaEnRevision() {}\n}\n", encoding="utf-8")
        git("add", "-A", cwd=codigo_repo)
        git("commit", "--quiet", "-m", "Cliente del buró", cwd=codigo_repo)
        listo = cargar(self.destino / "herramientas" / "listo.py", "listo_prueba")
        paquete = listo.preparar("FRAUD-123").read_text(encoding="utf-8")
        self.assertIn("- Consola: `src/main/java/BuroClient.java:4`", paquete)
        self.assertIn("- Pendientes: `src/main/java/BuroClient.java:3`", paquete)
        self.assertIn("1. La consulta responde en menos de 800 ms.", paquete)

        self.assertIn("## Spec (el código debe cumplirla)", paquete)
        self.assertIn("El commit «Cliente del buró» no sigue Conventional Commits (EQ-010.2).", paquete)
        modulo = self.hdu("Completa")
        self.assertEqual(modulo.avisos_convencion("fix/FRAUD-1-timeout", ["fix(buro): define el timeout", "refactor!: cambia el contrato"]), [])
        self.assertEqual(len(modulo.avisos_convencion("feature/x", ["wip", "build: x"])), 3)
        self.assertEqual(modulo.TIPO_RAMA["hotfix"], "fix")

        registro = self.destino / "trabajo" / "FRAUD-123" / "listo.json"
        registro.write_text(json.dumps({"criterios": {"1": "fraude-core:src/test/java/BuroClientTest.java:3"}, "deuda": [],
                                        "decisiones_aplicadas": ["ADR-EQ-002"]}), encoding="utf-8")
        with self.assertRaises(listo.ErrorListo) as error:
            listo.cerrar("FRAUD-123")
        self.assertIn("el criterio 2 no tiene prueba", str(error.exception))
        self.assertIn("spec: no está aprobada", str(error.exception))
        self.aprobar_spec("FRAUD-123")
        registro.write_text(json.dumps({
            "criterios": {"1": "fraude-core:src/test/java/BuroClientTest.java:3", "2": "fraude-core:src/test/java/BuroClientTest.java:5"},
            "deuda": [{"tipo": "tecnica", "descripcion": "El timeout del buró queda fijo en el código; falta llevarlo a configuración.",
                       "evidencia": "fraude-core:src/main/java/BuroClient.java:3"}],
            "desvios": ["El timeout se definió en el cliente y no en el servicio."],
            "decisiones_aplicadas": ["ADR-EQ-002", "decisiones:ADR-010"]}), encoding="utf-8")
        archivos = listo.cerrar("FRAUD-123")
        descripcion = archivos[0].read_text(encoding="utf-8")
        self.assertIn("| 1 | La consulta responde en menos de 800 ms. | `src/test/java/BuroClientTest.java:3` |", descripcion)
        self.assertIn("- **Técnica:** El timeout del buró queda fijo en el código", descripcion)
        self.assertIn("### Desvíos de la spec", descripcion)
        self.assertIn("<!-- radiografia:listo ", descripcion)
        import mr
        datos = mr.registro_listo(descripcion)
        self.assertEqual((datos["clave"], datos["repo"], datos["commit"]), ("FRAUD-123", "fraude-core", git("rev-parse", "HEAD", cwd=codigo_repo)))
        self.assertEqual(datos["senales"]["consola"], 1)
        self.assertEqual(mr.contraste_spec(self.raiz, "motor-fraudes", datos),
                         ["Desvío declarado respecto de la spec: El timeout se definió en el cliente y no en el servicio."])
        self.assertIn("no está en la rama principal", mr.contraste_spec(self.raiz, "motor-fraudes", {"clave": "FRAUD-9"})[0])
        self.assertIn("Comprobar el tipo en Jira", mr.contraste_spec(self.raiz, "motor-fraudes", {"clave": "FRAUD-9", "tipo": "hotfix"})[0])
        self.assertIn("Criterio 9: no existe", mr.contraste_spec(self.raiz, "motor-fraudes", {"clave": "FRAUD-123", "criterios": {"9": "x:y:1"}})[0])

        (codigo_repo / "src/test/java/BuroClientTest.java").write_text(
            "class BuroClientTest {\n  @Disabled\n  @Test\n  void respondeEnMenosDe800ms() {}\n  @Test\n  void quedaEnRevision() {}\n}\n",
            encoding="utf-8")
        git("commit", "--quiet", "-am", "Deshabilita", cwd=codigo_repo)
        listo.preparar("FRAUD-123")
        registro.write_text(json.dumps({"criterios": {"1": "fraude-core:src/test/java/BuroClientTest.java:4",
                                                      "2": "fraude-core:src/test/java/BuroClientTest.java:6"}, "sin_deuda": True}),
                            encoding="utf-8")
        with self.assertRaises(listo.ErrorListo) as error:
            listo.cerrar("FRAUD-123")
        self.assertIn("está deshabilitada", str(error.exception))


if __name__ == "__main__":
    unittest.main()
