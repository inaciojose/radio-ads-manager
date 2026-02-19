"""
schemas.py - Schemas de Validação

Os schemas definem o formato dos dados que a API aceita e retorna.
O Pydantic valida automaticamente se os dados estão corretos.

Diferença entre Model (models.py) e Schema:
- Model: Representa tabela no banco de dados (SQLAlchemy)
- Schema: Representa dados na API (entrada/saída) (Pydantic)
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal


# ============================================
# SCHEMAS: Cliente
# ============================================

class ClienteBase(BaseModel):
    """Schema base com campos comuns de Cliente"""
    nome: str = Field(..., min_length=3, max_length=200, description="Nome ou razão social")
    cnpj_cpf: Optional[str] = Field(None, max_length=18, description="CNPJ ou CPF")
    email: Optional[str] = Field(None, max_length=100)
    telefone: Optional[str] = Field(None, max_length=20)
    endereco: Optional[str] = None
    status: str = Field(default="ativo", description="Status: ativo ou inativo")
    observacoes: Optional[str] = None
    
    @validator('status')
    def validar_status(cls, v):
        """Valida que o status é um dos valores permitidos"""
        if v not in ['ativo', 'inativo']:
            raise ValueError('Status deve ser "ativo" ou "inativo"')
        return v


class ClienteCreate(ClienteBase):
    """Schema para criar um novo cliente (POST)"""
    pass


class ClienteUpdate(BaseModel):
    """Schema para atualizar um cliente (PUT/PATCH)"""
    # Todos os campos são opcionais na atualização
    nome: Optional[str] = Field(None, min_length=3, max_length=200)
    cnpj_cpf: Optional[str] = Field(None, max_length=18)
    email: Optional[str] = Field(None, max_length=100)
    telefone: Optional[str] = Field(None, max_length=20)
    endereco: Optional[str] = None
    status: Optional[str] = None
    observacoes: Optional[str] = None


class ClienteResponse(ClienteBase):
    """Schema para retornar um cliente (GET)"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True  # Permite converter de model SQLAlchemy para Pydantic


# ============================================
# SCHEMAS: ContratoItem
# ============================================

class ContratoItemBase(BaseModel):
    """Schema base para item de contrato"""
    tipo_programa: str = Field(..., description="Tipo: musical, esporte, jornal, etc.")
    quantidade_contratada: int = Field(..., gt=0, description="Quantidade de chamadas contratadas")
    observacoes: Optional[str] = None


class ContratoItemCreate(ContratoItemBase):
    """Schema para criar item de contrato"""
    pass


class ContratoItemUpdate(BaseModel):
    """Schema para atualizar item de contrato"""
    tipo_programa: Optional[str] = None
    quantidade_contratada: Optional[int] = Field(None, gt=0)
    observacoes: Optional[str] = None


class ContratoItemResponse(ContratoItemBase):
    """Schema para retornar item de contrato"""
    id: int
    contrato_id: int
    quantidade_executada: int
    percentual_execucao: float
    quantidade_restante: int
    
    class Config:
        from_attributes = True


# ============================================
# SCHEMAS: ContratoArquivoMeta
# ============================================

class ContratoArquivoMetaBase(BaseModel):
    arquivo_audio_id: int
    quantidade_meta: int = Field(..., gt=0)
    modo_veiculacao: str = Field(default="fixo", description="fixo ou rodizio")
    ativo: bool = True
    observacoes: Optional[str] = None

    @validator("modo_veiculacao")
    def validar_modo_veiculacao(cls, v):
        if v not in ["fixo", "rodizio"]:
            raise ValueError('modo_veiculacao deve ser "fixo" ou "rodizio"')
        return v


class ContratoArquivoMetaCreate(ContratoArquivoMetaBase):
    pass


class ContratoArquivoMetaUpdate(BaseModel):
    quantidade_meta: Optional[int] = Field(None, gt=0)
    modo_veiculacao: Optional[str] = None
    ativo: Optional[bool] = None
    observacoes: Optional[str] = None

    @validator("modo_veiculacao")
    def validar_modo_veiculacao_update(cls, v):
        if v is None:
            return v
        if v not in ["fixo", "rodizio"]:
            raise ValueError('modo_veiculacao deve ser "fixo" ou "rodizio"')
        return v


