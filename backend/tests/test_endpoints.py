from datetime import date, datetime
import os

import pytest
from fastapi import HTTPException

# Mantém os testes independentes do banco de runtime.
os.environ["DATABASE_URL"] = "sqlite:///./test_radio_ads.db"

from app import models, schemas
from app.auth import hash_password
from app.database import Base, SessionLocal, engine, init_db
from app.main import health_check
from app.routers import auth as auth_router
from app.routers import clientes as clientes_router
from app.routers import contratos as contratos_router
from app.routers import veiculacoes as veiculacoes_router
from log_monitor.monitor import APIClient, Config, ZaraLogParser


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    init_db()
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


def test_login_retorna_usuario_com_campos_completos(db):
    user = models.Usuario(
        username="admin_test",
        nome="Administrador Teste",
        password_hash=hash_password("segredo123"),
        role="admin",
        ativo=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    payload = schemas.LoginRequest(username="admin_test", password="segredo123")
    resposta = auth_router.login(payload, db=db)

    assert resposta["access_token"]
    assert resposta["token_type"] == "bearer"
    assert isinstance(resposta["usuario"], models.Usuario)
    assert resposta["usuario"].created_at is not None


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


def test_zara_em_janela_obs_nao_contabiliza_automaticamente(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente OBS",
            cnpj_cpf="11.111.111/0001-11",
        ),
        db=db,
    )
    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 2, 28),
            frequencia="102.7",
            valor_total=1000,
            itens=[schemas.ContratoItemCreate(tipo_programa="esporte", quantidade_contratada=20)],
        ),
        db=db,
    )
    arquivo = models.ArquivoAudio(
        cliente_id=cliente.id,
        nome_arquivo="obs_video_spot.mp3",
        titulo="OBS spot",
    )
    db.add(arquivo)
    db.flush()
    db.add(models.Veiculacao(
        arquivo_audio_id=arquivo.id,
        data_hora=datetime(2026, 2, 16, 11, 30, 0),  # segunda-feira
        frequencia="102.7",
        tipo_programa="esporte",
        fonte="zara_log",
        processado=False,
    ))
    db.commit()

    resp = veiculacoes_router.processar_veiculacoes(
        data_inicio=date(2026, 2, 16),
        data_fim=date(2026, 2, 16),
        db=db,
    )
    assert resp["success"] is True

    contrato_atualizado = contratos_router.buscar_contrato(contrato.id, db=db)
    assert contrato_atualizado.itens[0].quantidade_executada == 0

    veiculacao = db.query(models.Veiculacao).first()
    assert veiculacao.processado is True
    assert veiculacao.contabilizada is False


def test_meta_por_arquivo_contabiliza_sem_tipo_programa(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Meta Arquivo",
            cnpj_cpf="66.666.666/0001-66",
        ),
        db=db,
    )
    arquivo = models.ArquivoAudio(
        cliente_id=cliente.id,
        nome_arquivo="campanha_a.mp3",
        titulo="Campanha A",
    )
    db.add(arquivo)
    db.commit()
    db.refresh(arquivo)

    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date.today(),
            data_fim=date.today(),
            frequencia="102.7",
            valor_total=500,
            itens=[schemas.ContratoItemCreate(tipo_programa="musical", quantidade_contratada=5)],
            arquivos_metas=[
                schemas.ContratoArquivoMetaCreate(
                    arquivo_audio_id=arquivo.id,
                    quantidade_meta=3,
                    modo_veiculacao="rodizio",
                )
            ],
        ),
        db=db,
    )
    db.add(models.Veiculacao(
        arquivo_audio_id=arquivo.id,
        data_hora=datetime.combine(date.today(), datetime.min.time()).replace(hour=10),
        frequencia="102.7",
        tipo_programa=None,
        fonte="obs_manual",
        processado=False,
        contabilizada=False,
    ))
    db.commit()

    veiculacoes_router.processar_veiculacoes(
        data_inicio=date.today(),
        data_fim=date.today(),
        db=db,
    )

    meta = db.query(models.ContratoArquivoMeta).filter(
        models.ContratoArquivoMeta.contrato_id == contrato.id,
        models.ContratoArquivoMeta.arquivo_audio_id == arquivo.id,
    ).first()
    assert meta is not None
    assert meta.quantidade_executada == 1
    assert contratos_router.buscar_contrato(contrato.id, db=db).itens[0].quantidade_executada == 0


