"""veiculacoes: adiciona coluna motivo_nao_contabilizada

Revision ID: 0015_veiculacao_motivo
Revises: 0014_nf_competencia_ativa
Create Date: 2026-02-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0015_veiculacao_motivo"
down_revision: Union[str, None] = "0014_nf_competencia_ativa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("veiculacoes") as batch_op:
        batch_op.add_column(sa.Column("motivo_nao_contabilizada", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("veiculacoes") as batch_op:
        batch_op.drop_column("motivo_nao_contabilizada")
