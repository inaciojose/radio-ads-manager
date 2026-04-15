"""routers/caixeta.py - Grade de Comerciais (Caixeta)."""

from io import BytesIO
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import ROLE_ADMIN, ROLE_OPERADOR, require_roles
from app.database import get_db
from app.services.export_service import build_caixeta_pdf
from app.services import audit_service as audit

router = APIRouter(prefix="/caixeta", tags=["Caixeta"])

_TIPOS_VALIDOS = {"semana", "sabado"}


def _validate_tipo(tipo: str) -> None:
    if tipo not in _TIPOS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo inválido. Use: {', '.join(sorted(_TIPOS_VALIDOS))}",
        )


# PDF deve ser declarado antes de /{tipo} para evitar conflito de roteamento
@router.get("/{tipo}/pdf")
def baixar_pdf_caixeta(tipo: str, db: Session = Depends(get_db)):
    """Gera e retorna o PDF da grade. Acessível sem autenticação."""
    _validate_tipo(tipo)
    caixeta = db.query(models.Caixeta).filter(models.Caixeta.tipo == tipo).first()
    if not caixeta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grade não encontrada")
    content = build_caixeta_pdf(caixeta, tipo)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=caixeta_{tipo}.pdf"},
    )


@router.get("/{tipo}", response_model=schemas.CaixetaResponse)
def get_caixeta(tipo: str, db: Session = Depends(get_db)):
    """Retorna a grade atual. Acessível sem autenticação."""
    _validate_tipo(tipo)
    caixeta = db.query(models.Caixeta).filter(models.Caixeta.tipo == tipo).first()
    if not caixeta:
        return schemas.CaixetaResponse(tipo=tipo, blocos=[])
    return caixeta