def test_lancamento_lote_manual_cria_sem_duplicar(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Lote",
            cnpj_cpf="77.777.777/0001-77",
        ),
        db=db,
    )
    arquivo = models.ArquivoAudio(
        cliente_id=cliente.id,
        nome_arquivo="lote_obs.mp3",
        titulo="Lote OBS",
    )
    db.add(arquivo)
    db.commit()
    db.refresh(arquivo)

    payload = schemas.VeiculacaoLoteManualCreate(
        arquivo_audio_id=arquivo.id,
        data=date.today(),
        horarios=["11:00", "11:00", "12:30:00", "25:99"],
        frequencia="102.7",
        fonte="obs_manual",
    )
    resp = veiculacoes_router.lancar_veiculacoes_lote(payload, db=db)
    assert resp["success"] is True
    assert resp["detalhes"]["criadas"] == 2
    assert resp["detalhes"]["existentes"] == 1
    assert "25:99" in resp["detalhes"]["horarios_invalidos"]

    total = db.query(models.Veiculacao).count()
    assert total == 2


def test_ingestao_lote_idempotente(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Ingestao",
            cnpj_cpf="78.888.888/0001-78",
        ),
        db=db,
    )
    arquivo = models.ArquivoAudio(
        cliente_id=cliente.id,
        nome_arquivo="lote_ingest.mp3",
        titulo="Lote ingest",
    )
    db.add(arquivo)
    db.commit()
    db.refresh(arquivo)

    evento = schemas.VeiculacaoCreate(
        arquivo_audio_id=arquivo.id,
        data_hora=datetime.now().replace(microsecond=0),
        frequencia="102.7",
        tipo_programa="musical",
        fonte="zara_log",
    )
    resp = veiculacoes_router.ingestao_veiculacoes_lote(
        payload=[evento, evento],
        db=db,
    )

    assert resp["success"] is True
    assert resp["detalhes"]["recebidas"] == 2
    assert resp["detalhes"]["criadas"] == 1
    assert resp["detalhes"]["existentes"] == 1
    assert resp["detalhes"]["falhas"] == 0


def test_atualizar_item_contrato_altera_quantidade(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Item",
            cnpj_cpf="44.444.444/0001-44",
        ),
        db=db,
    )
    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date.today(),
            data_fim=date.today(),
            valor_total=1000,
            itens=[schemas.ContratoItemCreate(tipo_programa="musical", quantidade_contratada=10)],
        ),
        db=db,
    )

    item = contrato.itens[0]
    atualizado = contratos_router.atualizar_item_contrato(
        contrato_id=contrato.id,
        item_id=item.id,
        item_update=schemas.ContratoItemUpdate(
            quantidade_contratada=25,
            tipo_programa="esporte",
        ),
        db=db,
    )
    assert atualizado.quantidade_contratada == 25
    assert atualizado.tipo_programa == "esporte"


def test_criar_contrato_sem_data_fim_com_meta_diaria(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Sem Prazo",
            cnpj_cpf="88.888.888/0001-88",
        ),
        db=db,
    )
    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date.today(),
            data_fim=None,
            valor_total=900,
            itens=[
                schemas.ContratoItemCreate(
                    tipo_programa="musical",
                    quantidade_diaria_meta=6,
                )
            ],
        ),
        db=db,
    )

    assert contrato.data_fim is None
    assert contrato.itens[0].quantidade_contratada is None
    assert contrato.itens[0].quantidade_diaria_meta == 6


def test_processamento_contabiliza_contrato_sem_data_fim(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Vigencia Aberta",
            cnpj_cpf="89.999.999/0001-89",
        ),
        db=db,
    )
    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date(2026, 1, 1),
            data_fim=None,
            valor_total=750,
            itens=[
                schemas.ContratoItemCreate(
                    tipo_programa="jornal",
                    quantidade_contratada=30,
                    quantidade_diaria_meta=2,
                )
            ],
        ),
        db=db,
    )

    arquivo = models.ArquivoAudio(
        cliente_id=cliente.id,
        nome_arquivo="spot_sem_fim.mp3",
        titulo="Spot sem fim",
    )
    db.add(arquivo)
    db.flush()
    db.add(models.Veiculacao(
        arquivo_audio_id=arquivo.id,
        data_hora=datetime(2026, 2, 16, 9, 0, 0),
        tipo_programa="jornal",
        fonte="obs_manual",
        processado=False,
    ))
    db.commit()

    resp = veiculacoes_router.processar_veiculacoes(
        data_inicio=date(2026, 2, 16),
        data_fim=date(2026, 2, 16),
        db=db,
    )
    assert resp["success"] is True

    contrato_atualizado = contratos_router.buscar_contrato(contrato.id, db=db)
    assert contrato_atualizado.itens[0].quantidade_executada == 1


