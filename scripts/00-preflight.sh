#!/usr/bin/env bash
# Verificación de solo lectura del estado del servidor. Se puede ejecutar en cualquier momento.
source "$(dirname "$0")/lib.sh"

fallos=0
falla() { error "$*"; fallos=$((fallos + 1)); }

info "Sistema"
. /etc/os-release
echo "    $PRETTY_NAME, kernel $(uname -r), $(uname -m)"
[[ "$VERSION_CODENAME" == "resolute" ]] || aviso "Los scripts se probaron en Ubuntu 26.04 (resolute)."

info "Recursos"
cpus=$(nproc)
ram_gb=$(awk '/MemTotal/ {printf "%.1f", $2/1024/1024}' /proc/meminfo)
swap_gb=$(awk '/SwapTotal/ {printf "%.1f", $2/1024/1024}' /proc/meminfo)
disco_libre=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
disco_uso=$(df --output=pcent / | tail -1 | tr -dc '0-9')
echo "    vCPU=$cpus RAM=${ram_gb}G swap=${swap_gb}G disco_libre=${disco_libre}G uso=${disco_uso}%"
[[ "$disco_uso" -lt 75 ]] || falla "Disco por encima del 75 %: ampliar el boot volume (ver runbook)."
awk -v s="$swap_gb" 'BEGIN{exit !(s+0 < 1)}' && aviso "Sin swap: ejecutar 01-preparar-host.sh."

info "Firewall del host (INPUT)"
for p in 80 443; do
  if sudo iptables -C INPUT -p tcp -m state --state NEW -m tcp --dport "$p" -j ACCEPT 2>/dev/null; then
    ok "INPUT acepta tcp/$p"
  else
    aviso "INPUT no acepta tcp/$p (ejecutar 01-preparar-host.sh)"
  fi
done

info "Docker"
if command -v docker >/dev/null 2>&1; then
  echo "    $(docker --version)"
  apt-mark showhold 2>/dev/null | grep -q '^docker-ce$' && ok "docker-ce retenido (apt-mark hold)" || aviso "docker-ce no está retenido"
  swarm=$(sudo docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null || echo "?")
  echo "    Swarm: $swarm"
else
  echo "    Docker no instalado todavía."
fi

info "Puertos 80/443/3000"
for p in 80 443 3000; do
  dueno=$(sudo ss -Htlnp "sport = :$p" 2>/dev/null | grep -oE 'users:\(\("[^"]+' | head -1 | cut -d'"' -f2 || true)
  if [[ -z "$dueno" ]]; then echo "    :$p libre"; else echo "    :$p en uso por $dueno"; fi
done

if command -v docker >/dev/null 2>&1 && sudo docker service ls >/dev/null 2>&1; then
  info "Servicios de Dokploy"
  sudo docker service ls --format '    {{.Name}} {{.Replicas}} {{.Image}}' | grep -E 'dokploy' || aviso "Dokploy no instalado."
  sudo docker ps --filter name=dokploy-traefik --format '    {{.Names}} {{.Status}} {{.Image}}'
fi

info "DNS público (debe apuntar a $IP_PUBLICA)"
hosts=("$PANEL_HOST" "$ESTADO_HOST")
if [[ -f "$RAIZ/equipos/equipos.csv" ]]; then
  while IFS=, read -r slug _; do
    [[ "$slug" == "slug" || -z "$slug" ]] && continue
    hosts+=("$slug.$DOMINIO")
  done < "$RAIZ/equipos/equipos.csv"
fi
sin_dns=0
for h in "${hosts[@]}"; do
  ips=$(resolver_a "$h")
  if [[ " $ips " == *" $IP_PUBLICA "* ]]; then
    ok "$h → $ips"
  else
    sin_dns=$((sin_dns + 1))
    printf '    %-40s → %s\n' "$h" "${ips:-(sin registro)}"
  fi
done
[[ "$sin_dns" -eq 0 ]] || aviso "$sin_dns nombre(s) aún sin DNS hacia $IP_PUBLICA."

info "Salida a Internet"
for u in https://github.com https://registry-1.docker.io/v2/ https://acme-v02.api.letsencrypt.org/directory; do
  code=$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$u" || echo 000)
  [[ "$code" != "000" ]] && ok "$u ($code)" || falla "Sin acceso a $u"
done

echo
if [[ "$fallos" -eq 0 ]]; then ok "Preflight sin fallos bloqueantes."; else error "$fallos fallo(s) bloqueante(s)."; exit 1; fi
