"""Disparo de jobs com as rotinas mockadas — nunca chama Snov.io/Sheets."""
import threading
import time

import pytest

import server


def _espera_job_terminar(timeout=5):
    fim = time.time() + timeout
    while time.time() < fim:
        if server.RUN_LOCK.acquire(blocking=False):
            server.RUN_LOCK.release()
            return
        time.sleep(0.01)
    raise AssertionError("job não terminou a tempo")


@pytest.fixture(autouse=True)
def sem_job_pendente():
    yield
    _espera_job_terminar()


def test_lock_impede_job_concorrente(client, auth, monkeypatch):
    liberar = threading.Event()
    monkeypatch.setattr(server.acao, "extrai_campanhas", lambda **_: liberar.wait(5))

    primeiro = client.post("/api/run/campanhas", headers=auth)
    assert primeiro.status_code == 200
    assert primeiro.get_json() == {"started": True}

    segundo = client.post("/api/run/planilhas", headers=auth)
    assert segundo.status_code == 409

    status = client.get("/api/status", headers=auth).get_json()
    assert status["running"] is True
    assert status["action"] == "extrai_campanhas"

    liberar.set()
    _espera_job_terminar()
    status = client.get("/api/status", headers=auth).get_json()
    assert status["running"] is False
    assert status["success"] is True


def test_job_com_erro_registra_falha(client, auth, monkeypatch):
    def explode():
        raise RuntimeError("snov fora do ar")

    monkeypatch.setattr(server.acao, "extrai_dia_anterior", explode)
    assert client.post("/api/run/dia-anterior", headers=auth).status_code == 200
    _espera_job_terminar()

    status = client.get("/api/status", headers=auth).get_json()
    assert status["success"] is False
    assert "snov fora do ar" in status["error"]


def test_campanhas_selecionadas_repassa_ids(client, auth, monkeypatch):
    recebido = {}
    monkeypatch.setattr(server.acao, "extrai_campanhas", lambda ids_selecionados=None: recebido.update(ids=ids_selecionados))

    res = client.post("/api/run/campanhas-selecionadas", json={"ids": ["a", "b", "a"]}, headers=auth)
    assert res.status_code == 200
    _espera_job_terminar()
    assert recebido["ids"] == {"a", "b"}


def test_run_custom_processa_cada_dia(client, auth, monkeypatch):
    dias = []
    monkeypatch.setattr(server.acao, "extrai_dia_anterior_custom", dias.append)

    res = client.post("/api/run/custom", json={"inicio": "2026-09-29", "fim": "2026-10-01"}, headers=auth)
    assert res.status_code == 200
    _espera_job_terminar()
    assert dias == ["2026-09-29", "2026-09-30", "2026-10-01"]


def test_run_custom_so_inicio_processa_um_dia(client, auth, monkeypatch):
    dias = []
    monkeypatch.setattr(server.acao, "extrai_dia_anterior_custom", dias.append)

    assert client.post("/api/run/custom", json={"data": "2026-10-01"}, headers=auth).status_code == 200
    _espera_job_terminar()
    assert dias == ["2026-10-01"]


def test_logs_paginados_por_since(client, auth, monkeypatch):
    monkeypatch.setattr(server, "LOG_BUFFER", server.deque(["l1", "l2", "l3"], maxlen=5000))
    res = client.get("/api/logs?since=1", headers=auth).get_json()
    assert res == {"total": 3, "lines": ["l2", "l3"]}
