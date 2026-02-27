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
    auto_concluir_contratos_expirados,
    criar_contrato_com_itens,
)
from app.services.veiculacoes_service import resolver_item_contrato_para_veiculacao


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


def _normalizar_status_nota_para_contrato(status_nota: str) -> str:
    if status_nota == "paga":
        return "paga"
    if status_nota == "emitida":
        return "emitida"
    return "pendente"


def _sincronizar_resumo_nf_contrato(db: Session, contrato: models.Contrato) -> None:
    notas = (
        db.query(models.NotaFiscal)
        .filter(models.NotaFiscal.contrato_id == contrato.id)
        .order_by(models.NotaFiscal.created_at.desc(), models.NotaFiscal.id.desc())
        .all()
    )

    if not notas:
        contrato.status_nf = "pendente"
        contrato.numero_nf = None
        contrato.data_emissao_nf = None
        return

    if contrato.nf_dinamica == "unica":
        # NFs canceladas preservam dados no banco mas não afetam o resumo do contrato
        nota_unica = next(
            (n for n in notas if n.tipo == "unica" and n.status != "cancelada"), None
        )
        if not nota_unica:
            contrato.status_nf = "pendente"
            contrato.numero_nf = None
            contrato.data_emissao_nf = None
            return
        contrato.status_nf = _normalizar_status_nota_para_contrato(nota_unica.status)
        contrato.numero_nf = nota_unica.numero
        contrato.data_emissao_nf = nota_unica.data_emissao
        return

    # Para mensal: apenas NFs não canceladas entram no resumo do contrato
    notas_validas = [n for n in notas if n.tipo == "mensal" and n.status != "cancelada"]
    if not notas_validas:
        contrato.status_nf = "pendente"
        contrato.numero_nf = None
        contrato.data_emissao_nf = None
        return
    statuses = [n.status for n in notas_validas]
    if all(s == "paga" for s in statuses):
        contrato.status_nf = "paga"
    elif any(s in {"emitida", "paga"} for s in statuses):
        contrato.status_nf = "emitida"
    else:
        contrato.status_nf = "pendente"

    nota_ref = next((n for n in notas_validas if n.numero), None)
    contrato.numero_nf = nota_ref.numero if nota_ref else None
    contrato.data_emissao_nf = nota_ref.data_emissao if nota_ref else None


def _validar_unicidade_numero_nf(
    db: Session,
    numero: Optional[str],
    numero_recibo: Optional[str],
    nota_id_atual: Optional[int] = None,
) -> None:
    """Garante que numero e numero_recibo sejam unicos entre NFs nao canceladas."""
    if numero:
        q = db.query(models.NotaFiscal).filter(
            models.NotaFiscal.numero == numero,
            models.NotaFiscal.status != "cancelada",
        )
        if nota_id_atual:
            q = q.filter(models.NotaFiscal.id != nota_id_atual)
        if q.first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ja existe uma nota fiscal ativa com o numero '{numero}'.",
            )
    if numero_recibo:
        q = db.query(models.NotaFiscal).filter(
            models.NotaFiscal.numero_recibo == numero_recibo,
            models.NotaFiscal.status != "cancelada",
        )
        if nota_id_atual:
            q = q.filter(models.NotaFiscal.id != nota_id_atual)
        if q.first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ja existe uma nota fiscal ativa com o numero de recibo '{numero_recibo}'.",
            )


def _validar_tipo_nota_para_contrato(contrato: models.Contrato, tipo_nota: str) -> None:
    if contrato.nf_dinamica != tipo_nota:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contrato com nf_dinamica '{contrato.nf_dinamica}' aceita apenas notas do tipo '{contrato.nf_dinamica}'.",
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


def _validar_regras_itens_por_tipo_contrato(
    data_fim: Optional[date],
    itens: list,
) -> None:
    if not itens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contrato precisa ter pelo menos um item.",
        )

    if data_fim:
        if not any((item.quantidade_contratada or 0) > 0 for item in itens):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contrato com data fim exige meta total (quantidade_contratada).",
            )
    else:
        if not any((item.quantidade_diaria_meta or 0) > 0 for item in itens):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contrato sem data fim exige meta diaria (quantidade_diaria_meta).",
            )


