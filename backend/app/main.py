"""
main.py - Arquivo Principal da API

Este é o ponto de entrada da aplicação.
Aqui configuramos o FastAPI e registramos todas as rotas.
"""

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
import uuid

from app.database import init_db, get_database_info
from app.auth import (
    ROLE_ADMIN,
    ROLE_OPERADOR,
    ensure_initial_admin,
    require_monitor_or_roles,
    validate_auth_settings,
)
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
def health_check(_auth=Depends(require_monitor_or_roles(ROLE_ADMIN, ROLE_OPERADOR))):
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
