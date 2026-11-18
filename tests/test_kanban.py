import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import crud, dashboard
from db.models import AuditEvent, Dados, ContaOverride
from db.session import engine
from tests.test_data_collection import metric
from tests.test_reporting_backup import available


def seed(monkeypatch):
    available(monkeypatch)
    monkeypatch.setattr('db.avancos_api.cliente_da_conta', lambda account: 'Cliente A' if account == 'a@test.example' else 'Cliente B')
    row = metric('200'); row['conta'] = 'b@test.example'
    crud.atualiza_registros(pd.DataFrame([metric(), row]))


def names(squads):
    return {squad: sorted({r['cliente'] for r in rows}) for squad, rows in squads.items() if rows}


def test_move_changes_squad_in_every_view(client, admin, monkeypatch):
    seed(monkeypatch)
    assert names(dashboard.get_squads_summary()) == {'Sem squad': ['Cliente A', 'Cliente B']}
    assert client.post('/api/kanban/mover', json={'contas': ['A@test.example'], 'squad': 'Onboarding'}, headers=admin).status_code == 200
    assert names(dashboard.get_squads_summary()) == {'Onboarding': ['Cliente A'], 'Sem squad': ['Cliente B']}
    assert set(dashboard.get_contas_resumo()) >= {'Onboarding'}
    assert [c['cliente'] for c in dashboard.get_contas_resumo()['Onboarding']] == ['Cliente A']
    with Session(engine) as db:
        assert db.scalars(select(AuditEvent).where(AuditEvent.action == 'kanban.moved')).one().actor == 'admin@example.test'


def test_exclude_hides_without_deleting_and_restore_brings_back(client, admin, monkeypatch):
    seed(monkeypatch)
    assert client.post('/api/kanban/excluir', json={'contas': ['a@test.example']}, headers=admin).status_code == 200
    assert names(dashboard.get_squads_summary()) == {'Sem squad': ['Cliente B']}
    assert 'Cliente A' not in [c['cliente'] for rows in dashboard.get_contas_resumo().values() for c in rows]
    board = client.get('/api/kanban').json
    assert [c['cliente'] for c in board['colunas'][board['excluidos']]] == ['Cliente A']
    with Session(engine) as db:
        assert db.query(Dados).count() == 2  # dados coletados continuam no banco
    assert client.post('/api/kanban/restaurar', json={'contas': ['a@test.example']}, headers=admin).status_code == 200
    assert names(dashboard.get_squads_summary()) == {'Sem squad': ['Cliente A', 'Cliente B']}


def test_moving_an_excluded_client_restores_it(client, admin, monkeypatch):
    seed(monkeypatch)
    client.post('/api/kanban/excluir', json={'contas': ['a@test.example']}, headers=admin)
    client.post('/api/kanban/mover', json={'contas': ['a@test.example'], 'squad': 'Geral'}, headers=admin)
    assert names(dashboard.get_squads_summary())['Geral'] == ['Cliente A']
    with Session(engine) as db:
        assert db.get(ContaOverride, 'a@test.example').excluded is False


def test_kanban_is_admin_only(client, viewer):
    assert client.get('/api/kanban').status_code == 403
    assert client.post('/api/kanban/mover', json={'contas': ['a@test.example'], 'squad': 'Geral'}, headers=viewer).status_code == 403
    assert client.post('/api/kanban/mover', json={'contas': ['a@test.example'], 'squad': 'Inexistente'}, headers=viewer).status_code == 403


def test_kanban_rejects_bad_requests(client, admin):
    for body in ({'contas': [], 'squad': 'Geral'}, {'contas': 'x', 'squad': 'Geral'}, {'contas': ['a@test.example'], 'squad': 'Excluídos'}, {'contas': ['a@test.example'], 'squad': 'Inexistente'},
                 {'contas': ['a@test.example']}, {'contas': [1], 'squad': 'Geral'}):
        assert client.post('/api/kanban/mover', json=body, headers=admin).status_code == 400
    assert client.post('/api/kanban/excluir', json={'contas': []}, headers=admin).status_code == 400


def test_advances_and_traffic_light_are_off_by_default(client, admin, monkeypatch):
    seed(monkeypatch)
    monkeypatch.delenv('AVANCOS_PANEL_ENABLED')
    def forbidden(*args, **kwargs):
        raise AssertionError('Avanços não deveriam ser consultados com o painel desligado.')
    monkeypatch.setattr('db.avancos_api.total_por_cliente', forbidden)
    monkeypatch.setattr('db.avancos_api.status_por_cliente', forbidden)
    monkeypatch.setattr('db.avancos_api.avancos_dia_do_cliente', forbidden)
    assert client.get('/api/auth/me').json['avancosAtivo'] is False
    item = client.get('/api/analise-contas').json['squads']['Sem squad'][0]
    assert item['avancos'] is None and item['statusAvanco'] is None
    assert client.get('/api/squads').json['squads']['Sem squad'][0]['avancosHoje'] is None
    analysis = client.get('/api/analise-cliente?cliente=Cliente%20A').json
    assert analysis['statusAvanco'] is None
    assert all(day['avancos'] is None for day in analysis['dias'])
    monkeypatch.setenv('AVANCOS_PANEL_ENABLED', 'true')
    assert client.get('/api/auth/me').json['avancosAtivo'] is True


def test_partial_exclusion_hides_the_whole_client_even_with_new_account(client, admin, monkeypatch):
    available(monkeypatch)
    monkeypatch.setattr('db.avancos_api.cliente_da_conta', lambda account: 'Cliente C')
    crud.atualiza_registros(pd.DataFrame([metric()]))
    client.post('/api/kanban/excluir', json={'contas': ['a@test.example']}, headers=admin)
    nova = metric('300'); nova['conta'] = 'a2@test.example'
    crud.atualiza_registros(pd.DataFrame([nova]))
    assert names(dashboard.get_squads_summary()) == {}
    assert [c['cliente'] for c in client.get('/api/kanban').json['colunas']['Excluídos']] == ['Cliente C']


def test_kanban_writes_require_csrf_token(client, admin):
    for path, body in (('mover', {'contas': ['a@test.example'], 'squad': 'Geral'}),
                       ('excluir', {'contas': ['a@test.example']}), ('restaurar', {'contas': ['a@test.example']})):
        assert client.post('/api/kanban/' + path, json=body).status_code == 403


def test_kanban_rejects_oversized_account_names(client, admin):
    assert client.post('/api/kanban/excluir', json={'contas': ['x' * 256]}, headers=admin).status_code == 400
