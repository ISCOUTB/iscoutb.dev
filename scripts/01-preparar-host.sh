#!/usr/bin/env bash
# Prepara Ubuntu 26.04 en OCI para Dokploy. Idempotente: se puede volver a ejecutar.
#   sudo ./scripts/01-preparar-host.sh
source "$(dirname "$0")/lib.sh"
requiere_root
export DEBIAN_FRONTEND=noninteractive

info "Zona horaria: $ZONA_HORARIA"
timedatectl set-timezone "$ZONA_HORARIA"

info "Actualizando paquetes del sistema"
apt-get update -q
apt-get -y -q upgrade
apt-get install -y -q ca-certificates curl gnupg jq

info "Swap de ${SWAP_GB} GB"
if swapon --show=NAME --noheadings | grep -qx /swapfile; then
  ok "swap ya activo"
else
  fallocate -l "${SWAP_GB}G" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  ok "swap creado"
fi
cat > /etc/sysctl.d/90-dokploy.conf <<'EOF'
# Plataforma Dokploy (laboratorio de Arquitecturas de Software)
vm.swappiness = 10
fs.inotify.max_user_instances = 1024
fs.inotify.max_user_watches = 524288
EOF
sysctl --quiet --system

info "Firewall del host: permitir 80/tcp, 443/tcp y 443/udp antes del REJECT de Oracle"
# Las reglas se agregan a rules.v4 para que sobrevivan al reinicio. No se usa `netfilter-persistent save`:
# con Docker instalado guardaría sus cadenas y romperían al restaurarse antes de que Docker arranque.
REGLAS=/etc/iptables/rules.v4
declare -a NUEVAS=(
  "-A INPUT -p tcp -m state --state NEW -m tcp --dport 80 -j ACCEPT"
  "-A INPUT -p tcp -m state --state NEW -m tcp --dport 443 -j ACCEPT"
  "-A INPUT -p udp -m udp --dport 443 -j ACCEPT"
)
for r in "${NUEVAS[@]}"; do
  if ! grep -qxF -- "$r" "$REGLAS"; then
    # Inserta justo después de la regla del puerto 22.
    sed -i "\#^-A INPUT -p tcp -m state --state NEW -m tcp --dport 22 -j ACCEPT\$#a $r" "$REGLAS"
  fi
  # Aplica en caliente, antes del REJECT, sin recargar el archivo completo.
  regla_viva="${r#-A INPUT }"
  # shellcheck disable=SC2086
  if ! iptables -C INPUT $regla_viva 2>/dev/null; then
    pos=$(iptables -L INPUT --line-numbers -n | awk '/REJECT/ {print $1; exit}')
    # shellcheck disable=SC2086
    iptables -I INPUT "${pos:-1}" $regla_viva
  fi
done
ok "reglas INPUT: $(iptables -S INPUT | grep -cE 'dport (80|443)') de 3"

info "Docker CE $DOCKER_VERSION desde download.docker.com"
install -d -m 0755 /etc/docker
if [[ ! -f /etc/docker/daemon.json ]] || ! cmp -s "$RAIZ/config/daemon.json" /etc/docker/daemon.json; then
  install -m 0644 "$RAIZ/config/daemon.json" /etc/docker/daemon.json
  daemon_cambio=1
fi

if ! command -v docker >/dev/null 2>&1; then
  install -d -m 0755 /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${VERSION_CODENAME:-$(. /etc/os-release && echo "$VERSION_CODENAME")}
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt-get update -q
  version_pkg=$(apt-cache madison docker-ce | awk '{print $3}' | grep -E "^5:${DOCKER_VERSION//./\\.}-" | head -1)
  [[ -n "$version_pkg" ]] || morir "docker-ce $DOCKER_VERSION no está en el repositorio. Disponibles: $(apt-cache madison docker-ce | awk '{print $3}' | head -5 | tr '\n' ' ')"
  apt-get install -y -q \
    "docker-ce=$version_pkg" "docker-ce-cli=$version_pkg" "docker-ce-rootless-extras=$version_pkg" \
    containerd.io docker-buildx-plugin docker-compose-plugin
  ok "Docker instalado: $(docker --version)"
elif [[ "${daemon_cambio:-0}" -eq 1 ]]; then
  systemctl restart docker
fi
apt-mark hold docker-ce docker-ce-cli docker-ce-rootless-extras >/dev/null
systemctl enable --now docker containerd >/dev/null

usuario="${SUDO_USER:-ubuntu}"
if ! id -nG "$usuario" | grep -qw docker; then
  usermod -aG docker "$usuario"
  aviso "$usuario agregado al grupo docker (efectivo en la próxima sesión)."
fi

info "Actualizaciones automáticas de seguridad"
systemctl enable --now unattended-upgrades >/dev/null
ok "unattended-upgrades activo; los paquetes de Docker quedan retenidos"

echo
ok "Host listo. Siguiente paso: sudo ./scripts/02-instalar-dokploy.sh"
