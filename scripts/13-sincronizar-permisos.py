#!/usr/bin/env python3
"""Mantiene al día los proyectos de los equipos. Idempotente; solo llama a la API cuando algo cambió.

1. Da a cada estudiante acceso a TODO el proyecto de su equipo (entornos y servicios): en Dokploy un
   servicio nuevo solo queda visible para quien lo creó.
2. Activa "Isolated Deployment" en todo servicio Compose de un equipo. Sin él, los servicios con dominio
   comparten la red dokploy-network y un servicio "api" de un equipo puede resolverse en el "api" de otro.
   Los estudiantes crean el servicio a mano y pueden olvidarlo; el cambio rige desde el siguiente despliegue.

Pensado para cron:
    */5 * * * * /home/ubuntu/dokploy-platform/scripts/13-sincronizar-permisos.py --silencioso
"""
import argparse
import sys

from dokploy import PERMISOS_ESTUDIANTE, Dokploy, ErrorApi, leer_csv, servicios_de_proyecto


def sincronizar(api, silencioso=False):
    correo_a_slug = {i["correo"].strip().lower(): i["slug"]
                     for i in leer_csv("integrantes.csv") if i.get("correo", "").strip()}
    proyectos = {p["name"]: p["projectId"] for p in api.get("project.all")}
    cache_proyecto = {}
    cambios = 0
    for m in api.get("user.all"):
        if m.get("role") != "member":
            continue
        correo = (m.get("user") or {}).get("email", "").lower()
        slug = correo_a_slug.get(correo)
        if not slug:
            print(f"aviso: {correo} no está en integrantes.csv; no se le asigna proyecto", file=sys.stderr)
            continue
        if slug not in proyectos:
            print(f"aviso: no existe el proyecto '{slug}' (ejecuta 10-aprovisionar-equipos.py)", file=sys.stderr)
            continue
        pid = proyectos[slug]
        if pid not in cache_proyecto:
            cache_proyecto[pid] = servicios_de_proyecto(api.get("project.one", projectId=pid))
        entornos, servicios = cache_proyecto[pid]

        deseado = {"accessedProjects": [pid], "accessedEnvironments": entornos, "accessedServices": servicios}
        banderas_ok = all(m.get(k) == v for k, v in PERMISOS_ESTUDIANTE.items()
                          if not k.startswith("accessed"))
        listas_ok = all(set(m.get(k) or []) == set(v) for k, v in deseado.items())
        if banderas_ok and listas_ok:
            continue
        api.post("user.assignPermissions", {"id": m["userId"], **PERMISOS_ESTUDIANTE, **deseado})
        cambios += 1
        if not silencioso:
            print(f"{slug:<14} {correo}: {len(entornos)} entornos, {len(servicios)} servicios")
    aislados = forzar_aislamiento(api, {e["slug"] for e in leer_csv("equipos.csv")}, proyectos, silencioso)
    if not silencioso or cambios or aislados:
        print(f"Permisos actualizados: {cambios} · servicios Compose aislados ahora: {aislados}")


def forzar_aislamiento(api, slugs, proyectos, silencioso):
    activados = 0
    for slug in sorted(slugs & set(proyectos)):
        for env in api.get("project.one", projectId=proyectos[slug]).get("environments", []):
            for c in env.get("compose", []) or []:
                if not api.get("compose.one", composeId=c["composeId"]).get("isolatedDeployment"):
                    api.post("compose.update", {"composeId": c["composeId"], "isolatedDeployment": True})
                    activados += 1
                    print(f"{slug:<14} {c['name']}: Isolated Deployment activado (rige desde el próximo despliegue)")
    return activados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--silencioso", action="store_true")
    args = ap.parse_args()
    try:
        sincronizar(Dokploy(), args.silencioso)
    except ErrorApi as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