def _resolver_item_em_lista(itens: list, tipo_programa: Optional[str]):
    if not itens:
        return None
    if tipo_programa:
        item = next((i for i in itens if i.tipo_programa == tipo_programa), None)
        if item:
            return item
    if len(itens) == 1:
        return itens[0]
    return itens[0]


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
    auto_concluir_contratos_expirados(db)

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
    notas_fiscais_pendentes = (
        db.query(models.NotaFiscal)
        .filter(models.NotaFiscal.status == "pendente")
        .count()
    )
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

        itens_contrato = itens_por_contrato.get(veiculacao.contrato_id, [])
        item_contabilizado = _resolver_item_em_lista(itens_contrato, veiculacao.tipo_programa)

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


@router.get("/resumo/dashboard")
def resumo_dashboard(db: Session = Depends(get_db)):
    hoje = date.today()
    inicio_dia = datetime.combine(hoje, datetime.min.time())
    fim_dia = datetime.combine(hoje, datetime.max.time())

    clientes_ativos = db.query(models.Cliente).filter(models.Cliente.status == "ativo").count()
    contratos_ativos = (
        db.query(models.Contrato)
        .filter(models.Contrato.status_contrato == "ativo")
        .count()
    )
    nf_pendentes = (
        db.query(models.Contrato)
        .filter(
            models.Contrato.status_contrato == "ativo",
            models.Contrato.status_nf == "pendente",
        )
        .count()
    )

    total_veiculacoes = db.query(models.Veiculacao).filter(
        models.Veiculacao.data_hora.between(inicio_dia, fim_dia)
    ).count()

    por_tipo = (
        db.query(models.Veiculacao.tipo_programa, func.count(models.Veiculacao.id))
        .filter(models.Veiculacao.data_hora.between(inicio_dia, fim_dia))
        .group_by(models.Veiculacao.tipo_programa)
        .all()
    )
    por_tipo_programa = {tipo or "não definido": total for tipo, total in por_tipo}

    top_clientes_raw = (
        db.query(
            models.ArquivoAudio.cliente_id,
            models.Cliente.nome,
            func.count(models.Veiculacao.id).label("total"),
        )
        .select_from(models.Veiculacao)
        .join(models.ArquivoAudio, models.Veiculacao.arquivo_audio_id == models.ArquivoAudio.id)
        .join(models.Cliente, models.ArquivoAudio.cliente_id == models.Cliente.id)
        .filter(models.Veiculacao.data_hora.between(inicio_dia, fim_dia))
        .group_by(models.ArquivoAudio.cliente_id, models.Cliente.nome)
        .order_by(func.count(models.Veiculacao.id).desc())
        .limit(10)
        .all()
    )
    top_10_clientes = [
        {"cliente_id": cliente_id, "cliente_nome": cliente_nome, "total": total}
        for cliente_id, cliente_nome, total in top_clientes_raw
    ]

    recentes_raw = (
        db.query(
            models.Veiculacao.id,
            models.Veiculacao.data_hora,
            models.Veiculacao.frequencia,
            models.Veiculacao.tipo_programa,
            models.Veiculacao.processado,
            models.ArquivoAudio.nome_arquivo.label("arquivo_nome"),
            models.Cliente.nome.label("cliente_nome"),
        )
        .select_from(models.Veiculacao)
        .join(models.ArquivoAudio, models.Veiculacao.arquivo_audio_id == models.ArquivoAudio.id)
        .join(models.Cliente, models.ArquivoAudio.cliente_id == models.Cliente.id)
        .filter(models.Veiculacao.data_hora.between(inicio_dia, fim_dia))
        .order_by(models.Veiculacao.data_hora.desc())
        .limit(10)
        .all()
    )
    recentes = [
        {
            "id": item.id,
            "data_hora": item.data_hora,
            "frequencia": item.frequencia,
            "tipo_programa": item.tipo_programa,
            "processado": item.processado,
            "arquivo_nome": item.arquivo_nome,
            "cliente_nome": item.cliente_nome,
        }
        for item in recentes_raw
    ]

    return {
        "data": hoje,
        "clientes_ativos": clientes_ativos,
        "contratos_ativos": contratos_ativos,
        "nf_pendentes": nf_pendentes,
        "total_veiculacoes": total_veiculacoes,
        "por_tipo_programa": por_tipo_programa,
        "top_10_clientes": top_10_clientes,
        "meta_diaria": resumo_meta_diaria_hoje(db),
        "recentes": recentes,
    }


