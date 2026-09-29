#!/usr/bin/env python3
"""Aprovisiona los equipos en Dokploy a partir de equipos/equipos.csv e equipos/integrantes.csv.

Por equipo crea (si no existen):
  - el proyecto <slug> con los entornos production y development;
  - con --compose, el servicio Compose "sistema" en production, conectado al repositorio del
    equipo por la GitHub App (deploy/compose.lab.yaml, autodeploy e Isolated Deployment);
  - con --cuentas, las cuentas de los integrantes con correo (rol member).
Al final sincroniza los permisos de cada estudiante con el proyecto de su equipo.

  ./scripts/10-aprovisionar-equipos.py                      # solo proyectos y entornos
  ./scripts/10-aprovisionar-equipos.py --compose            # + servicio Compose por equipo
  ./scripts/10-aprovisionar-equipos.py --cuentas            # + cuentas con contraseña inicial
  ./scripts/10-aprovisionar-equipos.py --equipo routb ...   # limitar a un equipo
"""
import argparse
import csv
import os
import secrets
import string
import sys

from dokploy import RAIZ, Dokploy, ErrorApi, cargar_env, leer_csv

RUTA_COMPOSE = "./deploy/compose.lab.yaml"
ENTORNOS = ["production", "development"]


def contrasena():
    alfabeto = string.ascii_letters + string.digits
    return "-".join("".join(secrets.choice(alfabeto) for _ in range(5)) for _ in range(4))


def asegurar_proyecto(api, equipo, proyectos):
    slug = equipo["slug"]
    if slug in proyectos:
        proyecto = api.get("project.one", projectId=proyectos[slug])
    else:
        desc = f"{equipo['equipo']} · github.com/{cargar_env().get('GITHUB_ORG', 'ISCOUTB')}/{equipo['repo']}"
        creado = api.post("project.create", {"name": slug, "description": desc})
        proyecto = api.get("project.one", projectId=creado["project"]["projectId"])
        print(f"  proyecto creado")
    existentes = {e["name"] for e in proyecto["environments"]}
    for nombre in ENTORNOS:
        if nombre not in existentes:
            api.post("environment.create", {"name": nombre, "projectId": proyecto["projectId"],
                                            "description": f"Entorno {nombre} de {slug}"})
            print(f"  entorno {nombre} creado")
    return api.get("project.one", projectId=proyecto["projectId"])


def asegurar_compose(api, equipo, proyecto, github_id, org):
    prod = next(e for e in proyecto["environments"] if e["name"] == "production")
    if any(c["name"] == "sistema" for c in prod.get("compose", [])):
        return
    creado = api.post("compose.create", {
        "name": "sistema", "environmentId": prod["environmentId"], "composeType": "docker-compose",
        "appName": f"{equipo['slug']}-sistema",
        "description": f"Sistema de {equipo['equipo']} desde {RUTA_COMPOSE}"})
    api.post("compose.update", {
        "composeId": creado["composeId"], "sourceType": "github", "githubId": github_id,
        "owner": org, "repository": equipo["repo"], "branch": equipo["rama"],
        "composePath": RUTA_COMPOSE, "autoDeploy": True, "triggerType": "push",
        "isolatedDeployment": True})
    print(f"  compose 'sistema' creado ({equipo['repo']}@{equipo['rama']}:{RUTA_COMPOSE})")


def asegurar_cuentas(api, slug, integrantes, correos_existentes, credenciales):
    for i in integrantes:
        correo = i["correo"].strip().lower()
        if not correo:
            print(f"  aviso: {i['nombre']} sin correo en integrantes.csv")
            continue
        if correo in correos_existentes:
            continue
        clave = contrasena()
        api.post("user.createUserWithCredentials", {"email": correo, "password": clave, "role": "member"})
        credenciales.append({"slug": slug, "nombre": i["nombre"], "correo": correo, "contrasena_inicial": clave})
        correos_existentes.add(correo)
        print(f"  cuenta creada: {correo}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compose", action="store_true", help="crear el servicio Compose por equipo")
    ap.add_argument("--cuentas", action="store_true", help="crear cuentas de estudiantes")
    ap.add_argument("--equipo", help="aprovisionar solo este slug")
    args = ap.parse_args()

    api = Dokploy()
    org = cargar_env().get("GITHUB_ORG", "ISCOUTB")
    equipos = [e for e in leer_csv("equipos.csv") if not args.equipo or e["slug"] == args.equipo]
    if not equipos:
        sys.exit("No hay equipos que aprovisionar (revisa equipos/equipos.csv o --equipo).")
    integrantes = leer_csv("integrantes.csv")

    github_id = None
    if args.compose:
        proveedores = api.get("github.githubProviders")
        if not proveedores:
            sys.exit("No hay GitHub App configurada (Settings → Git → GitHub). Ver docs/runbook-docente.md.")
        github_id = proveedores[0]["githubId"]

    correos_existentes = {(m.get("user") or {}).get("email", "").lower() for m in api.get("user.all")}
    proyectos = {p["name"]: p["projectId"] for p in api.get("project.all")}
    credenciales = []
    try:
        for e in equipos:
            print(f"{e['slug']} ({e['equipo']})")
            proyecto = asegurar_proyecto(api, e, proyectos)
            if args.compose and e["existe"] == "si":
                asegurar_compose(api, e, proyecto, github_id, org)
            if args.cuentas:
                asegurar_cuentas(api, e["slug"], [i for i in integrantes if i["slug"] == e["slug"]],
                                 correos_existentes, credenciales)
    except ErrorApi as err:
        print(f"ERROR: {err}", file=sys.stderr)
    finally:
        if credenciales:
            ruta = os.path.join(RAIZ, "equipos", "credenciales.csv")
            nuevo = not os.path.exists(ruta)
            with open(ruta, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(credenciales[0]))
                if nuevo:
                    w.writeheader()
                w.writerows(credenciales)
            os.chmod(ruta, 0o600)
            print(f"{len(credenciales)} credencial(es) nuevas en equipos/credenciales.csv (privado)")

    from importlib import import_module
    import_module("13-sincronizar-permisos").sincronizar(api)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
