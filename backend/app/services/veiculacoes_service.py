import os
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models


def resolver_item_contrato_para_veiculacao(
    contrato: models.Contrato,
    tipo_programa: Optional[str],
):
    """
    Resolve o item de contrato para contabilização.
    Estratégia:
    1) tentar match exato por tipo_programa;
    2) se houver item único, usar esse item;
    3) fallback configurável (padrão: primeiro item).
    """
    itens = list(contrato.itens or [])
    if not itens:
        return None

    if tipo_programa:
        item = next((i for i in itens if i.tipo_programa == tipo_programa), None)
        if item:
            return item

    if len(itens) == 1:
        return itens[0]

    fallback = os.getenv("CONTRATO_ITEM_FALLBACK_STRATEGY", "first").strip().lower()
    if fallback == "first":
        return itens[0]
    return None


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

    return resolver_item_contrato_para_veiculacao(contrato, veiculacao.tipo_programa)


def buscar_meta_contabilizada(db: Session, veiculacao: models.Veiculacao):
    """
    Resolve qual meta por arquivo foi (ou seria) contabilizada para a veiculação.
    """
    if not veiculacao.contrato_id:
        return None

    return db.query(models.ContratoArquivoMeta).filter(
        models.ContratoArquivoMeta.contrato_id == veiculacao.contrato_id,
        models.ContratoArquivoMeta.arquivo_audio_id == veiculacao.arquivo_audio_id,
        models.ContratoArquivoMeta.ativo == True,  # noqa: E712
    ).first()


def _parse_hora(valor: str) -> time:
    raw = valor.strip()
    if len(raw.split(":")) == 2:
        raw = f"{raw}:00"
    return time.fromisoformat(raw)


def _parse_dias_semana(valor: str) -> set[int]:
    dias = set()
    for trecho in valor.split(","):
        item = trecho.strip()
        if not item:
            continue
        if "-" in item:
            ini_str, fim_str = item.split("-", 1)
            ini = int(ini_str.strip())
            fim = int(fim_str.strip())
            for d in range(ini, fim + 1):
                dias.add(d)
        else:
            dias.add(int(item))
    return dias


def _carregar_regras_bloqueio():
    """
    Regras no formato:
      frequencia|dias_iso|hh:mm-hh:mm|motivo
    Exemplo:
      102.7|1-5|11:00-14:00|obs_video
    """
    raw = os.getenv(
        "AUTO_AUDIT_BLOCK_WINDOWS",
        "102.7|1-5|11:00-14:00|obs_video",
    )
    regras = []
    for chunk in raw.split(";"):
        item = chunk.strip()
        if not item:
            continue
        partes = [p.strip() for p in item.split("|")]
        if len(partes) != 4:
            continue
        frequencia, dias_str, janela, motivo = partes
        if "-" not in janela:
            continue
        inicio_str, fim_str = janela.split("-", 1)
        regras.append(
            {
                "frequencia": frequencia,
                "dias": _parse_dias_semana(dias_str),
                "inicio": _parse_hora(inicio_str),
                "fim": _parse_hora(fim_str),
                "motivo": motivo or "bloqueio_auditoria_automatica",
            }
        )
    return regras


def _auditoria_automatica_bloqueada(veiculacao: models.Veiculacao) -> Optional[str]:
    # Bloqueio só para origem automática do Zara.
    if (veiculacao.fonte or "zara_log") != "zara_log":
        return None

    if not veiculacao.frequencia:
        return None

    regras = _carregar_regras_bloqueio()
    if not regras:
        return None

    horario = veiculacao.data_hora.time()
    dia_iso = veiculacao.data_hora.isoweekday()

    for regra in regras:
        if regra["frequencia"] != veiculacao.frequencia:
            continue
        if dia_iso not in regra["dias"]:
            continue
        if regra["inicio"] <= horario < regra["fim"]:
            return regra["motivo"]
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
            if force and veiculacao.processado and veiculacao.contabilizada:
                meta_anterior = buscar_meta_contabilizada(db, veiculacao)
                if meta_anterior and meta_anterior.quantidade_executada > 0:
                    meta_anterior.quantidade_executada -= 1
                else:
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
                or_(
                    models.Contrato.data_fim.is_(None),
                    models.Contrato.data_fim >= veiculacao.data_hora.date(),
                ),
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
                veiculacao.contabilizada = False
                veiculacao.contrato_id = None
                processadas += 1
                continue

            bloqueio = _auditoria_automatica_bloqueada(veiculacao)
            if bloqueio:
                veiculacao.processado = True
                veiculacao.contabilizada = False
                veiculacao.contrato_id = contrato.id
                processadas += 1
                continue

            contabilizada = False
            meta = db.query(models.ContratoArquivoMeta).filter(
                models.ContratoArquivoMeta.contrato_id == contrato.id,
                models.ContratoArquivoMeta.arquivo_audio_id == veiculacao.arquivo_audio_id,
                models.ContratoArquivoMeta.ativo == True,  # noqa: E712
            ).first()
            if meta:
                meta.quantidade_executada += 1
                contabilizada = True
            else:
                item = resolver_item_contrato_para_veiculacao(
                    contrato,
                    veiculacao.tipo_programa,
                )

                if item:
                    item.quantidade_executada += 1
                    contabilizada = True

            veiculacao.processado = True
            veiculacao.contabilizada = contabilizada
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
