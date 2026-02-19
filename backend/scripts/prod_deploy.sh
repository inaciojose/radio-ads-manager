#!/usr/bin/env bash
set -euo pipefail

# Deploy de produção para backend + banco + frontend estático.
# Uso:
#   ./scripts/prod_deploy.sh /opt/radio-ads/backend /var/www/radio-ads

BACKEND_DIR="${1:-$(pwd)}"
FRONTEND_PUBLISH_DIR="${2:-/var/www/radio-ads}"
REPO_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"
FRONTEND_SRC_DIR="${REPO_ROOT}/frontend"

cd "${BACKEND_DIR}"

if [[ ! -f ".env.prod" ]]; then
  echo "ERRO: arquivo .env.prod não encontrado em ${BACKEND_DIR}"
  exit 1
fi

echo "[1/5] Build e subida dos containers..."
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

echo "[2/5] Aguardando API ficar saudável..."
for i in {1..30}; do
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null; then
    echo "API saudável."
    break
  fi
  sleep 2
  if [[ "$i" == "30" ]]; then
    echo "ERRO: API não ficou saudável no tempo esperado."
    docker compose -f docker-compose.prod.yml ps
    exit 1
  fi
done

if [[ ! -d "${FRONTEND_SRC_DIR}" ]]; then
  echo "ERRO: frontend não encontrado em ${FRONTEND_SRC_DIR}"
  exit 1
fi

echo "[3/5] Publicando frontend em ${FRONTEND_PUBLISH_DIR}..."
sudo mkdir -p "${FRONTEND_PUBLISH_DIR}"
sudo rsync -av --delete "${FRONTEND_SRC_DIR}/" "${FRONTEND_PUBLISH_DIR}/"

echo "[4/5] Estado dos containers:"
docker compose -f docker-compose.prod.yml ps

echo "[5/5] Deploy concluído."
echo "Acesse: https://SEU_DOMINIO"
