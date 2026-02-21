"""
main.py - Arquivo Principal da API

Este é o ponto de entrada da aplicação.
Aqui configuramos o FastAPI e registramos todas as rotas.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
import uuid
from typing import Any

from app.database import init_db, get_database_info
from app.auth import ensure_initial_admin, validate_auth_settings
from app.routers import arquivos, auth, clientes, contratos, notas_fiscais, usuarios, veiculacoes


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
APP_DEBUG = _env_bool("APP_DEBUG", APP_ENV in {"development", "dev", "local"})
API_DOCS_ENABLED = _env_bool("API_DOCS_ENABLED", APP_DEBUG)


# ============================================
# LIFECYCLE: Inicialização e Encerramento
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    
    - Startup: Executado quando a aplicação inicia
    - Shutdown: Executado quando a aplicação encerra
    """
    # STARTUP
    print("🚀 Iniciando Radio Ads Manager...")

    # Hardening de configuração em produção
    validate_auth_settings()
    
    # Inicializar banco de dados
    init_db()
    ensure_initial_admin()
    
    # Mostrar informações do banco
    db_info = get_database_info()
    print(f"📊 Banco de dados: {db_info['type']}")
    if db_info["type"] == "SQLite":
        print(f"📁 Local: {db_info['path']}")
        print(f"💾 Tamanho: {db_info['size_mb']} MB")
    else:
        print(f"🔗 URL: {db_info['url']}")
        print(f"🔌 Conectado: {db_info.get('connected', False)}")
    
    print("✅ Aplicação pronta!")
    print("📖 Documentação: http://localhost:8000/docs")
    
    yield  # Aqui a aplicação roda normalmente
    
    # SHUTDOWN
    print("👋 Encerrando aplicação...")


# ============================================
# CRIAR APLICAÇÃO FASTAPI
# ============================================

app = FastAPI(
    title="Radio Ads Manager API",
    description="API para gerenciamento de anúncios de rádio",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if API_DOCS_ENABLED else None,
    redoc_url="/redoc" if API_DOCS_ENABLED else None,
)


# ============================================
# CONFIGURAR CORS
# ============================================
# CORS permite que o frontend (em outro domínio) acesse a API

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5500,http://127.0.0.1:5500"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os métodos (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Permite todos os headers
)


# ============================================
# ERROS DE VALIDAÇÃO (422)
# ============================================

DEFAULT_ERROR_CODE_BY_STATUS = {
    400: "BAD_REQUEST",
    401: "AUTH_UNAUTHORIZED",
    403: "AUTH_FORBIDDEN",
    404: "RESOURCE_NOT_FOUND",
    409: "RESOURCE_CONFLICT",
    422: "VALIDATION_ERROR",
}

ERROR_CODE_EXACT_MAP = {
    "Usuário ou senha inválidos": "AUTH_INVALID_CREDENTIALS",
    "Username já cadastrado": "USER_USERNAME_ALREADY_EXISTS",
    "Usuário não encontrado": "USER_NOT_FOUND",
    "Não é possível excluir seu próprio usuário": "USER_SELF_DELETE_NOT_ALLOWED",
    "Não é possível remover o último admin ativo": "USER_LAST_ADMIN_DELETE_NOT_ALLOWED",
    "Sem permissão": "AUTH_FORBIDDEN",
    "Token inválido": "AUTH_INVALID_TOKEN",
    "Token expirado": "AUTH_TOKEN_EXPIRED",
    "Autenticação obrigatória": "AUTH_REQUIRED",
}

ERROR_CODE_PREFIX_MAP = [
    ("Cliente com ID ", "CLIENT_NOT_FOUND"),
    ("Contrato com ID ", "CONTRACT_NOT_FOUND"),
    ("Item ", "CONTRACT_ITEM_NOT_FOUND"),
    ("Meta ", "CONTRACT_META_NOT_FOUND"),
    ("Nota fiscal com ID ", "INVOICE_NOT_FOUND"),
    ("Arquivo com ID ", "AUDIO_FILE_NOT_FOUND"),
    ("Veiculação com ID ", "AIRING_NOT_FOUND"),
    ("Já existe um cliente cadastrado com o CNPJ/CPF:", "CLIENT_DOCUMENT_ALREADY_EXISTS"),
    ("Já existe outro cliente com o CNPJ/CPF:", "CLIENT_DOCUMENT_ALREADY_EXISTS"),
    ("Não é possível deletar cliente com ", "CLIENT_HAS_ACTIVE_CONTRACTS"),
    ("Ja existe arquivo cadastrado com nome ", "AUDIO_FILE_NAME_ALREADY_EXISTS"),
    ("Ja existe meta para este arquivo neste contrato", "CONTRACT_FILE_GOAL_ALREADY_EXISTS"),
    ("Ja existe nota para este tipo/competencia neste contrato.", "INVOICE_ALREADY_EXISTS_FOR_PERIOD"),
    ("Competencia invalida. Use o formato YYYY-MM.", "INVALID_COMPETENCE_FORMAT"),
]


def _infer_error_code_from_message(message: str, status_code: int) -> str:
    if message in ERROR_CODE_EXACT_MAP:
        return ERROR_CODE_EXACT_MAP[message]

    for prefix, code in ERROR_CODE_PREFIX_MAP:
        if message.startswith(prefix):
            return code

    return DEFAULT_ERROR_CODE_BY_STATUS.get(status_code, "REQUEST_ERROR")


