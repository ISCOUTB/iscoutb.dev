#!/usr/bin/env bash
# Instala Dokploy con versión fijada usando el instalador oficial revisado en vendor/.
#   sudo ./scripts/02-instalar-dokploy.sh
# Docker debe estar instalado antes (01-preparar-host.sh): el instalador oficial intenta instalar
# Docker 28.5.0, que no existe para Ubuntu 26.04 (https://github.com/Dokploy/dokploy/issues/5471).
source "$(dirname "$0")/lib.sh"
requiere_root
requiere_cmd docker curl

INSTALADOR="$RAIZ/vendor/dokploy-install.sh"
mkdir -p "$RAIZ/vendor"
# sha256 del install.sh revisado el 2026-09-28. Si cambia, revisar el diff antes de actualizar este valor.
SHA_REVISADO="92749e5fe1678d1a2dc1e5bad193a1e113fcdbee3cf24193fc14ab85765b6b8a"

if docker service inspect dokploy >/dev/null 2>&1; then
  ok "Dokploy ya está instalado: $(docker service inspect dokploy --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}' | cut -d@ -f1)"
  exit 0
fi

[[ -f "$INSTALADOR" ]] || curl -fsSL https://dokploy.com/install.sh -o "$INSTALADOR"
sha=$(sha256sum "$INSTALADOR" | cut -d' ' -f1)
[[ "$sha" == "$SHA_REVISADO" ]] || morir "El instalador cambió (sha256 $sha). Revísalo y actualiza SHA_REVISADO."

info "Instalando Dokploy $DOKPLOY_VERSION (advertise $IP_PRIVADA)"
DOKPLOY_VERSION="$DOKPLOY_VERSION" ADVERTISE_ADDR="$IP_PRIVADA" bash "$INSTALADOR" 2>&1 | tee "$RAIZ/vendor/instalacion-$(date +%Y%m%d-%H%M).log"

info "Esperando a que el panel responda en localhost:3000"
for _ in $(seq 1 60); do
  code=$(curl -s -o /dev/null -m 5 -w '%{http_code}' http://localhost:3000 || true)
  [[ "$code" =~ ^(200|302|307)$ ]] && break
  sleep 5
done
[[ "$code" =~ ^(200|302|307)$ ]] || morir "El panel no respondió (HTTP $code). Revisa: docker service logs dokploy"

docker service ls --format '    {{.Name}} {{.Replicas}} {{.Image}}'
docker ps --filter name=dokploy-traefik --format '    {{.Names}} {{.Status}} {{.Image}}'
echo
ok "Dokploy responde (HTTP $code)."
cat <<EOF

SIGUIENTE PASO (hazlo ya: la primera cuenta registrada queda como owner):
  1. En VS Code, pestaña PORTS → Forward a Port → 3000.
  2. Abre http://localhost:3000 y registra la cuenta del docente.
  El puerto 3000 NO debe abrirse en el Security List de OCI.
EOF
