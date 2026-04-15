"""
routers/clientes.py - Endpoints para gerenciar clientes

Este arquivo contém todas as rotas (endpoints) relacionadas a clientes:
- Listar todos os clientes
- Buscar um cliente específico
- Criar novo cliente
- Atualizar cliente
- Deletar cliente
"""

from io import BytesIO
from typing import List, Optional
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.auth import ROLE_ADMIN, ROLE_OPERADOR, require_roles
from app.database import get_db
from app import models, schemas
from app.services.export_service import build_excel, build_pdf
from app.services import audit_service as audit


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
    codigo_chamada: Optional[int] = Query(None, description="Filtrar por código de chamada"),
    db: Session = Depends(get_db)
):
    """Lista todos os clientes cadastrados."""
    query = db.query(models.Cliente)

    if status:
        query = query.filter(models.Cliente.status == status)

    if busca:
        busca_pattern = f"%{busca}%"
        query = query.filter(
            (models.Cliente.nome.ilike(busca_pattern)) |
            (models.Cliente.cnpj_cpf.ilike(busca_pattern))
        )

    if codigo_chamada is not None:
        query = query.filter(models.Cliente.codigo_chamada == codigo_chamada)

    clientes = query.order_by(models.Cliente.nome).offset(skip).limit(limit).all()
    return clientes


# ============================================
# ENDPOINT: Buscar cliente específico
# ============================================

_EXPORT_HEADERS_CLIENTES = ["Nome", "CNPJ/CPF", "Email", "Telefone", "Status"]


def _cliente_export_row(c) -> list:
    return [
        c.nome or "-",
        c.cnpj_cpf or "-",
        c.email or "-",
        c.telefone or "-",
        c.status or "-",
    ]


def _build_clientes_query(db: Session, status: Optional[str], busca: Optional[str]):
    query = db.query(models.Cliente)
    if status:
        query = query.filter(models.Cliente.status == status)
    if busca:
        p = f"%{busca}%"
        query = query.filter(
            (models.Cliente.nome.ilike(p)) | (models.Cliente.cnpj_cpf.ilike(p))
        )
    return query.order_by(models.Cliente.nome)


@router.get("/exportar/excel")
def exportar_clientes_excel(
    status: Optional[str] = Query(None),
    busca: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    clientes = _build_clientes_query(db, status, busca).all()
    data = [_cliente_export_row(c) for c in clientes]
    content = build_excel(_EXPORT_HEADERS_CLIENTES, data, sheet_name="Clientes")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=clientes.xlsx"},
    )


@router.get("/exportar/pdf")
def exportar_clientes_pdf(
    status: Optional[str] = Query(None),
    busca: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    clientes = _build_clientes_query(db, status, busca).all()
    data = [_cliente_export_row(c) for c in clientes]

    partes = []
    if status:
        partes.append(f"Status: {status.capitalize()}")
    if busca:
        partes.append(f"Busca: {busca}")
    filtros_texto = " | ".join(partes) if partes else None

    content = build_pdf(
        _EXPORT_HEADERS_CLIENTES,
        data,
        title="Relatório de Clientes",
        username=current_user.nome,
        filtros_texto=filtros_texto,
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=clientes.pdf"},
    )


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
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
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

    # Verificar unicidade do codigo_chamada
    if cliente.codigo_chamada is not None:
        existente_codigo = db.query(models.Cliente).filter(
            models.Cliente.codigo_chamada == cliente.codigo_chamada
        ).first()
        if existente_codigo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Já existe um cliente com o código de chamada {cliente.codigo_chamada}"
            )

    # Criar novo cliente
    db_cliente = models.Cliente(**cliente.model_dump())
    db.add(db_cliente)
    db.flush()
    audit.registrar(
        db, current_user.id, current_user.nome,
        audit.AREA_CLIENTES, audit.ACAO_CRIADO,
        db_cliente.id, db_cliente.nome,
    )
    db.commit()
    db.refresh(db_cliente)

    return db_cliente


# ============================================
# ENDPOINT: Atualizar cliente
# ============================================

