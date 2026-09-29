#!/usr/bin/env bash
# Comprueba desde el servidor la URL y el health check de cada equipo, con el mismo formato que las
# fichas de evaluación (S8, Corte 2, final). La comprobación oficial se hace desde fuera de la red.
#   ./scripts/22-verificar-despliegues.sh [slug]
source "$(dirname "$0")/lib.sh"

printf '%-14s %-38s %-26s %s\n' "equipo" "url" "raíz" "health"
while IFS=, read -r slug _; do
  [[ "$slug" == "slug" || -z "$slug" ]] && continue
  [[ -n "${1:-}" && "$slug" != "$1" ]] && continue
  url="https://$slug.$DOMINIO"
  raiz=$(curl -sS -o /dev/null -m 15 -w 'http=%{http_code} t=%{time_total}s' "$url" 2>/dev/null || echo "sin respuesta")
  health="-"
  for ruta in /health /api/health /healthz; do
    code=$(curl -sS -o /dev/null -m 10 -w '%{http_code}' "$url$ruta" 2>/dev/null || true)
    if [[ "$code" == "200" ]]; then health="200 $ruta"; break; fi
    [[ "$health" == "-" && -n "$code" && "$code" != "000" ]] && health="$code $ruta"
  done
  printf '%-14s %-38s %-26s %s\n' "$slug" "$url" "$raiz" "$health"
done < "$RAIZ/equipos/equipos.csv"
echo "Hora de la comprobación: $(date '+%Y-%m-%d %H:%M:%S %Z')"
