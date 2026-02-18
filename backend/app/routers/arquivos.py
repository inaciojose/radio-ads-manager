"""
routers/arquivos.py - Endpoints para gerenciar arquivos de audio.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import ROLE_ADMIN, ROLE_OPERADOR, require_roles
from app import models, schemas
from app.database import get_db


router = APIRouter(
    prefix="/arquivos",
    tags=["Arquivos"],
)


@router.get("/", response_model=List[schemas.ArquivoAudioResponse])
def listar_arquivos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    cliente_id: Optional[int] = Query(None),
    ativo: Optional[bool] = Query(None),
    busca: Optional[str] = Query(None, description="Busca por nome_arquivo ou titulo"),
    db: Session = Depends(get_db),
):
    query = db.query(models.ArquivoAudio)

    if cliente_id:
        query = query.filter(models.ArquivoAudio.cliente_id == cliente_id)
    if ativo is not None:
        query = query.filter(models.ArquivoAudio.ativo == ativo)
    if busca:
        pattern = f"%{busca}%"
        query = query.filter(
            (models.ArquivoAudio.nome_arquivo.ilike(pattern))
            | (models.ArquivoAudio.titulo.ilike(pattern))
        )

    return query.order_by(models.ArquivoAudio.data_upload.desc()).offset(skip).limit(limit).all()


@router.get("/relatorios/nao-utilizados")
def relatorio_nao_utilizados(
    dias: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    limite_data = datetime.now() - timedelta(days=dias)

    usados_recentemente = (
        db.query(models.Veiculacao.arquivo_audio_id)
        .filter(models.Veiculacao.data_hora >= limite_data)
        .distinct()
        .subquery()
    )

    arquivos = (
        db.query(models.ArquivoAudio)
        .filter(models.ArquivoAudio.ativo == True)  # noqa: E712
        .filter(~models.ArquivoAudio.id.in_(usados_recentemente))
        .order_by(models.ArquivoAudio.nome_arquivo)
        .all()
    )

    return {
        "dias_sem_uso": dias,
        "total": len(arquivos),
        "items": [
            {
                "id": a.id,
                "cliente_id": a.cliente_id,
                "nome_arquivo": a.nome_arquivo,
                "titulo": a.titulo,
                "duracao_segundos": a.duracao_segundos,
                "ativo": a.ativo,
                "data_upload": a.data_upload,
            }
            for a in arquivos
        ],
    }


@router.get("/{arquivo_id}", response_model=schemas.ArquivoAudioResponse)
def buscar_arquivo(
    arquivo_id: int,
    db: Session = Depends(get_db),
):
    arquivo = db.query(models.ArquivoAudio).filter(models.ArquivoAudio.id == arquivo_id).first()
    if not arquivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo com ID {arquivo_id} nao encontrado",
        )
    return arquivo


@router.post("/", response_model=schemas.ArquivoAudioResponse, status_code=status.HTTP_201_CREATED)
def criar_arquivo(
    arquivo: schemas.ArquivoAudioCreate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == arquivo.cliente_id).first()
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente com ID {arquivo.cliente_id} nao encontrado",
        )

    existente = (
        db.query(models.ArquivoAudio)
        .filter(models.ArquivoAudio.nome_arquivo == arquivo.nome_arquivo)
        .first()
    )
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ja existe arquivo cadastrado com nome '{arquivo.nome_arquivo}'",
        )

    db_arquivo = models.ArquivoAudio(**arquivo.model_dump())
    db.add(db_arquivo)
    db.commit()
    db.refresh(db_arquivo)
    return db_arquivo


@router.put("/{arquivo_id}", response_model=schemas.ArquivoAudioResponse)
def atualizar_arquivo(
    arquivo_id: int,
    arquivo_update: schemas.ArquivoAudioUpdate,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    db_arquivo = db.query(models.ArquivoAudio).filter(models.ArquivoAudio.id == arquivo_id).first()
    if not db_arquivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo com ID {arquivo_id} nao encontrado",
        )

    update_data = arquivo_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_arquivo, field, value)

    db.commit()
    db.refresh(db_arquivo)
    return db_arquivo


@router.patch("/{arquivo_id}/toggle-ativo", response_model=schemas.ArquivoAudioResponse)
def toggle_arquivo_ativo(
    arquivo_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    db_arquivo = db.query(models.ArquivoAudio).filter(models.ArquivoAudio.id == arquivo_id).first()
    if not db_arquivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo com ID {arquivo_id} nao encontrado",
        )

    db_arquivo.ativo = not db_arquivo.ativo
    db.commit()
    db.refresh(db_arquivo)
    return db_arquivo


@router.delete("/{arquivo_id}", response_model=schemas.MessageResponse)
def deletar_arquivo(
    arquivo_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_roles(ROLE_ADMIN, ROLE_OPERADOR)),
):
    db_arquivo = db.query(models.ArquivoAudio).filter(models.ArquivoAudio.id == arquivo_id).first()
    if not db_arquivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo com ID {arquivo_id} nao encontrado",
        )

    db.delete(db_arquivo)
    db.commit()
    return {
        "message": f"Arquivo '{db_arquivo.nome_arquivo}' deletado com sucesso",
        "success": True,
    }


@router.get("/{arquivo_id}/estatisticas")
def estatisticas_arquivo(
    arquivo_id: int,
    db: Session = Depends(get_db),
):
    db_arquivo = (
        db.query(models.ArquivoAudio)
        .join(models.Cliente, models.ArquivoAudio.cliente_id == models.Cliente.id)
        .filter(models.ArquivoAudio.id == arquivo_id)
        .first()
    )
    if not db_arquivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo com ID {arquivo_id} nao encontrado",
        )

    total_veiculacoes = (
        db.query(func.count(models.Veiculacao.id))
        .filter(models.Veiculacao.arquivo_audio_id == arquivo_id)
        .scalar()
        or 0
    )
    ultima_veiculacao = (
        db.query(models.Veiculacao.data_hora)
        .filter(models.Veiculacao.arquivo_audio_id == arquivo_id)
        .order_by(models.Veiculacao.data_hora.desc())
        .first()
    )

    return {
        "arquivo_id": db_arquivo.id,
        "nome_arquivo": db_arquivo.nome_arquivo,
        "cliente_id": db_arquivo.cliente_id,
        "cliente_nome": db_arquivo.cliente.nome if db_arquivo.cliente else None,
        "ativo": db_arquivo.ativo,
        "total_veiculacoes": total_veiculacoes,
        "ultima_veiculacao": ultima_veiculacao[0] if ultima_veiculacao else None,
    }
