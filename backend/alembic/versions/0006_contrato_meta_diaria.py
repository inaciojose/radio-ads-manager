"""allow open-ended contracts and daily target on contract items

Revision ID: 0006_contrato_meta_diaria
Revises: 0005_contrato_metas
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_contrato_meta_diaria"
down_revision: Union[str, None] = "0005_contrato_metas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("contratos", "data_fim", existing_type=sa.Date(), nullable=True)
    op.add_column("contrato_itens", sa.Column("quantidade_diaria_meta", sa.Integer(), nullable=True))
    op.alter_column(
        "contrato_itens",
        "quantidade_contratada",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "contrato_itens",
        "quantidade_contratada",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_column("contrato_itens", "quantidade_diaria_meta")
    op.alter_column("contratos", "data_fim", existing_type=sa.Date(), nullable=False)
