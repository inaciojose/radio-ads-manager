from sqlalchemy.orm import Session

from app import models, schemas


def criar_contrato_com_itens(db: Session, contrato: schemas.ContratoCreate):
    """
    Cria contrato com seus itens em uma única transação.
    """
    db_contrato = models.Contrato(
        cliente_id=contrato.cliente_id,
        numero_contrato=models.criar_numero_contrato(db),
        data_inicio=contrato.data_inicio,
        data_fim=contrato.data_fim,
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
            observacoes=item.observacoes,
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_contrato)
    return db_contrato

