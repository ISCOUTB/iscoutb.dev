# Políticas de uso del servidor del laboratorio

El servidor del laboratorio es **compartido por los 23 equipos** del curso y es la alternativa
gratuita de despliegue (sin tarjeta). Lo que un equipo haga afecta a los demás. Al usarlo aceptas
estas reglas; su incumplimiento puede llevar a detener tus servicios sin aviso previo.

## Qué puedes desplegar

- El sistema de tu equipo: API, base de datos, frontend web, broker de mensajes y trabajos del proyecto.
- **Un proyecto por equipo**, con los entornos `production` y `development`.
- **Cuota por equipo:** como máximo **4 contenedores** y **512 MB de memoria sumando los límites**,
  con 0,5 CPU por contenedor como máximo.
- Brokers permitidos: RabbitMQ, NATS o Redis Streams. **Kafka no** (no cabe en la cuota).
- Las apps móviles (Flutter, Kotlin) no se despliegan aquí: apuntan a la URL pública de tu API.
  Flutter web se publica en GitHub Pages o equivalente, porque su imagen de compilación ocupa ~3 GB.

## Qué está prohibido

1. Montar `/var/run/docker.sock` o cualquier ruta del servidor (bind mounts). Usa volúmenes con nombre.
2. Contenedores `privileged`, `cap_add`, `network_mode: host` o `pid: host`.
3. Publicar puertos en el servidor (`ports:`). El tráfico público entra solo por el dominio de tu
   equipo (HTTPS); lo interno se comunica por la red del equipo con `expose`.
4. Desactivar **Isolated Deployment** en el servicio Compose.
5. Usar dominios fuera del espacio de tu equipo. Solo puedes usar `<equipo>.iscoutb.dev` y
   `<algo>-<equipo>.iscoutb.dev` (p. ej. `api-routb`, `dev-routb`). La auditoría detecta cualquier otro.
6. Minería, escaneos de red, envío masivo de correo, proxies abiertos o cualquier uso ajeno al curso.
7. Guardar secretos en el repositorio. Van en Dokploy → Environment.
8. Acceder, o intentar acceder, a servicios de otros equipos o a la plataforma.

## Qué hace la plataforma por su cuenta

- Una **auditoría semanal** revisa montajes, privilegios, puertos, límites y dominios de todos
  los servicios; el docente recibe el reporte.
- Limpieza diaria de imágenes y caché de compilación sin uso.
- Solo hay **2 compilaciones en paralelo**: en las horas previas a un cierre habrá cola.
  Despliega con tiempo.

## Datos y disponibilidad

- Es un entorno académico **sin garantía de disponibilidad**. No subas datos personales reales.
- Los volúmenes de tu equipo no tienen copia de seguridad garantizada. Si tu entrega depende de
  datos, versiona un script de siembra (*seed*) en el repositorio.
- **Cierre del semestre:** después del 30-nov-2026 se eliminan proyectos, volúmenes y cuentas.
