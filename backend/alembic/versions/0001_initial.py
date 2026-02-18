"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("cnpj_cpf", sa.String(length=18), nullable=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("telefone", sa.String(length=20), nullable=True),
        sa.Column("endereco", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clientes_id", "clientes", ["id"], unique=False)
    op.create_index("ix_clientes_cnpj_cpf", "clientes", ["cnpj_cpf"], unique=True)

    op.create_table(
        "contratos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("numero_contrato", sa.String(length=50), nullable=True),
        sa.Column("data_inicio", sa.Date(), nullable=False),
        sa.Column("data_fim", sa.Date(), nullable=False),
        sa.Column("valor_total", sa.Float(), nullable=True),
        sa.Column("status_contrato", sa.String(length=20), nullable=True),
        sa.Column("status_nf", sa.String(length=20), nullable=True),
        sa.Column("numero_nf", sa.String(length=50), nullable=True),
        sa.Column("data_emissao_nf", sa.Date(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contratos_id", "contratos", ["id"], unique=False)
    op.create_index("ix_contratos_numero_contrato", "contratos", ["numero_contrato"], unique=True)

    op.create_table(
        "arquivos_audio",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=False),
        sa.Column("nome_arquivo", sa.String(length=255), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=True),
        sa.Column("duracao_segundos", sa.Integer(), nullable=True),
        sa.Column("caminho_completo", sa.Text(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=True),
        sa.Column("data_upload", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_arquivos_audio_id", "arquivos_audio", ["id"], unique=False)
    op.create_index("ix_arquivos_audio_nome_arquivo", "arquivos_audio", ["nome_arquivo"], unique=True)

    op.create_table(
        "contrato_itens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contrato_id", sa.Integer(), nullable=False),
        sa.Column("tipo_programa", sa.String(length=50), nullable=False),
        sa.Column("quantidade_contratada", sa.Integer(), nullable=False),
        sa.Column("quantidade_executada", sa.Integer(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["contrato_id"], ["contratos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contrato_itens_id", "contrato_itens", ["id"], unique=False)

    op.create_table(
        "veiculacoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("arquivo_audio_id", sa.Integer(), nullable=False),
        sa.Column("contrato_id", sa.Integer(), nullable=True),
        sa.Column("data_hora", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tipo_programa", sa.String(length=50), nullable=True),
        sa.Column("fonte", sa.String(length=50), nullable=True),
        sa.Column("processado", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["arquivo_audio_id"], ["arquivos_audio.id"]),
        sa.ForeignKeyConstraint(["contrato_id"], ["contratos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_veiculacoes_id", "veiculacoes", ["id"], unique=False)
    op.create_index("ix_veiculacoes_data_hora", "veiculacoes", ["data_hora"], unique=False)
    op.create_index("ix_veiculacoes_processado", "veiculacoes", ["processado"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_veiculacoes_processado", table_name="veiculacoes")
    op.drop_index("ix_veiculacoes_data_hora", table_name="veiculacoes")
    op.drop_index("ix_veiculacoes_id", table_name="veiculacoes")
    op.drop_table("veiculacoes")

    op.drop_index("ix_contrato_itens_id", table_name="contrato_itens")
    op.drop_table("contrato_itens")

    op.drop_index("ix_arquivos_audio_nome_arquivo", table_name="arquivos_audio")
    op.drop_index("ix_arquivos_audio_id", table_name="arquivos_audio")
    op.drop_table("arquivos_audio")

    op.drop_index("ix_contratos_numero_contrato", table_name="contratos")
    op.drop_index("ix_contratos_id", table_name="contratos")
    op.drop_table("contratos")

    op.drop_index("ix_clientes_cnpj_cpf", table_name="clientes")
    op.drop_index("ix_clientes_id", table_name="clientes")
    op.drop_table("clientes")
