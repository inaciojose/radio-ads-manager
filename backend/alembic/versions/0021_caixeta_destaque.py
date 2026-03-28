"""caixeta_destaque: campo destaque por comercial

Revision ID: 0021_caixeta_destaque
Revises: 0020_caixeta_comercial
Create Date: 2026-03-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_caixeta_destaque"
down_revision: Union[str, None] = "0020_caixeta_comercial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "caixeta_comercial",
        sa.Column("destaque", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("caixeta_comercial", "destaque")