def test_resumo_meta_diaria_hoje(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Meta Hoje",
            cnpj_cpf="90.000.000/0001-90",
        ),
        db=db,
    )
    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date.today(),
            data_fim=None,
            valor_total=400,
            itens=[
                schemas.ContratoItemCreate(
                    tipo_programa="musical",
                    quantidade_contratada=20,
                    quantidade_diaria_meta=4,
                )
            ],
        ),
        db=db,
    )

    arquivo = models.ArquivoAudio(
        cliente_id=cliente.id,
        nome_arquivo="spot_meta_hoje.mp3",
        titulo="Spot meta hoje",
    )
    db.add(arquivo)
    db.flush()
    db.add(models.Veiculacao(
        arquivo_audio_id=arquivo.id,
        contrato_id=contrato.id,
        data_hora=datetime.combine(date.today(), datetime.min.time()).replace(hour=10),
        tipo_programa="musical",
        fonte="obs_manual",
        processado=True,
        contabilizada=True,
    ))
    db.commit()

    resumo = contratos_router.resumo_meta_diaria_hoje(db=db)
    assert resumo["meta_diaria_total"] == 4
    assert resumo["executadas_hoje"] == 1
    assert resumo["percentual_cumprimento"] == 25.0


def test_listar_contratos_com_busca_por_cliente(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Busca Especial",
            cnpj_cpf="55.555.555/0001-55",
        ),
        db=db,
    )
    contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date.today(),
            data_fim=date.today(),
            valor_total=500,
            itens=[schemas.ContratoItemCreate(tipo_programa="musical", quantidade_contratada=5)],
        ),
        db=db,
    )

    encontrados = contratos_router.listar_contratos(
        skip=0,
        limit=20,
        cliente_id=None,
        status_contrato=None,
        status_nf=None,
        frequencia=None,
        busca="Especial",
        db=db,
    )
    assert len(encontrados) == 1
    assert encontrados[0].cliente_id == cliente.id


def test_criar_veiculacao_idempotente_nao_duplica_registro(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Idempotencia",
            cnpj_cpf="22.222.222/0001-22",
        ),
        db=db,
    )

    arquivo = models.ArquivoAudio(
        cliente_id=cliente.id,
        nome_arquivo="spot_idempotente.mp3",
        titulo="Spot idempotente",
    )
    db.add(arquivo)
    db.flush()

    payload = schemas.VeiculacaoCreate(
        arquivo_audio_id=arquivo.id,
        data_hora=datetime.now(),
        frequencia="102.7",
        tipo_programa="musical",
        fonte="zara_log",
    )

    primeira = veiculacoes_router.criar_veiculacao(payload, db=db)
    segunda = veiculacoes_router.criar_veiculacao(payload, db=db)

    assert primeira.id == segunda.id
    total = db.query(models.Veiculacao).count()
    assert total == 1


def test_deletar_veiculacao_processada_reverte_contador(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Delecao",
            cnpj_cpf="33.333.333/0001-33",
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
        nome_arquivo="spot_delete.mp3",
        titulo="Spot delete",
        duracao_segundos=30,
    )
    db.add(arquivo)
    db.flush()

    veiculacao = veiculacoes_router.criar_veiculacao(
        schemas.VeiculacaoCreate(
            arquivo_audio_id=arquivo.id,
            data_hora=datetime.now(),
            tipo_programa="musical",
            fonte="teste",
        ),
        db=db,
    )

    veiculacoes_router.processar_veiculacoes(
        data_inicio=date.today(),
        data_fim=date.today(),
        db=db,
    )
    assert contratos_router.buscar_contrato(contrato.id, db=db).itens[0].quantidade_executada == 1

    resposta_delete = veiculacoes_router.deletar_veiculacao(veiculacao.id, db=db)
    assert resposta_delete["success"] is True

    contrato_atualizado = contratos_router.buscar_contrato(contrato.id, db=db)
    assert contrato_atualizado.itens[0].quantidade_executada == 0


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


