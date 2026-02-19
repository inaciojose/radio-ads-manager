# Deploy de Produção (Rocky Linux + Docker + Whaler)

Este guia cobre:
- Backend FastAPI
- Banco PostgreSQL
- Frontend estático
- Nginx com proxy `/api`
- HTTPS com Let's Encrypt
- Backup/restore
- Operação e acesso do usuário final

## 1. Topologia de produção

Fluxo recomendado:
1. Usuário acessa `https://radio.seu-dominio.com`.
2. Nginx serve o frontend.
3. Requisições `/api/*` são encaminhadas para `127.0.0.1:8000` (container da API).
4. API acessa PostgreSQL via rede Docker.

Com isso, a API não fica exposta diretamente na internet.

## 2. Pré-requisitos no Rocky Linux

```bash
sudo dnf -y update
sudo dnf -y install git curl ca-certificates rsync
sudo timedatectl set-timezone America/Sao_Paulo
```

Portas necessárias:
1. `22/tcp` (SSH)
2. `80/tcp` (HTTP)
3. `443/tcp` (HTTPS)

## 3. Instalar Docker + Compose Plugin

```bash
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Faça logout/login e valide:

```bash
docker --version
docker compose version
```

## 4. Clonar projeto no servidor

```bash
sudo mkdir -p /opt/radio-ads
sudo chown -R $USER:$USER /opt/radio-ads
cd /opt/radio-ads
git clone <URL_DO_REPOSITORIO> .
```

## 5. Configurar variáveis de produção

```bash
cd /opt/radio-ads/backend
cp .env.prod.example .env.prod
```

Gerar segredos:

```bash
openssl rand -base64 48   # AUTH_TOKEN_SECRET
openssl rand -base64 32   # POSTGRES_PASSWORD
openssl rand -base64 24   # INITIAL_ADMIN_PASSWORD
```

Edite `.env.prod`:
1. `AUTH_TOKEN_SECRET`: obrigatório forte
2. `POSTGRES_PASSWORD`: obrigatório forte
3. `DATABASE_URL`: com mesmo usuário/senha do postgres
4. `CORS_ALLOW_ORIGINS=https://radio.seu-dominio.com`
5. `APP_DEBUG=false`
6. `API_DOCS_ENABLED=false`

## 6. Subir backend + banco

```bash
cd /opt/radio-ads/backend
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f api
```

Observação:
- O serviço API já executa `alembic upgrade head` no startup.

Teste saúde local:

```bash
curl -fsS http://127.0.0.1:8000/health
```

## 7. Publicar frontend

```bash
sudo mkdir -p /var/www/radio-ads
sudo rsync -av --delete /opt/radio-ads/frontend/ /var/www/radio-ads/
```

## 8. Configurar Nginx

Instalar:

```bash
sudo dnf -y install nginx
sudo systemctl enable --now nginx
```

Aplicar config:

```bash
sudo cp /opt/radio-ads/backend/deploy/nginx/radio-ads.conf /etc/nginx/conf.d/radio-ads.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 9. HTTPS com Let's Encrypt

```bash
sudo dnf -y install certbot python3-certbot-nginx
sudo certbot --nginx -d radio.seu-dominio.com
sudo systemctl enable --now certbot-renew.timer
```

## 10. Firewall

```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
```

## 11. Deploy automatizado com script

O projeto inclui:
- `backend/scripts/prod_deploy.sh`
- `backend/scripts/backup_postgres.sh`
- `backend/scripts/restore_postgres.sh`

Deploy:

```bash
cd /opt/radio-ads/backend
./scripts/prod_deploy.sh /opt/radio-ads/backend /var/www/radio-ads
```

## 12. Backup e restore

Backup manual:

```bash
cd /opt/radio-ads/backend
./scripts/backup_postgres.sh /opt/radio-ads/backend /opt/radio-ads/backups
```

Restore manual:

```bash
cd /opt/radio-ads/backend
./scripts/restore_postgres.sh /opt/radio-ads/backend /opt/radio-ads/backups/radio_ads_YYYY-MM-DD_HH-MM-SS.sql.gz
```

## 13. Agendar backup diário (cron)

```bash
crontab -e
```

Adicionar:

```cron
0 2 * * * /opt/radio-ads/backend/scripts/backup_postgres.sh /opt/radio-ads/backend /opt/radio-ads/backups >> /opt/radio-ads/backups/backup.log 2>&1
```

## 14. Whaler (operação)

No Whaler:
1. Cadastrar stack com `backend/docker-compose.prod.yml`.
2. Definir env file: `backend/.env.prod`.
3. Acompanhar saúde de `radio-ads-api-prod` e `radio-ads-postgres-prod`.
4. Habilitar alertas de:
   - status `unhealthy`
   - restart loop
   - uso alto de CPU/memória

## 15. Como o usuário acessa o sistema

1. Acessa `https://radio.seu-dominio.com`.
2. Faz login com o usuário inicial (ou usuário criado).
3. Usa módulos de clientes, contratos, veiculações, arquivos e NFs.
4. Todo tráfego de API ocorre por `https://radio.seu-dominio.com/api/...`.

## 16. Checklist de go-live

1. `docker compose ps` com serviços `healthy`.
2. `curl https://radio.seu-dominio.com/api/health` responde `healthy`.
3. Login funcionando.
4. CRUD básico funcionando (cliente/contrato/NF).
5. Backup criado e restore testado em ambiente de homologação.
6. Certificado HTTPS válido e renovação automática ativa.
7. Whaler com monitoramento/alerta ativo.
