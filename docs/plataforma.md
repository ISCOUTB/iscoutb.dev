# La plataforma por dentro (para el docente)

Guía para estudiantes: [README](../README.md).

Plataforma autoalojada donde los equipos del curso despliegan sus sistemas desde GitHub, con
URL pública HTTPS, infraestructura como código y secretos fuera del repositorio. Es la
alternativa sin tarjeta que el curso promete en el taller de despliegue.

```
Internet ─► Cloudflare DNS (*.iscoutb.dev, DNS only) ─► OCI Security List (22, 80, 443) ─► VM Ubuntu 26.04 · Docker 29 · Swarm 1 nodo
             ├─ Traefik v3.6 + certificado wildcard *.iscoutb.dev (Let's Encrypt, DNS-01 Cloudflare)
             │    ├─ panel.iscoutb.dev                → Dokploy v0.30.7
             │    └─ <equipo>.iscoutb.dev, <x>-<equipo> → sistema del equipo (/ web, /api API)
             └─ un proyecto por equipo → Compose desde deploy/compose.lab.yaml del repositorio
                (red aislada, límites de CPU/RAM, autodeploy por GitHub App)
```

## Contenido

| Ruta | Para qué |
|---|---|
| `scripts/00-preflight.sh` | Estado del servidor, puertos, DNS y salida a Internet (solo lectura) |
| `scripts/01-preparar-host.sh` | Zona horaria, swap, firewall, Docker 29 retenido |
| `scripts/02-instalar-dokploy.sh` | Instalador oficial revisado (sha256) con versión fijada |
| `scripts/03-certificado-wildcard.sh` | Traefik con DNS-01 en Cloudflare y certificado `*.iscoutb.dev` |
| `scripts/04-configurar-dokploy.py` | Organización, concurrencia, limpieza, GitHub compartido, dominio del panel |
| `scripts/05-post-instalacion.sh` | Cierra el puerto 3000 e instala el cron |
| `scripts/09-generar-equipos.py` | `EQUIPOS.md` + GitHub → `equipos/equipos.csv` e `integrantes.csv` |
| `scripts/10-aprovisionar-equipos.py` | Proyectos, entornos, servicio Compose y cuentas por equipo |
| `scripts/11-dns-cloudflare.sh` | Registro wildcard `*.iscoutb.dev` en Cloudflare |
| `scripts/12-desplegar-capstonehub.py` | Despliega CapstoneHUB (app del docente) en su propio proyecto; ver `plataforma/capstonehub/` |
| `scripts/13-sincronizar-permisos.py` | Comparte con todo el equipo los servicios de su proyecto (cron) |
| `scripts/20-auditar-servicios.sh` | docker.sock, bind mounts, privileged, puertos, límites y dominios ajenos (cron) |
| `scripts/21-estado-capacidad.sh` | Consumo por equipo y disco |
| `scripts/22-verificar-despliegues.sh` | URL y health de cada equipo con el formato de las fichas |
| `plataforma/capstonehub/` | Compose adaptado de CapstoneHUB y notas de las adaptaciones |
| `plantillas/` | `compose.lab.yaml` (Postgres/MySQL) y Dockerfiles para los equipos |
| `README.md` | Guía paso a paso para los equipos |
| `docs/politicas-uso.md` | Cuotas y prohibiciones |
| `docs/runbook-docente.md` | Puesta en marcha, operación, escalado, backups, incidentes, cierre |

Archivos privados, fuera de git: `.env` (API keys y token de Cloudflare), `equipos/integrantes.csv` (correos) y
`equipos/credenciales.csv` (contraseñas iniciales).

La puesta en marcha y su estado están en [docs/runbook-docente.md](runbook-docente.md#puesta-en-marcha-orden).