def test_processamento_respeita_frequencia_contrato(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Frequencia",
            cnpj_cpf="11.111.111/0001-11",
        ),
        db=db,
    )

    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date.today(),
            data_fim=date.today(),
            frequencia="102.7",
            valor_total=1000,
            itens=[schemas.ContratoItemCreate(tipo_programa="musical", quantidade_contratada=10)],
        ),
        db=db,
    )

    arquivo = models.ArquivoAudio(
        cliente_id=cliente.id,
        nome_arquivo="spot_freq.mp3",
        titulo="Spot freq",
    )
    db.add(arquivo)
    db.flush()

    veiculacao = models.Veiculacao(
        arquivo_audio_id=arquivo.id,
        data_hora=datetime.now(),
        frequencia="104.7",
        tipo_programa="musical",
        fonte="teste",
    )
    db.add(veiculacao)
    db.commit()

    veiculacoes_router.processar_veiculacoes(
        data_inicio=date.today(),
        data_fim=date.today(),
        db=db,
    )

    contrato_atualizado = contratos_router.buscar_contrato(contrato.id, db=db)
    assert contrato_atualizado.itens[0].quantidade_executada == 0


def test_parser_linha_real_com_pasta_chamadas():
    config = Config()
    parser = ZaraLogParser(config)
    base_date = datetime(2026, 2, 16)
    line = (
        "06:42:47\tInício\tMain\tdefault\t"
        r"J:\AZARASTUDIO\CHAMADAS\(59) PARAISO HOTEL FAMILIAR (17-10-14).mp3"
    )

    parsed = parser.parse_line(line, base_date, "102.7")
    assert parsed is not None
    assert parsed["nome_arquivo"] == "(59) PARAISO HOTEL FAMILIAR (17-10-14).mp3"
    assert parsed["frequencia"] == "102.7"


def test_parser_ignora_evento_interrompido():
    config = Config()
    parser = ZaraLogParser(config)
    base_date = datetime(2026, 2, 16)
    line = (
        "06:42:47\tInterrompido\tMain\tdefault\t"
        r"J:\AZARASTUDIO\CHAMADAS\SPOT_CLIENTE.mp3"
    )

    parsed = parser.parse_line(line, base_date, "102.7")
    assert parsed is None


def test_criar_e_listar_faturamento_mensal_contrato(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Faturamento",
            cnpj_cpf="10.101.010/0001-10",
        ),
        db=db,
    )
    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date(2026, 1, 10),
            data_fim=None,
            valor_total=1200,
            itens=[
                schemas.ContratoItemCreate(
                    tipo_programa="musical",
                    quantidade_contratada=10,
                    quantidade_diaria_meta=1,
                )
            ],
        ),
        db=db,
    )

    faturamento = contratos_router.criar_faturamento_mensal_contrato(
        contrato_id=contrato.id,
        payload=schemas.ContratoFaturamentoMensalCreate(
            competencia=date(2026, 2, 1),
            status_nf="pendente",
            valor_cobrado=1200,
        ),
        db=db,
    )
    assert faturamento.competencia == date(2026, 2, 1)
    assert faturamento.status_nf == "pendente"

    encontrados = contratos_router.listar_faturamentos_mensais_contrato(
        contrato_id=contrato.id,
        competencia="2026-02",
        status_nf=None,
        db=db,
    )
    assert len(encontrados) == 1
    assert encontrados[0].id == faturamento.id


def test_emitir_nf_mensal_cria_on_demand(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Emissao Mensal",
            cnpj_cpf="20.202.020/0001-20",
        ),
        db=db,
    )
    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date(2026, 1, 1),
            data_fim=None,
            valor_total=2200,
            itens=[
                schemas.ContratoItemCreate(
                    tipo_programa="jornal",
                    quantidade_contratada=20,
                    quantidade_diaria_meta=1,
                )
            ],
        ),
        db=db,
    )

    emitido = contratos_router.emitir_nota_fiscal_mensal_contrato(
        contrato_id=contrato.id,
        competencia="2026-03",
        payload=schemas.EmitirNotaFiscalMensalRequest(
            numero_nf="NF-2026-03-0001",
            valor_cobrado=2200,
        ),
        db=db,
    )
    assert emitido.competencia == date(2026, 3, 1)
    assert emitido.status_nf == "emitida"
    assert emitido.numero_nf == "NF-2026-03-0001"


def test_competencia_invalida_retorna_400(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Competencia",
            cnpj_cpf="30.303.030/0001-30",
        ),
        db=db,
    )
    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date(2026, 1, 1),
            data_fim=None,
            valor_total=1500,
            itens=[
                schemas.ContratoItemCreate(
                    tipo_programa="esporte",
                    quantidade_contratada=15,
                    quantidade_diaria_meta=1,
                )
            ],
        ),
        db=db,
    )

    with pytest.raises(HTTPException) as excinfo:
        contratos_router.listar_faturamentos_mensais_contrato(
            contrato_id=contrato.id,
            competencia="2026-13",
            status_nf=None,
            db=db,
        )
    assert excinfo.value.status_code == 400


