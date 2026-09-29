"""Cliente mínimo de la API de Dokploy (tRPC expuesto como OpenAPI) y utilidades comunes.

Las rutas siguen el patrón /api/<router>.<procedimiento>: GET para consultas (input como query
string) y POST para mutaciones (input como JSON). Autenticación con la cabecera x-api-key.
"""
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Claves de identificador de cada tipo de servicio dentro de un entorno (project.one).
TIPOS_SERVICIO = {
    "applications": "applicationId", "compose": "composeId", "libsql": "libsqlId",
    "mariadb": "mariadbId", "mongo": "mongoId", "mysql": "mysqlId",
    "postgres": "postgresId", "redis": "redisId",
}

# Permisos de un estudiante: gestiona los servicios de su proyecto y nada de la infraestructura.
PERMISOS_ESTUDIANTE = {
    "canCreateProjects": False, "canDeleteProjects": False,
    "canCreateServices": True, "canDeleteServices": True,
    "canCreateEnvironments": False, "canDeleteEnvironments": False,
    "canAccessToDocker": False, "canAccessToTraefikFiles": False,
    "canAccessToAPI": False, "canAccessToSSHKeys": False,
    "canAccessToGitProviders": False,
    "accessedGitProviders": [], "accessedServers": [],
}


def cargar_env():
    env = {}
    ruta = os.path.join(RAIZ, ".env")
    if os.path.exists(ruta):
        with open(ruta) as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, v = linea.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("DOKPLOY_URL", "DOKPLOY_API_KEY", "GITHUB_ORG", "DOMINIO"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


class ErrorApi(Exception):
    pass


class Dokploy:
    def __init__(self, url=None, api_key=None):
        env = cargar_env()
        self.url = (url or env.get("DOKPLOY_URL") or "http://localhost:3000").rstrip("/")
        self.api_key = api_key or env.get("DOKPLOY_API_KEY")
        if not self.api_key:
            sys.exit("Falta DOKPLOY_API_KEY en .env (Dokploy → Settings → Profile → API/CLI).")

    def _pedir(self, metodo, ruta, datos=None):
        url = f"{self.url}/api/{ruta}"
        cuerpo = None
        if metodo == "GET" and datos:
            url += "?" + urllib.parse.urlencode(datos)
        elif metodo == "POST":
            cuerpo = json.dumps(datos or {}).encode()
        req = urllib.request.Request(url, data=cuerpo, method=metodo, headers={
            "x-api-key": self.api_key, "accept": "application/json",
            "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                texto = r.read().decode()
                return json.loads(texto) if texto else None
        except urllib.error.HTTPError as e:
            detalle = e.read().decode(errors="ignore")[:500]
            raise ErrorApi(f"{metodo} {ruta} → HTTP {e.code}: {detalle}") from None

    def get(self, ruta, **params):
        return self._pedir("GET", ruta, params)

    def post(self, ruta, datos=None):
        return self._pedir("POST", ruta, datos)


def leer_csv(nombre):
    ruta = os.path.join(RAIZ, "equipos", nombre)
    if not os.path.exists(ruta):
        return []
    with open(ruta, newline="") as f:
        return list(csv.DictReader(f))


def servicios_de_proyecto(proyecto):
    """Devuelve (ids de entornos, ids de servicios) de un proyecto de project.one."""
    entornos, servicios = [], []
    for env in proyecto.get("environments", []):
        entornos.append(env["environmentId"])
        for tipo, clave in TIPOS_SERVICIO.items():
            servicios += [s[clave] for s in env.get(tipo, []) or []]
    return entornos, servicios
