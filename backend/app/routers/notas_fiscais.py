"""routers/notas_fiscais.py - Visao global de notas fiscais."""

from datetime import date
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import ROLE_ADMIN, ROLE_OPERADOR, require_roles
from app.database import get_db
from app.services.export_service import build_excel, build_pdf, make_bar_chart


router = APIRouter(prefix="/notas-fiscais", tags=["Notas Fiscais"])

_SORT_COLUMNS = {
    "cliente_nome": models.Cliente.nome,
    "contrato_numero": models.Contrato.numero_contrato,
    "competencia": models.NotaFiscal.competencia,
    "valor_bruto": models.NotaFiscal.valor_bruto,
    "status": models.NotaFiscal.status,
    "numero": models.NotaFiscal.numero,
}

_EXPORT_HEADERS = [
    "Cliente",
    "Contrato",
    "Competência",
    "Número NF",
    "Valor Bruto",
    "Valor Líquido",
    "Valor Pago",
    "Forma de Pagamento",
    "Status",
]

_DEFAULT_ORDER = [
    models.NotaFiscal.competencia.desc(),
    models.NotaFiscal.data_emissao.desc(),
    models.NotaFiscal.created_at.desc(),
    models.NotaFiscal.id.desc(),
]

_MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


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


def _build_nf_query(
    db: Session,
    competencia: Optional[str],
    status_nf: Optional[str],
    cliente_id: Optional[int],
    busca: Optional[str],
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

    if busca:
        termo = f"%{busca.strip()}%"
        query = query.filter(
            or_(
                models.NotaFiscal.numero.ilike(termo),
                models.NotaFiscal.numero_recibo.ilike(termo),
            )
        )

    return query


def _format_competencia(d: Optional[date]) -> str:
    if not d:
        return "-"
    return f"{d.month:02d}/{d.year}"


def _fmt_currency(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _nf_export_row(nota, contrato, cliente) -> list:
    return [
        cliente.nome or "-",
        contrato.numero_contrato or f"#{contrato.id}",
        _format_competencia(nota.competencia),
        nota.numero or "-",
        _fmt_currency(nota.valor_bruto),
        _fmt_currency(nota.valor_liquido),
        _fmt_currency(nota.valor_pago),
        nota.forma_pagamento or "-",
        nota.status or "-",
    ]


def _build_filtros_texto_nf(
    competencia: Optional[str],
    status_nf: Optional[str],
    cliente_id: Optional[int],
    busca: Optional[str],
    db: Session,
) -> Optional[str]:
    partes = []
    if competencia:
        ano, mes = competencia.split("-")
        partes.append(f"Período: {_MESES_PT[int(mes) - 1]}/{ano}")
    if status_nf:
        partes.append(f"Status: {status_nf.capitalize()}")
    if cliente_id:
        cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
        if cliente:
            partes.append(f"Cliente: {cliente.nome}")
    if busca:
        partes.append(f"Busca: {busca}")
    return " | ".join(partes) if partes else None


def _get_chart_faturamento_mensal(db: Session, cliente_id: Optional[int] = None):
    """Retorna (labels, values) dos últimos 12 meses de NFs pagas."""
    today = date.today()
    m, y = today.month - 11, today.year
    if m <= 0:
        m += 12
        y -= 1

    start = date(y, m, 1)
    query = db.query(
        models.NotaFiscal.tipo,
        models.NotaFiscal.competencia,
        models.NotaFiscal.data_pagamento,
        models.NotaFiscal.valor_liquido,
    ).filter(models.NotaFiscal.status == "paga")

    if cliente_id:
        query = query.join(models.Contrato, models.NotaFiscal.contrato_id == models.Contrato.id)
        query = query.filter(models.Contrato.cliente_id == cliente_id)

    totais: dict = {}
    for tipo, competencia, data_pag, valor in query.all():
        if not valor:
            continue
        if tipo == "mensal" and competencia and competencia >= start:
            key = (competencia.year, competencia.month)
        elif tipo == "unica" and data_pag and data_pag >= start:
            key = (data_pag.year, data_pag.month)
        else:
            continue
        totais[key] = totais.get(key, 0.0) + float(valor)

    labels, values = [], []
    for i in range(12):
        mm = m + i
        yy = y
        while mm > 12:
            mm -= 12
            yy += 1
        labels.append(f"{_MESES_PT[mm - 1]}/{yy}")
        values.append(round(totais.get((yy, mm), 0.0), 2))

    return labels, values


@router.get("/exportar/excel")
def exportar_notas_fiscais_excel(
    competencia: Optional[str] = Query(None),
    status_nf: Optional[str] = Query(None, pattern="^(pendente|emitida|paga|cancelada)$"),
    cliente_id: Optional[int] = Query(None, ge=1),
    busca: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    rows = (
        _build_nf_query(db, competencia, status_nf, cliente_id, busca)
        .order_by(*_DEFAULT_ORDER)
        .all()
    )
    data = [_nf_export_row(nota, contrato, cliente) for nota, contrato, cliente in rows]
    content = build_excel(_EXPORT_HEADERS, data, sheet_name="Notas Fiscais")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=notas_fiscais.xlsx"},
    )


@router.get("/exportar/pdf")
def exportar_notas_fiscais_pdf(
    competencia: Optional[str] = Query(None),
    status_nf: Optional[str] = Query(None, pattern="^(pendente|emitida|paga|cancelada)$"),
    cliente_id: Optional[int] = Query(None, ge=1),
    busca: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    rows = (
        _build_nf_query(db, competencia, status_nf, cliente_id, busca)
        .order_by(*_DEFAULT_ORDER)
        .all()
    )
    data = [_nf_export_row(nota, contrato, cliente) for nota, contrato, cliente in rows]

    filtros_texto = _build_filtros_texto_nf(competencia, status_nf, cliente_id, busca, db)

    chart_labels, chart_values = _get_chart_faturamento_mensal(db, cliente_id)
    chart = make_bar_chart(
        chart_values,
        chart_labels,
        title="Faturamento Mensal — Últimos 12 Meses (NFs Pagas, Valor Líquido)",
    )

    content = build_pdf(
        _EXPORT_HEADERS,
        data,
        title="Relatório de Notas Fiscais",
        username=current_user.nome,
        filtros_texto=filtros_texto,
        pre_content=[chart],
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=notas_fiscais.pdf"},
    )


@router.get("/", response_model=schemas.NotaFiscalListResponse)
def listar_notas_fiscais(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    competencia: Optional[str] = Query(None, description="Filtro YYYY-MM"),
    status_nf: Optional[str] = Query(None, pattern="^(pendente|emitida|paga|cancelada)$"),
    cliente_id: Optional[int] = Query(None, ge=1),
    busca: Optional[str] = Query(None, description="Busca por número da NF ou número do recibo"),
    sort_by: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    query = _build_nf_query(db, competencia, status_nf, cliente_id, busca)
    total = query.count()

    sort_col = _SORT_COLUMNS.get(sort_by) if sort_by else None
    if sort_col is not None:
        primary_order = sort_col.asc() if sort_dir == "asc" else sort_col.desc()
        order_clause = [primary_order, models.NotaFiscal.id.desc()]
    else:
        order_clause = _DEFAULT_ORDER

    rows = query.order_by(*order_clause).offset(skip).limit(limit).all()

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
            serie=nota.serie,
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
