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
│   ├── requirements.txt
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
```

## Executar API
```bash
cd backend
python -m app.main
```

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
- SQLite local: `backend/radio_ads.db`
- O arquivo é criado automaticamente na primeira execução.

## Observações
- Regras de negócio ficam em `backend/app/services`.
- Endpoints HTTP ficam em `backend/app/routers`.
- Scripts manuais e testes automatizados estão separados para evitar confusão no fluxo de desenvolvimento.
