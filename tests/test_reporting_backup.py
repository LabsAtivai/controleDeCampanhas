import json
from datetime import datetime

import pandas as pd
import pytest
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import avancos_api, crud, dashboard
from db.models import Dados, SquadMapping, DataRepair
from db.session import engine
from tests.test_data_collection import metric


def available(monkeypatch):
    monkeypatch.setattr(avancos_api, 'cliente_da_conta', lambda account: 'Cliente')
    monkeypatch.setattr(avancos_api, 'total_por_cliente', lambda *args: {'cliente': 2})
    monkeypatch.setattr(avancos_api, 'status_por_cliente', lambda: {'cliente': 'verde'})
    monkeypatch.setattr(avancos_api, 'tem_vinculo', lambda *args: True)


def test_multiple_accounts_use_union_of_sending_days(monkeypatch):
    available(monkeypatch)
    row = metric('200', '2026-01-02'); row['conta'] = 'b@test.example'
    crud.atualiza_registros(pd.DataFrame([metric(), row]))
    with Session(engine) as db:
        db.add_all([SquadMapping(campanha_id='100', squad='Geral'), SquadMapping(campanha_id='200', squad='Geral')]); db.commit()
    item = dashboard.get_contas_resumo()['Geral'][0]
    assert item['diasDisparos'] == 2
    assert item['emailsSent'] == 20
    assert item['avancos'] == 2


def test_unmapped_accounts_are_visible_and_multiple_squads_do_not_duplicate_advances(monkeypatch):
    available(monkeypatch)
    crud.atualiza_registros(pd.DataFrame([metric()]))
    assert dashboard.get_contas_resumo()['Sem squad'][0]['emailsSent'] == 10
    row = metric('200'); row['conta'] = 'b@test.example'
    crud.atualiza_registros(pd.DataFrame([row]))
    with Session(engine) as db:
        db.add_all([SquadMapping(campanha_id='100', squad='Geral'), SquadMapping(campanha_id='200', squad='Onboarding')]); db.commit()
    result = dashboard.get_contas_resumo()
    assert result['Geral'][0]['avancos'] == 2
    assert sum(item['avancos'] for squad in result.values() for item in squad) == 2


def test_single_date_bound_is_applied(monkeypatch):
    crud.atualiza_registros(pd.DataFrame([metric(), metric(day='2026-01-09')]))
    monkeypatch.setattr(avancos_api, 'contas_do_cliente', lambda *args: ['a@test.example'])
    monkeypatch.setattr(avancos_api, 'avancos_dia_do_cliente', lambda *args: {})
    assert [r['data'] for r in crud.get_analise_cliente('Cliente', inicio='2026-01-09')] == ['2026-01-09']


def test_expired_cache_survives_upstream_failure_and_restart(monkeypatch):
    now = 1800000000.0
    monkeypatch.setattr(avancos_api.time, 'time', lambda: now)
    assert avancos_api._cached('test', lambda: {'count': 2}) == {'count': 2}
    avancos_api._cache.clear()
    avancos_api.begin_request()
    monkeypatch.setattr(avancos_api.time, 'time', lambda: now + 61)
    def unavailable():
        raise requests.ConnectionError('offline')
    assert avancos_api._cached('test', unavailable) == {'count': 2}
    assert avancos_api.warnings()


def test_unavailable_mapping_is_attempted_once_per_request(monkeypatch):
    from unittest.mock import Mock
    upstream = Mock(side_effect=requests.ConnectionError('offline'))
    monkeypatch.setattr(avancos_api, '_get', upstream)
    assert avancos_api.cliente_da_conta('a@test.example') == 'a@test.example'
    assert avancos_api.cliente_da_conta('b@test.example') == 'b@test.example'
    assert avancos_api.cliente_da_conta('c@test.example') == 'c@test.example'
    assert upstream.call_count == 1


def test_missing_integration_is_not_reported_as_zero(monkeypatch):
    available(monkeypatch)
    crud.atualiza_registros(pd.DataFrame([metric()]))
    def unavailable(*args):
        raise avancos_api.IntegrationUnavailable('offline')
    monkeypatch.setattr(avancos_api, 'total_por_cliente', unavailable)
    monkeypatch.setattr(avancos_api, 'status_por_cliente', unavailable)
    result = dashboard.get_contas_resumo()['Sem squad'][0]
    assert result['avancos'] is None
    assert result['statusAvanco'] == 'indisponivel'


def test_semaphore_only_interested_by_default(monkeypatch):
    monkeypatch.delenv('SEMAFORO_TIPOS', raising=False)
    assert avancos_api._conta_no_semaforo('Interessado')
    assert not avancos_api._conta_no_semaforo('Encaminhamento')
    assert not avancos_api._conta_no_semaforo('Apresentação')
    assert not avancos_api._conta_no_semaforo('Nutrição')


def test_backup_roundtrip_is_restorable_and_preserves_metrics(tmp_path):
    from manage import backup, restore
    crud.atualiza_registros(pd.DataFrame([metric()]))
    path = backup(tmp_path / 'snapshot.jsonl.gz')
    with engine.begin() as conn:
        conn.execute(Dados.__table__.delete())
    with pytest.raises(ValueError):
        restore(path)
    restore(path, replace=True)
    with Session(engine) as db:
        assert db.scalar(select(Dados)).emails_sent == 10


def test_migration_archives_duplicates_before_creating_unique_index():
    from db.migrations import migrate
    index = next(i for i in Dados.__table__.indexes if i.unique)
    index.drop(engine)
    with engine.begin() as conn:
        conn.execute(Dados.__table__.insert(), [{'id_conta':'100','data':'2026-01-01','emails_sent':1}, {'id_conta':'100','data':'2026-01-01','emails_sent':2}])
    with pytest.raises(RuntimeError):
        migrate()
    migrate(resolve_duplicates=True)
    with Session(engine) as db:
        assert db.scalar(select(Dados)).emails_sent == 2
        assert json.loads(db.scalar(select(DataRepair)).payload)['emails_sent'] == 1
