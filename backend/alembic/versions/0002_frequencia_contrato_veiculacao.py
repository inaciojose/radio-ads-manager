"""add frequencia to contratos and veiculacoes

Revision ID: 0002_frequencia
Revises: 0001_initial
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_frequencia"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contratos", sa.Column("frequencia", sa.String(length=10), nullable=True))
    op.execute("UPDATE contratos SET frequencia = 'ambas' WHERE frequencia IS NULL")

    op.add_column("veiculacoes", sa.Column("frequencia", sa.String(length=10), nullable=True))
    op.create_index("ix_veiculacoes_frequencia", "veiculacoes", ["frequencia"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_veiculacoes_frequencia", table_name="veiculacoes")
    op.drop_column("veiculacoes", "frequencia")
    op.drop_column("contratos", "frequencia")
