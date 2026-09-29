# CapstoneHUB en el servidor del laboratorio

Aplicación del docente (`github.com/ISCOUTB/CapstoneHUB`, Proyecto Ingeniería I UTB) desplegada como
ejemplo de referencia en el proyecto `capstonehub` de Dokploy.

| Pieza | Imagen / origen | Dominio |
|---|---|---|
| frontend (Next.js standalone) | contexto git `hub-frontend` | https://capstonehub.iscoutb.dev |
| backend (NestJS + Prisma; Swagger en `/api`, health en `/`) | contexto git `hub-backend` | https://api-capstonehub.iscoutb.dev |
| db | `postgres:15-alpine` | interno |
| storage (S3) | `ghcr.io/coollabsio/minio:RELEASE.2025-04-22T22-12-26Z` | interno |

Se despliega con `./scripts/12-desplegar-capstonehub.py` (idempotente). El código se construye desde
`main` (variable `CAPSTONE_REF` para fijar una rama, etiqueta o commit). No hay autodeploy: para publicar
cambios, *Deploy* en Dokploy o volver a ejecutar el script.

Los secretos se generaron al primer despliegue y viven solo en Dokploy → capstonehub → capstonehub →
Environment (`INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD` son el usuario administrador inicial).

## Adaptaciones frente al repositorio (y por qué)

1. **`compose.yml` de desarrollo → `compose.yaml` del laboratorio.** Se quitan `ports:` (5432, 3000, 3001,
   9000, 9001 publicados en el servidor), `container_name`, el bind mount `${DB_DATA_LOCATION}` y las
   rutas `env_file`; se agregan límites de CPU/memoria, healthchecks y volúmenes con nombre.
2. **`hub-backend/Dockerfile` no compila desde un clon limpio.** El cliente de Prisma se genera en
   `src/generated/prisma` (en `.gitignore`) y el Dockerfile ejecuta `npm run build` sin `prisma generate`:
   `nest build` falla con 87 errores TS2339 (`Property 'projectAttachment' does not exist…`). El compose
   lo define en línea con ese único paso añadido. **Arreglo propuesto para el repositorio:** en
   `hub-backend/Dockerfile`, antes de `RUN npm run build`, añadir `RUN npx prisma generate`.
3. **MinIO.** `quay.io/minio/minio` ya no se puede descargar (HTTP 401) y `github.com/minio/minio` está
   archivado. Se usa una compilación fija de la comunidad, solo en red interna. Es una versión de
   abril de 2025 sin más parches: para producción real conviene migrar a otro almacén compatible con S3
   (OCI Object Storage, Garage, RustFS) cambiando solo `S3_*`; el backend habla S3 estándar.
   El bucket se crea al arrancar (`mkdir /data/<bucket>`), por lo que no hace falta `minio-init`.
4. **CORS.** El backend no habilita CORS. Hoy el frontend es una página estática; si más adelante el
   navegador llama a `api-capstonehub…`, hay que agregar `app.enableCors({ origin: [...] })` en `main.ts`.
5. **`BACKEND_URL`** del frontend apunta a la red interna (`http://backend:3001`): sirve para llamadas
   desde el servidor de Next.js, no desde el navegador.
