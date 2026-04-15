#!/usr/bin/env bash
# ==============================================================================
# backup_postgres.sh — Backup automático do banco de dados Radio Ads Manager
#
# Uso direto:
#   ./scripts/backup_postgres.sh
#
# Via cron (exemplo — todo dia às 02:00):
#   0 2 * * * /caminho/para/radio-ads-manager/backend/scripts/backup_postgres.sh >> /var/log/radio-ads-backup.log 2>&1
#
# Variáveis de ambiente opcionais (sobrescrevem os valores do .env):
#   BACKUP_DIR   — diretório destino (padrão: <backend>/backups)
#   BACKUP_KEEP  — dias de retenção (padrão: 30)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "${SCRIPT_DIR}")"
ENV_FILE="${BACKEND_DIR}/.env"

# --- Carregar .env ---
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[backup] ERRO: .env não encontrado em ${BACKEND_DIR}" >&2
  exit 1
fi

# Lê apenas DATABASE_URL do .env (evita problemas com valores que têm espaços)
DB_URL="$(grep -E '^DATABASE_URL=' "${ENV_FILE}" | head -1 | cut -d= -f2-)"
if [[ -z "${DB_URL}" ]]; then
  echo "[backup] ERRO: DATABASE_URL não definida no .env" >&2
  exit 1
fi

# Remove driver prefix (postgresql+psycopg2:// → postgresql://)
DB_URL_CLEAN="${DB_URL#*+*://}"
DB_URL_CLEAN="${DB_URL_CLEAN#*://}"

DB_USER="${DB_URL_CLEAN%%:*}"
DB_URL_CLEAN="${DB_URL_CLEAN#*:}"
DB_PASS="${DB_URL_CLEAN%%@*}"
DB_URL_CLEAN="${DB_URL_CLEAN#*@}"
DB_HOST="${DB_URL_CLEAN%%:*}"
DB_URL_CLEAN="${DB_URL_CLEAN#*:}"
DB_PORT="${DB_URL_CLEAN%%/*}"
DB_NAME="${DB_URL_CLEAN#*/}"

# --- Configurações ---
BACKUP_DIR="${BACKUP_DIR:-${BACKEND_DIR}/backups}"
BACKUP_KEEP="${BACKUP_KEEP:-30}"

mkdir -p "${BACKUP_DIR}"

TIMESTAMP="$(date +%F_%H-%M-%S)"
OUT_FILE="${BACKUP_DIR}/radio_ads_${TIMESTAMP}.sql.gz"

echo "[backup] $(date '+%F %T') — Iniciando backup de ${DB_NAME}@${DB_HOST}:${DB_PORT}"

CONTAINER="${POSTGRES_CONTAINER:-postgres-radio}"

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  # PostgreSQL em Docker (modo preferencial)
  docker exec "${CONTAINER}" \
    pg_dump -U "${DB_USER}" -d "${DB_NAME}" \
    | gzip > "${OUT_FILE}"
else
  # PostgreSQL local (pg_dump deve estar no PATH)
  PGPASSWORD="${DB_PASS}" pg_dump \
    -h "${DB_HOST}" -p "${DB_PORT}" \
    -U "${DB_USER}" -d "${DB_NAME}" \
    --no-password \
    | gzip > "${OUT_FILE}"
fi

SIZE="$(du -sh "${OUT_FILE}" | cut -f1)"
echo "[backup] $(date '+%F %T') — Backup concluído: ${OUT_FILE} (${SIZE})"

# --- Limpeza de backups antigos ---
DELETED="$(find "${BACKUP_DIR}" -name "radio_ads_*.sql.gz" -mtime "+${BACKUP_KEEP}" -print -delete | wc -l)"
if [[ "${DELETED}" -gt 0 ]]; then
  echo "[backup] ${DELETED} backup(s) antigo(s) removido(s) (>${BACKUP_KEEP} dias)"
fi
