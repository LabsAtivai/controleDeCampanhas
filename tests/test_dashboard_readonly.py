"""Smoke SÓ-LEITURA contra o MySQL real (dadoscampanha + relatoriolistas).

Não altera nada no banco:
  - só chama rotas GET (nenhum create_tables/create_all, nenhum job);
  - toda conexão abre com SET SESSION TRANSACTION READ ONLY (o MySQL recusa
    qualquer escrita com erro 1792) e a suíte aborta se @@transaction_read_only != 1
    — necessário porque o usuário do banco também tem permissão de escrita.

Confere formato (contrato do front) e sanidade, não valores.

    TEST_READONLY_DATABASE_URL=<mesma URL de LISTAS_SQUAD_DATABASE_URL> pytest -m readonly_db -v
"""
import os
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url

from contratos import (
    CONTRATO_AVANCO, CONTRATO_CAMPANHA_SQUAD, CONTRATO_CONTA_RESUMO, CONTRATO_DIA_ANALISE, STATUS_AVANCO,
)
from db import dashboard, session as db_session

READONLY_URL = os.environ.get("TEST_READONLY_DATABASE_URL")

pytestmark = [
    pytest.mark.readonly_db,
    pytest.mark.skipif(not READONLY_URL, reason="TEST_READONLY_DATABASE_URL não definida (smoke só-leitura)"),
]

METRICAS = ("totalContacted", "emailsSent", "delivered", "emailOpens", "linkClicks", "emailReplies")


def _engine_somente_leitura(url):
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})

    @event.listens_for(engine, "connect")
    def _sessao_read_only(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
        cursor.close()

    with engine.connect() as conn:
        if conn.execute(text("SELECT @@transaction_read_only")).scalar() != 1:
            engine.dispose()
            pytest.exit("Sessão MySQL não ficou READ ONLY — smoke abortado sem tocar no banco.", returncode=2)
    return engine


@pytest.fixture(scope="module")
def engines():
    cross = _engine_somente_leitura(READONLY_URL)
    principal = _engine_somente_leitura(make_url(READONLY_URL).set(database="dadoscampanha"))
    yield cross, principal
    cross.dispose()
    principal.dispose()


@pytest.fixture
def banco_real(engines, monkeypatch):
    cross, principal = engines
    monkeypatch.setattr(dashboard, "_cross_engine", cross)
    monkeypatch.setattr(db_session, "_engine", principal)


def _metricas_sas(item):
    for campo in METRICAS:
        assert isinstance(item[campo], int) and item[campo] >= 0, (campo, item)


def test_sessao_e_read_only(engines):
    for engine in engines:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT @@transaction_read_only")).scalar() == 1


def test_squads(client, auth, banco_real):
    res = client.get("/api/squads", headers=auth)
    assert res.status_code == 200, res.get_json()
    corpo = res.get_json()
    assert set(corpo) == {"squads", "geradoEm"}
    assert set(corpo["squads"]) == set(dashboard.SQUADS)
    itens = [i for lista in corpo["squads"].values() for i in lista]
    assert itens, "nenhuma campanha mapeada em listas_squad"
    for item in itens:
        assert set(item) == CONTRATO_CAMPANHA_SQUAD
        _metricas_sas(item)


@pytest.mark.parametrize("dias", [None, 7])
def test_analise_contas(client, auth, banco_real, dias):
    rota = "/api/analise-contas"
    if dias:
        rota += f"?inicio={(date.today() - timedelta(days=dias)).isoformat()}&fim={date.today().isoformat()}"
    res = client.get(rota, headers=auth)
    assert res.status_code == 200, res.get_json()
    squads = res.get_json()["squads"]
    assert set(squads) == set(dashboard.SQUADS)
    for contas in squads.values():
        for c in contas:
            assert set(c) == CONTRATO_CONTA_RESUMO
            _metricas_sas(c)
            assert c["statusAvanco"] in STATUS_AVANCO
            assert c["avancos"] >= 0 and c["diasDisparos"] >= 0
            for taxa in ("taxaAbertura", "taxaResposta"):
                assert c[taxa] is None or c[taxa] >= 0, (taxa, c)


def test_analise_cliente(client, auth, banco_real):
    squads = client.get("/api/analise-contas", headers=auth).get_json()["squads"]
    contas = [c["conta"] for lista in squads.values() for c in lista]
    assert contas, "nenhuma conta para analisar"

    inicio = (date.today() - timedelta(days=90)).isoformat()
    res = client.get(f"/api/analise-cliente?conta={contas[0]}&inicio={inicio}&fim={date.today().isoformat()}", headers=auth)
    assert res.status_code == 200, res.get_json()
    dias = res.get_json()["dias"]
    for d in dias:
        assert set(d) == CONTRATO_DIA_ANALISE
        _metricas_sas(d)
    assert [d["data"] for d in dias] == sorted(d["data"] for d in dias)
    for campo in ("cumEmailsSent", "cumEmailOpens", "cumEmailReplies"):
        valores = [d[campo] for d in dias]
        assert valores == sorted(valores), f"{campo} diminuiu"


def test_avancos_listagem(client, auth, banco_real):
    res = client.get("/api/avancos", headers=auth)
    assert res.status_code == 200
    for a in res.get_json():
        assert set(a) == CONTRATO_AVANCO
