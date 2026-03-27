"""routers/comissoes.py - Visão de comissões por responsável."""

from datetime import date
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import ROLE_ADMIN, ROLE_OPERADOR, require_roles
from app.database import get_db
from app.services.export_service import build_excel, build_pdf, make_horizontal_bar_chart

router = APIRouter(prefix="/comissoes", tags=["Comissões"])


def _parse_mes(valor: str) -> date:
    raw = (valor or "").strip()
    if len(raw) != 7 or raw[4] != "-":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parâmetro 'mes' inválido. Use o formato YYYY-MM.",
        )
    try:
        ano = int(raw[:4])
        mes = int(raw[5:7])
        return date(ano, mes, 1)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parâmetro 'mes' inválido. Use o formato YYYY-MM.",
        )


def _next_month(first: date) -> date:
    if first.month == 12:
        return date(first.year + 1, 1, 1)
    return date(first.year, first.month + 1, 1)


def _nf_mes_filter(first_of_month: date):
    """Filtro SQLAlchemy: NFs pagas no mês informado."""
    first_of_next = _next_month(first_of_month)
    return and_(
        models.NotaFiscal.status == "paga",
        or_(
            and_(
                models.NotaFiscal.tipo == "mensal",
                models.NotaFiscal.competencia == first_of_month,
            ),
            and_(
                models.NotaFiscal.tipo == "unica",
                models.NotaFiscal.data_pagamento >= first_of_month,
                models.NotaFiscal.data_pagamento < first_of_next,
            ),
        ),
    )


