#!/usr/bin/env bash
# Auditoría de seguridad, límites y dominios de los servicios de los equipos.
# Contenedores: docker.sock, bind mounts fuera de /etc/dokploy, privileged, capacidades extra,
#   red/PID del host, puertos publicados en el host y ausencia de límite de memoria.
# Dominios (base de Dokploy): cada equipo solo usa <slug>.<dominio> o <algo>-<slug>.<dominio>,
#   ningún nombre se repite entre proyectos y nadie usa los nombres reservados de la plataforma.
#   sudo ./scripts/20-auditar-servicios.sh      (reporte en reportes/auditoria-AAAAMMDD.txt)
# Sale con código 1 si hay hallazgos. Cron: lunes 07:00 (05-post-instalacion.sh).
source "$(dirname "$0")/lib.sh"
requiere_cmd docker jq python3
mkdir -p "$RAIZ/reportes"
reporte="$RAIZ/reportes/auditoria-$(date +%Y%m%d).txt"
: > "$reporte"

ids=$(docker ps -q)
if [[ -n "$ids" ]]; then
  # shellcheck disable=SC2086
  docker inspect $ids | jq -r '
    .[]
    | (.Name | ltrimstr("/")) as $n
    | select($n | test("^(dokploy|dokploy-postgres|dokploy-traefik)([.]|$)") | not)
    | (.Config.Labels["com.docker.compose.project"] // .Config.Labels["com.docker.swarm.service.name"] // $n) as $app
    | [
        (.Mounts[]? | select(.Source == "/var/run/docker.sock" or .Source == "/run/docker.sock") | "docker.sock montado"),
        (.Mounts[]? | select(.Type == "bind" and (.Source | startswith("/etc/dokploy/") | not)) | "bind mount del host: \(.Source)"),
        (if .HostConfig.Privileged then "privileged" else empty end),
        (.HostConfig.CapAdd // [] | .[] | "capacidad extra: \(.)"),
        (if .HostConfig.NetworkMode == "host" then "red del host" else empty end),
        (if .HostConfig.PidMode == "host" then "PID del host" else empty end),
        (.HostConfig.PortBindings // {} | to_entries[] | select(.value != null and (.value | length) > 0)
           | "puerto publicado en el host: \(.value[0].HostPort)->\(.key)"),
        (if (.HostConfig.Memory // 0) == 0 then "sin límite de memoria" else empty end)
      ][]
    | "\($app)\t\($n)\t\(.)"
  ' | sort -u | while IFS=$'\t' read -r app cont hallazgo; do
    # El límite de los servicios Swarm (tipo Application) está en el servicio, no en el contenedor.
    if [[ "$hallazgo" == "sin límite de memoria" ]] && docker service inspect "$app" >/dev/null 2>&1; then
      lim=$(docker service inspect "$app" --format '{{with .Spec.TaskTemplate.Resources}}{{with .Limits}}{{.MemoryBytes}}{{end}}{{end}}')
      [[ -n "$lim" && "$lim" != "0" ]] && continue
    fi
    printf '%s\t%s\t%s\n' "$app" "$cont" "$hallazgo"
  done >> "$reporte"
fi

pg=$(docker ps -qf name=dokploy-postgres)
if [[ -n "$pg" ]]; then
  docker exec "$pg" psql -U dokploy -d dokploy -AtF $'\t' -c '
    select p.name, d.host from domain d
    left join application a on a."applicationId" = d."applicationId"
    left join compose c on c."composeId" = d."composeId"
    join environment e on e."environmentId" = coalesce(a."environmentId", c."environmentId")
    join project p on p."projectId" = e."projectId"' 2>/dev/null \
  | python3 -c '
import csv, re, sys
from collections import defaultdict
dominio, ruta_csv = sys.argv[1], sys.argv[2]
slugs = {e["slug"] for e in csv.DictReader(open(ruta_csv))}
reservados = {f"{n}.{dominio}" for n in ("panel", "estado", "certificado", "www", "api", "mail")}
usos = defaultdict(set)
for linea in sys.stdin:
    if "\t" not in linea:
        continue
    proyecto, host = linea.rstrip("\n").split("\t", 1)
    host = host.lower()
    usos[host].add(proyecto)
    if proyecto not in slugs:
        continue  # proyectos de la plataforma (piloto, plataforma…)
    if host.endswith(".traefik.me"):
        continue
    propio = re.fullmatch(rf"({re.escape(proyecto)}|[a-z0-9-]+-{re.escape(proyecto)})\.{re.escape(dominio)}", host)
    if host in reservados:
        print(f"{proyecto}\t-\tdominio reservado de la plataforma: {host}")
    elif not propio:
        print(f"{proyecto}\t-\tdominio fuera de su espacio ({proyecto}.{dominio} o <algo>-{proyecto}.{dominio}): {host}")
for host, proyectos in usos.items():
    if len(proyectos) > 1:
        print(f"{",".join(sorted(proyectos))}\t-\tdominio usado por varios proyectos: {host}")
' "$DOMINIO" "$RAIZ/equipos/equipos.csv" >> "$reporte"
fi

if [[ -s "$reporte" ]]; then
  error "$(wc -l < "$reporte") hallazgo(s) — $reporte"
  awk -F'\t' '{printf "  %-34s %s\n", $1, $3}' "$reporte"
  exit 1
fi
ok "Sin hallazgos ($(echo "$ids" | grep -c . || true) contenedores y dominios revisados)."
