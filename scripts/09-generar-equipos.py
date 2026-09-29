#!/usr/bin/env python3
"""Genera equipos/equipos.csv (público) y equipos/integrantes.csv (privado, correos por completar)
a partir de EQUIPOS.md del repositorio de retroalimentación y de la API pública de GitHub.

Uso: ./scripts/09-generar-equipos.py [--feedback ISCOUTB/AS_202620_feedback]
"""
import argparse
import csv
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Slugs más cortos para nombres largos; el resto se deriva del nombre del equipo.
SLUG_MANUAL = {
    "Calificación automática": "calificacion",
    "Tienda virtual UTB": "tiendautb",
}
ARCHIVOS_DEPLOY = re.compile(
    r"(^|/)(Dockerfile|docker-compose[^/]*\.ya?ml|compose[^/]*\.ya?ml)$", re.I)


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dokploy-platform",
                                               "Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def http_texto(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dokploy-platform"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def slug_de(nombre):
    if nombre in SLUG_MANUAL:
        return SLUG_MANUAL[nombre]
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feedback", default="ISCOUTB/AS_202620_feedback")
    ap.add_argument("--rama-feedback", default="master")
    args = ap.parse_args()

    org = args.feedback.split("/")[0]
    md = http_texto(f"https://raw.githubusercontent.com/{args.feedback}/{args.rama_feedback}/EQUIPOS.md")
    filas = re.findall(r"^\|\s*([^|]+?)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|", md, re.M)
    if not filas:
        sys.exit("No se encontró la tabla de equipos en EQUIPOS.md")

    equipos, integrantes = [], []
    for nombre, repo, miembros in filas:
        slug = slug_de(nombre)
        rama, existe, dockerfile, compose = "", "no", "no", "no"
        try:
            meta = http_json(f"https://api.github.com/repos/{org}/{repo}")
            rama, existe = meta["default_branch"], "si"
            arbol = http_json(f"https://api.github.com/repos/{org}/{repo}/git/trees/{rama}?recursive=1")
            rutas = [x["path"] for x in arbol.get("tree", []) if x["type"] == "blob"]
            encontrados = [p for p in rutas if ARCHIVOS_DEPLOY.search(p) and p.count("/") <= 2]
            dockerfile = ";".join(p for p in encontrados if p.lower().endswith("dockerfile")) or "no"
            compose = ";".join(p for p in encontrados if "compose" in p.lower()) or "no"
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
        nombres = [m.strip() for m in miembros.split("·") if m.strip()]
        equipos.append({"slug": slug, "equipo": nombre, "repo": repo, "rama": rama, "existe": existe,
                        "dockerfile": dockerfile, "compose": compose, "integrantes": len(nombres)})
        integrantes += [{"slug": slug, "nombre": n, "correo": ""} for n in nombres]

    slugs = [e["slug"] for e in equipos]
    duplicados = {s for s in slugs if slugs.count(s) > 1}
    if duplicados:
        sys.exit(f"Slugs duplicados: {duplicados}. Agrégalos a SLUG_MANUAL.")

    destino = os.path.join(RAIZ, "equipos")
    with open(os.path.join(destino, "equipos.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(equipos[0]))
        w.writeheader()
        w.writerows(equipos)

    # integrantes.csv es privado (tendrá correos). No se sobrescriben correos ya escritos.
    ruta_int = os.path.join(destino, "integrantes.csv")
    previos = {}
    if os.path.exists(ruta_int):
        with open(ruta_int) as f:
            previos = {(r["slug"], r["nombre"]): r["correo"] for r in csv.DictReader(f)}
    for i in integrantes:
        i["correo"] = previos.get((i["slug"], i["nombre"]), "")
    with open(ruta_int, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["slug", "nombre", "correo"])
        w.writeheader()
        w.writerows(integrantes)
    os.chmod(ruta_int, 0o600)

    faltan = sum(1 for i in integrantes if not i["correo"])
    print(f"{len(equipos)} equipos → equipos/equipos.csv")
    print(f"{len(integrantes)} integrantes → equipos/integrantes.csv ({faltan} sin correo)")
    for e in equipos:
        if e["existe"] == "no":
            print(f"  aviso: el repositorio {e['repo']} no es visible públicamente")


if __name__ == "__main__":
    main()
