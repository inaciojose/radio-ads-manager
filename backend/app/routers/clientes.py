"""
routers/clientes.py - Endpoints para gerenciar clientes

Este arquivo contém todas as rotas (endpoints) relacionadas a clientes:
- Listar todos os clientes
- Buscar um cliente específico
- Criar novo cliente
- Atualizar cliente
- Deletar cliente
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.auth import ROLE_ADMIN, ROLE_OPERADOR, require_roles
from app.database import get_db
from app import models, schemas


# Criar o router (grupo de rotas relacionadas)
# prefix="/clientes" significa que todas as rotas começam com /clientes
# tags serve para organizar na documentação automática
router = APIRouter(
    prefix="/clientes",
    tags=["Clientes"]
)


# ============================================
# ENDPOINT: Listar todos os clientes
# ============================================

@router.get("/", response_model=List[schemas.ClienteResponse])
def listar_clientes(
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros"),
    status: Optional[str] = Query(None, description="Filtrar por status (ativo/inativo)"),
    busca: Optional[str] = Query(None, description="Buscar por nome ou CNPJ/CPF"),
    db: Session = Depends(get_db)
):
    """
    Lista todos os clientes cadastrados.
    
    Parâmetros:
    - skip: Quantos registros pular (para paginação)
    - limit: Quantos registros retornar (máximo)
    - status: Filtrar por status (opcional)
    - busca: Buscar por nome ou documento (opcional)
    
    Exemplo de uso:
    GET /clientes?skip=0&limit=10&status=ativo
    """
    query = db.query(models.Cliente)
    
    # Aplicar filtros se fornecidos
    if status:
        query = query.filter(models.Cliente.status == status)
    
    if busca:
        # Busca por nome ou CNPJ/CPF (case-insensitive)
        busca_pattern = f"%{busca}%"
        query = query.filter(
            (models.Cliente.nome.ilike(busca_pattern)) |
            (models.Cliente.cnpj_cpf.ilike(busca_pattern))
        )
    
    # Ordenar por nome e aplicar paginação
    clientes = query.order_by(models.Cliente.nome).offset(skip).limit(limit).all()
    
    return clientes


# ============================================
# ENDPOINT: Buscar cliente específico
# ============================================

@router.get("/{cliente_id}", response_model=schemas.ClienteResponse)
def buscar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db)
):
    """
    Busca um cliente específico pelo ID.
    
    Exemplo de uso:
    GET /clientes/1
    """
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente com ID {cliente_id} não encontrado"
        )
    
    return cliente


# ============================================
# ENDPOINT: Criar novo cliente
# ============================================

@router.post("/", response_model=schemas.ClienteResponse, status_code=status.HTTP_201_CREATED)
def criar_cliente(
    cliente: schemas.ClienteCreate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    """
    Cria um novo cliente.
    
    Exemplo de uso:
    POST /clientes
    Body: {
        "nome": "Empresa XYZ",
        "cnpj_cpf": "12.345.678/0001-90",
        "email": "contato@empresa.com",
        "telefone": "(88) 99999-9999"
    }
    """
    # Verificar se já existe cliente com este CNPJ/CPF
    if cliente.cnpj_cpf:
        cliente_existente = db.query(models.Cliente).filter(
            models.Cliente.cnpj_cpf == cliente.cnpj_cpf
        ).first()
        
        if cliente_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Já existe um cliente cadastrado com o CNPJ/CPF: {cliente.cnpj_cpf}"
            )
    
    # Criar novo cliente
    db_cliente = models.Cliente(**cliente.model_dump())
    db.add(db_cliente)
    db.commit()
    db.refresh(db_cliente)  # Atualiza com dados do banco (ID, timestamps, etc.)
    
    return db_cliente


# ============================================
# ENDPOINT: Atualizar cliente
# ============================================

@router.put("/{cliente_id}", response_model=schemas.ClienteResponse)
def atualizar_cliente(
    cliente_id: int,
    cliente_update: schemas.ClienteUpdate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    """
    Atualiza os dados de um cliente.
    
    Exemplo de uso:
    PUT /clientes/1
    Body: {
        "telefone": "(88) 88888-8888",
        "status": "inativo"
    }
    """
    # Buscar cliente
    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    
    if not db_cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente com ID {cliente_id} não encontrado"
        )
    
    # Atualizar apenas os campos fornecidos
    update_data = cliente_update.model_dump(exclude_unset=True)
    
    # Se está atualizando CNPJ/CPF, verificar se não existe outro cliente com ele
    if "cnpj_cpf" in update_data and update_data["cnpj_cpf"]:
        cliente_existente = db.query(models.Cliente).filter(
            models.Cliente.cnpj_cpf == update_data["cnpj_cpf"],
            models.Cliente.id != cliente_id
        ).first()
        
        if cliente_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Já existe outro cliente com o CNPJ/CPF: {update_data['cnpj_cpf']}"
            )
    
    # Aplicar atualizações
    for field, value in update_data.items():
        setattr(db_cliente, field, value)
    
    db.commit()
    db.refresh(db_cliente)
    
    return db_cliente


# ============================================
# ENDPOINT: Deletar cliente
# ============================================

@router.delete("/{cliente_id}", response_model=schemas.MessageResponse)
def deletar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    """
    Deleta um cliente.
    
    ATENÇÃO: Isso também deletará todos os contratos e arquivos relacionados
    (por causa do CASCADE no banco de dados).
    
    Exemplo de uso:
    DELETE /clientes/1
    """
    # Buscar cliente
    db_cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    
    if not db_cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente com ID {cliente_id} não encontrado"
        )
    
    # Verificar se tem contratos ativos
    contratos_ativos = db.query(models.Contrato).filter(
        models.Contrato.cliente_id == cliente_id,
        models.Contrato.status_contrato == "ativo"
    ).count()
    
    if contratos_ativos > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível deletar cliente com {contratos_ativos} contrato(s) ativo(s). Cancele os contratos primeiro."
        )
    
    # Deletar cliente
    db.delete(db_cliente)
    db.commit()
    
    return {
        "message": f"Cliente '{db_cliente.nome}' deletado com sucesso",
        "success": True
    }


# ============================================
# ENDPOINT: Estatísticas do cliente
# ============================================

@router.get("/{cliente_id}/resumo", response_model=schemas.ResumoCliente)
def resumo_cliente(
    cliente_id: int,
    db: Session = Depends(get_db)
):
    """
    Retorna um resumo completo do cliente com estatísticas.
    
    Exemplo de uso:
    GET /clientes/1/resumo
    """
    # Buscar cliente
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente com ID {cliente_id} não encontrado"
        )
    
    # Contar contratos
    total_contratos = db.query(models.Contrato).filter(
        models.Contrato.cliente_id == cliente_id
    ).count()
    
    contratos_ativos = db.query(models.Contrato).filter(
        models.Contrato.cliente_id == cliente_id,
        models.Contrato.status_contrato == "ativo"
    ).count()
    
    # Buscar último contrato
    ultimo_contrato = db.query(models.Contrato).filter(
        models.Contrato.cliente_id == cliente_id
    ).order_by(models.Contrato.created_at.desc()).first()
    
    # Contar veiculações do mês atual
    from datetime import datetime
    primeiro_dia_mes = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    veiculacoes_mes = db.query(models.Veiculacao).join(
        models.ArquivoAudio
    ).filter(
        models.ArquivoAudio.cliente_id == cliente_id,
        models.Veiculacao.data_hora >= primeiro_dia_mes
    ).count()
    
    return {
        "cliente": cliente,
        "contratos_ativos": contratos_ativos,
        "total_contratos": total_contratos,
        "total_veiculacoes_mes": veiculacoes_mes,
        "ultimo_contrato": ultimo_contrato
    }
