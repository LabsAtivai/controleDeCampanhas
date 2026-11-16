from datetime import datetime, date
from unittest.mock import Mock

import pandas as pd
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import crud
from db.models import Dados, Campanha, ContaSnovio
from db.session import engine
from rotina import acao


def account(id='a', email='a@test.example'):
    return {'id': id, 'email': email, 'email_snovio': email}


def campaign(id=100, status='Active'):
    return pd.DataFrame([{'id': id, 'campaign': 'Campanha', 'list_id': None, 'status': status}])


def metric(id='100', day='2026-01-01', sent=10):
    return {'conta': 'A@TEST.EXAMPLE', 'campanha': 'Campanha', 'id_conta': id, 'data': day,
        'total_contacted': sent, 'emails_sent': sent, 'delivered': sent, 'email_opens': 1, 'link_clicks': 1, 'email_replies': 0}


def test_metrics_atomic_idempotent_upsert():
    crud.atualiza_registros(pd.DataFrame([metric()]))
    crud.atualiza_registros(pd.DataFrame([metric(sent=20)]))
    with Session(engine) as db:
        rows = db.scalars(select(Dados)).all()
        assert len(rows) == 1
        assert rows[0].emails_sent == 20
        assert rows[0].conta == 'a@test.example'


def test_campaign_reconciliation_preserves_unselected():
    crud.sincroniza_campanhas([(account(), campaign()), (account('b', 'b@test.example'), campaign(200))])
    crud.sincroniza_campanhas([(account(), pd.DataFrame())])
    active = crud.get_campanhas_ativas()
    assert active['id'].tolist() == [200]
    assert len(crud.get_campanhas_ativas(historico=True)) == 2


def test_inactive_accounts_removed_only_on_complete_sync():
    crud.sincroniza_campanhas([(account(), campaign())])
    crud.sincroniza_campanhas([], active_ids=set())
    assert crud.get_campanhas_ativas().empty
    assert len(crud.get_campanhas_ativas(historico=True)) == 1


def test_master_publication_uses_complete_db(monkeypatch):
    crud.sincroniza_campanhas([(account(), campaign()), (account('b', 'b@test.example'), campaign(200))])
    client = Mock()
    monkeypatch.setenv('GOOGLE_MASTER_SHEET_ID', 'test-sheet')
    monkeypatch.setattr(acao, 'google_client', lambda: client)
    publish = Mock()
    monkeypatch.setattr(acao, '_replace_sheet', publish)
    acao.atualiza_aba_campanhas_master()
    frame = publish.call_args.args[1]
    assert set(frame['id']) == {100, 200}


def test_sheet_write_is_one_atomic_request(monkeypatch):
    sheet = Mock(id=10, rows=100, cols=20)
    acao._replace_sheet(sheet, pd.DataFrame([{'name': '=HYPERLINK("bad")'}]))
    request = sheet.client.sheet.batch_update.call_args.args[1]
    assert len(request) == 1
    assert 'updateCells' in request[0]
    assert request[0]['updateCells']['rows'][1]['values'][0]['userEnteredValue']['stringValue'].startswith('=')
    sheet.clear.assert_not_called()


def prepare_collection(monkeypatch):
    credentials = pd.DataFrame([{'Email Snovio':'A@TEST.EXAMPLE', 'Client id':'dummy', 'Client Secret':'dummy'}])
    monkeypatch.setattr(acao.api, 'senhas', lambda: credentials)
    monkeypatch.setattr(acao.api, 'gera_token', lambda *args: 'dummy')
    monkeypatch.setattr(acao.time, 'sleep', lambda *args: None)
    monkeypatch.setattr(acao, 'hoje_sp', lambda: date(2026, 11, 10))


def test_all_failures_never_report_success(monkeypatch):
    crud.sincroniza_campanhas([(account(), campaign(status='Paused'))])
    prepare_collection(monkeypatch)
    monkeypatch.setattr(acao.api, 'get_campaign_analytics', Mock(side_effect=RuntimeError('upstream failed')))
    with pytest.raises(acao.CollectionError) as failure:
        acao.extrai_dia_anterior_custom('2026-01-01')
    assert failure.value.result['collected'] == 0
    assert not failure.value.partial


def test_partial_collection_persists_successes_and_reports_failures(monkeypatch):
    crud.sincroniza_campanhas([(account(), pd.concat([campaign(100), campaign(101)]))])
    prepare_collection(monkeypatch)
    def analytics(token, id, *args):
        if id == 101:
            raise RuntimeError('simulated failure')
        return {k: v for k, v in metric().items() if k not in {'conta', 'campanha', 'id_conta', 'data'}}
    monkeypatch.setattr(acao.api, 'get_campaign_analytics', analytics)
    with pytest.raises(acao.CollectionError) as failure:
        acao.extrai_dia_anterior_custom('2026-01-01')
    assert failure.value.partial
    assert failure.value.result['collected'] == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Dados)) == 1


def test_backfill_includes_paused_campaigns(monkeypatch):
    crud.sincroniza_campanhas([(account(), campaign(status='Paused'))])
    prepare_collection(monkeypatch)
    monkeypatch.setattr(acao.api, 'get_campaign_analytics', lambda *args: {k:v for k,v in metric().items() if k not in {'conta','campanha','id_conta','data'}})
    assert acao.extrai_dia_anterior_custom('2026-01-01')['collected'] == 1


def test_campaigns_without_credential_are_skipped_not_failed(monkeypatch):
    crud.sincroniza_campanhas([(account(), campaign(100)),
                               (account('b', 'b@test.example'), campaign(200))])
    prepare_collection(monkeypatch)
    monkeypatch.setattr(acao.api, 'get_campaign_analytics', lambda *args: {k:v for k,v in metric().items() if k not in {'conta','campanha','id_conta','data'}})
    result = acao.extrai_dia_anterior_custom('2026-01-01')
    assert result['collected'] == 1
    assert result['skipped'] == ['200']
    assert result['failed'] == []


def test_auth_rejection_on_inactive_campaign_is_skipped_but_active_fails(monkeypatch):
    class Rejected(Exception):
        status = 401
    crud.sincroniza_campanhas([(account(), pd.concat([campaign(100, 'Archived'), campaign(101, 'Active')]))])
    prepare_collection(monkeypatch)
    monkeypatch.setattr(acao.api, 'get_campaign_analytics', Mock(side_effect=Rejected()))
    with pytest.raises(acao.CollectionError) as failure:
        acao.extrai_dia_anterior_custom('2026-01-01')
    assert failure.value.result['skipped'] == ['100']
    assert [f['campaign'] for f in failure.value.result['failed']] == ['101']
