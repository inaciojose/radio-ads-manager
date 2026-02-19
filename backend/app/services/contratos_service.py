from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas


class NumeroContratoConflictError(RuntimeError):
    pass


def _is_numero_contrato_conflict(exc: IntegrityError) -> bool:
    raw = str(getattr(exc, "orig", exc)).lower()
    return "numero_contrato" in raw or "contratos.numero_contrato" in raw


def criar_contrato_com_itens(
    db: Session,
    contrato: schemas.ContratoCreate,
    max_retries: int = 3,
):
    """
    Cria contrato com seus itens em uma única transação.
    """
    tentativas = max(1, max_retries)

    for tentativa in range(1, tentativas + 1):
        db_contrato = models.Contrato(
            cliente_id=contrato.cliente_id,
            numero_contrato=models.criar_numero_contrato(db),
            data_inicio=contrato.data_inicio,
            data_fim=contrato.data_fim,
            frequencia=contrato.frequencia,
            valor_total=contrato.valor_total,
            status_contrato=contrato.status_contrato,
            status_nf=contrato.status_nf,
            numero_nf=contrato.numero_nf,
            data_emissao_nf=contrato.data_emissao_nf,
            observacoes=contrato.observacoes,
        )
        db.add(db_contrato)
        db.flush()

        for item in contrato.itens:
            db_item = models.ContratoItem(
                contrato_id=db_contrato.id,
                tipo_programa=item.tipo_programa,
                quantidade_contratada=item.quantidade_contratada,
                quantidade_diaria_meta=item.quantidade_diaria_meta,
                observacoes=item.observacoes,
            )
            db.add(db_item)

        for meta in contrato.arquivos_metas:
            db_meta = models.ContratoArquivoMeta(
                contrato_id=db_contrato.id,
                arquivo_audio_id=meta.arquivo_audio_id,
                quantidade_meta=meta.quantidade_meta,
                modo_veiculacao=meta.modo_veiculacao,
                ativo=meta.ativo,
                observacoes=meta.observacoes,
            )
            db.add(db_meta)

        try:
            db.commit()
            db.refresh(db_contrato)
            return db_contrato
        except IntegrityError as exc:
            db.rollback()
            is_retryable = _is_numero_contrato_conflict(exc)
            if is_retryable and tentativa < tentativas:
                continue
            if is_retryable:
                raise NumeroContratoConflictError(
                    "Nao foi possivel gerar numero_contrato unico"
                ) from exc
            raise
