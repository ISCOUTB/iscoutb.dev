#!/usr/bin/env bash
# Registro DNS de la plataforma en Cloudflare: un wildcard *.<dominio> hacia el servidor.
# Con él, panel.<dominio>, <equipo>.<dominio> y <algo>-<equipo>.<dominio> resuelven sin más registros.
#   ./scripts/11-dns-cloudflare.sh
# Requiere CLOUDFLARE_API_TOKEN en .env (Zone:DNS:Edit y Zone:Zone:Read sobre la zona).
# El registro queda en "DNS only" (sin proxy de Cloudflare): el certificado es de Let's Encrypt y la
# latencia que miden los equipos es la del servidor.
source "$(dirname "$0")/lib.sh"
requiere_cmd curl jq

cf() {
  local metodo="$1" ruta="$2" datos="${3:-}"
  curl -fsS -m 30 -X "$metodo" "https://api.cloudflare.com/client/v4$ruta" \
    -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" \
    ${datos:+--data "$datos"}
}

[[ -n "$CLOUDFLARE_API_TOKEN" ]] || morir "Define CLOUDFLARE_API_TOKEN en .env"
# No se usa /user/tokens/verify: los tokens de cuenta (Account API Tokens) responden 401 ahí aunque sean válidos.
zona=$(cf GET "/zones?name=$DOMINIO" 2>/dev/null | jq -r '.result[0].id // empty' || true)
[[ -n "$zona" ]] || morir "El token no es válido o no tiene acceso a la zona $DOMINIO (Zone:Zone:Read)."
cf GET "/zones/$zona/dns_records?per_page=1" >/dev/null 2>&1 || morir "El token no puede leer los registros DNS (Zone:DNS:Edit)."
ok "token válido para la zona $DOMINIO"

nombre="*.$DOMINIO"
actual=$(cf GET "/zones/$zona/dns_records?type=A&name=$(jq -rn --arg n "$nombre" '$n|@uri')" | jq -c '.result[0] // empty')
deseado=$(jq -cn --arg ip "$IP_PUBLICA" '{type:"A", name:"*", content:$ip, ttl:1, proxied:false,
  comment:"Dokploy · servidor del laboratorio de Arquitecturas de Software"}')

if [[ -z "$actual" ]]; then
  cf POST "/zones/$zona/dns_records" "$deseado" >/dev/null
  ok "creado $nombre → $IP_PUBLICA (DNS only)"
elif [[ "$(jq -r .content <<<"$actual")" != "$IP_PUBLICA" || "$(jq -r .proxied <<<"$actual")" != "false" ]]; then
  cf PUT "/zones/$zona/dns_records/$(jq -r .id <<<"$actual")" "$deseado" >/dev/null
  ok "actualizado $nombre → $IP_PUBLICA (DNS only)"
else
  ok "$nombre ya apunta a $IP_PUBLICA"
fi

info "Comprobando resolución pública"
for h in "$PANEL_HOST" "prueba-$RANDOM.$DOMINIO"; do
  for _ in $(seq 1 12); do
    [[ " $(resolver_a "$h") " == *" $IP_PUBLICA "* ]] && break
    sleep 5
  done
  ips=$(resolver_a "$h")
  [[ " $ips " == *" $IP_PUBLICA "* ]] && ok "$h → $ips" || aviso "$h aún no resuelve (propagación en curso)"
done
