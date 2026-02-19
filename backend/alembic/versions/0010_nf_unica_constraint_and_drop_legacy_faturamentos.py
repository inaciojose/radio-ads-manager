"""enforce unica nf per contrato and drop legacy monthly table

Revision ID: 0010_nf_unica_constraint
Revises: 0009_api_keys_service
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_nf_unica_constraint"
down_revision: Union[str, None] = "0009_api_keys_service"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_notas_fiscais_unica_por_contrato",
        "notas_fiscais",
        ["contrato_id"],
        unique=True,
        postgresql_where=sa.text("tipo = 'unica'"),
        sqlite_where=sa.text("tipo = 'unica'"),
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "contrato_faturamentos_mensais" in tables:
        indexes = {idx["name"] for idx in inspector.get_indexes("contrato_faturamentos_mensais")}
        for idx_name in [
            "ix_contrato_faturamentos_mensais_competencia",
            "ix_contrato_faturamentos_mensais_contrato_id",
            "ix_contrato_faturamentos_mensais_id",
        ]:
            if idx_name in indexes:
                op.drop_index(idx_name, table_name="contrato_faturamentos_mensais")
        op.drop_table("contrato_faturamentos_mensais")


def downgrade() -> None:
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
        sa.UniqueConstraint("contrato_id", "competencia", name="uq_contrato_faturamento_competencia"),
    )
    op.create_index("ix_contrato_faturamentos_mensais_id", "contrato_faturamentos_mensais", ["id"], unique=False)
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

    op.drop_index("uq_notas_fiscais_unica_por_contrato", table_name="notas_fiscais")
