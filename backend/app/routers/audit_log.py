"""routers/audit_log.py - Consulta do Audit Log (somente leitura, apenas admin)."""

from datetime import date, datetime, timezone
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import ROLE_ADMIN, require_roles
from app.database import get_db
from app.services.export_service import build_excel, build_pdf

router = APIRouter(prefix="/audit-log", tags=["Audit Log"])

_REQUIRE_ADMIN = Depends(require_roles(ROLE_ADMIN))

_EXPORT_HEADERS = [
    "Data/Hora",
    "Usuário",
    "Área",
    "Ação",
    "Registro",
    "Detalhe",
]

_AREAS_VALIDAS = {
    "Clientes", "Contratos", "Notas Fiscais", "Veiculações",
    "Responsáveis", "Programas", "Usuários", "Arquivos", "Caixeta",
}

_ACOES_VALIDAS = {"criado", "editado", "excluído", "inativado", "cancelado"}


def _build_query(
    db: Session,
    data_inicio: Optional[date],
    data_fim: Optional[date],
    usuario_id: Optional[int],
    area: Optional[str],
    acao: Optional[str],
):
    q = db.query(models.AuditLog)
    if data_inicio:
        q = q.filter(models.AuditLog.data_hora >= datetime(data_inicio.year, data_inicio.month, data_inicio.day, tzinfo=timezone.utc))
    if data_fim:
        from datetime import timedelta
        fim_dt = datetime(data_fim.year, data_fim.month, data_fim.day, 23, 59, 59, tzinfo=timezone.utc)
        q = q.filter(models.AuditLog.data_hora <= fim_dt)
    if usuario_id is not None:
        q = q.filter(models.AuditLog.usuario_id == usuario_id)
    if area:
        q = q.filter(models.AuditLog.area == area)
    if acao:
        q = q.filter(models.AuditLog.acao == acao)
    return q.order_by(models.AuditLog.data_hora.desc())


def _row(item: models.AuditLog) -> list:
    dt = item.data_hora
    if dt and dt.tzinfo:
        from zoneinfo import ZoneInfo
        dt_local = dt.astimezone(ZoneInfo("America/Fortaleza"))
        dt_str = dt_local.strftime("%d/%m/%Y %H:%M:%S")
    elif dt:
        dt_str = dt.strftime("%d/%m/%Y %H:%M:%S")
    else:
        dt_str = "-"

    registro = item.registro_descricao or item.registro_id or "-"
    return [
        dt_str,
        item.usuario_nome or "-",
        item.area or "-",
        item.acao or "-",
        registro,
        item.detalhe or "-",
    ]


@router.get("/", response_model=schemas.AuditLogListResponse)
def listar_audit_log(
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    usuario_id: Optional[int] = Query(None),
    area: Optional[str] = Query(None),
    acao: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    _auth=_REQUIRE_ADMIN,
):
    q = _build_query(db, data_inicio, data_fim, usuario_id, area, acao)
    total = q.count()
    items = q.limit(limit).all()
    return {"items": items, "total": total}


@router.get("/exportar/excel")
def exportar_audit_log_excel(
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    usuario_id: Optional[int] = Query(None),
    area: Optional[str] = Query(None),
    acao: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _auth=_REQUIRE_ADMIN,
):
    items = _build_query(db, data_inicio, data_fim, usuario_id, area, acao).limit(5000).all()
    data = [_row(i) for i in items]
    content = build_excel(_EXPORT_HEADERS, data, sheet_name="Audit Log")
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=audit_log.xlsx"},
    )


@router.get("/exportar/pdf")
def exportar_audit_log_pdf(
    data_inicio: Optional[date] = Query(None),
    data_fim: Optional[date] = Query(None),
    usuario_id: Optional[int] = Query(None),
    area: Optional[str] = Query(None),
    acao: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN)),
):
    items = _build_query(db, data_inicio, data_fim, usuario_id, area, acao).limit(5000).all()
    data = [_row(i) for i in items]

    partes = []
    if data_inicio:
        partes.append(f"De: {data_inicio.strftime('%d/%m/%Y')}")
    if data_fim:
        partes.append(f"Até: {data_fim.strftime('%d/%m/%Y')}")
    if area:
        partes.append(f"Área: {area}")
    if acao:
        partes.append(f"Ação: {acao.capitalize()}")
    filtros_texto = " | ".join(partes) if partes else None

    content = build_pdf(
        _EXPORT_HEADERS,
        data,
        title="Audit Log",
        username=current_user.nome,
        filtros_texto=filtros_texto,
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=audit_log.pdf"},
    )
