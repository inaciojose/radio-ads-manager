"""
routers/programas.py - CRUD de Programas de Rádio
"""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import ROLE_ADMIN, ROLE_OPERADOR, require_roles
from app.database import get_db
from app.services import audit_service as audit

router = APIRouter(prefix="/programas", tags=["Programas"])


def _serialize(programa: schemas.ProgramaBase | schemas.ProgramaUpdate) -> dict:
    """Converte o schema para dict pronto para persistir (dias_semana → JSON string)."""
    data = programa.model_dump(exclude_unset=True)
    if "dias_semana" in data and isinstance(data["dias_semana"], list):
        data["dias_semana"] = json.dumps(data["dias_semana"])
    return data


@router.get("/", response_model=List[schemas.ProgramaResponse])
def listar_programas(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(models.Programa)
    if status:
        query = query.filter(models.Programa.status == status)
    return query.order_by(models.Programa.nome).all()


@router.post(
    "/",
    response_model=schemas.ProgramaResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_programa(
    payload: schemas.ProgramaCreate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    existente = (
        db.query(models.Programa)
        .filter(models.Programa.nome == payload.nome)
        .first()
    )
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um programa com o nome '{payload.nome}'",
        )

    db_programa = models.Programa(**_serialize(payload))
    db.add(db_programa)
    db.flush()
    audit.registrar(
        db, current_user.id, current_user.nome,
        audit.AREA_PROGRAMAS, audit.ACAO_CRIADO,
        db_programa.id, db_programa.nome,
    )
    db.commit()
    db.refresh(db_programa)
    return db_programa


@router.put("/{programa_id}", response_model=schemas.ProgramaResponse)
def atualizar_programa(
    programa_id: int,
    payload: schemas.ProgramaUpdate,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    db_programa = db.query(models.Programa).filter(models.Programa.id == programa_id).first()
    if not db_programa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa não encontrado")

    data = _serialize(payload)
    if "nome" in data and data["nome"] != db_programa.nome:
        conflito = (
            db.query(models.Programa)
            .filter(models.Programa.nome == data["nome"], models.Programa.id != programa_id)
            .first()
        )
        if conflito:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um programa com o nome '{data['nome']}'",
            )

    for field, value in data.items():
        setattr(db_programa, field, value)

    audit.registrar(
        db, current_user.id, current_user.nome,
        audit.AREA_PROGRAMAS, audit.ACAO_EDITADO,
        db_programa.id, db_programa.nome,
    )
    db.commit()
    db.refresh(db_programa)
    return db_programa


@router.delete("/{programa_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_programa(
    programa_id: int,
    db: Session = Depends(get_db),
    current_user: models.Usuario = Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    db_programa = db.query(models.Programa).filter(models.Programa.id == programa_id).first()
    if not db_programa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programa não encontrado")

    audit.registrar(
        db, current_user.id, current_user.nome,
        audit.AREA_PROGRAMAS, audit.ACAO_EXCLUIDO,
        programa_id, db_programa.nome,
    )
    db.delete(db_programa)
    db.commit()
