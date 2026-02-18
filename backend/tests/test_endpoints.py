from datetime import date, datetime
import os

import pytest

# Mantém os testes independentes do banco de runtime.
os.environ["DATABASE_URL"] = "sqlite:///./test_radio_ads.db"

from app import models, schemas
from app.database import Base, SessionLocal, engine
from app.main import health_check
from app.routers import clientes as clientes_router
from app.routers import contratos as contratos_router
from app.routers import veiculacoes as veiculacoes_router
from log_monitor.monitor import APIClient


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_health_endpoint():
    payload = health_check()
    assert payload["status"] == "healthy"
    assert "database" in payload


def test_criar_e_listar_clientes(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Teste",
            cnpj_cpf="12.345.678/0001-99",
            status="ativo",
        ),
        db=db,
    )

    clientes = clientes_router.listar_clientes(
        skip=0,
        limit=100,
        status="ativo",
        busca=None,
        db=db,
    )
    assert len(clientes) == 1
    assert cliente.id == clientes[0].id
    assert clientes[0].nome == "Cliente Teste"


def test_reprocessamento_force_nao_duplica_contagem(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Contrato",
            cnpj_cpf="98.765.432/0001-10",
        ),
        db=db,
    )

    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date.today(),
            data_fim=date.today(),
            valor_total=1000,
            itens=[
                schemas.ContratoItemCreate(
                    tipo_programa="musical",
                    quantidade_contratada=10,
                )
            ],
        ),
        db=db,
    )

    arquivo = models.ArquivoAudio(
        cliente_id=cliente.id,
        nome_arquivo="spot_cliente.mp3",
        titulo="Spot Cliente",
        duracao_segundos=30,
    )
    db.add(arquivo)
    db.flush()

    veiculacao = models.Veiculacao(
        arquivo_audio_id=arquivo.id,
        data_hora=datetime.now(),
        tipo_programa="musical",
        fonte="teste",
    )
    db.add(veiculacao)
    db.commit()

    processar_1 = veiculacoes_router.processar_veiculacoes(
        data_inicio=date.today(),
        data_fim=date.today(),
        db=db,
    )
    assert processar_1["success"] is True

    contrato_atualizado_1 = contratos_router.buscar_contrato(contrato.id, db=db)
    assert contrato_atualizado_1.itens[0].quantidade_executada == 1

    processar_force = veiculacoes_router.processar_veiculacoes(
        data_inicio=date.today(),
        data_fim=date.today(),
        force=True,
        db=db,
    )
    assert processar_force["success"] is True

    contrato_atualizado_2 = contratos_router.buscar_contrato(contrato.id, db=db)
    assert contrato_atualizado_2.itens[0].quantidade_executada == 1


def test_monitor_busca_arquivo_por_nome_exato():
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return [
                {"id": 1, "nome_arquivo": "spot_cliente_v2.mp3"},
                {"id": 2, "nome_arquivo": "spot_cliente.mp3"},
            ]

    class FakeSession:
        @staticmethod
        def get(*args, **kwargs):
            return FakeResponse()

    api_client = APIClient("http://localhost:8000")
    api_client.session = FakeSession()

    arquivo = api_client.get_arquivo_by_nome("spot_cliente.mp3")
    assert arquivo is not None
    assert arquivo["id"] == 2
