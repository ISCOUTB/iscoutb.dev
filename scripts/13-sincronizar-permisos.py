#!/usr/bin/env python3
"""Da a cada estudiante acceso a TODO el proyecto de su equipo (entornos y servicios).

En Dokploy un servicio nuevo solo queda visible para quien lo creó; este script lo comparte con
el resto del equipo. Es idempotente y solo llama a la API cuando algo cambió. Pensado para cron:
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
    if not silencioso or cambios:
        print(f"Permisos actualizados: {cambios}")


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
