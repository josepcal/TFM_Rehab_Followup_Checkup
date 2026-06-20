# FTM Recording Database — MinIO local

Stack local de object storage compatible con S3 para las grabaciones WAV del MVP.
El bucket queda privado; la app deberá usar signed URLs para subir/leer objetos.

## Arranque

```bash
cd bbdd_dev_setup/ftm-recording-database
./up.sh
```

El script crea `.env` desde `.env.example` si no existe, levanta MinIO y verifica
que el bucket privado quede creado.

Consola MinIO:

```txt
http://localhost:9001
```

Credenciales por defecto local:

```txt
minioadmin / minioadmin123
```

## Bucket

El servicio `minio-init` crea automáticamente:

```txt
ftm-recordings
```

y deja el acceso anónimo desactivado.

## Variables recomendadas para la API

```env
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin123
S3_BUCKET=ftm-recordings
S3_REGION=eu-local-1
S3_FORCE_PATH_STYLE=true
```

## Comandos útiles

```bash
# Ver estado
docker compose ps

# Logs
docker compose logs -f minio

# Parar conservando datos
docker compose stop

# Borrar contenedores y volumen local
docker compose down -v
```

> Nota: este stack es solo local/dev. En cloud usar bucket gestionado S3/GCS o MinIO
> con credenciales fuera del repo y TLS detrás del reverse proxy.