@router.get("/{contrato_id}/resumo/monitoramento")
def resumo_monitoramento_contrato(
    contrato_id: int,
    data_ref: Optional[date] = Query(None, description="Data de referencia (padrao: hoje)"),
    db: Session = Depends(get_db),
):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    if not data_ref:
        data_ref = date.today()

    inicio_dia = datetime.combine(data_ref, datetime.min.time())
    fim_dia = datetime.combine(data_ref, datetime.max.time())

    metas_arquivo_ativas = db.query(models.ContratoArquivoMeta).filter(
        models.ContratoArquivoMeta.contrato_id == contrato.id,
        models.ContratoArquivoMeta.ativo == True,  # noqa: E712
    ).all()
    usa_metas_arquivo = len(metas_arquivo_ativas) > 0

    total_meta = 0
    total_executadas = 0
    if usa_metas_arquivo:
        total_meta = sum(m.quantidade_meta or 0 for m in metas_arquivo_ativas)
        total_executadas = sum(m.quantidade_executada or 0 for m in metas_arquivo_ativas)
    else:
        total_meta = sum((i.quantidade_contratada or 0) for i in (contrato.itens or []))
        total_executadas = sum((i.quantidade_executada or 0) for i in (contrato.itens or []))

    meta_diaria_total = sum((i.quantidade_diaria_meta or 0) for i in (contrato.itens or []))

    executadas_hoje = 0
    if meta_diaria_total > 0:
        pares_meta_arquivo = {(m.contrato_id, m.arquivo_audio_id) for m in metas_arquivo_ativas}
        veiculacoes_hoje = db.query(models.Veiculacao).filter(
            models.Veiculacao.contrato_id == contrato.id,
            models.Veiculacao.data_hora.between(inicio_dia, fim_dia),
            models.Veiculacao.contabilizada == True,  # noqa: E712
        ).all()

        for veiculacao in veiculacoes_hoje:
            if (veiculacao.contrato_id, veiculacao.arquivo_audio_id) in pares_meta_arquivo:
                continue
            item = resolver_item_contrato_para_veiculacao(contrato, veiculacao.tipo_programa)
            if item and (item.quantidade_diaria_meta or 0) > 0:
                executadas_hoje += 1

    percentual_total = 0.0
    if total_meta > 0:
        percentual_total = round((total_executadas / total_meta) * 100, 2)

    percentual_diario = 0.0
    if meta_diaria_total > 0:
        percentual_diario = round((executadas_hoje / meta_diaria_total) * 100, 2)

    return {
        "contrato_id": contrato.id,
        "numero_contrato": contrato.numero_contrato,
        "data_referencia": data_ref,
        "usa_metas_arquivo": usa_metas_arquivo,
        "total": {
            "meta": total_meta,
            "executadas": total_executadas,
            "percentual": percentual_total,
        },
        "diario": {
            "meta": meta_diaria_total,
            "executadas": executadas_hoje,
            "percentual": percentual_diario,
        },
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

    _validar_regras_itens_por_tipo_contrato(contrato.data_fim, contrato.itens)

    try:
        db_contrato = criar_contrato_com_itens(db, contrato)
        if contrato.nf_dinamica == "unica" and (
            contrato.numero_nf
            or contrato.data_emissao_nf
            or contrato.status_nf != "pendente"
        ):
            nota = models.NotaFiscal(
                contrato_id=db_contrato.id,
                tipo="unica",
                status=contrato.status_nf,
                numero=contrato.numero_nf,
                data_emissao=contrato.data_emissao_nf,
            )
            db.add(nota)
            db.flush()
            _sincronizar_resumo_nf_contrato(db, db_contrato)
            db.commit()
            db.refresh(db_contrato)
        return db_contrato
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

    itens_validacao = list(contrato.itens or []) + [item]
    _validar_regras_itens_por_tipo_contrato(contrato.data_fim, itens_validacao)

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

    db_contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not db_contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    update_data = item_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_item, field, value)

    if not db_item.quantidade_contratada and not db_item.quantidade_diaria_meta:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Item precisa ter quantidade_contratada, quantidade_diaria_meta ou ambas",
        )

    _validar_regras_itens_por_tipo_contrato(db_contrato.data_fim, db_contrato.itens or [])

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

    _validar_regras_itens_por_tipo_contrato(db_contrato.data_fim, db_contrato.itens or [])

    tem_notas = db.query(models.NotaFiscal.id).filter(
        models.NotaFiscal.contrato_id == db_contrato.id
    ).first() is not None
    if tem_notas:
        _sincronizar_resumo_nf_contrato(db, db_contrato)

    db.commit()
    db.refresh(db_contrato)
    return db_contrato


