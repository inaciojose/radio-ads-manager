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
import secrets
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from app.database import init_db, get_database_info, SessionLocal
from app.auth import ensure_initial_admin, validate_auth_settings, set_monitor_secret
from app.routers import arquivos, audit_log, auth, caixeta, clientes, comissoes, contratos, notas_fiscais, programas, responsaveis, usuarios, veiculacoes
from app.services.contratos_service import auto_concluir_contratos_expirados
from app.services.audit_service import limpar_logs_antigos
from app.services.veiculacoes_service import limpar_veiculacoes_antigas


# ============================================
# MONITOR DE LOGS — Subprocesso gerenciado
# ============================================

_monitor_process: Optional[subprocess.Popen] = None
_monitor_stop_event = threading.Event()
_monitor_watchdog_thread: Optional[threading.Thread] = None


def _monitor_script_path() -> Path:
    return Path(__file__).resolve().parent.parent / "log_monitor" / "monitor.py"


def _log_sources_acessiveis() -> bool:
    """Retorna True se ao menos um diretório de LOG_SOURCES existir."""
    raw = os.getenv("LOG_SOURCES", "")
    for chunk in raw.split(";"):
        if "=" not in chunk:
            continue
        _, path = chunk.split("=", 1)
        if Path(path.strip()).exists():
            return True
    return False


def _pipe_reader(proc: subprocess.Popen):
    """Lê stdout do subprocesso e repassa ao print (capturado pelo uvicorn)."""
    try:
        for line in proc.stdout:
            print(f"[monitor] {line.rstrip()}", flush=True)
    except Exception:
        pass


def _start_monitor() -> Optional[subprocess.Popen]:
    script = _monitor_script_path()
    if not script.exists():
        print("⚠️  Monitor de logs não encontrado em:", script)
        return None

    if not _log_sources_acessiveis():
        print("⚠️  Monitor de logs não iniciado — nenhum diretório de LOG_SOURCES acessível")
        return None

    try:
        monitor_secret = secrets.token_hex(32)
        set_monitor_secret(monitor_secret)
        env = os.environ.copy()
        env["RADIO_ADS_MONITOR_SECRET"] = monitor_secret
        proc = subprocess.Popen(
            [sys.executable, str(script), "watch"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        threading.Thread(target=_pipe_reader, args=(proc,), daemon=True).start()
        return proc
    except Exception as exc:
        print(f"⚠️  Falha ao iniciar monitor de logs: {exc}")
        return None


def _monitor_watchdog_fn():
    """Reinicia o monitor se o processo morrer."""
    global _monitor_process
    while not _monitor_stop_event.wait(timeout=30):
        if _monitor_process and _monitor_process.poll() is not None:
            print("⚠️  Monitor de logs encerrou inesperadamente — reiniciando...")
            _monitor_process = _start_monitor()
            if _monitor_process:
                print(f"🔍 Monitor de logs reiniciado (PID {_monitor_process.pid})")


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

    # Concluir contratos de dinâmica única cujo período já encerrou
    with SessionLocal() as db:
        n = auto_concluir_contratos_expirados(db)
        if n:
            print(f"📋 {n} contrato(s) concluído(s) automaticamente")

    # Remover entradas de audit log com mais de 30 dias
    with SessionLocal() as db:
        n_audit = limpar_logs_antigos(db, dias=30)
        if n_audit:
            print(f"🗑️  {n_audit} registro(s) de audit log removido(s) (>30 dias)")

    # Remover veiculações com mais de 90 dias
    with SessionLocal() as db:
        n_veic = limpar_veiculacoes_antigas(db, dias=90)
        if n_veic:
            print(f"🗑️  {n_veic} veiculação(ões) removida(s) (>90 dias)")

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

    # Iniciar monitor de logs como subprocesso
    global _monitor_process, _monitor_watchdog_thread
    _monitor_stop_event.clear()
    _monitor_process = _start_monitor()
    if _monitor_process:
        print(f"🔍 Monitor de logs iniciado (PID {_monitor_process.pid})")
        _monitor_watchdog_thread = threading.Thread(target=_monitor_watchdog_fn, daemon=True)
        _monitor_watchdog_thread.start()

    yield  # Aqui a aplicação roda normalmente

    # SHUTDOWN
    print("👋 Encerrando aplicação...")
    _monitor_stop_event.set()
    if _monitor_process and _monitor_process.poll() is None:
        _monitor_process.terminate()
        try:
            _monitor_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _monitor_process.kill()
        print("🛑 Monitor de logs encerrado")


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

# Registrar router de programas
app.include_router(programas.router)

# Registrar router de responsáveis
app.include_router(responsaveis.router)

# Registrar router de comissões
app.include_router(comissoes.router)

# Registrar router de arquivos
app.include_router(arquivos.router)

# Registrar visão global de notas fiscais
app.include_router(notas_fiscais.router)

# Registrar auth
app.include_router(auth.router)

# Registrar usuários
app.include_router(usuarios.router)

# Registrar grade de comerciais (caixeta)
app.include_router(caixeta.router)

# Registrar audit log (somente admin)
app.include_router(audit_log.router)


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
