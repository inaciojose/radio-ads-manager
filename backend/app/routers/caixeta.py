"""routers/caixeta.py - Grade de Comerciais (Caixeta)."""

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
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
