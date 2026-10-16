import pytest

import server

ROTAS_PROTEGIDAS = [
    ("GET", "/api/status"),
    ("GET", "/api/logs"),
    ("GET", "/api/clientes"),
    ("GET", "/api/squads"),
    ("GET", "/api/avancos"),
    ("POST", "/api/avancos"),
    ("DELETE", "/api/avancos/1"),
    ("GET", "/api/analise-cliente?conta=x@ativa.ai"),
    ("GET", "/api/analise-contas"),
    ("POST", "/api/run/campanhas"),
    ("POST", "/api/run/campanhas-selecionadas"),
    ("POST", "/api/run/dia-anterior"),
    ("POST", "/api/run/custom"),
    ("POST", "/api/run/planilhas"),
]


def test_health_publico(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json() == {"ok": True}


@pytest.mark.parametrize("metodo,rota", ROTAS_PROTEGIDAS)
def test_sem_token_401(client, metodo, rota):
    res = client.open(rota, method=metodo)
    assert res.status_code == 401


@pytest.mark.parametrize("metodo,rota", ROTAS_PROTEGIDAS)
def test_token_errado_401(client, metodo, rota):
    res = client.open(rota, method=metodo, headers={"X-API-Token": "errado"})
    assert res.status_code == 401


def test_servidor_sem_painel_token_500(client, monkeypatch):
    monkeypatch.setattr(server, "API_TOKEN", "")
    res = client.get("/api/status", headers={"X-API-Token": ""})
    assert res.status_code == 500


def test_status_com_token(client, auth):
    res = client.get("/api/status", headers=auth)
    assert res.status_code == 200
    assert set(res.get_json()) == {"running", "action", "started_at", "finished_at", "success", "error"}


def test_cors_headers(client):
    res = client.get("/api/health")
    assert res.headers["Access-Control-Allow-Origin"] == server.FRONTEND_ORIGIN
    assert "X-API-Token" in res.headers["Access-Control-Allow-Headers"]


def test_preflight_options_sem_token(client):
    # Rotas existentes: o Flask responde OPTIONS sozinho (200); o options_handler
    # do server só cobre caminhos sem rota (204). Em ambos o preflight passa sem token.
    for rota, esperado in (("/api/squads", 200), ("/api/rota-que-nao-existe", 204)):
        res = client.options(rota)
        assert res.status_code == esperado
        assert "X-API-Token" in res.headers["Access-Control-Allow-Headers"]
