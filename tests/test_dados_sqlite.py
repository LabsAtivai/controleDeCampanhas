"""Rotas de dados que usam só ORM (rodam em SQLite): avanços e análise por cliente.
As chaves conferidas aqui são o contrato que o painel-frontend consome."""
from contratos import CONTRATO_AVANCO, CONTRATO_DIA_ANALISE
from db import crud
from db.models import Dados


def _dado(conta, campanha_id, data, enviados, abertos=0, respostas=0, cliques=0):
    return Dados(
        conta=conta, campanha=f"camp {campanha_id}", id_conta=str(campanha_id), data=data,
        total_contacted=enviados, emails_sent=enviados, delivered=enviados,
        email_opens=abertos, links_clicks=cliques, email_replies=respostas,
    )


# ---------- avanços ----------

def test_avancos_crud_completo(client, auth, sqlite_db):
    criado = client.post(
        "/api/avancos", json={"data": "2026-10-01", "conta": "abluo@ativa.ai", "quantidade": "3"}, headers=auth
    )
    assert criado.status_code == 201
    corpo = criado.get_json()
    assert set(corpo) == CONTRATO_AVANCO
    assert corpo["quantidade"] == 3

    client.post("/api/avancos", json={"data": "2026-10-02", "conta": "outro@ativa.ai", "quantidade": 1}, headers=auth)

    todos = client.get("/api/avancos", headers=auth).get_json()
    assert [a["data"] for a in todos] == ["2026-10-02", "2026-10-01"]  # mais recente primeiro

    filtrado = client.get("/api/avancos?conta=abluo@ativa.ai", headers=auth).get_json()
    assert len(filtrado) == 1 and filtrado[0]["conta"] == "abluo@ativa.ai"

    assert client.delete(f"/api/avancos/{corpo['id']}", headers=auth).get_json() == {"deleted": True}
    assert client.delete(f"/api/avancos/{corpo['id']}", headers=auth).status_code == 404


# ---------- análise por cliente ----------

def _seed_analise(engine):
    from sqlalchemy.orm import Session

    with Session(engine) as s:
        s.add_all([
            _dado("abluo@ativa.ai", 1, "2026-10-01", 10, abertos=4, respostas=1),
            _dado("abluo@ativa.ai", 2, "2026-10-01", 5, abertos=1),
            _dado("abluo@ativa.ai", 1, "2026-10-03", 20, abertos=8, respostas=2, cliques=3),
            _dado("outro@ativa.ai", 9, "2026-10-01", 999),
        ])
        s.commit()
    crud.cria_avanco("2026-10-02", "abluo@ativa.ai", 2)  # dia sem disparo, só avanço
    crud.cria_avanco("2026-10-03", "abluo@ativa.ai", 1)


def test_analise_cliente_soma_campanhas_e_acumula(client, auth, sqlite_db):
    _seed_analise(sqlite_db)

    res = client.get("/api/analise-cliente?conta=abluo@ativa.ai", headers=auth)
    assert res.status_code == 200
    corpo = res.get_json()
    assert corpo["conta"] == "abluo@ativa.ai"

    dias = corpo["dias"]
    assert [d["data"] for d in dias] == ["2026-10-01", "2026-10-02", "2026-10-03"]
    for d in dias:
        assert set(d) == CONTRATO_DIA_ANALISE

    d1, d2, d3 = dias
    assert (d1["emailsSent"], d1["emailOpens"], d1["emailReplies"], d1["avancos"]) == (15, 5, 1, 0)
    assert (d2["emailsSent"], d2["avancos"]) == (0, 2)
    assert (d3["emailsSent"], d3["linkClicks"], d3["avancos"]) == (20, 3, 1)
    assert (d3["cumEmailsSent"], d3["cumEmailOpens"], d3["cumEmailReplies"]) == (35, 13, 3)


def test_analise_cliente_filtra_periodo(client, auth, sqlite_db):
    _seed_analise(sqlite_db)
    res = client.get("/api/analise-cliente?conta=abluo@ativa.ai&inicio=2026-10-02&fim=2026-10-03", headers=auth)
    dias = res.get_json()["dias"]
    assert [d["data"] for d in dias] == ["2026-10-02", "2026-10-03"]
    assert dias[-1]["cumEmailsSent"] == 20  # acumulado reinicia dentro do período


def test_analise_cliente_conta_inexistente(client, auth, sqlite_db):
    res = client.get("/api/analise-cliente?conta=ninguem@ativa.ai", headers=auth)
    assert res.get_json() == {"conta": "ninguem@ativa.ai", "dias": []}
