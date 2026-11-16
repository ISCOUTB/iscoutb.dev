#!/usr/bin/env bash
# Vigila el disco: avisa de contenedores cuya capa escribible crece sin control y libera lo recuperable.
#   sudo ./scripts/26-vigilar-disco.sh            # solo informa
#   sudo ./scripts/26-vigilar-disco.sh --limpiar  # además limpia (lo usa el cron diario)
#
# Causa típica de crecimiento: Neo4j descomprime su navegador web en /tmp (decompressed-browser*, ~90 MB cada
# vez) y no lo borra; un contenedor en bucle de reinicios o con muchas peticiones llena el disco en días.
# La defensa de fondo es "tmpfs: /tmp" con tamaño en el compose (ver plantillas/); esto es la red de seguridad.
#
# Variables: LIMITE_CAPA_GB (def. 5) · UMBRAL_DISCO (def. 80, % de uso de /)
source "$(dirname "$0")/lib.sh"
requiere_cmd docker

LIMITE_CAPA_GB="${LIMITE_CAPA_GB:-5}"
UMBRAL_DISCO="${UMBRAL_DISCO:-80}"
limpiar=0; [[ "${1:-}" == "--limpiar" ]] && limpiar=1

uso() { df --output=pcent / | tail -1 | tr -dc '0-9'; }
echo "$(date '+%F %T') disco / al $(uso) %"

info "Contenedores con capa escribible > ${LIMITE_CAPA_GB} GB"
excedidos=0
while IFS=$'\t' read -r nombre tam; do
  # tam llega como "132GB (virtual 133GB)"; solo interesa la parte escribible.
  escribible="${tam%% *}"
  gb=$(python3 - "$escribible" <<'PY'
import re, sys
m = re.match(r"([\d.]+)\s*([kMGT]?B)", sys.argv[1])
n, u = float(m.group(1)), m.group(2)
print(round(n * {"B": 1e-9, "kB": 1e-6, "MB": 1e-3, "GB": 1, "TB": 1e3}[u], 1))
PY
)
  if python3 -c "import sys; sys.exit(0 if float('$gb') > float('$LIMITE_CAPA_GB') else 1)"; then
    excedidos=$((excedidos + 1))
    aviso "$nombre escribe ${gb} GB fuera de volúmenes"
    if [[ $limpiar -eq 1 ]]; then
      # Fuga conocida de Neo4j: se borra solo esa basura; no se toca nada más del contenedor.
      docker exec "$nombre" sh -c 'rm -rf /tmp/decompressed-browser* 2>/dev/null' 2>/dev/null \
        && ok "$nombre: /tmp/decompressed-browser* eliminado"
    fi
  fi
done < <(docker ps -s --format '{{.Names}}\t{{.Size}}')
[[ $excedidos -gt 0 ]] || ok "ninguno"

if [[ $limpiar -eq 1 ]]; then
  info "Limpieza de imágenes sin uso (>7 días) y caché de build"
  docker image prune -af --filter "until=168h" | tail -1
  docker builder prune -af --filter "until=168h" | tail -1
fi

actual=$(uso)
if [[ "$actual" -ge "$UMBRAL_DISCO" ]]; then
  error "Disco / al ${actual} % (umbral ${UMBRAL_DISCO} %): revisar scripts/21-estado-capacidad.sh y ampliar el volumen."
  exit 1
fi
ok "Disco / al ${actual} %"
