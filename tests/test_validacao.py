"""Validação de entrada — nenhum desses casos chega a disparar job ou tocar banco."""
import pytest


@pytest.mark.parametrize(
    "body,trecho",
    [
        ({}, "informe"),
        ({"inicio": "15/10/2026"}, "formato"),
        ({"inicio": "2026-10-10", "fim": "2026-10-01"}, "antes"),
        ({"inicio": "2026-01-01", "fim": "2026-03-01"}, "31 dias"),
    ],
)
def test_run_custom_invalido(client, auth, body, trecho):
    res = client.post("/api/run/custom", json=body, headers=auth)
    assert res.status_code == 400
    assert trecho in res.get_json()["error"]


def test_run_campanhas_selecionadas_sem_ids(client, auth):
    res = client.post("/api/run/campanhas-selecionadas", json={"ids": []}, headers=auth)
    assert res.status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"data": "2026-10-01", "conta": "x@ativa.ai"},
        {"data": "2026-10-01", "quantidade": 1},
        {"conta": "x@ativa.ai", "quantidade": 1},
        {"data": "2026-10-01", "conta": "x@ativa.ai", "quantidade": "dois"},
        {"data": "01/10/2026", "conta": "x@ativa.ai", "quantidade": 1},
    ],
)
def test_criar_avanco_invalido(client, auth, body):
    res = client.post("/api/avancos", json=body, headers=auth)
    assert res.status_code == 400


def test_analise_cliente_sem_conta(client, auth):
    res = client.get("/api/analise-cliente", headers=auth)
    assert res.status_code == 400
