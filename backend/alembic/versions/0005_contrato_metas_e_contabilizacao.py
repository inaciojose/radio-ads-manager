"""add contract file targets and contabilizada flag

Revision ID: 0005_contrato_metas
Revises: 0004_usuarios_auth
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_contrato_metas"
down_revision: Union[str, None] = "0004_usuarios_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "veiculacoes",
        sa.Column(
            "contabilizada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_index("ix_veiculacoes_contabilizada", "veiculacoes", ["contabilizada"], unique=False)

    op.create_table(
        "contrato_arquivo_metas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contrato_id", sa.Integer(), nullable=False),
        sa.Column("arquivo_audio_id", sa.Integer(), nullable=False),
        sa.Column("quantidade_meta", sa.Integer(), nullable=False),
        sa.Column("quantidade_executada", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("modo_veiculacao", sa.String(length=20), nullable=False, server_default="fixo"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["arquivo_audio_id"], ["arquivos_audio.id"]),
        sa.ForeignKeyConstraint(["contrato_id"], ["contratos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contrato_id", "arquivo_audio_id", name="uq_contrato_arquivo_meta"),
    )
    op.create_index("ix_contrato_arquivo_metas_id", "contrato_arquivo_metas", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_contrato_arquivo_metas_id", table_name="contrato_arquivo_metas")
    op.drop_table("contrato_arquivo_metas")

    op.drop_index("ix_veiculacoes_contabilizada", table_name="veiculacoes")
    op.drop_column("veiculacoes", "contabilizada")