@router.put("/{cliente_id}", response_model=schemas.ClienteResponse)
def atualizar_cliente(
    cliente_id: int,
    cliente_update: schemas.ClienteUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
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

    # Bloquear inativação de cliente com contratos ativos
    if update_data.get("status") == "inativo" and db_cliente.status != "inativo":
        contratos_ativos = db.query(models.Contrato).filter(
            models.Contrato.cliente_id == cliente_id,
            models.Contrato.status_contrato == "ativo",
        ).all()
        if contratos_ativos:
            numeros = ", ".join(c.numero_contrato or f"#{c.id}" for c in contratos_ativos)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Não é possível inativar este cliente pois possui contrato(s) ativo(s): {numeros}",
            )

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

    # Se está atualizando codigo_chamada, verificar unicidade
    if "codigo_chamada" in update_data and update_data["codigo_chamada"] is not None:
        existente_codigo = db.query(models.Cliente).filter(
            models.Cliente.codigo_chamada == update_data["codigo_chamada"],
            models.Cliente.id != cliente_id
        ).first()
        if existente_codigo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Já existe outro cliente com o código de chamada {update_data['codigo_chamada']}"
            )

    # Aplicar atualizações
    for field, value in update_data.items():
        setattr(db_cliente, field, value)

    acao = audit.ACAO_INATIVADO if update_data.get("status") == "inativo" else audit.ACAO_EDITADO
    audit.registrar(
        db, current_user.id, current_user.nome,
        audit.AREA_CLIENTES, acao,
        db_cliente.id, db_cliente.nome,
        detalhe=", ".join(f"{k}={v}" for k, v in update_data.items()) or None,
    )
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
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
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
    
    nome_cliente = db_cliente.nome
    audit.registrar(
        db, current_user.id, current_user.nome,
        audit.AREA_CLIENTES, audit.ACAO_EXCLUIDO,
        cliente_id, nome_cliente,
    )
    db.delete(db_cliente)
    db.commit()

    return {
        "message": f"Cliente '{nome_cliente}' deletado com sucesso",
        "success": True
    }


# ============================================
# ENDPOINT: Estatísticas do cliente
# ============================================

@router.get("/{cliente_id}/progresso", response_model=schemas.ClienteProgressoResponse)
def progresso_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
):
    """
    Retorna o progresso de veiculações do cliente para o dia atual e o mês corrente.

    - veiculacoes_hoje: contagem direta de veiculacoes com cliente_id = X e data = hoje
    - meta_diaria_total: soma das quantidade_diaria_meta dos itens de contratos ativos
    - meta_total: soma das quantidade_contratada dos itens de contratos ativos
    - tem_alerta: True quando veiculacoes_hoje < meta_diaria_total (e meta existe)
    """
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Cliente com ID {cliente_id} não encontrado")

    hoje = date.today()
    inicio_hoje = datetime.combine(hoje, datetime.min.time())
    fim_hoje = datetime.combine(hoje, datetime.max.time())
    primeiro_dia_mes = hoje.replace(day=1)
    inicio_mes = datetime.combine(primeiro_dia_mes, datetime.min.time())

    # Contar veiculações do dia vinculadas ao cliente (via cliente_id direto)
    veiculacoes_hoje = db.query(func.count(models.Veiculacao.id)).filter(
        models.Veiculacao.cliente_id == cliente_id,
        models.Veiculacao.data_hora.between(inicio_hoje, fim_hoje),
    ).scalar() or 0

    # Contar veiculações do mês
    veiculacoes_mes = db.query(func.count(models.Veiculacao.id)).filter(
        models.Veiculacao.cliente_id == cliente_id,
        models.Veiculacao.data_hora >= inicio_mes,
    ).scalar() or 0

    # Somar metas dos contratos ativos do cliente
    contratos_ativos = db.query(models.Contrato).filter(
        models.Contrato.cliente_id == cliente_id,
        models.Contrato.status_contrato == "ativo",
    ).all()

    meta_diaria_total: Optional[int] = None
    meta_total: Optional[int] = None

    for contrato in contratos_ativos:
        for item in contrato.itens:
            if item.quantidade_diaria_meta is not None:
                meta_diaria_total = (meta_diaria_total or 0) + item.quantidade_diaria_meta
            if item.quantidade_contratada is not None:
                meta_total = (meta_total or 0) + item.quantidade_contratada

    tem_alerta = (
        meta_diaria_total is not None and veiculacoes_hoje < meta_diaria_total
    )

    return schemas.ClienteProgressoResponse(
        cliente_id=cliente_id,
        cliente_nome=cliente.nome,
        codigo_chamada=cliente.codigo_chamada,
        veiculacoes_hoje=veiculacoes_hoje,
        meta_diaria_total=meta_diaria_total,
        meta_total=meta_total,
        veiculacoes_mes=veiculacoes_mes,
        tem_alerta=tem_alerta,
    )


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
