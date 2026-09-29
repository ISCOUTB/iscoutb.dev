# Runbook del docente · servidor del laboratorio (Dokploy)

## Componentes

| Pieza | Dónde | Notas |
|---|---|---|
| VM | OCI `VM.Standard.E5.Flex` Phoenix, 2 vCPU, 12 GB + 4 GB swap, 45 GB | Ubuntu 26.04 |
| Docker | 29.8.1, retenido con `apt-mark hold` | Swarm de un nodo, logs rotados (10 MB × 3) |
| Dokploy | servicio Swarm `dokploy`, imagen `dokploy/dokploy:v0.30.7` | datos en el volumen `dokploy` y en `/etc/dokploy` |
| BD de Dokploy | servicio `dokploy-postgres` (postgres:16) | contraseña en el secreto Docker `dokploy_postgres_password` |
| Proxy | contenedor `dokploy-traefik` (traefik v3.6.25) | wildcard `*.iscoutb.dev` por DNS-01; `acme.json` en `/etc/dokploy/traefik/dynamic/` |
| DNS | Cloudflare, zona `iscoutb.dev` | un solo registro `*.iscoutb.dev` A hacia la IP pública de la VM, *DNS only* |
| Cron | `/etc/cron.d/dokploy-plataforma` | permisos cada 5 min; auditoría (contenedores y dominios) los lunes 07:00 |

Perímetro: el Security List de OCI solo abre 22, 80 y 443. Los puertos que publica Docker saltan
el `INPUT` de iptables, así que **no abras otros puertos en OCI**: es la única barrera.

## Puesta en marcha (orden)

| Paso | Comando o acción | Estado al 29-sep-2026 |
|---|---|---|
| 1 | `sudo ./scripts/01-preparar-host.sh` | hecho |
| 2 | `sudo ./scripts/02-instalar-dokploy.sh` | hecho |
| 3 | Crear la cuenta owner (VS Code → Ports → Forward 3000) | hecho |
| 4 | Token de Cloudflare y `ACME_EMAIL` en `.env` (sección siguiente) | hecho |
| 5 | `./scripts/11-dns-cloudflare.sh` (wildcard `*.iscoutb.dev`) | hecho |
| 6 | `sudo ./scripts/03-certificado-wildcard.sh` | hecho (vence 27-dic-2026, renovación automática) |
| 7 | Settings → Profile → API/CLI → Generate (**sin límite de peticiones**, sin vencimiento); pegar en `.env` como `DOKPLOY_API_KEY` | hecho |
| 8 | GitHub App (más abajo). Opcional: sin ella los equipos usan el origen *Git* con su repositorio público | pendiente |
| 9 | `./scripts/04-configurar-dokploy.py --email-acme <correo>` | hecho (falta compartir GitHub tras el paso 8) |
| 10 | `sudo ./scripts/05-post-instalacion.sh` (cierra el 3000, instala el cron) | hecho |
| 11 | Correos de Moodle en `equipos/integrantes.csv` | hecho |
| 12 | `./scripts/10-aprovisionar-equipos.py --cuentas` (proyectos y cuentas); `--compose` solo con la GitHub App | hecho (86 cuentas, 23 proyectos) |
| 13 | Entregar a cada estudiante su fila de `equipos/credenciales.csv` (privado, sin servidor de correo) | pendiente |

Tras el paso 10 el panel **solo** es accesible en https://panel.iscoutb.dev.

> **Clave de API:** debe crearse con el límite de peticiones desactivado. La que trae el panel por defecto
> (10 peticiones cada 15 min) bloquea todo con 401 al agotarse (`Rate limit exceeded` en `docker service logs dokploy`).

### Token de Cloudflare

Cloudflare → *My Profile → API Tokens → Create Token → Edit zone DNS* (sirve también un token de
cuenta, *Manage Account → Account API Tokens*; ese tipo responde 401 en `/user/tokens/verify`, por eso
los scripts lo validan consultando la zona). Permisos
**Zone · DNS · Edit** y **Zone · Zone · Read**, recurso **Include · Specific zone · iscoutb.dev**.
Pégalo en `.env` como `CLOUDFLARE_API_TOKEN` (nunca en el chat ni en git). Traefik lo usa para
crear los registros TXT `_acme-challenge` al emitir y renovar el wildcard (cada ~60 días, solo).

El registro wildcard va en *DNS only* (nube gris). Con proxy de Cloudflare el tráfico de los equipos
pasaría por su CDN (caché, límite de 100 s por petición, latencia distinta a la del servidor), y
las mediciones de los escenarios dejarían de reflejar el servidor.

**Rotar el token:** crea uno nuevo, actualiza `.env`, ejecuta `sudo ./scripts/03-certificado-wildcard.sh`
(recrea Traefik y lo reconecta a las redes de los equipos) y revoca el anterior en Cloudflare.

### GitHub App en la organización ISCOUTB

1. Dokploy → *Settings → Git → GitHub → Create GitHub App*. Marca **Organization** y escribe `ISCOUTB`.
2. GitHub crea la app y pide instalarla: elige **Only select repositories** y marca los
   repositorios `AS_202620_*`. Se requiere ser owner de la organización.
3. De vuelta en Dokploy el proveedor aparece como configurado. Vuelve a ejecutar
   `04-configurar-dokploy.py` para compartirlo con la organización.
4. En la app de GitHub, deja desactivados los *pull request previews*: cada PR levantaría otra
   copia del sistema en el servidor.

## Aplicaciones de la plataforma

