# Radio Ads Manager

Sistema de gerenciamento de anúncios para rádio com controle de clientes, contratos, veiculações e monitoramento via logs.

## Funcionalidades
- Cadastro de clientes/anunciantes
- Gestão de contratos e pacotes de propaganda
- Controle de veiculações e execução dos itens contratados
- Integração com logs do Zara Studio
- Controle de notas fiscais
- Dashboard e relatórios

## Estrutura do Projeto
```text
radio-ads-manager/
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── routers/
│   │   └── services/
│   ├── log_monitor/
│   ├── scripts/           # scripts manuais de demonstração
│   ├── tests/             # suíte pytest automatizada
│   ├── docker-compose.yml
│   ├── requirements.txt
│   ├── alembic.ini
│   └── pytest.ini
├── frontend/
└── docs/
```

## Pré-requisitos
- Python 3.8+
- pip

## Instalação
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Banco de Dados (PostgreSQL)
```bash
cd backend
docker compose up -d postgres
```

Configuração de ambiente (`backend/.env`):
- `DATABASE_URL=postgresql+psycopg2://radio_user:radio_pass@localhost:5432/radio_ads`
- `LOG_SOURCES=102.7=K:\Registro FM;104.7=K:\Registro 104_7`
- `CHAMADAS_BASE_PATH=J:\AZARASTUDIO\CHAMADAS`

## Migrações (Alembic)
```bash
cd backend
alembic upgrade head
```

Se o banco já existir com tabelas criadas anteriormente (sem histórico Alembic), marque a revisão atual:
```bash
cd backend
alembic stamp head
```

## Executar API
```bash
cd backend
python -m app.main
```

Execução em produção (exemplo):
```bash
cd backend
APP_ENV=production \
APP_DEBUG=false \
API_DOCS_ENABLED=false \
APP_RELOAD=false \
WEB_CONCURRENCY=2 \
python -m app.main
```

Requisitos mínimos para produção:
- `AUTH_TOKEN_SECRET` com 32+ caracteres
- `INITIAL_ADMIN_PASSWORD` forte (10+ caracteres)
- `APP_ENV=production`

## Deploy com Docker (Produção)
Arquivos:
- `backend/Dockerfile`
- `backend/docker-compose.prod.yml`
- `backend/.env.prod.example`

Passos:
```bash
cd backend
cp .env.prod.example .env.prod
# edite .env.prod com senhas/chaves reais
docker compose -f docker-compose.prod.yml up -d --build
```

Observações:
- A API sobe executando `alembic upgrade head` automaticamente antes de iniciar.
- Healthchecks habilitados para `postgres` e `api`.
- Política de reinício: `unless-stopped`.

## Documentação da API
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testes Automatizados
```bash
cd backend
python -m pytest -q
```

## Scripts Manuais
```bash
cd backend
python scripts/api_demo.py
python scripts/contratos_demo.py
python scripts/sistema_completo_demo.py
```

## Banco de Dados
- Principal: PostgreSQL via `DATABASE_URL` no arquivo `backend/.env`.
- Fallback local: SQLite (`backend/radio_ads.db`) caso `DATABASE_URL` não esteja configurada.

## Observações
- Regras de negócio ficam em `backend/app/services`.
- Endpoints HTTP ficam em `backend/app/routers`.
- Scripts manuais e testes automatizados estão separados para evitar confusão no fluxo de desenvolvimento.
