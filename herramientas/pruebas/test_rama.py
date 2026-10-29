"""Pruebas de la fase 2: revisión de ramas, publicación en el MR o PR, reporte semanal y cliente de la plataforma."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from unittest import mock
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import estado  # noqa: E402
import hallazgos  # noqa: E402
import plataforma  # noqa: E402
import rama  # noqa: E402
import test_revision  # noqa: E402
from comun import ErrorRadiografia  # noqa: E402
from test_productos import ejecutar  # noqa: E402
from test_sync_arquitectura import commit  # noqa: E402

CLIENTE_BURO = """\
public class BuroClient {
    public String consultar(String rut) {
        System.out.println("consultando buró");
        return restTemplate.getForObject(url, String.class);
    }
}
"""


class ClienteFalso:
    """Plataforma git simulada: registra lo que se publica."""

    def __init__(self, mr: dict | None = None) -> None:
        self.mr, self.comentarios, self.siguiente = mr, {}, 100

    def mr_de_rama(self, proyecto: str, rama_: str) -> dict | None:
        return self.mr

    def enlace_archivo(self, proyecto: str, commit_: str, archivo: str, linea: int | None) -> str:
        return f"https://gitlab.com/{proyecto}/-/blob/{commit_}/{archivo}#L{linea}"

    def comentar_mr(self, proyecto: str, numero: int, cuerpo: str, id_comentario: int | None = None) -> int:
        if id_comentario is None:
            id_comentario, self.siguiente = self.siguiente, self.siguiente + 1
        self.comentarios[id_comentario] = cuerpo
        return id_comentario


MR = {"numero": 7, "url": "https://gitlab.com/x/-/merge_requests/7", "titulo": "Consulta al buró", "descripcion": "Agrega el cliente.",
      "destino": "main", "autor": "dev1", "aprobado_por": ["dev1"]}

LOTE = """\
hallazgos:
  - fuente: decisiones:ADR-010
    categoria: incumplimiento
    severidad: alta
    titulo: Llamada al buró sin timeout
    detalle: Una demora del buró bloquea los hilos del servicio.
    evidencia: [src/main/java/BuroClient.java:4]
    fragmento: return restTemplate.getForObject(url, String.class);
    cita_documento: Ninguna llamada externa sin timeout explícito
