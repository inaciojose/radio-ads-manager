"""veiculacoes: arquivo_audio_id nullable + nome_arquivo_raw

Permite registrar veiculações de arquivos não cadastrados no sistema.

Revision ID: 0011_arquivo_opcional
Revises: 0010_nf_unica_constraint
Create Date: 2026-02-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_arquivo_opcional"
down_revision: Union[str, None] = "0010_nf_unica_constraint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adiciona coluna para nome bruto do arquivo (para veiculações sem cadastro)
    op.add_column(
        "veiculacoes",
        sa.Column("nome_arquivo_raw", sa.String(length=255), nullable=True),
    )

    # Torna arquivo_audio_id opcional (batch para compatibilidade com SQLite)
    with op.batch_alter_table("veiculacoes") as batch_op:
        batch_op.alter_column(
            "arquivo_audio_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("veiculacoes") as batch_op:
        batch_op.alter_column(
            "arquivo_audio_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    op.drop_column("veiculacoes", "nome_arquivo_raw")
