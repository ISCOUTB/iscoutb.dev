#!/usr/bin/env python3
"""Despliega Check_U (ISCOUTB/check_u) en el proyecto 'checku' de Dokploy. Idempotente.

  ./scripts/17-desplegar-checku.py                 # crea/actualiza y despliega, esperando el resultado
  ./scripts/17-desplegar-checku.py --sin-desplegar # solo crea/actualiza proyecto, servicio, variables y dominios

Los secretos se generan una sola vez y viven únicamente en Dokploy (Environment del servicio): al volver
a ejecutar se conservan. El compose es plataforma/checku/compose.yaml.
"""
import argparse
import os
import subprocess
import sys
import time

from dokploy import RAIZ, Dokploy, ErrorApi, cargar_env

PROYECTO = "checku"
SERVICIO = "checku"
RUTA_COMPOSE = os.path.join(RAIZ, "plataforma", "checku", "compose.yaml")
# (subdominio, servicio del compose, puerto del contenedor)
DOMINIOS = [("checku", "frontend", 3000), ("api-checku", "backend", 3000), ("panel-checku", "panel", 5000)]


def leer_env(texto):
    return {k: v for k, v in (l.split("=", 1) for l in (texto or "").splitlines() if "=" in l and not l.startswith("#"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-desplegar", action="store_true")
    ap.add_argument("--espera-max", type=int, default=1500, help="segundos a esperar el despliegue")
    args = ap.parse_args()

    dominio = cargar_env().get("DOMINIO", "iscoutb.dev")
    api = Dokploy()
    plantilla = open(RUTA_COMPOSE).read()

    # 1. Proyecto y entorno production
    proyectos = {p["name"]: p["projectId"] for p in api.get("project.all")}
    if PROYECTO in proyectos:
        proyecto = api.get("project.one", projectId=proyectos[PROYECTO])
    else:
        creado = api.post("project.create", {"name": PROYECTO, "description": "Check_U · Proyecto Ingeniería I UTB (github.com/ISCOUTB/check_u)"})
        proyecto = api.get("project.one", projectId=creado["project"]["projectId"])
        print("proyecto creado")
    entorno = next((e for e in proyecto["environments"] if e["name"] == "production"), proyecto["environments"][0])

    # 2. Servicio Compose (origen "raw": el archivo vive en la plataforma, el código se construye desde git)
    existente = next((c for c in entorno.get("compose", []) if c["name"] == SERVICIO), None)
    if existente:
        compose_id = existente["composeId"]
    else:
        nuevo = api.post("compose.create", {"name": SERVICIO, "environmentId": entorno["environmentId"], "composeType": "docker-compose",
                                            "appName": SERVICIO, "sourceType": "raw", "composeFile": plantilla,
                                            "description": "Panel Flask (OCR de cédulas) + backend NestJS + frontend Next.js"})
        compose_id = nuevo["composeId"]
        print(f"servicio Compose creado ({nuevo['appName']})")
    api.post("compose.update", {"composeId": compose_id, "sourceType": "raw", "composeFile": plantilla,
                                "isolatedDeployment": True, "autoDeploy": False})
    compose = api.get("compose.one", composeId=compose_id)

    # 3. Variables: se conservan las existentes; se generan las que falten
    env = leer_env(compose.get("env"))
    por_defecto = {"DOMINIO": dominio, "CHECKU_REF": "main"}
    nuevas = [k for k in por_defecto if k not in env]
    env = {**por_defecto, **env}
    api.post("compose.saveEnvironment", {"composeId": compose_id, "createEnvFile": True, "env": "\n".join(f"{k}={v}" for k, v in env.items())})
    print(f"variables: {len(env)} ({len(nuevas)} generadas ahora; los valores están en Dokploy → checku → Environment)")

    # 4. Dominios con HTTPS (certificado wildcard de Traefik)
    hosts = {d["host"] for d in api.get("domain.byComposeId", composeId=compose_id)}
    for sub, servicio, puerto in DOMINIOS:
        host = f"{sub}.{dominio}"
        if host in hosts:
            continue
        api.post("domain.create", {"host": host, "path": "/", "port": puerto, "https": True, "certificateType": "letsencrypt",
                                   "composeId": compose_id, "serviceName": servicio, "domainType": "compose", "stripPath": False})
        print(f"dominio https://{host} → {servicio}:{puerto}")

    if args.sin_desplegar:
        return

    # 5. Despliegue y espera
    previos = {d["deploymentId"] for d in api.get("compose.one", composeId=compose_id).get("deployments", [])}
    api.post("compose.deploy", {"composeId": compose_id, "title": "Despliegue de Check_U", "description": f"ref {env['CHECKU_REF']}"})
    print("despliegue encolado; esperando…")
    inicio, ultimo = time.time(), None
    while time.time() - inicio < args.espera_max:
        time.sleep(10)
        c = api.get("compose.one", composeId=compose_id)
        estado = c["composeStatus"]
        nuevo_dep = [d for d in c.get("deployments", []) if d["deploymentId"] not in previos]
        if estado != ultimo:
            print(f"  [{int(time.time() - inicio):>4}s] estado: {estado}")
            ultimo = estado
        if estado in ("done", "error") and nuevo_dep:
            break
    else:
        sys.exit("Tiempo de espera agotado; revisa el despliegue en Dokploy.")

    dep = nuevo_dep[0] if nuevo_dep else None
    if estado == "error":
        print("El despliegue falló. Fin del registro:")
        if dep and dep.get("logPath"):
            print(subprocess.run(["sudo", "tail", "-n", "40", dep["logPath"]], capture_output=True, text=True).stdout)
        sys.exit(1)
    print("despliegue terminado")
    for sub, _, _ in DOMINIOS:
        print(f"  https://{sub}.{dominio}")


if __name__ == "__main__":
    try:
        main()
    except ErrorApi as e:
        sys.exit(str(e))