def test_criar_nota_fiscal_unica_sincroniza_resumo_contrato(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente NF Unica",
            cnpj_cpf="31.313.131/0001-31",
        ),
        db=db,
    )
    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 2, 1),
            nf_dinamica="unica",
            itens=[
                schemas.ContratoItemCreate(
                    tipo_programa="musical",
                    quantidade_contratada=10,
                )
            ],
        ),
        db=db,
    )

    nota = contratos_router.criar_nota_fiscal_contrato(
        contrato_id=contrato.id,
        payload=schemas.NotaFiscalCreate(
            tipo="unica",
            status="emitida",
            numero="NF-UNICA-001",
            data_emissao=date(2026, 1, 20),
            valor=1000,
        ),
        db=db,
    )
    assert nota.tipo == "unica"
    assert nota.status == "emitida"

    contrato_atualizado = contratos_router.buscar_contrato(contrato.id, db=db)
    assert contrato_atualizado.status_nf == "emitida"
    assert contrato_atualizado.numero_nf == "NF-UNICA-001"
    assert contrato_atualizado.data_emissao_nf == date(2026, 1, 20)


def test_criar_nota_mensal_em_contrato_unico_retorna_400(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente NF Erro Tipo",
            cnpj_cpf="32.323.232/0001-32",
        ),
        db=db,
    )
    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 2, 1),
            nf_dinamica="unica",
            itens=[
                schemas.ContratoItemCreate(
                    tipo_programa="jornal",
                    quantidade_contratada=5,
                )
            ],
        ),
        db=db,
    )

    with pytest.raises(HTTPException) as excinfo:
        contratos_router.criar_nota_fiscal_contrato(
            contrato_id=contrato.id,
            payload=schemas.NotaFiscalCreate(
                tipo="mensal",
                competencia=date(2026, 1, 1),
                status="pendente",
            ),
            db=db,
        )
    assert excinfo.value.status_code == 400


def test_contrato_fechado_exige_meta_total(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Fechado",
            cnpj_cpf="40.404.040/0001-40",
        ),
        db=db,
    )

    with pytest.raises(HTTPException) as excinfo:
        contratos_router.criar_contrato(
            schemas.ContratoCreate(
                cliente_id=cliente.id,
                data_inicio=date(2026, 1, 1),
                data_fim=date(2026, 2, 1),
                valor_total=1000,
                itens=[
                    schemas.ContratoItemCreate(
                        tipo_programa="musical",
                        quantidade_diaria_meta=2,
                    )
                ],
            ),
            db=db,
        )
    assert excinfo.value.status_code == 400


def test_contrato_recorrente_exige_meta_diaria(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Recorrente",
            cnpj_cpf="50.505.050/0001-50",
        ),
        db=db,
    )

    with pytest.raises(HTTPException) as excinfo:
        contratos_router.criar_contrato(
            schemas.ContratoCreate(
                cliente_id=cliente.id,
                data_inicio=date(2026, 1, 1),
                data_fim=None,
                valor_total=1000,
                itens=[
                    schemas.ContratoItemCreate(
                        tipo_programa="jornal",
                        quantidade_contratada=10,
                    )
                ],
            ),
            db=db,
        )
    assert excinfo.value.status_code == 400


def test_processamento_sem_tipo_programa_em_item_unico_contabiliza(db):
    cliente = clientes_router.criar_cliente(
        schemas.ClienteCreate(
            nome="Cliente Sem Tipo",
            cnpj_cpf="60.606.060/0001-60",
        ),
        db=db,
    )
    contrato = contratos_router.criar_contrato(
        schemas.ContratoCreate(
            cliente_id=cliente.id,
            data_inicio=date.today(),
            data_fim=date.today(),
            valor_total=900,
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
        nome_arquivo="spot_sem_tipo.mp3",
        titulo="Spot sem tipo",
    )
    db.add(arquivo)
    db.flush()
    db.add(models.Veiculacao(
        arquivo_audio_id=arquivo.id,
        data_hora=datetime.now(),
        tipo_programa=None,
        fonte="obs_manual",
        processado=False,
    ))
    db.commit()

    resp = veiculacoes_router.processar_veiculacoes(
        data_inicio=date.today(),
        data_fim=date.today(),
        db=db,
    )
    assert resp["success"] is True

    contrato_atualizado = contratos_router.buscar_contrato(contrato.id, db=db)
    assert contrato_atualizado.itens[0].quantidade_executada == 1
