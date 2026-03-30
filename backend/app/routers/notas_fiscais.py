"""routers/notas_fiscais.py - Visao global de notas fiscais."""

import re
from datetime import date
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
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


# ---------------------------------------------------------------------------
# Importar NF via PDF
# ---------------------------------------------------------------------------

def _extrair_valor(texto: str, *patterns: str) -> Optional[float]:
    """Tenta extrair um valor monetário usando os padrões fornecidos."""
    for pat in patterns:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            # Remove separadores de milhar e troca vírgula por ponto
            raw = raw.replace(".", "").replace(",", ".")
            try:
                return float(raw)
            except ValueError:
                continue
    return None


def _limpar_cnpj(cnpj: str) -> str:
    """Retorna apenas os dígitos do CNPJ."""
    return re.sub(r"\D", "", cnpj)


def _parsear_pdf_nfcom(texto: str) -> dict:
    """Extrai campos de uma NFCom a partir do texto bruto do PDF."""
    resultado: dict = {}

    # Número da NF: após 'NOTA FISCAL FATURA No.' ou 'No.'
    m = re.search(r"NOTA FISCAL FATURA\s*N[Oo°]\.?\s*(\d+)", texto)
    if m:
        resultado["numero"] = m.group(1).lstrip("0") or m.group(1)

    # Data de emissão: DD/MM/YYYY após 'DATA DE EMISSÃO'
    m = re.search(r"DATA DE EMISS[ÃA]O[:\s]*(\d{2}/\d{2}/\d{4})", texto)
    if m:
        d, mo, y = m.group(1).split("/")
        resultado["data_emissao"] = f"{y}-{mo}-{d}"

    # Competência: YYYY/MM após 'REFERÊNCIA (ANO/MÊS)'
    m = re.search(r"REFER[EÊ]NCIA\s*\(ANO/M[EÊ]S\)[:\s]*(\d{4})/(\d{2})", texto)
    if m:
        resultado["competencia"] = f"{m.group(1)}-{m.group(2)}"

    # Valor: várias formas possíveis no layout da NFCom
    valor = _extrair_valor(
        texto,
        r"TOTAL\s+A\s+PAGAR[:\s]*R\$\s*([\d.,]+)",
        r"VALOR\s+TOTAL\s+NFF\s+R\$\s*([\d.,]+)",
        r"VALOR\s+TOTAL\s+DA\s+NOTA\s+R\$\s*([\d.,]+)",
        r"TOTAL\s+R\$\s*([\d.,]+)",
    )
    if valor is not None:
        resultado["valor_bruto"] = valor

    # CNPJ do tomador: extrai o valor que vem após o rótulo 'CNPJ/CPF:',
    # exclusivo do bloco do tomador (evita pegar o CNPJ do emitente no cabeçalho)
    m = re.search(r"CNPJ/CPF[:\s]+(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2})", texto)
    if m:
        resultado["cnpj_tomador"] = m.group(1)

    # Nome do tomador: bloco após 'TOMADOR' ou 'DESTINATÁRIO'
    m = re.search(
        r"(?:TOMADOR|DESTINAT[AÁ]RIO)[^\n]*\n\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^\n]{3,80})",
        texto,
        re.IGNORECASE,
    )
    if m:
        resultado["nome_tomador"] = m.group(1).strip()

    return resultado


@router.post("/importar-pdf", response_model=schemas.ImportarNFPdfResponse)
def importar_pdf_nf(
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    """Extrai campos de uma NFCom em PDF e tenta identificar o cliente pelo CNPJ."""
    if not arquivo.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(status_code=500, detail="pdfplumber não instalado no servidor.")

    conteudo = arquivo.file.read()
    from io import BytesIO as _BytesIO

    texto = ""
    try:
        with pdfplumber.open(_BytesIO(conteudo)) as pdf:
            for pagina in pdf.pages:
                texto += (pagina.extract_text() or "") + "\n"
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Não foi possível ler o PDF: {exc}")

    dados = _parsear_pdf_nfcom(texto)

    # Identifica cliente pelo CNPJ
    cliente_id = None
    cliente_nome = None
    if dados.get("cnpj_tomador"):
        cnpj_digits = _limpar_cnpj(dados["cnpj_tomador"])
        cliente = (
            db.query(models.Cliente)
            .filter(models.Cliente.cnpj_cpf.isnot(None))
            .all()
        )
        for c in cliente:
            if _limpar_cnpj(c.cnpj_cpf or "") == cnpj_digits:
                cliente_id = c.id
                cliente_nome = c.nome
                break

    campos_preenchidos = [k for k in ("numero", "data_emissao", "competencia", "valor_bruto") if k in dados]

    return schemas.ImportarNFPdfResponse(
        numero=dados.get("numero"),
        data_emissao=dados.get("data_emissao"),
        competencia=dados.get("competencia"),
        valor_bruto=dados.get("valor_bruto"),
        cnpj_tomador=dados.get("cnpj_tomador"),
        nome_tomador=dados.get("nome_tomador"),
        cliente_id=cliente_id,
        cliente_nome=cliente_nome,
        campos_preenchidos=campos_preenchidos,
    )
