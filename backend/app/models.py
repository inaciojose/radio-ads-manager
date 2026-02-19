"""
models.py - Modelos do Banco de Dados

Aqui definimos as classes Python que representam as tabelas do banco.
O SQLAlchemy converte essas classes em tabelas automaticamente.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


# ============================================
# MODELO: Usuario
# ============================================

class Usuario(Base):
    """
    Usuário do sistema para autenticação e autorização.
    """
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(60), nullable=False, unique=True, index=True)
    nome = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="operador")  # admin|operador
    ativo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Usuario(id={self.id}, username='{self.username}', role='{self.role}')>"


# ============================================
# MODELO: Cliente
# ============================================

class Cliente(Base):
    """
    Representa um cliente/anunciante da rádio.
    
    Relacionamentos:
    - Um cliente pode ter vários contratos
    - Um cliente pode ter vários arquivos de áudio
    """
    __tablename__ = "clientes"
    
    # Colunas
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    cnpj_cpf = Column(String(18), unique=True, index=True)
    email = Column(String(100))
    telefone = Column(String(20))
    endereco = Column(Text)
    status = Column(String(20), default="ativo")  # 'ativo' ou 'inativo'
    observacoes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relacionamentos (SQLAlchemy cria automaticamente)
    # 'back_populates' cria a relação bidirecional
    contratos = relationship("Contrato", back_populates="cliente", cascade="all, delete-orphan")
    arquivos_audio = relationship("ArquivoAudio", back_populates="cliente", cascade="all, delete-orphan")
    
    def __repr__(self):
        """Representação em string (útil para debug)"""
        return f"<Cliente(id={self.id}, nome='{self.nome}')>"


# ============================================
# MODELO: Contrato
# ============================================

class Contrato(Base):
    """
    Representa um contrato/pacote de propaganda.
    
    Relacionamentos:
    - Pertence a um cliente
    - Tem vários itens (contrato_itens) detalhando as quantidades
    """
    __tablename__ = "contratos"
    
    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    numero_contrato = Column(String(50), unique=True, index=True)
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=False)
    frequencia = Column(String(10), default="ambas")  # '102.7', '104.7' ou 'ambas'
    valor_total = Column(Float)
    status_contrato = Column(String(20), default="ativo")  # 'ativo', 'concluído', 'cancelado'
    status_nf = Column(String(20), default="pendente")  # 'pendente', 'emitida', 'paga'
    numero_nf = Column(String(50))
    data_emissao_nf = Column(Date)
    observacoes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relacionamentos
    cliente = relationship("Cliente", back_populates="contratos")
    itens = relationship("ContratoItem", back_populates="contrato", cascade="all, delete-orphan")
    arquivos_metas = relationship("ContratoArquivoMeta", back_populates="contrato", cascade="all, delete-orphan")
    veiculacoes = relationship("Veiculacao", back_populates="contrato")
    
    def __repr__(self):
        return f"<Contrato(id={self.id}, numero='{self.numero_contrato}')>"


# ============================================
# MODELO: ContratoItem
# ============================================

class ContratoItem(Base):
    """
    Representa um item do contrato (tipo de programa e quantidade).
    
    Exemplo:
    - 30 chamadas na programação musical
    - 20 chamadas no programa de esportes
    """
    __tablename__ = "contrato_itens"
    
    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    tipo_programa = Column(String(50), nullable=False)  # 'musical', 'esporte', 'jornal', etc.
    quantidade_contratada = Column(Integer, nullable=False)
    quantidade_executada = Column(Integer, default=0)
    observacoes = Column(Text)
    
    # Relacionamento
    contrato = relationship("Contrato", back_populates="itens")
    
    def __repr__(self):
        return f"<ContratoItem(tipo='{self.tipo_programa}', contratada={self.quantidade_contratada}, executada={self.quantidade_executada})>"
    
    @property
    def percentual_execucao(self):
        """Calcula o percentual de execução deste item"""
        if self.quantidade_contratada == 0:
            return 0
        return round((self.quantidade_executada / self.quantidade_contratada) * 100, 2)
    
    @property
    def quantidade_restante(self):
        """Calcula quantas chamadas ainda faltam"""
        return max(0, self.quantidade_contratada - self.quantidade_executada)


class ContratoArquivoMeta(Base):
    """
    Meta de veiculação por peça (arquivo) dentro de um contrato.

    Permite campanhas com múltiplos spots no mesmo contrato, com meta
    específica por arquivo.
    """
    __tablename__ = "contrato_arquivo_metas"
    __table_args__ = (
        UniqueConstraint("contrato_id", "arquivo_audio_id", name="uq_contrato_arquivo_meta"),
    )

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    arquivo_audio_id = Column(Integer, ForeignKey("arquivos_audio.id"), nullable=False)
    quantidade_meta = Column(Integer, nullable=False)
    quantidade_executada = Column(Integer, default=0, nullable=False)
    modo_veiculacao = Column(String(20), default="fixo", nullable=False)  # fixo|rodizio
    ativo = Column(Boolean, default=True, nullable=False)
    observacoes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    contrato = relationship("Contrato", back_populates="arquivos_metas")
    arquivo_audio = relationship("ArquivoAudio", back_populates="contrato_metas")

    @property
    def percentual_execucao(self):
        if self.quantidade_meta == 0:
            return 0
        return round((self.quantidade_executada / self.quantidade_meta) * 100, 2)

    @property
    def quantidade_restante(self):
        return max(0, self.quantidade_meta - self.quantidade_executada)


# ============================================
# MODELO: ArquivoAudio
# ============================================

class ArquivoAudio(Base):
    """
    Representa um arquivo de áudio de propaganda.
    
    Este é o link entre o arquivo físico e o cliente.
    """
    __tablename__ = "arquivos_audio"
    
    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    nome_arquivo = Column(String(255), nullable=False, unique=True, index=True)
    titulo = Column(String(200))
    duracao_segundos = Column(Integer)
    caminho_completo = Column(Text)
    ativo = Column(Boolean, default=True)
    data_upload = Column(DateTime(timezone=True), server_default=func.now())
    observacoes = Column(Text)
    
    # Relacionamentos
    cliente = relationship("Cliente", back_populates="arquivos_audio")
    contrato_metas = relationship("ContratoArquivoMeta", back_populates="arquivo_audio", cascade="all, delete-orphan")
    veiculacoes = relationship("Veiculacao", back_populates="arquivo_audio", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ArquivoAudio(id={self.id}, nome='{self.nome_arquivo}')>"


# ============================================
# MODELO: Veiculacao
# ============================================

class Veiculacao(Base):
    """
    Representa uma veiculação (quando a propaganda foi ao ar).
    
    Esta tabela é preenchida automaticamente pelo monitor de logs.
    """
    __tablename__ = "veiculacoes"
    
    id = Column(Integer, primary_key=True, index=True)
    arquivo_audio_id = Column(Integer, ForeignKey("arquivos_audio.id"), nullable=False)
    contrato_id = Column(Integer, ForeignKey("contratos.id"))
    data_hora = Column(DateTime(timezone=True), nullable=False, index=True)
    frequencia = Column(String(10), index=True)  # Frequência onde a chamada foi executada
    tipo_programa = Column(String(50))
    fonte = Column(String(50), default="zara_log")  # De onde veio a informação
    processado = Column(Boolean, default=False, index=True)  # Se já foi contabilizado
    contabilizada = Column(Boolean, default=True, index=True)  # Se incrementou algum contador de contrato
    
    # Relacionamentos
    arquivo_audio = relationship("ArquivoAudio", back_populates="veiculacoes")
    contrato = relationship("Contrato", back_populates="veiculacoes")
    
    def __repr__(self):
        return f"<Veiculacao(id={self.id}, data_hora={self.data_hora}, processado={self.processado})>"


# ============================================
# MÉTODOS ÚTEIS
# ============================================

def criar_numero_contrato(db, ano=None):
    """
    Gera um número de contrato sequencial no formato AAAA/NNN
    Exemplo: 2024/001, 2024/002, etc.
    
    Args:
        db: Sessão do banco
        ano: Ano do contrato (usa o ano atual se não informado)
    
    Returns:
        String no formato AAAA/NNN
    """
    from datetime import datetime
    
    if ano is None:
        ano = datetime.now().year
    
    # Buscar o último número de contrato do ano
    ultimo_contrato = (
        db.query(Contrato)
        .filter(Contrato.numero_contrato.like(f"{ano}/%"))
        .order_by(Contrato.numero_contrato.desc())
        .first()
    )
    
    if ultimo_contrato:
        # Extrair o número sequencial
        numero_str = ultimo_contrato.numero_contrato.split("/")[1]
        proximo_numero = int(numero_str) + 1
    else:
        proximo_numero = 1
    
    # Formatar com zeros à esquerda (001, 002, etc.)
    return f"{ano}/{proximo_numero:03d}"
