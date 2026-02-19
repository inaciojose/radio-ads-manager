#!/usr/bin/env bash
set -euo pipefail

# Backup lógico do PostgreSQL de produção em container Docker.
# Uso:
#   ./scripts/backup_postgres.sh /opt/radio-ads/backend /opt/radio-ads/backups

BACKEND_DIR="${1:-$(pwd)}"
BACKUP_DIR="${2:-${BACKEND_DIR}/backups}"
ENV_FILE="${BACKEND_DIR}/.env.prod"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERRO: .env.prod não encontrado em ${BACKEND_DIR}"
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

: "${POSTGRES_USER:?POSTGRES_USER ausente no .env.prod}"
: "${POSTGRES_DB:?POSTGRES_DB ausente no .env.prod}"

mkdir -p "${BACKUP_DIR}"
TIMESTAMP="$(date +%F_%H-%M-%S)"
OUT_FILE="${BACKUP_DIR}/radio_ads_${TIMESTAMP}.sql"

echo "Gerando backup em ${OUT_FILE}..."
docker exec radio-ads-postgres-prod \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" > "${OUT_FILE}"

gzip -f "${OUT_FILE}"
echo "Backup concluído: ${OUT_FILE}.gz"
