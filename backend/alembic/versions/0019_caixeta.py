"""caixeta: criar tabelas de grade de comerciais

Revision ID: 0019_caixeta
Revises: 0018_comissionamentos
Create Date: 2026-03-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_caixeta"
down_revision: Union[str, None] = "0018_comissionamentos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "caixeta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(10), nullable=False, unique=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.Column("updated_by", sa.String(120), nullable=True),
    )

    op.create_table(
        "caixeta_bloco",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "caixeta_id",
            sa.Integer(),
            sa.ForeignKey("caixeta.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nome_programa", sa.String(200), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "caixeta_horario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "bloco_id",
            sa.Integer(),
            sa.ForeignKey("caixeta_bloco.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("horario", sa.String(10), nullable=False),
        sa.Column("comerciais", sa.Text(), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("caixeta_horario")
    op.drop_table("caixeta_bloco")
    op.drop_table("caixeta")
