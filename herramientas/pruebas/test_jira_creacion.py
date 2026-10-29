"""Pruebas de /crear (Tareas, Spikes y Bugs): borrador, contexto del producto, validación según ADR-EQ-008 y creación en Jira."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hallazgos  # noqa: E402
import jira as historia  # noqa: E402
import productos  # noqa: E402
import test_revision  # noqa: E402

CUERPO_VALIDO = """\
# Agregar el diagrama de contexto C4 en fraude-core

**Como** desarrollador del equipo
**Quiero** documentar en un diagrama C4 los sistemas con los que se comunica fraude-core
**Para** que una persona nueva entienda sus dependencias sin leer el código

## Criterios de aceptación

- Existe docs/arquitectura/c4-contexto.md con un diagrama C4Context y 3 sistemas externos identificados.
- La revisión ya no reporta los hallazgos de origen (H-0001).

## Contexto

El repositorio no tiene diagrama de contexto (H-0001).

## Decisiones que aplican

- ADR-EQ-001: todo contenedor e integración real aparece en el diagrama.

## Fuera de alcance

- El diagrama de contenedores.

## Trazabilidad

- H-0001

## Definición de terminado

Según ADR-EQ-009 (Definición de terminado) del equipo Back.
"""


class Respuesta:
    def __init__(self, datos, estado: int = 200) -> None:
        self.status_code, self._datos, self.text = estado, datos, str(datos)

    def json(self):
        return self._datos


class JiraFalso:
    def __init__(self) -> None:
        self.headers, self.auth, self.creadas = {}, None, []

    def get(self, url, timeout=None, params=None):
        return Respuesta([{"id": "customfield_10050", "name": "Tipo", "schema": {"type": "option"}},
                          {"id": "customfield_10060", "name": "Equipos", "schema": {"type": "array"}}])

    def post(self, url, json=None, timeout=None):
        assert url.endswith("/rest/api/3/issue")
        self.creadas.append(json)
        return Respuesta({"key": "FRAUD-900"}, 201)


class PruebaHistoria(unittest.TestCase):
    setUp_revision = test_revision.PruebaRevision.setUp
    tearDown = test_revision.PruebaRevision.tearDown

    def setUp(self) -> None:
        self.setUp_revision()
        productos.configurar_historias(self.raiz, "motor-fraudes", "jira", "project = FRAUD AND labels = motor-fraudes",
                                       None, None, "Tipo", None)
        (self.raiz / ".env").write_text("JIRA_URL=https://ejemplo.atlassian.net\nJIRA_EMAIL=a@b.c\nJIRA_TOKEN=x\n", encoding="utf-8")
        (self.raiz / "harness.yaml").write_text((self.raiz / "harness.yaml").read_text(encoding="utf-8")
                                                + "jira:\n  equipos: Back\n", encoding="utf-8")
        self.jira = JiraFalso()

    def ejecutar(self, *argumentos: str) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = historia.main(["--raiz", str(self.raiz), *argumentos], sesion=self.jira)
        return codigo, salida.getvalue()

    def nueva(self, *extra: str) -> Path:
        codigo, salida = self.ejecutar("nueva", "motor-fraudes", *extra)
        self.assertEqual(codigo, 0, salida)
        return self.raiz / salida.split("Borrador: ")[1].split("\n")[0].strip()

    def completar(self, borrador: Path, cuerpo: str = CUERPO_VALIDO) -> None:
        datos, _ = historia.leer_borrador(borrador)
        historia.escribir_borrador(borrador, datos, cuerpo)

    def test_nueva_arma_borrador_y_contexto_del_producto(self) -> None:
        borrador = self.nueva("--tipo", "tarea", "--titulo", "Agregar el diagrama de contexto C4", "--desde", "H-0001")
        datos, cuerpo = historia.leer_borrador(borrador)
        self.assertEqual((datos["tipo_incidencia"], datos["tipo"], datos["equipos"]), ("tarea", "Deuda Técnica", "Back"))
        self.assertEqual((datos["repos"], datos["hallazgos"]), (["fraude-core"], ["H-0001"]))
        self.assertIn("- La revisión ya no reporta los hallazgos de origen (H-0001).", cuerpo, "el criterio fijo se completa solo")
        contexto = borrador.with_name(borrador.stem + "-contexto.md").read_text(encoding="utf-8")
        self.assertIn("**H-0001** · fraude-core · EQ-001.1", contexto)
        self.assertIn("`ADR-EQ-001`", contexto, "la decisión del hallazgo de origen aparece entre las que aplican")
        self.assertIn("## AS IS de los repositorios", contexto)
        self.assertIn("## Historias de Jira parecidas", contexto)

    def test_validacion_segun_adr_eq_008(self) -> None:
        borrador = self.nueva("--tipo", "tarea", "--titulo", "Agregar el diagrama", "--desde", "H-0001")
        self.assertIn("quedan textos de la plantilla sin completar (<…>)", historia.validar(self.raiz, "motor-fraudes", borrador))
        self.completar(borrador)
        self.assertEqual(historia.validar(self.raiz, "motor-fraudes", borrador), [])

        malo = (CUERPO_VALIDO.replace("**Como** desarrollador del equipo", "**Como** sistema")
                .replace("**Para** que una persona nueva entienda sus dependencias sin leer el código",
                         "**Para** documentar en un diagrama C4 los sistemas de fraude-core")
                .replace("El repositorio no tiene", "Es importante destacar que el repositorio no tiene")
                .replace("- Existe docs/arquitectura/c4-contexto.md con un diagrama C4Context y 3 sistemas externos identificados.\n", ""))
        self.completar(borrador, malo)
        errores = "\n".join(historia.validar(self.raiz, "motor-fraudes", borrador))
        self.assertIn("no «sistema»", errores)
        self.assertIn("el «Para» repite el «Quiero»", errores)
        self.assertIn("criterio de aceptación propio y medible", errores)
        self.assertIn("«es importante destacar»", errores)

    def test_combinaciones_y_reglas_de_spike(self) -> None:
        codigo, salida = self.ejecutar("nueva", "motor-fraudes", "--tipo", "bug", "--categoria", "Deuda Técnica", "--titulo", "x")
        self.assertIn("Un Bug solo admite Tipo Bau/Incidentes", salida)
        spike = self.nueva("--tipo", "spike", "--titulo", "Evaluar brokers de mensajería para decidir cuál usar")
        _, cuerpo = historia.leer_borrador(spike)
        cuerpo = cuerpo.replace("2 días.", "5 días.").replace("<Una sola pregunta, concreta.>", "¿Kafka o RabbitMQ? ¿Con qué costo?")
        self.completar(spike, cuerpo)
        errores = "\n".join(historia.validar(self.raiz, "motor-fraudes", spike))
        self.assertIn("la duración máxima de un Spike es 2 días", errores)
        self.assertIn("una sola pregunta", errores)

    def test_crear_con_vista_previa_y_confirmacion(self) -> None:
        borrador = self.nueva("--tipo", "tarea", "--titulo", "Agregar el diagrama", "--desde", "H-0001")
        codigo, salida = self.ejecutar("crear", "motor-fraudes", borrador.name)
        self.assertEqual(codigo, 1, "un borrador inválido no se crea")
        self.assertIn("no se puede crear", salida)

        self.completar(borrador)
        codigo, salida = self.ejecutar("crear", "motor-fraudes", borrador.name)
        self.assertEqual(codigo, 0, salida)
        self.assertIn("Vista previa (no se creó nada)", salida)
        self.assertEqual(self.jira.creadas, [], "sin --confirmar no se escribe en Jira")
        solicitud = json.loads(borrador.with_name(borrador.stem + "-jira.json").read_text(encoding="utf-8"))["fields"]
        self.assertEqual(solicitud["project"], {"key": "FRAUD"})
        self.assertEqual(solicitud["issuetype"], {"name": "Tarea"})
        self.assertEqual(solicitud["customfield_10050"], {"value": "Deuda Técnica"})
        self.assertEqual(solicitud["customfield_10060"], [{"value": "Back"}], "campo de selección múltiple")
        self.assertEqual(solicitud["labels"], ["motor-fraudes"])
        self.assertEqual(solicitud["summary"], "Agregar el diagrama de contexto C4 en fraude-core")
        self.assertEqual(solicitud["description"]["content"][0]["content"][0]["marks"], [{"type": "strong"}])

        codigo, salida = self.ejecutar("crear", "motor-fraudes", borrador.name, "--confirmar")
        self.assertEqual(codigo, 0, salida)
        self.assertIn("Creada en Jira: FRAUD-900", salida)
        datos, _ = historia.leer_borrador(borrador)
        self.assertEqual((datos["estado"], datos["jira"]), ("creada", "FRAUD-900"))
        h = next(h for h in hallazgos.cargar(self.raiz, "motor-fraudes")["hallazgos"].values() if h["id"] == "H-0001")
        self.assertEqual(h["historia_jira"], "FRAUD-900")
        codigo, salida = self.ejecutar("crear", "motor-fraudes", borrador.name, "--confirmar")
        self.assertIn("ya se creó en Jira como FRAUD-900", salida)
        self.assertEqual(len(self.jira.creadas), 1)


if __name__ == "__main__":
    unittest.main()
