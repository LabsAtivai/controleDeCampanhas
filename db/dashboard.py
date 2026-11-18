"""Aggregates metrics in the main database; squad mapping never hides accounts."""
import os
import re
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session

from core.config import enabled
from db import avancos_api
from db.models import Dados, SquadMapping, ContaOverride
from db.session import engine

SQUADS = ['Onboarding', 'SDR REMOTO', 'Geral', 'Sem squad']
EXCLUDED = 'Excluídos'
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

def avancos_ativo():
    """Avanços e semáforo ficam fora do painel até AVANCOS_PANEL_ENABLED=true (o código é mantido)."""
    return enabled('AVANCOS_PANEL_ENABLED', False)

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

def _overrides():
    with Session(engine) as db:
        return {r.conta.lower(): (r.squad, bool(r.excluded)) for r in db.scalars(select(ContaOverride))}

def _apply_overrides(names, chosen):
    """Aplica os ajustes manuais do kanban. Troca a equipe do cliente (quando todas as contas
    ajustadas concordam) e devolve o conjunto de clientes ocultos (todas as contas excluídas)."""
    overrides = _overrides()
    if not overrides:
        return set()
    accounts_of = defaultdict(list)
    for account, client in names.items():
        accounts_of[client].append(account.lower())
    hidden = set()
    for client, accounts in accounts_of.items():
        found = [overrides[a] for a in accounts if a in overrides]
        if not found:
            continue
        # Cliente excluído some inteiro: basta uma conta excluída (contas novas dele não reaparecem sozinhas).
        if any(overrides[a][1] for a in accounts if a in overrides):
            hidden.add(client)
        squads = {squad for squad, excluded in found if squad and not excluded}
        if len(squads) == 1:
            chosen[client] = next(iter(squads))
    return hidden

def get_squads_summary(include_excluded=False):
    mapping = _mappings()
    with Session(engine) as db:
        latest = select(Dados.id_conta, func.max(Dados.data).label('max_date')).group_by(Dados.id_conta).subquery()
        rows = db.scalars(select(Dados).join(latest,
            (Dados.id_conta == latest.c.id_conta) & (Dados.data == latest.c.max_date))).all()
    names, groups = _client_squads([(r.conta, r.id_conta) for r in rows], mapping)
    hidden = _apply_overrides(names, groups)
    today = avancos_api.hoje_sp()
    totals = optional(lambda: avancos_api.total_por_cliente(today.isoformat(), today.isoformat())) if avancos_ativo() else None
    squads = {s: [] for s in SQUADS}
    if include_excluded:
        squads[EXCLUDED] = []
    for r in rows:
        name = names[r.conta]
        if name in hidden and not include_excluded:
            continue
        group = EXCLUDED if name in hidden else groups[name]
        stale = r.data < (today - timedelta(days=1)).isoformat()
        if stale:
            avancos_api.warn('Há campanhas com coleta anterior a ontem; confira as datas individuais.')
        squads.setdefault(group, []).append({
            'cliente': name, 'avancosHoje': totals.get(avancos_api._norm(name), 0) if totals is not None else None,
            'campaignId': r.id_conta, 'campanha': r.campanha, 'conta': r.conta, 'data': r.data,
            'stale': stale, 'totalContacted': r.total_contacted, 'emailsSent': r.emails_sent,
            'delivered': r.delivered, 'emailOpens': r.email_opens, 'linkClicks': r.links_clicks or 0, 'emailReplies': r.email_replies})
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
    hidden = _apply_overrides(names, groups)
    ativo = avancos_ativo()
    totals = optional(lambda: avancos_api.total_por_cliente(inicio, fim)) if ativo else None
    statuses = optional(avancos_api.status_por_cliente) if ativo else None
    clients = {}
    fields = ['totalContacted', 'emailsSent', 'delivered', 'emailOpens', 'linkClicks', 'emailReplies']
    for account, campaign, day, *metrics in rows:
        name = names[account]
        if name in hidden:
            continue
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
        item['statusAvanco'] = None if not ativo else ('indisponivel' if statuses is None else
            statuses.get(key, 'vermelho') if avancos_api.tem_vinculo(name) else 'sem_vinculo')
        for field, label in [('emailOpens', 'taxaAbertura'), ('emailReplies', 'taxaResposta')]:
            item[label] = round(item[field] / item['emailsSent'] * 100, 2) if item['emailsSent'] else None
        squads.setdefault(groups[name], []).append(item)
    return squads


def get_kanban():
    """Clientes por equipe para o quadro de gestão (inclui os excluídos, que podem ser restaurados)."""
    columns = {s: [] for s in SQUADS + [EXCLUDED]}
    for squad, rows in get_squads_summary(include_excluded=True).items():
        clients = {}
        for row in rows:
            item = clients.setdefault(row['cliente'], {'cliente': row['cliente'], 'contas': set(), 'campanhas': 0,
                'emailsSent': 0, 'ultimaColeta': None})
            item['contas'].add(row['conta'])
            item['campanhas'] += 1
            item['emailsSent'] += int(row['emailsSent'] or 0)
            item['ultimaColeta'] = max(item['ultimaColeta'] or row['data'], row['data'])
        columns.setdefault(squad, []).extend(
            {**c, 'contas': sorted(c['contas'])} for c in sorted(clients.values(), key=lambda c: c['cliente'].lower()))
    return columns

def set_override(accounts, squad=None, excluded=None, actor=None):
    """Move (squad) e/ou exclui/restaura (excluded) as contas. Nunca remove dados coletados."""
    from core.time import utcnow
    if squad is not None and squad not in SQUADS:
        raise ValueError('Equipe inválida.')
    accounts = sorted({str(a).strip().lower() for a in accounts if str(a).strip()})
    if not accounts or len(accounts) > 200 or any(len(a) > 255 for a in accounts):
        raise ValueError('Informe de 1 a 200 contas válidas.')
    with Session(engine) as db:
        for account in accounts:
            row = db.get(ContaOverride, account) or ContaOverride(conta=account, excluded=False)
            if squad is not None:
                row.squad = squad
                row.excluded = False
            if excluded is not None:
                row.excluded = excluded
            row.updated_by, row.updated_at = actor, utcnow()
            db.add(row)
        db.commit()
    return accounts
