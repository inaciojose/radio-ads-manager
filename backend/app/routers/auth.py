from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import create_access_token, get_current_user, verify_password
from app.database import get_db


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.username == payload.username).first()
    if not user or not user.ativo or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
        )

    token = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": user,
    }


@router.get("/me", response_model=schemas.UsuarioResponse)
def me(current_user: models.Usuario = Depends(get_current_user)):
    return current_user
