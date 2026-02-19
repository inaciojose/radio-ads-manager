"""add nf dynamics and invoices table

Revision ID: 0008_nf_dinamica_notas
Revises: 0007_faturamento_mensal
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "0008_nf_dinamica_notas"
down_revision: Union[str, None] = "0007_faturamento_mensal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contratos",
        sa.Column("nf_dinamica", sa.String(length=20), nullable=False, server_default="unica"),
    )

    op.create_table(
        "notas_fiscais",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contrato_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False, server_default="unica"),
        sa.Column("competencia", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pendente"),
        sa.Column("numero", sa.String(length=50), nullable=True),
        sa.Column("serie", sa.String(length=20), nullable=True),
        sa.Column("data_emissao", sa.Date(), nullable=True),
        sa.Column("data_pagamento", sa.Date(), nullable=True),
        sa.Column("valor", sa.Float(), nullable=True),
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
            "tipo",
            "competencia",
            name="uq_nota_fiscal_competencia",
        ),
    )
    op.create_index("ix_notas_fiscais_id", "notas_fiscais", ["id"], unique=False)
    op.create_index("ix_notas_fiscais_contrato_id", "notas_fiscais", ["contrato_id"], unique=False)
    op.create_index("ix_notas_fiscais_competencia", "notas_fiscais", ["competencia"], unique=False)

    # Migra NF legada do contrato (modo unico).
    op.execute(
        """
        INSERT INTO notas_fiscais (
            contrato_id, tipo, competencia, status, numero, data_emissao, valor, observacoes
        )
        SELECT
            c.id,
            'unica',
            NULL,
            COALESCE(c.status_nf, 'pendente'),
            c.numero_nf,
            c.data_emissao_nf,
            c.valor_total,
            c.observacoes
        FROM contratos c
        WHERE c.numero_nf IS NOT NULL OR c.data_emissao_nf IS NOT NULL OR c.status_nf IS NOT NULL
        """
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "contrato_faturamentos_mensais" in tables:
        op.execute(
            """
            INSERT INTO notas_fiscais (
                contrato_id, tipo, competencia, status, numero, data_emissao, data_pagamento, valor, observacoes
            )
            SELECT
                f.contrato_id,
                'mensal',
                f.competencia,
                COALESCE(f.status_nf, 'pendente'),
                f.numero_nf,
                f.data_emissao_nf,
                f.data_pagamento_nf,
                f.valor_cobrado,
                f.observacoes
            FROM contrato_faturamentos_mensais f
            """
        )

        # Define dinamica mensal para contratos que possuem historico mensal.
        op.execute(
            """
            UPDATE contratos
            SET nf_dinamica = 'mensal'
            WHERE id IN (SELECT DISTINCT contrato_id FROM contrato_faturamentos_mensais)
            """
        )

    op.execute(text("UPDATE contratos SET nf_dinamica = COALESCE(nf_dinamica, 'unica')"))


def downgrade() -> None:
    op.drop_index("ix_notas_fiscais_competencia", table_name="notas_fiscais")
    op.drop_index("ix_notas_fiscais_contrato_id", table_name="notas_fiscais")
    op.drop_index("ix_notas_fiscais_id", table_name="notas_fiscais")
    op.drop_table("notas_fiscais")
    op.drop_column("contratos", "nf_dinamica")
