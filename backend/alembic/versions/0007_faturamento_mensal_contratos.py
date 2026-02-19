"""add monthly invoicing table for contracts

Revision ID: 0007_faturamento_mensal
Revises: 0006_contrato_meta_diaria
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_faturamento_mensal"
down_revision: Union[str, None] = "0006_contrato_meta_diaria"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contrato_faturamentos_mensais",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contrato_id", sa.Integer(), nullable=False),
        sa.Column("competencia", sa.Date(), nullable=False),
        sa.Column("status_nf", sa.String(length=20), nullable=False, server_default="pendente"),
        sa.Column("numero_nf", sa.String(length=50), nullable=True),
        sa.Column("data_emissao_nf", sa.Date(), nullable=True),
        sa.Column("data_pagamento_nf", sa.Date(), nullable=True),
        sa.Column("valor_cobrado", sa.Float(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contrato_id"], ["contratos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contrato_id",
            "competencia",
            name="uq_contrato_faturamento_competencia",
        ),
    )
    op.create_index(
        "ix_contrato_faturamentos_mensais_id",
        "contrato_faturamentos_mensais",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_contrato_faturamentos_mensais_contrato_id",
        "contrato_faturamentos_mensais",
        ["contrato_id"],
        unique=False,
    )
    op.create_index(
        "ix_contrato_faturamentos_mensais_competencia",
        "contrato_faturamentos_mensais",
        ["competencia"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_contrato_faturamentos_mensais_competencia",
        table_name="contrato_faturamentos_mensais",
    )
    op.drop_index(
        "ix_contrato_faturamentos_mensais_contrato_id",
        table_name="contrato_faturamentos_mensais",
    )
    op.drop_index(
        "ix_contrato_faturamentos_mensais_id",
        table_name="contrato_faturamentos_mensais",
    )
    op.drop_table("contrato_faturamentos_mensais")
