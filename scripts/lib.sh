# shellcheck shell=bash
# Funciones comunes para los scripts de la plataforma. Se incluye con: source "$(dirname "$0")/lib.sh"

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Valores por defecto; .env los sobrescribe.
DOMINIO="iscoutb.dev"
IP_PUBLICA=""   # obligatoria: se define en .env
IP_PRIVADA=""   # obligatoria para 02-instalar-dokploy.sh: se define en .env
DOKPLOY_VERSION="v0.30.7"
DOCKER_VERSION="29.8.1"
ZONA_HORARIA="America/Bogota"
SWAP_GB=4
GITHUB_ORG="ISCOUTB"
REPO_PREFIX="AS_202620_"
DOKPLOY_URL=""
DOKPLOY_API_KEY=""
CLOUDFLARE_API_TOKEN=""
ACME_EMAIL=""

if [[ -f "$RAIZ/.env" ]]; then
  # shellcheck disable=SC1091
  source "$RAIZ/.env"
fi

PANEL_HOST="${PANEL_HOST:-panel.$DOMINIO}"
ESTADO_HOST="${ESTADO_HOST:-estado.$DOMINIO}"
DOKPLOY_URL="${DOKPLOY_URL:-https://$PANEL_HOST}"

if [[ -t 1 ]]; then
  C_OK=$'\033[0;32m'; C_WARN=$'\033[1;33m'; C_ERR=$'\033[0;31m'; C_INFO=$'\033[0;34m'; C_FIN=$'\033[0m'
else
  C_OK=""; C_WARN=""; C_ERR=""; C_INFO=""; C_FIN=""
fi

info()  { printf '%s==>%s %s\n' "$C_INFO" "$C_FIN" "$*"; }
ok()    { printf '%s[ok]%s %s\n' "$C_OK" "$C_FIN" "$*"; }
aviso() { printf '%s[aviso]%s %s\n' "$C_WARN" "$C_FIN" "$*" >&2; }
error() { printf '%s[error]%s %s\n' "$C_ERR" "$C_FIN" "$*" >&2; }
morir() { error "$*"; exit 1; }

requiere_root() {
  [[ "$(id -u)" -eq 0 ]] || morir "Ejecuta este script con sudo."
}

requiere_cmd() {
  local c
  for c in "$@"; do command -v "$c" >/dev/null 2>&1 || morir "Falta el comando '$c'."; done
}

# Resuelve un nombre usando DNS público (evita cachés locales).
resolver_a() {
  curl -fsS -m 8 "https://dns.google/resolve?name=$1&type=A" 2>/dev/null \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(" ".join(a["data"] for a in d.get("Answer",[]) if a.get("type")==1))' 2>/dev/null || true
}

# Llamada a la API de Dokploy (tRPC sobre HTTP). Uso: dokploy_api GET|POST ruta [json]
dokploy_api() {
  local metodo="$1" ruta="$2" cuerpo="${3:-}"
  [[ -n "$DOKPLOY_API_KEY" ]] || morir "Define DOKPLOY_API_KEY en $RAIZ/.env (Settings → Profile → API/CLI)."
  if [[ "$metodo" == "GET" ]]; then
    curl -fsS -m 30 -H "x-api-key: $DOKPLOY_API_KEY" -H 'accept: application/json' "$DOKPLOY_URL/api/$ruta"
  else
    curl -fsS -m 60 -X POST -H "x-api-key: $DOKPLOY_API_KEY" -H 'accept: application/json' \
      -H 'Content-Type: application/json' -d "$cuerpo" "$DOKPLOY_URL/api/$ruta"
  fi
}
