"""Resumo por squad pro painel visual — cruza dadoscampanha.dados com
relatoriolistas.listas_squad (mesma máquina MySQL, bancos separados).

Usa uma conexão própria (LISTAS_SQUAD_DATABASE_URL) com grant cruzado:
eduardoStorini tem SELECT em dadoscampanha (todo) e em relatoriolistas.listas_squad
(só essa tabela, GRANT mínimo aplicado em produção).
"""
import os
from datetime import date

from sqlalchemy import create_engine, text

from db import avancos_api

_cross_engine = None

SQUADS = ["Onboarding", "SDR REMOTO", "Geral"]

_SQL = """
SELECT
  ls.squad,
  latest.id_conta AS campaign_id,
  latest.campanha,
  latest.conta,
  latest.data,
  latest.total_contacted, latest.emails_sent, latest.delivered,
  latest.email_opens, latest.links_clicks, latest.email_replies
FROM (
  SELECT d.*
  FROM dadoscampanha.dados d
  INNER JOIN (
    SELECT id_conta, MAX(data) AS max_data
    FROM dadoscampanha.dados
    GROUP BY id_conta
  ) m ON m.id_conta = d.id_conta AND m.max_data = d.data
) latest
JOIN relatoriolistas.listas_squad ls ON ls.campanha_id = CAST(latest.id_conta AS UNSIGNED)
ORDER BY ls.squad, latest.conta, latest.campanha
"""


def _get_engine():
    global _cross_engine
    if _cross_engine is None:
        url = os.environ.get("LISTAS_SQUAD_DATABASE_URL")
        if not url:
            raise RuntimeError("LISTAS_SQUAD_DATABASE_URL não configurada no ambiente.")
        _cross_engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
    return _cross_engine


def get_squads_summary() -> dict:
    engine = _get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(_SQL)).mappings().all()

    hoje = avancos_api.hoje_sp().isoformat()
    avancos_hoje = avancos_api.total_por_cliente(hoje, hoje)

    squads = {s: [] for s in SQUADS}
    for r in rows:
        squad = r["squad"]
        if squad not in squads:
            continue
        cliente = avancos_api.cliente_da_conta(r["conta"])
        squads[squad].append(
            {
                "cliente": cliente,
                "avancosHoje": avancos_hoje.get(avancos_api._norm(cliente), 0),
                "campaignId": r["campaign_id"],
                "campanha": r["campanha"],
                "conta": r["conta"],
                "data": r["data"],
                "totalContacted": r["total_contacted"],
                "emailsSent": r["emails_sent"],
                "delivered": r["delivered"],
                "emailOpens": r["email_opens"],
                "linkClicks": r["links_clicks"],
                "emailReplies": r["email_replies"],
            }
        )
    return squads


_SQL_CONTAS_BASE = """
SELECT
  ls.squad,
  d.conta,
  SUM(d.total_contacted) AS total_contacted,
  SUM(d.emails_sent) AS emails_sent,
  SUM(d.delivered) AS delivered,
  SUM(d.email_opens) AS email_opens,
  SUM(d.links_clicks) AS links_clicks,
  SUM(d.email_replies) AS email_replies,
  MAX(d.data) AS ultima_coleta,
  COUNT(DISTINCT CASE WHEN d.emails_sent > 0 THEN d.data END) AS dias_disparos
FROM dadoscampanha.dados d
JOIN relatoriolistas.listas_squad ls ON ls.campanha_id = CAST(d.id_conta AS UNSIGNED)
{where}
GROUP BY ls.squad, d.conta
ORDER BY ls.squad, d.conta
"""

def get_contas_resumo(inicio: str = None, fim: str = None) -> dict:
    """Resumo por cliente agrupado por squad, somando o período pedido (e todas as
    contas Snov.io do cliente) — base da tela de análise. inicio/fim em
    'YYYY-MM-DD' (inclusive); se ambos None, soma o histórico inteiro ("geral").
    Avanços e semáforo vêm do sistema de avanços (ver avancos_api)."""
    engine = _get_engine()
    params = {}
    where_dados = ""
    if inicio and fim:
        where_dados = "WHERE d.data BETWEEN :inicio AND :fim"
        params = {"inicio": inicio, "fim": fim}

    with engine.connect() as conn:
        rows = conn.execute(text(_SQL_CONTAS_BASE.format(where=where_dados)), params).mappings().all()

    avancos_periodo = avancos_api.total_por_cliente(inicio, fim)
    status_clientes = avancos_api.status_por_cliente()

    squads = {s: {} for s in SQUADS}
    for r in rows:
        squad = r["squad"]
        if squad not in squads:
            continue
        cliente = avancos_api.cliente_da_conta(r["conta"])
        item = squads[squad].setdefault(cliente, {
            "cliente": cliente,
            "contas": [],
            "totalContacted": 0, "emailsSent": 0, "delivered": 0,
            "emailOpens": 0, "linkClicks": 0, "emailReplies": 0,
            "ultimaColeta": None, "diasDisparos": 0,
        })
        item["contas"].append(r["conta"])
        item["totalContacted"] += int(r["total_contacted"] or 0)
        item["emailsSent"] += int(r["emails_sent"] or 0)
        item["delivered"] += int(r["delivered"] or 0)
        item["emailOpens"] += int(r["email_opens"] or 0)
        item["linkClicks"] += int(r["links_clicks"] or 0)
        item["emailReplies"] += int(r["email_replies"] or 0)
        item["diasDisparos"] = max(item["diasDisparos"], int(r["dias_disparos"] or 0))
        if r["ultima_coleta"] and (not item["ultimaColeta"] or r["ultima_coleta"] > item["ultimaColeta"]):
            item["ultimaColeta"] = r["ultima_coleta"]

    saida = {}
    for squad, clientes in squads.items():
        linhas = []
        for item in clientes.values():
            chave = avancos_api._norm(item["cliente"])
            enviados = item["emailsSent"]
            item["avancos"] = avancos_periodo.get(chave, 0)
            item["taxaAbertura"] = round(item["emailOpens"] / enviados * 100, 2) if enviados else None
            item["taxaResposta"] = round(item["emailReplies"] / enviados * 100, 2) if enviados else None
            item["statusAvanco"] = (
                status_clientes.get(chave, "vermelho") if avancos_api.tem_vinculo(item["cliente"]) else "sem_vinculo"
            )
            linhas.append(item)
        saida[squad] = linhas
    return saida
