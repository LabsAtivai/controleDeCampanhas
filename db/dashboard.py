"""Resumo por squad pro painel visual — cruza dadoscampanha.dados com
relatoriolistas.listas_squad (mesma máquina MySQL, bancos separados).

Usa uma conexão própria (LISTAS_SQUAD_DATABASE_URL) com grant cruzado:
eduardoStorini tem SELECT em dadoscampanha (todo) e em relatoriolistas.listas_squad
(só essa tabela, GRANT mínimo aplicado em produção).
"""
import os

from sqlalchemy import create_engine, text

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
  FROM dados d
  INNER JOIN (
    SELECT id_conta, MAX(data) AS max_data
    FROM dados
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

    squads = {s: [] for s in SQUADS}
    for r in rows:
        squad = r["squad"]
        if squad not in squads:
            continue
        squads[squad].append(
            {
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
FROM dados d
JOIN relatoriolistas.listas_squad ls ON ls.campanha_id = CAST(d.id_conta AS UNSIGNED)
{where}
GROUP BY ls.squad, d.conta
ORDER BY ls.squad, d.conta
"""

_SQL_AVANCOS_BASE = """
SELECT conta, SUM(quantidade) AS total
FROM avancos
{where}
GROUP BY conta
"""


def get_contas_resumo(inicio: str = None, fim: str = None) -> dict:
    """Resumo por conta (cliente) agrupado por squad, somando o período pedido —
    base da tela de análise por cliente. inicio/fim em 'YYYY-MM-DD' (inclusive);
    se ambos None, soma o histórico inteiro ("geral")."""
    engine = _get_engine()
    params = {}
    where_dados = ""
    where_avancos = ""
    if inicio and fim:
        where_dados = "WHERE d.data BETWEEN :inicio AND :fim"
        where_avancos = "WHERE data BETWEEN :inicio AND :fim"
        params = {"inicio": inicio, "fim": fim}

    with engine.connect() as conn:
        rows = conn.execute(text(_SQL_CONTAS_BASE.format(where=where_dados)), params).mappings().all()
        avancos_rows = conn.execute(text(_SQL_AVANCOS_BASE.format(where=where_avancos)), params).mappings().all()

    avancos_por_conta = {r["conta"]: int(r["total"] or 0) for r in avancos_rows}

    squads = {s: [] for s in SQUADS}
    for r in rows:
        squad = r["squad"]
        if squad not in squads:
            continue
        emails_sent = int(r["emails_sent"] or 0)
        email_opens = int(r["email_opens"] or 0)
        email_replies = int(r["email_replies"] or 0)
        squads[squad].append(
            {
                "conta": r["conta"],
                "totalContacted": int(r["total_contacted"] or 0),
                "emailsSent": emails_sent,
                "delivered": int(r["delivered"] or 0),
                "emailOpens": email_opens,
                "linkClicks": int(r["links_clicks"] or 0),
                "emailReplies": email_replies,
                "avancos": avancos_por_conta.get(r["conta"], 0),
                "ultimaColeta": r["ultima_coleta"],
                "diasDisparos": int(r["dias_disparos"] or 0),
                "taxaAbertura": round(email_opens / emails_sent * 100, 2) if emails_sent else None,
                "taxaResposta": round(email_replies / emails_sent * 100, 2) if emails_sent else None,
            }
        )
    return squads
