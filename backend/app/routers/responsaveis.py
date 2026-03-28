"""
routers/responsaveis.py - CRUD de Responsáveis
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import ROLE_ADMIN, ROLE_OPERADOR, require_roles
from app.database import get_db
from app.services import audit_service as audit

router = APIRouter(prefix="/responsaveis", tags=["Responsáveis"])


@router.get("/", response_model=List[schemas.ResponsavelResponse])
def listar_responsaveis(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(models.Responsavel)
    if status:
        query = query.filter(models.Responsavel.status == status)
    return query.order_by(models.Responsavel.nome).all()


@router.post(
    "/",
    response_model=schemas.ResponsavelResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_responsavel(
    payload: schemas.ResponsavelCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    db_resp = models.Responsavel(**payload.model_dump())
    db.add(db_resp)
    db.flush()
    audit.registrar(
        db, current_user.id, current_user.nome,
        audit.AREA_RESPONSAVEIS, audit.ACAO_CRIADO,
        db_resp.id, db_resp.nome,
    )
    db.commit()
    db.refresh(db_resp)
    return db_resp


@router.put("/{responsavel_id}", response_model=schemas.ResponsavelResponse)
def atualizar_responsavel(
    responsavel_id: int,
    payload: schemas.ResponsavelUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    db_resp = db.query(models.Responsavel).filter(models.Responsavel.id == responsavel_id).first()
    if not db_resp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Responsável não encontrado")

    data = payload.model_dump(exclude_unset=True)
    # codigo não é alterável via API
    data.pop("codigo", None)
    for field, value in data.items():
        setattr(db_resp, field, value)

    acao = audit.ACAO_INATIVADO if data.get("status") == "inativo" else audit.ACAO_EDITADO
    audit.registrar(
        db, current_user.id, current_user.nome,
        audit.AREA_RESPONSAVEIS, acao,
        db_resp.id, db_resp.nome,
    )
    db.commit()
    db.refresh(db_resp)
    return db_resp
