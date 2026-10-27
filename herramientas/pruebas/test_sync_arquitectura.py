"""Pruebas de sync_arquitectura con un repositorio de arquitectura de ejemplo."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sync_arquitectura  # noqa: E402

ADR_REEMPLAZADO = """\
# ADR-001: Adopción de una herramienta de asistencia de código

## 2. Estado

Reemplazado por ADR-003

## 3. Fecha

- Fecha de creación: `01-03-2026`
- Fecha de aprobación: `15-03-2026`

## 11. Regla rápida

> Se usa la herramienta A.
"""

ADR_ESTADO_DESCONOCIDO = """\
# ADR-002: Baseline de Java

## 2. Estado

En borrador

## 3. Fecha

- Fecha de creación: `10-05-2026`
"""

ADR_VIGENTE = """\
# ADR-003: Adopción de Cursor como asistente de código estándar

## 2. Estado

**Aprobado**

## 3. Fecha

- Fecha de creación: `01-07-2026`
- Fecha de aprobación: `01-07-2026`

## 4. Contexto

Texto de contexto con un bloque de código que no debe leerse como sección:

```
## 2. Estado
Rechazado
```

## 10. Referencias

- Reemplaza a ADR-001.

## 11. Regla rápida

> Cursor es el asistente de código estándar,
> con privacy mode activo.
"""


def ejecutar(*argumentos: str, cwd: Path) -> str:
    return subprocess.run(argumentos, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def commit(repo: Path, mensaje: str) -> str:
    ejecutar("git", "add", "-A", cwd=repo)
    ejecutar("git", "-c", "user.name=Prueba", "-c", "user.email=prueba@example.com",
             "commit", "--quiet", "-m", mensaje, cwd=repo)
    return ejecutar("git", "rev-parse", "HEAD", cwd=repo)


class PruebaSyncArquitectura(unittest.TestCase):

    def setUp(self) -> None:
        self.temporal = tempfile.TemporaryDirectory()
        base = Path(self.temporal.name)
        self.origen = base / "origen"
        self.raiz = base / "raiz"
        adrs = self.origen / "docs" / "adrs"
        adrs.mkdir(parents=True)
        ejecutar("git", "init", "--quiet", "-b", "main", cwd=self.origen)
        (adrs / "0001-herramienta-a.md").write_text(ADR_REEMPLAZADO, encoding="utf-8")
        (adrs / "0002-baseline-java.md").write_text(ADR_ESTADO_DESCONOCIDO, encoding="utf-8")
        (adrs / "0003-adopcion-cursor.md").write_text(ADR_VIGENTE, encoding="utf-8")
        (adrs / "README.md").write_text("# Decision records\n", encoding="utf-8")
        self.commit_inicial = commit(self.origen, "ADR iniciales")

        self.raiz.mkdir()
        self.escribir_config(ruta="docs/adrs")

    def tearDown(self) -> None:
        self.temporal.cleanup()

    def escribir_config(self, ruta: str) -> None:
        (self.raiz / "harness.yaml").write_text(textwrap.dedent(f"""\
            version: 1
            arquitectura:
              fuentes:
                - id: decision-records
                  url: {self.origen}
                  ref: main
                  ruta: {ruta}
                  tipo: adr
              estados:
                vigente: [Aprobado]
                pendiente: [Propuesto]
                no_vigente: [Reemplazado, Deprecado]
            """), encoding="utf-8")

    def sincronizar(self) -> tuple[int, str]:
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = sync_arquitectura.main(["--raiz", str(self.raiz)])
        return codigo, salida.getvalue()

    def documentos(self) -> dict[str, dict]:
        indice = json.loads((self.raiz / "arquitectura" / "indice.json").read_text(encoding="utf-8"))
        return {d["id"]: d for d in indice["documentos"]}

    def test_indice_lock_y_lectura_de_adr(self) -> None:
        codigo, salida = self.sincronizar()
        self.assertEqual(codigo, 0, salida)

        documentos = self.documentos()
        self.assertEqual(set(documentos), {"ADR-001", "ADR-002", "ADR-003"}, "el README no se indexa")

        vigente = documentos["ADR-003"]
        self.assertEqual(vigente["estado"], "Aprobado")
        self.assertEqual(vigente["vigencia"], "vigente")
        self.assertEqual(vigente["fecha_creacion"], "2026-07-01")
        self.assertEqual(vigente["fecha_aprobacion"], "2026-07-01")
        self.assertEqual(vigente["regla_rapida"], "Cursor es el asistente de código estándar, con privacy mode activo.")
        self.assertEqual(vigente["reemplaza"], ["ADR-001"])

        reemplazado = documentos["ADR-001"]
        self.assertEqual(reemplazado["vigencia"], "no_vigente")
        self.assertEqual(reemplazado["reemplazado_por"], ["ADR-003"])
        self.assertEqual(reemplazado["reemplaza"], [])

        desconocido = documentos["ADR-002"]
        self.assertEqual(desconocido["vigencia"], "NO DETERMINADO")
        self.assertIn("En borrador", desconocido["motivo"])

        lock = json.loads((self.raiz / "arquitectura" / "fuentes.lock").read_text(encoding="utf-8"))
        self.assertEqual(lock["decision-records"]["commit"], self.commit_inicial)

        indice_md = (self.raiz / "arquitectura" / "INDICE.md").read_text(encoding="utf-8")
        self.assertIn("ADR-003", indice_md)
        self.assertIn("Documentos con vigencia NO DETERMINADO", indice_md)
        self.assertTrue((self.raiz / "arquitectura" / "decision-records" / "0003-adopcion-cursor.md").exists())

    def test_detecta_cambios_entre_sincronizaciones(self) -> None:
        self.sincronizar()
        adr = self.origen / "docs" / "adrs" / "0002-baseline-java.md"
        adr.write_text(ADR_ESTADO_DESCONOCIDO.replace("En borrador", "Aprobado"), encoding="utf-8")
        nuevo_commit = commit(self.origen, "Aprueba ADR-002")

        codigo, salida = self.sincronizar()
        self.assertEqual(codigo, 0, salida)
        self.assertIn("Documentos modificados: arquitectura/decision-records/0002-baseline-java.md", salida)
        self.assertIn("Cambio de vigencia: arquitectura/decision-records/0002-baseline-java.md: NO DETERMINADO -> vigente", salida)
        self.assertIn("Fuentes con commits nuevos: decision-records", salida)
        lock = json.loads((self.raiz / "arquitectura" / "fuentes.lock").read_text(encoding="utf-8"))
        self.assertEqual(lock["decision-records"]["commit"], nuevo_commit)

    def test_ruta_inexistente_es_un_error_y_conserva_lo_anterior(self) -> None:
        self.sincronizar()
        self.escribir_config(ruta="no-existe")
        codigo, salida = self.sincronizar()
        self.assertEqual(codigo, 1)
        self.assertIn("La ruta 'no-existe' no existe en la fuente 'decision-records'", salida)
        self.assertEqual(len(self.documentos()), 3, "se conservan los documentos de la sincronización anterior")

    def test_sin_fuentes_no_hace_nada(self) -> None:
        (self.raiz / "harness.yaml").write_text("version: 1\narquitectura:\n  fuentes: []\n", encoding="utf-8")
        codigo, salida = self.sincronizar()
        self.assertEqual(codigo, 0)
        self.assertIn("No hay fuentes de arquitectura", salida)
        self.assertFalse((self.raiz / "arquitectura").exists())


if __name__ == "__main__":
    unittest.main()
