#!/usr/bin/env bash
# Certificado wildcard *.<dominio> de Let's Encrypt con validación DNS-01 en Cloudflare.
#   sudo ./scripts/03-certificado-wildcard.sh
# Requiere CLOUDFLARE_API_TOKEN y ACME_EMAIL en .env. Idempotente.
#
# - Cambia el resolver "letsencrypt" de Traefik (el que usa Dokploy para todos los dominios) de HTTP-01
#   a DNS-01 con Cloudflare. Así los dominios bajo *.<dominio> usan el certificado wildcard.
# - Agrega un router "ancla" que mantiene el wildcard emitido y renovado aunque no haya dominios.
# - Recrea el contenedor dokploy-traefik con el token (Dokploy conserva sus variables al recrearlo).
source "$(dirname "$0")/lib.sh"
requiere_root
requiere_cmd docker jq python3 openssl

[[ -n "$CLOUDFLARE_API_TOKEN" ]] || morir "Define CLOUDFLARE_API_TOKEN en .env"
[[ "$ACME_EMAIL" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]] || morir "Define ACME_EMAIL en .env"
# Se valida con la zona (no con /user/tokens/verify, que rechaza los tokens de cuenta).
zona=$(curl -fsS -m 20 -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" "https://api.cloudflare.com/client/v4/zones?name=$DOMINIO" | jq -r '.result[0].id // empty' || true)
[[ -n "$zona" ]] || morir "El token de Cloudflare no es válido o no tiene acceso a la zona $DOMINIO."

TRAEFIK_YML=/etc/dokploy/traefik/traefik.yml
DINAMICO=/etc/dokploy/traefik/dynamic
ACME_JSON=$DINAMICO/acme.json

info "Resolver letsencrypt → DNS-01 (Cloudflare)"
cp --update=none "$TRAEFIK_YML" "$TRAEFIK_YML.original"
python3 - "$TRAEFIK_YML" "$ACME_EMAIL" <<'PY'
import sys, yaml
ruta, correo = sys.argv[1], sys.argv[2]
with open(ruta) as f:
    cfg = yaml.safe_load(f)
acme = cfg.setdefault("certificatesResolvers", {}).setdefault("letsencrypt", {}).setdefault("acme", {})
acme["email"] = correo
acme.setdefault("storage", "/etc/dokploy/traefik/dynamic/acme.json")
acme.pop("httpChallenge", None)
acme["dnsChallenge"] = {
    "provider": "cloudflare",
    "resolvers": ["1.1.1.1:53", "8.8.8.8:53"],
    "propagation": {"delayBeforeChecks": "10s"},
}
with open(ruta, "w") as f:
    yaml.safe_dump(cfg, f, sort_keys=False)
PY
ok "$TRAEFIK_YML actualizado (copia original en traefik.yml.original)"

cat > "$DINAMICO/zz-certificado-wildcard.yml" <<YML
# Ancla del certificado wildcard (03-certificado-wildcard.sh). No borrar: mantiene *.$DOMINIO
# emitido y renovado. Dokploy no gestiona este archivo.
http:
  routers:
    certificado-wildcard:
      rule: Host(\`certificado.$DOMINIO\`)
      entryPoints:
        - websecure
      service: noop@internal
      tls:
        certResolver: letsencrypt
        domains:
          - main: $DOMINIO
            sans:
              - "*.$DOMINIO"
YML
ok "router ancla en $DINAMICO/zz-certificado-wildcard.yml"

info "Recreando dokploy-traefik con el token de Cloudflare"
imagen=$(docker inspect dokploy-traefik --format '{{.Config.Image}}')
mapfile -t redes < <(docker inspect dokploy-traefik --format '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' | grep -v '^$')
mapfile -t env_previas < <(docker inspect dokploy-traefik --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -vE '^(PATH|CF_DNS_API_TOKEN)=' | grep -v '^$')
archivo_env=$(mktemp)
chmod 600 "$archivo_env"
printf '%s\n' "${env_previas[@]}" "CF_DNS_API_TOKEN=$CLOUDFLARE_API_TOKEN" | grep -v '^$' > "$archivo_env"
docker rm -f dokploy-traefik >/dev/null
docker run -d --name dokploy-traefik --restart always --network dokploy-network \
  --env-file "$archivo_env" \
  -v "$TRAEFIK_YML:/etc/traefik/traefik.yml" \
  -v "$DINAMICO:/etc/dokploy/traefik/dynamic" \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -p 80:80/tcp -p 443:443/tcp -p 443:443/udp \
  "$imagen" >/dev/null
rm -f "$archivo_env"
# Redes aisladas de los equipos a las que Traefik ya estaba conectado.
for r in "${redes[@]}"; do
  [[ "$r" == "dokploy-network" ]] || docker network connect "$r" dokploy-traefik 2>/dev/null || aviso "no se pudo reconectar a la red $r"
done
ok "dokploy-traefik recreado (${#redes[@]} red(es))"

info "Esperando el certificado *.$DOMINIO (hasta 4 minutos)"
for _ in $(seq 1 48); do
  if jq -e --arg d "*.$DOMINIO" '.letsencrypt.Certificates[]? | select(.domain.sans[]? == $d)' "$ACME_JSON" >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
if ! jq -e --arg d "*.$DOMINIO" '.letsencrypt.Certificates[]? | select(.domain.sans[]? == $d)' "$ACME_JSON" >/dev/null 2>&1; then
  docker logs --since 5m dokploy-traefik 2>&1 | grep -iE 'acme|error|cloudflare' | tail -15
  morir "El certificado no se emitió. Revisa los permisos del token y los logs de arriba."
fi

echo | openssl s_client -connect 127.0.0.1:443 -servername "certificado.$DOMINIO" 2>/dev/null \
  | openssl x509 -noout -subject -issuer -enddate -ext subjectAltName
ok "certificado wildcard emitido y servido por Traefik"
