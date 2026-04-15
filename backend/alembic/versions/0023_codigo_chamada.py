"""0023_codigo_chamada

Revision ID: 0023
Revises: 0022_audit_log
Create Date: 2026-04-14

Adiciona:
- clientes.codigo_chamada  (Integer, unique, nullable)
- veiculacoes.cliente_id   (FK → clientes, nullable)
- veiculacoes.codigo_chamada_raw (Integer, nullable) — número extraído do nome do arquivo
- veiculacoes.status_chamada (String(10), nullable) — 'verde'|'vermelho'|'amarelo'
- caixeta_comercial.codigo_chamada (Integer, nullable)
"""

from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022_audit_log"
branch_labels = None
depends_on = None


def upgrade():
    # clientes: código identificador da chamada
    with op.batch_alter_table("clientes") as batch_op:
        batch_op.add_column(sa.Column("codigo_chamada", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint("uq_clientes_codigo_chamada", ["codigo_chamada"])
        batch_op.create_index("ix_clientes_codigo_chamada", ["codigo_chamada"])

    # veiculacoes: vínculo direto com cliente + campos do novo fluxo
    with op.batch_alter_table("veiculacoes") as batch_op:
        batch_op.add_column(sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=True))
        batch_op.add_column(sa.Column("codigo_chamada_raw", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("status_chamada", sa.String(10), nullable=True))
        batch_op.create_index("ix_veiculacoes_cliente_id", ["cliente_id"])
        batch_op.create_index("ix_veiculacoes_codigo_chamada_raw", ["codigo_chamada_raw"])

    # caixeta_comercial: código para cruzamento com veiculações
    with op.batch_alter_table("caixeta_comercial") as batch_op:
        batch_op.add_column(sa.Column("codigo_chamada", sa.Integer(), nullable=True))
        batch_op.create_index("ix_caixeta_comercial_codigo_chamada", ["codigo_chamada"])


def downgrade():
    with op.batch_alter_table("caixeta_comercial") as batch_op:
        batch_op.drop_index("ix_caixeta_comercial_codigo_chamada")
        batch_op.drop_column("codigo_chamada")

    with op.batch_alter_table("veiculacoes") as batch_op:
        batch_op.drop_index("ix_veiculacoes_codigo_chamada_raw")
        batch_op.drop_index("ix_veiculacoes_cliente_id")
        batch_op.drop_column("status_chamada")
        batch_op.drop_column("codigo_chamada_raw")
        batch_op.drop_column("cliente_id")

    with op.batch_alter_table("clientes") as batch_op:
        batch_op.drop_index("ix_clientes_codigo_chamada")
        batch_op.drop_constraint("uq_clientes_codigo_chamada", type_="unique")
        batch_op.drop_column("codigo_chamada")
