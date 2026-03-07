"""programas: criar tabela de programas de rádio

Revision ID: 0016_programas
Revises: 0015_veiculacao_motivo
Create Date: 2026-03-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_programas"
down_revision: Union[str, None] = "0015_veiculacao_motivo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "programas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("dias_semana", sa.Text(), nullable=False),
        sa.Column("horario_inicio", sa.String(length=5), nullable=False),
        sa.Column("horario_fim", sa.String(length=5), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="ativo",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nome", name="uq_programas_nome"),
    )
    op.create_index("ix_programas_id", "programas", ["id"], unique=False)
    op.create_index("ix_programas_nome", "programas", ["nome"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_programas_nome", table_name="programas")
    op.drop_index("ix_programas_id", table_name="programas")
    op.drop_table("programas")
