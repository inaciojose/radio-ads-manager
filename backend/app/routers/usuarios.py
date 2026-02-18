from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import ROLE_ADMIN, hash_password, require_roles
from app.database import get_db


router = APIRouter(prefix="/usuarios", tags=["Usuários"])


@router.get("/", response_model=List[schemas.UsuarioResponse], dependencies=[Depends(require_roles(ROLE_ADMIN))])
def listar_usuarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    busca: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(models.Usuario)
    if busca:
        pattern = f"%{busca}%"
        query = query.filter(
            models.Usuario.username.ilike(pattern) | models.Usuario.nome.ilike(pattern)
        )

    return query.order_by(models.Usuario.username).offset(skip).limit(limit).all()


@router.post("/", response_model=schemas.UsuarioResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles(ROLE_ADMIN))])
def criar_usuario(payload: schemas.UsuarioCreate, db: Session = Depends(get_db)):
    existente = db.query(models.Usuario).filter(models.Usuario.username == payload.username).first()
    if existente:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username já cadastrado")

    db_user = models.Usuario(
        username=payload.username,
        nome=payload.nome,
        password_hash=hash_password(payload.password),
        role=payload.role,
        ativo=payload.ativo,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.patch("/{usuario_id}", response_model=schemas.UsuarioResponse, dependencies=[Depends(require_roles(ROLE_ADMIN))])
def atualizar_usuario(
    usuario_id: int,
    payload: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
):
    db_user = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")

    update_data = payload.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    return db_user
