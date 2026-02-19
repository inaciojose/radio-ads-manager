"""
routers/contratos.py - Endpoints para gerenciar contratos.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import ROLE_ADMIN, ROLE_OPERADOR, require_roles
from app import models, schemas
from app.database import get_db
from app.services.contratos_service import (
    NumeroContratoConflictError,
    criar_contrato_com_itens,
)


router = APIRouter(
    prefix="/contratos",
    tags=["Contratos"],
)


def _parse_competencia_yyyy_mm(valor: str) -> date:
    raw = (valor or "").strip()
    if len(raw) != 7 or raw[4] != "-":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Competencia invalida. Use o formato YYYY-MM.",
        )
    try:
        ano = int(raw[:4])
        mes = int(raw[5:7])
        return date(ano, mes, 1)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Competencia invalida. Use o formato YYYY-MM.",
        )


def _validar_competencia_no_periodo_contrato(
    contrato: models.Contrato,
    competencia: date,
) -> None:
    inicio_comp = date(competencia.year, competencia.month, 1)
    if contrato.data_inicio:
        inicio_contrato = date(contrato.data_inicio.year, contrato.data_inicio.month, 1)
        if inicio_comp < inicio_contrato:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Competencia anterior ao inicio do contrato.",
            )
    if contrato.data_fim:
        fim_contrato = date(contrato.data_fim.year, contrato.data_fim.month, 1)
        if inicio_comp > fim_contrato:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Competencia posterior ao fim do contrato.",
            )


def _validar_arquivo_do_cliente(db: Session, cliente_id: int, arquivo_audio_id: int):
    arquivo = db.query(models.ArquivoAudio).filter(
        models.ArquivoAudio.id == arquivo_audio_id
    ).first()
    if not arquivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo com ID {arquivo_audio_id} nao encontrado",
        )
    if arquivo.cliente_id != cliente_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Arquivo {arquivo_audio_id} nao pertence ao cliente do contrato",
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
            models.Contrato.data_fim.isnot(None),
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


@router.get("/resumo/meta-diaria-hoje")
def resumo_meta_diaria_hoje(db: Session = Depends(get_db)):
    hoje = date.today()
    inicio_dia = datetime.combine(hoje, datetime.min.time())
    fim_dia = datetime.combine(hoje, datetime.max.time())

    contratos_ativos = db.query(models.Contrato).filter(
        models.Contrato.status_contrato == "ativo",
        models.Contrato.data_inicio <= hoje,
        or_(
            models.Contrato.data_fim.is_(None),
            models.Contrato.data_fim >= hoje,
        ),
    ).all()

    if not contratos_ativos:
        return {
            "data": hoje,
            "meta_diaria_total": 0,
            "executadas_hoje": 0,
            "percentual_cumprimento": 0.0,
        }

    contrato_ids = {c.id for c in contratos_ativos}
    itens_por_contrato = {c.id: (c.itens or []) for c in contratos_ativos}
    meta_diaria_total = sum(
        (item.quantidade_diaria_meta or 0)
        for c in contratos_ativos
        for item in (c.itens or [])
    )

    metas_arquivo_ativas = db.query(
        models.ContratoArquivoMeta.contrato_id,
        models.ContratoArquivoMeta.arquivo_audio_id,
    ).filter(
        models.ContratoArquivoMeta.contrato_id.in_(contrato_ids),
        models.ContratoArquivoMeta.ativo == True,  # noqa: E712
    ).all()
    pares_meta_arquivo = {(contrato_id, arquivo_id) for contrato_id, arquivo_id in metas_arquivo_ativas}

    veiculacoes_hoje = db.query(models.Veiculacao).filter(
        models.Veiculacao.data_hora.between(inicio_dia, fim_dia),
        models.Veiculacao.contabilizada == True,  # noqa: E712
        models.Veiculacao.contrato_id.in_(contrato_ids),
    ).all()

    executadas_hoje = 0
    for veiculacao in veiculacoes_hoje:
        if (veiculacao.contrato_id, veiculacao.arquivo_audio_id) in pares_meta_arquivo:
            continue

        item_contabilizado = None
        itens_contrato = itens_por_contrato.get(veiculacao.contrato_id, [])
        if veiculacao.tipo_programa:
            item_contabilizado = next(
                (i for i in itens_contrato if i.tipo_programa == veiculacao.tipo_programa),
                None,
            )
            if not item_contabilizado and itens_contrato:
                item_contabilizado = itens_contrato[0]

        if item_contabilizado and (item_contabilizado.quantidade_diaria_meta or 0) > 0:
            executadas_hoje += 1

    percentual = 0.0
    if meta_diaria_total > 0:
        percentual = round((executadas_hoje / meta_diaria_total) * 100, 2)

    return {
        "data": hoje,
        "meta_diaria_total": meta_diaria_total,
        "executadas_hoje": executadas_hoje,
        "percentual_cumprimento": percentual,
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
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == contrato.cliente_id).first()
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente com ID {contrato.cliente_id} nao encontrado",
        )

    for meta in contrato.arquivos_metas:
        _validar_arquivo_do_cliente(db, contrato.cliente_id, meta.arquivo_audio_id)

    try:
        return criar_contrato_com_itens(db, contrato)
    except NumeroContratoConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflito ao gerar numero do contrato. Tente novamente.",
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dados invalidos para criacao do contrato.",
        )


@router.post("/{contrato_id}/itens", response_model=schemas.ContratoItemResponse, status_code=status.HTTP_201_CREATED)
def adicionar_item_contrato(
    contrato_id: int,
    item: schemas.ContratoItemCreate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
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
        quantidade_diaria_meta=item.quantidade_diaria_meta,
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
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
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

    if not db_item.quantidade_contratada and not db_item.quantidade_diaria_meta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Item precisa ter quantidade_contratada, quantidade_diaria_meta ou ambas",
        )

    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/{contrato_id}/arquivos-metas", response_model=List[schemas.ContratoArquivoMetaResponse])
def listar_arquivos_metas_contrato(
    contrato_id: int,
    db: Session = Depends(get_db),
):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )
    return (
        db.query(models.ContratoArquivoMeta)
        .filter(models.ContratoArquivoMeta.contrato_id == contrato_id)
        .order_by(models.ContratoArquivoMeta.id.asc())
        .all()
    )


@router.post(
    "/{contrato_id}/arquivos-metas",
    response_model=schemas.ContratoArquivoMetaResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_arquivo_meta_contrato(
    contrato_id: int,
    meta: schemas.ContratoArquivoMetaCreate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    _validar_arquivo_do_cliente(db, contrato.cliente_id, meta.arquivo_audio_id)
    db_meta = models.ContratoArquivoMeta(
        contrato_id=contrato_id,
        arquivo_audio_id=meta.arquivo_audio_id,
        quantidade_meta=meta.quantidade_meta,
        modo_veiculacao=meta.modo_veiculacao,
        ativo=meta.ativo,
        observacoes=meta.observacoes,
    )
    db.add(db_meta)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ja existe meta para este arquivo neste contrato",
        )
    db.refresh(db_meta)
    return db_meta


@router.put(
    "/{contrato_id}/arquivos-metas/{meta_id}",
    response_model=schemas.ContratoArquivoMetaResponse,
)
def atualizar_arquivo_meta_contrato(
    contrato_id: int,
    meta_id: int,
    meta_update: schemas.ContratoArquivoMetaUpdate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    db_meta = db.query(models.ContratoArquivoMeta).filter(
        models.ContratoArquivoMeta.id == meta_id,
        models.ContratoArquivoMeta.contrato_id == contrato_id,
    ).first()
    if not db_meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meta {meta_id} do contrato {contrato_id} nao encontrada",
        )

    update_data = meta_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_meta, field, value)

    db.commit()
    db.refresh(db_meta)
    return db_meta


@router.delete(
    "/{contrato_id}/arquivos-metas/{meta_id}",
    response_model=schemas.MessageResponse,
)
def deletar_arquivo_meta_contrato(
    contrato_id: int,
    meta_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    db_meta = db.query(models.ContratoArquivoMeta).filter(
        models.ContratoArquivoMeta.id == meta_id,
        models.ContratoArquivoMeta.contrato_id == contrato_id,
    ).first()
    if not db_meta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meta {meta_id} do contrato {contrato_id} nao encontrada",
        )

    db.delete(db_meta)
    db.commit()
    return {
        "message": f"Meta de arquivo {meta_id} removida com sucesso",
        "success": True,
    }


@router.put("/{contrato_id}", response_model=schemas.ContratoResponse)
def atualizar_contrato(
    contrato_id: int,
    contrato_update: schemas.ContratoUpdate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
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
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
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


@router.get(
    "/{contrato_id}/faturamentos",
    response_model=List[schemas.ContratoFaturamentoMensalResponse],
)
def listar_faturamentos_mensais_contrato(
    contrato_id: int,
    competencia: Optional[str] = Query(None, description="Filtro YYYY-MM"),
    status_nf: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    query = db.query(models.ContratoFaturamentoMensal).filter(
        models.ContratoFaturamentoMensal.contrato_id == contrato_id
    )

    if competencia:
        competencia_ref = _parse_competencia_yyyy_mm(competencia)
        query = query.filter(models.ContratoFaturamentoMensal.competencia == competencia_ref)

    if status_nf:
        query = query.filter(models.ContratoFaturamentoMensal.status_nf == status_nf)

    return query.order_by(models.ContratoFaturamentoMensal.competencia.desc()).all()


@router.post(
    "/{contrato_id}/faturamentos",
    response_model=schemas.ContratoFaturamentoMensalResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_faturamento_mensal_contrato(
    contrato_id: int,
    payload: schemas.ContratoFaturamentoMensalCreate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    _validar_competencia_no_periodo_contrato(contrato, payload.competencia)

    faturamento = models.ContratoFaturamentoMensal(
        contrato_id=contrato_id,
        competencia=payload.competencia,
        status_nf=payload.status_nf,
        numero_nf=payload.numero_nf,
        data_emissao_nf=payload.data_emissao_nf,
        data_pagamento_nf=payload.data_pagamento_nf,
        valor_cobrado=payload.valor_cobrado,
        observacoes=payload.observacoes,
    )
    db.add(faturamento)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ja existe faturamento para essa competencia neste contrato.",
        )
    db.refresh(faturamento)
    return faturamento


@router.post(
    "/{contrato_id}/faturamentos/{competencia}/emitir",
    response_model=schemas.ContratoFaturamentoMensalResponse,
)
def emitir_nota_fiscal_mensal_contrato(
    contrato_id: int,
    competencia: str,
    payload: schemas.EmitirNotaFiscalMensalRequest,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    competencia_ref = _parse_competencia_yyyy_mm(competencia)
    _validar_competencia_no_periodo_contrato(contrato, competencia_ref)

    faturamento = db.query(models.ContratoFaturamentoMensal).filter(
        models.ContratoFaturamentoMensal.contrato_id == contrato_id,
        models.ContratoFaturamentoMensal.competencia == competencia_ref,
    ).first()

    if not faturamento:
        faturamento = models.ContratoFaturamentoMensal(
            contrato_id=contrato_id,
            competencia=competencia_ref,
            status_nf="pendente",
        )
        db.add(faturamento)
        db.flush()

    faturamento.status_nf = "emitida"
    faturamento.numero_nf = payload.numero_nf
    faturamento.data_emissao_nf = payload.data_emissao_nf or date.today()
    if payload.valor_cobrado is not None:
        faturamento.valor_cobrado = payload.valor_cobrado
    if payload.observacoes is not None:
        faturamento.observacoes = payload.observacoes

    db.commit()
    db.refresh(faturamento)
    return faturamento


@router.patch(
    "/faturamentos/{faturamento_id}",
    response_model=schemas.ContratoFaturamentoMensalResponse,
)
def atualizar_faturamento_mensal(
    faturamento_id: int,
    payload: schemas.ContratoFaturamentoMensalUpdate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    faturamento = db.query(models.ContratoFaturamentoMensal).filter(
        models.ContratoFaturamentoMensal.id == faturamento_id
    ).first()
    if not faturamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Faturamento mensal com ID {faturamento_id} nao encontrado",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(faturamento, field, value)

    db.commit()
    db.refresh(faturamento)
    return faturamento


@router.delete("/{contrato_id}", response_model=schemas.MessageResponse)
def deletar_contrato(
    contrato_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
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
