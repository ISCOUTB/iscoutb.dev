#!/usr/bin/env bash
# Cierre de la instalación, una vez que el panel funciona por HTTPS en su dominio:
#   - deja de publicar el puerto 3000 (el panel solo queda accesible por Traefik);
#   - resuelve el panel a 127.0.0.1 desde el propio servidor, para que los scripts no dependan del NAT;
#   - instala las tareas cron de la plataforma.
#   sudo ./scripts/05-post-instalacion.sh
source "$(dirname "$0")/lib.sh"
requiere_root

code=$(curl -s -o /dev/null -m 15 --resolve "$PANEL_HOST:443:127.0.0.1" -w '%{http_code}' "https://$PANEL_HOST" || true)
[[ "$code" =~ ^(200|302|307)$ ]] || morir "https://$PANEL_HOST no responde con certificado válido (HTTP $code). Ejecuta antes 03-certificado-wildcard.sh y 04-configurar-dokploy.py."
ok "https://$PANEL_HOST responde (HTTP $code)"

if docker service inspect dokploy --format '{{json .Endpoint.Ports}}' | grep -q '"PublishedPort":3000'; then
  docker service update --quiet --publish-rm "published=3000,target=3000,mode=host" dokploy >/dev/null
  ok "puerto 3000 retirado del servicio dokploy"
else
  ok "el puerto 3000 ya no estaba publicado"
fi

if ! grep -qE "^127\.0\.0\.1\s+$PANEL_HOST\b" /etc/hosts; then
  echo "127.0.0.1 $PANEL_HOST" >> /etc/hosts
  ok "$PANEL_HOST → 127.0.0.1 en /etc/hosts (solo para este servidor)"
fi

usuario="${SUDO_USER:-ubuntu}"
mkdir -p "$RAIZ/reportes"
chown "$usuario:$usuario" "$RAIZ/reportes"
cat > /etc/cron.d/dokploy-plataforma <<CRON
# Plataforma Dokploy · Arquitecturas de Software (generado por 05-post-instalacion.sh)
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# Comparte con todo el equipo los servicios que crea cualquiera de sus integrantes.
*/5 * * * * $usuario $RAIZ/scripts/13-sincronizar-permisos.py --silencioso >> $RAIZ/reportes/sincronizacion.log 2>&1
# Auditoría de seguridad y límites, lunes 07:00.
0 7 * * 1 root $RAIZ/scripts/20-auditar-servicios.sh >> $RAIZ/reportes/auditoria.log 2>&1
CRON
chmod 644 /etc/cron.d/dokploy-plataforma
ok "cron instalado en /etc/cron.d/dokploy-plataforma"
