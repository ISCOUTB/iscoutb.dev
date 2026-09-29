# iscoutb.dev · Servidor del laboratorio de Arquitecturas de Software

Servidor compartido para que cada equipo despliegue su sistema **sin tarjeta de crédito** y lo muestre
con una **URL pública con HTTPS**. Es lo que piden la evidencia S8, el Corte 2 y el proyecto final:
URL accesible desde fuera de la universidad, infraestructura como código versionada, secretos fuera
del repositorio, *health check*, logs y una métrica consultable.

> Panel: **https://panel.iscoutb.dev** · Tu sistema: **https://&lt;tu-equipo&gt;.iscoutb.dev**
>
> Antes de empezar lee las [políticas de uso](docs/politicas-uso.md) (2 minutos).

## Contenido

1. [Qué recibes y qué necesitas](#1-qué-recibes-y-qué-necesitas)
2. [Tu equipo y tu dirección](#2-tu-equipo-y-tu-dirección)
3. [Paso a paso para publicar tu proyecto](#3-paso-a-paso-para-publicar-tu-proyecto)
4. [Operar y comprobar tu sistema](#4-operar-y-comprobar-tu-sistema)
5. [Evidencia para tus entregas](#5-evidencia-para-tus-entregas)
6. [Errores frecuentes](#6-errores-frecuentes)
7. [Plantillas incluidas](#7-plantillas-incluidas)

## 1. Qué recibes y qué necesitas

**Recibes** (el docente te los entrega en persona o por el aula; no hay envío por correo):

- un usuario en el panel: **tu correo institucional** `@utb.edu.co`;
- una **contraseña inicial** personal;
- un **proyecto** con el nombre de tu equipo, con los entornos `production` y `development`;
- cuota por equipo: **4 contenedores y 512 MB de memoria en total**, 0,5 CPU por contenedor.

**Necesitas**:

- tu repositorio en la organización `ISCOUTB` (`AS_202620_...`), **público**, con tu sistema;
- Docker en tu computador para probar antes de publicar (`docker compose`);
- que tu sistema se pueda describir con **Docker Compose** (una API, su base de datos y, si aplica,
  un frontend web y un broker de mensajes).

Las apps móviles (Flutter, Kotlin) **no se despliegan aquí**: tu app apunta a la URL pública de tu API.
Flutter *web* se publica en GitHub Pages: compilarlo en el servidor ocupa unos 3 GB.

## 2. Tu equipo y tu dirección

Cada equipo tiene un nombre corto (*slug*) que es también el nombre de su proyecto en el panel y de su
dirección. Puedes usar `<slug>.iscoutb.dev` y cualquier `<algo>-<slug>.iscoutb.dev`
(p. ej. `api-routb.iscoutb.dev`, `dev-routb.iscoutb.dev`). No hace falta pedir DNS ni certificados: hay
un certificado `*.iscoutb.dev` para todos. Los subdominios de dos niveles (`dev.routb.iscoutb.dev`) **no**
funcionan.

| Slug | Equipo | Repositorio | Rama | Dirección principal |
|---|---|---|---|---|
| `audioshare` | AudioShare | `AS_202620_AudioShare` | `master` | https://audioshare.iscoutb.dev |
| `clubsutb` | Clubs UTB | `AS_202620_Clubs_UTB` | `master` | https://clubsutb.iscoutb.dev |
| `dinamikutb` | DinamikUTB | `AS_202620_DinamikUTB` | `master` | https://dinamikutb.iscoutb.dev |
| `drift` | Drift | `AS_202620_Drift` | `master` | https://drift.iscoutb.dev |
| `elmapita` | ElMapita | `AS_202620_ElMapita` | `main` | https://elmapita.iscoutb.dev |
| `enagenda` | EnAgenda | `AS_202620_EnAgenda` | `master` | https://enagenda.iscoutb.dev |
| `gimnasioutb` | GimnasioUTB | `AS_202620_GimnasioUTB` | `main` | https://gimnasioutb.iscoutb.dev |
| `inventrack` | InvenTrack | `AS_202620_InvenTrack` | `main` | https://inventrack.iscoutb.dev |
| `laplacita` | LaPlacita | `AS_202620_LaPlacita` | `master` | https://laplacita.iscoutb.dev |
| `lostvault` | LostVault | `AS_202620_LostVault` | `main` | https://lostvault.iscoutb.dev |
| `mapsutb` | mapsutb | `AS_202620_mapsutb` | `master` | https://mapsutb.iscoutb.dev |
| `pideutb` | PideUtb | `AS_202620_PideUtb` | `master` | https://pideutb.iscoutb.dev |
| `campusmarket` | CampusMarket | `AS_202620_PROYECTO_CAMPUSMARKET` | `master` | https://campusmarket.iscoutb.dev |
| `recobra` | Recobra | `AS_202620_Recobra` | `master` | https://recobra.iscoutb.dev |
| `routb` | ROUTB | `AS_202620_ROUTB` | `master` | https://routb.iscoutb.dev |
| `shareu` | ShareU | `AS_202620_ShareU` | `master` | https://shareu.iscoutb.dev |
| `calificacion` | Calificación automática | `AS_202620_Sistema-de-calificacion-automatica` | `master` | https://calificacion.iscoutb.dev |
| `taia` | TAIA | `AS_202620_TAIA_-Task-Artificial-Intelligence-Assistant` | `main` | https://taia.iscoutb.dev |
| `tiendautb` | Tienda virtual UTB | `AS_202620_TIENDA-VIRTUAL-UTB` | `main` | https://tiendautb.iscoutb.dev |
| `tractar` | TRACTAR | `AS_202620_TRACTAR` | `main` | https://tractar.iscoutb.dev |
| `uniteam` | uniTeam | `AS_202620_uniTeam` | `master` | https://uniteam.iscoutb.dev |
| `xald` | XALD | `AS_202620_XALD` | `master` | https://xald.iscoutb.dev |
| `verifacts` | Verifacts | `AS_202620_Verifacts` | `master` | https://verifacts.iscoutb.dev |

## 3. Paso a paso para publicar tu proyecto

### 3.1 Entra y protege tu cuenta

1. Abre **https://panel.iscoutb.dev** y entra con tu correo institucional y la contraseña inicial.
2. **Cambia la contraseña ya**: *Settings → Profile → Password*. La inicial la conoce el docente.
3. Recomendado: activa la verificación en dos pasos en la misma pantalla.

Solo verás el proyecto de tu equipo. Si no lo ves, avisa al docente.

### 3.2 Describe tu entorno en `deploy/compose.lab.yaml`

En **tu repositorio** crea `deploy/compose.lab.yaml`. Parte de
[`plantillas/compose.lab.yaml`](plantillas/compose.lab.yaml) (Postgres) o
[`plantillas/compose.lab.mysql.yaml`](plantillas/compose.lab.mysql.yaml) (MySQL) y ajusta:

- `build.context` es **relativo a la carpeta `deploy/`**: si tu API está en `backend/`, escribe `../backend`.
- Cada servicio lleva su límite en `deploy.resources.limits`. La suma del equipo no puede pasar de **512 MB**.
- **Sin** `ports:` (usa `expose:`), **sin** `container_name`, **sin** bind mounts, **sin** `privileged`, **sin**
  `/var/run/docker.sock` y **sin** redes externas. Los datos van en **volúmenes con nombre**.
- Los valores sensibles se escriben como `${NOMBRE}`: el valor real va en el panel (paso 3.5), **nunca**
  en el repositorio.

Este archivo **es tu evidencia de infraestructura como código**: versiónalo y hazle *commit*.

### 3.3 Un Dockerfile por pieza y un `/health`

- Parte de las plantillas: [FastAPI](plantillas/Dockerfile.fastapi), [Node](plantillas/Dockerfile.node),
  [Next.js](plantillas/Dockerfile.next) y [Vite + nginx](plantillas/Dockerfile.vite-nginx). Son de varias
  etapas con imágenes `slim` o `alpine`: compilan más rápido y ocupan menos disco compartido.
- Tu API debe exponer `GET /health` (o `/api/health`) que responda `200` solo si puede atender, incluida su
  base de datos. La plantilla lo usa en su `healthcheck`, y el revisor lo consulta con `curl`.
- Escribe logs en **JSON** a la salida estándar (stdout).

### 3.4 Prueba en tu computador, igual que lo ejecutará el servidor

```bash
cp deploy/.env.example deploy/.env      # valores de prueba; deploy/.env va en .gitignore
docker compose --env-file deploy/.env -f deploy/compose.lab.yaml up --build
curl -s http://localhost:8000/health      # ajusta el puerto con un "ports:" SOLO en tu copia local
```

Haz *commit* y *push* de `deploy/compose.lab.yaml` y de los Dockerfile a la rama de la tabla del apartado 2.

### 3.5 Tu servicio ya está creado: configúralo

Cada equipo tiene ya en su proyecto, entorno **production**, un servicio Compose llamado **`sistema`**, conectado
a tu repositorio y a la rama de la tabla del apartado 2, leyendo `./deploy/compose.lab.yaml`, con
**Isolated Deployment** y **despliegue automático** activados. Solo falta configurarlo:

1. En el panel abre tu proyecto → **production** → **sistema**. (Si no lo ves, espera 5 minutos o avisa al docente.)
2. Pestaña **General → Provider**: comprueba que aparezcan `ISCOUTB`, tu repositorio, tu rama y
   `./deploy/compose.lab.yaml` como *Compose Path*. Si tu compose está en otra ruta, cámbiala y **Save**.
3. Pestaña **Environment**: escribe una variable por línea (`POSTGRES_PASSWORD=...`, claves de APIs externas,
   etc.) y guarda. Dokploy genera `deploy/.env` en el servidor al desplegar. Esta pantalla más la referencia
   `${VARIABLE}` de tu compose demuestran la **protección de secretos**. Usa valores largos y aleatorios;
   evita `$` y comillas en las contraseñas.
4. Pestaña **Domains → Add Domain**, una vez por cada pieza pública:

   | Campo | Frontend | API |
   |---|---|---|
   | Service Name | el servicio web de tu compose (`web`) | el de tu API (`api`) |
   | Host | `<slug>.iscoutb.dev` | `<slug>.iscoutb.dev` (o `api-<slug>.iscoutb.dev`) |
   | Path | `/` | `/api` (o `/` si usas `api-<slug>`) |
   | Strip Path | no | sí, si tu API no incluye `/api` en sus rutas |
   | Container Port | 80 (nginx) o 3000 (Next.js) | el de tu API (8000, 3001…) |
   | HTTPS | activado | activado |
   | Certificate Provider | **Let's Encrypt** | **Let's Encrypt** |

   Si no tienes frontend, publica la API directamente en `/`. Con FastAPI bajo `/api` y Strip Path arranca
   uvicorn con `--root-path /api` para que `/api/docs` funcione. Separar por ruta (`/api`) o por nombre
   (`api-<slug>`) son decisiones válidas: justifícala en un ADR (CORS, cookies, versionado).
5. Pulsa **Deploy** (pestaña **General**). Sigue el avance en **Deployments**; la primera compilación tarda varios
   minutos. Los cambios de dominio en un Compose se aplican **al volver a desplegar**.

> **Ojo con el despliegue automático:** desde ahora cada *push* a tu rama dispara un despliegue. Mientras tu
> repositorio no tenga `deploy/compose.lab.yaml`, ese despliegue **falla en segundos**: es normal y no daña nada.
> Cuando lo tenga, cada *push* reconstruye tu sistema. Si prefieres controlar cuándo se despliega, apaga
> **Autodeploy** en **General**. Recuerda que solo hay 2 compilaciones simultáneas para todos los equipos.
>
> **Si tu servicio no existe** (o lo borraste por error), créalo: proyecto → **production** →
> **Create Service → Compose**; nombre `sistema`; *Provider* **GitHub** (o **Git** con
> `https://github.com/ISCOUTB/<repositorio>.git`), rama, *Compose Path* `./deploy/compose.lab.yaml`; y activa
> **Enable Isolated Deployment** en **Advanced** (aparece como *Deprecated*, pero es obligatoria).

### 3.6 Desplegar solo lo que pasó el CI (opcional)

Con el despliegue automático, todo *push* a la rama del servicio se publica. Para que **solo se publique lo que ya
pasó tus pruebas**, separa las ramas:

1. Crea una rama de publicación (por ejemplo `produccion`) en tu repositorio y protégela en GitHub
   (*Settings → Branches*): que solo reciba *pull requests* con el CI en verde.
2. En el panel, servicio **sistema → General → Provider**, cambia **Branch** a `produccion` y guarda.
3. Trabaja en `main`/`master` como siempre; cuando el CI pase, fusiona a `produccion`: ese *merge* es el que despliega.

Así, además, tienes un historial claro de **qué versión está publicada** y **cómo volver atrás** (revertir el
*merge*), lo que sirve como evidencia de tu procedimiento de reversión.

### Bases de datos

- La base de datos es **un servicio más de tu compose** (`db`), con un volumen con nombre y **sin** `ports:`. No se
  puede entrar a ella desde Internet, y en el panel no tienes terminal del servidor: tu API se conecta usando el
  nombre del servicio como host (`db`, puerto 5432 o 3306).
- Las migraciones se ejecutan **al arrancar tu API** (Prisma `migrate deploy`, Alembic `upgrade head`, Flyway…),
  no a mano. Así un despliegue limpio siempre deja la base lista.
- Para revisar datos, ejecuta el mismo compose en tu computador (`docker compose exec db psql ...`) o expón
  consultas de solo lectura en tu API.
- **No hay copia de seguridad garantizada** de tus volúmenes: versiona un *script de siembra* (*seed*) para
  recrear los datos de la demostración.
- Usa `postgres:15-alpine` o `16-alpine` y `mysql:8.4`, con los parámetros de memoria de las plantillas.
  Servicios externos (Supabase, Firebase) también funcionan: el servidor tiene salida a Internet.

### Tareas frecuentes

| Quiero… | Cómo |
|---|---|
| Publicar un cambio | *push* a la rama (se despliega solo) o **Deploy** |
| Cambiar una variable | pestaña **Environment** → guardar → **Deploy** (las variables se leen al desplegar) |
| Ver por qué falló | **Deployments** → el último despliegue → registro completo |
| Ver qué hace mi sistema | **Logs** (por contenedor) y **Monitoring** |
| Reconstruir sin cambios de código | **Rebuild** |
| Volver a una versión anterior | `git revert` + *push*, y **Deploy** |
| Agregar un segundo dominio | **Domains → Add Domain** con `<algo>-<slug>.iscoutb.dev` y volver a desplegar |
| Probar algo sin tocar producción | crea el servicio en el entorno **development** con `dev-<slug>.iscoutb.dev` |

## 5. Evidencia para tus entregas

| Lo que piden las fichas | Dónde lo tienes |
|---|---|
| URL del sistema accesible desde fuera | `https://<slug>.iscoutb.dev` |
| Infraestructura como código versionada | `deploy/compose.lab.yaml` y los Dockerfile en tu repositorio |
| Health check consultable | `GET /health` de tu API |
| Logs estructurados | JSON a stdout, visibles en **Logs** |
| Métrica ligada al escenario | ruta de métricas de tu API |
| Protección de secretos | `${VARIABLE}` en el compose + pestaña **Environment** (sin valores en el repositorio) |
| Estimación de costo mensual | ver abajo |

**Datos para tu estimación de costo:** el servidor es una VM de Oracle Cloud `VM.Standard.E5.Flex` con
1 OCPU (2 vCPU), 12 GB de RAM y 45 GB de disco, en la región Phoenix, **compartida entre 23 equipos**. Tu
equipo usa como máximo 0,5 CPU por contenedor y 512 MB. Estima con la lista de precios pública de Oracle
Cloud (por OCPU-hora, por GB de RAM-hora y por GB de disco al mes) y declara tus supuestos: fracción
asignada a tu equipo, horas al mes y en qué punto dejarías de caber en la capa gratuita.

### Lista de comprobación antes de entregar

- [ ] `deploy/compose.lab.yaml` y los Dockerfile están en la **rama que se califica** y funcionan con `docker compose up --build` en limpio.
- [ ] `https://<slug>.iscoutb.dev` abre **desde fuera de la universidad** y con candado válido.
- [ ] `GET /health` responde `200` y falla (no `200`) si la base de datos no está disponible.
- [ ] No hay contraseñas, claves ni tokens en el repositorio ni en su historial (`git log -S` y `git grep`).
- [ ] Los logs salen en JSON y tu métrica es consultable por URL.
- [ ] La última compilación terminó en **Done** y no depende de un archivo que solo existe en tu computador.
- [ ] Desplegaste con al menos 24 horas de margen antes del cierre.

## 6. Errores frecuentes

| Síntoma | Causa probable y solución |
|---|---|
| `404 page not found` | El dominio no está asignado al servicio, el **Service Name** no es el de tu compose, o falta volver a desplegar. |
| `502 Bad Gateway` | **Container Port** equivocado, o tu app escucha en `127.0.0.1`: debe escuchar en `0.0.0.0`. |
| Certificado inválido | Dominio fuera de `*.iscoutb.dev`, de dos niveles, o con HTTPS desactivado. |
| El build termina con `Killed` / código 137 | Se acabó la memoria compilando: usa imágenes `slim`, reduce dependencias, no compiles Flutter aquí. |
| Despliegue en cola | Hay 2 compilaciones simultáneas en todo el servidor: espera tu turno. |
| `service "x" refers to undefined network` | Quita las redes externas del compose; **Isolated Deployment** crea la red del equipo. |
| Los datos desaparecieron | Usaste bind mount o volumen anónimo: declara un **volumen con nombre**. |
| `bind: address already in use` / puerto publicado | Quita `ports:` del compose: usa `expose:` y un dominio. |
| **NestJS/Prisma:** `nest build` falla con errores TS2339 (`Property 'x' does not exist on type 'PrismaService'`) | El cliente de Prisma no está generado: agrega `RUN npx prisma generate` antes de `npm run build` en tu Dockerfile (con `npm ci --ignore-scripts` no se genera solo). |
| **Next.js:** la app no encuentra la API | Las variables `NEXT_PUBLIC_*` se fijan al **compilar**: pásalas como `build args`. Las de servidor sí pueden ir en **Environment**. |
| **CORS:** el navegador bloquea las llamadas a `api-<slug>` | Habilita CORS en tu API para `https://<slug>.iscoutb.dev`, o publica todo bajo un solo host con `/api`. |
| **MinIO:** `unauthorized` al descargar `quay.io/minio/minio` | MinIO dejó de publicar esas imágenes y el proyecto está archivado. Para archivos usa otro almacén compatible con S3 (Garage, RustFS) o el almacenamiento de un proveedor; tu código no cambia, solo las variables `S3_*`. Ejemplo de referencia: [`plataforma/capstonehub/`](plataforma/capstonehub/). |
| **Kafka** | No cabe en 512 MB y no está permitido. Usa RabbitMQ, NATS o Redis Streams. |

Si algo no se resuelve con esta tabla, pregunta al docente con el **mensaje de error completo** y la
pestaña **Deployments** abierta: es lo primero que se revisa.

## 7. Plantillas incluidas

| Archivo | Para qué |
|---|---|
| [`plantillas/compose.lab.yaml`](plantillas/compose.lab.yaml) | API + Postgres con límites, `healthcheck` y volumen con nombre; incluye ejemplos comentados de frontend y broker |
| [`plantillas/compose.lab.mysql.yaml`](plantillas/compose.lab.mysql.yaml) | Variante con MySQL 8.4 ajustada a 256 MB |
| [`plantillas/Dockerfile.fastapi`](plantillas/Dockerfile.fastapi) | FastAPI en dos etapas, usuario sin privilegios |
| [`plantillas/Dockerfile.node`](plantillas/Dockerfile.node) | API Node.js |
| [`plantillas/Dockerfile.next`](plantillas/Dockerfile.next) | Next.js en modo *standalone* |
| [`plantillas/Dockerfile.vite-nginx`](plantillas/Dockerfile.vite-nginx) + [`nginx-spa.conf`](plantillas/nginx-spa.conf) | SPA (Vite/React/Vue) servida con nginx |
| [`plataforma/capstonehub/`](plataforma/capstonehub/) | Ejemplo real: un sistema con backend, frontend, Postgres y almacenamiento S3 adaptado a este servidor |

---

**Para el docente:** cómo está montada la plataforma, cómo se opera y cómo se aprovisionan los equipos está en
[`docs/plataforma.md`](docs/plataforma.md) y [`docs/runbook-docente.md`](docs/runbook-docente.md).
