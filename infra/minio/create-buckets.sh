#!/bin/sh
# Crée les buckets applicatifs au démarrage (idempotent). Exécuté par le
# conteneur minio/mc à usage unique dans docker-compose (service createbuckets).
set -eu

for i in $(seq 1 30); do
    if mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" 2>/dev/null; then
        break
    fi
    echo "En attente de MinIO... ($i/30)"
    sleep 2
done

mc mb --ignore-existing "local/${MINIO_BUCKET_ARTIFACTS}"
mc mb --ignore-existing "local/${MINIO_BUCKET_LANGFUSE}"

echo "Buckets prêts: ${MINIO_BUCKET_ARTIFACTS}, ${MINIO_BUCKET_LANGFUSE}"
