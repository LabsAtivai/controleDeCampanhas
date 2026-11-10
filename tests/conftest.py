import os
import tempfile
from pathlib import Path

import pytest

DIRECTORY = tempfile.TemporaryDirectory(prefix='ativa-tests-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(DIRECTORY.name) / 'audit.db').replace('\\', '/')
os.environ['SECRET_KEY'] = 'test-secret-not-used-in-production-123456789'
os.environ['COOKIE_SECURE'] = 'false'
os.environ['TRUST_PROXY'] = 'false'
os.environ['LISTAS_SQUAD_DATABASE_URL'] = ''
os.environ['CREDENTIALS_API_URL'] = 'https://credentials.invalid'
os.environ['CREDENTIALS_API_KEY'] = 'test-only'
os.environ['AVANCOS_API_URL'] = 'https://advances.invalid/api'
os.environ['AVANCOS_API_KEY'] = ''
os.environ['ALLOW_LEGACY_TOKEN'] = 'false'
os.environ['ADMIN_EMAIL'] = ''
os.environ['ADMIN_PASSWORD'] = ''
os.environ['GOOGLE_SHEETS_ENABLED'] = 'false'
os.environ['SNOV_REQUEST_INTERVAL'] = '0'
os.environ['ALERT_WEBHOOK_URL'] = ''

from db.models import Base
from db.session import engine


@pytest.fixture(scope='session', autouse=True)
def dispose_database():
    yield
    engine.dispose()
    DIRECTORY.cleanup()


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch):
    from db.migrations import migrate
    from db import avancos_api
    Base.metadata.drop_all(engine)
    migrate()
    avancos_api._cache.clear()
    avancos_api.begin_request()
    # Accidental production network calls must fail immediately, including in new tests.
    def forbidden(*args, **kwargs):
        raise AssertionError('Rede externa não autorizada em teste.')
    monkeypatch.setattr('httpx.request', forbidden)
    monkeypatch.setattr('requests.get', forbidden)
    monkeypatch.setattr('httpx.Client.get', forbidden)
    yield


@pytest.fixture
def app():
    from webapp import create_app
    return create_app({'TESTING': True})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin(client):
    from core.security import save_user
    save_user('admin@example.test', 'Very-Strong-Test-Password', 'admin')
    response = client.post('/api/auth/login', json={'email': 'admin@example.test', 'password': 'Very-Strong-Test-Password'})
    assert response.status_code == 200
    return {'X-CSRF-Token': response.json['csrf']}


@pytest.fixture
def viewer(client):
    from core.security import save_user
    save_user('viewer@example.test', 'Very-Strong-Test-Password', 'viewer')
    response = client.post('/api/auth/login', json={'email': 'viewer@example.test', 'password': 'Very-Strong-Test-Password'})
    return {'X-CSRF-Token': response.json['csrf']}
