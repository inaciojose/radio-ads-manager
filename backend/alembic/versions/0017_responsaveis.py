"""responsaveis: criar tabela e seed de responsáveis especiais

Revision ID: 0017_responsaveis
Revises: 0016_programas
Create Date: 2026-03-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_responsaveis"
down_revision: Union[str, None] = "0016_programas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "responsaveis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("telefone", sa.String(length=20), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="ativo",
            nullable=False,
        ),
        sa.Column("codigo", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo", name="uq_responsaveis_codigo"),
    )
    op.create_index("ix_responsaveis_id", "responsaveis", ["id"], unique=False)

    # Responsáveis especiais com código identificável
    op.execute(
        """
        INSERT INTO responsaveis (nome, status, codigo, created_at)
        VALUES
          ('Lima Jr', 'ativo', 'lima_jr', CURRENT_TIMESTAMP),
          ('Luís Augusto', 'ativo', 'luis_augusto', CURRENT_TIMESTAMP)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_responsaveis_id", table_name="responsaveis")
    op.drop_table("responsaveis")
