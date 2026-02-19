"""
database.py - Configuração do Banco de Dados

Suporta PostgreSQL via DATABASE_URL e mantém fallback para SQLite local.
"""

import os
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# ============================================
# CONFIGURAÇÃO DA CONEXÃO
# ============================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(BASE_DIR, "radio_ads.db")
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Permite uso de PostgreSQL em produção e SQLite como fallback local.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
IS_SQLITE = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

engine_kwargs: dict[str, Any] = {"echo": False}
if IS_SQLITE:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)

# SessionLocal é uma "fábrica" de sessões
# Cada vez que precisamos falar com o banco, criamos uma sessão nova
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base é a classe pai de todos os nossos modelos (tabelas)
Base = declarative_base()


def _ensure_sqlite_indexes() -> None:
    """
    Mantém índices funcionais que não são expressos no metadata.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_veiculacoes_evento
                ON veiculacoes (arquivo_audio_id, data_hora, IFNULL(frequencia, ''))
                """
            )
        )


# ============================================
# FUNÇÃO AUXILIAR PARA CRIAR SESSÕES
# ============================================

def get_db():
    """
    Esta função cria uma sessão do banco de dados e a fecha automaticamente
    quando terminar de usar. É usada como "dependency" no FastAPI.
    
    Uso:
        @app.get("/clientes")
        def listar_clientes(db: Session = Depends(get_db)):
            # Aqui 'db' é uma sessão pronta para usar
            clientes = db.query(Cliente).all()
            return clientes
    """
    db = SessionLocal()
    try:
        yield db  # Retorna a sessão para ser usada
    finally:
        db.close()  # Fecha a sessão quando terminar


# ============================================
# FUNÇÃO PARA INICIALIZAR O BANCO
# ============================================

def init_db():
    """
    Cria todas as tabelas no banco de dados se elas não existirem.
    Deve ser chamada uma vez quando o aplicativo inicia.
    """
    # Importar todos os modelos aqui para que o SQLAlchemy os conheça
    from app import models
    
    if IS_SQLITE:
        Base.metadata.create_all(bind=engine)
        _ensure_sqlite_indexes()
        print(f"✅ Banco de dados SQLite inicializado em: {SQLALCHEMY_DATABASE_URL}")
        return

    print("✅ Banco PostgreSQL configurado. Use Alembic para aplicar migrações: `alembic upgrade head`.")


# ============================================
# INFORMAÇÕES SOBRE O BANCO
# ============================================

def get_database_info():
    """
    Retorna informações sobre o banco de dados.
    Útil para debug e monitoramento.
    """
    if IS_SQLITE:
        exists = os.path.exists(DATABASE_PATH)
        return {
            "type": "SQLite",
            "url": SQLALCHEMY_DATABASE_URL,
            "path": DATABASE_PATH,
            "exists": exists,
            "size_mb": round(os.path.getsize(DATABASE_PATH) / (1024 * 1024), 2) if exists else 0,
        }

    connected = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        connected = True
    except Exception:
        connected = False

    return {
        "type": "PostgreSQL",
        "url": SQLALCHEMY_DATABASE_URL,
        "connected": connected,
        "exists": connected,
        "size_mb": None,
    }