class ContratoArquivoMetaResponse(ContratoArquivoMetaBase):
    id: int
    contrato_id: int
    quantidade_executada: int
    percentual_execucao: float
    quantidade_restante: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================
# SCHEMAS: Contrato
# ============================================

class ContratoBase(BaseModel):
    """Schema base para contrato"""
    cliente_id: int
    data_inicio: date
    data_fim: date
    frequencia: str = Field(default="ambas", description="Frequência: 102.7, 104.7 ou ambas")
    valor_total: Optional[float] = Field(None, ge=0, description="Valor total do contrato")
    status_contrato: str = Field(default="ativo")
    status_nf: str = Field(default="pendente")
    numero_nf: Optional[str] = None
    data_emissao_nf: Optional[date] = None
    observacoes: Optional[str] = None
    
    @validator('status_contrato')
    def validar_status_contrato(cls, v):
        if v not in ['ativo', 'concluído', 'cancelado']:
            raise ValueError('Status inválido')
        return v
    
    @validator('status_nf')
    def validar_status_nf(cls, v):
        if v not in ['pendente', 'emitida', 'paga']:
            raise ValueError('Status NF inválido')
        return v

    @validator('frequencia')
    def validar_frequencia(cls, v):
        if v not in ['102.7', '104.7', 'ambas']:
            raise ValueError('Frequência deve ser "102.7", "104.7" ou "ambas"')
        return v
    
    @validator('data_fim')
    def validar_datas(cls, v, values):
        """Valida que data_fim é maior que data_inicio"""
        if 'data_inicio' in values and v < values['data_inicio']:
            raise ValueError('Data fim deve ser maior que data início')
        return v


class ContratoCreate(ContratoBase):
    """Schema para criar contrato com seus itens"""
    itens: List[ContratoItemCreate] = Field(..., min_items=1, description="Itens do contrato")
    arquivos_metas: List[ContratoArquivoMetaCreate] = Field(default_factory=list)


class ContratoUpdate(BaseModel):
    """Schema para atualizar contrato"""
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    frequencia: Optional[str] = None
    valor_total: Optional[float] = None
    status_contrato: Optional[str] = None
    status_nf: Optional[str] = None
    numero_nf: Optional[str] = None
    data_emissao_nf: Optional[date] = None
    observacoes: Optional[str] = None

    @validator('frequencia')
    def validar_frequencia_update(cls, v):
        if v is None:
            return v
        if v not in ['102.7', '104.7', 'ambas']:
            raise ValueError('Frequência deve ser "102.7", "104.7" ou "ambas"')
        return v


class ContratoResponse(ContratoBase):
    """Schema para retornar contrato"""
    id: int
    numero_contrato: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    itens: List[ContratoItemResponse] = []
    arquivos_metas: List[ContratoArquivoMetaResponse] = []
    
    class Config:
        from_attributes = True


class ContratoResumo(BaseModel):
    """Schema para resumo de contrato (usado em listas)"""
    id: int
    numero_contrato: str
    cliente_id: int
    cliente_nome: str
    data_inicio: date
    data_fim: date
    valor_total: Optional[float]
    status_contrato: str
    status_nf: str
    total_contratado: int
    total_executado: int
    percentual_conclusao: float


# ============================================
# SCHEMAS: ArquivoAudio
# ============================================

class ArquivoAudioBase(BaseModel):
    """Schema base para arquivo de áudio"""
    cliente_id: int
    nome_arquivo: str = Field(..., max_length=255)
    titulo: Optional[str] = Field(None, max_length=200)
    duracao_segundos: Optional[int] = Field(None, ge=0)
    caminho_completo: Optional[str] = None
    ativo: bool = True
    observacoes: Optional[str] = None


class ArquivoAudioCreate(ArquivoAudioBase):
    """Schema para criar arquivo de áudio"""
    pass


class ArquivoAudioUpdate(BaseModel):
    """Schema para atualizar arquivo de áudio"""
    titulo: Optional[str] = None
    ativo: Optional[bool] = None
    observacoes: Optional[str] = None


class ArquivoAudioResponse(ArquivoAudioBase):
    """Schema para retornar arquivo de áudio"""
    id: int
    data_upload: datetime
    
    class Config:
        from_attributes = True


# ============================================
# SCHEMAS: Veiculacao
# ============================================

