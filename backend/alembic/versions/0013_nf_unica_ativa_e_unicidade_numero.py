"""notas_fiscais: permite multiplas unicas canceladas e valida unicidade de numero/recibo

Substitui o index parcial que bloqueava uma segunda NF unica no contrato, mesmo
que a anterior estivesse cancelada. O novo index so considera NFs ativas
(status != 'cancelada'), preservando o dado historico das canceladas no banco.

Revision ID: 0013_nf_unica_ativa
Revises: 0012_nf_novos_campos
Create Date: 2026-02-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_nf_unica_ativa"
down_revision: Union[str, None] = "0012_nf_novos_campos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove constraint antiga (qualquer unica por contrato)
    op.drop_index("uq_notas_fiscais_unica_por_contrato", table_name="notas_fiscais")

    # Nova constraint: apenas uma unica ATIVA por contrato (canceladas sao ignoradas)
    op.create_index(
        "uq_notas_fiscais_unica_ativa_por_contrato",
        "notas_fiscais",
        ["contrato_id"],
        unique=True,
        sqlite_where=sa.text("tipo = 'unica' AND status != 'cancelada'"),
        postgresql_where=sa.text("tipo = 'unica' AND status != 'cancelada'"),
    )


def downgrade() -> None:
    op.drop_index("uq_notas_fiscais_unica_ativa_por_contrato", table_name="notas_fiscais")
    op.create_index(
        "uq_notas_fiscais_unica_por_contrato",
        "notas_fiscais",
        ["contrato_id"],
        unique=True,
        sqlite_where=sa.text("tipo = 'unica'"),
        postgresql_where=sa.text("tipo = 'unica'"),
    )