@router.get(
    "/{contrato_id}/notas-fiscais",
    response_model=List[schemas.NotaFiscalResponse],
)
def listar_notas_fiscais_contrato(
    contrato_id: int,
    tipo: Optional[str] = Query(None, pattern="^(unica|mensal)$"),
    competencia: Optional[str] = Query(None, description="Filtro YYYY-MM"),
    status_nf: Optional[str] = Query(None, pattern="^(pendente|emitida|paga|cancelada)$"),
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    query = db.query(models.NotaFiscal).filter(
        models.NotaFiscal.contrato_id == contrato_id
    )
    if tipo:
        query = query.filter(models.NotaFiscal.tipo == tipo)
    if competencia:
        query = query.filter(
            models.NotaFiscal.competencia == _parse_competencia_yyyy_mm(competencia)
        )
    if status_nf:
        query = query.filter(models.NotaFiscal.status == status_nf)

    return (
        query.order_by(
            models.NotaFiscal.competencia.desc(),
            models.NotaFiscal.created_at.desc(),
            models.NotaFiscal.id.desc(),
        ).all()
    )


@router.post(
    "/{contrato_id}/notas-fiscais",
    response_model=schemas.NotaFiscalResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_nota_fiscal_contrato(
    contrato_id: int,
    payload: schemas.NotaFiscalCreate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )

    _validar_tipo_nota_para_contrato(contrato, payload.tipo)
    if payload.tipo == "mensal":
        _validar_competencia_no_periodo_contrato(contrato, payload.competencia)

    _validar_unicidade_numero_nf(db, payload.numero, payload.numero_recibo)

    nota = models.NotaFiscal(
        contrato_id=contrato_id,
        tipo=payload.tipo,
        competencia=payload.competencia,
        status=payload.status,
        numero=payload.numero,
        serie=payload.serie,
        data_emissao=payload.data_emissao,
        data_pagamento=payload.data_pagamento,
        numero_recibo=payload.numero_recibo,
        valor_bruto=payload.valor_bruto,
        valor_liquido=payload.valor_liquido,
        valor_pago=payload.valor_pago,
        forma_pagamento=payload.forma_pagamento,
        campanha_agentes=payload.campanha_agentes,
        observacoes=payload.observacoes,
    )
    db.add(nota)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ja existe nota para este tipo/competencia neste contrato.",
        )

    _sincronizar_resumo_nf_contrato(db, contrato)
    db.commit()
    db.refresh(nota)
    return nota


@router.patch(
    "/notas-fiscais/{nota_id}",
    response_model=schemas.NotaFiscalResponse,
)
def atualizar_nota_fiscal(
    nota_id: int,
    payload: schemas.NotaFiscalUpdate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    nota = db.query(models.NotaFiscal).filter(models.NotaFiscal.id == nota_id).first()
    if not nota:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nota fiscal com ID {nota_id} nao encontrada",
        )

    update_data = payload.model_dump(exclude_unset=True)

    _validar_unicidade_numero_nf(
        db,
        update_data.get("numero"),
        update_data.get("numero_recibo"),
        nota_id_atual=nota.id,
    )

    for field, value in update_data.items():
        setattr(nota, field, value)

    contrato = db.query(models.Contrato).filter(models.Contrato.id == nota.contrato_id).first()
    _sincronizar_resumo_nf_contrato(db, contrato)
    db.commit()
    db.refresh(nota)
    return nota


@router.delete(
    "/notas-fiscais/{nota_id}",
    response_model=schemas.MessageResponse,
)
def deletar_nota_fiscal(
    nota_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    nota = db.query(models.NotaFiscal).filter(models.NotaFiscal.id == nota_id).first()
    if not nota:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nota fiscal com ID {nota_id} nao encontrada",
        )

    contrato = db.query(models.Contrato).filter(models.Contrato.id == nota.contrato_id).first()
    db.delete(nota)
    db.flush()
    _sincronizar_resumo_nf_contrato(db, contrato)
    db.commit()
    return {"message": f"Nota fiscal {nota_id} removida com sucesso", "success": True}


@router.get(
    "/{contrato_id}/faturamentos",
    response_model=List[schemas.NotaFiscalResponse],
)
def listar_faturamentos_mensais_contrato(
    contrato_id: int,
    competencia: Optional[str] = Query(None, description="Filtro YYYY-MM"),
    status_nf: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    return listar_notas_fiscais_contrato(
        contrato_id=contrato_id,
        tipo="mensal",
        competencia=competencia,
        status_nf=status_nf,
        db=db,
        _auth=_auth,
    )


@router.post(
    "/{contrato_id}/faturamentos",
    response_model=schemas.NotaFiscalResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_faturamento_mensal_contrato(
    contrato_id: int,
    payload: schemas.NotaFiscalCreate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )
    if contrato.nf_dinamica != "mensal":
        contrato.nf_dinamica = "mensal"
        db.flush()

    payload_mensal = schemas.NotaFiscalCreate(
        tipo="mensal",
        competencia=payload.competencia,
        status=payload.status,
        numero=payload.numero,
        serie=payload.serie,
        data_emissao=payload.data_emissao,
        data_pagamento=payload.data_pagamento,
        numero_recibo=payload.numero_recibo,
        valor_bruto=payload.valor_bruto,
        valor_liquido=payload.valor_liquido,
        valor_pago=payload.valor_pago,
        forma_pagamento=payload.forma_pagamento,
        campanha_agentes=payload.campanha_agentes,
        observacoes=payload.observacoes,
    )

    return criar_nota_fiscal_contrato(
        contrato_id=contrato_id,
        payload=payload_mensal,
        db=db,
        _auth=_auth,
    )


@router.post(
    "/{contrato_id}/faturamentos/{competencia}/emitir",
    response_model=schemas.NotaFiscalResponse,
)
def emitir_nota_fiscal_mensal_contrato(
    contrato_id: int,
    competencia: str,
    payload: schemas.EmitirNotaFiscalMensalRequest,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    competencia_ref = _parse_competencia_yyyy_mm(competencia)

    contrato = db.query(models.Contrato).filter(models.Contrato.id == contrato_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato com ID {contrato_id} nao encontrado",
        )
    if contrato.nf_dinamica != "mensal":
        contrato.nf_dinamica = "mensal"
        db.flush()
    _validar_competencia_no_periodo_contrato(contrato, competencia_ref)

    nota = db.query(models.NotaFiscal).filter(
        models.NotaFiscal.contrato_id == contrato_id,
        models.NotaFiscal.tipo == "mensal",
        models.NotaFiscal.competencia == competencia_ref,
    ).first()
    if not nota:
        nota = models.NotaFiscal(
            contrato_id=contrato_id,
            tipo="mensal",
            competencia=competencia_ref,
            status="pendente",
        )
        db.add(nota)
        db.flush()

    nota.status = payload.status or "emitida"
    nota.numero = payload.numero_nf
    nota.data_emissao = payload.data_emissao_nf or date.today()
    if payload.data_pagamento is not None:
        nota.data_pagamento = payload.data_pagamento
    if payload.numero_recibo is not None:
        nota.numero_recibo = payload.numero_recibo
    if payload.valor_bruto is not None:
        nota.valor_bruto = payload.valor_bruto
    if payload.valor_liquido is not None:
        nota.valor_liquido = payload.valor_liquido
    if payload.valor_pago is not None:
        nota.valor_pago = payload.valor_pago
    if payload.forma_pagamento is not None:
        nota.forma_pagamento = payload.forma_pagamento
    if payload.campanha_agentes is not None:
        nota.campanha_agentes = payload.campanha_agentes
    if payload.observacoes is not None:
        nota.observacoes = payload.observacoes

    _sincronizar_resumo_nf_contrato(db, contrato)
    db.commit()
    db.refresh(nota)
    return nota


@router.patch(
    "/faturamentos/{faturamento_id}",
    response_model=schemas.NotaFiscalResponse,
)
def atualizar_faturamento_mensal(
    faturamento_id: int,
    payload: schemas.NotaFiscalUpdate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    return atualizar_nota_fiscal(
        nota_id=faturamento_id,
        payload=payload,
        db=db,
        _auth=_auth,
    )


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
