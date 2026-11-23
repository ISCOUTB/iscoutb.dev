#!/usr/bin/env python3
"""Suspende proyectos sin uso y bloquea cuentas de estudiantes que no entran al panel.

Dos reglas independientes:
  · PROYECTO: sin tráfico ni despliegues en DIAS_PROYECTO (30) días → se detienen sus servicios.
    Los volúmenes y datos se conservan; reactivar = arrancarlos de nuevo.
  · CUENTA: el estudiante (rol member) no inicia sesión en DIAS_CUENTA (90) días → cuenta bloqueada
    (user.banned) y sesiones cerradas. Solo se desbloquean las que bloqueó este script.

Señales de uso de un proyecto (gana la más reciente):
  - tráfico: peticiones exitosas a sus routers de Traefik (el log rota en horas, por eso --registrar
    guarda la última fecha en reportes/actividad.json);
  - último despliegue en Dokploy;
  - "vigilado desde": primer registro del script, para no suspender nada hasta tener historial.
Se ignoran health checks, estáticos de rutina y peticiones desde la propia máquina (IGNORAR_IPS).

Uso:
    ./27-suspender-inactivos.py --registrar          # anota actividad (cron cada 15 min)
    ./27-suspender-inactivos.py                      # informe en seco: qué se suspendería hoy
    ./27-suspender-inactivos.py --aplicar            # suspende y bloquea (cron diario)
    ./27-suspender-inactivos.py --reactivar SLUG     # arranca el proyecto y le da otro mes de plazo
    ./27-suspender-inactivos.py --desbloquear CORREO # desbloquea una cuenta
Variables: DIAS_PROYECTO · DIAS_CUENTA · IGNORAR_IPS (separadas por coma, además de loopback y 172.16/12)
"""
import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from dokploy import RAIZ, Dokploy, ErrorApi, leer_csv

DIAS_PROYECTO = int(os.environ.get("DIAS_PROYECTO", 30))
DIAS_CUENTA = int(os.environ.get("DIAS_CUENTA", 90))
IGNORAR_IPS = [i.strip() for i in os.environ.get("IGNORAR_IPS", "").split(",") if i.strip()]
ESTADO = os.path.join(RAIZ, "reportes", "actividad.json")
MOTIVO_BAN = "Inactividad: sin iniciar sesión en {} días (script 27)"
PG = "dokploy-postgres"

# Tipo de servicio → (clave del identificador, ruta de la API).
TIPOS = {"compose": "composeId", "applications": "applicationId", "postgres": "postgresId",
         "mysql": "mysqlId", "mariadb": "mariadbId", "mongo": "mongoId", "redis": "redisId",
         "libsql": "libsqlId"}
RUTA = {"compose": "compose", "applications": "application"}  # el resto usa su propio nombre
RUTAS_RUTINA = re.compile(r"^/(health|healthz|ping|status|metrics|favicon\.ico|robots\.txt)\b", re.I)
LOG = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) [^"]*" (\d{3}) \S+ "[^"]*" "[^"]*" \d+ "([^"]+)"')


def ahora():
    return datetime.now(timezone.utc)


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def psql(sql):
    """Ejecuta SQL en el Postgres de Dokploy; devuelve filas separadas por '|'."""
    nombre = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True,
                            check=True).stdout.split()
    contenedor = next((n for n in nombre if n.startswith(PG)), None)
    if not contenedor:
        sys.exit(f"No encuentro el contenedor {PG}")
    r = subprocess.run(["docker", "exec", contenedor, "psql", "-U", "dokploy", "-d", "dokploy",
                        "-At", "-F", "|", "-c", sql], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"psql: {r.stderr.strip()}")
    return [f.split("|") for f in r.stdout.splitlines() if f]


def cargar():
    try:
        with open(ESTADO) as f:
            e = json.load(f)
    except (OSError, ValueError):
        e = {}
    e.setdefault("vigilado_desde", iso(ahora()))
    e.setdefault("proyectos", {})   # slug → {"ultimo_trafico": iso}
    e.setdefault("suspendidos", {})  # slug → {"desde": iso, "servicios": [[tipo, id], ...]}
    return e


def guardar(e):
    os.makedirs(os.path.dirname(ESTADO), exist_ok=True)
    tmp = ESTADO + ".tmp"
    with open(tmp, "w") as f:
        json.dump(e, f, indent=1, sort_keys=True)
    os.replace(tmp, ESTADO)


