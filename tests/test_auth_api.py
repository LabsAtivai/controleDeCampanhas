import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from core.security import save_user
from db.models import Job, AuditEvent
from db.session import engine


def test_authentication_csrf_and_logout(client, admin):
    assert client.get('/api/auth/me').json['role'] == 'admin'
    assert client.post('/api/run/campanhas').status_code == 403
    assert client.post('/api/run/campanhas', headers=admin).status_code == 202
    assert client.post('/api/auth/logout', headers=admin).status_code == 200
    assert client.get('/api/jobs').status_code == 401


def test_viewer_cannot_operate_or_manage_users(client, viewer):
    assert client.get('/api/jobs').status_code == 403
    assert client.post('/api/run/campanhas', headers=viewer).status_code == 403
    assert client.get('/api/users').status_code == 403
    assert client.get('/api/auth/me').status_code == 200


def test_password_change_revokes_session(client, admin):
    save_user('admin@example.test', 'Another-Strong-Password', 'admin')
    assert client.get('/api/auth/me').status_code == 401


def test_shared_token_disabled_by_default(client):
    assert client.get('/api/jobs', headers={'X-API-Token': 'test'}).status_code == 401


def test_login_limit(client):
    for _ in range(10):
        assert client.post('/api/auth/login', json={'email': 'unknown@test.example', 'password': 'wrong'}).status_code == 401
    assert client.post('/api/auth/login', json={'email': 'unknown@test.example', 'password': 'wrong'}).status_code == 429


@pytest.mark.parametrize('body', [[1], None, 'bad', {'email': 12, 'password': []}])
def test_bad_login_json(client, body):
    assert client.post('/api/auth/login', json=body).status_code == 400


@pytest.mark.parametrize('body', [[1], {'inicio': 123}, {'inicio': '2026-02-30'},
    {'inicio': '2026-01-02', 'fim': '2026-01-01'}, {'inicio': '2026-01-01', 'fim': '2026-02-01'}])
def test_custom_validation(client, admin, body):
    assert client.post('/api/run/custom', json=body, headers=admin).status_code == 400


def test_queue_is_persistent_and_audited(client, admin):
    response = client.post('/api/run/campanhas', headers=admin)
    assert response.status_code == 202
    with Session(engine) as db:
        job = db.get(Job, response.json['job_id'])
        assert job.status == 'queued'
        assert job.actor == 'admin@example.test'
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == 'job.queued'))


def test_retired_local_advances(client, admin):
    assert client.post('/api/avancos', json={'quantidade': -1}, headers=admin).status_code == 410


def test_cursor_and_period_validation(client, admin):
    assert client.get('/api/logs?since=abc').status_code == 400
    assert client.get('/api/logs?since=-1').status_code == 400
    assert client.get('/api/analise-contas?inicio=2026-02-30').status_code == 400
    assert client.get('/api/ready').status_code == 200


def test_session_cookie_and_csp(client, admin):
    response = client.get('/api/auth/me')
    assert "script-src 'self'" in response.headers['Content-Security-Policy']
    assert 'unsafe-eval' not in response.headers['Content-Security-Policy']
    assert response.headers['Cache-Control'] == 'no-store'


def test_user_management_and_self_protection(client, admin):
    assert client.post('/api/users', json={'email': 'staff@example.test', 'password': 'Strong-Password-123', 'role': 'viewer'}, headers=admin).status_code == 201
    assert any(u['email'] == 'staff@example.test' for u in client.get('/api/users').json)
    assert client.post('/api/users', json={'email': 'admin@example.test', 'password': 'Strong-Password-123', 'role': 'viewer'}, headers=admin).status_code == 400
