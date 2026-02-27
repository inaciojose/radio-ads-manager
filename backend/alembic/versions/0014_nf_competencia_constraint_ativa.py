"""notas_fiscais: converte uq_nota_fiscal_competencia para partial index excluindo canceladas

O UniqueConstraint anterior (sem filtro) bloqueava criar uma nova NF para o mesmo
contrato/tipo/competencia mesmo quando a NF existente estava cancelada.
O novo partial index so considera NFs com status != 'cancelada'.

Revision ID: 0014_nf_competencia_ativa
Revises: 0013_nf_unica_ativa
Create Date: 2026-02-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014_nf_competencia_ativa"
down_revision: Union[str, None] = "0013_nf_unica_ativa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove UniqueConstraint incondicional (bloqueia NFs canceladas)
    with op.batch_alter_table("notas_fiscais") as batch_op:
        batch_op.drop_constraint("uq_nota_fiscal_competencia", type_="unique")

    # Recria como partial index: apenas NFs ativas participam da unicidade
    op.create_index(
        "uq_nota_fiscal_competencia_ativa",
        "notas_fiscais",
        ["contrato_id", "tipo", "competencia"],
        unique=True,
        sqlite_where=sa.text("status != 'cancelada'"),
        postgresql_where=sa.text("status != 'cancelada'"),
    )


def downgrade() -> None:
    op.drop_index("uq_nota_fiscal_competencia_ativa", table_name="notas_fiscais")

    with op.batch_alter_table("notas_fiscais") as batch_op:
        batch_op.create_unique_constraint(
            "uq_nota_fiscal_competencia",
            ["contrato_id", "tipo", "competencia"],
        )
