#!/usr/bin/env python3
"""Configuración inicial de Dokploy por API (idempotente). Requiere DOKPLOY_API_KEY en .env.

  ./scripts/04-configurar-dokploy.py --email-acme docente@dominio

- Nombre de la organización del curso.
- 2 builds en paralelo (la VM tiene 2 vCPU), limpieza diaria de Docker y de logs de despliegue.
- Comparte la GitHub App con la organización para que los equipos la usen en servicios nuevos.
- Asigna panel.<dominio> con HTTPS; usa el wildcard emitido por 03-certificado-wildcard.sh.
"""
import argparse
import json
import sys
import time
import urllib.request

from dokploy import Dokploy, ErrorApi, cargar_env

NOMBRE_ORG = "Arquitecturas de Software 2026-2"


def dns_publico(host):
    url = f"https://dns.google/resolve?name={host}&type=A"
    with urllib.request.urlopen(url, timeout=10) as r:
        return [a["data"] for a in json.load(r).get("Answer", []) if a.get("type") == 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--email-acme", help="correo para Let's Encrypt (avisos de expiración)")
    ap.add_argument("--concurrencia", type=int, default=2)
    args = ap.parse_args()

    env = cargar_env()
    dominio = env.get("DOMINIO", "iscoutb.dev")
    ip = env.get("IP_PUBLICA", "")
    panel = env.get("PANEL_HOST", f"panel.{dominio}")
    api = Dokploy()

    org = api.get("organization.active")
    if org and org.get("name") != NOMBRE_ORG:
        api.post("organization.update", {"organizationId": org["id"], "name": NOMBRE_ORG})
        print(f"[ok] organización renombrada: {NOMBRE_ORG}")

    api.post("settings.updateBuildsConcurrency", {"buildsConcurrency": args.concurrencia})
    print(f"[ok] builds en paralelo: {args.concurrencia}")
    api.post("settings.updateDockerCleanup", {"enableDockerCleanup": True})
    print("[ok] limpieza diaria de Docker activada")
    api.post("settings.updateLogCleanup", {"cronExpression": "0 3 * * *"})
    print("[ok] limpieza de logs de despliegue: diaria 03:00")

    proveedores = [p for p in api.get("gitProvider.getAll") if p.get("providerType") == "github"]
    if not proveedores:
        print("[pendiente] GitHub App: Settings → Git → GitHub (ver docs/runbook-docente.md)")
    for p in proveedores:
        if not p.get("sharedWithOrganization"):
            api.post("gitProvider.toggleShare", {"gitProviderId": p["gitProviderId"], "sharedWithOrganization": True})
        print(f"[ok] proveedor GitHub '{p.get('name')}' compartido con la organización")

    actual = api.get("settings.getWebServerSettings") or {}
    if actual.get("host") == panel and actual.get("https"):
        print(f"[ok] panel ya asignado a https://{panel}")
        return
    if ip not in dns_publico(panel):
        print(f"[pendiente] {panel} aún no resuelve a {ip}; crea el registro A y vuelve a ejecutar.")
        return
    if not args.email_acme:
        sys.exit("Falta --email-acme para emitir el certificado del panel.")
    api.post("settings.assignDomainServer", {"host": panel, "certificateType": "letsencrypt",
                                             "letsEncryptEmail": args.email_acme, "https": True})
    print(f"[ok] panel asignado a {panel}; esperando el certificado…")
    for _ in range(24):
        try:
            with urllib.request.urlopen(f"https://{panel}", timeout=10) as r:
                print(f"[ok] https://{panel} responde con certificado válido (HTTP {r.status})")
                return
        except Exception:
            time.sleep(5)
    print(f"[aviso] el certificado aún no está listo; revisa: sudo docker logs dokploy-traefik")


if __name__ == "__main__":
    try:
        main()
    except ErrorApi as e:
        sys.exit(str(e))