class VeiculacaoBase(BaseModel):
    """Schema base para veiculação"""
    arquivo_audio_id: int
    contrato_id: Optional[int] = None
    data_hora: datetime
    frequencia: Optional[str] = Field(None, description='Frequência: 102.7 ou 104.7')
    tipo_programa: Optional[str] = None
    fonte: str = "zara_log"

    @validator('frequencia')
    def validar_frequencia_veiculacao(cls, v):
        if v is None:
            return v
        if v not in ['102.7', '104.7']:
            raise ValueError('Frequência da veiculação deve ser "102.7" ou "104.7"')
        return v


class VeiculacaoCreate(VeiculacaoBase):
    """Schema para criar veiculação"""
    pass


class VeiculacaoLoteManualCreate(BaseModel):
    """Schema para lançamento manual em lote (OBS/manual)."""
    arquivo_audio_id: int
    data: date
    horarios: List[str] = Field(..., min_items=1, description="Lista HH:MM ou HH:MM:SS")
    frequencia: str = Field(..., description='Frequência: 102.7 ou 104.7')
    tipo_programa: Optional[str] = None
    fonte: str = Field(default="obs_manual")

    @validator("frequencia")
    def validar_frequencia_lote(cls, v):
        if v not in ["102.7", "104.7"]:
            raise ValueError('Frequência da veiculação deve ser "102.7" ou "104.7"')
        return v


class VeiculacaoResponse(VeiculacaoBase):
    """Schema para retornar veiculação"""
    id: int
    processado: bool
    contabilizada: bool
    
    class Config:
        from_attributes = True


class VeiculacaoDetalhada(BaseModel):
    """Schema para veiculação com informações completas"""
    id: int
    data_hora: datetime
    frequencia: Optional[str]
    tipo_programa: Optional[str]
    processado: bool
    arquivo_nome: str
    arquivo_titulo: Optional[str]
    cliente_nome: str
    numero_contrato: Optional[str]


# ============================================
# SCHEMAS: Relatórios e Estatísticas
# ============================================

class EstatisticasDia(BaseModel):
    """Estatísticas do dia"""
    data: date
    total_veiculacoes: int
    veiculacoes_por_tipo: dict
    veiculacoes_por_cliente: dict
    veiculacoes_nao_processadas: int


class ResumoCliente(BaseModel):
    """Resumo completo de um cliente"""
    cliente: ClienteResponse
    contratos_ativos: int
    total_contratos: int
    total_veiculacoes_mes: int
    ultimo_contrato: Optional[ContratoResumo]


# ============================================
# SCHEMAS: Auth e Usuários
# ============================================

class LoginRequest(BaseModel):
    username: str
    password: str


class UsuarioBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=60)
    nome: str = Field(..., min_length=3, max_length=120)
    role: str = Field(default="operador")
    ativo: bool = True

    @validator("role")
    def validar_role(cls, v):
        if v not in ["admin", "operador"]:
            raise ValueError('Role deve ser "admin" ou "operador"')
        return v


class UsuarioCreate(UsuarioBase):
    password: str = Field(..., min_length=6)


class UsuarioUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=60)
    nome: Optional[str] = Field(None, min_length=3, max_length=120)
    role: Optional[str] = None
    ativo: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)

    @validator("role")
    def validar_role_update(cls, v):
        if v is None:
            return v
        if v not in ["admin", "operador"]:
            raise ValueError('Role deve ser "admin" ou "operador"')
        return v


class UsuarioResponse(UsuarioBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


# ============================================
# SCHEMAS: Respostas Padrão
# ============================================

class MessageResponse(BaseModel):
    """Resposta padrão para operações"""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Resposta de erro"""
    error: str
    detail: Optional[str] = None
    success: bool = False


# ============================================
# SCHEMAS: Filtros e Paginação
# ============================================

class FiltroVeiculacao(BaseModel):
    """Filtros para buscar veiculações"""
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    cliente_id: Optional[int] = None
    contrato_id: Optional[int] = None
    tipo_programa: Optional[str] = None
    processado: Optional[bool] = None


class Paginacao(BaseModel):
    """Parâmetros de paginação"""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=100)


class PaginatedResponse(BaseModel):
    """Resposta paginada genérica"""
    items: List
    total: int
    page: int
    per_page: int
    total_pages: int