def ip_ignorada(ip):
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if a.is_loopback or a in ipaddress.ip_network("172.16.0.0/12") or a in ipaddress.ip_network("10.0.0.0/8"):
        return True
    return ip in IGNORAR_IPS


def mapa_appnames(api, slugs):
    """appName de cada servicio con router (compose/aplicaciones) → slug del proyecto."""
    m = {}
    for p in api.get("project.all"):
        if p["name"] not in slugs:
            continue
        for env in api.get("project.one", projectId=p["projectId"]).get("environments", []):
            for tipo in ("compose", "applications"):
                for s in env.get(tipo, []) or []:
                    if s.get("appName"):
                        m[s["appName"]] = p["name"]
    return m


def registrar(api, estado, slugs):
    """Lee el access log reciente de Traefik y anota la última petición real de cada proyecto."""
    appnames = sorted(mapa_appnames(api, slugs).items(), key=lambda kv: -len(kv[0]))
    r = subprocess.run(["docker", "logs", "--since", "25m", "dokploy-traefik"], capture_output=True, text=True)
    ultimos = {}
    for linea in (r.stdout + r.stderr).splitlines():
        m = LOG.match(linea)
        if not m:
            continue
        ip, fecha, _metodo, ruta, codigo, router = m.groups()
        if int(codigo) >= 400 or RUTAS_RUTINA.match(ruta) or ip_ignorada(ip):
            continue
        for appname, slug in appnames:
            if router.startswith(appname):
                t = datetime.strptime(fecha, "%d/%b/%Y:%H:%M:%S %z").astimezone(timezone.utc)
                if slug not in ultimos or t > ultimos[slug]:
                    ultimos[slug] = t
                break
    for slug, t in ultimos.items():
        previo = estado["proyectos"].get(slug, {}).get("ultimo_trafico")
        if not previo or t > parse(previo):
            estado["proyectos"].setdefault(slug, {})["ultimo_trafico"] = iso(t)
    return len(ultimos)


def ultima_actividad_proyectos(estado, slugs):
    despliegues = {n: parse(f) for n, f, in psql(
        'select p.name, max(d."createdAt") from deployment d '
        'left join compose c on c."composeId"=d."composeId" '
        'left join application a on a."applicationId"=d."applicationId" '
        'join environment e on e."environmentId"=coalesce(c."environmentId",a."environmentId") '
        'join project p on p."projectId"=e."projectId" group by 1')}
    base = parse(estado["vigilado_desde"])
    res = {}
    for slug in slugs:
        candidatos = [(base, "vigilado desde")]
        if slug in despliegues:
            candidatos.append((despliegues[slug], "despliegue"))
        t = estado["proyectos"].get(slug, {}).get("ultimo_trafico")
        if t:
            candidatos.append((parse(t), "tráfico"))
        res[slug] = max(candidatos)
    return res


def servicios(api, slug):
    """[(tipo, id, nombre, estado)] de todos los servicios del proyecto."""
    pid = next((p["projectId"] for p in api.get("project.all") if p["name"] == slug), None)
    if not pid:
        return []
    out = []
    for env in api.get("project.one", projectId=pid).get("environments", []):
        for tipo, clave in TIPOS.items():
            for s in env.get(tipo, []) or []:
                estado = s.get("composeStatus") or s.get("applicationStatus") or ""
                out.append((tipo, s[clave], s.get("name", ""), estado))
    return out


def accion(api, tipo, sid, verbo):
    ruta = RUTA.get(tipo, tipo)
    clave = TIPOS[tipo]
    api.post(f"{ruta}.{verbo}", {clave: sid})


def suspender(api, estado, slug, aplicar):
    sv = [s for s in servicios(api, slug) if s[3] != "idle"]
    if not aplicar:
        return len(sv)
    detenidos = []
    for tipo, sid, nombre, _ in sv:
        try:
            accion(api, tipo, sid, "stop")
            detenidos.append([tipo, sid])
        except ErrorApi as e:
            print(f"  aviso: no se pudo detener {nombre}: {e}", file=sys.stderr)
    estado["suspendidos"][slug] = {"desde": iso(ahora()), "servicios": detenidos}
    return len(detenidos)


def reactivar(api, estado, slug):
    s = estado["suspendidos"].pop(slug, None)
    if s is None:
        sys.exit(f"{slug} no figura como suspendido")
    for tipo, sid in s["servicios"]:
        try:
            accion(api, tipo, sid, "start")
        except ErrorApi as e:
            print(f"aviso: no se pudo arrancar {tipo} {sid}: {e}", file=sys.stderr)
    estado["proyectos"].setdefault(slug, {})["ultimo_trafico"] = iso(ahora())  # otro mes de plazo
    print(f"{slug}: {len(s['servicios'])} servicios arrancados; plazo de {DIAS_PROYECTO} días reiniciado")