@router.get("/", response_model=List[schemas.ComissaoResumoItem])
def visao_geral_comissoes(
    mes: str = Query(..., description="Mês no formato YYYY-MM"),
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    first_of_month = _parse_mes(mes)

    rows = (
        db.query(
            models.Responsavel.id,
            models.Responsavel.nome,
            models.Comissionamento.percentagem,
            models.NotaFiscal.valor_liquido,
        )
        .join(models.Comissionamento, models.Responsavel.id == models.Comissionamento.responsavel_id)
        .join(models.Contrato, models.Comissionamento.contrato_id == models.Contrato.id)
        .join(models.NotaFiscal, models.NotaFiscal.contrato_id == models.Contrato.id)
        .filter(_nf_mes_filter(first_of_month))
        .all()
    )

    totais: dict[int, dict] = {}
    for resp_id, resp_nome, perc, valor in rows:
        if perc is not None and valor is not None:
            comissao = valor * perc / 100
        else:
            comissao = 0.0
        if resp_id not in totais:
            totais[resp_id] = {"nome": resp_nome, "total": 0.0}
        totais[resp_id]["total"] += comissao

    return [
        schemas.ComissaoResumoItem(
            responsavel_id=rid,
            responsavel_nome=data["nome"],
            total_comissao=round(data["total"], 2),
        )
        for rid, data in sorted(totais.items(), key=lambda x: x[1]["total"], reverse=True)
        if data["total"] > 0
    ]


_MESES_PT_COM = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                 "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

_EXPORT_HEADERS_COMISSOES = ["Responsável", "Total de Comissão"]


def _fmt_brl_com(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _compute_comissoes(db: Session, first_of_month: date) -> list:
    """Retorna lista de dicts {responsavel_id, nome, total} ordenada por total desc."""
    rows = (
        db.query(
            models.Responsavel.id,
            models.Responsavel.nome,
            models.Comissionamento.percentagem,
            models.NotaFiscal.valor_liquido,
        )
        .join(models.Comissionamento, models.Responsavel.id == models.Comissionamento.responsavel_id)
        .join(models.Contrato, models.Comissionamento.contrato_id == models.Contrato.id)
        .join(models.NotaFiscal, models.NotaFiscal.contrato_id == models.Contrato.id)
        .filter(_nf_mes_filter(first_of_month))
        .all()
    )
    totais: dict = {}
    for resp_id, resp_nome, perc, valor in rows:
        if perc is not None and valor is not None:
            comissao = valor * perc / 100
        else:
            comissao = 0.0
        if resp_id not in totais:
            totais[resp_id] = {"nome": resp_nome, "total": 0.0}
        totais[resp_id]["total"] += comissao
    return [
        {"responsavel_id": rid, "nome": d["nome"], "total": round(d["total"], 2)}
        for rid, d in sorted(totais.items(), key=lambda x: x[1]["total"], reverse=True)
        if d["total"] > 0
    ]


@router.get("/exportar/excel")
def exportar_comissoes_excel(
    mes: str = Query(..., description="Mês no formato YYYY-MM"),
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    first_of_month = _parse_mes(mes)
    items = _compute_comissoes(db, first_of_month)
    data = [[item["nome"], _fmt_brl_com(item["total"])] for item in items]
    content = build_excel(_EXPORT_HEADERS_COMISSOES, data, sheet_name="Comissões")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=comissoes.xlsx"},
    )


@router.get("/exportar/pdf")
def exportar_comissoes_pdf(
    mes: str = Query(..., description="Mês no formato YYYY-MM"),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    first_of_month = _parse_mes(mes)
    items = _compute_comissoes(db, first_of_month)
    data = [[item["nome"], _fmt_brl_com(item["total"])] for item in items]

    ano, m = mes.split("-")
    mes_label = f"{_MESES_PT_COM[int(m) - 1]}/{ano}"
    filtros_texto = f"Mês: {mes_label}"

    pre_content = []
    if items:
        h = max(150, 30 * len(items) + 40)
        chart = make_horizontal_bar_chart(
            [item["total"] for item in items],
            [item["nome"] for item in items],
            title=f"Comissões por Responsável — {mes_label}",
            width=750,
            height=h,
        )
        pre_content.append(chart)

    content = build_pdf(
        _EXPORT_HEADERS_COMISSOES,
        data,
        title="Relatório de Comissões",
        username=current_user.nome,
        filtros_texto=filtros_texto,
        pre_content=pre_content,
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=comissoes.pdf"},
    )


@router.get("/{responsavel_id}", response_model=schemas.ComissaoDetalheResponse)
def detalhe_comissao_responsavel(
    responsavel_id: int,
    mes: str = Query(..., description="Mês no formato YYYY-MM"),
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    first_of_month = _parse_mes(mes)

    responsavel = (
        db.query(models.Responsavel)
        .filter(models.Responsavel.id == responsavel_id)
        .first()
    )
    if not responsavel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Responsável não encontrado")

    rows = (
        db.query(
            models.Contrato.id,
            models.Contrato.numero_contrato,
            models.Cliente.nome,
            models.Comissionamento.percentagem,
            models.NotaFiscal.valor_liquido,
        )
        .join(models.Comissionamento, models.Comissionamento.contrato_id == models.Contrato.id)
        .join(models.Cliente, models.Contrato.cliente_id == models.Cliente.id)
        .join(models.NotaFiscal, models.NotaFiscal.contrato_id == models.Contrato.id)
        .filter(models.Comissionamento.responsavel_id == responsavel_id)
        .filter(_nf_mes_filter(first_of_month))
        .all()
    )

    contratos = []
    total = 0.0
    for contrato_id, numero_contrato, cliente_nome, perc, valor in rows:
        valor_comissao = round(valor * perc / 100, 2) if perc is not None and valor is not None else None
        if valor_comissao:
            total += valor_comissao
        contratos.append(
            schemas.ComissaoDetalheItem(
                contrato_id=contrato_id,
                numero_contrato=numero_contrato,
                cliente_nome=cliente_nome,
                valor_liquido=valor,
                percentagem=perc,
                valor_comissao=valor_comissao,
            )
        )

    return schemas.ComissaoDetalheResponse(
        responsavel_id=responsavel_id,
        responsavel_nome=responsavel.nome,
        mes=mes,
        total_comissao=round(total, 2),
        contratos=contratos,
    )
