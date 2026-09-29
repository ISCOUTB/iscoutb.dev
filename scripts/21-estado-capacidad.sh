#!/usr/bin/env bash
# Uso de CPU/RAM por equipo (prefijo del nombre de la app) y estado del disco.
#   sudo ./scripts/21-estado-capacidad.sh
source "$(dirname "$0")/lib.sh"
requiere_cmd docker

info "Host"
free -h | awk 'NR<=3'
df -h / | awk 'NR==2 {print "Disco /: " $3 " usados de " $2 " (" $5 ")"}'
uso=$(df --output=pcent / | tail -1 | tr -dc '0-9')
[[ "$uso" -lt 75 ]] || aviso "Disco por encima del 75 %: limpiar imágenes o ampliar el boot volume."

info "Docker"
docker system df

info "Consumo por equipo (contenedores en ejecución)"
docker stats --no-stream --format '{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' | python3 -c '
import re, sys
def mib(v):
    n, u = re.match(r"([\d.]+)\s*([KMG]i?B)", v).groups()
    return float(n) * {"KiB": 1/1024, "MiB": 1, "GiB": 1024, "KB": 1/1000, "MB": 1, "GB": 1000}[u]
equipos = {}
for linea in sys.stdin:
    nombre, cpu, mem = linea.rstrip("\n").split("\t")
    base = nombre.split(".")[0]
    eq = "plataforma" if base.startswith("dokploy") else base.split("-")[0]
    e = equipos.setdefault(eq, [0, 0.0, 0.0])
    e[0] += 1; e[1] += float(cpu.rstrip("%")); e[2] += mib(mem.split("/")[0])
print("%-16s%6s%9s%10s" % ("equipo", "cont.", "CPU %", "RAM MiB"))
for eq, (n, cpu, mem) in sorted(equipos.items(), key=lambda x: -x[1][2]):
    alerta = "  ← supera 512 MiB" if eq != "plataforma" and mem > 512 else ""
    print(f"{eq:<16}{n:>6}{cpu:>9.1f}{mem:>10.0f}{alerta}")
'
