"""Integração das queries cross-DB do dashboard (/api/squads, /api/analise-contas).

O SQL usa nomes fixos de banco (dadoscampanha., relatoriolistas.) e sintaxe MySQL,
então precisa de um MySQL de teste DESCARTÁVEL:

    TEST_DATABASE_URL=mysql+pymysql://root:password@localhost:3306/

Trava de segurança: se dadoscampanha.dados já existir com linhas e sem a tabela
marcadora _pytest_marker (criada só por esta suíte), a execução é abortada —
isso indica que a URL aponta pra um banco real.
"""
import os
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text

from contratos import CONTRATO_CAMPANHA_SQUAD, CONTRATO_CONTA_RESUMO
from db import dashboard, models

TEST_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.mysql,
    pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL não definida (MySQL de teste)"),
]


@pytest.fixture(scope="module")
def mysql_engine():
    servidor = create_engine(TEST_URL.rstrip("/") + "/")
    with servidor.begin() as conn:
        conn.execute(text("CREATE DATABASE IF NOT EXISTS dadoscampanha"))
        conn.execute(text("CREATE DATABASE IF NOT EXISTS relatoriolistas"))

    banco = create_engine(TEST_URL.rstrip("/") + "/dadoscampanha")
    tabelas = inspect(banco).get_table_names()
    if "dados" in tabelas and "_pytest_marker" not in tabelas:
        with banco.connect() as conn:
            if conn.execute(text("SELECT COUNT(*) FROM dados")).scalar():
                pytest.exit(
                    "TEST_DATABASE_URL aponta pra um banco com dados reais (dadoscampanha.dados "
                    "populada e sem _pytest_marker). Use um MySQL descartável.",
                    returncode=2,
                )

    models.Base.metadata.create_all(bind=banco)
    with servidor.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS dadoscampanha._pytest_marker (id INT)"))
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS relatoriolistas.listas_squad ("
            " id INT AUTO_INCREMENT PRIMARY KEY, campanha_id BIGINT UNSIGNED NOT NULL, squad VARCHAR(100) NOT NULL)"
        ))
    banco.dispose()
    yield servidor
    servidor.dispose()


@pytest.fixture
def cross_db(mysql_engine, monkeypatch):
    with mysql_engine.begin() as conn:
        for tabela in ("dadoscampanha.dados", "dadoscampanha.avancos", "relatoriolistas.listas_squad"):
            conn.execute(text(f"DELETE FROM {tabela}"))
    monkeypatch.setattr(dashboard, "_cross_engine", mysql_engine)
    return mysql_engine


def _insere_dado(conn, conta, campanha_id, data, enviados, abertos=0, respostas=0, cliques=0):
    conn.execute(
        text(
            "INSERT INTO dadoscampanha.dados (conta, campanha, id_conta, data, total_contacted, emails_sent,"
            " delivered, email_opens, links_clicks, email_replies)"
            " VALUES (:conta, :campanha, :id, :data, :env, :env, :env, :ab, :cl, :resp)"
        ),
        {"conta": conta, "campanha": f"camp {campanha_id}", "id": str(campanha_id), "data": data,
         "env": enviados, "ab": abertos, "cl": cliques, "resp": respostas},
    )


def _insere_squad(conn, campanha_id, squad):
    conn.execute(text("INSERT INTO relatoriolistas.listas_squad (campanha_id, squad) VALUES (:c, :s)"),
                 {"c": campanha_id, "s": squad})


def _insere_avanco(conn, data, conta, quantidade):
    conn.execute(
        text("INSERT INTO dadoscampanha.avancos (data, conta, quantidade, criado_em) VALUES (:d, :c, :q, NOW())"),
        {"d": data, "c": conta, "q": quantidade},
    )


