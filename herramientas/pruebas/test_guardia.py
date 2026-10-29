"""Pruebas de la guardia de comandos de Cursor (.cursor/hooks.json)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import guardia  # noqa: E402
from comun import RAIZ  # noqa: E402


class PruebaGuardia(unittest.TestCase):

    def test_permisos(self) -> None:
        casos = {
            "git -C productos/motor-fraudes/repos/fraude-core push origin main": "deny",
            "cd productos/motor-fraudes/repos/fraude-core && git commit -am x": "deny",
            "git -C .cache/ramas/motor-fraudes/fraude-core/feature-buro checkout main": "deny",
            "git -C productos/motor-fraudes/repos/fraude-core reset --hard HEAD~1": "deny",
            "glab mr merge 12": "deny",
            "gh pr review 7 --approve": "deny",
            "curl -X POST https://gitlab.com/api/v4/projects/1/merge_requests/7/notes": "deny",
            "curl -s https://empresa.atlassian.net/rest/api/3/issue -d '{}'": "deny",
            ".venv/bin/python herramientas/rama.py publicar motor-fraudes fraude-core feature/buro --confirmar": "ask",
            ".venv/bin/python herramientas/jira.py crear motor-fraudes 001-agregar-timeout.md --confirmar": "ask",
            "git -C productos/motor-fraudes/repos/fraude-core log --oneline -5": "allow",
            "git -C productos/motor-fraudes/repos/merge-service log -1": "allow",
            "git -c core.pager=cat -C productos/motor-fraudes/repos/fraude-core tag v1": "deny",
            "git diff HEAD~1 -- herramientas/": "allow",
            "make revisar P=motor-fraudes R=fraude-core": "allow",
            "curl -s https://sonar.empresa.com/api/system/status": "allow",
        }
        for comando, esperado in casos.items():
            self.assertEqual(guardia.evaluar(comando)[0], esperado, comando)
        self.assertEqual(guardia.evaluar("git commit -m x", "/x/radiografia/productos/mf/repos/core")[0], "deny",
                         "también según la carpeta de trabajo")
        self.assertEqual(guardia.evaluar("git commit -m x", "/x/radiografia")[0], "allow",
                         "radiografia mismo sí se versiona")

    def test_hook_responde_json(self) -> None:
        salida = subprocess.run([sys.executable, str(RAIZ / "herramientas" / "guardia.py")], capture_output=True, text=True,
                                input=json.dumps({"command": "glab mr approve 3", "cwd": str(RAIZ)}), check=True).stdout
        respuesta = json.loads(salida)
        self.assertEqual(respuesta["permission"], "deny")
        self.assertIn("glab", respuesta["agentMessage"])
        configuracion = json.loads((RAIZ / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(configuracion["hooks"]["beforeShellExecution"][0]["command"], "python3 herramientas/guardia.py")


if __name__ == "__main__":
    unittest.main()
