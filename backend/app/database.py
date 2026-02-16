"""
database.py - Configuração do Banco de Dados

Este arquivo configura a conexão com o banco de dados SQLite
e cria a "sessão" que usaremos para fazer consultas.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# ============================================
# CONFIGURAÇÃO DA CONEXÃO
# ============================================

# Caminho onde o arquivo do banco será salvo
# Você pode mudar isso depois para colocar em outro local
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_PATH = os.path.join(BASE_DIR, "radio_ads.db")

# String de conexão do SQLite
# sqlite:/// significa "usar SQLite" e depois vem o caminho do arquivo
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Criar o "engine" - é como se fosse o motor que conecta ao banco
# check_same_thread=False é necessário para SQLite funcionar com FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    echo=False  # Se True, mostra todas as queries SQL no console (útil para debug)
)

# SessionLocal é uma "fábrica" de sessões
# Cada vez que precisamos falar com o banco, criamos uma sessão nova
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base é a classe pai de todos os nossos modelos (tabelas)
Base = declarative_base()


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
    
    # Criar todas as tabelas
    Base.metadata.create_all(bind=engine)
    print(f"✅ Banco de dados inicializado em: {DATABASE_PATH}")


# ============================================
# INFORMAÇÕES SOBRE O BANCO
# ============================================

def get_database_info():
    """
    Retorna informações sobre o banco de dados.
    Útil para debug e monitoramento.
    """
    return {
        "type": "SQLite",
        "path": DATABASE_PATH,
        "exists": os.path.exists(DATABASE_PATH),
        "size_mb": round(os.path.getsize(DATABASE_PATH) / (1024 * 1024), 2) if os.path.exists(DATABASE_PATH) else 0
    }