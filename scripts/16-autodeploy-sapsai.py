#!/usr/bin/env python3
"""Redespliega sapsai cuando cambia la rama main de VerbaNexAI/sapsai (sustituye al webhook de GitHub).

Lo ejecuta cron cada 2 minutos (/etc/cron.d/sapsai-autodeploy). Consulta el último commit de la rama con
`git ls-remote` (el repositorio es público) y, si difiere del último desplegado, lanza el despliegue en Dokploy.
El último commit desplegado se guarda en reportes/sapsai-ultimo-commit; si no existe, se toma el actual sin desplegar.
Si registras el webhook de Dokploy en GitHub, borra /etc/cron.d/sapsai-autodeploy para no desplegar dos veces.
"""
import os
import subprocess
import sys
import time

from dokploy import RAIZ, Dokploy, ErrorApi

URL = "https://github.com/VerbaNexAI/sapsai.git"
RAMA = "main"
PROYECTO = SERVICIO = "sapsai"
ESTADO = os.path.join(RAIZ, "reportes", "sapsai-ultimo-commit")


def log(msg):
    print(f"{time.strftime('%F %T')} {msg}", flush=True)


def main():
    sha = subprocess.run(["git", "ls-remote", URL, f"refs/heads/{RAMA}"], capture_output=True, text=True, timeout=60,
                         env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}).stdout.split()[:1]
    if not sha:
        return log("no se pudo consultar GitHub; se reintenta")
    sha = sha[0]
    previo = open(ESTADO).read().strip() if os.path.exists(ESTADO) else None
    if previo is None:
        open(ESTADO, "w").write(sha)
        return log(f"estado inicial: {sha[:7]}")
    if sha == previo:
        return

    api = Dokploy()
    proyecto = next(p for p in api.get("project.all") if p["name"] == PROYECTO)
    compose = next(c for e in proyecto["environments"] for c in e.get("compose", []) if c["name"] == SERVICIO)
    if api.get("compose.one", composeId=compose["composeId"])["composeStatus"] == "running":
        return log("hay un despliegue en curso; se reintenta")
    api.post("compose.deploy", {"composeId": compose["composeId"], "title": f"Autodeploy {sha[:7]}", "description": f"{RAMA} {sha}"})
    open(ESTADO, "w").write(sha)
    log(f"despliegue lanzado: {previo[:7]} → {sha[:7]}")


if __name__ == "__main__":
    try:
        main()
    except (ErrorApi, subprocess.TimeoutExpired, StopIteration) as e:
        sys.exit(f"{time.strftime('%F %T')} error: {e!r}")
