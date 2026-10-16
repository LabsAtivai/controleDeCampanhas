"""Erros internos não vazam detalhe pro cliente; o traceback vai pro log."""
import logging

import pytest

import server
from conftest import TEST_TOKEN

SEGREDO = "segredo interno"


def _explode(*_args, **_kwargs):
    raise RuntimeError(SEGREDO)


@pytest.mark.parametrize(
    "alvo,funcao,rota",
    [
        (server.credentials_api, "get_active_clients", "/api/clientes"),
        (server.dashboard, "get_squads_summary", "/api/squads"),
        (server.dashboard, "get_contas_resumo", "/api/analise-contas"),
        (server.crud, "get_analise_cliente", "/api/analise-cliente?conta=x@ativa.ai"),
        (server.crud, "lista_avancos", "/api/avancos"),
    ],
)
def test_erro_interno_nao_vaza_detalhe(client, auth, monkeypatch, caplog, alvo, funcao, rota):
    monkeypatch.setattr(alvo, funcao, _explode)

    res = client.get(rota, headers=auth)

    assert res.status_code == 500
    assert res.get_json() == {"error": server.ERRO_INTERNO}
    assert SEGREDO not in res.get_data(as_text=True)
    # o traceback completo fica registrado no log
    assert any(r.exc_text and SEGREDO in r.exc_text for r in caplog.records)


def test_erros_http_padrao_nao_viram_500(client, auth):
    assert client.get("/nao-existe", headers=auth).status_code == 404
    # /api/<path> casa com a rota de OPTIONS, então GET em rota inexistente é 405
    assert client.get("/api/nao-existe", headers=auth).status_code == 405


def test_log_de_acesso_sem_token_nem_query(client, auth, monkeypatch, caplog):
    monkeypatch.setattr(server.crud, "lista_avancos", lambda conta: [])

    with caplog.at_level(logging.DEBUG, logger="painel"):
        client.get("/api/avancos?conta=x@ativa.ai", headers=auth)

    linhas = [r.getMessage() for r in caplog.records if r.name == "painel"]
    assert any("GET /api/avancos 200" in l for l in linhas)
    assert not any(TEST_TOKEN in l or "x@ativa.ai" in l for l in linhas)


def test_polling_loga_em_debug(client, auth, caplog):
    with caplog.at_level(logging.DEBUG, logger="painel"):
        client.get("/api/status", headers=auth)

    registro = next(r for r in caplog.records if r.name == "painel" and "/api/status" in r.getMessage())
    assert registro.levelno == logging.DEBUG
