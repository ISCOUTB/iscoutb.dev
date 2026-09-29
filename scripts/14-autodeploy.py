#!/usr/bin/env python3
"""Consulta o cambia el despliegue automático (Autodeploy) de los servicios Compose de los equipos.

  ./scripts/14-autodeploy.py                    # estado de todos los equipos
  ./scripts/14-autodeploy.py --desactivar       # manual para todos (cola saturada, fechas de entrega)
  ./scripts/14-autodeploy.py --activar          # automático para todos
  ./scripts/14-autodeploy.py --desactivar --equipo routb --equipo drift

Con Autodeploy apagado los estudiantes despliegan con el botón Deploy del panel.
"""
import argparse
import sys

from dokploy import Dokploy, ErrorApi, leer_csv


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--activar", action="store_true")
    g.add_argument("--desactivar", action="store_true")
    ap.add_argument("--equipo", action="append", help="limitar a estos slugs (repetible)")
    a = ap.parse_args()

    api = Dokploy()
    proyectos = {p["name"]: p["projectId"] for p in api.get("project.all")}
    slugs = [e["slug"] for e in leer_csv("equipos.csv") if not a.equipo or e["slug"] in a.equipo]
    total = {True: 0, False: 0}
    for slug in slugs:
        if slug not in proyectos:
            continue
        for env in api.get("project.one", projectId=proyectos[slug]).get("environments", []):
            for c in env.get("compose", []) or []:
                actual = bool(api.get("compose.one", composeId=c["composeId"]).get("autoDeploy"))
                if a.activar or a.desactivar:
                    deseado = a.activar
                    if actual != deseado:
                        api.post("compose.update", {"composeId": c["composeId"], "autoDeploy": deseado})
                        print(f"{slug:<14} {env['name']}/{c['name']}: autodeploy {'activado' if deseado else 'desactivado'}")
                    actual = deseado
                total[actual] += 1
    print(f"Autodeploy activado en {total[True]} servicio(s), desactivado en {total[False]}.")


if __name__ == "__main__":
    try:
        main()
    except ErrorApi as e:
        sys.exit(str(e))
