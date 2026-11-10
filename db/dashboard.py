"""Aggregates metrics in the main database; squad mapping never hides accounts."""
import os
import re
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session

from db import avancos_api
from db.models import Dados, SquadMapping
from db.session import engine

SQUADS = ['Onboarding', 'SDR REMOTO', 'Geral', 'Sem squad']
_cross_engine = None

def _mappings():
    global _cross_engine
    if not os.getenv('LISTAS_SQUAD_DATABASE_URL'):
        with Session(engine) as db:
            return {str(r.campanha_id): r.squad for r in db.scalars(select(SquadMapping))}
    def load():
        global _cross_engine
        if _cross_engine is None:
            _cross_engine = create_engine(os.environ['LISTAS_SQUAD_DATABASE_URL'], pool_pre_ping=True,
                pool_recycle=3600, connect_args={'connect_timeout': 5})
        table = os.getenv('SQUAD_MAPPING_TABLE', 'relatoriolistas.listas_squad')
        if not re.fullmatch(r'[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?', table):
            raise ValueError('SQUAD_MAPPING_TABLE inválida.')
        try:
            with _cross_engine.connect() as conn:
                rows = conn.execute(text(f'SELECT campanha_id, squad FROM {table}')).mappings().all()
        except Exception:
            raise avancos_api.IntegrationUnavailable('Mapeamento de squads indisponível.') from None
        mapping = defaultdict(set)
        for row in rows:
            if row['squad']:
                mapping[str(row['campanha_id'])].add(str(row['squad']))
        return {k: next(iter(v)) if len(v) == 1 else 'Geral' for k, v in mapping.items()}
    try:
        return avancos_api._cached('squad_mapping', load)
    except avancos_api.IntegrationUnavailable:
        return {}

def optional(call):
    try:
        return call()
    except avancos_api.IntegrationUnavailable:
        return None

def _client_squads(accounts_campaigns, mapping):
    by_client = defaultdict(set)
    names = {}
    for account, campaign_id in accounts_campaigns:
        name = avancos_api.cliente_da_conta(account)
        names[account] = name
        by_client[name].add(mapping.get(str(campaign_id), 'Sem squad'))
    chosen = {}
    for client, groups in by_client.items():
        mapped = groups - {'Sem squad'}
        chosen[client] = next(iter(mapped)) if len(mapped) == 1 else ('Geral' if mapped else 'Sem squad')
        if 'Sem squad' in groups:
            avancos_api.warn('Existem campanhas sem mapeamento de squad; confira a cobertura.')
    return names, chosen

def get_squads_summary():
    mapping = _mappings()
    with Session(engine) as db:
        latest = select(Dados.id_conta, func.max(Dados.data).label('max_date')).group_by(Dados.id_conta).subquery()
        rows = db.scalars(select(Dados).join(latest,
            (Dados.id_conta == latest.c.id_conta) & (Dados.data == latest.c.max_date))).all()
    names, groups = _client_squads([(r.conta, r.id_conta) for r in rows], mapping)
    today = avancos_api.hoje_sp()
    totals = optional(lambda: avancos_api.total_por_cliente(today.isoformat(), today.isoformat()))
    squads = {s: [] for s in SQUADS}
    for r in rows:
        name = names[r.conta]
        group = groups[name]
        stale = r.data < (today - timedelta(days=1)).isoformat()
        if stale:
            avancos_api.warn('Há campanhas com coleta anterior a ontem; confira as datas individuais.')
        squads.setdefault(group, []).append({
            'cliente': name, 'avancosHoje': totals.get(avancos_api._norm(name), 0) if totals is not None else None,
            'campaignId': r.id_conta, 'campanha': r.campanha, 'conta': r.conta, 'data': r.data,
            'stale': stale, 'totalContacted': r.total_contacted, 'emailsSent': r.emails_sent,
            'delivered': r.delivered, 'emailOpens': r.email_opens, 'linkClicks': r.links_clicks, 'emailReplies': r.email_replies})
    return squads

def get_contas_resumo(inicio=None, fim=None):
    from core.validation import period
    period(inicio, fim)
    mapping = _mappings()
    with Session(engine) as db:
        query = select(Dados.conta, Dados.id_conta, Dados.data,
            func.sum(Dados.total_contacted), func.sum(Dados.emails_sent), func.sum(Dados.delivered),
            func.sum(Dados.email_opens), func.sum(Dados.links_clicks), func.sum(Dados.email_replies))
        if inicio:
            query = query.where(Dados.data >= inicio)
        if fim:
            query = query.where(Dados.data <= fim)
        rows = db.execute(query.group_by(Dados.conta, Dados.id_conta, Dados.data)).all()
    names, groups = _client_squads([(r[0], r[1]) for r in rows], mapping)
    totals = optional(lambda: avancos_api.total_por_cliente(inicio, fim))
    statuses = optional(avancos_api.status_por_cliente)
    clients = {}
    fields = ['totalContacted', 'emailsSent', 'delivered', 'emailOpens', 'linkClicks', 'emailReplies']
    for account, campaign, day, *metrics in rows:
        name = names[account]
        item = clients.setdefault(name, {'cliente': name, 'contas': set(), '_days': set(),
            'ultimaColeta': None, **{k: 0 for k in fields}})
        item['contas'].add(account)
        if (metrics[1] or 0) > 0:
            item['_days'].add(day)
        for key, value in zip(fields, metrics):
            item[key] += int(value or 0)
        item['ultimaColeta'] = max(item['ultimaColeta'] or day, day)
    squads = {s: [] for s in SQUADS}
    for name, item in clients.items():
        item['contas'] = sorted(item['contas'])
        item['diasDisparos'] = len(item.pop('_days'))
        key = avancos_api._norm(name)
        item['avancos'] = totals.get(key, 0) if totals is not None else None
        item['statusAvanco'] = ('indisponivel' if statuses is None else
            statuses.get(key, 'vermelho') if avancos_api.tem_vinculo(name) else 'sem_vinculo')
        for field, label in [('emailOpens', 'taxaAbertura'), ('emailReplies', 'taxaResposta')]:
            item[label] = round(item[field] / item['emailsSent'] * 100, 2) if item['emailsSent'] else None
        squads.setdefault(groups[name], []).append(item)
    return squads
