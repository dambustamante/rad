"""Guardia de los comandos de terminal que ejecuta Cursor en el harness (hook beforeShellExecution).

Lee de la entrada estándar el JSON del hook ({"command": "...", "cwd": "..."}) y responde con un permiso:

- deny: push a la rama principal (main, master) o con --force; acciones sobre MR o PR con glab o gh
  (aprobar, mergear, cerrar); escrituras HTTP directas (curl o wget con POST, PUT, PATCH o DELETE).
- allow: el resto, incluido el flujo normal de git en las ramas de trabajo.

Solo usa la biblioteca estándar.
"""

from __future__ import annotations

import json
import re
import sys

PUSH = re.compile(r"\bgit((\s+-[Cc]\s+\S+)|(\s+--[\w-]+(=\S+)?))*\s+push\b(?P<resto>[^|;&]*)")
PRINCIPAL = re.compile(r"(\s|:|/)(main|master)(\s|$)")
FORZADO = re.compile(r"(\s|^)(-f|--force|--force-with-lease)(\s|=|$)|\s\+\S")
CLI_PLATAFORMA = re.compile(r"\b(glab\s+mr|gh\s+pr)\s+(merge|approve|close|review)\b"
                            r"|\b(glab|gh)\s+api\b[^|;&]*(-X|--method)\s*(POST|PUT|PATCH|DELETE)\b", re.IGNORECASE)
HTTP_ESCRITURA = re.compile(r"\b(curl|wget)\b[^|;&]*(-X\s*|--request\s+|--method[=\s])(POST|PUT|PATCH|DELETE)\b"
                            r"|\bcurl\b[^|;&]*\s(-d|--data[\w-]*|-F|--form)\s", re.IGNORECASE)


def evaluar(comando: str) -> tuple[str, str]:
    push = PUSH.search(comando)
    if push and FORZADO.search(push.group("resto")):
        return "deny", "No se hace push con --force: se reescribe historia compartida."
    if push and PRINCIPAL.search(push.group("resto") + " "):
        return "deny", "No se hace push a la rama principal: se trabaja en una rama propia y se abre un MR."
    if CLI_PLATAFORMA.search(comando):
        return "deny", "Aprobar, mergear o cerrar MR no se hace desde aquí: se hace en GitLab, con su revisión."
    if HTTP_ESCRITURA.search(comando):
        return "deny", "No se escribe por HTTP directamente desde el harness."
    if re.search(r"(^|\s)--confirmar(\s|$)", comando):
        return "ask", "Este comando crea una Tarea en Jira. Aprobarlo solo si ya se revisó la vista previa."
    return "allow", ""


def main() -> int:
    try:
        entrada = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        entrada = {}
    permiso, motivo = evaluar(str(entrada.get("command") or ""))
    respuesta = {"permission": permiso}
    if motivo:
        respuesta.update({"userMessage": motivo, "agentMessage": motivo})
    print(json.dumps(respuesta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
