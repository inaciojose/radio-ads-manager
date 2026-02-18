from datetime import date, datetime
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models


def buscar_item_contabilizado(db: Session, veiculacao: models.Veiculacao):
    """
    Resolve qual item de contrato foi (ou seria) contabilizado para a veiculação.
    Mantém a mesma lógica do processamento principal: tenta por tipo_programa e,
    se não existir, usa o primeiro item do contrato.
    """
    if not veiculacao.contrato_id:
        return None

    contrato = db.query(models.Contrato).filter(
        models.Contrato.id == veiculacao.contrato_id
    ).first()
    if not contrato:
        return None

    if veiculacao.tipo_programa:
        item = db.query(models.ContratoItem).filter(
            models.ContratoItem.contrato_id == contrato.id,
            models.ContratoItem.tipo_programa == veiculacao.tipo_programa
        ).first()
        if item:
            return item

    if contrato.itens:
        return contrato.itens[0]

    return None


def processar_veiculacoes_periodo(
    db: Session,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    force: bool = False,
):
    """
    Processa veiculações no período e contabiliza execução nos itens de contrato.
    """
    if not data_inicio:
        data_inicio = date.today()
    if not data_fim:
        data_fim = data_inicio

    inicio_periodo = datetime.combine(data_inicio, datetime.min.time())
    fim_periodo = datetime.combine(data_fim, datetime.max.time())

    query = db.query(models.Veiculacao).filter(
        models.Veiculacao.data_hora.between(inicio_periodo, fim_periodo)
    )

    if not force:
        query = query.filter(models.Veiculacao.processado == False)

    veiculacoes = query.all()
    if not veiculacoes:
        return {
            "message": f"Nenhuma veiculação para processar no período {data_inicio} a {data_fim}",
            "success": True
        }

    processadas = 0
    erros = 0

    for veiculacao in veiculacoes:
        try:
            if force and veiculacao.processado:
                item_anterior = buscar_item_contabilizado(db, veiculacao)
                if item_anterior and item_anterior.quantidade_executada > 0:
                    item_anterior.quantidade_executada -= 1

            arquivo = veiculacao.arquivo_audio
            if not arquivo:
                erros += 1
                continue

            contrato = db.query(models.Contrato).filter(
                models.Contrato.cliente_id == arquivo.cliente_id,
                models.Contrato.status_contrato == "ativo",
                models.Contrato.data_inicio <= veiculacao.data_hora.date(),
                models.Contrato.data_fim >= veiculacao.data_hora.date()
            )

            # Se a veiculação veio de uma frequência específica, prioriza contratos dessa frequência
            # e também contratos marcados como "ambas".
            if veiculacao.frequencia:
                contrato = contrato.filter(
                    or_(
                        models.Contrato.frequencia == veiculacao.frequencia,
                        models.Contrato.frequencia == "ambas",
                        models.Contrato.frequencia.is_(None),
                    )
                )

            contrato = contrato.first()

            if not contrato:
                veiculacao.processado = True
                veiculacao.contrato_id = None
                processadas += 1
                continue

            item = None
            if veiculacao.tipo_programa:
                item = db.query(models.ContratoItem).filter(
                    models.ContratoItem.contrato_id == contrato.id,
                    models.ContratoItem.tipo_programa == veiculacao.tipo_programa
                ).first()

            if not item and contrato.itens:
                item = contrato.itens[0]

            if item:
                item.quantidade_executada += 1

            veiculacao.processado = True
            veiculacao.contrato_id = contrato.id
            processadas += 1
        except Exception:
            erros += 1

    db.commit()

    return {
        "message": f"Processamento concluído: {processadas} veiculações processadas, {erros} erros",
        "success": True,
        "detalhes": {
            "periodo": f"{data_inicio} a {data_fim}",
            "total_veiculacoes": len(veiculacoes),
            "processadas": processadas,
            "erros": erros
        }
    }