@router.put("/{tipo}", response_model=schemas.CaixetaResponse)
def salvar_caixeta(
    tipo: str,
    payload: schemas.CaixetaSaveRequest,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    """Salva (ou substitui) a grade completa. Requer admin ou operador."""
    _validate_tipo(tipo)

    caixeta = db.query(models.Caixeta).filter(models.Caixeta.tipo == tipo).first()
    if not caixeta:
        caixeta = models.Caixeta(tipo=tipo)
        db.add(caixeta)
        db.flush()

    # Remove blocos existentes (cascade apaga horários)
    for bloco in list(caixeta.blocos):
        db.delete(bloco)
    db.flush()

    # Insere novos blocos, horários e comerciais
    for i, bd in enumerate(payload.blocos):
        bloco = models.CaixetaBloco(
            caixeta_id=caixeta.id,
            nome_programa=bd.nome_programa,
            ordem=i,
        )
        db.add(bloco)
        db.flush()
        for j, hd in enumerate(bd.horarios):
            horario = models.CaixetaHorario(
                bloco_id=bloco.id,
                horario=hd.horario,
                ordem=j,
            )
            db.add(horario)
            db.flush()
            for k, cd in enumerate(hd.comerciais):
                db.add(models.CaixetaComercial(
                    horario_id=horario.id,
                    nome=cd.nome,
                    observacao=cd.observacao,
                    destaque=cd.destaque,
                    ordem=k,
                    codigo_chamada=cd.codigo_chamada,
                ))

    caixeta.updated_by = current_user.nome
    num_blocos = len(payload.blocos)
    audit.registrar(
        db, current_user.id, current_user.nome,
        audit.AREA_CAIXETA, audit.ACAO_EDITADO,
        tipo, f"Grade {tipo}",
        detalhe=f"{num_blocos} bloco(s) salvo(s)",
    )
    db.commit()
    db.refresh(caixeta)
    return caixeta


# status-veiculacoes deve ficar antes de /{tipo} para não colidir
@router.get("/{tipo}/status-veiculacoes", response_model=schemas.CaixetaStatusVeiculacoesResponse)
def status_veiculacoes_caixeta(
    tipo: str,
    data: Optional[date] = Query(None, description="Data a verificar (padrão: hoje)"),
    janela_minutos: int = Query(30, ge=5, le=120, description="Janela em minutos ao redor do horário agendado"),
    db: Session = Depends(get_db),
):
    """
    Para cada comercial da caixeta que tem codigo_chamada configurado,
    verifica se houve veiculação do cliente correspondente na data indicada
    dentro de uma janela de ±janela_minutos ao redor do horário agendado.

    Retorna:
    - tocou: existe veiculação com cliente_id correspondente na janela
    - nao_tocou: codigo_chamada configurado mas nenhuma veiculação na janela
    - sem_codigo: comercial sem codigo_chamada configurado
    """
    _validate_tipo(tipo)
    if not data:
        data = date.today()

    caixeta = db.query(models.Caixeta).filter(models.Caixeta.tipo == tipo).first()
    if not caixeta:
        return schemas.CaixetaStatusVeiculacoesResponse(tipo=tipo, data=data, comerciais=[])

    # Cache: codigo_chamada → cliente_id (somente clientes ativos)
    codigos_usados = set()
    for bloco in caixeta.blocos:
        for horario in bloco.horarios:
            for comercial in horario.comerciais:
                if comercial.codigo_chamada:
                    codigos_usados.add(comercial.codigo_chamada)

    codigo_para_cliente: dict[int, int] = {}
    if codigos_usados:
        clientes = db.query(models.Cliente.codigo_chamada, models.Cliente.id).filter(
            models.Cliente.codigo_chamada.in_(codigos_usados),
            models.Cliente.status == "ativo",
        ).all()
        codigo_para_cliente = {c.codigo_chamada: c.id for c in clientes}

    # Período do dia
    inicio_dia = datetime.combine(data, datetime.min.time())
    fim_dia = datetime.combine(data, datetime.max.time())

    # Buscar todas as veiculações do dia dos clientes relevantes
    cliente_ids = list(codigo_para_cliente.values())
    veiculacoes_do_dia: list[models.Veiculacao] = []
    if cliente_ids:
        veiculacoes_do_dia = db.query(models.Veiculacao).filter(
            models.Veiculacao.cliente_id.in_(cliente_ids),
            models.Veiculacao.data_hora.between(inicio_dia, fim_dia),
        ).all()

    # Indexar por cliente_id → lista de datetimes
    from collections import defaultdict
    vei_por_cliente: dict[int, list[datetime]] = defaultdict(list)
    vei_por_cliente_obj: dict[int, list[models.Veiculacao]] = defaultdict(list)
    for v in veiculacoes_do_dia:
        vei_por_cliente[v.cliente_id].append(v.data_hora)
        vei_por_cliente_obj[v.cliente_id].append(v)

    janela = timedelta(minutes=janela_minutos)
    resultado: list[schemas.CaixetaComercialStatus] = []

    for bloco in caixeta.blocos:
        for horario in bloco.horarios:
            h_str = horario.horario  # "HH:MM"
            try:
                h_time = datetime.strptime(h_str, "%H:%M").time()
                h_dt = datetime.combine(data, h_time)
            except ValueError:
                h_dt = None

            for comercial in horario.comerciais:
                if not comercial.codigo_chamada:
                    resultado.append(schemas.CaixetaComercialStatus(
                        comercial_id=comercial.id,
                        nome=comercial.nome,
                        codigo_chamada=None,
                        horario=h_str,
                        status="sem_codigo",
                    ))
                    continue

                cliente_id = codigo_para_cliente.get(comercial.codigo_chamada)
                if not cliente_id or h_dt is None:
                    resultado.append(schemas.CaixetaComercialStatus(
                        comercial_id=comercial.id,
                        nome=comercial.nome,
                        codigo_chamada=comercial.codigo_chamada,
                        horario=h_str,
                        status="nao_tocou",
                    ))
                    continue

                # Verificar se existe veiculação dentro da janela
                match = None
                for v in vei_por_cliente_obj.get(cliente_id, []):
                    if abs((v.data_hora - h_dt).total_seconds()) <= janela.total_seconds():
                        match = v
                        break

                resultado.append(schemas.CaixetaComercialStatus(
                    comercial_id=comercial.id,
                    nome=comercial.nome,
                    codigo_chamada=comercial.codigo_chamada,
                    horario=h_str,
                    status="tocou" if match else "nao_tocou",
                    veiculacao_id=match.id if match else None,
                    veiculacao_hora=match.data_hora.strftime("%H:%M:%S") if match else None,
                ))

    return schemas.CaixetaStatusVeiculacoesResponse(tipo=tipo, data=data, comerciais=resultado)
