"""
schemas.py - Schemas de Validação

Os schemas definem o formato dos dados que a API aceita e retorna.
O Pydantic valida automaticamente se os dados estão corretos.

Diferença entre Model (models.py) e Schema:
- Model: Representa tabela no banco de dados (SQLAlchemy)
- Schema: Representa dados na API (entrada/saída) (Pydantic)
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime, date
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
    
    @field_validator("status")
    @classmethod
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
    
    model_config = ConfigDict(from_attributes=True)


# ============================================
# SCHEMAS: ContratoItem
# ============================================

class ContratoItemBase(BaseModel):
    """Schema base para item de contrato"""
    tipo_programa: str = Field(..., description="Tipo: musical, esporte, jornal, etc.")
    quantidade_contratada: Optional[int] = Field(None, gt=0, description="Quantidade total de chamadas contratadas")
    quantidade_diaria_meta: Optional[int] = Field(None, gt=0, description="Meta diária de chamadas")
    observacoes: Optional[str] = None

    @model_validator(mode="after")
    def validar_meta_total_ou_diaria(self):
        if not self.quantidade_contratada and not self.quantidade_diaria_meta:
            raise ValueError("Informe quantidade_contratada, quantidade_diaria_meta ou ambas")
        return self


class ContratoItemCreate(ContratoItemBase):
    """Schema para criar item de contrato"""
    pass


class ContratoItemUpdate(BaseModel):
    """Schema para atualizar item de contrato"""
    tipo_programa: Optional[str] = None
    quantidade_contratada: Optional[int] = Field(None, gt=0)
    quantidade_diaria_meta: Optional[int] = Field(None, gt=0)
    observacoes: Optional[str] = None


class ContratoItemResponse(ContratoItemBase):
    """Schema para retornar item de contrato"""
    id: int
    contrato_id: int
    quantidade_executada: int
    percentual_execucao: float
    quantidade_restante: Optional[int]
    
    model_config = ConfigDict(from_attributes=True)


# ============================================
# SCHEMAS: ContratoArquivoMeta
# ============================================

class ContratoArquivoMetaBase(BaseModel):
    arquivo_audio_id: int
    quantidade_meta: int = Field(..., gt=0)
    modo_veiculacao: str = Field(default="fixo", description="fixo ou rodizio")
    ativo: bool = True
    observacoes: Optional[str] = None

    @field_validator("modo_veiculacao")
    @classmethod
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

    @field_validator("modo_veiculacao")
    @classmethod
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

    model_config = ConfigDict(from_attributes=True)


class EmitirNotaFiscalMensalRequest(BaseModel):
    numero_nf: str = Field(..., min_length=1, max_length=50)
    data_emissao_nf: Optional[date] = None
    valor_cobrado: Optional[float] = Field(None, ge=0)
    observacoes: Optional[str] = None


# ============================================
# SCHEMAS: Nota Fiscal
# ============================================

class NotaFiscalBase(BaseModel):
    tipo: str = Field(default="unica", description="unica ou mensal")
    competencia: Optional[date] = Field(
        None,
        description="Primeiro dia do mes quando tipo mensal",
    )
    status: str = Field(default="pendente")
    numero: Optional[str] = Field(None, max_length=50)
    serie: Optional[str] = Field(None, max_length=20)
    data_emissao: Optional[date] = None
    data_pagamento: Optional[date] = None
    valor: Optional[float] = Field(None, ge=0)
    observacoes: Optional[str] = None

    @field_validator("tipo")
    @classmethod
    def validar_tipo_nf(cls, v):
        if v not in ["unica", "mensal"]:
            raise ValueError('tipo deve ser "unica" ou "mensal"')
        return v

    @field_validator("status")
    @classmethod
    def validar_status_nf_crud(cls, v):
        if v not in ["pendente", "emitida", "paga", "cancelada"]:
            raise ValueError('status deve ser "pendente", "emitida", "paga" ou "cancelada"')
        return v

    @model_validator(mode="after")
    def validar_competencia_por_tipo(self):
        if self.tipo == "mensal":
            if self.competencia is None:
                raise ValueError("competencia e obrigatoria para notas mensais")
            if self.competencia.day != 1:
                raise ValueError("competencia deve ser o primeiro dia do mes")
        elif self.competencia is not None:
            raise ValueError("competencia deve ser nula para notas unicas")
        return self


class NotaFiscalCreate(NotaFiscalBase):
    pass


class NotaFiscalUpdate(BaseModel):
    status: Optional[str] = None
    numero: Optional[str] = Field(None, max_length=50)
    serie: Optional[str] = Field(None, max_length=20)
    data_emissao: Optional[date] = None
    data_pagamento: Optional[date] = None
    valor: Optional[float] = Field(None, ge=0)
    observacoes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validar_status_nf_update(cls, v):
        if v is None:
            return v
        if v not in ["pendente", "emitida", "paga", "cancelada"]:
            raise ValueError('status deve ser "pendente", "emitida", "paga" ou "cancelada"')
        return v


class NotaFiscalResponse(NotaFiscalBase):
    id: int
    contrato_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class NotaFiscalListItem(BaseModel):
    id: int
    contrato_id: int
    contrato_numero: str
    cliente_id: int
    cliente_nome: str
    tipo: str
    competencia: Optional[date] = None
    status: str
    numero: Optional[str] = None
    data_emissao: Optional[date] = None
    data_pagamento: Optional[date] = None
    valor: Optional[float] = None
    observacoes: Optional[str] = None
    created_at: datetime


class NotaFiscalListResponse(BaseModel):
    items: List[NotaFiscalListItem]
    total: int
    skip: int
    limit: int


# ============================================
# SCHEMAS: Contrato
# ============================================

class ContratoBase(BaseModel):
    """Schema base para contrato"""
    cliente_id: int
    data_inicio: date
    data_fim: Optional[date] = None
    frequencia: str = Field(default="ambas", description="Frequência: 102.7, 104.7 ou ambas")
    valor_total: Optional[float] = Field(None, ge=0, description="Valor total do contrato")
    status_contrato: str = Field(default="ativo")
    nf_dinamica: str = Field(default="unica", description="unica ou mensal")
    status_nf: str = Field(default="pendente")
    numero_nf: Optional[str] = None
    data_emissao_nf: Optional[date] = None
    observacoes: Optional[str] = None
    
    @field_validator("status_contrato")
    @classmethod
    def validar_status_contrato(cls, v):
        if v not in ['ativo', 'concluído', 'cancelado']:
            raise ValueError('Status inválido')
        return v
    
    @field_validator("status_nf")
    @classmethod
    def validar_status_nf(cls, v):
        if v not in ['pendente', 'emitida', 'paga']:
            raise ValueError('Status NF inválido')
        return v

    @field_validator("nf_dinamica")
    @classmethod
    def validar_nf_dinamica(cls, v):
        if v not in ["unica", "mensal"]:
            raise ValueError('nf_dinamica deve ser "unica" ou "mensal"')
        return v

    @field_validator("frequencia")
    @classmethod
    def validar_frequencia(cls, v):
        if v not in ['102.7', '104.7', 'ambas']:
            raise ValueError('Frequência deve ser "102.7", "104.7" ou "ambas"')
        return v
    
    @model_validator(mode="after")
    def validar_datas(self):
        """Valida que data_fim é maior que data_inicio quando informada."""
        if self.data_fim is None:
            return self
        if self.data_fim < self.data_inicio:
            raise ValueError('Data fim deve ser maior que data início')
        return self


class ContratoCreate(ContratoBase):
    """Schema para criar contrato com seus itens"""
    itens: List[ContratoItemCreate] = Field(..., min_length=1, description="Itens do contrato")
    arquivos_metas: List[ContratoArquivoMetaCreate] = Field(default_factory=list)


class ContratoUpdate(BaseModel):
    """Schema para atualizar contrato"""
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    frequencia: Optional[str] = None
    valor_total: Optional[float] = None
    status_contrato: Optional[str] = None
    nf_dinamica: Optional[str] = None
    status_nf: Optional[str] = None
    numero_nf: Optional[str] = None
    data_emissao_nf: Optional[date] = None
    observacoes: Optional[str] = None

    @field_validator("frequencia")
    @classmethod
    def validar_frequencia_update(cls, v):
        if v is None:
            return v
        if v not in ['102.7', '104.7', 'ambas']:
            raise ValueError('Frequência deve ser "102.7", "104.7" ou "ambas"')
        return v

    @field_validator("nf_dinamica")
    @classmethod
    def validar_nf_dinamica_update(cls, v):
        if v is None:
            return v
        if v not in ["unica", "mensal"]:
            raise ValueError('nf_dinamica deve ser "unica" ou "mensal"')
        return v


class ContratoResponse(ContratoBase):
    """Schema para retornar contrato"""
    id: int
    numero_contrato: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    itens: List[ContratoItemResponse] = []
    arquivos_metas: List[ContratoArquivoMetaResponse] = []
    notas_fiscais: List[NotaFiscalResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


class ContratoResumo(BaseModel):
    """Schema para resumo de contrato (usado em listas)"""
    id: int
    numero_contrato: str
    cliente_id: int
    cliente_nome: str
    data_inicio: date
    data_fim: Optional[date] = None
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
    
    model_config = ConfigDict(from_attributes=True)


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

    @field_validator("frequencia")
    @classmethod
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
    horarios: List[str] = Field(..., min_length=1, description="Lista HH:MM ou HH:MM:SS")
    frequencia: str = Field(..., description='Frequência: 102.7 ou 104.7')
    tipo_programa: Optional[str] = None
    fonte: str = Field(default="obs_manual")

    @field_validator("frequencia")
    @classmethod
    def validar_frequencia_lote(cls, v):
        if v not in ["102.7", "104.7"]:
            raise ValueError('Frequência da veiculação deve ser "102.7" ou "104.7"')
        return v


class VeiculacaoResponse(VeiculacaoBase):
    """Schema para retornar veiculação"""
    id: int
    processado: bool
    contabilizada: bool
    
    model_config = ConfigDict(from_attributes=True)


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

    @field_validator("role")
    @classmethod
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

    @field_validator("role")
    @classmethod
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

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse


class ApiKeyCreateRequest(BaseModel):
    descricao: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Descrição da finalidade da chave (ex: monitor produção).",
    )


class ApiKeyCreateResponse(BaseModel):
    id: int
    descricao: Optional[str] = None
    ativo: bool
    created_at: datetime
    api_key: str


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