| App | Proyecto Dokploy | URL | Cómo se despliega |
|---|---|---|---|
| CapstoneHUB (docente) | `capstonehub` | https://capstonehub.iscoutb.dev (web), https://api-capstonehub.iscoutb.dev (API, Swagger en `/api`) | `./scripts/12-desplegar-capstonehub.py`; detalles y adaptaciones en `plataforma/capstonehub/README.md` |

Las credenciales del administrador inicial de CapstoneHUB están en Dokploy → capstonehub → capstonehub →
*Environment* (`INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`). No hay autodeploy: para publicar cambios del
repositorio, *Deploy* en Dokploy o volver a ejecutar el script.

## Operación semanal

```bash
sudo ./scripts/21-estado-capacidad.sh      # RAM/CPU por equipo y disco
sudo ./scripts/20-auditar-servicios.sh     # hallazgos de seguridad (también por cron, lunes)
./scripts/22-verificar-despliegues.sh      # URL y health de cada equipo, formato de las fichas
tail reportes/sincronizacion.log           # cambios de permisos
```

- Hallazgo de auditoría: pide la corrección al equipo; si es grave (docker.sock, privileged),
  detén el servicio en el panel (*Stop*) de inmediato.
- Un equipo por encima de 512 MB: revisa los límites de su compose.

## Altas, bajas y cambios

- **Cambió `EQUIPOS.md`:** `./scripts/09-generar-equipos.py` (conserva los correos ya escritos),
  completa los correos nuevos y ejecuta `./scripts/10-aprovisionar-equipos.py --compose --cuentas`.
- **Estudiante que se retira:** *Settings → Users → Remove*, y bórralo de `integrantes.csv`.
- **Cambio de equipo:** cambia su `slug` en `integrantes.csv`; el cron ajusta los permisos en 5 min.
- **Contraseña olvidada:** *Settings → Users*, o crea una nueva cuenta tras eliminar la anterior.
- **Dominios:** no requieren trámite. Cada equipo usa `<slug>.iscoutb.dev` o `<algo>-<slug>.iscoutb.dev`;
  la auditoría reporta nombres ajenos, reservados (`panel`, `estado`, `certificado`…) o duplicados.

## Capacidad y escalado

Umbrales: disco > 75 %, o RAM disponible < 1,5 GB sostenida (`free -h`), o swap en uso continuo.

- **Disco:** OCI → Boot Volume → *Edit* → nuevo tamaño (en caliente, sin reinicio). Luego en la VM:
  `sudo growpart /dev/sda 1 && sudo resize2fs /dev/sda1`.
- **RAM/CPU:** OCI → Instance → *Edit shape* (1 → 2 OCPU, 12 → 24 GB). **Requiere reinicio**:
  hazlo fuera de semanas de entrega. La semana 12 (brokers) es el punto de riesgo.
- **Alivio inmediato:** `docker builder prune -af` y `docker image prune -af` liberan caché de builds.

## Copias de seguridad

- **Boot volume (recomendado):** OCI → Boot Volume → *Backup policy* (bronze: mensual/semanal).
- **Dokploy a Object Storage:** crea un bucket y una *Customer Secret Key* (OCI → Profile). En
  Dokploy → *Settings → S3 Destinations*: endpoint
  `https://<namespace>.compat.objectstorage.us-phoenix-1.oraclecloud.com`, región
  `us-phoenix-1`. Luego programa el backup de la base de Dokploy (*Settings → Web Server → Backups*).
- **Manual, antes de cambios grandes:**
  `sudo docker exec $(sudo docker ps -qf name=dokploy-postgres) pg_dump -U dokploy dokploy | gzip > dokploy-$(date +%F).sql.gz`

## Incidentes

| Síntoma | Acción |
|---|---|
| El panel no carga | `sudo docker service ps dokploy` y `sudo docker service logs --tail 100 dokploy`; reiniciar con `sudo docker service update --force dokploy` |
| Ningún dominio responde | `sudo docker logs --tail 100 dokploy-traefik`; `sudo docker restart dokploy-traefik` |
| Despliegues atascados en cola | Panel → *Settings → Server → Clean all deployment queue* (o `settings.cleanAllDeploymentQueue`) |
| Disco lleno | `sudo docker system df`; `sudo docker builder prune -af`; luego ampliar el volumen |
| Tras recrear Traefik, un equipo sin red | Volver a desplegar su servicio (reconecta Traefik a la red aislada) |
| Certificado inválido en un dominio | ¿Está bajo `*.iscoutb.dev` y es de un solo nivel? Si el wildcard venció o falló: `sudo docker logs dokploy-traefik 2>&1 \| grep -i acme` y verificar el token |

## Actualizaciones

- Ubuntu: `unattended-upgrades` aplica parches de seguridad. Docker está retenido a propósito.
- **Dokploy solo entre semestres:** backup manual, luego
  `sudo docker service update --image dokploy/dokploy:<version> dokploy`, y actualiza
  `DOKPLOY_VERSION` en `.env`. No uses el botón *Update* del panel durante el semestre.

## Cierre del semestre (después del 30-nov-2026)

1. Si hace falta evidencia, exporta la tabla de `22-verificar-despliegues.sh` antes de borrar.
2. Borra los proyectos de los equipos (con sus volúmenes) y las cuentas de estudiantes.
3. `sudo docker system prune -af --volumes`.
4. Para el siguiente periodo: actualiza `REPO_PREFIX` en `.env` y el nombre de la organización en
   `04-configurar-dokploy.py`, regenera los equipos y vuelve a aprovisionar.
