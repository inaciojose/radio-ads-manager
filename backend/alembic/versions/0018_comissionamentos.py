"""comissionamentos: criar tabela de comissionamentos por contrato

Revision ID: 0018_comissionamentos
Revises: 0017_responsaveis
Create Date: 2026-03-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_comissionamentos"
down_revision: Union[str, None] = "0017_responsaveis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comissionamentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contrato_id", sa.Integer(), nullable=False),
        sa.Column("responsavel_id", sa.Integer(), nullable=False),
        sa.Column("percentagem", sa.Float(), nullable=True),
        sa.Column(
            "is_principal",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["contrato_id"], ["contratos.id"]),
        sa.ForeignKeyConstraint(["responsavel_id"], ["responsaveis.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comissionamentos_id", "comissionamentos", ["id"], unique=False)
    op.create_index(
        "ix_comissionamentos_contrato_id", "comissionamentos", ["contrato_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_comissionamentos_contrato_id", table_name="comissionamentos")
    op.drop_index("ix_comissionamentos_id", table_name="comissionamentos")
    op.drop_table("comissionamentos")
