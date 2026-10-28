"""Pruebas de productos: inspección, alta, baja y sincronización de repositorios."""

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

import productos  # noqa: E402
from test_sync_arquitectura import commit, ejecutar  # noqa: E402

POM = """\
<project>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.3.4</version>
  </parent>
</project>
"""

PACKAGE_JSON = json.dumps({"dependencies": {"@nestjs/core": "^10.0.0"}, "devDependencies": {"typescript": "^5.4.0"}})


def crear_repo(carpeta: Path, rama: str, archivos: dict[str, str]) -> None:
    carpeta.mkdir(parents=True)
    ejecutar("git", "init", "--quiet", "-b", rama, cwd=carpeta)
    for ruta, contenido in archivos.items():
        destino = carpeta / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")
    commit(carpeta, "Contenido inicial")


class PruebaProductos(unittest.TestCase):

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        base = Path(self.temporal.name)
        self.java = base / "fraude-core"
        self.node = base / "fraude-backoffice"
        crear_repo(self.java, "main", {
            "pom.xml": POM,
            "sonar-project.properties": "sonar.projectKey=banco_fraude-core\n",
            "README.md": "# fraude-core\n",
            "docs/arquitectura/c4-contexto.md": "# Contexto\n",
            "docs/contratos/openapi.yaml": "openapi: 3.0.0\n",
            "Dockerfile": "FROM eclipse-temurin:21\n",
            ".gitlab-ci.yml": "stages: [build]\n",
        })
        crear_repo(self.node, "develop", {"package.json": PACKAGE_JSON})
        self.raiz = base / "raiz"
        (self.raiz / "productos").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def ejecutar(self, *argumentos: str) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = productos.main(["--raiz", str(self.raiz), *argumentos])
        return codigo, salida.getvalue()

    def agregar(self, producto: str, id_repo: str, url: Path | str, rama: str, *extra: str) -> tuple[int, str]:
        return self.ejecutar("agregar", "--producto", producto, "--id", id_repo, "--url", str(url),
                             "--rama", rama, "--tipo", "propio", *extra)

    def test_inspeccionar_detecta_stack_sonar_y_presencia(self) -> None:
        codigo, salida = self.ejecutar("inspeccionar", str(self.java))
        self.assertEqual(codigo, 0, salida)
        datos = json.loads(salida)
        self.assertEqual(datos["id_sugerido"], "fraude-core")
        self.assertEqual(datos["rama_por_defecto"], "main")
        self.assertEqual(datos["stack"], ["Java (Maven)", "Spring Boot 3.3.4"])
        self.assertEqual(datos["sonar_detectado"], "banco_fraude-core")
        presencia = datos["presencia"]
        self.assertTrue(presencia["readme"] and presencia["c4_contexto"] and presencia["dockerfile"] and presencia["ci"])
        self.assertFalse(presencia["c4_contenedores"])
        self.assertEqual(presencia["contratos"], ["docs/contratos/openapi.yaml"])

        codigo, salida = self.ejecutar("inspeccionar", str(self.node))
        datos = json.loads(salida)
        self.assertEqual(datos["rama_por_defecto"], "develop")
        self.assertEqual(datos["stack"], ["Node.js", "TypeScript", "NestJS"])
        self.assertIsNone(datos["sonar_detectado"])

    def test_agregar_crea_el_producto_y_valida(self) -> None:
        codigo, salida = self.agregar("motor-fraudes", "fraude-core", self.java, "main",
                                      "--sonar", "banco_fraude-core", "--descripcion", "Motor de fraudes")
        self.assertEqual(codigo, 0, salida)
        self.assertIn("Producto 'motor-fraudes' creado con la sigla MF", salida)
        codigo, salida = self.agregar("motor-fraudes", "fraude-backoffice", self.node, "rama-inexistente")
        self.assertEqual(codigo, 1)
        self.assertIn("La ref 'rama-inexistente' no existe", salida)
        codigo, salida = self.agregar("motor-fraudes", "fraude-backoffice", self.node, "develop")
        self.assertEqual(codigo, 0, salida)

        texto = (self.raiz / "productos" / "motor-fraudes" / "producto.yaml").read_text(encoding="utf-8")
        self.assertIn("# Producto motor-fraudes. Se administra con el comando /producto", texto)
        self.assertIn("Motor de fraudes", texto)
        self.assertIn("c4: null", texto)
        self.assertIn("sonar: null", texto, "un valor vacío se escribe como null explícito")
        self.assertIn("sonar: banco_fraude-core", texto)

        listado = json.loads(self.ejecutar("listar")[1])
        self.assertEqual([r["id"] for r in listado[0]["repos"]], ["fraude-core", "fraude-backoffice"])
        self.assertEqual(listado[0]["repos"][1]["estado"], "activo")

        codigo, salida = self.agregar("otro-producto", "copia", self.java, "main")
        self.assertEqual(codigo, 1)
        self.assertIn("ya está registrado en el producto 'motor-fraudes'", salida)

        codigo, salida = self.agregar("Motor Fraudes", "x", self.node, "develop")
        self.assertEqual(codigo, 1)
        self.assertIn("debe ir en minúsculas", salida)

    def test_urls_equivalentes(self) -> None:
        self.assertEqual(productos.normalizar_url_git("git@gitlab.com:banco/fraude-core.git"),
                         productos.normalizar_url_git("https://gitlab.com/banco/fraude-core/"))
        self.assertNotEqual(productos.normalizar_url_git("git@gitlab.com:banco/fraude-core.git"),
                            productos.normalizar_url_git("git@github.com:banco/fraude-core.git"))

    def test_sincronizar_clona_actualiza_y_respeta_cambios_locales(self) -> None:
        self.agregar("motor-fraudes", "fraude-core", self.java, "main")
        codigo, salida = self.ejecutar("sincronizar")
        self.assertEqual(codigo, 0, salida)
        self.assertIn("[actualizado] motor-fraudes/fraude-core (main)", salida)
        copia = self.raiz / "productos" / "motor-fraudes" / "repos" / "fraude-core"
        self.assertTrue((copia / "pom.xml").exists())

        codigo, salida = self.ejecutar("sincronizar", "--producto", "motor-fraudes")
        self.assertIn("[sin cambios]", salida)

        (self.java / "CHANGELOG.md").write_text("cambio\n", encoding="utf-8")
        commit(self.java, "Nuevo commit")
        codigo, salida = self.ejecutar("sincronizar")
        self.assertIn("[actualizado]", salida)
        self.assertTrue((copia / "CHANGELOG.md").exists())

        (copia / "pom.xml").write_text("modificado localmente\n", encoding="utf-8")
        codigo, salida = self.ejecutar("sincronizar")
        self.assertIn("[omitido]", salida)
        self.assertEqual((copia / "pom.xml").read_text(encoding="utf-8"), "modificado localmente\n",
                         "nunca se descartan cambios locales")

    def test_retirar(self) -> None:
        self.agregar("motor-fraudes", "fraude-core", self.java, "main")
        codigo, salida = self.ejecutar("retirar", "--producto", "motor-fraudes", "--id", "fraude-core",
                                       "--motivo", "Reemplazado por otro servicio")
        self.assertEqual(codigo, 0, salida)
        repo = json.loads(self.ejecutar("listar")[1])[0]["repos"][0]
        self.assertEqual(repo["estado"], "retirado")
        self.assertEqual(repo["motivo_retiro"], "Reemplazado por otro servicio")
        codigo, salida = self.ejecutar("sincronizar")
        self.assertIn("No hay repositorios activos", salida)

    def test_sigla(self) -> None:
        self.assertEqual(productos.proponer_sigla(self.raiz, "motor-fraudes"), "MF")
        self.assertEqual(productos.proponer_sigla(self.raiz, "pagos"), "PAG")
        self.assertEqual(productos.proponer_sigla(self.raiz, "a"), "AX", "siempre al menos dos letras")
        self.agregar("motor-fraudes", "fraude-core", self.java, "main")
        self.assertNotEqual(productos.proponer_sigla(self.raiz, "monitor-fiscal"), "MF", "no repite una sigla en uso")

        codigo, salida = self.ejecutar("sigla", "motor-fraudes", "--asignar", "eq")
        self.assertIn("2 a 5 letras mayúsculas", salida)
        codigo, salida = self.ejecutar("sigla", "motor-fraudes", "--asignar", "EQ")
        self.assertIn("ya está en uso o reservada", salida)
        codigo, salida = self.ejecutar("sigla", "motor-fraudes", "--asignar", "FRA")
        self.assertEqual(codigo, 0, salida)
        self.assertIn("Sigla de 'motor-fraudes': FRA", salida)

        decisiones = self.raiz / "productos" / "motor-fraudes" / "decisiones"
        decisiones.mkdir()
        (decisiones / "ADR-FRA-001-algo.md").write_text("# ADR-FRA-001: Algo\n", encoding="utf-8")
        codigo, salida = self.ejecutar("sigla", "motor-fraudes", "--asignar", "MF")
        self.assertIn("su sigla no se puede cambiar", salida)


if __name__ == "__main__":
    unittest.main()
