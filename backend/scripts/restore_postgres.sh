#!/usr/bin/env bash
set -euo pipefail

# Restauração de backup lógico no PostgreSQL de produção.
# Uso:
#   ./scripts/restore_postgres.sh /opt/radio-ads/backend /opt/radio-ads/backups/radio_ads_YYYY-MM-DD_HH-MM-SS.sql.gz

BACKEND_DIR="${1:-$(pwd)}"
BACKUP_FILE="${2:-}"
ENV_FILE="${BACKEND_DIR}/.env.prod"

if [[ -z "${BACKUP_FILE}" ]]; then
  echo "ERRO: informe o caminho do arquivo de backup (.sql ou .sql.gz)."
  exit 1
fi
if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "ERRO: backup não encontrado: ${BACKUP_FILE}"
  exit 1
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERRO: .env.prod não encontrado em ${BACKEND_DIR}"
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

: "${POSTGRES_USER:?POSTGRES_USER ausente no .env.prod}"
: "${POSTGRES_DB:?POSTGRES_DB ausente no .env.prod}"

read -r -p "ATENÇÃO: isso sobrescreverá dados de ${POSTGRES_DB}. Continuar? (yes/no) " CONFIRM
if [[ "${CONFIRM}" != "yes" ]]; then
  echo "Operação cancelada."
  exit 1
fi

echo "Limpando schema public..."
docker exec -i radio-ads-postgres-prod psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"

echo "Restaurando backup..."
if [[ "${BACKUP_FILE}" == *.gz ]]; then
  gunzip -c "${BACKUP_FILE}" | docker exec -i radio-ads-postgres-prod psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"
else
  cat "${BACKUP_FILE}" | docker exec -i radio-ads-postgres-prod psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"
fi

echo "Restore concluído com sucesso."