"""


class PruebaRama(unittest.TestCase):
    setUp_base = test_revision.PruebaRevision.setUp
    tearDown = test_revision.PruebaRevision.tearDown

    def setUp(self) -> None:
        self.setUp_base()
        parche = mock.patch("rama.proyecto_de", return_value="banco/fraude-core")
        parche.start()
        self.addCleanup(parche.stop)
        ejecutar("git", "checkout", "--quiet", "-b", "feature/buro", cwd=self.core)
        (self.core / "src/main/java/BuroClient.java").write_text(CLIENTE_BURO, encoding="utf-8")
        commit(self.core, "Cliente del buró")
        ejecutar("git", "checkout", "--quiet", "main", cwd=self.core)

    def preparar(self, cliente) -> dict:
        return rama.preparar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro", cliente)

    def lote(self, texto: str) -> None:
        estado_rama = hallazgos.cargar(self.raiz, "motor-fraudes")["ramas"]["fraude-core@feature/buro"]
        (self.raiz / "productos" / "motor-fraudes" / "revisiones" / estado_rama["id_revision"] / "lote.yaml").write_text(texto, encoding="utf-8")

    def de_la_rama(self) -> dict[str, dict]:
        return {(h["criterio"] or h["fuente"]): h for h in hallazgos.cargar(self.raiz, "motor-fraudes")["hallazgos"].values()
                if h["rama"] == "feature/buro" and h["estado"] == "abierto"}

    def test_solo_lo_que_cambia_la_rama(self) -> None:
        r = self.preparar(ClienteFalso(MR))
        self.assertEqual(r["estado"]["cambiados"], ["src/main/java/BuroClient.java"])
        self.assertEqual(r["estado"]["commits"], 1)
        automaticos = self.de_la_rama()
        self.assertEqual(automaticos["EQ-003.1"]["evidencia"][0]["archivo"], "src/main/java/BuroClient.java",
                         "la salida a consola de EvaluacionController ya estaba en main: no se atribuye a la rama")
        self.assertEqual(len(automaticos), 1)
        paquete = r["paquete"].read_text(encoding="utf-8")
        for esperado in ("+        System.out.println(\"consultando buró\");", "Aprobado por otra persona (EQ-008.2): todavía no",
                         "- `ADR-EQ-002` Integraciones resilientes con política de degradación explícita (propuesta): EQ-002.1", "> Agrega el cliente."):
            self.assertIn(esperado, paquete)

    def test_registrar_valida_que_la_evidencia_este_en_la_rama(self) -> None:
        self.preparar(ClienteFalso(MR))
        self.lote(LOTE.replace("BuroClient.java:4", "EvaluacionController.java:4")
                  .replace("return restTemplate.getForObject(url, String.class);", 'System.out.println("evaluando");'))
        with self.assertRaises(ErrorRadiografia) as error:
            rama.registrar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro")
        self.assertIn("no es un archivo que cambia la rama", str(error.exception))
        self.lote(LOTE)
        r = rama.registrar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro")
        self.assertEqual(len(r["resumen"]["nuevos"]), 1)
        self.assertTrue(r["veredicto"].startswith("NO PASA"), "un incumplimiento alto de arquitectura en la rama no pasa")

    def test_publicar_en_el_mr_y_editar_el_mismo_comentario(self) -> None:
        cliente = ClienteFalso(MR)
        self.preparar(cliente)
        self.lote(LOTE)
        rama.registrar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro")
        with self.assertRaises(ErrorRadiografia) as error:
            rama.publicar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro", cliente=cliente)
        self.assertIn("ningún hallazgo de la rama está marcado Resolver", str(error.exception))

        id_timeout = self.de_la_rama()["decisiones:ADR-010"]["id"]
        vista = rama.publicar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro", [id_timeout], cliente=cliente)
        self.assertFalse(vista["publicado"])
        self.assertEqual(cliente.comentarios, {}, "sin --confirmar no se publica nada")
        self.assertIn("| ⏳ pendiente | alta | Llamada al buró sin timeout | [src/main/java/BuroClient.java:4]"
                      "(https://gitlab.com/", vista["cuerpo"])
        self.assertEqual(vista["destino"], f"MR {MR['url']}")

        rama.publicar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro", [id_timeout], confirmar=True, cliente=cliente)
        self.assertEqual(list(cliente.comentarios), [100])
        self.assertEqual(self.de_la_rama()["decisiones:ADR-010"]["triaje"]["decision"], "resolver",
                         "lo elegido al publicar queda triado como Resolver")

        ejecutar("git", "checkout", "--quiet", "feature/buro", cwd=self.core)
        (self.core / "src/main/java/BuroClient.java").write_text(CLIENTE_BURO.replace("String.class)", "String.class, timeout)"),
                                                                 encoding="utf-8")
        commit(self.core, "Timeout en el cliente del buró")
        ejecutar("git", "checkout", "--quiet", "main", cwd=self.core)
        self.preparar(cliente)
        self.lote("hallazgos: []\n")
        rama.registrar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro")
        rama.publicar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro", confirmar=True, cliente=cliente)
        self.assertEqual(list(cliente.comentarios), [100], "se edita el mismo comentario")
        self.assertIn("| ✅ corregido | alta | Llamada al buró sin timeout |", cliente.comentarios[100])

    def test_solo_se_revisan_mr(self) -> None:
        with self.assertRaises(ErrorRadiografia) as error:
            self.preparar(ClienteFalso(None))
        self.assertIn("Solo se revisan MR", str(error.exception))

    def test_el_lenguaje_bloquea_la_publicacion(self) -> None:
        cliente = ClienteFalso(MR)
        self.preparar(cliente)
        self.lote(LOTE.replace("Una demora del buró", "Es importante destacar que una demora del buró"))
        rama.registrar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro")
        id_timeout = self.de_la_rama()["decisiones:ADR-010"]["id"]
        with self.assertRaises(ErrorRadiografia) as error:
            rama.publicar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro", [id_timeout], confirmar=True, cliente=cliente)
        self.assertIn("avisos de lenguaje", str(error.exception))
        self.assertEqual(cliente.comentarios, {})

    def test_reporte_semanal(self) -> None:
        self.preparar(ClienteFalso(MR))
        self.lote(LOTE)
        rama.registrar(self.raiz, "motor-fraudes", "fraude-core", "feature/buro")
        self.assertIn("motor-fraudes: sin reporte semanal: `/estado semanal`.", estado.que_sigue(estado.revisar_estado(self.raiz)))
        archivo = estado.semanal(self.raiz, "motor-fraudes")
        texto = archivo.read_text(encoding="utf-8")
        self.assertIn("| fraude-core | 1 | 1 | 1 |", texto)
        self.assertIn("| `feature/buro` |", texto)
        self.assertIn("[Consulta al buró](https://gitlab.com/x/-/merge_requests/7)", texto)
        self.assertIn(": NO PASA", texto)
        self.assertIn("· fraude-core @feature/buro · decisiones:ADR-010 · Llamada al buró sin timeout", texto)
        self.assertNotIn("sin reporte semanal", " ".join(estado.que_sigue(estado.revisar_estado(self.raiz))))
        siguiente = estado.semanal(self.raiz, "motor-fraudes", date.today() + timedelta(days=8))
        self.assertIn(f"Cambios desde el {date.today().isoformat()}", siguiente.read_text(encoding="utf-8"))


class SesionFalsa:
    def __init__(self, respuestas: dict) -> None:
        self.headers, self.respuestas, self.pedidos = {}, respuestas, []

    def request(self, metodo: str, url: str, timeout: int, **opciones):
        self.pedidos.append((metodo, url, opciones.get("params") or opciones.get("json")))
        ruta = url.split("/api/v4", 1)[-1].split("api.github.com", 1)[-1]
        datos = self.respuestas[(metodo, ruta)]
        return type("Respuesta", (), {"status_code": 200, "content": b"x", "text": json.dumps(datos), "json": lambda self: datos})()


class PruebaPlataforma(unittest.TestCase):

    def test_proyecto_de_la_url(self) -> None:
        for url, esperado in (("git@gitlab.com:banco/fraude/fraude-core.git", "banco/fraude/fraude-core"),
                              ("https://gitlab.com/banco/fraude-core.git", "banco/fraude-core"),
                              ("ssh://git@github.com:22/banco/fraude-core", "banco/fraude-core")):
            self.assertEqual(plataforma.proyecto_de(url), esperado)
        with self.assertRaises(ErrorRadiografia):
            plataforma.proyecto_de("/Users/equipo/repos/fraude-core")

    def test_gitlab_mr_y_comentario(self) -> None:
        proyecto = "/projects/banco%2Ffraude-core"
        sesion = SesionFalsa({
            ("GET", f"{proyecto}/merge_requests"): [{"iid": 7, "web_url": "u", "title": "t", "description": "d",
                                                     "target_branch": "main", "author": {"username": "dev1"}}],
            ("GET", f"{proyecto}/merge_requests/7/approvals"): {"approved_by": [{"user": {"username": "lider"}}]},
            ("POST", f"{proyecto}/merge_requests/7/notes"): {"id": 55},
            ("PUT", f"{proyecto}/merge_requests/7/notes/55"): {"id": 55},
        })
        cliente = plataforma.ClientePlataforma(plataforma.ConfigPlataforma("gitlab", "https://gitlab.com", "t"), sesion)
        mr = cliente.mr_de_rama("banco/fraude-core", "feature/buro")
        self.assertEqual((mr["numero"], mr["destino"], mr["aprobado_por"]), (7, "main", ["lider"]))
        self.assertEqual(sesion.pedidos[0][2], {"source_branch": "feature/buro", "state": "opened"})
        self.assertEqual(cliente.comentar_mr("banco/fraude-core", 7, "hola"), 55)
        self.assertEqual(cliente.comentar_mr("banco/fraude-core", 7, "hola", 55), 55)
        self.assertEqual(sesion.pedidos[-1][0], "PUT")
        self.assertEqual(cliente.enlace_archivo("banco/fraude-core", "abc", "src/A.java", 4),
                         "https://gitlab.com/banco/fraude-core/-/blob/abc/src/A.java#L4")
        self.assertEqual(sesion.headers["PRIVATE-TOKEN"], "t")

    def test_config_desde_env(self) -> None:
        self.assertIsNone(plataforma.ConfigPlataforma.desde_env({"GIT_PLATAFORMA": "gitlab"}))
        self.assertEqual(plataforma.ConfigPlataforma.motivo_sin_config({"GIT_PLATAFORMA": "gitlab"}), "GITLAB_TOKEN no está definido en .env")
        config = plataforma.ConfigPlataforma.desde_env({"GIT_PLATAFORMA": "github", "GITHUB_TOKEN": "x"})
        self.assertEqual((config.tipo, config.url), ("github", "https://github.com"))


if __name__ == "__main__":
    unittest.main()