def _normalize_http_exception_detail(detail: Any, status_code: int) -> tuple[str, str, dict]:
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("detail") or "Erro de requisição")
        code = str(detail.get("code") or _infer_error_code_from_message(message, status_code))
        meta = {k: v for k, v in detail.items() if k not in {"message", "detail", "code"}}
        return message, code, meta

    message = str(detail or "Erro de requisição")
    code = _infer_error_code_from_message(message, status_code)
    return message, code, {}

def _translate_validation_message(message: str) -> str:
    raw = (message or "").strip()
    lower = raw.lower()

    if "field required" in lower:
        return "Campo obrigatório."
    if "string should have at least" in lower:
        return raw.replace("String should have at least", "Deve ter no mínimo").replace(
            "characters", "caracteres"
        )
    if "string should have at most" in lower:
        return raw.replace("String should have at most", "Deve ter no máximo").replace(
            "characters", "caracteres"
        )
    if "input should be greater than or equal to" in lower:
        return raw.replace("Input should be greater than or equal to", "Deve ser maior ou igual a")
    if "input should be greater than" in lower:
        return raw.replace("Input should be greater than", "Deve ser maior que")
    if "input should be less than or equal to" in lower:
        return raw.replace("Input should be less than or equal to", "Deve ser menor ou igual a")
    if "input should be less than" in lower:
        return raw.replace("Input should be less than", "Deve ser menor que")
    if "input should be a valid boolean" in lower:
        return "Valor inválido. Informe verdadeiro ou falso."
    if "input should be a valid date" in lower:
        return "Data inválida. Verifique o formato informado."
    if "input should be a valid integer" in lower:
        return "Número inteiro inválido."
    if "input should be a valid number" in lower:
        return "Número inválido."
    if "input should be a valid string" in lower:
        return "Texto inválido."

    return raw or "Valor inválido."


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        details.append(
            {
                "loc": list(err.get("loc", [])),
                "msg": _translate_validation_message(err.get("msg", "")),
                "type": err.get("type", "value_error"),
            }
        )

    return JSONResponse(
        status_code=422,
        content={
            "error": "Dados inválidos",
            "detail": details,
            "code": "VALIDATION_ERROR",
            "success": False,
        },
    )


# ============================================
# ERROS DE NEGÓCIO / AUTORIZAÇÃO (4xx)
# ============================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    message, code, meta = _normalize_http_exception_detail(exc.detail, exc.status_code)
    content = {
        "error": "Erro de requisição",
        "detail": message,
        "code": code,
        "success": False,
    }
    if meta:
        content["meta"] = meta
    return JSONResponse(status_code=exc.status_code, content=content)


# ============================================
# TRATAMENTO DE ERROS GLOBAL
# ============================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Captura todos os erros não tratados e retorna uma resposta JSON.
    Útil para debug e para que o frontend saiba o que aconteceu.
    """
    import traceback

    error_id = str(uuid.uuid4())
    print(f"❌ Erro não tratado [{error_id}]: {exc}")
    print(traceback.format_exc())

    return JSONResponse(
        status_code=500,
        content={
            "error": "Erro interno do servidor",
            "detail": str(exc) if APP_DEBUG else "Erro interno. Consulte os logs com o ID informado.",
            "error_id": error_id,
            "success": False
        }
    )


# ============================================
# ROTAS PRINCIPAIS
# ============================================

@app.get("/")
def root():
    """
    Rota raiz - Informações básicas da API
    """
    return {
        "app": "Radio Ads Manager API",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
        "endpoints": {
            "clientes": "/clientes",
            "contratos": "/contratos",
            "veiculacoes": "/veiculacoes",
            "arquivos": "/arquivos",
            "notas_fiscais": "/notas-fiscais",
            "auth": "/auth",
            "usuarios": "/usuarios",
        }
    }


@app.get("/health")
def health_check():
    """
    Endpoint de health check - Verifica se a aplicação está funcionando
    """
    db_info = get_database_info()
    
    return {
        "status": "healthy",
        "database": {
            "connected": db_info["exists"],
            "size_mb": db_info["size_mb"]
        }
    }


# ============================================
# REGISTRAR ROUTERS
# ============================================

# Registrar router de clientes
app.include_router(clientes.router)

# Registrar router de contratos
app.include_router(contratos.router)

# Registrar router de veiculações
app.include_router(veiculacoes.router)

# Registrar router de arquivos
app.include_router(arquivos.router)

# Registrar visão global de notas fiscais
app.include_router(notas_fiscais.router)

# Registrar auth
app.include_router(auth.router)

# Registrar usuários
app.include_router(usuarios.router)


# ============================================
# EXECUTAR APLICAÇÃO
# ============================================

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload_enabled = _env_bool("APP_RELOAD", APP_DEBUG)
    workers = int(os.getenv("WEB_CONCURRENCY", "2"))

    run_kwargs = {
        "app": "app.main:app",
        "host": host,
        "port": port,
        "reload": reload_enabled,
    }
    if not reload_enabled:
        run_kwargs["workers"] = max(1, workers)

    uvicorn.run(**run_kwargs)
