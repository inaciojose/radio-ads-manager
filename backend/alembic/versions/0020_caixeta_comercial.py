"""caixeta_comercial: comerciais individuais com observação por linha

Revision ID: 0020_caixeta_comercial
Revises: 0019_caixeta
Create Date: 2026-03-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_caixeta_comercial"
down_revision: Union[str, None] = "0019_caixeta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cria tabela de comerciais individuais com observação própria
    op.create_table(
        "caixeta_comercial",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "horario_id",
            sa.Integer(),
            sa.ForeignKey("caixeta_horario.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(300), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
    )

    # Remove colunas que foram substituídas pela nova estrutura
    op.drop_column("caixeta_horario", "comerciais")
    op.drop_column("caixeta_bloco", "observacao")


def downgrade() -> None:
    op.add_column("caixeta_bloco", sa.Column("observacao", sa.Text(), nullable=True))
    op.add_column("caixeta_horario", sa.Column("comerciais", sa.Text(), nullable=True))
    op.drop_table("caixeta_comercial")
