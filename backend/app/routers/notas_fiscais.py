"""routers/notas_fiscais.py - Visao global de notas fiscais."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import ROLE_ADMIN, ROLE_OPERADOR, require_roles
from app.database import get_db


router = APIRouter(prefix="/notas-fiscais", tags=["Notas Fiscais"])


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


@router.get("/", response_model=schemas.NotaFiscalListResponse)
def listar_notas_fiscais(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    competencia: Optional[str] = Query(None, description="Filtro YYYY-MM"),
    status_nf: Optional[str] = Query(None, pattern="^(pendente|emitida|paga|cancelada)$"),
    cliente_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    query = (
        db.query(models.NotaFiscal, models.Contrato, models.Cliente)
        .join(models.Contrato, models.NotaFiscal.contrato_id == models.Contrato.id)
        .join(models.Cliente, models.Contrato.cliente_id == models.Cliente.id)
    )

    if competencia:
        competencia_ref = _parse_competencia_yyyy_mm(competencia)
        query = query.filter(models.NotaFiscal.competencia == competencia_ref)

    if status_nf:
        query = query.filter(models.NotaFiscal.status == status_nf)

    if cliente_id:
        query = query.filter(models.Contrato.cliente_id == cliente_id)

    total = query.count()
    rows = (
        query.order_by(
            models.NotaFiscal.competencia.desc(),
            models.NotaFiscal.data_emissao.desc(),
            models.NotaFiscal.created_at.desc(),
            models.NotaFiscal.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = [
        schemas.NotaFiscalListItem(
            id=nota.id,
            contrato_id=contrato.id,
            contrato_numero=contrato.numero_contrato or f"#{contrato.id}",
            cliente_id=cliente.id,
            cliente_nome=cliente.nome,
            tipo=nota.tipo,
            competencia=nota.competencia,
            status=nota.status,
            numero=nota.numero,
            data_emissao=nota.data_emissao,
            data_pagamento=nota.data_pagamento,
            numero_recibo=nota.numero_recibo,
            valor_bruto=nota.valor_bruto,
            valor_liquido=nota.valor_liquido,
            valor_pago=nota.valor_pago,
            forma_pagamento=nota.forma_pagamento,
            campanha_agentes=nota.campanha_agentes,
            observacoes=nota.observacoes,
            created_at=nota.created_at,
        )
        for nota, contrato, cliente in rows
    ]

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }
