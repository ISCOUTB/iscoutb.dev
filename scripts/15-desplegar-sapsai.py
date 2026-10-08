#!/usr/bin/env python3
"""Despliega SAPSAI (VerbaNexAI/sapsai) en el proyecto 'sapsai' de Dokploy. Idempotente.

  ./scripts/15-desplegar-sapsai.py                 # crea/actualiza y despliega, esperando el resultado
  ./scripts/15-desplegar-sapsai.py --sin-desplegar # solo crea/actualiza proyecto, servicio, variables y dominio

Los secretos se generan una sola vez y viven únicamente en Dokploy (Environment del servicio): al volver a
ejecutar se conservan. Las credenciales externas (R2, Google, correo) quedan con un valor de relleno hasta que
se editen en Dokploy → sapsai → Environment.

El origen es el propio repositorio (rama main, archivo docker-compose.dokploy.yml) por SSH con la llave "sapsai-deploy"
de Dokploy (deploy key con escritura en VerbaNexAI/sapsai) y autodeploy activado: Dokploy redespliega cuando GitHub
llama al webhook del servicio (Dokploy → sapsai → Deployments → Webhook URL), que se registra a mano en el repositorio.
"""
import argparse
import os
import secrets
import string
import subprocess
import sys
import time

from dokploy import Dokploy, ErrorApi, cargar_env

PROYECTO = "sapsai"
SERVICIO = "sapsai"
URL_GIT = "git@github.com:VerbaNexAI/sapsai.git"
RAMA = "main"
RUTA_COMPOSE = "./docker-compose.dokploy.yml"
LLAVE_SSH = "sapsai-deploy"
# (subdominio, servicio del compose, puerto del contenedor)
DOMINIOS = [("sapsai", "frontend", 80)]
PENDIENTE = "pendiente"


def alfanum(n):
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(n))


def leer_env(texto):
    return {k: v for k, v in (l.split("=", 1) for l in (texto or "").splitlines() if "=" in l and not l.startswith("#"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-desplegar", action="store_true")
    ap.add_argument("--espera-max", type=int, default=1800, help="segundos a esperar el despliegue")
    args = ap.parse_args()

    dominio = cargar_env().get("DOMINIO", "iscoutb.dev")
    api = Dokploy()

    proyectos = {p["name"]: p["projectId"] for p in api.get("project.all")}
    if PROYECTO in proyectos:
        proyecto = api.get("project.one", projectId=proyectos[PROYECTO])
    else:
        creado = api.post("project.create", {"name": PROYECTO, "description": "SAPSAI (github.com/VerbaNexAI/sapsai)"})
        proyecto = api.get("project.one", projectId=creado["project"]["projectId"])
        print("proyecto creado")
    entorno = next((e for e in proyecto["environments"] if e["name"] == "production"), proyecto["environments"][0])

    existente = next((c for c in entorno.get("compose", []) if c["name"] == SERVICIO), None)
    if existente:
        compose_id = existente["composeId"]
    else:
        nuevo = api.post("compose.create", {"name": SERVICIO, "environmentId": entorno["environmentId"], "composeType": "docker-compose",
                                            "appName": SERVICIO, "sourceType": "raw", "composeFile": "services: {}",
                                            "description": "Frontend + backend Bun/Prisma + clasificador TensorFlow + PostgreSQL"})
        compose_id = nuevo["composeId"]
        print(f"servicio Compose creado ({nuevo['appName']})")
    llave = next((k["sshKeyId"] for k in api.get("sshKey.all") if k["name"] == LLAVE_SSH), None)
    if not llave:
        sys.exit(f"Falta la llave SSH '{LLAVE_SSH}' en Dokploy (Settings → SSH Keys) con acceso al repositorio.")
    api.post("compose.update", {"composeId": compose_id, "sourceType": "git", "customGitUrl": URL_GIT, "customGitBranch": RAMA,
                                "customGitSSHKeyId": llave, "composePath": RUTA_COMPOSE, "enableSubmodules": False,
                                "watchPaths": [], "isolatedDeployment": True, "autoDeploy": True})
    compose = api.get("compose.one", composeId=compose_id)

    env = leer_env(compose.get("env"))
    por_defecto = {
        "DOMINIO": dominio,
        "DB_USERNAME": "leafuser", "DB_PASSWORD": alfanum(28), "DB_NAME": "leafapp",
        "JWT_ACCESS_SECRET": secrets.token_hex(32), "JWT_REFRESH_SECRET": secrets.token_hex(32), "SESSION_SECRET": secrets.token_hex(32),
        "DEFAULT_EMAIL": f"admin@{dominio}", "DEFAULT_USERNAME": "admin", "DEFAULT_PASSWORD": alfanum(20),
        "R2_ACCOUNT_ID": PENDIENTE, "R2_ACCESS_KEY_ID": PENDIENTE, "R2_SECRET_ACCESS_KEY": PENDIENTE,
        "R2_BUCKET_NAME": PENDIENTE, "R2_PUBLIC_BASE_URL": f"https://{PENDIENTE}.invalid",
        "GOOGLE_CLIENT_ID": PENDIENTE, "GOOGLE_CLIENT_SECRET": PENDIENTE,
    }
    nuevas = [k for k in por_defecto if k not in env]
    env = {**por_defecto, **env}
    api.post("compose.saveEnvironment", {"composeId": compose_id, "createEnvFile": True, "env": "\n".join(f"{k}={v}" for k, v in env.items())})
    print(f"variables: {len(env)} ({len(nuevas)} generadas ahora)")
    faltan = [k for k, v in env.items() if PENDIENTE in v]
    if faltan:
        print("  pendientes de configurar en Dokploy → sapsai → Environment: " + ", ".join(faltan))

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

    previos = {d["deploymentId"] for d in api.get("compose.one", composeId=compose_id).get("deployments", [])}
    api.post("compose.deploy", {"composeId": compose_id, "title": "Despliegue de SAPSAI", "description": f"rama {RAMA}"})
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
