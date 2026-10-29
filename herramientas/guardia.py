"""Guardia de los comandos de terminal que ejecuta Cursor (hook beforeShellExecution de .cursor/hooks.json).

Lee de la entrada estándar el JSON del hook ({"command": "...", "cwd": "..."}) y responde con un permiso:

- deny: escrituras de git en las copias de los productos (productos/*/repos/, .cache/ramas/), acciones
  sobre MR o PR con glab o gh, y escrituras HTTP directas (curl o wget con POST, PUT, PATCH o DELETE).
  Lo que sale hacia la plataforma git o Jira se hace solo con los scripts, que muestran vista previa.
- ask: todo comando con --confirmar (publicar en un MR o crear en Jira): Cursor pide la aprobación del
  usuario antes de ejecutarlo.
- allow: el resto.

Solo usa la biblioteca estándar, para que funcione aunque no exista .venv.
"""

from __future__ import annotations

import json
import re
import sys

COPIAS = re.compile(r"(^|[\s/'\"=])(productos/[^/\s]+/repos|\.cache/ramas)(/|\s|$|['\"])")
# git, sus opciones globales (-C ruta, -c clave=valor, --opción) y el subcomando que escribe.
GIT_ESCRITURA = re.compile(r"\bgit((\s+-[Cc]\s+\S+)|(\s+--[\w-]+(=\S+)?))*\s+(commit|push|merge|rebase|reset\s+--hard|"
                           r"cherry-pick|revert|tag|am|branch\s+-[dDmM]|clean\s+-[a-z]*f|checkout|switch|stash|restore)\b")
CLI_PLATAFORMA = re.compile(r"\b(glab\s+mr|gh\s+pr)\s+(merge|approve|close|create|review|comment|update|reopen)\b"
                            r"|\b(glab|gh)\s+api\b[^|;&]*(-X|--method)\s*(POST|PUT|PATCH|DELETE)\b", re.IGNORECASE)
HTTP_ESCRITURA = re.compile(r"\b(curl|wget)\b[^|;&]*(-X\s*|--request\s+|--method[=\s])(POST|PUT|PATCH|DELETE)\b"
                            r"|\bcurl\b[^|;&]*\s(-d|--data[\w-]*|-F|--form)\s", re.IGNORECASE)


def evaluar(comando: str, cwd: str = "") -> tuple[str, str]:
    """(permiso, motivo) para un comando de terminal."""
    en_copia = bool(COPIAS.search(comando)) or bool(re.search(r"/(productos/[^/]+/repos|\.cache/ramas)(/|$)", cwd))
    if en_copia and GIT_ESCRITURA.search(comando):
        return "deny", ("Las copias de los repositorios de los productos son de solo lectura: no se hacen commit, push, "
                        "merge, reset ni cambios de rama en ellas.")
    if CLI_PLATAFORMA.search(comando):
        return "deny", ("No se actúa sobre MR o PR con glab o gh. El único comentario se publica con "
                        "`rama.py publicar --confirmar`, después de la vista previa.")
    if HTTP_ESCRITURA.search(comando):
        return "deny", ("No se escribe por HTTP directamente. Lo que sale hacia la plataforma git o Jira se hace con los "
                        "scripts de herramientas/, que muestran la vista previa.")
    if re.search(r"\bgit\b[^|;&]*\bpush\b", comando) and (re.search(r"productos/[^/\s]+/harness", comando + " " + cwd)):
        return "ask", "Push del harness del producto: aprobarlo solo si ya se revisó lo que se sube."
    if re.search(r"(^|\s)--confirmar(\s|$)", comando):
        return "ask", "Este comando publica o crea algo fuera de radiografia. Aprobarlo solo si ya se revisó la vista previa."
    return "allow", ""


def main() -> int:
    try:
        entrada = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        entrada = {}
    permiso, motivo = evaluar(str(entrada.get("command") or ""), str(entrada.get("cwd") or ""))
    respuesta = {"permission": permiso}
    if motivo:
        respuesta.update({"userMessage": motivo, "agentMessage": motivo})
    print(json.dumps(respuesta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