def test_squads_traz_ultima_coleta_por_campanha(client, auth, cross_db):
    with cross_db.begin() as conn:
        _insere_dado(conn, "abluo@ativa.ai", 1, "2026-10-01", 10)
        _insere_dado(conn, "abluo@ativa.ai", 1, "2026-10-02", 30, abertos=5)
        _insere_dado(conn, "biocarnes@ativa.ai", 2, "2026-10-02", 7)
        _insere_dado(conn, "fora@ativa.ai", 3, "2026-10-02", 99)  # sem squad mapeada
        _insere_dado(conn, "outra@ativa.ai", 4, "2026-10-02", 99)  # squad fora da lista SQUADS
        _insere_squad(conn, 1, "Onboarding")
        _insere_squad(conn, 2, "SDR REMOTO")
        _insere_squad(conn, 4, "Squad Desconhecida")

    corpo = client.get("/api/squads", headers=auth).get_json()
    assert set(corpo) == {"squads", "geradoEm"}
    squads = corpo["squads"]
    assert set(squads) == set(dashboard.SQUADS)

    (onb,) = squads["Onboarding"]
    assert set(onb) == CONTRATO_CAMPANHA_SQUAD
    assert (onb["data"], onb["emailsSent"], onb["emailOpens"]) == ("2026-10-02", 30, 5)
    assert [c["conta"] for c in squads["SDR REMOTO"]] == ["biocarnes@ativa.ai"]
    assert squads["Geral"] == []


def test_analise_contas_soma_periodo_e_semaforo(client, auth, cross_db):
    hoje = date.today()
    ontem = (hoje - timedelta(days=1)).isoformat()
    antigo = (hoje - timedelta(days=10)).isoformat()
    with cross_db.begin() as conn:
        _insere_dado(conn, "abluo@ativa.ai", 1, antigo, 100, abertos=40, respostas=10)
        _insere_dado(conn, "abluo@ativa.ai", 1, ontem, 100, abertos=10, respostas=0)
        _insere_dado(conn, "abluo@ativa.ai", 5, ontem, 0)  # dia sem disparo não conta em diasDisparos
        _insere_dado(conn, "biocarnes@ativa.ai", 2, ontem, 50)
        _insere_squad(conn, 1, "Onboarding")
        _insere_squad(conn, 5, "Onboarding")
        _insere_squad(conn, 2, "Onboarding")
        _insere_avanco(conn, ontem, "abluo@ativa.ai", 2)      # verde (>=2 nos últimos 3 dias)
        _insere_avanco(conn, antigo, "abluo@ativa.ai", 5)
        _insere_avanco(conn, antigo, "biocarnes@ativa.ai", 9)  # vermelho (nada recente)

    geral = client.get("/api/analise-contas", headers=auth).get_json()["squads"]
    contas = {c["conta"]: c for c in geral["Onboarding"]}
    abluo = contas["abluo@ativa.ai"]
    assert set(abluo) == CONTRATO_CONTA_RESUMO
    assert (abluo["emailsSent"], abluo["emailOpens"], abluo["emailReplies"]) == (200, 50, 10)
    assert (abluo["taxaAbertura"], abluo["taxaResposta"]) == (25.0, 5.0)
    assert (abluo["avancos"], abluo["diasDisparos"], abluo["ultimaColeta"]) == (7, 2, ontem)
    assert abluo["statusAvanco"] == "verde"
    assert contas["biocarnes@ativa.ai"]["statusAvanco"] == "vermelho"

    periodo = client.get(f"/api/analise-contas?inicio={ontem}&fim={hoje.isoformat()}", headers=auth).get_json()["squads"]
    abluo_p = {c["conta"]: c for c in periodo["Onboarding"]}["abluo@ativa.ai"]
    assert (abluo_p["emailsSent"], abluo_p["avancos"], abluo_p["diasDisparos"]) == (100, 2, 1)
    assert abluo_p["statusAvanco"] == "verde"  # janela fixa, independe do período


def test_analise_contas_sem_envio_taxa_nula(client, auth, cross_db):
    with cross_db.begin() as conn:
        _insere_dado(conn, "zerada@ativa.ai", 1, "2026-10-01", 0)
        _insere_squad(conn, 1, "Geral")
    (conta,) = client.get("/api/analise-contas", headers=auth).get_json()["squads"]["Geral"]
    assert conta["taxaAbertura"] is None and conta["taxaResposta"] is None