def cuentas_inactivas():
    """Estudiantes (member) sin sesión en DIAS_CUENTA días: [(correo, ultimo_acceso, bloqueado)]."""
    filas = psql(
        'select u.email, coalesce(banned,false), '
        'greatest((select max(updated_at) from session s where s.user_id=u.id), u.created_at) '
        'from "user" u where exists (select 1 from member m where m.user_id=u.id and m.role=\'member\') '
        "and u.role <> 'admin'")
    limite = ahora().replace(tzinfo=None) - timedelta(days=DIAS_CUENTA)
    res = []
    for correo, bloq, ult in filas:
        t = datetime.fromisoformat(ult)
        if t < limite:
            res.append((correo, t, bloq in ("t", "true")))
    return res


def bloquear(correos):
    motivo = MOTIVO_BAN.format(DIAS_CUENTA)
    lista = ",".join("'" + c.replace("'", "''") + "'" for c in correos)
    psql(f"update \"user\" set banned=true, ban_reason='{motivo}', ban_expires=null where email in ({lista})")
    psql(f"delete from session where user_id in (select id from \"user\" where email in ({lista}))")


def desbloquear(correo):
    c = correo.replace("'", "''")
    filas = psql(f"update \"user\" set banned=false, ban_reason=null, ban_expires=null, updated_at=now() "
                 f"where email='{c}' and ban_reason like 'Inactividad%' returning email")
    print(f"{correo}: desbloqueado" if filas else f"{correo}: no estaba bloqueado por este script")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registrar", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--reactivar", metavar="SLUG")
    ap.add_argument("--desbloquear", metavar="CORREO")
    args = ap.parse_args()

    if args.desbloquear:
        return desbloquear(args.desbloquear.strip().lower())
    api = Dokploy()
    slugs = {e["slug"] for e in leer_csv("equipos.csv")}
    estado = cargar()
    try:
        if args.reactivar:
            reactivar(api, estado, args.reactivar)
        elif args.registrar:
            n = registrar(api, estado, slugs)
            print(f"{iso(ahora())} proyectos con tráfico en la ventana: {n}")
        else:
            informe(api, estado, slugs, args.aplicar)
    except ErrorApi as e:
        sys.exit(str(e))
    finally:
        guardar(estado)


def informe(api, estado, slugs, aplicar):
    modo = "APLICANDO" if aplicar else "EN SECO (usa --aplicar para ejecutar)"
    print(f"{iso(ahora())} · {modo} · proyecto {DIAS_PROYECTO} d · cuenta {DIAS_CUENTA} d · "
          f"vigilado desde {estado['vigilado_desde']}")
    limite = ahora() - timedelta(days=DIAS_PROYECTO)
    print("\nProyectos")
    for slug, (t, fuente) in sorted(ultima_actividad_proyectos(estado, slugs).items(), key=lambda kv: kv[1]):
        dias = (ahora() - t).days
        if slug in estado["suspendidos"]:
            # Un despliegue o tráfico posterior a la suspensión (p. ej. webhook) lo revive.
            if t > parse(estado["suspendidos"][slug]["desde"]) and aplicar:
                print(f"  {slug:<14} actividad tras suspender ({fuente}): se marca como activo")
                estado["suspendidos"].pop(slug)
            continue
        if t < limite:
            n = suspender(api, estado, slug, aplicar)
            print(f"  {slug:<14} sin uso {dias} d (último: {fuente}) → {'detenidos' if aplicar else 'se detendrían'} {n} servicios")
        elif dias >= DIAS_PROYECTO - 7:
            print(f"  {slug:<14} aviso: {dias} d sin uso ({fuente}); se suspende en {DIAS_PROYECTO - dias} d")
    print(f"  suspendidos ahora: {', '.join(sorted(estado['suspendidos'])) or 'ninguno'}")

    print("\nCuentas de estudiantes")
    pend = [(c, t) for c, t, b in cuentas_inactivas() if not b]
    for c, t in pend:
        print(f"  {c:<32} último acceso {t:%F} → {'bloqueada' if aplicar else 'se bloquearía'}")
    if pend and aplicar:
        bloquear([c for c, _ in pend])
    if not pend:
        print("  ninguna por bloquear")


if __name__ == "__main__":
    main()
