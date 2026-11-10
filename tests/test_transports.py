from unittest.mock import Mock

import httpx
import pytest

from rotina import api, credentials_api, acao
from db import crud
from tests.test_data_collection import account, campaign, metric, prepare_collection


def test_snov_retries_rate_limit_without_accepting_error_body(monkeypatch):
    responses = [httpx.Response(429), httpx.Response(200, json={'access_token': 'test-only'})]
    request = Mock(side_effect=responses)
    monkeypatch.setattr(httpx, 'request', request)
    monkeypatch.setattr(api.time, 'sleep', lambda *args: None)
    assert api.gera_token('id', 'secret') == 'test-only'
    assert request.call_count == 2


def test_bad_token_response_is_an_error(monkeypatch):
    monkeypatch.setattr(api, '_request', lambda *args, **kwargs: {'error': 'denied'})
    with pytest.raises(api.SnovError):
        api.gera_token('id', 'secret')


def test_negative_upstream_metric_is_rejected(monkeypatch):
    values = {k: 0 for k in ['total_contacted','emails_sent','delivered','email_opens','link_clicks','email_replies']}
    values['emails_sent'] = -1
    monkeypatch.setattr(api, '_request', lambda *args, **kwargs: values)
    with pytest.raises(api.SnovError):
        api.get_campaign_analytics('test-only', '100', '2026-01-01', '2026-01-01')


def test_incomplete_credentials_pagination_never_succeeds(monkeypatch):
    monkeypatch.setattr(credentials_api, '_get', lambda *args, **kwargs: Mock(json=lambda: {'total':2,'items':[{'id':'a'}]}))
    with pytest.raises(RuntimeError, match='incompleta'):
        credentials_api._fetch_active_accounts(Mock())


def test_expired_snov_token_is_refreshed(monkeypatch):
    crud.sincroniza_campanhas([(account(), campaign())])
    prepare_collection(monkeypatch)
    token = Mock(side_effect=['old-test-token', 'new-test-token'])
    values = {k:v for k,v in metric().items() if k not in {'conta','campanha','id_conta','data'}}
    monkeypatch.setattr(api, 'gera_token', token)
    monkeypatch.setattr(api, 'get_campaign_analytics', Mock(side_effect=[api.SnovError('expired', 401), values]))
    assert acao.extrai_dia_anterior_custom('2026-01-01')['collected'] == 1
    assert token.call_count == 2
