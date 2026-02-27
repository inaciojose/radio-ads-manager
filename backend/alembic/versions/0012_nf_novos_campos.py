"""notas_fiscais: novos campos de recibo, valores e pagamento

Renomeia 'valor' para 'valor_bruto' e adiciona numero_recibo, valor_liquido,
valor_pago, forma_pagamento e campanha_agentes.

Revision ID: 0012_nf_novos_campos
Revises: 0011_arquivo_opcional
Create Date: 2026-02-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_nf_novos_campos"
down_revision: Union[str, None] = "0011_arquivo_opcional"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("notas_fiscais") as batch_op:
        # Renomeia 'valor' para 'valor_bruto' (valor total antes de deduções)
        batch_op.alter_column(
            "valor",
            new_column_name="valor_bruto",
            existing_type=sa.Float(),
            nullable=True,
        )
        batch_op.add_column(sa.Column("numero_recibo", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("valor_liquido", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("valor_pago", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("forma_pagamento", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("campanha_agentes", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("notas_fiscais") as batch_op:
        batch_op.drop_column("campanha_agentes")
        batch_op.drop_column("forma_pagamento")
        batch_op.drop_column("valor_pago")
        batch_op.drop_column("valor_liquido")
        batch_op.drop_column("numero_recibo")
        batch_op.alter_column(
            "valor_bruto",
            new_column_name="valor",
            existing_type=sa.Float(),
            nullable=True,
        )
