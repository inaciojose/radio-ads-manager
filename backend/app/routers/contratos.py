"""
routers/contratos.py - Endpoints para gerenciar contratos.
"""

from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services.contratos_service import criar_contrato_com_itens


router = APIRouter(
    prefix="/contratos",
    tags=["Contratos"],
)


@router.get("/", response_model=List[schemas.ContratoResponse])
def listar_contratos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    cliente_id: Optional[int] = Query(None),
    status_contrato: Optional[str] = Query(None),
    status_nf: Optional[str] = Query(None),
    frequencia: Optional[str] = Query(None),
    busca: Optional[str] = Query(None, description="Busca por número de contrato ou cliente"),
    db: Session = Depends(get_db),
):
    query = db.query(models.Contrato)

    if cliente_id:
        query = query.filter(models.Contrato.cliente_id == cliente_id)
    if status_contrato:
        query = query.filter(models.Contrato.status_contrato == status_contrato)
    if status_nf:
        query = query.filter(models.Contrato.status_nf == status_nf)
    if frequencia:
        query = query.filter(models.Contrato.frequencia == frequencia)
    if busca:
        pattern = f"%{busca}%"
        query = query.join(models.Cliente).filter(
            or_(
                models.Contrato.numero_contrato.ilike(pattern),
                models.Cliente.nome.ilike(pattern),
                models.Cliente.cnpj_cpf.ilike(pattern),
            )
        )

    return (
        query.order_by(models.Contrato.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/resumo/estatisticas")
def estatisticas_contratos(db: Session = Depends(get_db)):
    hoje = date.today()
    daqui_30_dias = hoje + timedelta(days=30)

    total_contratos = db.query(models.Contrato).count()
    contratos_ativos = db.query(models.Contrato).filter(models.Contrato.status_contrato == "ativo").count()
    notas_fiscais_pendentes = db.query(models.Contrato).filter(models.Contrato.status_nf == "pendente").count()
    vencendo_30_dias = (
        db.query(models.Contrato)
        .filter(
            models.Contrato.status_contrato == "ativo",
            models.Contrato.data_fim >= hoje,
            models.Contrato.data_fim <= daqui_30_dias,
        )
        .count()
    )
    valor_total_ativos = (
        db.query(func.coalesce(func.sum(models.Contrato.valor_total), 0))
        .filter(models.Contrato.status_contrato == "ativo")
        .scalar()
        or 0
    )

    return {
        "total_contratos": total_contratos,
        "contratos_ativos": contratos_ativos,
        "notas_fiscais_pendentes": notas_fiscais_pendentes,
        "vencendo_30_dias": vencendo_30_dias,
        "valor_total_ativos": float(valor_total_ativos),
    }


@router.get("/cliente/{cliente_id}/resumo")
def resumo_cliente_contratos(
    cliente_id: int,
    db: Session = Depends(get_db),
):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente com ID {cliente_id} nao encontrado",
        )

    contratos = (
        db.query(models.Contrato)
        .filter(models.Contrato.cliente_id == cliente_id)
        .order_by(models.Contrato.created_at.desc())
        .all()
    )
    contratos_ativos = len([c for c in contratos if c.status_contrato == "ativo"])

    chamadas_contratadas = 0
    chamadas_executadas = 0
    for contrato in contratos:
        for item in contrato.itens:
            chamadas_contratadas += item.quantidade_contratada or 0
            chamadas_executadas += item.quantidade_executada or 0

    percentual = 0.0
    if chamadas_contratadas > 0:
        percentual = round((chamadas_executadas / chamadas_contratadas) * 100, 2)

    contratos_serializados = [
        {
            "id": c.id,
            "numero_contrato": c.numero_contrato,
            "data_inicio": c.data_inicio,
            "data_fim": c.data_fim,
            "frequencia": c.frequencia,
            "status_contrato": c.status_contrato,
            "status_nf": c.status_nf,
        }
        for c in contratos
    ]

    return {
        "cliente_id": cliente_id,
        "cliente_nome": cliente.nome,
        "total_contratos": len(contratos),
        "contratos_ativos": contratos_ativos,
        "chamadas_contratadas": chamadas_contratadas,
        "chamadas_executadas": chamadas_executadas,
        "percentual_conclusao": percentual,
        "contratos": contratos_serializados,
    }


@router.get("/{contrato_id}", response_model=schemas.ContratoResponse)
def buscar_contrato(
    contrato_id: int,
    db: Session = Depends(get_db),
):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )
    return contrato


@router.post("/", response_model=schemas.ContratoResponse, status_code=status.HTTP_201_CREATED)
def criar_contrato(
    contrato: schemas.ContratoCreate,
    db: Session = Depends(get_db),
):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == contrato.cliente_id).first()
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente com ID {contrato.cliente_id} nao encontrado",
        )

    return criar_contrato_com_itens(db, contrato)


@router.post("/{contrato_id}/itens", response_model=schemas.ContratoItemResponse, status_code=status.HTTP_201_CREATED)
def adicionar_item_contrato(
    contrato_id: int,
    item: schemas.ContratoItemCreate,
    db: Session = Depends(get_db),
):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    db_item = models.ContratoItem(
        contrato_id=contrato_id,
        tipo_programa=item.tipo_programa,
        quantidade_contratada=item.quantidade_contratada,
        observacoes=item.observacoes,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.put(
    "/{contrato_id}/itens/{item_id}",
    response_model=schemas.ContratoItemResponse,
)
def atualizar_item_contrato(
    contrato_id: int,
    item_id: int,
    item_update: schemas.ContratoItemUpdate,
    db: Session = Depends(get_db),
):
    db_item = db.query(models.ContratoItem).filter(
        models.ContratoItem.id == item_id,
        models.ContratoItem.contrato_id == contrato_id,
    ).first()
    if not db_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} do contrato {contrato_id} nao encontrado",
        )

    update_data = item_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)

    db.commit()
    db.refresh(db_item)
    return db_item


@router.put("/{contrato_id}", response_model=schemas.ContratoResponse)
def atualizar_contrato(
    contrato_id: int,
    contrato_update: schemas.ContratoUpdate,
    db: Session = Depends(get_db),
):
    db_contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not db_contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    update_data = contrato_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_contrato, field, value)

    db.commit()
    db.refresh(db_contrato)
    return db_contrato


@router.patch("/{contrato_id}/nota-fiscal")
def atualizar_nota_fiscal(
    contrato_id: int,
    status_nf: str = Query(..., pattern="^(pendente|emitida|paga)$"),
    numero_nf: Optional[str] = Query(None),
    data_emissao: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    db_contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not db_contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    db_contrato.status_nf = status_nf
    db_contrato.numero_nf = numero_nf
    db_contrato.data_emissao_nf = data_emissao

    db.commit()
    db.refresh(db_contrato)

    return {
        "message": f"Nota fiscal do contrato {db_contrato.numero_contrato} atualizada",
        "success": True,
        "contrato": {
            "id": db_contrato.id,
            "numero_contrato": db_contrato.numero_contrato,
            "status_nf": db_contrato.status_nf,
            "numero_nf": db_contrato.numero_nf,
            "data_emissao_nf": db_contrato.data_emissao_nf,
        },
    }


@router.delete("/{contrato_id}", response_model=schemas.MessageResponse)
def deletar_contrato(
    contrato_id: int,
    db: Session = Depends(get_db),
):
    db_contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not db_contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    db.delete(db_contrato)
    db.commit()
    return {
        "message": f"Contrato '{db_contrato.numero_contrato}' deletado com sucesso",
        "success": True,
    }
