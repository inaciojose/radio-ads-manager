"""audit_service.py - Serviço de Auditoria

Registra ações relevantes realizadas no sistema.
Os registros são imutáveis via API — somente limpeza automática os remove.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models


# Áreas auditadas
AREA_CLIENTES = "Clientes"
AREA_CONTRATOS = "Contratos"
AREA_NOTAS_FISCAIS = "Notas Fiscais"
AREA_VEICULACOES = "Veiculações"
AREA_RESPONSAVEIS = "Responsáveis"
AREA_PROGRAMAS = "Programas"
AREA_USUARIOS = "Usuários"
AREA_ARQUIVOS = "Arquivos"
AREA_CAIXETA = "Caixeta"

# Tipos de ação
ACAO_CRIADO = "criado"
ACAO_EDITADO = "editado"
ACAO_EXCLUIDO = "excluído"
ACAO_INATIVADO = "inativado"
ACAO_CANCELADO = "cancelado"


def registrar(
    db: Session,
    usuario_id: Optional[int],
    usuario_nome: Optional[str],
    area: str,
    acao: str,
    registro_id: Optional[str | int],
    registro_descricao: Optional[str],
    detalhe: Optional[str] = None,
) -> None:
    """
    Registra uma entrada no audit log dentro da sessão atual.
    Não faz commit — deve ser chamada antes do commit da transação principal.
    """
    log = models.AuditLog(
        usuario_id=usuario_id,
        usuario_nome=usuario_nome,
        area=area,
        acao=acao,
        registro_id=str(registro_id) if registro_id is not None else None,
        registro_descricao=(registro_descricao or "")[:500] or None,
        detalhe=detalhe,
    )
    db.add(log)


def limpar_logs_antigos(db: Session, dias: int = 30) -> int:
    """
    Remove entradas de audit_log com mais de `dias` dias.
    Chamado automaticamente na inicialização da aplicação.
    Retorna a quantidade de registros removidos.
    """
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    n = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.data_hora < limite)
        .delete(synchronize_session=False)
    )
    db.commit()
    return n
