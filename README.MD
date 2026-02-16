# 📻 Radio Ads Manager

Sistema de gerenciamento de anúncios para rádio com controle de veiculação, clientes e contratos.

## 🎯 Funcionalidades

- ✅ Cadastro de clientes/anunciantes
- ✅ Gestão de contratos e pacotes de propaganda
- ✅ Controle de veiculações (quantas chamadas foram ao ar)
- ✅ Integração com logs do Zara Studio
- ✅ Controle de notas fiscais
- ✅ Dashboard e relatórios

## 📋 Pré-requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)
- Git (opcional)

## 🚀 Instalação

### Passo 1: Criar ambiente virtual

O ambiente virtual isola as dependências do projeto.

**Linux/Mac:**

```bash
cd radio-ads-manager/backend
python3 -m venv venv
source venv/bin/activate
```

**Windows:**

```bash
cd radio-ads-manager\backend
python -m venv venv
venv\Scripts\activate
```

### Passo 2: Instalar dependências

```bash
pip install -r requirements.txt
```

### Passo 3: Executar a aplicação

```bash
cd app
python main.py
```

Ou usando uvicorn diretamente:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📖 Acessar a Documentação

Após iniciar o servidor, acesse:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

A documentação é **interativa** - você pode testar todas as APIs direto pelo navegador!

## 🎓 Entendendo a Estrutura

```
backend/
├── app/
│   ├── main.py           # Arquivo principal (inicia o servidor)
│   ├── database.py       # Configuração do banco de dados
│   ├── models.py         # Modelos (tabelas) do banco
│   ├── schemas.py        # Validação de dados (entrada/saída)
│   └── routers/          # Endpoints da API
│       └── clientes.py   # Rotas de clientes
├── requirements.txt      # Dependências do projeto
└── radio_ads.db         # Banco de dados SQLite (criado automaticamente)
```

## 📚 Conceitos Importantes

### O que é uma API REST?

Uma API REST é como um "garçom" entre o frontend (interface) e o banco de dados:

- O **frontend** pede algo (ex: "me dê a lista de clientes")
- A **API** processa o pedido e busca no banco
- A **API** retorna a resposta (ex: lista de clientes em formato JSON)

### HTTP Methods (Verbos)

- **GET**: Buscar dados (ex: listar clientes)
- **POST**: Criar novo registro (ex: criar cliente)
- **PUT**: Atualizar registro completo
- **PATCH**: Atualizar apenas alguns campos
- **DELETE**: Deletar registro

### Status Codes (Códigos de Resposta)

- **200**: OK - Tudo certo
- **201**: Created - Registro criado com sucesso
- **400**: Bad Request - Dados inválidos
- **404**: Not Found - Não encontrado
- **500**: Internal Server Error - Erro no servidor

## 🧪 Testando a API

### 1. Via Documentação Interativa (Recomendado)

Acesse http://localhost:8000/docs e teste direto pelo navegador!

### 2. Via curl (Terminal)

**Listar clientes:**

```bash
curl http://localhost:8000/clientes
```

**Criar cliente:**

```bash
curl -X POST http://localhost:8000/clientes \
  -H "Content-Type: application/json" \
  -d '{
    "nome": "Empresa Teste",
    "cnpj_cpf": "12.345.678/0001-90",
    "email": "contato@teste.com",
    "telefone": "(88) 99999-9999"
  }'
```

**Buscar cliente específico:**

```bash
curl http://localhost:8000/clientes/1
```

### 3. Via Python

```python
import requests

# Listar clientes
response = requests.get("http://localhost:8000/clientes")
clientes = response.json()
print(clientes)

# Criar cliente
novo_cliente = {
    "nome": "Empresa XYZ",
    "cnpj_cpf": "98.765.432/0001-10",
    "email": "xyz@empresa.com"
}
response = requests.post("http://localhost:8000/clientes", json=novo_cliente)
print(response.json())
```

## 🗄️ Banco de Dados

O banco SQLite é criado automaticamente na primeira execução.

**Localização:** `backend/radio_ads.db`

### Visualizar o banco

Você pode usar ferramentas como:

- **DB Browser for SQLite** (GUI): https://sqlitebrowser.org/
- **sqlite3** (Terminal):
  ```bash
  sqlite3 radio_ads.db
  .tables  # Lista todas as tabelas
  SELECT * FROM clientes;  # Consulta
  ```

## 🔧 Próximos Passos

1. ✅ **Clientes** - PRONTO!
2. 🚧 **Contratos** - Vamos criar a seguir
3. 🚧 **Veiculações** - Depois dos contratos
4. 🚧 **Monitor de Logs** - Integração com Zara Studio
5. 🚧 **Frontend** - Interface web

## 🐛 Resolução de Problemas

### Erro: "Module not found"

```bash
# Certifique-se de estar no ambiente virtual
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Reinstale as dependências
pip install -r requirements.txt
```

### Erro: "Address already in use"

```bash
# A porta 8000 já está em uso
# Opção 1: Matar o processo
lsof -ti:8000 | xargs kill -9  # Linux/Mac
netstat -ano | findstr :8000   # Windows (depois kill com TaskManager)

# Opção 2: Usar outra porta
uvicorn app.main:app --port 8001
```

### Banco de dados corrompido

```bash
# Delete o banco e deixe ele ser recriado
rm radio_ads.db
python app/main.py
```

## 📞 Suporte

Se tiver dúvidas ou problemas:

1. Verifique os logs do servidor (mensagens no terminal)
2. Teste os endpoints na documentação interativa (/docs)
3. Verifique se o banco foi criado corretamente

## 📝 Licença

Este projeto é de uso interno da rádio.
