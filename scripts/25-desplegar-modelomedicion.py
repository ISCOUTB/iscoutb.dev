#!/usr/bin/env python3
"""Despliega Modelo de Medición (ISCOUTB/ModeloMedicionGruposInvestigacion, rama develop) en el proyecto
'modelomedicion' de Dokploy. Idempotente.

  ./scripts/25-desplegar-modelomedicion.py                 # crea/actualiza y despliega, esperando el resultado
  ./scripts/25-desplegar-modelomedicion.py --sin-desplegar # solo configura servicio, archivo, variables y dominio

El repositorio es privado: Dokploy lo clona con la GitHub App (origen "github") y el compose reducido,
plataforma/modelomedicion/compose.yaml, se monta como archivo del servicio (../files/compose.yaml) y se usa como
composePath. Los secretos se generan una vez y viven solo en Dokploy (Environment).
"""
import argparse
import os
import secrets
import string
import subprocess
import sys
import time

from dokploy import RAIZ, Dokploy, ErrorApi, cargar_env

PROYECTO = "modelomedicion"
SERVICIO = "sistema"
REPO, RAMA = "ModeloMedicionGruposInvestigacion", "develop"
RUTA_COMPOSE = os.path.join(RAIZ, "plataforma", "modelomedicion", "compose.yaml")
ARCHIVO = "compose.yaml"
DOMINIOS = [("modelomedicion", "api", 8000)]


def leer_env(texto):
    return {k: v for k, v in (l.split("=", 1) for l in (texto or "").splitlines() if "=" in l and not l.startswith("#"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-desplegar", action="store_true")
    ap.add_argument("--espera-max", type=int, default=1500)
    args = ap.parse_args()

    cfg = cargar_env()
    dominio, org = cfg.get("DOMINIO", "iscoutb.dev"), cfg.get("GITHUB_ORG", "ISCOUTB")
    api = Dokploy()
    plantilla = open(RUTA_COMPOSE).read()

    proyectos = {p["name"]: p["projectId"] for p in api.get("project.all")}
    if PROYECTO not in proyectos:
        sys.exit(f"No existe el proyecto '{PROYECTO}' (ejecuta 10-aprovisionar-equipos.py --equipo {PROYECTO}).")
    proyecto = api.get("project.one", projectId=proyectos[PROYECTO])
    entorno = next(e for e in proyecto["environments"] if e["name"] == "production")

    existente = next((c for c in entorno.get("compose", []) if c["name"] == SERVICIO), None)
    if existente:
        compose_id = existente["composeId"]
    else:
        nuevo = api.post("compose.create", {"name": SERVICIO, "environmentId": entorno["environmentId"], "composeType": "docker-compose",
                                            "appName": f"{PROYECTO}-{SERVICIO}", "description": "FastAPI + React + PostgreSQL + Redis"})
        compose_id = nuevo["composeId"]
        print("servicio Compose creado")
    github_id = api.get("github.githubProviders")[0]["githubId"]
    api.post("compose.update", {"composeId": compose_id, "sourceType": "github", "githubId": github_id, "owner": org,
                                "repository": REPO, "branch": RAMA, "composePath": f"../files/{ARCHIVO}",
                                "triggerType": "push", "autoDeploy": False, "isolatedDeployment": True})
    compose = api.get("compose.one", composeId=compose_id)

    # Archivo montado con el compose reducido (se actualiza en cada ejecución)
    montaje = next((m for m in compose.get("mounts", []) if m.get("type") == "file" and m.get("filePath") == ARCHIVO), None)
    if montaje:
        api.post("mounts.update", {"mountId": montaje["mountId"], "type": "file", "filePath": ARCHIVO, "content": plantilla,
                                   "serviceType": "compose", "serviceId": compose_id})
    else:
        api.post("mounts.create", {"type": "file", "filePath": ARCHIVO, "content": plantilla,
                                   "serviceType": "compose", "serviceId": compose_id, "mountPath": "/"})
    print("compose reducido montado en ../files/" + ARCHIVO)

    env = leer_env(compose.get("env"))
    alfanum = "".join
    por_defecto = {"DOMINIO": dominio,
                   "POSTGRES_PASSWORD": alfanum(secrets.choice(string.ascii_letters + string.digits) for _ in range(28)),
                   "SECRET_KEY": secrets.token_hex(32)}
    nuevas = [k for k in por_defecto if k not in env]
    env = {**por_defecto, **env}
    api.post("compose.saveEnvironment", {"composeId": compose_id, "createEnvFile": True, "env": "\n".join(f"{k}={v}" for k, v in env.items())})
    print(f"variables: {len(env)} ({len(nuevas)} generadas ahora)")

    hosts = {d["host"] for d in api.get("domain.byComposeId", composeId=compose_id)}
    for sub, servicio, puerto in DOMINIOS:
        host = f"{sub}.{dominio}"
        if host not in hosts:
            api.post("domain.create", {"host": host, "path": "/", "port": puerto, "https": True, "certificateType": "letsencrypt",
                                       "composeId": compose_id, "serviceName": servicio, "domainType": "compose", "stripPath": False})
            print(f"dominio https://{host} → {servicio}:{puerto}")

    if args.sin_desplegar:
        return
    previos = {d["deploymentId"] for d in api.get("compose.one", composeId=compose_id).get("deployments", [])}
    api.post("compose.deploy", {"composeId": compose_id, "title": "Despliegue de Modelo de Medición", "description": f"rama {RAMA}"})
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
    if estado == "error":
        dep = nuevo_dep[0]
        print("El despliegue falló. Fin del registro:")
        if dep.get("logPath"):
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
