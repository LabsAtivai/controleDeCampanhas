"""Gravação das rotinas de extração (crud) e cliente do sistema de credenciais.
Sem rede: httpx é substituído por MockTransport."""
import httpx
import pandas as pd
import pytest
from sqlalchemy.orm import Session

from db import crud, dashboard
from db.models import Dados
from rotina import credentials_api


def _linha(campanha_id, data, **metricas):
    base = {
        "conta": "abluo@ativa.ai", "campanha": "Camp", "id_conta": campanha_id, "data": data,
        "total_contacted": 10, "emails_sent": 10, "delivered": 9,
        "email_opens": 4, "link_clicks": 2, "email_replies": 1,
    }
    base.update(metricas)
    return base


# ---------- crud.atualiza_registros ----------

def test_atualiza_registros_insere_e_grava_cliques(sqlite_db):
    crud.atualiza_registros(pd.DataFrame([_linha("100", "2026-10-01")]))
    with Session(sqlite_db) as s:
        registro = s.query(Dados).one()
    # regressão do commit 911b3d1: chave 'link_clicks' do Snov.io -> coluna links_clicks
    assert registro.links_clicks == 2
    assert (registro.emails_sent, registro.email_replies) == (10, 1)


def test_atualiza_registros_e_upsert_por_campanha_e_data(sqlite_db):
    crud.atualiza_registros(pd.DataFrame([_linha("100", "2026-10-01"), _linha("100", "2026-10-02")]))
    crud.atualiza_registros(pd.DataFrame([_linha("100", "2026-10-01", emails_sent=50, link_clicks=7)]))
    with Session(sqlite_db) as s:
        registros = s.query(Dados).order_by(Dados.data).all()
    assert len(registros) == 2
    assert (registros[0].emails_sent, registros[0].links_clicks) == (50, 7)
    assert registros[1].emails_sent == 10


# ---------- campanhas / contas_snovio ----------

def test_sincroniza_e_lista_campanhas_ativas(sqlite_db):
    cliente = {"id": "acc-1", "email": "abluo@ativa.ai", "email_snovio": "abluo@ativa.ai"}
    campanhas = pd.DataFrame([
        {"id": 1, "campaign": "Ativa", "list_id": 10, "status": "Active"},
        {"id": 2, "campaign": "Pausada", "list_id": 11, "status": "Paused"},
        {"id": None, "campaign": "Sem id", "list_id": 12, "status": "Active"},
    ])
    assert crud.sincroniza_campanhas([(cliente, campanhas)]) == 3

    ativas = crud.get_campanhas_ativas()
    assert list(ativas.columns) == ["id", "campaign", "conta", "status"]
    assert ativas.to_dict("records") == [{"id": 1, "campaign": "Ativa", "conta": "abluo@ativa.ai", "status": "Active"}]

    # rodar de novo atualiza em vez de duplicar
    campanhas.loc[1, "status"] = "Active"
    crud.sincroniza_campanhas([(cliente, campanhas)])
    assert sorted(crud.get_campanhas_ativas()["id"]) == [1, 2]


def test_campanhas_ativas_vazio_mantem_colunas(sqlite_db):
    assert list(crud.get_campanhas_ativas().columns) == ["id", "campaign", "conta", "status"]


# ---------- credentials_api ----------

def _mock_credentials(monkeypatch, total_contas):
    contas = [{"id": f"acc-{i}", "email": f"c{i}@ativa.ai"} for i in range(total_contas)]

    def handler(request: httpx.Request):
        assert request.headers["X-API-Key"] == "chave"
        if request.url.path == "/api/accounts":
            assert request.url.params["status"] == "ACTIVE"
            page = int(request.url.params["page"])
            size = int(request.url.params["page_size"])
            return httpx.Response(200, json={"items": contas[(page - 1) * size: page * size], "total": len(contas)})
        account_id = request.url.path.split("/")[-2]
        return httpx.Response(200, json={
            "snov_id": f"id-{account_id}", "snov_secret": "segredo",
            "snov_email": f"snov-{account_id}@ativa.ai", "snov_password": "senha",
        })

    monkeypatch.setattr(
        credentials_api, "_client",
        lambda: httpx.Client(base_url="http://cred", headers={"X-API-Key": "chave"}, transport=httpx.MockTransport(handler)),
    )


def test_get_active_clients_pagina_e_mapeia(monkeypatch):
    _mock_credentials(monkeypatch, total_contas=150)  # 2 páginas de 100
    clientes = credentials_api.get_active_clients()
    assert len(clientes) == 150
    assert clientes[0] == {
        "id": "acc-0", "email": "c0@ativa.ai", "client_id": "id-acc-0", "client_secret": "segredo",
        "email_snovio": "snov-acc-0@ativa.ai", "senha": "senha",
    }


def test_client_exige_variaveis(monkeypatch):
    monkeypatch.delenv("CREDENTIALS_API_URL", raising=False)
    monkeypatch.delenv("CREDENTIALS_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        credentials_api._client()


def test_rota_clientes_nunca_expoe_segredo(client, auth, monkeypatch):
    _mock_credentials(monkeypatch, total_contas=2)
    corpo = client.get("/api/clientes", headers=auth).get_json()
    assert corpo == [
        {"id": "acc-0", "email": "c0@ativa.ai", "emailSnovio": "snov-acc-0@ativa.ai"},
        {"id": "acc-1", "email": "c1@ativa.ai", "emailSnovio": "snov-acc-1@ativa.ai"},
    ]


# ---------- semáforo de avanço ----------

@pytest.mark.parametrize("soma,esperado", [(0, "vermelho"), (1, "amarelo"), (2, "verde"), (7, "verde")])
def test_status_avanco(soma, esperado):
    assert dashboard._status_avanco(soma) == esperado
