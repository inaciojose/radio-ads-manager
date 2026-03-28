"""audit_log: tabela de auditoria de ações do sistema

Revision ID: 0022_audit_log
Revises: 0021_caixeta_destaque
Create Date: 2026-03-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_audit_log"
down_revision: Union[str, None] = "0021_caixeta_destaque"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "data_hora",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("usuario_nome", sa.String(120), nullable=True),
        sa.Column("area", sa.String(50), nullable=False),
        sa.Column("acao", sa.String(50), nullable=False),
        sa.Column("registro_id", sa.String(100), nullable=True),
        sa.Column("registro_descricao", sa.String(500), nullable=True),
        sa.Column("detalhe", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_log_data_hora", "audit_log", ["data_hora"])
    op.create_index("ix_audit_log_area", "audit_log", ["area"])
    op.create_index("ix_audit_log_acao", "audit_log", ["acao"])
    op.create_index("ix_audit_log_usuario_id", "audit_log", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_usuario_id", table_name="audit_log")
    op.drop_index("ix_audit_log_acao", table_name="audit_log")
    op.drop_index("ix_audit_log_area", table_name="audit_log")
    op.drop_index("ix_audit_log_data_hora", table_name="audit_log")
    op.drop_table("audit_log")
