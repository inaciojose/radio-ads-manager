"""add unique index for veiculacoes event identity

Revision ID: 0003_unique_veiculacoes
Revises: 0002_frequencia
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0003_unique_veiculacoes"
down_revision: Union[str, None] = "0002_frequencia"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove duplicidades existentes para permitir criar o índice único.
    op.execute(
        """
        DELETE FROM veiculacoes
        WHERE id IN (
            SELECT id FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY arquivo_audio_id, data_hora, COALESCE(frequencia, '')
                        ORDER BY id
                    ) AS rn
                FROM veiculacoes
            ) duplicadas
            WHERE duplicadas.rn > 1
        )
        """
    )

    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            """
            CREATE UNIQUE INDEX uq_veiculacoes_evento
            ON veiculacoes (arquivo_audio_id, data_hora, IFNULL(frequencia, ''))
            """
        )
    else:
        op.execute(
            """
            CREATE UNIQUE INDEX uq_veiculacoes_evento
            ON veiculacoes (arquivo_audio_id, data_hora, COALESCE(frequencia, ''))
            """
        )


def downgrade() -> None:
    op.drop_index("uq_veiculacoes_evento", table_name="veiculacoes")
